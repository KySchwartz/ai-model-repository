import os
import sys
import zipfile
import importlib.util
import subprocess
import shutil
import traceback
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

router = APIRouter()

# --- PLATFORM INFRASTRUCTURE ---
# We pre-define these to prevent re-installing heavy frameworks 
# or common formatting tools.
PRE_INSTALLED_LIBS = [
    'torch', 'torchvision', 'tensorflow', 'keras', 
    'numpy', 'pandas', 'scipy', 'skimage', 
    'pillow', 'ipython', 'cv2', 'sklearn',
    'python-docx', 'fpdf', 'python-magic'
]

BASE_WORKSPACE = "/app/workspaces"

def smart_pip_install(workspace_path: str):
    req_path = os.path.join(workspace_path, "requirements.txt")
    if not os.path.exists(req_path):
        return

    import importlib.util

    with open(req_path, 'r') as f:
        reqs = [line.strip() for line in f if line.strip() and not line.startswith('--')]

    to_install = []
    for req in reqs:
        # 1. Normalize the name (scikit-image -> skimage)
        pkg_name = req.split('==')[0].split('>=')[0].split('>')[0].strip().lower()
        import_name = pkg_name.replace('-', '_')
        
        # Specific mappings for libraries where pip name != import name
        mapping = {'scikit-image': 'skimage', 'opencv-python': 'cv2', 'opencv-python-headless': 'cv2'}
        import_name = mapping.get(pkg_name, import_name)

        # 2. ACTUALLY check if it's installed, don't just trust a list
        if importlib.util.find_spec(import_name) is None:
            to_install.append(req)

    if to_install:
        print(f"Platform installing missing requirements: {to_install}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", *to_install])

def handle_formatting(raw_result, output_path, extension):
    """Universal Output Formatter for Text-to-File models."""
    ext = extension.lower() if extension else ".txt"
    
    if ext == ".docx":
        from docx import Document
        doc = Document()
        doc.add_paragraph(str(raw_result))
        doc.save(output_path)
    elif ext == ".pdf":
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=str(raw_result))
        pdf.output(output_path)
    else:
        # Default to raw text file if no specific format is requested
        with open(output_path, "w") as f:
            f.write(str(raw_result))

@router.post("/execute")
async def execute_model(
    model_id: int,
    user_input: str,
    file_path: str,
    output_type: str = "text",
    extension: Optional[str] = None
):
    model_zip_path = f"/app/media_shared/{file_path}"
    workspace_root = os.path.join(BASE_WORKSPACE, f"model_{model_id}")
    
    # 1. Extraction & Persistence
    if not os.path.exists(workspace_root):
            os.makedirs(workspace_root, exist_ok=True)
            
            # Check if it's actually a zip before trying to extract
            if file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(model_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(workspace_root)
            else:
                # If it's just a single file (like model.py), copy it into the workspace
                import shutil
                shutil.copy(model_zip_path, os.path.join(workspace_root, "main.py"))

    # 2. Structural Discovery (Layout Agnostic)
    model_home = None
    # First, look for main.py (our standard)
    for root, dirs, files in os.walk(workspace_root):
        if "main.py" in files:
            model_home = root
            break
            
    # Fallback: If no main.py, look for ANY .py file to use as the entry point
    if not model_home:
        for root, dirs, files in os.walk(workspace_root):
            python_files = [f for f in files if f.endswith('.py')]
            if python_files:
                # Rename the first python file found to main.py so the rest of the script works
                old_path = os.path.join(root, python_files[0])
                new_path = os.path.join(root, "main.py")
                os.rename(old_path, new_path)
                model_home = root
                break

    if not model_home:
        return {"status": "error", "message": "No Python files found in upload."}

    # 3. Dynamic Environment Prep
    smart_pip_install(model_home)
    sys.path = [p for p in sys.path if BASE_WORKSPACE not in p]
    sys.path.insert(0, model_home)
    os.chdir(model_home)

    try:
        # 4. Load the Model Module
        spec = importlib.util.spec_from_file_location("dynamic_model", os.path.join(model_home, "main.py"))
        model_module = importlib.util.module_from_spec(spec)
        if "dynamic_model" in sys.modules:
            importlib.reload(model_module)
        spec.loader.exec_module(model_module)

        # 5. Core Execution
        if not hasattr(model_module, 'handle_request'):
            return {"status": "error", "message": "Model Contract Error: handle_request function missing."}

        # The model does its work here
        raw_result = model_module.handle_request(user_input)

        # 6. Response Strategy
        # The platform determines how to package the result based on requested output_type
        if output_type == "file":
            output_filename = f"output_{model_id}{extension or '.txt'}"
            final_media_path = f"/app/media_shared/temp_uploads/{output_filename}"
            os.makedirs(os.path.dirname(final_media_path), exist_ok=True)

            # Option A: Model returned a specialized object (like a PIL image)
            if hasattr(raw_result, 'save'):
                raw_result.save(final_media_path)
            
            # Option B: Model returned a path to a file it generated itself
            elif isinstance(raw_result, str) and os.path.exists(raw_result):
                shutil.move(raw_result, final_media_path)
            
            # Option C: Model returned text/data that the platform needs to format
            else:
                handle_formatting(raw_result, final_media_path, extension)
                
            return {
                "status": "success",
                "message": "Model executed and file generated",
                "download_url": f"temp_uploads/{output_filename}"
            }

        # Otherwise, return raw data (JSON/Text)
        return {"status": "success", "message": str(raw_result)}

    except Exception as e:
        return {
            "status": "error", 
            "message": f"Runtime Error: {str(e)}", 
            "traceback": traceback.format_exc()
        }