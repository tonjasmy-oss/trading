"""
Telegram Trading Bot
====================
通过 Telegram 控制交易助手：
  /start — 欢迎 + 帮助
  /status — 系统状态（监控/风控/持仓/权益）
  /positions — 当前持仓详情
  /alerts — 最近告警
  /price BTC — 查询价格
  /mode live|sim — 切换实盘/模拟模式
  /trade buy BTC 0.01 65000 — 模拟下单

使用方式：
  python3 telegram_bot.py
  或在 Dashboard 中已有 /api/telegram/... 路由
"""

import os
import logging
import asyncio
from typing import Optional

import telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logger = logging.getLogger(__name__)

# 环境变量配置
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = [int(uid) for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if uid.strip()]
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK_URL", "")

# 异步工具函数
def _sync_to_async(fn):
    """将同步函数包装为异步"""
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/start"""
    user = update.effective_user
    if ALLOWED_USER_IDS and user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ Access denied")
        return

    await update.message.reply_text(
        "📊 三省六部 Trading Bot\n\n"
        "Commands:\n"
        "/status   — 系统总览\n"
        "/positions — 当前持仓\n"
        "/alerts   — 最近告警\n"
        "/price BTC — 查询价格\n"
        "/mode live|sim — 切换模式\n"
        "/help     — 帮助"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/help"""
    await cmd_start(update, ctx)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """系统状态"""
    try:
        from database import get_positions, get_alerts
        from config import LIVE_TRADING_ENABLED
        import time

        positions = get_positions()
        alerts = get_alerts(5)
        total_cost = sum(p["quantity"] * p["avg_price"] for p in positions)

        msg = [
            f"📊 三省六部 系统状态",
            f"━━━━━━━━━━━━━━━━━━",
            f"🟢 监控: 运行中",
            f"💰 模式: {'实盘' if LIVE_TRADING_ENABLED else '模拟'}",
            f"📦 持仓: {len(positions)} 个品种",
            f"💵 总市值: ¥{total_cost:,.2f}",
            f"🔔 待处理告警: {len(alerts)}",
        ]

        if alerts:
            msg.append("最近告警:")
            for a in alerts[:3]:
                msg.append(f"  ⚠️ {a['symbol']} {a['alert_type']}")

        await update.message.reply_text("\n".join(msg))
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_positions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """持仓详情"""
    try:
        from portfolio import Portfolio
        pf = Portfolio()
        positions = pf.get_positions()
        value = pf.get_position_value()

        if not positions:
            await update.message.reply_text("📦 当前无持仓")
            return

        lines = ["📦 持仓详情", "━━━━━━━━━━━━━━━━━━"]
        for p in value.get("positions", []):
            lines.append(
                f"{p['symbol']} {p['market']}\n"
                f"  数量: {p['quantity']:.6f}\n"
                f"  均价: ¥{p['avg_price']:.4f}\n"
                f"  现价: ¥{p['current_price']:.4f}\n"
                f"  盈亏: {p['pnl_pct']:+.2f}%"
            )
            lines.append("")

        lines.append(f"总盈亏: {value['total_pnl']:+,.2f} ({value['total_pnl_pct']:+.2f}%)")

        await update.message.reply_text("\n".join(lines)[:4096])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """最近告警"""
    try:
        from database import get_alerts
        alerts = get_alerts(10)
        if not alerts:
            await update.message.reply_text("✅ 暂无告警")
            return

        lines = ["🔔 最近告警", "━━━━━━━━━━━━━━━━━━"]
        for a in alerts[:5]:
            lines.append(
                f"{a['symbol']} {a['alert_type']}\n"
                f"  价格: ¥{a['price']} | 阈值: {a['threshold']}%\n"
                f"  {a['message'] or a['alert_type']}"
            )
            lines.append("")

        await update.message.reply_text("\n".join(lines)[:4096])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """查询价格"""
    if not ctx.args:
        await update.message.reply_text("用法: /price BTC")
        return

    symbol = ctx.args[0].upper()
    market = "CRYPTO" if symbol in ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX"] else "US"

    try:
        if market == "CRYPTO":
            from crypto_api import get_crypto_price
            data = get_crypto_price(symbol)
        else:
            from stock_api import get_stock
            data = get_stock(symbol, market)

        if data:
            msg = (
                f"💰 {symbol} 当前价格\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"价格: {'$' if market == 'CRYPTO' else '¥'}{data.get('price', 0):,.4f}\n"
                f"24h涨跌: {data.get('change_pct', 0):+.2f}%\n"
                f"24h高: {data.get('high_24h', 0):,.2f}\n"
                f"24h低: {data.get('low_24h', 0):,.2f}"
            )
        else:
            msg = f"❌ 未找到 {symbol} 的价格数据"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """切换实盘/模拟模式"""
    if not ctx.args:
        await update.message.reply_text("用法: /mode live|sim")
        return

    mode = ctx.args[0].lower()
    if mode not in ("live", "sim"):
        await update.message.reply_text("用法: /mode live|sim")
        return

    try:
        import config
        config.LIVE_TRADING_ENABLED = (mode == "live")
        await update.message.reply_text(f"✅ 已切换到{'实盘' if mode == 'live' else '模拟'}模式")
        logger.info(f"[Telegram] Mode changed to {mode}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_trade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """模拟下单: /trade buy BTC 0.01 65000"""
    if len(ctx.args) < 4:
        await update.message.reply_text("用法: /trade <buy|sell> <symbol> <qty> <price>")
        return

    action = ctx.args[0].lower()
    symbol = ctx.args[1].upper()
    try:
        qty = float(ctx.args[2])
        price = float(ctx.args[3])
    except ValueError:
        await update.message.reply_text("数量和价格必须是数字")
        return

    try:
        from portfolio import Portfolio
        pf = Portfolio()
        if action == "buy":
            ok = pf.buy(symbol, "CRYPTO", qty, price)
        else:
            ok = pf.sell(symbol, "CRYPTO", qty, price)
        msg = f"✅ {'买入' if action == 'buy' else '卖出'} {symbol} {qty} @ {price}" if ok else "❌ 失败"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_run_cycle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """手动触发一次策略周期"""
    if not ctx.args:
        symbols = ["BTC", "ETH"]
    else:
        symbols = [s.upper() for s in ctx.args]

    await update.message.reply_text(f"🔄 运行策略周期: {symbols}...")

    try:
        from strategy.engine import AITradingEngine
        engine = AITradingEngine(enable_live=False)
        result = engine.run_cycle(symbols=symbols)

        lines = [f"✅ Cycle #{result['cycle']} 完成"]
        lines.append(f"决策数: {len(result['decisions'])}")
        for d in result['decisions'][:5]:
            lines.append(f"  {d['symbol']} {d['action']} @ {d.get('leverage',1)}x conf={d.get('confidence',0)}")
        lines.append(f"风控状态: {result['risk_status'].get('level','?')}")

        await update.message.reply_text("\n".join(lines)[:4096])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """MCP 用量统计"""
    try:
        from mcp.unified import get_client
        client = get_client()
        summary = client.get_usage_summary()
        msg = [
            "📈 AI 调用统计",
            "━━━━━━━━━━━━━━━━━━",
            f"总调用: {summary.get('total_calls', 0)} 次",
            f"总Token: {summary.get('total_tokens', 0):,}",
            f"总费用: ${summary.get('total_cost', 0):.6f}",
        ]
        by_model = summary.get("by_model", {})
        if by_model:
            msg.append("各模型:")
            for model, stats in by_model.items():
                msg.append(f"  {model}: ${stats['cost']:.4f} / {stats['tokens']:,} tokens")
        await update.message.reply_text("\n".join(msg))
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


def run_bot():
    """启动 Telegram Bot"""
    if not BOT_TOKEN:
        logger.warning("[Telegram] TELEGRAM_BOT_TOKEN not set, bot disabled")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # 命令处理
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("positions", cmd_positions))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("trade", cmd_trade))
    app.add_handler(CommandHandler("cycle", cmd_run_cycle))
    app.add_handler(CommandHandler("stats", cmd_stats))

    logger.info("[Telegram] Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_bot()