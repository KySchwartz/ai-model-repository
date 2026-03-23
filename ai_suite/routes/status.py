from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def read_root():
    return {"message": "AI Suite is Online"}

@router.get("/status")
def get_status():
    return {
        "status": "online",
        "capabilities": ["XGBoost", "Random Forest"],
        "version": "1.0.0"
    }
