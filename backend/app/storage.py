"""Object storage for product images, behind a small interface so tests can swap it out."""

from functools import lru_cache
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from app.config import Settings, get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def delete(self, key: str) -> None: ...


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def ensure_bucket(self) -> bool:
        """Create the bucket if it doesn't exist. Returns True if it was created."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return False
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)
            return True


class MemoryStorage:
    """Keeps files in a dict. Used by tests."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.files[key] = (data, content_type)

    def delete(self, key: str) -> None:
        self.files.pop(key, None)


@lru_cache
def get_storage() -> Storage:
    return S3Storage(get_settings())


def public_url(key: str) -> str:
    return f"{get_settings().s3_public_base_url.rstrip('/')}/{key}"
