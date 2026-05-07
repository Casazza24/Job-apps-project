"""
Orchestrator Agent — scores jobs, tailors resumes, writes cover letters using Gemini via Vertex AI.
Triggered after scraper inserts new jobs.
Auth: uses GCP service account on VM, or `gcloud auth application-default login` locally.
"""
import json
import os
from pathlib import Path
from typing import Optional

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

from shared.config import get_config
from shared.db import get_new_jobs, update_job_status, insert_application
from shared.gcp import upload_bytes_to_gcs
from shared.logger import get_logger

logger = get_logger("orchestrator")

SYSTEM_PROMPT = """
You are a job application assistant helping a candidate apply for roles in
data science, data engineering, software engineering, AI/ML, and data analytics.

Given a job description and the candidate's base resume, you will:
1. Score the job match from 0-100 based on skills alignment
2. Rewrite the resume bullet points to mirror the job description language
   and highlight the most relevant experience. Do not fabricate experience.
3. Write a personalized cover letter (3 short paragraphs, professional tone)

The candidate's URLs to include where relevant:
- LinkedIn: {linkedin_url}
- GitHub: {github_url}
- Portfolio: {portfolio_url}

Respond ONLY in valid JSON with this structure:
{{
  "match_score": <integer 0-100>,
  "score_reasoning": "<one sentence>",
  "tailored_bullets": [
    {{"original": "...", "tailored": "..."}}
  ],
  "cover_letter": "<full cover letter text>"
}}
"""


def load_base_resume(config) -> str:
    """Load base resume text from local file or GCS."""
    resume_path = config.RESUME_PATH
    if os.path.exists(resume_path):
        return Path(resume_path).read_text()
    if config.BUCKET_NAME and config.ENV != "local":
        from shared.gcp import download_bytes_from_gcs
        data = download_bytes_from_gcs(config.BUCKET_NAME, "base_resume.txt")
        return data.decode("utf-8")
    logger.warning("No resume file found", extra={"path": resume_path})
    return ""


def call_gemini(job: dict, base_resume: str, config) -> Optional[dict]:
    """Call Gemini via Vertex AI to score/tailor. Returns parsed JSON dict or None on error."""
    vertexai.init(project=config.GCP_PROJECT_ID, location=config.VERTEX_LOCATION)
    system = SYSTEM_PROMPT.format(
        linkedin_url=config.CANDIDATE_LINKEDIN,
        github_url=config.CANDIDATE_GITHUB,
        portfolio_url=config.CANDIDATE_PORTFOLIO,
    )
    user_prompt = f"""
Job Title: {job['title']}
Company: {job['company']}
Location: {job.get('location', 'Not specified')}

Job Description:
{job.get('description', 'No description available')}

Candidate Base Resume:
{base_resume}
"""
    try:
        model = GenerativeModel(
            "gemini-2.0-flash-001",
            system_instruction=system,
        )
        response = model.generate_content(
            user_prompt,
            generation_config=GenerationConfig(
                max_output_tokens=2048,
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini JSON", extra={"error": str(e), "job_id": job.get("id")})
        return None
    except Exception as e:
        logger.error("Gemini API call failed", extra={"error": str(e), "job_id": job.get("id")})
        return None


def generate_cover_letter_pdf(cover_letter_text: str, job: dict) -> bytes:
    """Generate a simple PDF for the cover letter using reportlab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=inch, leftMargin=inch,
                                topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"<b>{job['title']} — {job['company']}</b>", styles["Heading2"]),
            Spacer(1, 0.2 * inch),
        ]
        for para in cover_letter_text.split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), styles["BodyText"]))
                story.append(Spacer(1, 0.15 * inch))
        doc.build(story)
        return buffer.getvalue()
    except Exception as e:
        logger.warning("PDF generation failed, returning empty bytes", extra={"error": str(e)})
        return b""


def process_job(job: dict, base_resume: str, config) -> None:
    """Score, tailor, and create application record for a single job."""
    logger.info("Processing job", extra={"job_id": job["id"], "title": job["title"], "company": job["company"]})

    result = call_gemini(job, base_resume, config)
    if result is None:
        logger.warning("Skipping job due to Claude failure", extra={"job_id": job["id"]})
        return

    match_score = int(result.get("match_score", 0))
    score_reasoning = result.get("score_reasoning", "")
    tailored_bullets = result.get("tailored_bullets", [])
    cover_letter = result.get("cover_letter", "")

    # Upload cover letter PDF to GCS if in production
    cover_letter_url = None
    if config.BUCKET_NAME and config.ENV != "local":
        pdf_bytes = generate_cover_letter_pdf(cover_letter, job)
        if pdf_bytes:
            blob_name = f"cover_letters/job_{job['id']}.pdf"
            cover_letter_url = upload_bytes_to_gcs(config.BUCKET_NAME, pdf_bytes, blob_name)

    app = {
        "job_id": job["id"],
        "tailored_resume_url": None,
        "cover_letter_url": cover_letter_url,
        "cover_letter_text": cover_letter,
        "resume_diff": json.dumps(tailored_bullets),
        "status": "pending_review",
    }
    insert_application(app)
    update_job_status(job["id"], "reviewed", match_score=match_score, score_reasoning=score_reasoning)
    logger.info("Job processed", extra={"job_id": job["id"], "match_score": match_score})


def run_orchestrator() -> None:
    """Main entry point — process all new jobs."""
    config = get_config()
    base_resume = load_base_resume(config)
    if not base_resume:
        logger.error("No resume text found. Add resume.txt to project root or upload to GCS.")
        return

    jobs = get_new_jobs()
    logger.info("Found new jobs to process", extra={"count": len(jobs)})

    for job in jobs:
        try:
            process_job(job, base_resume, config)
        except Exception as e:
            logger.error("Unexpected error processing job", extra={"job_id": job.get("id"), "error": str(e)})


if __name__ == "__main__":
    run_orchestrator()
