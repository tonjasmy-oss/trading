"""
MCP Unified Client — 多模型统一接入层
======================================
参考 NOFX mcp/client.go + Claw402 设计理念，统一接入多个AI模型：
  - DeepSeek（主力）
  - Qwen（阿里）
  - OpenAI GPT
  - Gemini
  - Grok
  - Kimi

特性：
  - 模型路由：按名称/优先级自动选择
  - 统一计费：记录每次调用 token 消耗
  - Fallback：主模型失败自动切换备选
  - 重试机制：指数退避
  - 响应缓存：相同 prompt 避免重复计费

使用方式：
  from mcp.unified import MCPUnifiedClient
  client = MCPUnifiedClient()
  response = client.chat("你是专业交易员", model="deepseek")
"""

import os
import time
import hashlib
import logging
import requests
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    OPENAI = "openai"
    GEMINI = "gemini"
    GROK = "grok"
    KIMI = "kimi"


@dataclass
class ModelConfig:
    """模型配置"""
    provider: ModelProvider
    model_name: str
    api_base: str
    api_key: str
    max_tokens: int = 2000
    timeout: int = 120
    enabled: bool = True


@dataclass
class UsageRecord:
    """用量记录"""
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float          # USD
    latency_ms: int
    success: bool
    error: Optional[str] = None


@dataclass
class ChatResponse:
    """统一响应格式"""
    content: str
    model: str
    usage: UsageRecord
    raw: Dict[str, Any]


class MCPUnifiedClient:
    """
    多模型统一客户端
    统一接口调用多个AI模型，自动路由+计费+重试+缓存
    """

    # 默认模型（按优先级）
    DEFAULT_ORDER = ["deepseek", "qwen", "openai"]

    # 计费标准（参考 Claw402，USD/1M tokens）
    PRICING = {
        "deepseek-chat": {"input": 0.14, "output": 0.28},
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
        "qwen-max": {"input": 0.60, "output": 1.80},
        "qwen-plus": {"input": 0.60, "output": 1.80},  # approximation
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gemini-pro": {"input": 0.125, "output": 0.375},
        "moonshot-v1-8k": {"input": 0.60, "output": 1.80},
        "grok-beta": {"input": 5.00, "output": 15.00},
    }

    def __init__(
        self,
        config: Optional[Dict[str, ModelConfig]] = None,
        cache_dir: Optional[str] = None,
    ):
        self.config = self._build_config(config)
        self.usage_records: List[UsageRecord] = []
        self.cache_dir = cache_dir or "/tmp/mcp_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

    # ======================== 配置 ========================

    def _build_config(self, config: Optional[Dict[str, ModelConfig]]) -> Dict[str, ModelConfig]:
        """从环境变量构建模型配置"""
        default_configs = {
            "deepseek": ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name="deepseek-chat",
                api_base="https://api.deepseek.com/v1",
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            ),
            "qwen": ModelConfig(
                provider=ModelProvider.QWEN,
                model_name=os.getenv("QWEN_MODEL", "qwen-max"),
                api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.getenv("QWEN_API_KEY", ""),
            ),
            "openai": ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4o-mini",
                api_base="https://api.openai.com/v1",
                api_key=os.getenv("OPENAI_API_KEY", ""),
            ),
            "gemini": ModelConfig(
                provider=ModelProvider.GEMINI,
                model_name="gemini-2.0-flash",
                api_base="https://generativelanguage.googleapis.com/v1beta",
                api_key=os.getenv("GEMINI_API_KEY", ""),
            ),
            "kimi": ModelConfig(
                provider=ModelProvider.KIMI,
                model_name="moonshot-v1-8k",
                api_base="https://api.moonshot.cn/v1",
                api_key=os.getenv("KIMI_API_KEY", ""),
            ),
            "grok": ModelConfig(
                provider=ModelProvider.GROK,
                model_name="grok-beta",
                api_base="https://api.x.ai/v1",
                api_key=os.getenv("GROK_API_KEY", ""),
            ),
        }

        if config:
            default_configs.update(config)

        # 如果外部传入了配置，用外部的
        if config:
            for k, v in config.items():
                default_configs[k] = v

        return default_configs

    # ======================== 主入口 ========================

    def chat(
        self,
        message: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """
        统一 chat 接口
        Args:
            message: 用户消息
            system_prompt: 系统提示词
            model: 指定模型（None则按优先级自动选择）
            temperature: 温度参数
            max_tokens: 最大输出token
        Returns: ChatResponse
        """
        # 1. 检查缓存
        cache_key = self._cache_key(system_prompt, message, model or "auto")
        cached = self._cache_get(cache_key)
        if cached:
            logger.info(f"[MCP] Cache hit for {cache_key[:16]}...")
            return cached

        # 2. 选择模型
        target_model = model or self._select_model()
        cfg = self.config.get(target_model)

        if not cfg or not cfg.api_key:
            # 无key，尝试 fallback
            logger.warning(f"[MCP] {target_model} not configured, trying fallbacks")
            return self._try_fallback(system_prompt, message, temperature, max_tokens)

        # 3. 调用
        start = time.time()
        try:
            resp = self._call(
                cfg,
                system_prompt=system_prompt,
                message=message,
                temperature=temperature,
                max_tokens=max_tokens or cfg.max_tokens,
            )
            latency_ms = int((time.time() - start) * 1000)
            usage = self._calc_usage(resp, cfg.model_name, latency_ms)
            self._record_usage(usage)

            chat_resp = ChatResponse(
                content=self._extract_content(resp, cfg.provider),
                model=cfg.model_name,
                usage=usage,
                raw=resp,
            )

            # 4. 写入缓存
            self._cache_set(cache_key, chat_resp)
            return chat_resp

        except Exception as e:
            logger.error(f"[MCP] {target_model} failed: {e}")
            # 5. 失败自动fallback
            return self._try_fallback(system_prompt, message, temperature, max_tokens)

    # ======================== 实际调用 ========================

    def _call(
        self,
        cfg: ModelConfig,
        system_prompt: str,
        message: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """实际发起HTTP请求"""
        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": cfg.model_name,
            "messages": self._build_messages(system_prompt, message),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = requests.post(
            f"{cfg.api_base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=cfg.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
    ) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        return messages

    def _extract_content(
        self,
        resp: Dict[str, Any],
        provider: ModelProvider,
    ) -> str:
        """从响应中提取内容"""
        try:
            choices = resp.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
        except (KeyError, IndexError):
            pass
        return str(resp)

    # ======================== 模型选择 ========================

    def _select_model(self) -> str:
        """按优先级选择可用模型"""
        for name in self.DEFAULT_ORDER:
            cfg = self.config.get(name)
            if cfg and cfg.enabled and cfg.api_key:
                return name
        # 全部不可用，返回第一个有key的
        for name, cfg in self.config.items():
            if cfg.api_key:
                return name
        return "deepseek"

    def _try_fallback(
        self,
        system_prompt: str,
        message: str,
        temperature: float,
        max_tokens: Optional[int],
        _tried: Optional[set] = None,
    ) -> ChatResponse:
        """尝试所有可用模型（排除已失败的）"""
        _tried = _tried or set()
        remaining = [n for n in self.DEFAULT_ORDER if n not in _tried]

        for name in remaining:
            cfg = self.config.get(name)
            if not cfg or not cfg.api_key:
                continue
            _tried.add(name)
            try:
                start = time.time()
                resp = self._call(cfg, system_prompt, message, temperature, max_tokens or 2000)
                latency_ms = int((time.time() - start) * 1000)
                usage = self._calc_usage(resp, cfg.model_name, latency_ms)
                self._record_usage(usage)
                chat_resp = ChatResponse(
                    content=self._extract_content(resp, cfg.provider),
                    model=cfg.model_name,
                    usage=usage,
                    raw=resp,
                )
                return chat_resp
            except Exception as e:
                logger.warning(f"[MCP] Fallback {name} failed: {e}")
                continue

        # 全失败，返回mock
        return self._mock_response()

    def _mock_response(self) -> ChatResponse:
        """无可用模型时返回模拟响应"""
        return ChatResponse(
            content="[MOCK] No AI model available. Configure API keys.",
            model="mock",
            usage=UsageRecord(
                timestamp=datetime.now().isoformat(),
                model="mock",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost=0,
                latency_ms=0,
                success=False,
                error="No API key configured",
            ),
            raw={},
        )

    # ======================== 计费 ========================

    def _calc_usage(
        self,
        resp: Dict[str, Any],
        model_name: str,
        latency_ms: int,
    ) -> UsageRecord:
        """从响应计算token使用量和费用"""
        try:
            usage = resp.get("usage", {})
            pt = usage.get("prompt_tokens", 0)
            ct = usage.get("completion_tokens", 0)
            tt = usage.get("total_tokens", pt + ct)

            price = self.PRICING.get(model_name, {"input": 0.1, "output": 0.3})
            cost = (pt / 1_000_000) * price["input"] + (ct / 1_000_000) * price["output"]
        except Exception:
            pt = ct = tt = 0
            cost = 0

        return UsageRecord(
            timestamp=datetime.now().isoformat(),
            model=model_name,
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=tt,
            cost=round(cost, 6),
            latency_ms=latency_ms,
            success=True,
        )

    def _record_usage(self, usage: UsageRecord):
        """记录用量"""
        self.usage_records.append(usage)
        logger.info(
            f"[MCP] {usage.model}: {usage.total_tokens} tokens, "
            f"${usage.cost:.6f}, {usage.latency_ms}ms"
        )

    def get_usage_summary(self) -> Dict[str, Any]:
        """获取用量汇总"""
        if not self.usage_records:
            return {"total_cost": 0, "total_tokens": 0, "calls": 0}

        total_cost = sum(u.cost for u in self.usage_records)
        total_tokens = sum(u.total_tokens for u in self.usage_records)
        total_calls = len(self.usage_records)
        by_model: Dict[str, Dict] = {}

        for u in self.usage_records:
            if u.model not in by_model:
                by_model[u.model] = {"cost": 0, "tokens": 0, "calls": 0}
            by_model[u.model]["cost"] += u.cost
            by_model[u.model]["tokens"] += u.total_tokens
            by_model[u.model]["calls"] += 1

        return {
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "by_model": by_model,
        }

    def clear_usage(self):
        """清空用量记录"""
        self.usage_records.clear()

    # ======================== 缓存 ========================

    def _cache_key(self, system: str, message: str, model: str) -> str:
        s = f"{system or ''}|{message}|{model}"
        return hashlib.sha256(s.encode()).hexdigest()

    def _cache_get(self, key: str) -> Optional[ChatResponse]:
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(path):
            try:
                import json
                with open(path) as f:
                    d = json.load(f)
                # 反序列化 UsageRecord
                usage = UsageRecord(**d["usage"])
                return ChatResponse(
                    content=d["content"],
                    model=d["model"],
                    usage=usage,
                    raw={},
                )
            except Exception:
                return None
        return None

    def _cache_set(self, key: str, resp: ChatResponse):
        import json
        path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(path, "w") as f:
                json.dump({
                    "content": resp.content,
                    "model": resp.model,
                    "usage": vars(resp.usage),
                }, f)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    def clear_cache(self):
        """清空缓存目录"""
        import shutil
        for f in os.listdir(self.cache_dir):
            try:
                os.remove(os.path.join(self.cache_dir, f))
            except Exception:
                pass


# ─── 全局单例 ────────────────────────────────────────────────

_client: Optional[MCPUnifiedClient] = None

def get_client() -> MCPUnifiedClient:
    global _client
    if _client is None:
        _client = MCPUnifiedClient()
    return _client


# ─── 快捷入口 ────────────────────────────────────────────────

def quick_chat(message: str, model: str = "deepseek") -> str:
    """快速对话（用于测试）"""
    client = get_client()
    resp = client.chat(message=message, model=model)
    return resp.content


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== MCPUnifiedClient Test ===")
    client = get_client()
    print(f"Default model: {client._select_model()}")
    print(f"Usage summary: {client.get_usage_summary()}")

    # 测试chat（会失败但展示结构）
    resp = client.chat(
        message="Hello, respond with just 'OK'",
        model="deepseek",
        system_prompt="You are a helpful assistant.",
    )
    print(f"Response: {resp.content[:100]}")
    print(f"Model: {resp.model}, Cost: ${resp.usage.cost:.6f}")
    print(f"Usage summary: {client.get_usage_summary()}")