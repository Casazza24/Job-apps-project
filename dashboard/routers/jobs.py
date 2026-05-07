from fastapi import APIRouter
from shared.db import get_jobs_for_queue, get_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/")
async def list_jobs():
    return get_jobs_for_queue()


@router.get("/{job_id}")
async def get_job_detail(job_id: int):
    job = get_job(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job
