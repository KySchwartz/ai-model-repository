import importlib.util
import json
import os
import sys

def load_module_from_path(path: str):
    # Ensure the model directory is importable
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("user_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    if len(sys.argv) != 3:
        print(json.dumps({"error": "Usage: sandbox_runner.py <relative_model_path> <input_json>"}))
        sys.exit(1)

    relative_path = sys.argv[1]
    raw_input = sys.argv[2]

    model_dir = os.path.join("/workspace", relative_path)
    main_path = os.path.join(model_dir, "main.py")

    if not os.path.exists(main_path):
        print(json.dumps({"error": f"main.py not found at {main_path}"}))
        sys.exit(1)

    # NEW: Add per-model dependency folder to sys.path
    deps_path = os.path.join(model_dir, "deps")
    if os.path.isdir(deps_path):
        sys.path.insert(0, deps_path)
    print("DEPS PATH:", deps_path, "EXISTS:", os.path.isdir(deps_path), flush=True)

    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}))
        sys.exit(1)

    # IMPORTANT: No requirement installation here anymore
    module = load_module_from_path(main_path)

    if not hasattr(module, "handle_request"):
        print(json.dumps({"error": "handle_request function not found in main.py"}))
        sys.exit(1)

    try:
        result = module.handle_request(payload)
        print(json.dumps({"result": result}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
