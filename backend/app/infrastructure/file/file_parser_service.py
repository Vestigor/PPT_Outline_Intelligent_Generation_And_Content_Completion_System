from __future__ import annotations

import hashlib
import io

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.infrastructure.file.text_cleaner import clean_text
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

SUPPORTED_MIME_TYPES = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/plain",
})

_MIN_CHUNK = 32


class DocumentParserService:
    """
    文档格式识别、文本提取与分块服务。

    支持格式：
      PDF   → pdfplumber 逐页提取
      DOCX  → python-docx 段落提取
      MD/TXT → UTF-8 直接解码
    """

    def parse(self, content: bytes, file_type: str) -> str:
        """
        按 MIME 类型解析文件并返回清洗后的纯文本。

        Raises:
            BusinessException(UNSUPPORTED_FILE_TYPE): 不支持的文件类型
            BusinessException(EMPTY_FILE_CONTENT): 提取后文本为空
        """

        if "pdf" in file_type:
            raw = self._parse_pdf(content)
        elif "wordprocessingml" in file_type or "docx" in file_type:
            raw = self._parse_docx(content)
        elif "markdown" in file_type or "plain" in file_type or "text" in file_type:
            raw = content.decode("utf-8", errors="replace")
        else:
            logger.warning("Unsupported file type rejected: %s", file_type)
            raise BusinessException.exc(StatusCode.UNSUPPORTED_FILE_TYPE.value)

        cleaned = clean_text(raw)
        if not cleaned.strip():
            logger.warning("Empty content after parsing file type=%s", file_type)
            raise BusinessException.exc(StatusCode.EMPTY_FILE_CONTENT.value)

        return cleaned

    def compute_hash(self, cleaned_text: str) -> str:
        """对清洗后文本计算 SHA-256 指纹（用于去重检测）。"""
        return hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

    def split_into_chunks(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 64,
    ) -> list[str]:
        """
        语义分块策略：
        1. 以双换行为段落边界，保持语义完整
        2. 超长段落使用滑动窗口（步长 = chunk_size - overlap）
        3. 过滤短块（< _MIN_CHUNK 字符）
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        for para in paragraphs:
            if len(para) <= chunk_size:
                if len(para) >= _MIN_CHUNK:
                    chunks.append(para)
            else:
                step = max(1, chunk_size - overlap)
                for i in range(0, len(para), step):
                    piece = para[i : i + chunk_size]
                    if len(piece) >= _MIN_CHUNK:
                        chunks.append(piece)
        return chunks

    @staticmethod
    def is_supported(file_type: str) -> bool:
        return any(
            t in file_type
            for t in ("pdf", "wordprocessingml", "docx", "markdown", "plain", "text")
        )

    # ──────────────────────────────────────────────
    # 私有解析方法
    # ──────────────────────────────────────────────

    @staticmethod
    def _parse_pdf(content: bytes) -> str:
        import pdfplumber

        pages_text: list[str] = []
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        pages_text.append(extracted)
        except Exception as e:
            logger.error("PDF parsing failed: %s", e)
            raise BusinessException.exc(StatusCode.PARSE_FAILED.value)
        return "\n\n".join(pages_text)

    @staticmethod
    def _parse_docx(content: bytes) -> str:
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        except Exception as e:
            logger.error("DOCX parsing failed: %s", e)
            raise BusinessException.exc(StatusCode.PARSE_FAILED.value)
        return "\n\n".join(paras)
