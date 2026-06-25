"""Thin S3 wrapper for reference-document originals.

Every document keeps its text in the DB `content` column (the persona read path);
its original artifact (uploaded file, or a .md mirror of pasted text) lives in S3.

S3 is optional: if `s3_bucket` is unset we treat storage as disabled and callers
get a clear error when they try to use it. The boto3 client is built lazily and
cached so importing this module never requires AWS config.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from .config import get_settings

logger = logging.getLogger(__name__)


class StorageError(RuntimeError):
    """Raised when S3 is unconfigured or an S3 operation fails."""


def is_enabled() -> bool:
    return bool(get_settings().s3_bucket)


@lru_cache
def _client():
    """Lazily build (and cache) the boto3 S3 client from settings."""
    import boto3  # imported here so the dep is only needed when S3 is used

    settings = get_settings()
    if not settings.s3_bucket:
        raise StorageError("S3 is not configured (S3_BUCKET is empty).")

    kwargs: dict = {"region_name": settings.aws_region}
    # Fall back to the default credential chain (IAM role, env) when keys are
    # not explicitly set — handy on Railway/EC2.
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

    return boto3.client("s3", **kwargs)


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(filename: str) -> str:
    """Collapse anything risky in a filename to underscores; keep it short."""
    name = _SAFE.sub("_", filename.strip()) or "file"
    return name[:120]


def build_key(doc_id: int, filename: str) -> str:
    """S3 object key for a document's original artifact."""
    return f"documents/{doc_id}/{_safe_filename(filename)}"


def put_object(key: str, data: bytes, content_type: str | None = None) -> None:
    settings = get_settings()
    extra = {"ContentType": content_type} if content_type else {}
    try:
        _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, **extra)
    except Exception as exc:  # noqa: BLE001 — surface as a typed storage error
        raise StorageError(f"Failed to upload to S3: {exc}") from exc


def delete_object(key: str) -> None:
    settings = get_settings()
    try:
        _client().delete_object(Bucket=settings.s3_bucket, Key=key)
    except Exception as exc:  # noqa: BLE001
        raise StorageError(f"Failed to delete from S3: {exc}") from exc


def presigned_get_url(key: str, expires: int = 900) -> str:
    settings = get_settings()
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )
    except Exception as exc:  # noqa: BLE001
        raise StorageError(f"Failed to sign S3 URL: {exc}") from exc
