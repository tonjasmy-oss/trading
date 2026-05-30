"""
Strategy Engine — 策略执行引擎
================================
参考 NOFX StrategyEngine，串联整个策略循环：
  1. DataAssembler.build_context()  — 组装完整市场数据
  2. PromptBuilder.build()          — 构建 System+User Prompt
  3. MCP/AI 模型调用               — 获取 AI 决策
  4. ResponseParser.parse()        — 解析 AI 响应
  5. GlobalRiskManager              — 代码层风控校验
  6. 执行交易决策

使用方式：
  engine = AITradingEngine()
  result = engine.run_cycle(symbols=["BTC", "ETH"])
"""

import os
import time
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .data_assembler import DataAssembler, TradingContext
from .prompt_builder import PromptBuilder, TradingMode, RiskControlConfig
from .response_parser import ResponseParser, Decision, Action

logger = logging.getLogger(__name__)


class AITradingEngine:
    """
    AI 驱动交易引擎
    完整执行周期：数据 → Prompt → AI → 解析 → 风控 → 执行
    """

    def __init__(
        self,
        mode: TradingMode = TradingMode.CONSERVATIVE,
        mcp_model: str = "deepseek-chat",
        enable_live: bool = False,
    ):
        self.mode = mode
        self.mcp_model = mcp_model
        self.enable_live = enable_live

        self.assembler = DataAssembler()
        self.prompt_builder = PromptBuilder()
        self.parser = ResponseParser()

        # 风控（复用现有GlobalRiskManager）
        self._init_risk_manager()

        # 周期计数
        self._cycle = 0
        self._start_time = int(time.time())

    def _init_risk_manager(self):
        """初始化风控管理器"""
        try:
            from risk_manager import GlobalRiskManager
            initial = float(os.getenv("INITIAL_CAPITAL", "10000"))
            self.risk_mgr = GlobalRiskManager(initial_capital=initial)
        except Exception as e:
            logger.warning(f"GlobalRiskManager init failed: {e}, using mock")
            self.risk_mgr = None

    def run_cycle(
        self,
        symbols: Optional[List[str]] = None,
        fetch_quant: bool = False,
    ) -> Dict[str, Any]:
        """
        执行一次完整策略周期
        Returns: {
            cycle: int,
            reasoning: str,
            decisions: [...],
            execution_results: [...],
            risk_status: {...}
        }
        """
        symbols = symbols or ["BTC", "ETH"]
        self._cycle += 1
        cycle = self._cycle
        runtime = int(time.time()) - self._start_time

        logger.info(f"[Engine] ===== Cycle #{cycle} start ===== symbols={symbols}")

        # Step 1: 构建交易上下文
        ctx = self.assembler.build_context(symbols=symbols, fetch_quant=fetch_quant)

        # Step 2: 构建 Prompt
        system_prompt, user_prompt = self.prompt_builder.build(
            ctx=ctx,
            mode=self.mode,
            cycle=cycle,
            runtime_seconds=runtime,
        )

        # Step 3: 调用 AI 模型
        ai_response = self._call_ai(system_prompt, user_prompt)

        # Step 4: 解析 AI 响应
        parse_result = self.parser.parse(
            raw_response=ai_response,
            account_equity=ctx.account.equity,
            current_positions=[p.symbol for p in ctx.positions],
        )

        # Step 5: 风控校验
        validated = self._risk_check(parse_result.decisions, ctx)

        # Step 6: 执行
        execution_results = self._execute_decisions(validated, ctx)

        # Step 7: 更新风控状态
        risk_status = self._get_risk_status()

        logger.info(
            f"[Engine] Cycle #{cycle} done: "
            f"total={parse_result.total_count} valid={parse_result.valid_count} "
            f"executed={len([r for r in execution_results if r.get('success')])}"
        )

        return {
            "cycle": cycle,
            "reasoning": parse_result.reasoning,
            "decisions": [
                {
                    "symbol": d.symbol,
                    "action": d.action.value,
                    "leverage": d.leverage,
                    "size": d.position_size_usdt,
                    "stop_loss": d.stop_loss,
                    "take_profit": d.take_profit,
                    "confidence": d.confidence,
                    "is_valid": d.is_valid,
                    "errors": d.validation_errors,
                }
                for d in parse_result.decisions
            ],
            "execution_results": execution_results,
            "risk_status": risk_status,
            "context_summary": {
                "account_equity": ctx.account.equity,
                "open_positions": len(ctx.positions),
                "symbols_analyzed": symbols,
            },
        }

    # ======================== AI 调用 ========================

    def _call_ai(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用 AI 模型（通过 MCPUnifiedClient 统一层）
        支持：DeepSeek / Qwen / OpenAI / Gemini / Grok / Kimi
        自动路由 + 计费 + Fallback
        """
        model = self.mcp_model or os.getenv("AI_MODEL", "deepseek")

        try:
            from mcp.unified import get_client
            client = get_client()
            resp = client.chat(
                message=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=0.3,
            )
            if resp.usage.success:
                logger.info(
                    f"[Engine] AI call {resp.model}: "
                    f"{resp.usage.total_tokens} tokens, "
                    f"${resp.usage.cost:.6f}, {resp.usage.latency_ms}ms"
                )
            return resp.content
        except Exception as e:
            logger.error(f"[Engine] MCP call failed: {e}")
            return self._mock_ai_response()

    def _call_via_gateway(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
    ) -> str:
        """通过 Agent Gateway 调用"""
        import requests
        url = os.getenv("AGENT_GATEWAY_URL", "http://localhost:8080/api/agent/v1/chat")
        resp = requests.post(
            url,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=130,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content") or data.get("text") or data.get("response", "")

    def _call_direct(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
    ) -> str:
        """直接调用 OpenAI 兼容 API"""
        import requests

        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            logger.warning("No API key found, using mock response")
            return self._mock_ai_response()

        # Determine base URL
        if "deepseek" in model:
            base_url = "https://api.deepseek.com/v1"
        elif "qwen" in model:
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif "gpt" in model:
            base_url = "https://api.openai.com/v1"
        else:
            base_url = "https://api.deepseek.com/v1"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
        }

        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=130,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0]["message"]["content"]
        return ""

    def _mock_ai_response(self) -> str:
        """无API时的模拟响应（用于测试）"""
        return """
<reasoning>
BTC shows slight bullish divergence on 4H RSI, but overall market is mixed.
Current positions: none
Best candidate: BTC with moderate confidence
</reasoning>

<decision>
```json
[
  {
    "symbol": "BTC",
    "action": "open_long",
    "leverage": 3,
    "position_size_usdt": 100.00,
    "stop_loss": 58000.00,
    "take_profit": 65000.00,
    "confidence": 78,
    "risk_usdt": 20.00,
    "reasoning": "RSI bullish divergence on 4H, holding above EMA20 support"
  }
]
```
</decision>
"""

    # ======================== 风控校验 ========================

    def _risk_check(
        self,
        decisions: List[Decision],
        ctx: TradingContext,
    ) -> List[Decision]:
        """代码层风控校验，拦截违规决策"""
        validated = []
        for d in decisions:
            if not d.is_valid:
                logger.info(f"[Risk] Skip invalid decision: {d.symbol} {d.action.value}")
                continue

            if d.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                # 调用 GlobalRiskManager
                if self.risk_mgr:
                    can_open, reason = self.risk_mgr.can_open_position(
                        d.symbol,
                        estimated_price=d.stop_loss or 50000,
                    )
                    if not can_open:
                        logger.warning(f"[Risk] Blocked by GlobalRiskManager: {d.symbol} — {reason}")
                        d.is_valid = False
                        d.validation_errors.append(f"RiskManager: {reason}")
                        continue

                # 总暴露度检查
                total_exposure = d.position_size_usdt
                for pos in ctx.positions:
                    total_exposure += pos.quantity * pos.mark_price
                exposure_ratio = total_exposure / ctx.account.equity if ctx.account.equity else 1
                if exposure_ratio > 0.5:
                    logger.warning(f"[Risk] Exposure {exposure_ratio:.1%} > 50%, blocking {d.symbol}")
                    d.is_valid = False
                    d.validation_errors.append(f"Exposure {exposure_ratio:.1%} too high")
                    continue

            validated.append(d)

        return validated

    # ======================== 交易执行 ========================

    def _execute_decisions(
        self,
        decisions: List[Decision],
        ctx: TradingContext,
    ) -> List[Dict[str, Any]]:
        """执行决策（实盘或模拟）"""
        results = []

        # 按优先级排序：close → open → hold
        sorted_decisions = self.parser.sort_by_priority(decisions)

        for d in sorted_decisions:
            if not d.is_valid:
                continue

            if d.action in (Action.CLOSE_LONG, Action.CLOSE_SHORT):
                result = self._close_position(d)
            elif d.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                result = self._open_position(d)
            else:
                result = {"symbol": d.symbol, "action": d.action.value, "status": "ignored"}
            results.append(result)

        return results

    def _open_position(self, d: Decision) -> Dict[str, Any]:
        """开仓"""
        if not self.enable_live:
            logger.info(f"[Sim] OPEN {d.action.value} {d.symbol} ${d.position_size_usdt} @ leverage {d.leverage}x")
            return {"symbol": d.symbol, "action": d.action.value, "size": d.position_size_usdt, "status": "simulated"}

        try:
            # 实盘：调用统一交易API
            from stock_trading import StockTrader
            trader = StockTrader.get_trader("us")
            if not trader or not trader.is_connected():
                return {"symbol": d.symbol, "status": "error", "message": "Trader not connected"}

            # 估算数量
            qty = d.position_size_usdt / (d.stop_loss or 50000)
            if d.action == Action.OPEN_LONG:
                result = trader.buy(d.symbol, int(qty))
            else:
                result = trader.sell(d.symbol, int(qty))
            return {**result, "symbol": d.symbol}
        except Exception as e:
            logger.error(f"Open position failed: {e}")
            return {"symbol": d.symbol, "status": "error", "message": str(e)}

    def _close_position(self, d: Decision) -> Dict[str, Any]:
        """平仓"""
        if not self.enable_live:
            logger.info(f"[Sim] CLOSE {d.symbol}")
            return {"symbol": d.symbol, "action": "close", "status": "simulated"}

        try:
            from stock_trading import StockTrader
            trader = StockTrader.get_trader("us")
            if not trader or not trader.is_connected():
                return {"symbol": d.symbol, "status": "error", "message": "Trader not connected"}

            pos = trader.get_position(d.symbol)
            if not pos:
                return {"symbol": d.symbol, "status": "no_position"}

            return trader.sell(d.symbol, int(pos["quantity"]))
        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return {"symbol": d.symbol, "status": "error", "message": str(e)}

    def _get_risk_status(self) -> Dict[str, Any]:
        """获取当前风控状态"""
        if self.risk_mgr:
            status = self.risk_mgr.get_status()
            return {
                "level": status.level.value,
                "daily_loss_pct": status.daily_loss_pct,
                "total_exposure_pct": status.total_exposure_pct,
                "open_positions": status.open_positions,
                "daily_trade_count": status.daily_trade_count,
                "can_open": status.can_open,
            }
        return {}


# ─── 快捷入口 ────────────────────────────────────────────────

def quick_test():
    """快速测试完整流程"""
    engine = AITradingEngine()
    result = engine.run_cycle(symbols=["BTC", "ETH"])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    quick_test()