from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
_STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=5.0)


class LLMClientError(Exception):
    """
    LLM 调用对外暴露的错误。

    message 是面向用户的中文提示（可直接展示），不含上游 URL、token 等内部细节；
    完整的原始错误（状态码、响应体）只写入日志，不外泄给前端。
    """


def _friendly_http_error(status_code: int) -> str:
    """把上游 LLM 服务的 HTTP 状态码翻译成可操作的中文提示。"""
    if status_code in (401, 403):
        return "模型鉴权失败：API Key 无效、已过期，或该账号未开通所选模型，请检查 LLM 配置。"
    if status_code == 404:
        return "所选模型不存在：请确认模型名称与服务地址（base_url）是否正确。"
    if status_code == 429:
        return "调用过于频繁或额度已用尽，请稍后再试或检查账户额度。"
    if status_code >= 500:
        return "模型服务暂时不可用，请稍后重试。"
    return f"模型调用失败（HTTP {status_code}），请检查 LLM 配置。"


class LLMClient:
    """
    统一 LLM 调用客户端，兼容 OpenAI /v1/chat/completions 标准接口。
    支持同步调用、流式调用和 JSON Schema 约束输出。
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    @classmethod
    def from_user_config(cls, api_key: str, base_url: str, model: str) -> "LLMClient":
        return cls(api_key=api_key, base_url=base_url, model=model)

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        """非流式调用，返回完整助手回复字符串。"""
        payload = self._build_payload(
            messages, temperature, max_tokens, response_format, stream=False
        )
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, trust_env=False) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                logger.error("LLM HTTP error %s: %s", e.response.status_code, e.response.text)
                raise LLMClientError(_friendly_http_error(e.response.status_code)) from e
            except httpx.TimeoutException as e:
                logger.error("LLM call timeout: %s", e)
                raise LLMClientError("模型响应超时，请稍后重试。") from e
            except httpx.RequestError as e:
                logger.error("LLM call network error: %s", e)
                raise LLMClientError("无法连接模型服务，请检查网络或服务地址（base_url）。") from e
            except Exception as e:
                logger.error("LLM call failed: %s", e)
                raise LLMClientError("模型调用失败，请稍后重试。") from e

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式调用，逐 token yield 字符串片段。
        调用方：async for token in client.chat_stream(...):
        """
        payload = self._build_payload(messages, temperature, max_tokens, stream=True)
        async with httpx.AsyncClient(timeout=_STREAM_TIMEOUT, trust_env=False) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                            choices = obj.get("choices") or []
                            # 部分 OpenAI 兼容服务（如 DashScope/通义、deepseek）
                            # 会在最后多发一个仅含 usage 的帧（choices 为空）。
                            # 这里跳过而不是 return，保证后续 [DONE] 能正常终止流。
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except Exception:
                            continue
            except httpx.HTTPStatusError as e:
                # 流式响应体可能未读取，尽量取出错误正文写日志，不外泄给用户
                detail = ""
                try:
                    detail = (await e.response.aread()).decode("utf-8", "replace")
                except Exception:
                    pass
                logger.error("LLM stream HTTP error %s: %s", e.response.status_code, detail)
                raise LLMClientError(_friendly_http_error(e.response.status_code)) from e
            except httpx.TimeoutException as e:
                logger.error("LLM stream timeout: %s", e)
                raise LLMClientError("模型响应超时，请稍后重试。") from e
            except httpx.RequestError as e:
                logger.error("LLM stream network error: %s", e)
                raise LLMClientError("无法连接模型服务，请检查网络或服务地址（base_url）。") from e
            except LLMClientError:
                raise
            except Exception as e:
                logger.error("LLM stream failed: %s", e)
                raise LLMClientError("模型调用失败，请稍后重试。") from e

    async def chat_with_schema(
        self,
        messages: list[dict[str, str]],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        """
        带 JSON Schema 约束的调用，确保输出可解析为目标结构。
        Schema 描述注入到 system 提示中；response_format 设为 json_object。
        """
        schema_desc = json.dumps(schema, ensure_ascii=False, indent=2)
        schema_instruction = (
            f"\n\n你必须以合法的 JSON 格式回复，且严格符合以下 Schema：\n```json\n{schema_desc}\n```"
        )

        enhanced = list(messages)
        if enhanced and enhanced[0]["role"] == "system":
            enhanced[0] = {
                "role": "system",
                "content": enhanced[0]["content"] + schema_instruction,
            }
        else:
            enhanced.insert(0, {"role": "system", "content": schema_instruction})

        raw = await self.chat(
            enhanced,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """
        解析 LLM 输出的 JSON：处理 ```json 包裹、提取首个平衡 { ... } 块。
        """
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            end = -1 if lines[-1].strip().startswith("```") else len(lines)
            text = "\n".join(lines[1:end]).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            if start == -1:
                logger.error("LLM response has no JSON object: %s", text[:200])
                raise
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            return json.loads(text[start : i + 1])
            logger.error("LLM JSON unbalanced: %s", text[:200])
            raise

    # ──────────────────────────────────────────────
    # 私有工具
    # ──────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        return payload
