import httpx

AI_SUITE_URL = "http://ai_suite:8001"

async def get_ai_status():
    # 'ai_suite' is the name we gave the container in docker-compose.yml
    # Port 8001 is where FastAPI is listening
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AI_SUITE_URL}/status")
        return response.json()
    
async def validate_model_with_ai(framework, version, file_name):
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "framework": framework,
                "version": version,
                "file_name": file_name
            }
            response = await client.post(f"{AI_SUITE_URL}/validate", json=payload, timeout=5.0)
            return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}