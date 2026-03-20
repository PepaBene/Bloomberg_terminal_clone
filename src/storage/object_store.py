"""S3 / MinIO object storage abstraction for raw file archival.

Stores raw source files (SEC filings, XBRL documents, FRED JSON, etc.)
using the path convention::

    s3://{bucket}/raw/{domain}/{source}/{date}/{filename}

When S3 credentials are not configured, falls back to local filesystem
storage under ``data/raw/``.
"""

import logging
import os
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-import boto3 only when S3 is actually configured
_s3_client = None


def _get_s3_client():
    """Return a cached boto3 S3 client (or None if not configured)."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    endpoint = os.getenv("S3_ENDPOINT", "")
    access_key = os.getenv("S3_ACCESS_KEY", "")
    secret_key = os.getenv("S3_SECRET_KEY", "")

    if not (endpoint and access_key and secret_key):
        return None

    try:
        import boto3

        _s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        return _s3_client
    except ImportError:
        logger.warning("boto3 not installed; falling back to local storage.")
        return None


_DEFAULT_BUCKET = os.getenv("S3_BUCKET", "bloomberg-raw")
_LOCAL_BASE = Path("data/raw")


def put(
    domain: str,
    source: str,
    file_date: date,
    filename: str,
    data: bytes,
    *,
    bucket: str | None = None,
) -> str:
    """Store a raw file.

    Parameters
    ----------
    domain : str
        Data domain (e.g. "macro", "fundamentals").
    source : str
        Source system (e.g. "FRED", "EDGAR").
    file_date : date
        Logical date for partitioning.
    filename : str
        File name within the partition.
    data : bytes
        Raw file content.
    bucket : str, optional
        Override the default S3 bucket.

    Returns
    -------
    str
        The storage path where the file was written.
    """
    bucket = bucket or _DEFAULT_BUCKET
    key = f"raw/{domain}/{source}/{file_date.isoformat()}/{filename}"

    client = _get_s3_client()
    if client is not None:
        client.put_object(Bucket=bucket, Key=key, Body=data)
        path = f"s3://{bucket}/{key}"
        logger.debug("Stored %s (%d bytes)", path, len(data))
        return path

    # Local fallback
    local_path = _LOCAL_BASE / domain / source / file_date.isoformat() / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    path = str(local_path)
    logger.debug("Stored locally %s (%d bytes)", path, len(data))
    return path


def get(
    domain: str,
    source: str,
    file_date: date,
    filename: str,
    *,
    bucket: str | None = None,
) -> bytes | None:
    """Retrieve a raw file.

    Returns None if the file does not exist.
    """
    bucket = bucket or _DEFAULT_BUCKET
    key = f"raw/{domain}/{source}/{file_date.isoformat()}/{filename}"

    client = _get_s3_client()
    if client is not None:
        try:
            response = client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except client.exceptions.NoSuchKey:
            return None
        except Exception:
            logger.exception("Failed to retrieve %s from S3", key)
            return None

    # Local fallback
    local_path = _LOCAL_BASE / domain / source / file_date.isoformat() / filename
    if local_path.exists():
        return local_path.read_bytes()
    return None
