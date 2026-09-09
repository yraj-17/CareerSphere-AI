"""
MinIO object-storage service.

Binary files (resumes, profile images, media) are stored in MinIO.
PostgreSQL only stores metadata via the MediaObject model.
"""
from __future__ import annotations

import io
import uuid
from datetime import timedelta
from typing import BinaryIO, Optional, Tuple

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def ping_minio() -> bool:
    try:
        get_minio_client().list_buckets()
        return True
    except Exception:
        return False


def ensure_bucket(bucket_name: Optional[str] = None) -> None:
    """Create the application bucket if missing."""
    bucket = bucket_name or settings.MINIO_BUCKET
    client = get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"[MinIO] Created bucket '{bucket}'.")
    else:
        print(f"[MinIO] Bucket '{bucket}' ready.")


def build_object_key(user_id: str, purpose: str, filename: str) -> str:
    safe_name = filename.replace("\\", "/").split("/")[-1]
    return f"{user_id}/{purpose}/{uuid.uuid4().hex}_{safe_name}"


def upload_file(
    *,
    object_key: str,
    data: BinaryIO,
    length: int,
    content_type: str,
    bucket_name: Optional[str] = None,
) -> str:
    bucket = bucket_name or settings.MINIO_BUCKET
    client = get_minio_client()
    client.put_object(
        bucket,
        object_key,
        data,
        length=length,
        content_type=content_type or "application/octet-stream",
    )
    return object_key


def upload_bytes(
    *,
    object_key: str,
    payload: bytes,
    content_type: str,
    bucket_name: Optional[str] = None,
) -> str:
    return upload_file(
        object_key=object_key,
        data=io.BytesIO(payload),
        length=len(payload),
        content_type=content_type,
        bucket_name=bucket_name,
    )


def download_file(
    object_key: str,
    bucket_name: Optional[str] = None,
) -> Tuple[bytes, str]:
    bucket = bucket_name or settings.MINIO_BUCKET
    client = get_minio_client()
    response = client.get_object(bucket, object_key)
    try:
        data = response.read()
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        return data, content_type
    finally:
        response.close()
        response.release_conn()


def delete_file(object_key: str, bucket_name: Optional[str] = None) -> None:
    bucket = bucket_name or settings.MINIO_BUCKET
    try:
        get_minio_client().remove_object(bucket, object_key)
    except S3Error:
        raise


def presigned_get_url(
    object_key: str,
    expires_hours: int = 1,
    bucket_name: Optional[str] = None,
) -> str:
    bucket = bucket_name or settings.MINIO_BUCKET
    url = get_minio_client().presigned_get_object(
        bucket,
        object_key,
        expires=timedelta(hours=expires_hours),
    )
    if settings.MINIO_PUBLIC_URL:
        # Rewrite host for browser-facing URLs when behind a proxy / alternate host
        from urllib.parse import urlparse, urlunparse

        public = urlparse(settings.MINIO_PUBLIC_URL)
        parsed = urlparse(url)
        url = urlunparse(
            (
                public.scheme or parsed.scheme,
                public.netloc or parsed.netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )
    return url
