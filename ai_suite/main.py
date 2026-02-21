from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "AI Suite is Online"}

@app.get("/status")
def get_status():
    # This will eventually show if XGBoost/LLM models are loaded
    return {"status": "ready", "models_loaded": ["XGBoost", "Random Forest"]}