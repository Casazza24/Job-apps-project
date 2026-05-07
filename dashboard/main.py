"""
FastAPI dashboard — human review interface for job applications.
Runs on Cloud Run, accessed via Cloud IAP.
"""
import asyncio
import json
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from shared.db import (
    get_jobs_for_queue, get_application, get_pending_review_applications,
    get_submitted_applications, update_application_status, update_job_status
)
from shared.logger import get_logger

logger = get_logger("dashboard")

BASE_DIR = Path(__file__).parent
app = FastAPI(title="Job Agent Dashboard")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def parse_resume_diff(resume_diff_raw) -> list:
    """Safely parse resume_diff from DB (may be string or list)."""
    if not resume_diff_raw:
        return []
    if isinstance(resume_diff_raw, list):
        return resume_diff_raw
    try:
        return json.loads(resume_diff_raw)
    except Exception:
        return []


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/queue")


@app.get("/queue", response_class=HTMLResponse)
async def queue(request: Request):
    applications = get_pending_review_applications()
    return templates.TemplateResponse("queue.html", {
        "request": request,
        "applications": applications,
        "title": "Review Queue",
    })


@app.get("/review/{application_id}", response_class=HTMLResponse)
async def review(request: Request, application_id: int):
    application = get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    application["resume_diff_parsed"] = parse_resume_diff(application.get("resume_diff"))
    return templates.TemplateResponse("approve.html", {
        "request": request,
        "app": application,
        "title": f"{application['title']} @ {application['company']}",
    })


@app.post("/approve/{application_id}")
async def approve(application_id: int, cover_letter: str = Form(default="")):
    application = get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Save edited cover letter if provided
    if cover_letter.strip():
        from shared.db import execute
        execute("UPDATE applications SET cover_letter_text = %s WHERE id = %s",
                (cover_letter.strip(), application_id))

    update_application_status(application_id, "approved")
    update_job_status(application["job_id"], "approved")

    # Trigger submitter in background
    async def _submit():
        try:
            from agents.submitter.submitter import submit_application
            await submit_application(application_id)
        except Exception as e:
            logger.error("Submitter failed", extra={"application_id": application_id, "error": str(e)})

    asyncio.create_task(_submit())

    # htmx response: swap the card out
    return HTMLResponse(content=f'<div class="card skipped">✓ Approved — submitting #{application_id}</div>')


@app.post("/skip/{application_id}")
async def skip(application_id: int):
    application = get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    update_application_status(application_id, "skipped")
    update_job_status(application["job_id"], "skipped")
    return HTMLResponse(content=f'<div class="card skipped">✗ Skipped #{application_id}</div>')


@app.get("/tracker", response_class=HTMLResponse)
async def tracker(request: Request):
    applications = get_submitted_applications()
    return templates.TemplateResponse("tracker.html", {
        "request": request,
        "applications": applications,
        "title": "Application Tracker",
    })


@app.post("/trigger/scraper")
async def trigger_scraper():
    """Called by Cloud Scheduler to kick off the scraper."""
    async def _run():
        try:
            from agents.scraper.scraper import run_scraper
            await run_scraper()
        except Exception as e:
            logger.error("Scraper trigger failed", extra={"error": str(e)})
    asyncio.create_task(_run())
    return JSONResponse({"status": "scraper triggered"})


@app.post("/trigger/tracker")
async def trigger_tracker():
    """Called by Cloud Scheduler to run the tracker agent."""
    async def _run():
        try:
            from agents.tracker.tracker import run_tracker
            run_tracker()
        except Exception as e:
            logger.error("Tracker trigger failed", extra={"error": str(e)})
    asyncio.create_task(_run())
    return JSONResponse({"status": "tracker triggered"})


@app.get("/health")
async def health():
    return {"status": "ok"}
