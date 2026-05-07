from fastapi import APIRouter
from shared.db import get_submitted_applications

router = APIRouter(prefix="/api/tracker", tags=["tracker"])


@router.get("/")
async def tracker_status():
    return get_submitted_applications()
