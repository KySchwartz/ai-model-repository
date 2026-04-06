import os
import subprocess
from pathlib import Path

# Paths relative to the ai_suite container
MEDIA_ROOT = "/app/media/models"
CACHE_ROOT = "/app/workspaces/huggingface"

def prepare_model_dependencies(relative_path):
    model_dir = os.path.join(MEDIA_ROOT, relative_path)
    req_file = os.path.join(model_dir, "requirements.txt")
    deps_dir = os.path.join(model_dir, "deps")

    # 1. Install pip requirements into a local 'deps' folder
    if os.path.exists(req_file) and not os.path.exists(deps_dir):
        os.makedirs(deps_dir, exist_ok=True)
        subprocess.run([
            "pip", "install", 
            "--target", deps_dir, 
            "-r", req_file,
            "--no-cache-dir"
        ], check=True)

    # 2. Pre-fetch weights if it's a known Transformers model
    # For your capstone, we can trigger a 'warm-up' load here
    # This ensures t5-small is in the shared volume before the sandbox starts.
    if "transformers" in open(req_file).read() if os.path.exists(req_file) else False:
        _ensure_transformers_weights("t5-small")

def _ensure_transformers_weights(model_name):
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    # This runs in the AI_SUITE (which has internet) to fill the cache
    os.makedirs(CACHE_ROOT, exist_ok=True)
    AutoTokenizer.from_pretrained(model_name, cache_dir=CACHE_ROOT)
    AutoModelForSeq2SeqLM.from_pretrained(model_name, cache_dir=CACHE_ROOT)