from fastapi import FastAPI

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