"""
Main Submitter Agent entrypoint.
Called when an application is approved from the dashboard.
"""
import asyncio
from shared.config import get_config
from shared.db import get_application, update_application_status
from shared.logger import get_logger
from shared.platforms_registry import get_submitter_for_platform

logger = get_logger("submitter")


async def submit_application(application_id: int) -> None:
    """Submit a single approved application. Called by dashboard on /approve."""
    config = get_config()
    application = get_application(application_id)

    if not application:
        logger.error("Application not found", extra={"application_id": application_id})
        return

    platform = application.get("platform")
    logger.info("Submitting application", extra={
        "application_id": application_id,
        "platform": platform,
        "job_title": application.get("title"),
        "company": application.get("company"),
    })

    try:
        SubmitterClass = get_submitter_for_platform(platform)
        submitter = SubmitterClass(config=config)
        await submitter.submit(application)
        update_application_status(application_id, "submitted")
        logger.info("Application submitted successfully", extra={"application_id": application_id})
    except Exception as e:
        logger.error("Submission failed", extra={"application_id": application_id, "error": str(e)})
        update_application_status(application_id, "failed", notes=str(e))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        asyncio.run(submit_application(int(sys.argv[1])))
    else:
        print("Usage: python -m agents.submitter.submitter <application_id>")
