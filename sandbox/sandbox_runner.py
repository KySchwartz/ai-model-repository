import sys
import os
import importlib.util
import json

def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "message": "Missing arguments"}))
        return

    relative_path = sys.argv[1]
    user_input = sys.argv[2]
    model_dir = os.path.join("/workspace", relative_path)
    main_path = os.path.join(model_dir, "main.py")

    # DEBUG: Let's see what files are actually in the sandbox
    if os.path.exists(model_dir):
        print(f"DEBUG: Files in sandbox: {os.listdir(model_dir)}", file=sys.stderr)

    # Ensure the model directory and its deps are in the path
    sys.path.insert(0, model_dir)
    deps_path = os.path.join(model_dir, "deps")
    if os.path.isdir(deps_path):
        sys.path.insert(0, deps_path)

    try:
        user_model = load_module("user_model", main_path)
        result = user_model.handle_request(user_input)
        print(json.dumps({"status": "success", "data": result}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()