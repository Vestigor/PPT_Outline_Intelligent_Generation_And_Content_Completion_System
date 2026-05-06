from __future__ import annotations

import aioboto3
from botocore.exceptions import ClientError
from botocore.config import Config

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.config import settings
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


class FileService:
    """
    对象存储服务（S3 协议兼容，支持阿里云 OSS / MinIO）。
    通过 aioboto3 异步访问，所有方法均为 async。
    """

    def _session(self):
        return aioboto3.Session()

    def _client_kwargs(self) -> dict:
        return {
            "service_name": "s3",
            "endpoint_url": settings.OSS_ENDPOINT,
            "aws_access_key_id": settings.OSS_ACCESS_KEY,
            "aws_secret_access_key": settings.OSS_SECRET_KEY,
            "region_name": settings.OSS_REGION,
            "config": Config(
                max_pool_connections=settings.OSS_MAX_POOL_CONNECTIONS,
                retries={"max_attempts": settings.OSS_MAX_ATTEMPTS},
                # Disable automatic checksum headers — MinIO returns 502 on x-amz-checksum-mode
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        }

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传字节内容到对象存储，返回 oss_key。"""
        logger.debug("OSS upload: key=%s size=%d content_type=%s", key, len(data), content_type)
        try:
            async with self._session().client(**self._client_kwargs()) as client:
                await client.put_object(
                    Bucket=settings.OSS_BUCKET_NAME,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
            logger.info("OSS upload success: key=%s", key)
            return key
        except ClientError as e:
            logger.error("OSS upload failed: key=%s error=%s", key, e)
            raise BusinessException.exc(StatusCode.UPLOAD_DOCUMENT_FAILED.value)

    async def download(self, key: str) -> bytes:
        """按 oss_key 下载文件字节内容。"""
        logger.debug("OSS download: key=%s", key)
        try:
            async with self._session().client(**self._client_kwargs()) as client:
                response = await client.get_object(
                    Bucket=settings.OSS_BUCKET_NAME,
                    Key=key,
                )
                data: bytes = await response["Body"].read()
            logger.info("OSS download success: key=%s size=%d", key, len(data))
            return data
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("NoSuchKey", "404"):
                logger.warning("OSS key not found: key=%s", key)
                raise BusinessException.exc(StatusCode.DOCUMENT_NOT_FOUND.value)
            logger.error("OSS download failed: key=%s error=%s", key, e)
            raise BusinessException.exc(StatusCode.PARSE_FAILED.value)

    async def delete(self, key: str) -> bool:
        """删除对象，返回是否成功。"""
        logger.debug("OSS delete: key=%s", key)
        try:
            async with self._session().client(**self._client_kwargs()) as client:
                await client.delete_object(
                    Bucket=settings.OSS_BUCKET_NAME,
                    Key=key,
                )
            logger.info("OSS delete success: key=%s", key)
            return True
        except ClientError as e:
            logger.error("OSS delete failed: key=%s error=%s", key, e)
            return False

    async def exists(self, key: str) -> bool:
        """检查对象是否存在（HEAD object）。"""
        try:
            async with self._session().client(**self._client_kwargs()) as client:
                await client.head_object(
                    Bucket=settings.OSS_BUCKET_NAME,
                    Key=key,
                )
            return True
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchKey"):
                return False
            logger.error("OSS exists check error: key=%s error=%s", key, e)
            return False

    async def get_presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        """生成预签名下载链接，用于临时授权访问。"""
        logger.debug("Generating presigned URL: key=%s expires=%ds", key, expires_seconds)
        try:
            async with self._session().client(**self._client_kwargs()) as client:
                url: str = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": settings.OSS_BUCKET_NAME, "Key": key},
                    ExpiresIn=expires_seconds,
                )
            return url
        except ClientError as e:
            logger.error("Presigned URL generation failed: key=%s error=%s", key, e)
            raise BusinessException.exc(StatusCode.EXPORT_FAILED.value)
