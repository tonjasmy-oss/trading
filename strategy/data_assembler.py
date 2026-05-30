"""
Data Assembler — 市场数据组装层
=================================
参考 NOFX buildTradingContext()，组装完整的交易上下文数据：
  - 账户余额（equity, available, unrealizedPnL）
  - 当前持仓（symbol, side, entry, mark, qty, leverage, liq_price）
  - K线数据（多时间框架 OHLCV）
  - 技术指标（EMA, MACD, RSI, ATR, Volume）
  - 链上数据（OI, Funding Rate）
  - 量化数据（资金流向, OI变化）
  - 最近N笔平仓交易

使用方式：
  from strategy.data_assembler import DataAssembler
  assembler = DataAssembler()
  ctx = assembler.build_context(symbols=["BTC", "ETH"])
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AccountData:
    """账户数据"""
    equity: float
    available: float
    unrealized_pnl: float
    total_equity: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "equity": self.equity,
            "available": self.available,
            "unrealized_pnl": self.unrealized_pnl,
            "total_equity": self.total_equity,
        }


@dataclass
class PositionData:
    """持仓数据"""
    symbol: str
    side: str          # "long" / "short"
    entry_price: float
    mark_price: float
    quantity: float
    leverage: float
    unrealized_pnl: float
    liquidation_price: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "mark_price": self.mark_price,
            "quantity": self.quantity,
            "leverage": self.leverage,
            "unrealized_pnl": self.unrealized_pnl,
            "liquidation_price": self.liquidation_price,
        }


@dataclass
class MarketData:
    """市场数据（单时间框架）"""
    symbol: str
    timeframe: str
    ohlcv: List[Dict]       # [{"time": ts, "open": float, "high": float, "low": float, "close": float, "volume": float}]
    indicators: Dict[str, List[float]] = field(default_factory=dict)
    oi: Optional[float] = None
    funding_rate: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ohlcv": self.ohlcv,
            "indicators": self.indicators,
            "oi": self.oi,
            "funding_rate": self.funding_rate,
        }


@dataclass
class QuantData:
    """量化数据（资金流向/机构数据）"""
    institution_future_flow: float = 0.0
    institution_spot_flow: float = 0.0
    personal_future_flow: float = 0.0
    personal_spot_flow: float = 0.0
    oi_delta_1h: float = 0.0
    oi_delta_4h: float = 0.0
    oi_delta_24h: float = 0.0
    price_change_1h: float = 0.0
    price_change_4h: float = 0.0
    price_change_24h: float = 0.0


@dataclass
class TradingContext:
    """完整交易上下文"""
    account: AccountData
    positions: List[PositionData]
    market_data: Dict[str, Dict[str, MarketData]]   # symbol -> {timeframe -> MarketData}
    recent_trades: List[Dict]
    quant_data: Dict[str, QuantData]                # symbol -> QuantData
    btc_overview: Dict[str, Any]
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account": self.account.to_dict(),
            "positions": [p.to_dict() for p in self.positions],
            "market_data": {
                sym: {tf: md.to_dict() for tf, md in tfs.items()}
                for sym, tfs in self.market_data.items()
            },
            "recent_trades": self.recent_trades,
            "quant_data": {sym: vars(qd) for sym, qd in self.quant_data.items()},
            "btc_overview": self.btc_overview,
            "timestamp": self.timestamp,
        }


class DataAssembler:
    """
    市场数据组装器
    负责从各数据源汇聚完整的市场上下文
    """

    # 支持的时间框架
    TIMEFRAMES = ["5m", "15m", "1h", "4h"]
    PRIMARY_TF = "5m"
    PRIMARY_COUNT = 30

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}   # symbol -> {tf -> data}
        self._cache_ttl = 30                          # 缓存30秒

    def build_context(
        self,
        symbols: List[str],
        fetch_quant: bool = False,
        fetch_oi: bool = False,
    ) -> TradingContext:
        """
        构建完整交易上下文

        Args:
            symbols: 待分析的交易品种列表
            fetch_quant: 是否获取量化数据（资金流向等）
            fetch_oi: 是否获取OI数据
        """
        logger.info(f"[DataAssembler] build_context symbols={symbols}")

        # 1. 账户数据
        account = self._fetch_account()

        # 2. 持仓数据
        positions = self._fetch_positions()

        # 3. 市场数据（多时间框架）
        market_data: Dict[str, Dict[str, MarketData]] = {}
        for sym in symbols:
            market_data[sym] = {}
            for tf in self.TIMEFRAMES:
                md = self._fetch_market_data(sym, tf)
                if md:
                    market_data[sym][tf] = md

        # 4. BTC全局概览
        btc_overview = self._fetch_btc_overview()

        # 5. 最近平仓交易（最近10笔）
        recent_trades = self._fetch_recent_trades(limit=10)

        # 6. 量化数据（可选）
        quant_data: Dict[str, QuantData] = {}
        if fetch_quant:
            for sym in symbols:
                quant_data[sym] = self._fetch_quant_data(sym)

        return TradingContext(
            account=account,
            positions=positions,
            market_data=market_data,
            recent_trades=recent_trades,
            quant_data=quant_data,
            btc_overview=btc_overview,
        )

    # ======================== 私有方法 ========================

    def _fetch_account(self) -> AccountData:
        """获取账户数据（优先从实盘，无则取模拟）"""
        try:
            from stock_trading import StockTrader
            trader = StockTrader.get_trader("us")
            if trader and trader.is_connected():
                acc = trader.get_account()
                return AccountData(
                    equity=acc.get("portfolio_value", 0),
                    available=acc.get("cash", 0),
                    unrealized_pnl=0,
                    total_equity=acc.get("portfolio_value", 0),
                )
        except Exception as e:
            logger.warning(f"账户数据获取失败: {e}")

        # 回退：尝试从数据库读取模拟资金
        try:
            from database import get_positions
            from config import INITIAL_CAPITAL
            total_cost = sum(p["quantity"] * p["avg_price"] for p in get_positions())
            equity = INITIAL_CAPITAL + total_cost
            return AccountData(
                equity=equity,
                available=equity - total_cost,
                unrealized_pnl=0,
                total_equity=equity,
            )
        except Exception:
            return AccountData(equity=0, available=0, unrealized_pnl=0, total_equity=0)

    def _fetch_positions(self) -> List[PositionData]:
        """获取当前持仓"""
        try:
            from database import get_positions
            rows = get_positions()
            return [
                PositionData(
                    symbol=r["symbol"],
                    side="long",
                    entry_price=r["avg_price"],
                    mark_price=r["avg_price"],
                    quantity=r["quantity"],
                    leverage=1.0,
                    unrealized_pnl=0,
                    liquidation_price=0,
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"持仓数据获取失败: {e}")
            return []

    def _fetch_market_data(self, symbol: str, timeframe: str) -> Optional[MarketData]:
        """获取指定时间框架的市场数据（含技术指标）"""
        try:
            from crypto_api import get_crypto_price
            from stock_api import get_stock

            # 获取OHLCV（简化实现：取最近N个点）
            # 实际应调用K线API，这里用价格模拟
            price_data = get_crypto_price(symbol)
            if not price_data:
                # 尝试股票
                market = self._symbol_to_market(symbol)
                price_data = get_stock(symbol, market)

            if not price_data:
                return None

            current_price = price_data.get("price", 0)
            change_pct = price_data.get("change_pct", 0)

            # 模拟K线数据（实际应从交易所API获取）
            ohlcv = self._generate_ohlcv(symbol, timeframe, current_price)

            # 计算技术指标
            closes = [d["close"] for d in ohlcv]
            indicators = {
                "EMA20": self._calc_ema(closes, 20),
                "EMA60": self._calc_ema(closes, 60) if len(closes) >= 60 else self._calc_ema(closes, len(closes)),
                "RSI7": self._calc_rsi(closes, 7),
                "RSI14": self._calc_rsi(closes, 14),
                "MACD": self._calc_macd(closes),
                "ATR": self._calc_atr(ohlcv, 14) if len(ohlcv) >= 14 else 0,
                "Volume": [d["volume"] for d in ohlcv],
            }

            return MarketData(
                symbol=symbol,
                timeframe=timeframe,
                ohlcv=ohlcv,
                indicators=indicators,
                oi=None,
                funding_rate=None,
            )
        except Exception as e:
            logger.warning(f"市场数据获取失败 {symbol} {timeframe}: {e}")
            return None

    def _fetch_btc_overview(self) -> Dict[str, Any]:
        """获取BTC全局概览（用于User Prompt中的BTC市场概述段落）"""
        try:
            from crypto_api import get_crypto_price
            btc = get_crypto_price("BTC")
            if btc:
                return {
                    "price": btc.get("price", 0),
                    "change_pct": btc.get("change_pct", 0),
                    "high_24h": btc.get("high_24h", 0),
                    "low_24h": btc.get("low_24h", 0),
                    "volume_24h": btc.get("volume_24h", 0),
                }
        except Exception:
            pass
        return {}

    def _fetch_recent_trades(self, limit: int = 10) -> List[Dict]:
        """获取最近N笔平仓交易"""
        try:
            from database import get_trades
            trades = get_trades(limit)
            return [
                {
                    "symbol": t["symbol"],
                    "side": t["trade_type"],
                    "quantity": t["quantity"],
                    "price": t["price"],
                    "pnl_pct": 0,  # 简化，未计算
                    "closed_at": t["traded_at"],
                }
                for t in trades[:limit]
            ]
        except Exception:
            return []

    def _fetch_quant_data(self, symbol: str) -> QuantData:
        """获取量化数据（资金流向/OI变化）"""
        # 占位：实际应接入链上数据API（如Glassnode/BYBT等）
        return QuantData()

    def _fetch_oi(self, symbol: str) -> Optional[float]:
        """获取Open Interest"""
        # 占位：实际应从交易所期货API获取
        return None

    # ======================== 技术指标计算 ========================

    def _generate_ohlcv(self, symbol: str, timeframe: str, current_price: float) -> List[Dict]:
        """
        生成模拟K线数据（占位实现）
        实际应调用: Binance K线API / Hyperliquid 等
        """
        intervals = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
        seconds = intervals.get(timeframe, 300)
        now = int(time.time())
        count = self.PRIMARY_COUNT

        # 生成带趋势的模拟数据
        import random
        random.seed(hash(symbol + timeframe) % 2**32)
        base = current_price
        data = []
        for i in range(count):
            ts = now - (count - i) * seconds
            noise = random.uniform(-0.005, 0.005)
            close = base * (1 + noise + (i - count / 2) * 0.0003)
            open_ = base * (1 + random.uniform(-0.003, 0.003) + (i - count / 2) * 0.0003)
            high = max(open_, close) * (1 + random.uniform(0, 0.003))
            low = min(open_, close) * (1 - random.uniform(0, 0.003))
            volume = random.uniform(100, 1000)
            data.append({
                "time": ts,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": round(volume, 2),
            })
        return data

    def _calc_ema(self, prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            period = len(prices)
        if period == 0:
            return prices
        k = 2 / (period + 1)
        ema = [sum(prices[:period]) / period]
        for p in prices[period:]:
            ema.append(p * k + ema[-1] * (1 - k))
        return ema

    def _calc_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(d, 0) for d in deltas]
        losses = [-min(d, 0) for d in deltas]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        rsi = [50.0] * period
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - 100 / (1 + rs))
        return rsi

    def _calc_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> List[float]:
        if len(prices) < slow:
            return [0.0] * len(prices)
        ema_fast = self._calc_ema(prices, fast)
        ema_slow = self._calc_ema(prices, slow)
        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal_line = self._calc_ema(macd_line, signal)
        result = [0.0] * (len(prices) - len(signal_line))
        for i in range(len(signal_line)):
            result.append(macd_line[len(macd_line) - len(signal_line) + i] - signal_line[i])
        return result

    def _calc_atr(self, ohlcv: List[Dict], period: int = 14) -> float:
        if len(ohlcv) < period:
            return 0.0
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i]["high"]
            low = ohlcv[i]["low"]
            prev_close = ohlcv[i-1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return sum(trs[-period:]) / period

    # ======================== 工具方法 ========================

    def _symbol_to_market(self, symbol: str) -> str:
        """根据代码推断市场"""
        crypto_list = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX"]
        if symbol in crypto_list:
            return "CRYPTO"
        if symbol.isupper() and len(symbol) <= 5:
            if symbol.isdigit():
                if len(symbol) == 5 or (len(symbol) == 6 and symbol[0] == "6"):
                    return "CN"
                return "HK"
            return "US"
        return "CRYPTO"