import logging
from contextlib import asynccontextmanager
from typing import BinaryIO
import aioboto3
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from datetime import datetime
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_s3_retriable(exception: Exception) -> bool:
    """S3 операции, которые стоит повторять."""
    if not isinstance(exception, ClientError):
        return False

    error_code = exception.response.get("Error", {}).get("Code")
    retriable_codes = {
        "ServiceUnavailable",
        "RequestTimeout",
        "Throttling",
        "RequestLimitExceeded",
        "InternalError",
    }
    return error_code in retriable_codes


class S3Service:
    def __init__(self):
        self.session = aioboto3.Session()
        self.config = {
            "endpoint_url": settings.S3_ENDPOINT_URL,
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "region_name": settings.S3_REGION,
        }
        self.bucket = settings.S3_BUCKET_NAME

        self.upload_count = 0
        self.upload_bytes = 0
        self.upload_errors = 0
        self.delete_count = 0
        self.delete_errors = 0

    @asynccontextmanager
    async def get_client(self):
        """Context manager для S3 клиента."""
        async with self.session.client("s3", **self.config) as client:
            yield client

    async def ensure_bucket_exists(self):
        """Проверяет наличие бакета. Если нет — создает."""
        async with self.get_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket)
                logger.info(f"Bucket '{self.bucket}' exists.")
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "404":
                    logger.warning(f"Bucket '{self.bucket}' not found. Creating...")
                    await client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Bucket '{self.bucket}' created successfully.")
                else:
                    logger.critical(f"Error checking bucket: {e}")
                    raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ClientError, ConnectionError)),
    )
    async def upload_fileobj(
        self, file_obj: BinaryIO, object_key: str, content_type: str
    ):
        """Обновить файл с retry логикой и metrics."""
        start_time = datetime.utcnow()
        file_size = 0

        try:
            async with self.get_client() as client:
                if hasattr(file_obj, "seek") and hasattr(file_obj, "tell"):
                    current_pos = file_obj.tell()
                    file_obj.seek(0, 2)
                    file_size = file_obj.tell()
                    file_obj.seek(current_pos)

                await client.upload_fileobj(
                    file_obj,
                    self.bucket,
                    object_key,
                    ExtraArgs={"ContentType": content_type},
                )

            duration = (datetime.utcnow() - start_time).total_seconds()
            self.upload_count += 1
            self.upload_bytes += file_size

            logger.info(
                "s3_upload_success",
                extra={
                    "object_key": object_key,
                    "file_size_bytes": file_size,
                    "file_size_mb": round(file_size / (1024 * 1024), 2),
                    "duration_seconds": round(duration, 2),
                    "speed_mbps": round(
                        (file_size / (1024 * 1024)) / duration, 2
                    )
                    if duration > 0
                    else 0,
                    "total_uploads": self.upload_count,
                    "total_bytes_mb": round(self.upload_bytes / (1024 * 1024), 2),
                },
            )

        except ClientError as e:
            self.upload_errors += 1
            error_code = e.response.get("Error", {}).get("Code")

            if is_s3_retriable(e):
                logger.warning(
                    "s3_upload_retriable_error",
                    extra={
                        "object_key": object_key,
                        "error_code": error_code,
                        "error_msg": str(e),
                    },
                )
                raise
            else:
                logger.error(
                    "s3_upload_fatal_error",
                    extra={
                        "object_key": object_key,
                        "error_code": error_code,
                        "error_msg": str(e),
                    },
                )
                raise

    async def delete_file(self, object_key: str):
        """Удалить файл с error обработкой."""
        try:
            async with self.get_client() as client:
                await client.delete_object(Bucket=self.bucket, Key=object_key)
                self.delete_count += 1
                logger.info(f"Deleted file from S3: {object_key}")
        except ClientError as e:
            self.delete_errors += 1
            logger.error(f"Failed to delete file {object_key}: {e}")
            raise

    async def generate_presigned_url(
        self, object_key: str, expiration: int = 3600
    ) -> str:
        """Сгенерировать presigned URL с логированием."""
        try:
            async with self.get_client() as client:
                url = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": object_key},
                    ExpiresIn=expiration,
                )

                if settings.S3_PUBLIC_DOMAIN:
                    if settings.S3_ENDPOINT_URL in url:
                        url = url.replace(
                            settings.S3_ENDPOINT_URL, settings.S3_PUBLIC_DOMAIN
                        )

                logger.info(
                    "presigned_url_generated",
                    extra={
                        "object_key": object_key,
                        "expires_in_seconds": expiration,
                        "uses_public_domain": bool(settings.S3_PUBLIC_DOMAIN),
                    },
                )

                return url

        except ClientError as e:
            logger.error(
                "presigned_url_generation_failed",
                extra={"object_key": object_key, "error": str(e)},
            )
            return ""

    async def batch_upload(
        self, files: list[tuple], max_concurrent: int = 5
    ) -> tuple[int, int]:
        """Пакетная загрузка с контролем concurrency и расширенным логированием."""
        logger.info("batch_upload_started", extra={"file_count": len(files)})

        semaphore = asyncio.Semaphore(max_concurrent)

        async def upload_with_semaphore(file_obj, key, content_type):
            async with semaphore:
                try:
                    await self.upload_fileobj(file_obj, key, content_type)
                    return True
                except Exception as e:
                    logger.error(
                        "batch_upload_file_failed",
                        extra={"key": key, "error": str(e)},
                    )
                    return False

        tasks = [
            upload_with_semaphore(file_obj, key, content_type)
            for file_obj, key, content_type in files
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        failed = len(files) - successful

        logger.info(
            "batch_upload_completed",
            extra={
                "total": len(files),
                "successful": successful,
                "failed": failed,
                "success_rate": round((successful / len(files) * 100), 2)
                if files
                else 0,
            },
        )

        return successful, failed

    def get_stats(self) -> dict:
        """Метрики для мониторинга."""
        return {
            "upload_count": self.upload_count,
            "upload_bytes_mb": round(self.upload_bytes / (1024 * 1024), 2),
            "upload_errors": self.upload_errors,
            "delete_count": self.delete_count,
            "delete_errors": self.delete_errors,
            "error_rate": round(
                (self.upload_errors / self.upload_count * 100), 2
            )
            if self.upload_count > 0
            else 0,
        }


s3_service = S3Service()
