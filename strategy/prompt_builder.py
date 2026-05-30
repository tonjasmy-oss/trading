"""
Prompt Builder — 结构化 Prompt 构建器
======================================
参考 NOFX BuildSystemPrompt + BuildUserPrompt，输出完整AI决策Prompt：
  - System Prompt（8段式）：角色/交易模式/硬约束/频率/入场标准/决策过程/输出格式
  - User Prompt：系统状态+BTC概览+账户+持仓+候选币全量数据
  - 支持 XML+JSON 双层结构（reasoning + decision）

使用方式：
  from strategy.prompt_builder import PromptBuilder, TradingMode
  builder = PromptBuilder()
  sys_prompt, user_prompt = builder.build(account_equity=1000.0, mode=TradingMode.CONSERVATIVE)
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .data_assembler import TradingContext, AccountData, PositionData, MarketData


class TradingMode(Enum):
    AGGRESSIVE = "aggressive"      # 趋势突破，高仓位容忍
    CONSERVATIVE = "conservative"  # 多信号确认，保守资金管理
    SCALPING = "scalping"          # 短线动量，tight take-profit


@dataclass
class RiskControlConfig:
    """风控参数配置（硬约束代码层 + AI引导层）"""
    # 代码强制（硬约束）
    max_positions: int = 3
    altcoin_max_position_ratio: float = 1.0    # 单山寨币最大占总仓位比例
    btc_eth_max_position_ratio: float = 5.0   # BTC/ETH最大占比
    max_margin_usage: float = 0.90              # 最大保证金使用率
    min_position_size_usdt: float = 12.0        # 最小仓位（USDT）

    # AI引导（建议值）
    altcoin_max_leverage: float = 5.0
    btc_eth_max_leverage: float = 5.0
    min_risk_reward_ratio: float = 3.0          # 最小盈亏比
    min_confidence: float = 75.0                # 最低置信度


# ─── System Prompt 模板 ────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATES = {
    TradingMode.AGGRESSIVE: """
You are an aggressive cryptocurrency trading AI specialized in trend breakout strategies.
You seek high-probability momentum entries with rapid capital deployment.
""",
    TradingMode.CONSERVATIVE: """
You are a conservative cryptocurrency trading AI specializing in multi-signal confirmation.
You prioritize capital preservation and require strong confluence before entering.
""",
    TradingMode.SCALPING: """
You are a scalping trading AI specializing in short-term momentum捕捉 rapid price movements.
You execute quick entries with tight stop-losses and take-profits.
""",
}


class PromptBuilder:
    """
    Prompt 构建器
    负责组装完整的 System Prompt + User Prompt，供 AI 模型推理
    """

    def __init__(self, risk_config: Optional[RiskControlConfig] = None):
        self.risk_config = risk_config or RiskControlConfig()

    # ======================== 主入口 ========================

    def build(
        self,
        ctx: TradingContext,
        mode: TradingMode = TradingMode.CONSERVATIVE,
        custom_prompt: str = "",
        cycle: int = 1,
        runtime_seconds: int = 0,
    ) -> tuple[str, str]:
        """
        构建完整Prompt对
        Returns: (system_prompt, user_prompt)
        """
        system_prompt = self.build_system_prompt(ctx.account, mode, custom_prompt)
        user_prompt = self.build_user_prompt(ctx, mode, cycle, runtime_seconds)
        return system_prompt, user_prompt

    # ======================== System Prompt ========================

    def build_system_prompt(
        self,
        account: AccountData,
        mode: TradingMode,
        custom_prompt: str = "",
    ) -> str:
        """构建8段式System Prompt"""
        account_str = f"${account.equity:.2f}"

        # Section 1: 角色定义
        role_section = SYSTEM_PROMPT_TEMPLATES[mode]

        # Section 2: 硬约束（代码强制执行）
        rc = self.risk_config
        hard_constraints = f"""
## HARD CONSTRAINTS (Code-Enforced)
- NEVER exceed {rc.max_positions} open positions simultaneously
- NEVER open a position larger than {rc.altcoin_max_position_ratio*100:.0f}% of account equity in a single altcoin
- BTC/ETH max position: {rc.btc_eth_max_position_ratio*100:.0f}% of equity each
- Maximum margin usage: {rc.max_margin_usage*100:.0f}% of available margin
- Minimum position size: ${rc.min_position_size_usdt:.0f} USDT (reject smaller)
- Maximum {rc.max_positions} positions per cycle

## AI GUIDANCE (Suggested Values)
- Altcoin max leverage: {rc.altcoin_max_leverage}x
- BTC/ETH max leverage: {rc.btc_eth_max_leverage}x
- Minimum risk/reward ratio: {rc.min_risk_reward_ratio}:1
- Minimum confidence to open: {rc.min_confidence:.0f}/100
"""

        # Section 3: 交易模式
        mode_section = f"""
## Trading Mode: {mode.value.upper()}
{"Trend following, allow higher leverage for breakout moves" if mode == TradingMode.AGGRESSIVE else "Multi-signal confirmation, conservative position sizing" if mode == TradingMode.CONSERVATIVE else "Quick momentum entries, tight stops and targets"}
"""

        # Section 4: 决策过程（可编辑，此为默认）
        decision_process = """
## Decision Process
1. Analyze BTC trend direction and overall market sentiment
2. Check open positions for stop-loss triggers and holding period
3. Evaluate candidate coins: trend strength, RSI, MACD divergence, volume
4. Filter by risk/reward ratio (must exceed {rr}x) and confidence (min {conf})
5. Select top candidates, respect max position limit
6. Calculate position size: risk ≤ 2% of equity per trade
7. Set stop-loss (≤ -5% from entry) and take-profit (≥ {rr}x risk)
""".format(rr=rc.min_risk_reward_ratio, conf=rc.min_confidence)

        # Section 5: 输出格式（固定XML+JSON）
        output_format = """
## Output Format (MUST follow exactly)
```xml
<reasoning>
[Chain of Thought: analyze each candidate coin, compare signals, justify decisions]
</reasoning>

<decision>
```json
[
  {{
    "symbol": "BTCUSDT",
    "action": "open_long",    // open_long | close_long | close_short | hold | wait
    "leverage": 5,
    "position_size_usdt": 100.00,
    "stop_loss": 65000.00,
    "take_profit": 72000.00,
    "confidence": 85,
    "risk_usdt": 20.00,
    "reasoning": "..."
  }}
]
```
</decision>
"""
        # Section 6: 自定义
        custom_section = f"\n## Custom Instructions\n{custom_prompt}\n" if custom_prompt else ""

        parts = [
            role_section,
            f"\n## Account: Equity {account_str}",
            hard_constraints,
            mode_section,
            decision_process,
            output_format,
            custom_section,
        ]
        return "\n".join(parts)

    # ======================== User Prompt ========================

    def build_user_prompt(
        self,
        ctx: TradingContext,
        mode: TradingMode,
        cycle: int = 1,
        runtime_seconds: int = 0,
    ) -> str:
        """构建结构化User Prompt"""
        lines = []

        # 1. 系统状态
        runtime_h = runtime_seconds // 3600
        runtime_m = (runtime_seconds % 3600) // 60
        lines.append(f"## System Status")
        lines.append(f"- Time: [CURRENT TIME]")
        lines.append(f"- Cycle: #{cycle} (every 5 minutes)")
        lines.append(f"- Runtime: {runtime_h}h {runtime_m}m")
        lines.append("")

        # 2. BTC 全局概览
        btc = ctx.btc_overview
        lines.append(f"## BTC Market Overview")
        if btc:
            lines.append(
                f"- Price: ${btc.get('price', 0):,.2f} | "
                f"24h Change: {btc.get('change_pct', 0):+.2f}% | "
                f"High: ${btc.get('high_24h', 0):,.2f} | "
                f"Low: ${btc.get('low_24h', 0):,.2f}"
            )
        else:
            lines.append("- BTC data unavailable")
        lines.append("")

        # 3. 账户信息
        acc = ctx.account
        lines.append(f"## Account Information")
        lines.append(
            f"Equity: ${acc.equity:.2f} | "
            f"Available: ${acc.available:.2f} | "
            f"Unrealized PnL: ${acc.unrealized_pnl:+.2f}"
        )
        if ctx.positions:
            total_exposure = sum(p.quantity * p.mark_price for p in ctx.positions)
            exposure_pct = total_exposure / acc.equity * 100 if acc.equity > 0 else 0
            lines.append(f"Total Exposure: ${total_exposure:.2f} ({exposure_pct:.1f}% of equity)")
        else:
            lines.append("No open positions")
        lines.append("")

        # 4. 当前持仓（含指标）
        if ctx.positions:
            lines.append("## Current Positions")
            for pos in ctx.positions:
                pnl_pct = (pos.mark_price - pos.entry_price) / pos.entry_price * 100 if pos.entry_price else 0
                side_emoji = "🟢" if pos.side == "long" else "🔴"
                lines.append(
                    f"{side_emoji} {pos.symbol}: "
                    f"Entry=${pos.entry_price:.4f} | "
                    f"Mark=${pos.mark_price:.4f} | "
                    f"PnL={pnl_pct:+.2f}% | "
                    f"Leverage={pos.leverage}x | "
                    f"Liq=${pos.liquidation_price:.4f}"
                )
            lines.append("")
        else:
            lines.append("## Current Positions\nNone\n")

        # 5. 最近平仓交易
        if ctx.recent_trades:
            lines.append(f"## Recent Closed Trades (last {len(ctx.recent_trades)})")
            for t in ctx.recent_trades[:5]:
                lines.append(
                    f"- {t['symbol']} {t['side']} {t['quantity']:.4f} @ ${t['price']:.4f} | "
                    f"PnL: {t.get('pnl_pct', 0):+.2f}%"
                )
            lines.append("")

        # 6. 候选币（全量市场数据）
        lines.append("## Candidate Coins Analysis")
        for sym, tfs in ctx.market_data.items():
            lines.append(self._format_candidate_coin(sym, tfs))
            lines.append("")

        # 7. 决策请求
        lines.append("## Decision Request")
        lines.append(
            "Analyze the above data and output your trading decisions "
            "in the required XML+JSON format. "
            "Prioritize: close positions with stop-loss triggers > open new positions > hold/wait."
        )

        return "\n".join(lines)

    def _format_candidate_coin(self, symbol: str, tfs: Dict[str, MarketData]) -> str:
        """格式化单个候选币市场数据"""
        primary = tfs.get("5m") or tfs.get("15m")
        if not primary:
            return f"### {symbol} (no data available)"

        ind = primary.indicators
        closes = [d["close"] for d in primary.ohlcv]
        current_price = closes[-1] if closes else 0
        ema20 = ind.get("EMA20", [])
        ema_val = ema20[-1] if ema20 else current_price
        macd_vals = ind.get("MACD", [])
        macd_val = macd_vals[-1] if macd_vals else 0
        rsi7 = ind.get("RSI7", [50])
        rsi_val = rsi7[-1] if rsi7 else 50

        lines = [f"### {symbol}"]

        # 价格和指标摘要
        lines.append(
            f"- Price: ${current_price:.4f} | EMA20: ${ema_val:.4f} | "
            f"MACD: {macd_val:+.4f} | RSI7: {rsi_val:.1f}"
        )

        # OI / Funding Rate
        if primary.oi:
            lines.append(f"- Open Interest: ${primary.oi:,.0f}")
        if primary.funding_rate is not None:
            lines.append(f"- Funding Rate: {primary.funding_rate:+.4f}%")

        # 多时间框架K线数据（仅主要时间框架）
        for tf_name, tf_data in tfs.items():
            if not tf_data.ohlcv:
                continue
            closes_tf = [d["close"] for d in tf_data.ohlcv]
            ema_tf = tf_data.indicators.get(f"EMA20", [])
            macd_tf = tf_data.indicators.get("MACD", [])
            rsi_tf = tf_data.indicators.get("RSI7", [])

            price_str = ", ".join(f"{c:.2f}" for c in closes_tf[-5:]) if len(closes_tf) >= 5 else ", ".join(f"{c:.2f}" for c in closes_tf)
            ema_str = ", ".join(f"{e:.2f}" for e in ema_tf[-5:]) if len(ema_tf) >= 5 else ""
            macd_str = ", ".join(f"{m:+.2f}" for m in macd_tf[-5:]) if len(macd_tf) >= 5 else ""
            rsi_str = ", ".join(f"{r:.1f}" for r in rsi_tf[-5:]) if len(rsi_tf) >= 5 else ""

            lines.append(f"=== {tf_name.upper()} ===")
            lines.append(f"  Prices: [{price_str}]")
            if ema_str:
                lines.append(f"  EMA20: [{ema_str}]")
            if macd_str:
                lines.append(f"  MACD: [{macd_str}]")
            if rsi_str:
                lines.append(f"  RSI7: [{rsi_str}]")

        return "\n".join(lines)