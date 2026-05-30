"""
Technical Indicators — 技术指标计算层
=====================================
支持：
  - TA-Lib（如果可用）
  - pandas-ta（如果可用）
  - 纯NumPy fallback（保证始终可用，优先实现）

指标：
  EMA(n), SMA(n), MACD(12,26,9), RSI(n), ATR(n), Bollinger Bands, Volume

使用方式：
  from strategy.indicators import TechIndicators
  ti = TechIndicators()
  result = ti.compute_indicators(ohlcv, indicators=["EMA20", "RSI7", "MACD"])
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# 尝试导入
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    logger.info("pandas_ta not available, using NumPy fallback")


class TechIndicators:
    """
    技术指标计算器
    优先级: TA-Lib > pandas-ta > NumPy
    """

    def __init__(self, use_lib: str = "auto"):
        self.use_lib = use_lib
        if use_lib == "auto":
            if HAS_TALIB:
                self.use_lib = "talib"
            elif HAS_PANDAS_TA:
                self.use_lib = "pandas_ta"
            else:
                self.use_lib = "numpy"
        logger.info(f"[TechIndicators] Using: {self.use_lib}")

    def compute_indicators(
        self,
        ohlcv: List[Dict],
        indicators: Optional[List[str]] = None,
    ) -> Dict[str, List[float]]:
        """计算技术指标"""
        if not ohlcv:
            return {}

        df = self._to_df(ohlcv)
        close = df["close"].values
        indicators = indicators or ["EMA20", "EMA60", "RSI7", "RSI14", "MACD", "ATR"]

        results: Dict[str, List[float]] = {}
        for ind in indicators:
            upper = ind.upper()
            try:
                if upper == "EMA20":
                    results["EMA20"] = self.ema(close, 20)
                elif upper == "EMA60":
                    results["EMA60"] = self.ema(close, 60)
                elif upper.startswith("EMA") and upper[3:].isdigit():
                    results[upper] = self.ema(close, int(upper[3:]))
                elif upper == "SMA":
                    results["SMA"] = self.sma(close, 20)
                elif upper == "RSI7":
                    results["RSI7"] = self.rsi(close, 7)
                elif upper == "RSI14":
                    results["RSI14"] = self.rsi(close, 14)
                elif upper.startswith("RSI") and upper[3:].isdigit():
                    results[upper] = self.rsi(close, int(upper[3:]))
                elif upper == "MACD":
                    results["MACD"] = self.macd(close)
                elif upper == "ATR":
                    results["ATR"] = self.atr(df, 14)
                elif upper == "BBANDS":
                    u, m, l = self.bbands(close, 20)
                    results["BBANDS_UPPER"] = u
                    results["BBANDS_MID"] = m
                    results["BBANDS_LOWER"] = l
                elif upper == "VOLUME":
                    results["VOLUME"] = df["volume"].tolist() if "volume" in df.columns else []
            except Exception as e:
                logger.warning(f"[TechIndicators] {ind} failed: {e}")
                results[upper] = []
        return results

    # ─── EMA ────────────────────────────────────────────────

    def ema(self, prices, period: int) -> List[float]:
        """指数移动平均"""
        a = np.asarray(prices, dtype=float)
        if len(a) < period:
            return [np.nan] * len(a)
        if self.use_lib == "talib" and HAS_TALIB:
            return list(talib.EMA(a, timeperiod=period))
        if self.use_lib == "pandas_ta" and HAS_PANDAS_TA:
            return list(pd.Series(a).pipe(lambda s: ta.ema(s, length=period)).dropna())

        k = 2.0 / (period + 1)
        out = [np.nan] * (period - 1)
        out.append(float(a[:period].mean()))
        for i in range(period, len(a)):
            out.append(float(a[i] * k + out[-1] * (1 - k)))
        return out

    # ─── SMA ────────────────────────────────────────────────

    def sma(self, prices, period: int) -> List[float]:
        a = np.asarray(prices, dtype=float)
        if len(a) < period:
            return [np.nan] * len(a)
        if self.use_lib == "talib" and HAS_TALIB:
            return list(talib.SMA(a, timeperiod=period))

        out = []
        for i in range(len(a)):
            if i < period - 1:
                out.append(np.nan)
            else:
                out.append(float(a[i - period + 1:i + 1].mean()))
        return out

    # ─── RSI ────────────────────────────────────────────────

    def rsi(self, prices, period: int = 14) -> List[float]:
        a = np.asarray(prices, dtype=float)
        if len(a) < period + 1:
            return [50.0] * len(a)
        if self.use_lib == "talib" and HAS_TALIB:
            return list(talib.RSI(a, timeperiod=period))

        deltas = np.diff(a)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = gains[:period].mean()
        avg_loss = losses[:period].mean()
        out = [50.0] * period
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                out.append(100.0)
            else:
                out.append(100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
        return out

    # ─── MACD ───────────────────────────────────────────────

    def macd(self, prices, fast: int = 12, slow: int = 26, signal: int = 9) -> List[float]:
        a = np.asarray(prices, dtype=float)
        if len(a) < slow:
            return [0.0] * len(a)
        if self.use_lib == "talib" and HAS_TALIB:
            macd, sig, _ = talib.MACD(a, fastperiod=fast, slowperiod=slow, signalperiod=signal)
            return [float(m - s) for m, s in zip(macd, sig)]

        # Pure numpy: use pandas for rolling EMA (no talib/pandas-ta needed)
        s = pd.Series(a)
        e_fast = s.ewm(span=fast, adjust=False).mean().values
        e_slow = s.ewm(span=slow, adjust=False).mean().values
        macd_vals = e_fast - e_slow
        sig_series = pd.Series(macd_vals)
        sig_vals = sig_series.ewm(span=signal, adjust=False).mean().values
        histogram = macd_vals - sig_vals
        return [0.0 if np.isnan(v) else float(v) for v in histogram]

    # ─── ATR ────────────────────────────────────────────────

    def atr(self, df: pd.DataFrame, period: int = 14) -> List[float]:
        if self.use_lib == "talib" and HAS_TALIB:
            return list(talib.ATR(df["high"].values, df["low"].values, df["close"].values, timeperiod=period))

        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        tr = np.maximum(
            high[1:] - low[1:],
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        )
        out = [np.nan] * period
        if len(tr) < period:
            return out + [float(np.mean(tr))] * (len(tr) - period)
        out.append(float(tr[:period].mean()))
        for t in tr[period:]:
            out.append((out[-1] * (period - 1) + t) / period)
        return out

    # ─── Bollinger Bands ────────────────────────────────────

    def bbands(self, prices, period: int = 20) -> tuple:
        a = np.asarray(prices, dtype=float)
        if len(a) < period:
            return [np.nan] * len(a), [np.nan] * len(a), [np.nan] * len(a)
        if self.use_lib == "talib" and HAS_TALIB:
            u, m, l = talib.BBANDS(a, timeperiod=period)
            return list(u), list(m), list(l)

        mid = np.array(self.sma(a, period))
        std = pd.Series(a).rolling(period).std().values
        upper = mid + 2 * std
        lower = mid - 2 * std
        return list(upper), list(mid), list(lower)

    # ─── 工具 ────────────────────────────────────────────────

    def _to_df(self, ohlcv) -> pd.DataFrame:
        if isinstance(ohlcv, pd.DataFrame):
            return ohlcv
        df = pd.DataFrame(ohlcv)
        for col in ["open", "Open"]:
            if col in df.columns and "open" not in df.columns:
                df["open"] = df[col]
        for col in ["high", "High"]:
            if col in df.columns and "high" not in df.columns:
                df["high"] = df[col]
        for col in ["low", "Low"]:
            if col in df.columns and "low" not in df.columns:
                df["low"] = df[col]
        for col in ["close", "Close"]:
            if col in df.columns and "close" not in df.columns:
                df["close"] = df[col]
        for col in ["volume", "Volume"]:
            if col in df.columns and "volume" not in df.columns:
                df["volume"] = df[col]
        return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ti = TechIndicators(use_lib="numpy")

    np.random.seed(42)
    prices = 60000 + np.cumsum(np.random.randn(100) * 100)
    ohlcv = [
        {"time": 1700000000 + i * 300, "open": p - 50, "high": p + 100, "low": p - 150, "close": p, "volume": 500}
        for i, p in enumerate(prices)
    ]

    r = ti.compute_indicators(ohlcv, ["EMA20", "RSI7", "RSI14", "MACD", "ATR"])
    last = lambda k: round(float(r[k][-1]), 4)
    print(f"EMA20={last('EMA20')}, RSI7={last('RSI7')}, RSI14={last('RSI14')}, "
          f"MACD={last('MACD')}, ATR={last('ATR')}")
    print("✅ indicators OK")