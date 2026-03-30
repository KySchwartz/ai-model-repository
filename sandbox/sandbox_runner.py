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
    if len(sys.argv) < 4:
        print(json.dumps({"status": "error", "message": "Missing arguments"}))
        return

    model_rel_dir = sys.argv[1]
    entry_file_rel = sys.argv[2]
    user_input = sys.argv[3]
    
    model_dir = os.path.join("/workspace", model_rel_dir)
    main_path = os.path.join(model_dir, entry_file_rel)

    # Ensure the model directory and its deps are in the path
    sys.path.insert(0, model_dir)
    deps_path = os.path.join(model_dir, "deps")
    if os.path.isdir(deps_path):
        sys.path.insert(0, deps_path)

    try:
        if not os.path.exists(main_path):
            print(json.dumps({"status": "error", "message": f"File {entry_file_rel} not found"}))
            return

        user_model = load_module("user_model", main_path)
        result = user_model.handle_request(user_input)
        print(json.dumps({"status": "success", "data": result}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()