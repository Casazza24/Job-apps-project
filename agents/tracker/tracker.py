"""
Tracker Agent — polls application status and sends daily summary emails.
Triggered daily by Cloud Scheduler via POST /trigger/tracker.

Status flow: submitted → viewed → interview | rejected
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from shared.config import get_config
from shared.db import get_submitted_applications, update_application_status, fetchall, execute
from shared.logger import get_logger
from agents.tracker.notifier import send_daily_summary

logger = get_logger("tracker")

# Number of days after submission before creating a follow-up record
FOLLOW_UP_DAYS = 7


def check_linkedin_status(page, job_url: str) -> Optional[str]:
    """Stub: check LinkedIn application status. Returns new status string or None."""
    # Full implementation would navigate to the applications page and check status
    # LinkedIn application status is at: linkedin.com/my-items/saved-jobs/
    return None


def create_follow_up_if_needed(application: Dict[str, Any]) -> None:
    """Create a follow_up record if no response after FOLLOW_UP_DAYS days."""
    submitted_at = application.get("submitted_at")
    if not submitted_at:
        return
    if datetime.utcnow() - submitted_at < timedelta(days=FOLLOW_UP_DAYS):
        return

    # Check if a follow-up already exists
    existing = fetchall(
        "SELECT id FROM follow_ups WHERE application_id = %s AND sent_at IS NULL",
        (application["id"],)
    )
    if existing:
        return

    scheduled = submitted_at + timedelta(days=FOLLOW_UP_DAYS)
    execute(
        "INSERT INTO follow_ups (application_id, scheduled_at, type) VALUES (%s, %s, %s)",
        (application["id"], scheduled, "7_day_nudge")
    )
    logger.info("Follow-up created", extra={"application_id": application["id"]})


def run_tracker() -> None:
    """Main entry point — check all submitted applications and send daily summary."""
    config = get_config()
    applications = get_submitted_applications()
    logger.info("Tracker running", extra={"total_applications": len(applications)})

    new_updates: List[Dict[str, Any]] = []

    for app in applications:
        if app.get("status") not in ("submitted",):
            continue  # Only actively poll 'submitted' ones

        try:
            # Create follow-up records for old applications with no response
            create_follow_up_if_needed(app)

            # Update last_checked_at
            execute(
                "UPDATE applications SET last_checked_at = NOW() WHERE id = %s",
                (app["id"],)
            )

            # Platform-specific status checks (stubs — expand with Playwright automation)
            platform = app.get("platform", "")
            new_status = None

            if platform == "linkedin":
                # LinkedIn status can sometimes be polled via their jobs API
                # For now, log that we checked
                logger.debug("Checked LinkedIn application", extra={"application_id": app["id"]})
            elif platform == "greenhouse":
                # Greenhouse sends emails; we note the check
                logger.debug("Checked Greenhouse application", extra={"application_id": app["id"]})
            # Add more platform checks as needed

            if new_status and new_status != app.get("status"):
                update_application_status(app["id"], new_status)
                app["status"] = new_status
                new_updates.append(app)
                logger.info("Status updated", extra={
                    "application_id": app["id"],
                    "new_status": new_status,
                    "job": app.get("title"),
                })

        except Exception as e:
            logger.error("Error checking application", extra={
                "application_id": app.get("id"),
                "error": str(e),
            })

    # Send daily summary email
    try:
        send_daily_summary(applications, new_updates)
    except Exception as e:
        logger.error("Failed to send daily summary", extra={"error": str(e)})

    logger.info("Tracker complete", extra={
        "checked": len(applications),
        "updates": len(new_updates),
    })


if __name__ == "__main__":
    run_tracker()
