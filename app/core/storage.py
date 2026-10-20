"""S3-compatible storage wrapper (Integration Standard point 7). Falls back to
local disk under ./data/local_storage when no S3 endpoint is reachable, so the
service still runs with docker compose's MinIO or with nothing at all."""
import os
import json
import uuid
from datetime import datetime

from app.core.config import settings

LOCAL_ROOT = os.path.join("data", "local_storage")


def _use_s3() -> bool:
    return bool(settings.S3_ENDPOINT_URL) and os.environ.get("INCUBRIX_FORCE_LOCAL_STORAGE") != "1"


def _client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        use_ssl=settings.S3_USE_SSL,
        config=Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 1}),
    )


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Stores bytes and returns a download link."""
    if _use_s3():
        try:
            c = _client()
            try:
                c.create_bucket(Bucket=settings.S3_BUCKET)
            except Exception:
                pass
            c.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=content_type)
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"
        except Exception:
            pass  # fall through to local storage
    path = os.path.join(LOCAL_ROOT, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return f"file://{os.path.abspath(path)}"


def put_json(key: str, obj: dict) -> str:
    return put_bytes(key, json.dumps(obj, indent=2, default=str).encode(), "application/json")


def new_key(prefix: str, ext: str = "json") -> str:
    return f"{prefix}/{datetime.utcnow().strftime('%Y%m%d')}/{uuid.uuid4().hex}.{ext}"
