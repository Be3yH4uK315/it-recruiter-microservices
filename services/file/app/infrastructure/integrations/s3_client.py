from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.application.common.contracts import ObjectStorage
from app.config import Settings

try:
    import aioboto3
except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent import
    aioboto3 = None
    _S3_IMPORT_ERROR = exc
else:
    _S3_IMPORT_ERROR = None

try:
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError
    from botocore.session import get_session as get_botocore_session
except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent import
    BotoConfig = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment]
    get_botocore_session = None  # type: ignore[assignment]
    if _S3_IMPORT_ERROR is None:
        _S3_IMPORT_ERROR = exc


class S3ObjectStorage(ObjectStorage):
    def __init__(self, settings: Settings) -> None:
        if aioboto3 is None or BotoConfig is None or get_botocore_session is None:
            raise RuntimeError(
                "aioboto3/botocore are required for S3ObjectStorage"
            ) from _S3_IMPORT_ERROR
        self._settings = settings
        self._session = aioboto3.Session()
        self._bucket = settings.s3_bucket_name

        common_config = BotoConfig(
            s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
            signature_version="s3v4",
        )

        self._client_config = {
            "endpoint_url": settings.s3_endpoint_url,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
            "config": common_config,
        }

        public_endpoint = settings.s3_public_endpoint_url or settings.s3_endpoint_url
        self._presign_client_config = {
            "endpoint_url": public_endpoint,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
            "config": common_config,
        }
        self._presign_client = get_botocore_session().create_client(
            "s3",
            **self._presign_client_config,
        )

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator:
        async with self._session.client("s3", **self._client_config) as client:
            yield client

    @asynccontextmanager
    async def _get_presign_client(self) -> AsyncIterator:
        async with self._session.client("s3", **self._presign_client_config) as client:
            yield client

    async def ensure_bucket_exists(self) -> None:
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self._bucket)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchBucket", "NotFound"}:
                    await client.create_bucket(Bucket=self._bucket)
                    return
                raise

    async def generate_presigned_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        return self._presign_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    async def generate_presigned_download_url(
        self,
        *,
        object_key: str,
        expires_in: int,
    ) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
            },
            ExpiresIn=expires_in,
        )

    async def delete_object(self, *, object_key: str) -> None:
        async with self._get_client() as client:
            await client.delete_object(Bucket=self._bucket, Key=object_key)

    async def object_exists(self, *, object_key: str) -> bool:
        async with self._get_client() as client:
            try:
                await client.head_object(Bucket=self._bucket, Key=object_key)
                return True
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise

    async def get_object_size(self, *, object_key: str) -> int | None:
        async with self._get_client() as client:
            try:
                response = await client.head_object(Bucket=self._bucket, Key=object_key)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey", "NotFound"}:
                    return None
                raise

            content_length = response.get("ContentLength")
            return int(content_length) if content_length is not None else None
