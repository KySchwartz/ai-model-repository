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
GLOBAL_CACHE = "/app/ai_workspaces/global_model_cache"

class ExecutionRequest(BaseModel):
    model_id: int
    user_input: str
    file_path: str
    output_type: str = "text"
    extension: str = None

def smart_pip_install(model_home):
    req_path = os.path.join(model_home, "requirements.txt")
    if not os.path.exists(req_path):
        return

    deps_dir = os.path.join(model_home, "deps")
    os.makedirs(deps_dir, exist_ok=True)

    with open(req_path, 'r') as f:
        lines = f.readlines()

    BLOCKLIST = ['torch', 'tensorflow', 'nvidia', 'cuda', 'torchvision']
    cleaned_reqs = [] 
    to_install = []
    
    mapping = {
        'scikit-image': 'skimage', 
        'opencv-python': 'cv2', 
        'pillow': 'PIL',
        'scikit-learn': 'sklearn'
    }

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
        sys.path.insert(0, deps_dir)
        exists = importlib.util.find_spec(import_name) is not None
        sys.path.pop(0)

        if not exists:
            to_install.append(line)

    if to_install:
        print(f"DEBUG: Installing required local deps: {to_install}")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--no-cache-dir", 
            "--target", deps_dir,
            "--extra-index-url", "https://download.pytorch.org/whl/cpu",
            *to_install
        ])

    # FIXED: This block must be indented to stay inside the function!
    print(f"DEBUG: Scanning {model_home} for any model dependencies...")
    deps = scan_for_dependencies(model_home)
    
    if any(deps.values()):
        print(f"DEBUG: Provisioning found assets: {deps}")
        download_assets(deps, GLOBAL_CACHE)

def run_model_in_sandbox(model_home, user_input):
    # 1. Host Paths
    abs_model_path = os.path.abspath(model_home)
    abs_uploads_path = "/app/media/temp_uploads"
    abs_global_cache = os.path.abspath(GLOBAL_CACHE)

    # DEBUG: This will show up in your ai_suite terminal
    print(f"DEBUG: Mounting {abs_model_path} to container /app")

    # 2. THE FIX: Mount the specific folder directly to /app
    volumes = {
        abs_model_path: {'bind': '/app', 'mode': 'rw'},
        abs_global_cache: {'bind': '/root/.cache', 'mode': 'ro'},
        abs_uploads_path: {'bind': '/app/temp_uploads', 'mode': 'rw'}
    }

    env_vars = {
        "HF_HOME": "/root/.cache/huggingface",
        "TORCH_HOME": "/root/.cache/torch",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "PYTHONPATH": "/app/deps" 
    }

    try:
        container_output = client.containers.run(
            image="model-sandbox",
            command=["python", "main.py", user_input], # Simplified path
            volumes=volumes,
            environment=env_vars,
            network_disabled=False, 
            remove=True,
            stdout=True,
            stderr=True,
            working_dir="/app" # This makes main.py local to the command
        )
        
        raw_output = container_output.decode('utf-8').strip()
        
        for line in reversed(raw_output.splitlines()):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    return json.loads(line)
                except ValueError:
                    continue
                    
        return {"status": "error", "message": f"Malformed output from sandbox: {raw_output}"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/execute")
async def execute_model(request: ExecutionRequest):
    model_work_dir = os.path.join(WORKSPACE_ROOT, f"model_{request.model_id}")
    zip_full_path = os.path.join("/app/media", request.file_path)

    try:
        # 1. Persistence & Extraction
        if not os.path.exists(model_work_dir):
            os.makedirs(model_work_dir, exist_ok=True)
            if request.file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(zip_full_path, 'r') as zip_ref:
                    zip_ref.extractall(model_work_dir)
            else:
                shutil.copy(zip_full_path, os.path.join(model_work_dir, "main.py"))

        # 2. Structural Discovery
        model_home = None
        for root, dirs, files in os.walk(model_work_dir):
            if "main.py" in files:
                model_home = root
                break
        
        if not model_home:
            raise HTTPException(status_code=400, detail="No main.py found.")

        # 3. SMART Installation
        smart_pip_install(model_home)

        # 4. Sandbox Execution
        result_json = run_model_in_sandbox(model_home, request.user_input)
        
        # FIXED: Standardized error return so the frontend doesn't show "None"
        if result_json.get("status") == "error":
            return {"status": "error", "message": result_json.get("message")}

        raw_output = result_json.get("data", "")

        # 5. Formatting
        if request.output_type == "file":
            return handle_file_output(raw_output, request.model_id, request.extension)
        
        return {"status": "success", "message": str(raw_output)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def handle_file_output(text, model_id, extension):
    ext = (extension or ".txt").lower()
    file_name = f"output_{model_id}{ext}"
    save_path = f"/app/media/temp_uploads/{file_name}"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

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