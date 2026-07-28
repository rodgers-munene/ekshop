import logging
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


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


def upload_product_image(*, product_id: uuid.UUID, filename: str, content_type: str, data: bytes) -> str:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise StorageError(f"Unsupported image type: {content_type}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise StorageError("Image exceeds the 5MB size limit")

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    key = f"products/{product_id}/{uuid.uuid4().hex}.{extension}"

    try:
        _client().put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as e:
        raise StorageError(f"Upload failed: {e}") from e

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
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise StorageError(f"Unsupported image type: {content_type}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise StorageError("Image exceeds the 5MB size limit")

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    key = f"hero-slides/{uuid.uuid4().hex}.{extension}"

    try:
        _client().put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as e:
        raise StorageError(f"Upload failed: {e}") from e

    return _public_url(key)


def delete_hero_image(url: str) -> None:
    key = key_from_url(url)
    if not key:
        return
    try:
        _client().delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    except (BotoCoreError, ClientError, StorageError) as e:
        logger.warning("Failed to delete S3 object for %s: %s", url, e)
