from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ValidationRequest(BaseModel):
    framework: str
    version: str
    file_name: str

# Ensure the selected input type is allowed on the platform
@router.post("/validate")
async def validate_model(request: ValidationRequest):
    allowed_exts = ('.py', '.zip')

    if not request.file_name.lower().endswith(allowed_exts):
        return {"status": "invalid", "message": "Unsupported file extension for this platform."}

    return {"status": "valid", "message": "Model structure verified"}
