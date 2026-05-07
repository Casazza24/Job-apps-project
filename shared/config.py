import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "local")


def get_secret(name: str) -> str:
    if ENV == "local":
        val = os.getenv(name)
        if not val:
            raise ValueError(f"Missing env var: {name}")
        return val
    # Production: fetch from GCP Secret Manager
    from google.cloud import secretmanager
    project_id = os.getenv("GCP_PROJECT_ID")
    client = secretmanager.SecretManagerServiceClient()
    secret_path = f"projects/{project_id}/secrets/{name}/versions/latest"
    response = client.access_secret_version(name=secret_path)
    return response.payload.data.decode("utf-8")


class Config:
    ENV = ENV
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://jobagent:jobagent@localhost/jobagent")
    BUCKET_NAME = os.getenv("BUCKET_NAME", "")
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")

    CANDIDATE_LINKEDIN = os.getenv("CANDIDATE_LINKEDIN", "")
    CANDIDATE_GITHUB = os.getenv("CANDIDATE_GITHUB", "")
    CANDIDATE_PORTFOLIO = os.getenv("CANDIDATE_PORTFOLIO", "")
    CANDIDATE_FIRST_NAME = os.getenv("CANDIDATE_FIRST_NAME", "")
    CANDIDATE_LAST_NAME = os.getenv("CANDIDATE_LAST_NAME", "")
    CANDIDATE_EMAIL = os.getenv("CANDIDATE_EMAIL", "")

    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")

    VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

    RESUME_PATH = os.getenv("RESUME_PATH", "resume.txt")

    def get_platform_email(self, prefix: str) -> str:
        return get_secret(f"{prefix}_EMAIL")

    def get_platform_password(self, prefix: str) -> str:
        return get_secret(f"{prefix}_PASSWORD")


@lru_cache
def get_config() -> Config:
    return Config()
