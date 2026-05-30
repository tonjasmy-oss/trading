"""
OI & Funding Rate 数据接入
===========================
从交易所获取：
  - Open Interest（持仓量）
  - Funding Rate（资金费率）
支持：Binance / Bybit / OKX / Hyperliquid

使用方式：
  from market_data.oi_funding import OIProvider
  provider = OIProvider(exchange="binance")
  data = provider.get("BTC")
  print(data.oi, data.funding_rate)
"""

import os
import time
import logging
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OIData:
    """OI和Funding数据"""
    symbol: str
    oi: Optional[float]          # Open Interest (USD)
    oi_change_pct: Optional[float]  # OI变化百分比
    funding_rate: Optional[float]   # 资金费率
    next_funding_time: Optional[int]  # 下次结算时间戳
    timestamp: int


class OIProvider:
    """
    OI + Funding Rate 数据提供者
    自动选择可用交易所API
    """

    # 交易所API端点
    ENDPOINTS = {
        "binance": {
            "oi": "https://fapi.binance.com/futures/data/openInterestHist",
            "funding": "https://fapi.binance.com/futures/data/fundingRate",
        },
        "bybit": {
            "oi": "https://api.bybit.com/v5/market/open-interest",
            "funding": "https://api.bybit.com/v5/market/funding-rate",
        },
        "okx": {
            "oi": "https://www.okx.com/api/v5/rubik/stat/market/open-interest",
            "funding": "https://www.okx.com/api/v5/market/funding-rate",
        },
        "hyperliquid": {
            "oi": "https://api.hyperliquid.xyz/info",
            "funding": None,  # Hyperliquid无funding rate
        },
    }

    def __init__(self, exchange: str = "binance"):
        self.exchange = exchange.lower()
        if self.exchange not in self.ENDPOINTS:
            logger.warning(f"[OI] Unknown exchange {exchange}, using binance")
            self.exchange = "binance"

    def get(self, symbol: str) -> OIData:
        """
        获取指定品种的OI和Funding数据
        Args:
            symbol: 如 "BTC", "ETH"
        """
        symbol = symbol.upper().replace("USDT", "").replace("USD", "")

        if self.exchange == "binance":
            return self._binance(symbol)
        elif self.exchange == "bybit":
            return self._bybit(symbol)
        elif self.exchange == "okx":
            return self._okx(symbol)
        elif self.exchange == "hyperliquid":
            return self._hyperliquid(symbol)
        return OIData(symbol=symbol, oi=None, oi_change_pct=None,
                      funding_rate=None, next_funding_time=None, timestamp=int(time.time()))

    def get_batch(self, symbols: List[str]) -> Dict[str, OIData]:
        """批量获取多个品种"""
        return {sym: self.get(sym) for sym in symbols}

    # ======================== Binance ========================

    def _binance(self, symbol: str) -> OIData:
        """Binance Futures OI + Funding"""
        try:
            # Funding Rate
            funding = self._binance_funding(symbol + "USDT")
            # OI - 使用openInterestHist接口
            oi, oi_pct = self._binance_oi(symbol + "USDT")
            return OIData(
                symbol=symbol,
                oi=oi,
                oi_change_pct=oi_pct,
                funding_rate=funding.get("funding_rate"),
                next_funding_time=funding.get("next_funding_time"),
                timestamp=int(time.time()),
            )
        except Exception as e:
            logger.warning(f"[OI] Binance failed for {symbol}: {e}")
            return OIData(symbol=symbol, oi=None, oi_change_pct=None,
                          funding_rate=None, next_funding_time=None, timestamp=int(time.time()))

    def _binance_funding(self, symbol: str) -> Dict:
        """获取Binance Funding Rate"""
        try:
            url = f"{self.ENDPOINTS['binance']['funding']}?symbol={symbol}"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            if data.get("data"):
                item = data["data"][-1]
                return {
                    "funding_rate": float(item.get("fundingRate", 0)),
                    "next_funding_time": int(item.get("nextFundingTime", 0)),
                }
        except Exception as e:
            logger.warning(f"[OI] Binance funding failed: {e}")
        return {}

    def _binance_oi(self, symbol: str, period: str = "1h") -> tuple:
        """获取Binance Open Interest（最近值）"""
        try:
            url = f"{self.ENDPOINTS['binance']['oi']}?symbol={symbol}&period={period}&limit=2"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            if data.get("data") and len(data["data"]) >= 2:
                newest = data["data"][-1]
                oldest = data["data"][-2]
                oi = float(newest.get("openInterest", 0))
                oi_old = float(oldest.get("openInterest", 0))
                oi_pct = ((oi - oi_old) / oi_old * 100) if oi_old else 0
                return oi, oi_pct
        except Exception as e:
            logger.warning(f"[OI] Binance OI failed: {e}")
        return None, None

    # ======================== Bybit ========================

    def _bybit(self, symbol: str) -> OIData:
        """Bybit OI + Funding"""
        try:
            # OI
            oi, oi_pct = self._bybit_oi(symbol + "USDT")
            # Funding
            funding = self._bybit_funding(symbol + "USDT")
            return OIData(
                symbol=symbol,
                oi=oi,
                oi_change_pct=oi_pct,
                funding_rate=funding.get("funding_rate"),
                next_funding_time=funding.get("next_funding_time"),
                timestamp=int(time.time()),
            )
        except Exception as e:
            logger.warning(f"[OI] Bybit failed for {symbol}: {e}")
            return OIData(symbol=symbol, oi=None, oi_change_pct=None,
                          funding_rate=None, next_funding_time=None, timestamp=int(time.time()))

    def _bybit_oi(self, symbol: str) -> tuple:
        try:
            url = f"{self.ENDPOINTS['bybit']['oi']}?category=linear&symbol={symbol}&limit=2"
            resp = requests.get(url, timeout=5).json()
            items = resp.get("result", {}).get("list", [])
            if len(items) >= 2:
                newest = items[-1]
                oldest = items[-2]
                oi = float(newest.get("openInterest", 0))
                oi_old = float(oldest.get("openInterest", 0))
                oi_pct = ((oi - oi_old) / oi_old * 100) if oi_old else 0
                return oi, oi_pct
        except Exception as e:
            logger.warning(f"[OI] Bybit OI failed: {e}")
        return None, None

    def _bybit_funding(self, symbol: str) -> Dict:
        try:
            url = f"{self.ENDPOINTS['bybit']['funding']}?category=linear&symbol={symbol}"
            resp = requests.get(url, timeout=5).json()
            items = resp.get("result", {}).get("list", [])
            if items:
                item = items[-1]
                return {
                    "funding_rate": float(item.get("fundingRate", 0)),
                    "next_funding_time": int(float(item.get("nextFundingTime", 0))),
                }
        except Exception as e:
            logger.warning(f"[OI] Bybit funding failed: {e}")
        return {}

    # ======================== OKX ========================

    def _okx(self, symbol: str) -> OIData:
        """OKX OI + Funding"""
        try:
            oi, oi_pct = self._okx_oi(symbol + "-USDT-SWAP")
            funding = self._okx_funding(symbol + "-USDT-SWAP")
            return OIData(
                symbol=symbol,
                oi=oi,
                oi_change_pct=oi_pct,
                funding_rate=funding.get("funding_rate"),
                next_funding_time=funding.get("next_funding_time"),
                timestamp=int(time.time()),
            )
        except Exception as e:
            logger.warning(f"[OI] OKX failed for {symbol}: {e}")
            return OIData(symbol=symbol, oi=None, oi_change_pct=None,
                          funding_rate=None, next_funding_time=None, timestamp=int(time.time()))

    def _okx_oi(self, inst_id: str) -> tuple:
        try:
            url = f"{self.ENDPOINTS['okx']['oi']}?instId={inst_id}&period=1h&limit=2"
            resp = requests.get(url, timeout=5).json()
            items = resp.get("data", [])
            if len(items) >= 2:
                oi = float(items[-1][-1])  # 结构: [instId, ts, openInterest]
                oi_old = float(items[-2][-1])
                oi_pct = ((oi - oi_old) / oi_old * 100) if oi_old else 0
                return oi, oi_pct
        except Exception as e:
            logger.warning(f"[OI] OKX OI failed: {e}")
        return None, None

    def _okx_funding(self, inst_id: str) -> Dict:
        try:
            url = f"{self.ENDPOINTS['okx']['funding']}?instId={inst_id}"
            resp = requests.get(url, timeout=5).json()
            items = resp.get("data", [])
            if items:
                item = items[0]
                return {
                    "funding_rate": float(item.get("fundingRate", 0)),
                    "next_funding_time": int(float(item.get("nextFundingTime", 0))),
                }
        except Exception as e:
            logger.warning(f"[OI] OKX funding failed: {e}")
        return {}

    # ======================== Hyperliquid ========================

    def _hyperliquid(self, symbol: str) -> OIData:
        """Hyperliquid OI（无Funding Rate）"""
        try:
            url = self.ENDPOINTS["hyperliquid"]["oi"]
            resp = requests.post(
                url,
                json={"type": "openInterest", "symbol": symbol},
                timeout=5,
            )
            data = resp.json()
            oi = float(data.get("data", {}).get("open_interest", 0))
            return OIData(
                symbol=symbol,
                oi=oi,
                oi_change_pct=None,
                funding_rate=None,
                next_funding_time=None,
                timestamp=int(time.time()),
            )
        except Exception as e:
            logger.warning(f"[OI] Hyperliquid failed for {symbol}: {e}")
            return OIData(symbol=symbol, oi=None, oi_change_pct=None,
                          funding_rate=None, next_funding_time=None, timestamp=int(time.time()))


# ─── 快速测试 ────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    for exchange in ["binance", "bybit", "okx"]:
        try:
            provider = OIProvider(exchange=exchange)
            data = provider.get("BTC")
            print(f"\n[{exchange.upper()}] BTC:")
            print(f"  OI: ${data.oi:,.0f}" if data.oi else "  OI: N/A", end="")
            print(f"  OI变化: {data.oi_change_pct:+.2f}%" if data.oi_change_pct is not None else "", end="")
            print(f"  Funding: {data.funding_rate:+.4f}%" if data.funding_rate is not None else "  Funding: N/A")
        except Exception as e:
            print(f"[{exchange}] Error: {e}")

    print("\n✅ OI Provider OK")