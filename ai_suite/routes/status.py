from fastapi import APIRouter

router = APIRouter()

# Default API response
@router.get("/")
def read_root():
    return {"message": "AI Suite is Online"}

# Simple verification to ensure the ai_suite is returning a response
@router.get("/status")
def get_status():
    return {
        "status": "online",
        "capabilities": ["XGBoost", "Random Forest"],
        "version": "1.0.0"
    }
