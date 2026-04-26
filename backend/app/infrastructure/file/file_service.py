from __future__ import annotations

from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


class FileService:
    """
    对象存储服务（OSS / S3 协议兼容）。
    负责原始文件的上传、下载与删除。
    Embedding Worker 和 SessionService 通过此服务读写文件，
    其余模块仅存储 oss_key，不直接操作文件内容。
    """

    def __init__(self) -> None:
        # TODO: 初始化 OSS / S3 客户端（从 settings 读取 endpoint / bucket / ak / sk）
        self._client = None
        self._bucket: str = ""

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """
        上传字节内容到对象存储，返回 oss_key。
        key 建议格式：{module}/{user_id}/{hash}_{filename}
        """
        # TODO: PUT object，设置 content-type
        pass

    async def download(self, key: str) -> bytes:
        """按 oss_key 下载文件字节内容。"""
        # TODO: GET object，返回 body bytes
        pass

    async def delete(self, key: str) -> bool:
        """删除对象，返回是否成功。"""
        # TODO: DELETE object
        pass

    async def exists(self, key: str) -> bool:
        """检查对象是否存在（HEAD object）。"""
        # TODO: HEAD object，200 则 True，404 则 False
        pass

    def get_presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        """
        生成预签名下载链接，用于临时授权访问（如导出 PPT 文件后提供下载链接）。
        """
        # TODO: 生成带签名的临时 URL
        pass
