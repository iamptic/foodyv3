# In your main FastAPI app file (e.g., app/main.py):
from fastapi import FastAPI
from .health_endpoints import router as health_router

app = FastAPI(title="Foody API")

# Example: ensure your business routers have prefixes like '/api' or '/api/v1'
# from .routers import merchant, offers
# app.include_router(merchant.router, prefix="/api/v1")
# app.include_router(offers.router, prefix="/api/v1")

# Mount health/ready
app.include_router(health_router)

# CORS example:
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in prod, e.g. ['https://web-production-...up.railway.app']
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
