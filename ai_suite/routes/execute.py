import os
import io
import sys
import uuid
import json
import zipfile
import subprocess
import shutil
import docker
import importlib.util
import ast
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from routes.provisioner import scan_for_dependencies, download_assets

router = APIRouter()
client = docker.from_env()

WORKSPACE_ROOT = "/app/workspaces"
CACHE_ROOT = "/app/workspaces/huggingface"
GLOBAL_CACHE = "/app/workspaces/global_model_cache"

class ExecutionRequest(BaseModel):
    model_id: int
    user_input: str
    file_path: str
    output_type: str = "text"
    extension: str = None

def find_handle_request_file(directory):
    """Finds the .py file containing the handle_request function."""
    # 1. Check main.py first as a priority
    main_py = os.path.join(directory, "main.py")
    if os.path.exists(main_py):
        with open(main_py, 'r', encoding='utf-8') as f:
            if "def handle_request" in f.read():
                return "main.py"

    # 2. Scan all other .py files
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                with open(full_path, 'r', encoding='utf-8') as f:
                    if "def handle_request" in f.read():
                        return os.path.relpath(full_path, directory)
    return None

def smart_pip_install(model_id, model_home):
    req_path = os.path.join(model_home, "requirements.txt")
    deps_dir = os.path.join(model_home, "deps")
    os.makedirs(deps_dir, exist_ok=True)

    # These packages are pre-installed in the model-sandbox Docker image.
    BLOCKLIST = [
        'torch', 'tensorflow', 'nvidia', 'cuda', 'torchvision', 'transformers', 
        'huggingface-hub', 'scikit-learn', 'scikit-image', 'pandas', 'numpy', 
        'pillow', 'python-docx', 'fpdf', 'opencv-python', 'ipython'
    ]
    cleaned_reqs = [] 
    to_install = []
    
    mapping = {
        'scikit-image': 'skimage', 
        'opencv-python': 'cv2', 
        'pillow': 'PIL',
        'scikit-learn': 'sklearn'
    }
    
    if os.path.exists(req_path):
        with open(req_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip().lower()
            if not line or line.startswith(('#', '--')):
                continue
            
            pkg_name = line.split('==')[0].split('>=')[0].split('>')[0].strip()
            
            if any(blocked in pkg_name for blocked in BLOCKLIST):
                print(f"DEBUG: Skipping pre-installed package: {pkg_name}")
                continue

            cleaned_reqs.append(line)

            import_name = mapping.get(pkg_name, pkg_name).replace('-', '_')
            pkg_path = os.path.join(deps_dir, import_name)
            if not os.path.exists(pkg_path):
                to_install.append(line)

        if to_install:
            print(f"DEBUG: Installing required local deps: {to_install}")
            # SECURITY: Run pip in a temporary container, NOT in the orchestrator.
            # This prevents malicious setup.py scripts from accessing the Docker socket.
            pip_command = [
                "pip", "install", "--no-cache-dir",
                "--target", f"/workspace/model_{model_id}/deps",
                "--extra-index-url", "https://download.pytorch.org/whl/cpu"
            ] + to_install
            
            client.containers.run(
                image="python:3.11-slim",
                command=pip_command,
                volumes={'ai_workspaces': {'bind': '/workspace', 'mode': 'rw'}},
                network_mode="bridge",
                remove=True
            )

    # Scanning should run regardless of whether requirements.txt exists
    print(f"DEBUG: Scanning {model_home} for any model dependencies...")
    deps = scan_for_dependencies(model_home)

    if any(deps.values()):
        print(f"DEBUG: Provisioning found assets: {deps}")
        download_assets(deps, GLOBAL_CACHE)

def run_model_in_sandbox(model_home, entry_file, user_input):
    """Runs the model in a network-isolated container with resource limits."""
    # In DooD, we mount the named volume 'ai_workspaces' directly.
    rel_model_path = os.path.relpath(model_home, WORKSPACE_ROOT)
    
    # Ensure the sandbox can access uploaded files in temp_uploads
    sandbox_user_input = user_input
    if user_input.startswith("temp_uploads/"):
        sandbox_user_input = os.path.join("/app/media", user_input)

    volumes = {
        'ai_workspaces': {'bind': '/workspace', 'mode': 'rw'},
        'media_data': {'bind': '/app/media', 'mode': 'ro'}
    }

    try:
        container_result = client.containers.run(
            image="model-sandbox",
            entrypoint=["python", "/sandbox/sandbox_runner.py"], 
            command=[rel_model_path, entry_file, sandbox_user_input],
            volumes=volumes,
            environment={
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "HF_HUB_OFFLINE": "1",
                "HF_HOME": "/workspace/global_model_cache",
                "TORCH_HOME": "/workspace/global_model_cache/torch"
            },
            network_disabled=True,
            read_only=True,          # SECURITY: Prevent modification of the container root FS
            mem_limit="2g",          # Increased to 2GB to prevent OOM (Exit Code 137)
            nano_cpus=2000000000,    # Increased to 2.0 CPUs for better performance
            working_dir=os.path.join("/workspace", rel_model_path),
            tmpfs={'/tmp': ''},      # Allow small temporary writes in RAM
            remove=True
        )
        # Clean up output to ensure we only parse the JSON part
        decoded_output = container_result.decode('utf-8').strip().split('\n')[-1]
        return json.loads(decoded_output)
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@router.post("/execute")
async def execute_model(request: ExecutionRequest):
    model_work_dir = os.path.join(WORKSPACE_ROOT, f"model_{request.model_id}")
    zip_full_path = os.path.join("/app/media", request.file_path)

    try:
        # 1. Extraction (Same as your original)
        if not os.path.exists(model_work_dir):
            os.makedirs(model_work_dir, exist_ok=True)
            if request.file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(zip_full_path, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        filename = os.path.basename(member)
                        if not filename: continue # Skip directories
                        target_path = os.path.join(model_work_dir, member)
                        if os.path.commonprefix([os.path.abspath(target_path), os.path.abspath(model_work_dir)]) == os.path.abspath(model_work_dir):
                            zip_ref.extract(member, model_work_dir)
            else:
                shutil.copy(zip_full_path, os.path.join(model_work_dir, "main.py"))

        # 2. Find the model home and the entry point file
        model_home = None
        for root, dirs, files in os.walk(model_work_dir):
            if any(f.endswith(".py") for f in files):
                model_home = root
                entry_file = find_handle_request_file(model_home)
                if entry_file:
                    break
        
        if not model_home or not entry_file:
            raise HTTPException(status_code=400, detail="Could not find handle_request in any Python file.")

        # 3. Dependencies
        smart_pip_install(request.model_id, model_home)

        # 4. Run (using the restored mount strategy)
        result_json = run_model_in_sandbox(model_home, entry_file, request.user_input)
        
        if result_json.get("status") == "error":
            return {"status": "error", "message": result_json.get("message")}

        # If the model service expects a file output, process it here
        if request.output_type == "file":
            return handle_file_output(result_json.get("data", ""), request.model_id, request.extension, model_home)

        return {"status": "success", "message": result_json.get("data", "")}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def handle_file_output(text, model_id, extension, model_home=None):
    ext = (extension or ".txt").lower()
    file_name = f"output_{model_id}{ext}"
    save_path = f"/app/media/temp_uploads/{file_name}"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Check if 'text' is actually a filename generated inside the sandbox
    if model_home:
        # SECURITY: Ensure 'text' is strictly a filename to prevent path traversal
        potential_file = os.path.join(model_home, os.path.basename(str(text)))
        if os.path.isfile(potential_file):
            # If the dev created a file with a specific extension, respect it over the default
            _, actual_ext = os.path.splitext(potential_file)
            if actual_ext and actual_ext.lower() != ext:
                file_name = f"output_{model_id}{actual_ext.lower()}"
                save_path = os.path.join(os.path.dirname(save_path), file_name)

            shutil.copy(potential_file, save_path)
            return {
                "status": "success",
                "message": "File generated",
                "download_url": f"temp_uploads/{file_name}"
            }

    if ext == ".docx":
        doc = Document()
        doc.add_paragraph(str(text))
        doc.save(save_path)
    elif ext == ".pdf":
        c = canvas.Canvas(save_path, pagesize=letter)
        c.drawString(100, 750, str(text))
        c.save()
    else:
        with open(save_path, "w") as f:
            f.write(str(text))

    return {
        "status": "success",
        "message": "File generated",
        "download_url": f"temp_uploads/{file_name}"
    }