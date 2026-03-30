import os
import re
import subprocess
from pathlib import Path
from huggingface_hub import snapshot_download

# Patterns for common ML loading functions
SIGNATURES = {
    # Catches almost any string inside a from_pretrained() call
    "huggingface": r'from_pretrained\s*\(\s*["\']([^"\']+)["\']',
    "pytorch_hub": r'torch\.hub\.load\s*\(\s*["\']([^"\']+)["\']',
    "tf_hub": r'hub\.(?:load|KerasLayer)\s*\(\s*["\']([^"\']+)["\']',
    # Catches common model file extensions in URLs
    "urls": r'["\'](https?://[^\s"\']+\.(?:bin|pth|h5|joblib|onnx|zip|tar\.gz|json))["\']'
}

def scan_for_dependencies(workspace_path):
    """
    Scans ONLY the main entry point and top-level .py files.
    Avoids scanning deep into library folders.
    """
    found_assets = {"huggingface": set(), "pytorch_hub": set(), "tf_hub": set(), "urls": set()}
    
    # Only scan files in the ROOT of the model directory
    # This prevents scanning 'deps/' or 'venv/'
    files_to_scan = [f for f in os.listdir(workspace_path) if f.endswith(".py")]

    for file_name in files_to_scan:
        file_path = os.path.join(workspace_path, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for key, pattern in SIGNATURES.items():
                    matches = re.findall(pattern, content)
                    for match in matches:
                        # CLEANUP: Ignore common placeholders/template strings
                        if "{" in match or "}" in match or "/" not in match:
                            continue
                        
                        found_assets[key if key != "generic_url" else "urls"].add(match)
        except Exception as e:
            print(f"Error scanning {file_name}: {e}")
            
    return found_assets

def download_assets(assets, cache_dir):
    """
    Downloads the detected assets into the shared volume.
    Note: This runs on the HOST where internet is available.
    """
    os.makedirs(cache_dir, exist_ok=True)
    
# 1. Hugging Face: Download the ENTIRE repo (Weights + Tokenizer + Config)
    if assets["huggingface"]:
        for model_id in assets["huggingface"]:
            print(f"Provisioning full HF snapshot: {model_id}")
            # This ensures OFFLINE mode has everything it needs
            snapshot_download(
                repo_id=model_id, 
                cache_dir=cache_dir,
                local_files_only=False
            )

    # Example for Generic URLs (uses wget or curl)
    if assets["urls"]:
        for url in assets["urls"]:
            filename = url.split("/")[-1]
            dest = os.path.join(cache_dir, filename)
            if not os.path.exists(dest):
                print(f"Provisioning URL Asset: {url}")
                subprocess.run(["curl", "-L", url, "-o", dest])