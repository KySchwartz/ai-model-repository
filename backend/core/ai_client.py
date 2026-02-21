import httpx

async def get_ai_status():
    # 'ai_suite' is the name we gave the container in docker-compose.yml
    # Port 8001 is where FastAPI is listening
    async with httpx.AsyncClient() as client:
        response = await client.get("http://ai_suite:8001/status")
        return response.json()