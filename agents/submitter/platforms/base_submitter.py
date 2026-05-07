"""Base class for all platform submitters."""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseSubmitter(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    async def submit(self, application: Dict[str, Any]) -> None:
        """Submit an application. Raises on failure."""
        pass

    def _get_resume_bytes(self, application: Dict[str, Any]) -> bytes:
        """Download tailored resume from GCS or return empty bytes."""
        resume_url = application.get("tailored_resume_url")
        if resume_url and self.config.BUCKET_NAME:
            try:
                from shared.gcp import download_bytes_from_gcs
                blob_name = resume_url.replace(f"gs://{self.config.BUCKET_NAME}/", "")
                return download_bytes_from_gcs(self.config.BUCKET_NAME, blob_name)
            except Exception:
                pass
        return b""
