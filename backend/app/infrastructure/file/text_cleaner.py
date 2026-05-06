from __future__ import annotations

import re


# 整行图片文件名：image123.png
_IMAGE_FILENAME_LINE = re.compile(
    r"(?m)^image\d+\.(png|jpe?g|gif|bmp|webp|svg|tiff?)\s*$"
)

# HTTP/HTTPS 图片链接（含 URL 查询参数）
_IMAGE_URL = re.compile(
    r"https?://\S+?\.(png|jpe?g|gif|bmp|webp|svg|tiff?)(\?\S*)?",
    re.IGNORECASE,
)

# 文件协议 URL（Tika / PDF 临时路径等）
_FILE_URL = re.compile(r"file:(//)?\\S+", re.IGNORECASE)

# 分隔线：---, ___, ***, === 至少 3 个连续符号独占一行
_SEPARATOR_LINE = re.compile(r"(?m)^\s*[-_*=]{3,}\s*$")

# 控制字符，保留 \n(0x0A) 和 \t(0x09)
_CONTROL_CHARS = re.compile(r"[--]")

# HTML 标签
_HTML_TAGS = re.compile(r"<[^>]+>")


def clean_text(text: str) -> str:
    """
    对提取后的原始文本进行规范化清洗：
    1. 去除不可见控制字符
    2. 删除图片文件名行、图片链接、文件路径
    3. 删除分隔线
    4. 统一换行符、压缩连续空行（最多保留一个空行）
    5. 去除行尾空白

    返回清洗后的字符串，首尾无多余空白。
    """
    if not text or not text.strip():
        return ""

    t = text
    t = _CONTROL_CHARS.sub("", t)
    t = _IMAGE_FILENAME_LINE.sub("", t)
    t = _IMAGE_URL.sub("", t)
    t = _FILE_URL.sub("", t)
    t = _SEPARATOR_LINE.sub("", t)

    # 统一换行符
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # 行尾空白
    t = re.sub(r"(?m)[ \t]+$", "", t)
    # 压缩连续空行：最多保留 1 个空行
    t = re.sub(r"\n{3,}", "\n\n", t)

    return t.strip()


def clean_text_limit(text: str, max_length: int) -> str:
    """清洗后截断到 max_length 字符。"""
    cleaned = clean_text(text)
    return cleaned[:max_length] if len(cleaned) > max_length else cleaned


def clean_to_single_line(text: str) -> str:
    """清洗并折叠所有换行为单个空格，适合单行展示。"""
    if not text or not text.strip():
        return ""
    result = re.sub(r"[\r\n]+", " ", text)
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def strip_html(text: str) -> str:
    """移除 HTML 标签和常见 HTML 实体，返回纯文本。"""
    if not text or not text.strip():
        return ""
    result = _HTML_TAGS.sub(" ", text)
    for entity, char in (
        ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
        ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"),
    ):
        result = result.replace(entity, char)
    result = re.sub(r"\s+", " ", result)
    return result.strip()
