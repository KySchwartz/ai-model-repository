from fastapi import FastAPI
from routes.status import router as status_router
from routes.validate import router as validate_router
from routes.execute import router as execute_router

app = FastAPI()

# Mount routers
app.include_router(status_router)
app.include_router(validate_router)
app.include_router(execute_router)