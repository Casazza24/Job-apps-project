from fastapi import APIRouter
from shared.db import get_pending_review_applications, get_submitted_applications

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("/pending")
async def pending():
    return get_pending_review_applications()


@router.get("/submitted")
async def submitted():
    return get_submitted_applications()
