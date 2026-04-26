from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any


class LLMClient:
    """
    统一 LLM 调用客户端，兼容 OpenAI 标准接口（/v1/chat/completions）。
    所有主流服务商（Qwen、GLM、DeepSeek 等）均通过 base_url 适配，
    无需修改调用代码即可切换模型。
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        # TODO: 初始化 httpx.AsyncClient 或 openai.AsyncOpenAI
        self._client = None

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        """
        同步调用（非流式），返回完整助手回复字符串。
        response_format={"type": "json_object"} 时启用 JSON 模式。
        """
        # TODO: POST /v1/chat/completions，解析 choices[0].message.content
        pass

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式调用，逐 token yield 字符串片段。
        调用方通过 async for token in client.chat_stream(...) 消费。
        """
        # TODO: POST /v1/chat/completions?stream=true，逐行解析 SSE data 字段
        yield ""  # 占位，使函数成为合法 async generator

    async def chat_with_schema(
        self,
        messages: list[dict[str, str]],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        """
        带 JSON Schema 约束的调用，确保输出严格符合预定义结构。
        内部使用 response_format={"type":"json_object"} 并在 system prompt 中注入 schema。
        返回解析后的 Python dict。
        """
        # TODO: 构造带 schema 描述的 system prompt，调用 chat，json.loads 解析结果
        pass

    @classmethod
    def from_user_config(cls, api_key: str, base_url: str, model: str) -> "LLMClient":
        """从用户 LLM 配置构造客户端（ModelService.get_default_llm_api_key 的结果）。"""
        return cls(api_key=api_key, base_url=base_url, model=model)
