from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class Job(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    external_id: str
    platform: str
    title: str
    company: str
    location: Optional[str] = None
    salary: Optional[str] = None
    url: str
    description: Optional[str] = None
    status: str = "new"  # new, reviewed, approved, skipped, submitted, captcha_required
    match_score: Optional[float] = None
    score_reasoning: Optional[str] = None
    scraped_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    is_workday: bool = False
    workday_url: Optional[str] = None

    class Config:
        from_attributes = True


class Application(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    status: str = "pending_review"  # pending_review, approved, skipped, submitted, failed
    tailored_resume_url: Optional[str] = None
    cover_letter: Optional[str] = None
    tailored_bullets: Optional[List[str]] = None
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class WorkdayAccount(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    company: str
    email_alias: str
    password: str
    workday_url: str
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None

    class Config:
        from_attributes = True


class FollowUp(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str
    follow_up_date: datetime
    message: Optional[str] = None
    sent: bool = False
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class OrchestratorResult(BaseModel):
    match_score: float = Field(ge=0, le=100)
    score_reasoning: str
    tailored_bullets: List[str]
    cover_letter: str
