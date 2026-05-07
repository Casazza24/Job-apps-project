"""
Notifier — sends daily email summaries via SendGrid (or logs if no key configured).
"""
from typing import List, Dict, Any
from shared.config import get_config
from shared.logger import get_logger

logger = get_logger("notifier")


def send_daily_summary(applications: List[Dict[str, Any]], new_updates: List[Dict[str, Any]]) -> None:
    """Send daily summary email with application status updates."""
    config = get_config()

    subject = f"Job Agent Daily Summary — {len(applications)} applications tracked"
    body = _build_email_body(applications, new_updates, config)

    if config.SENDGRID_API_KEY and config.NOTIFICATION_EMAIL:
        _send_via_sendgrid(config, subject, body)
    else:
        # Log the summary if no email configured
        logger.info("Daily summary (no email configured)", extra={
            "subject": subject,
            "total_applications": len(applications),
            "new_updates": len(new_updates),
        })
        print(f"\n{'='*60}")
        print(f"DAILY SUMMARY: {subject}")
        print('='*60)
        print(body)
        print('='*60)


def _build_email_body(applications: List[Dict], new_updates: List[Dict], config) -> str:
    total = len(applications)
    submitted = sum(1 for a in applications if a.get("status") == "submitted")
    interviews = sum(1 for a in applications if a.get("status") == "interview")
    rejected = sum(1 for a in applications if a.get("status") == "rejected")

    lines = [
        f"Hi {config.CANDIDATE_FIRST_NAME},",
        "",
        "Here's your daily job application summary:",
        "",
        f"  Total applications tracked: {total}",
        f"  Submitted (awaiting response): {submitted}",
        f"  Interviews scheduled: {interviews}",
        f"  Rejected: {rejected}",
        "",
    ]

    if new_updates:
        lines.append("NEW STATUS UPDATES:")
        for app in new_updates:
            lines.append(f"  • {app.get('title')} @ {app.get('company')} → {app.get('status', '').upper()}")
        lines.append("")

    lines.append("View your dashboard to review pending applications.")
    return "\n".join(lines)


def _send_via_sendgrid(config, subject: str, body: str) -> None:
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg = sendgrid.SendGridAPIClient(api_key=config.SENDGRID_API_KEY)
        message = Mail(
            from_email=config.NOTIFICATION_EMAIL,
            to_emails=config.NOTIFICATION_EMAIL,
            subject=subject,
            plain_text_content=body,
        )
        response = sg.send(message)
        logger.info("Daily summary email sent", extra={
            "status_code": response.status_code,
            "to": config.NOTIFICATION_EMAIL,
        })
    except Exception as e:
        logger.error("Failed to send email", extra={"error": str(e)})


def send_captcha_alert(application_id: int, job_title: str, company: str) -> None:
    """Alert user that a CAPTCHA was encountered during submission."""
    config = get_config()
    subject = f"CAPTCHA Required: {job_title} @ {company}"
    body = (
        f"The submitter encountered a CAPTCHA while applying to:\n\n"
        f"  Job: {job_title}\n"
        f"  Company: {company}\n"
        f"  Application ID: {application_id}\n\n"
        f"Please manually complete this application or solve the CAPTCHA via the dashboard."
    )
    if config.SENDGRID_API_KEY and config.NOTIFICATION_EMAIL:
        _send_via_sendgrid(config, subject, body)
    else:
        logger.warning("CAPTCHA alert (no email configured)", extra={
            "application_id": application_id,
            "job": job_title,
            "company": company,
        })
