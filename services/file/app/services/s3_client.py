import logging
from contextlib import asynccontextmanager
from typing import BinaryIO
import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

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

    @asynccontextmanager
    async def get_client(self):
        async with self.session.client("s3", **self.config) as client:
            yield client

    async def ensure_bucket_exists(self):
        """
        Проверяет наличие бакета. Если нет — создает.
        """
        async with self.get_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket)
                logger.info(f"Bucket '{self.bucket}' exists.")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    logger.warning(f"Bucket '{self.bucket}' not found. Creating...")
                    await client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Bucket '{self.bucket}' created successfully.")
                else:
                    logger.critical(f"Error checking bucket: {e}")
                    raise

    async def upload_fileobj(self, file_obj: BinaryIO, object_key: str, content_type: str):
        async with self.get_client() as client:
            await client.upload_fileobj(
                file_obj,
                self.bucket,
                object_key,
                ExtraArgs={'ContentType': content_type}
            )
            logger.info(f"Uploaded file stream to S3: {object_key}")

    async def delete_file(self, object_key: str):
        async with self.get_client() as client:
            await client.delete_object(Bucket=self.bucket, Key=object_key)
            logger.info(f"Deleted file from S3: {object_key}")

    async def generate_presigned_url(self, object_key: str, expiration: int = 3600) -> str:
        async with self.get_client() as client:
            try:
                url = await client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket, 'Key': object_key},
                    ExpiresIn=expiration
                )

                if settings.S3_PUBLIC_DOMAIN:
                    if settings.S3_ENDPOINT_URL in url:
                        return url.replace(settings.S3_ENDPOINT_URL, settings.S3_PUBLIC_DOMAIN)
                
                return url
            except ClientError as e:
                logger.error(f"Error generating URL: {e}")
                return ""

s3_service = S3Service()