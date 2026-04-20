import sys
import os
import importlib.util
import json
import uuid
import resource

def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def process_result_item(item, model_dir):
    """Helper to process a single output item from handle_request."""
    # Handle PIL Images
    try:
        from PIL import Image
        if isinstance(item, Image.Image):
            out_filename = f"result_{uuid.uuid4().hex}.png"
            save_path = os.path.join(model_dir, os.path.basename(out_filename))
            item.save(save_path)
            return out_filename
    except (ImportError, Exception):
        pass

    # Handle raw bytes
    if isinstance(item, (bytes, bytearray)):
        out_filename = f"result_{uuid.uuid4().hex}.bin"
        save_path = os.path.join(model_dir, out_filename)
        with open(save_path, "wb") as f:
            f.write(item)
        return out_filename

    return item

def get_precise_metrics():
    """Captures container resource usage via cgroups or resource module fallback."""
    # 1. Memory Usage (Peak) in MB
    peak_mem_mb = 0
    # List of common cgroup paths for memory peak/usage
    mem_paths = [
        "/sys/fs/cgroup/memory.peak",                   # Cgroup v2 Peak
        "/sys/fs/cgroup/memory.current",                # Cgroup v2 Current (Fallback)
        "/sys/fs/cgroup/memory/memory.max_usage_in_bytes", # Cgroup v1 Peak
        "/sys/fs/cgroup/memory/memory.usage_in_bytes"   # Cgroup v1 Current
    ]
    
    for path in mem_paths:
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    val = int(f.read().strip()) / (1024 * 1024)
                    peak_mem_mb = max(peak_mem_mb, val)
        except Exception:
            continue
    
    if peak_mem_mb <= 0:
        peak_mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    # 2. CPU Usage (Total User + System) in seconds
    usage_self = resource.getrusage(resource.RUSAGE_SELF)
    usage_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_seconds = (usage_self.ru_utime + usage_self.ru_stime + 
                   usage_children.ru_utime + usage_children.ru_stime)
    
    return {"peak_memory": peak_mem_mb, "cpu_usage": cpu_seconds}

def main():
    # Expecting: [script_path, model_rel_dir, entry_file_rel, user_input]
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
            # Debugging information to help trace volume mount issues
            print(f"DEBUG: Root /workspace contents: {os.listdir(model_dir)}")
            print(f"DEBUG: Attempted to load: {main_path}")
            print(json.dumps({"status": "error", "message": f"File {entry_file_rel} not found"}))
            sys.exit(1) # Ensure the orchestrator sees the failure

        # Attempt to parse user_input as JSON for handle_request(dict) compatibility
        user_input_data = user_input
        try:
            if isinstance(user_input, str) and (user_input.startswith('{') or user_input.startswith('[')):
                user_input_data = json.loads(user_input)
        except (json.JSONDecodeError, TypeError):
            pass

        print(f"DEBUG: Passing input of type {type(user_input_data).__name__} to handle_request")

        user_model = load_module("user_model", main_path)
        result = user_model.handle_request(user_input_data)
        
        if isinstance(result, list):
            processed_data = [process_result_item(i, model_dir) for i in result]
        else:
            processed_data = process_result_item(result, model_dir)

        # Capture precise resource usage from the kernel before exiting
        metrics = get_precise_metrics()

        # Use a prefix to help the orchestrator find the JSON block in the logs
        output = json.dumps({"status": "success", "data": processed_data, "metrics": metrics})
        print(f"RESULT_JSON:{output}")
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()