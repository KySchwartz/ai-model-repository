import os
import sys
import zipfile
import importlib.util
import subprocess
import shutil
import traceback
import ast
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from pydantic import BaseModel
from docx import Document
import fitz

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
        #import_name = pkg_name.replace('-', '_')
        
        # FIX: Auto-correct legacy package names that fail on modern Python
        if pkg_name == 'pil':
            req = 'Pillow'
            pkg_name = 'pillow'
        elif pkg_name == 'sklearn':
            req = 'scikit-learn'
            pkg_name = 'scikit-learn'

        # Specific mappings for libraries where pip name != import name
        mapping = {
            'scikit-image': 'skimage', 
            'opencv-python': 'cv2', 
            'opencv-python-headless': 'cv2',
            'pillow': 'PIL',
            'scikit-learn': 'sklearn'
        }
        #import_name = mapping.get(pkg_name, import_name)
        import_name = mapping.get(pkg_name, pkg_name)

        # 2. ACTUALLY check if it's installed, don't just trust a list
        try:
            if importlib.util.find_spec(import_name) is None:
                to_install.append(req)
        except (ImportError, ValueError):
            to_install.append(req)

    if to_install:
        try:
            print(f"Attempting to install: {to_install}")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "--no-cache-dir", *to_install
            ], timeout=60) # Add a timeout so it doesn't hang forever
        except subprocess.CalledProcessError as e:
            cleaned = [r.split('==')[0] for r in to_install]
            subprocess.check_call([sys.executable, "-m", "pip", "install", *cleaned])
            # Instead of raising a hard error, we return a message
            return (f"Library Installation Failed: {to_install}. Check version compatibility."
                    "This often happens if a library version is incompatible with Python 3.11. "
                    "Try removing the version number from requirements.txt.")
    return None

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

def is_binary(file_path):
    """Check if a file contains null bytes (indicating it's binary data)."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' in chunk
    except:
        return True
    
def validate_main_code(file_path):
    """
    Statically inspects the file to see if 'handle_request' is defined.
    This is safer than importing because it doesn't execute any code.
    """
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'handle_request':
                return True
    except Exception:
        return False
    return False

def extract_text_word_pdf(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    
    # List of formats we WANT to convert to strings
    if ext == '.docx':
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    
    elif ext == '.pdf':
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    
    elif ext == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    # CRITICAL: For Excel, Images, and CSVs, DO NOT read the file.
    # Return the PATH string so the model can use its own library (like pandas).
    return file_path

class ExecutionRequest(BaseModel):
    model_id: int
    user_input: str
    file_path: str
    output_type: str = "text"
    extension: Optional[str] = None

@router.post("/execute")
async def execute_model(request: ExecutionRequest):
    # Extract variables from the request body
    model_id = request.model_id
    user_input = request.user_input
    file_path = request.file_path
    output_type = request.output_type
    extension = request.extension

    try:
        model_zip_path = f"/app/media/{file_path}"
        workspace_root = os.path.join(BASE_WORKSPACE, f"model_{model_id}")
        
        # 1. Extraction & Persistence
        # Always reset the workspace
        if os.path.exists(workspace_root):
            shutil.rmtree(workspace_root)

        os.makedirs(workspace_root, exist_ok=True)

        # Always extract or copy the model file
        if file_path.lower().endswith('.zip'):
            with zipfile.ZipFile(model_zip_path, 'r') as zip_ref:
                zip_ref.extractall(workspace_root)
        else:
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

                for f in python_files:
                    temp_path = os.path.join(root, f)
                    
                    # REBUSTNESS CHECK: Ensure the file is actually text, not a binary/LICENSE
                    try:
                        with open(temp_path, 'rb') as check_f:
                            # If a null byte is found, it's binary; skip it
                            if b'\x00' in check_f.read(1024): 
                                continue 
                    except Exception:
                        continue

                    # Once a valid text-based Python file is found:
                    new_path = os.path.join(root, "main.py")
                    os.rename(temp_path, new_path)
                    model_home = root
                    break # Exit the file loop
                
                if model_home:
                    break # Exit the directory walk

        if not model_home:
            return {"status": "error", "message": "No Python files found in upload."}

        # 3. Dynamic Environment Prep
        install_error = smart_pip_install(model_home)
        if install_error:
            return {"status": "error", "message": install_error}
        sys.path = [p for p in sys.path if BASE_WORKSPACE not in p]
        sys.path.insert(0, model_home)
        os.chdir(model_home)

        # 4. Load the Model Module
        module_name = f"dynamic_model_{model_id}"

        # Clear old module cache
        if module_name in sys.modules:
            del sys.modules[module_name]

        importlib.invalidate_caches()

        spec = importlib.util.spec_from_file_location(module_name, os.path.join(model_home, "main.py"))
        model_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = model_module


        if not validate_main_code(os.path.join(model_home, "main.py")):
            return {
                "status": "error", 
                "message": "Model Contract Error: Your script is missing the required 'handle_request(user_input)' function."
            }

        spec.loader.exec_module(model_module)

        # 5. Core Execution
        if not hasattr(model_module, 'handle_request'):
            return {"status": "error", "message": "Model Contract Error: handle_request function missing."}
        
        # Decide if final_input should be an extracted string or an absolute file path.
        # We only treat it as a file if it explicitly comes from the uploads folder.
        is_data_file = isinstance(user_input, str) and user_input.startswith("temp_uploads/")

        if is_data_file:
            # Build the absolute path for the data file
            # Normalize: strip any accidental leading slashes
            clean_input = user_input.lstrip("/")

            abs_data_path = os.path.join("/app/media", clean_input)

            ext = os.path.splitext(abs_data_path)[1].lower()

            # Platform intelligence: If it's a document, extract the text.
            if ext in ['.docx', '.pdf', '.txt']:
                final_input = extract_text_word_pdf(abs_data_path)
            else:
                # If it's Excel/Binary, send the clean absolute path.
                final_input = abs_data_path
        else:
            # It's just a text string like "test" or an empty prompt.
            # No path-prefixing happens here, fixing the [Errno 2] error.
            final_input = user_input

        # THE CACHE KILLER: Prevents the server from 'remembering' old bugs.
        module_name = "dynamic_model"
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Call the script's handle_request function
        raw_result = model_module.handle_request(final_input)

        # 6. Response Strategy
        # The platform determines how to package the result based on requested output_type
        if output_type == "file":
            output_filename = f"output_{model_id}{extension or '.txt'}"
            final_media_path = f"/app/media/temp_uploads/{output_filename}"
            os.makedirs(os.path.dirname(final_media_path), exist_ok=True)

            # Option A: Model returned a specialized object (like a PIL image)
            if hasattr(raw_result, 'save'):
                raw_result.save(final_media_path)

            # Option B: Model returned a path to a file it generated itself
            elif isinstance(raw_result, str):

                # CASE 1: Model returned an absolute file path
                if raw_result.startswith("/") and os.path.exists(raw_result):
                    shutil.move(raw_result, final_media_path)

                # CASE 2: Model returned a relative file path
                elif os.path.exists(os.path.join("/app/media", raw_result)):
                    source_path = os.path.join("/app/media", raw_result)
                    shutil.move(source_path, final_media_path)

                # CASE 3: Model returned TEXT, not a file path
                else:
                    handle_formatting(raw_result, final_media_path, extension)

            # Option C: Model returned non-string data (numbers, dicts, etc.)
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