from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "AI Suite is Online"}

@app.get("/status")
def get_status():
    return {
            "status": "online",
            "capabilities": ["XGBoost", "Random Forest"],
            "version": "1.0.0"
        }

class ValidationRequest(BaseModel):
    framework: str
    version: str
    file_name: str

@app.post("/validate")
async def validate_model(request: ValidationRequest):
    # This commented code might be handy later if we only support specific frameworks
    # For testing it is just annoying
    """
    valid_frameworks = ["XGBoost", "Random Forest", "TensorFlow", "Excel", "General"]
    
    if request.framework not in valid_frameworks:
        return {"status": "invalid", "message": f"{request.framework} is not a supported framework."}
    """
    
    allowed_exts = ('.json', '.pkl', '.bst', '.h5', '.txt', '.xlsx', '.docx')
    if not request.file_name.lower().endswith(allowed_exts):
        return {"status": "invalid", "message": "Unsupported file extension for this platform."}

    return {"status": "valid", "message": "Model structure verified"}

@app.post("/execute")
async def execute_model(model_id: int, file_path: str):
    # This path points to the SHARED volume we set up in Docker
    full_path = f"/app/media_shared/{file_path}"
    
    if os.path.exists(full_path):
        # For now, we just return a "Success" message to prove connectivity
        return {
            "status": "success",
            "message": f"AI Suite located model {model_id} at {full_path}. Ready for processing."
        }
    else:
        raise HTTPException(status_code=404, detail=f"Model file not found at {full_path}")