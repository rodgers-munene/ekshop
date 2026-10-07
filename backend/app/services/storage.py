import logging
import re
import uuid
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# KYC accepts PDF as well as images: a national ID or licence is often scanned
# rather than photographed, and rejecting PDF would leave riders with no way to
# comply on a phone.
ALLOWED_KYC_CONTENT_TYPES = ALLOWED_CONTENT_TYPES | {"application/pdf"}
MAX_KYC_UPLOAD_BYTES = 10 * 1024 * 1024  # a scanned page is larger than a product shot


class StorageError(Exception):
    pass


def _client():
    if not (settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY and settings.AWS_S3_BUCKET):
        raise StorageError(
            "AWS S3 is not configured: set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY "
            "and AWS_S3_BUCKET before uploading product images."
        )
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _public_url(key: str) -> str:
    if settings.AWS_S3_PUBLIC_URL:
        return f"{settings.AWS_S3_PUBLIC_URL.rstrip('/')}/{key}"
    return f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


def key_from_url(url: str) -> str | None:
    """Recover the S3 object key from a public URL produced by upload_product_image."""
    if settings.AWS_S3_PUBLIC_URL and url.startswith(settings.AWS_S3_PUBLIC_URL):
        return url[len(settings.AWS_S3_PUBLIC_URL.rstrip("/")) + 1:]
    marker = f".amazonaws.com/"
    if marker in url:
        return url.split(marker, 1)[1]
    return None


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"


def _put(*, key: str, content_type: str, data: bytes, allowed: set, max_bytes: int, label: str) -> None:
    """Validate and write one object. Shared so the three uploaders below do not
    each repeat the same validation and the same two exception handlers."""
    if content_type not in allowed:
        raise StorageError(f"Unsupported {label} type: {content_type}")
    if len(data) > max_bytes:
        raise StorageError(f"{label} exceeds the {max_bytes // (1024 * 1024)}MB size limit")
    try:
        _client().put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as e:
        raise StorageError(f"Upload failed: {e}") from e


def upload_product_image(*, product_id: uuid.UUID, filename: str, content_type: str, data: bytes) -> str:
    key = f"products/{product_id}/{uuid.uuid4().hex}.{_extension(filename)}"
    _put(
        key=key,
        content_type=content_type,
        data=data,
        allowed=ALLOWED_CONTENT_TYPES,
        max_bytes=MAX_UPLOAD_BYTES,
        label="image",
    )
    return _public_url(key)


def delete_product_image(url: str) -> None:
    key = key_from_url(url)
    if not key:
        return
    try:
        _client().delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    except (BotoCoreError, ClientError, StorageError) as e:
        logger.warning("Failed to delete S3 object for %s: %s", url, e)


def upload_hero_image(*, filename: str, content_type: str, data: bytes) -> str:
    key = f"hero-slides/{uuid.uuid4().hex}.{_extension(filename)}"
    _put(
        key=key,
        content_type=content_type,
        data=data,
        allowed=ALLOWED_CONTENT_TYPES,
        max_bytes=MAX_UPLOAD_BYTES,
        label="image",
    )
    return _public_url(key)


def delete_hero_image(url: str) -> None:
    key = key_from_url(url)
    if not key:
        return
    try:
        _client().delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    except (BotoCoreError, ClientError, StorageError) as e:
        logger.warning("Failed to delete S3 object for %s: %s", url, e)


def upload_category_icon(*, category_id: uuid.UUID, filename: str, content_type: str, data: bytes) -> str:
    key = f"categories/{category_id}/{uuid.uuid4().hex}.{_extension(filename)}"
    _put(
        key=key,
        content_type=content_type,
        data=data,
        allowed=ALLOWED_CONTENT_TYPES,
        max_bytes=MAX_UPLOAD_BYTES,
        label="image",
    )
    return _public_url(key)


def delete_category_icon(url: str) -> None:
    key = key_from_url(url)
    if not key:
        return
    try:
        _client().delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    except (BotoCoreError, ClientError, StorageError) as e:
        logger.warning("Failed to delete S3 object for %s: %s", url, e)


# ── Rider KYC documents ──────────────────────────────────────────────────────
#
# Separate bucket, separate credentials, and nothing publicly reachable. These
# functions deliberately do not reuse _client(): the point of the split is that
# the KYC bucket is a different trust boundary with its own access key.


def _kyc_client():
    missing = [
        name
        for name, value in (
            ("KYC_S3_BUCKET", settings.KYC_S3_BUCKET),
            ("KYC_S3_ACCESS_KEY_ID", settings.KYC_S3_ACCESS_KEY_ID),
            ("KYC_S3_SECRET_ACCESS_KEY", settings.KYC_S3_SECRET_ACCESS_KEY),
        )
        if not value
    ]
    if missing:
        raise StorageError(
            "KYC document storage is not configured. Set "
            + ", ".join(missing)
            + " before a rider uploads identity documents."
        )
    return boto3.client(
        "s3",
        region_name=settings.KYC_S3_REGION,
        aws_access_key_id=settings.KYC_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.KYC_S3_SECRET_ACCESS_KEY,
    )


def upload_kyc_document(
    *,
    agent_id: uuid.UUID,
    kind: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> str:
    """Store one identity document and return its **object key**, not a URL.

    Returning the key is deliberate. A presigned URL expires, so storing one in
    the database would leave the admin review queue pointing at a dead link; the
    URL is generated on read instead.
    """
    if content_type not in ALLOWED_KYC_CONTENT_TYPES:
        raise StorageError(f"Unsupported KYC document type: {content_type}")
    if len(data) > MAX_KYC_UPLOAD_BYTES:
        raise StorageError(
            f"KYC document exceeds the {MAX_KYC_UPLOAD_BYTES // (1024 * 1024)}MB size limit"
        )

    # `kind` is caller-supplied, so it is reduced to a safe path segment rather
    # than trusted: a value like "../../users" must not be able to walk out of
    # the rider's own prefix.
    safe_kind = re.sub(r"[^a-z0-9_-]+", "-", (kind or "document").lower()).strip("-") or "document"
    key = f"kyc/{agent_id}/{safe_kind}/{uuid.uuid4().hex}.{_extension(filename)}"

    try:
        _kyc_client().put_object(
            Bucket=settings.KYC_S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as e:
        raise StorageError(f"KYC upload failed: {e}") from e

    return key


def presign_kyc_url(key: str, expires_seconds: Optional[int] = None) -> Optional[str]:
    """A time-limited view URL for one stored KYC document.

    Returns None rather than raising when storage is unconfigured, so a read of
    the review queue degrades to "documents unavailable" instead of 500-ing the
    whole admin screen.
    """
    if not key:
        return None
    try:
        client = _kyc_client()
    except StorageError:
        logger.warning("KYC storage is not configured; cannot presign %s", key)
        return None
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.KYC_S3_BUCKET, "Key": key},
            ExpiresIn=expires_seconds or settings.KYC_URL_EXPIRY_SECONDS,
        )
    except (BotoCoreError, ClientError) as e:
        logger.warning("Could not presign KYC object %s: %s", key, e)
        return None


def delete_kyc_document(key: str) -> None:
    """Best-effort removal. Never raises: a stale object is an operational
    problem, not a reason to fail the request that triggered the delete."""
    if not key:
        return
    try:
        _kyc_client().delete_object(Bucket=settings.KYC_S3_BUCKET, Key=key)
    except (BotoCoreError, ClientError, StorageError) as e:
        logger.warning("Failed to delete KYC object %s: %s", key, e)
