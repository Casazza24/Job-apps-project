"""
Resume tailoring utilities — extracts and applies tailored bullets.
"""
import json
from typing import List, Dict


def extract_tailored_bullets(resume_diff_json: str) -> List[Dict[str, str]]:
    """Parse resume_diff JSON from DB into list of {original, tailored} dicts."""
    try:
        bullets = json.loads(resume_diff_json) if isinstance(resume_diff_json, str) else resume_diff_json
        return bullets if isinstance(bullets, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def apply_bullets_to_resume_text(base_resume: str, bullets: List[Dict[str, str]]) -> str:
    """Replace original bullet text with tailored text in the resume."""
    result = base_resume
    for bullet in bullets:
        original = bullet.get("original", "").strip()
        tailored = bullet.get("tailored", "").strip()
        if original and tailored:
            result = result.replace(original, tailored)
    return result


def generate_tailored_resume_pdf(base_resume: str, bullets: List[Dict[str, str]], candidate_name: str = "") -> bytes:
    """
    Generate a tailored resume PDF using reportlab.
    Applies bullet substitutions then renders as a simple text PDF.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
        import io

        tailored_text = apply_bullets_to_resume_text(base_resume, bullets)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=0.75 * inch, leftMargin=0.75 * inch,
                                topMargin=0.75 * inch, bottomMargin=0.75 * inch)
        styles = getSampleStyleSheet()
        story = []
        if candidate_name:
            story.append(Paragraph(f"<b>{candidate_name}</b>", styles["Heading1"]))
            story.append(Spacer(1, 0.1 * inch))

        for line in tailored_text.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.05 * inch))
            elif line.startswith("##") or line.startswith("**"):
                clean = line.lstrip("#").strip().strip("*")
                story.append(Paragraph(f"<b>{clean}</b>", styles["Heading3"]))
            elif line.startswith("-") or line.startswith("•"):
                story.append(Paragraph(line, styles["BodyText"]))
            else:
                story.append(Paragraph(line, styles["BodyText"]))

        doc.build(story)
        return buffer.getvalue()
    except Exception:
        return b""
