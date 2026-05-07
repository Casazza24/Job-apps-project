import os
from typing import Optional
from pathlib import Path
from shared.logger import get_logger

logger = get_logger("gcp")


def upload_to_gcs(bucket_name: str, source_path: str, destination_blob: str) -> str:
    """Upload a local file to Google Cloud Storage. Returns the GCS URI."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob)
        blob.upload_from_filename(source_path)
        uri = f"gs://{bucket_name}/{destination_blob}"
        logger.info("Uploaded file to GCS", extra={"uri": uri, "source": source_path})
        return uri
    except Exception as e:
        logger.error("Failed to upload to GCS", extra={"error": str(e), "source": source_path})
        raise


def upload_bytes_to_gcs(bucket_name: str, data: bytes, destination_blob: str, content_type: str = "application/pdf") -> str:
    """Upload bytes directly to Google Cloud Storage. Returns the GCS URI."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob)
        blob.upload_from_string(data, content_type=content_type)
        uri = f"gs://{bucket_name}/{destination_blob}"
        logger.info("Uploaded bytes to GCS", extra={"uri": uri, "size": len(data)})
        return uri
    except Exception as e:
        logger.error("Failed to upload bytes to GCS", extra={"error": str(e)})
        raise


def download_from_gcs(bucket_name: str, source_blob: str, destination_path: str) -> None:
    """Download a file from Google Cloud Storage to local path."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(source_blob)
        Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(destination_path)
        logger.info("Downloaded from GCS", extra={"source": source_blob, "dest": destination_path})
    except Exception as e:
        logger.error("Failed to download from GCS", extra={"error": str(e)})
        raise


def download_bytes_from_gcs(bucket_name: str, source_blob: str) -> bytes:
    """Download a file from GCS and return as bytes."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(source_blob)
        data = blob.download_as_bytes()
        logger.info("Downloaded bytes from GCS", extra={"source": source_blob, "size": len(data)})
        return data
    except Exception as e:
        logger.error("Failed to download bytes from GCS", extra={"error": str(e)})
        raise


def get_secret_from_manager(project_id: str, secret_name: str, version: str = "latest") -> str:
    """Retrieve a secret value from GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
        response = client.access_secret_version(name=name)
        return response.payload.data.decode("utf-8")
    except Exception as e:
        logger.error("Failed to get secret from Secret Manager", extra={"error": str(e), "secret": secret_name})
        raise


def create_secret_in_manager(project_id: str, secret_name: str, secret_value: str) -> None:
    """Create or update a secret in GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{project_id}"

        # Try to create the secret, ignore if it already exists
        try:
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
        except Exception:
            pass  # Secret already exists

        # Add a new version
        secret_path = f"projects/{project_id}/secrets/{secret_name}"
        client.add_secret_version(
            request={
                "parent": secret_path,
                "payload": {"data": secret_value.encode("utf-8")},
            }
        )
        logger.info("Created/updated secret in Secret Manager", extra={"secret": secret_name})
    except Exception as e:
        logger.error("Failed to create secret in Secret Manager", extra={"error": str(e)})
        raise
