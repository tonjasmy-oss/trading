"""
mcp/ — 多模型统一接入层
支持：DeepSeek / Qwen / OpenAI / Gemini / Grok / Kimi
"""

from .unified import MCPUnifiedClient, get_client, quick_chat, ModelProvider, ModelConfig, UsageRecord, ChatResponse

__all__ = [
    "MCPUnifiedClient",
    "get_client",
    "quick_chat",
    "ModelProvider",
    "ModelConfig",
    "UsageRecord",
    "ChatResponse",
]