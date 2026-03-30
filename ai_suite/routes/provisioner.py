import os
import re
import subprocess
from pathlib import Path
from huggingface_hub import snapshot_download

# Patterns for common ML loading functions
SIGNATURES = {
    # Captures the entire argument block for processing
    "huggingface": r'(?:from_pretrained|pipeline|load_dataset)\s*\(([\s\S]*?)\)',
    "pytorch_hub": r'torch\.hub\.load\s*\(([\s\S]*?)\)',
    "tf_hub": r'hub\.(?:load|KerasLayer)\s*\(([\s\S]*?)\)',
    # Catches common model file extensions in URLs
    "urls": r'["\'](https?://[^\s"\']+\.(?:bin|pth|h5|joblib|onnx|zip|tar\.gz|json))["\']'
}

# Broad regex for any string that looks like a Hugging Face repo (e.g., "org/model")
HF_REPO_RE = r'["\']([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)["\']'

# Common single-word model IDs that don't have slashes
COMMON_MODELS = {"gpt2", "t5-small", "t5-base", "t5-large", "bert-base-uncased", "distilgpt2"}

def scan_for_dependencies(workspace_path):
    """
    Recursively scans the project for model dependencies,
    ignoring common library/dependency directories.
    """
    found_assets = {"huggingface": set(), "pytorch_hub": set(), "tf_hub": set(), "urls": set()}
    
    # Known pipeline tasks to ignore if they appear as the model ID
    TASKS = {
        'summarization', 'text-generation', 'text2text-generation', 
        'translation', 'fill-mask', 'sentiment-analysis', 
        'question-answering', 'zero-shot-classification', 'ner', 'audio-classification'
    }
    
    # File types that might contain model identifiers
    SCAN_EXTENSIONS = (".py", ".json", ".yaml", ".yml", ".txt")

    for root, dirs, files in os.walk(workspace_path):
        # Skip the 'deps' directory created by the orchestrator
        if 'deps' in dirs:
            dirs.remove('deps')
            
        for file_name in files:
            if file_name.endswith(SCAN_EXTENSIONS):
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # 1. Broad scan for "namespace/repo" strings anywhere in the file
                        # This catches variables: model_id = "facebook/bart-large-cnn"
                        repo_matches = re.findall(HF_REPO_RE, content)
                        for match in repo_matches:
                            # Filter out false positives (MIME types, paths, URLs)
                            if any(x in match.lower() for x in ['image/', 'text/', 'application/', 'http', '.py', '.png']):
                                continue
                            found_assets["huggingface"].add(match)

                        # 2. Function-specific scan for complex calls
                        for key, pattern in SIGNATURES.items():
                            raw_calls = re.findall(pattern, content)
                            for call_args in raw_calls:
                                potential_ids = re.findall(r'["\']([^"\']+)["\']', call_args)
                                for match in potential_ids:
                                    if "{" in match or "}" in match or not match.strip():
                                        continue
                                    if key == "huggingface" and match.lower() in TASKS:
                                        continue
                                    
                                    found_assets[key].add(match)
                        
                        # 3. Check for common single-word models
                        for model in COMMON_MODELS:
                            if f'"{model}"' in content or f"'{model}'" in content:
                                found_assets["huggingface"].add(model)

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
        # HF_HOME structure expects models in a 'hub' subfolder
        hf_hub_cache = os.path.join(cache_dir, "hub")
        for model_id in assets["huggingface"]:
            try:
                print(f"Provisioning full HF snapshot: {model_id}")
                # This ensures OFFLINE mode has everything it needs
                snapshot_download(
                    repo_id=model_id, 
                    cache_dir=hf_hub_cache,
                    local_files_only=False,
                    resume_download=True
                )
            except Exception as e:
                print(f"Failed to provision {model_id}: {e}")

    # Example for Generic URLs (uses wget or curl)
    if assets["urls"]:
        for url in assets["urls"]:
            filename = url.split("/")[-1]
            dest = os.path.join(cache_dir, filename)
            if not os.path.exists(dest):
                print(f"Provisioning URL Asset: {url}")
                subprocess.run(["curl", "-L", url, "-o", dest])