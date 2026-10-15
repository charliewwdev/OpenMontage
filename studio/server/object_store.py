"""S3-compatible object store (DTok MinIO).

Reads the same OSS_* names as dtok-app, plus Studio-specific overrides:

  OSS_API_BASE_URL / MINIO_ENDPOINT / S3_ENDPOINT
  OSS_CONSOLE_USERNAME / MINIO_ACCESS_KEY / S3_ACCESS_KEY
  OSS_CONSOLE_PASSWORD / MINIO_SECRET_KEY / S3_SECRET_KEY
  MINIO_BUCKET / S3_BUCKET          (default: dtok-app)
  MINIO_PREFIX / S3_PREFIX          (default: openmontage)
  MINIO_PUBLIC_BASE / S3_PUBLIC_BASE (default: OSS_API_BASE_URL)

Blobs live under ``{prefix}/inspire/{id}`` and ``{prefix}/media/{project}/{rel}``.
Postgres keeps metadata (and optional BYTEA fallback). Disk is a local cache.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote

logger = logging.getLogger("studio.object_store")

_client = None
_client_failed = False


def _first(*names: str, default: str = "") -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return default


def endpoint() -> str:
    return _first("MINIO_ENDPOINT", "S3_ENDPOINT", "OSS_API_BASE_URL").rstrip("/")


def access_key() -> str:
    return _first("MINIO_ACCESS_KEY", "S3_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "OSS_CONSOLE_USERNAME")


def secret_key() -> str:
    return _first("MINIO_SECRET_KEY", "S3_SECRET_KEY", "AWS_SECRET_ACCESS_KEY", "OSS_CONSOLE_PASSWORD")


def bucket() -> str:
    return _first("MINIO_BUCKET", "S3_BUCKET", default="dtok-app")


def prefix() -> str:
    return _first("MINIO_PREFIX", "S3_PREFIX", default="openmontage").strip("/")


def public_base() -> str:
    return _first("MINIO_PUBLIC_BASE", "S3_PUBLIC_BASE", "OSS_API_BASE_URL", "MINIO_ENDPOINT").rstrip("/")


def enabled() -> bool:
    return bool(endpoint() and access_key() and secret_key() and bucket())


def ping() -> dict[str, Any]:
    if not enabled():
        return {"enabled": False}
    try:
        client = _s3()
        if client is None:
            return {"enabled": True, "ok": False, "error": "boto3 missing"}
        # HeadBucket often 403 on this shared dtok-app policy; PUT+GET a tiny probe instead.
        key = f"{prefix()}/.health"
        client.put_object(Bucket=bucket(), Key=key, Body=b"ok", ContentType="text/plain")
        client.get_object(Bucket=bucket(), Key=key)
        return {
            "enabled": True,
            "ok": True,
            "bucket": bucket(),
            "prefix": prefix(),
            "endpoint": endpoint(),
        }
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc)[:200]}


def _s3():
    global _client, _client_failed
    if _client is not None or _client_failed:
        return _client
    if not enabled():
        return None
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        logger.error("boto3 not installed: %s", exc)
        _client_failed = True
        return None
    _client = boto3.client(
        "s3",
        endpoint_url=endpoint(),
        aws_access_key_id=access_key(),
        aws_secret_access_key=secret_key(),
        region_name=_first("MINIO_REGION", "S3_REGION", "AWS_REGION", default="us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    return _client


def _key(*parts: str) -> str:
    segs = [prefix()]
    for part in parts:
        chunk = str(part or "").replace("\\", "/").strip("/")
        if not chunk or ".." in chunk.split("/"):
            raise ValueError("invalid object key")
        segs.append(chunk)
    return "/".join(segs)


def public_url(key: str) -> str:
    base = public_base()
    if not base:
        return ""
    return f"{base}/{bucket()}/{quote(key, safe='/')}"


def put_bytes(key: str, data: bytes, content_type: str | None = None) -> str:
    client = _s3()
    if client is None:
        raise RuntimeError("object store not configured")
    ctype = (content_type or "application/octet-stream").strip()
    extra: dict[str, Any] = {}
    acl = _first("MINIO_ACL", "S3_ACL")
    if acl:
        extra["ACL"] = acl
    client.put_object(
        Bucket=bucket(),
        Key=key,
        Body=data,
        ContentType=ctype,
        **extra,
    )
    return public_url(key)


def get_bytes(key: str) -> tuple[bytes, str] | None:
    client = _s3()
    if client is None:
        return None
    try:
        resp = client.get_object(Bucket=bucket(), Key=key)
    except Exception:
        return None
    body = resp["Body"].read()
    ctype = str(resp.get("ContentType") or "application/octet-stream")
    return body, ctype


def exists(key: str) -> bool:
    client = _s3()
    if client is None:
        return False
    try:
        client.head_object(Bucket=bucket(), Key=key)
        return True
    except Exception:
        # Some policies deny Head but allow Get.
        return get_bytes(key) is not None


def inspire_key(item_id: str) -> str:
    return _key("inspire", item_id)


def media_key(project_id: str, rel_path: str) -> str:
    return _key("media", project_id, rel_path.replace("\\", "/").lstrip("/"))


def put_inspire(item_id: str, data: bytes, content_type: str = "image/jpeg") -> str:
    return put_bytes(inspire_key(item_id), data, content_type)


def get_inspire(item_id: str) -> tuple[bytes, str] | None:
    return get_bytes(inspire_key(item_id))


def put_media(project_id: str, rel_path: str, data: bytes, content_type: str | None = None) -> str:
    return put_bytes(media_key(project_id, rel_path), data, content_type)


def get_media(project_id: str, rel_path: str) -> tuple[bytes, str] | None:
    return get_bytes(media_key(project_id, rel_path))
