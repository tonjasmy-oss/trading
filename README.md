# 📊 Trading System — 三省六部 AI 交易系统

> 基于多 Agent 架构的量化交易监控系统，参考 NOFX 设计理念重构

**Language**: [中文](README.md) · [English](README_EN.md)

---

## 🎯 项目概览

本系统是一个完整的 AI 驱动的交易监控平台，支持：
- 🪙 **加密货币**（Binance/Bybit/OKX/Hyperliquid）
- 📈 **美股/港股/A股**（Alpaca/老虎证券/富途）
- 🤖 **AI 决策**（DeepSeek/Qwen/OpenAI/Gemini 多模型统一）
- 📊 **Dashboard**（React SPA + TradingView K线）

---

## 🏗 架构 — 三省六部

```
┌─────────────────────────────────────────────────────────┐
│                    三省六部 Agent 系统                    │
├────────────┬────────────┬────────────┬───────────────────┤
│  太子(编排) │  中书省(策略)│  门下省(风控)│   尚书省(执行)   │
│   任务分拣  │  Data+Prompt│  RiskMgr  │   实盘交易       │
└────────────┴────────────┴────────────┴───────────────────┘
```

| 部门 | 职责 | 核心模块 |
|------|------|---------|
| **太子** | 皇上旨意接收/分发/回奏 | 飞书 Relay |
| **中书省** | 策略生成/AI Prompt 构建 | `strategy/engine.py` `prompt_builder.py` |
| **门下省** | 风控审核/信号校验 | `risk_manager.py` `GlobalRiskManager` |
| **尚书省** | 实盘执行/交易路由 | `stock_trading/unified_trader.py` |
| **户部** | 资金管理/权益统计 | `portfolio.py` `database.py` |
| **刑部** | 安全审计/权限管控 | `agent_gateway/fastapi_routes.py` |

---

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 18 + TypeScript + Vite + TailwindCSS + lightweight-charts |
| **后端** | Python 3.13 + FastAPI |
| **AI** | MCP 统一层（DeepSeek/Qwen/OpenAI/Gemini/Kimi/Grok） |
| **数据库** | SQLite |
| **指标** | 纯 NumPy 技术指标（EMA/RSI/MACD/ATR/BBANDS） |
| **数据** | K线 + 技术指标 + OI/Funding Rate |

---

## 🚀 快速启动

### 方式一：本地 Python

```bash
# 1. 克隆
git clone https://github.com/tonjasmy-oss/trading.git
cd trading

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动后端
python3 main.py --port 8081

# 4. 启动前端（新窗口）
cd frontend && npm install && npm run dev
```

### 方式二：Docker

```bash
docker compose up -d
# 后端: http://localhost:8081
# 前端: http://localhost:5173
```

### 方式三：Railway（一键部署）

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/nofx?referralCode=nofx)

---

## 📁 项目结构

```
trading/
├── main.py                    # 后端入口（FastAPI + Dashboard）
├── config.py                  # 全局配置
├── dashboard.py                # Web Dashboard
│
├── strategy/                   # 【中书省】策略模块
│   ├── data_assembler.py       # 多时间框架K线 + 指标组装
│   ├── prompt_builder.py       # System 8段式 + User结构化Prompt
│   ├── response_parser.py     # AI响应 XML+JSON 双层解析
│   ├── engine.py              # 完整策略循环引擎
│   └── indicators.py          # 纯NumPy技术指标库
│
├── mcp/                        # 【AI模型统一层】
│   └── unified.py             # 多模型路由 + 计费 + Fallback
│
├── market_data/               # 市场数据
│   └── oi_funding.py         # OI + Funding Rate（Binance/Bybit/OKX）
│
├── risk_manager.py             # 【门下省】GlobalRiskManager + Trailing Stop
├── portfolio.py               # 【户部】持仓管理
├── live_trading.py            # 【尚书省】实盘交易编排
│
├── stock_trading/             # 券商接口
│   └── unified_trader.py      # Alpaca + Tiger + Futu 统一接口
│
├── crypto_api.py              # 加密货币行情
├── stock_api.py               # 股票行情（A/港/美）
├── monitor.py                 # 价格监控 + 飞书告警
├── telegram_bot.py             # Telegram 控制Bot
│
├── frontend/                  # 【React SPA 前端】
│   ├── src/
│   │   ├── pages/            # Dashboard/行情/持仓/交易/告警
│   │   ├── components/        # KLineChart（TradingView K线）
│   │   ├── stores/            # Zustand 状态管理
│   │   └── services/          # API 接口层
│   └── vite.config.ts         # Vite 配置 + 代理
│
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## ⚙️ 环境变量配置

复制 `.env.example` 为 `.env`，填入以下配置：

```bash
# 交易所
CRYPTO_API_KEY=your_binance_key
CRYPTO_API_SECRET=your_binance_secret

# AI 模型
DEEPSEEK_API_KEY=your_deepseek_key

# 飞书告警
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_SECRET=your_feishu_secret

# Telegram Bot（可选）
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_ALLOWED_USERS=123456,789012

# Dashboard
DASHBOARD_PORT=8081
```

---

## 📊 核心功能

### 策略引擎（参考 NOFX）

```
Coin Selection → Data Assembly → System Prompt → User Prompt → AI Request → Parsing → Execution
```

| 功能 | 说明 |
|------|------|
| **多源选币** | Static / AI500评分池 / OI持仓增长排名 / 混合模式 |
| **多时间框架** | 5m / 15m / 1h / 4h K线 + 指标 |
| **结构化 Prompt** | 8段式 System Prompt + 结构化 User Prompt |
| **AI 响应解析** | XML+JSON 双层提取 + 字符编码修复 |
| **多策略投票** | RSI + SMA + MACD 加权聚合 |

### 风控体系（参考 NOFX 双层设计）

```python
# 代码层（硬约束）
max_positions: 3          # 最大持仓数
max_margin_usage: 90%      # 最大保证金使用
min_position_size: 12 USDT # 最小仓位

# AI引导层（建议值）
altcoin_max_leverage: 5x
min_risk_reward_ratio: 3:1
min_confidence: 75
```

额外特性：
- 动态风险等级（equity 回落 5% → CAUTION，10% → LOCK）
- Trailing Stop（跟踪止损）
- 持仓超时强制平仓（72h）

### 技术指标

```
EMA(n)   — 指数移动平均（任意周期）
RSI(n)   — 相对强弱指数
MACD     — MACD线 - Signal线
ATR      — 平均真实波幅
BBANDS   — 布林带（20周期 ±2σ）
```

---

## 🌐 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/system/status` | GET | 系统状态 |
| `/api/sansheng/status` | GET | 三省六部架构状态 |
| `/api/positions` | GET | 当前持仓 |
| `/api/portfolio/value` | GET | 持仓市值 + 盈亏 |
| `/api/trades` | GET | 交易历史 |
| `/api/alerts` | GET | 告警记录 |
| `/api/market/prices` | GET | 全市场实时行情 |
| `/api/stock/chart` | GET | 股票K线 + 回测图表 |
| `/api/trading/mode` | POST | 实盘/模拟切换（需Token） |

---

## 🎨 前端截图

Dashboard 包含：
- 📈 系统总览 + 三省状态卡片
- 🌐 四市场行情（加密/美股/港股/A股）
- 💼 持仓管理 + 盈亏统计
- 📋 交易记录 + 方向高亮
- 🔔 告警历史时间线

K线图使用 `lightweight-charts`（TradingView 开源库），支持：
- 阴阳线（红涨绿跌）
- 买卖点标记
- 权益曲线

---

## 🔧 开发指南

### 添加新的技术指标

```python
from strategy.indicators import TechIndicators

ti = TechIndicators(use_lib="numpy")
result = ti.compute_indicators(ohlcv, indicators=["EMA20", "RSI7", "MACD"])
print(result["EMA20"][-1])
```

### 运行策略周期（测试）

```python
from strategy.engine import AITradingEngine

engine = AITradingEngine(enable_live=False)
result = engine.run_cycle(symbols=["BTC", "ETH"])
print(result["decisions"])
```

### 接入新的 AI 模型

```python
from mcp.unified import get_client

client = get_client()
resp = client.chat(
    message="Your trading prompt",
    system_prompt="You are a professional trader",
    model="qwen",  # 自动 fallback
)
print(resp.content)
```

### Telegram Bot 命令

```
/start     — 欢迎
/status    — 系统状态
/positions — 持仓
/alerts    — 告警
/price BTC — 查询价格
/mode live — 切换实盘
/cycle BTC — 手动触发策略周期
/stats     — AI 调用统计
```

---

## 📝 许可证

本项目基于 AGPL-3.0 开源，参考 NOFX（AGPL-3.0）设计理念。

NOFX 仓库：https://github.com/NoFxAiOS/nofx

---

## 🙏 致谢

- [NOFX](https://github.com/NoFxAiOS/nofx) — AI Trading Terminal 设计参考
- [lightweight-charts](https://tradingview.github.io/lightweight-charts/) — TradingView 开源 K线库
- [TailwindCSS](https://tailwindcss.com/) — CSS 框架