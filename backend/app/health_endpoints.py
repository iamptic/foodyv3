# Drop-in FastAPI include for health and ready endpoints
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")  # liveness
async def health():
    return {"status": "ok"}

@router.get("/ready")   # readiness
async def ready():
    # optionally check db connection here
    return {"status": "ready"}
