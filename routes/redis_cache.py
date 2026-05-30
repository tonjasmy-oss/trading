"""Redis 缓存层 - 提供实时持仓共享和价格缓存"""
import json
import time
from typing import Optional, Dict, Any
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

_redis_client = None


def _get_redis():
    """延迟初始化 Redis 连接（配置了但未启用时不影响启动）"""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


class RedisCache:
    """Redis 缓存工具"""

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """读取缓存值"""
        r = _get_redis()
        if r is None:
            return None
        try:
            val = r.get(key)
            if val:
                return json.loads(val)
        except Exception:
            pass
        return None

    @staticmethod
    def set(key: str, value: Any, ttl: int = 60) -> bool:
        """写入缓存值，ttl 单位为秒"""
        r = _get_redis()
        if r is None:
            return False
        try:
            r.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            return False

    @staticmethod
    def delete(key: str) -> bool:
        """删除缓存"""
        r = _get_redis()
        if r is None:
            return False
        try:
            r.delete(key)
            return True
        except Exception:
            return False

    @staticmethod
    def hset(key: str, field: str, value: Any) -> bool:
        """Hash 表写入"""
        r = _get_redis()
        if r is None:
            return False
        try:
            r.hset(key, field, json.dumps(value))
            return True
        except Exception:
            return False

    @staticmethod
    def hget(key: str, field: str) -> Optional[Any]:
        """Hash 表读取"""
        r = _get_redis()
        if r is None:
            return None
        try:
            val = r.hget(key, field)
            if val:
                return json.loads(val)
        except Exception:
            pass
        return None

    @staticmethod
    def hgetall(key: str) -> Dict[str, Any]:
        """Hash 表读取全部"""
        r = _get_redis()
        if r is None:
            return {}
        try:
            data = r.hgetall(key)
            return {k: json.loads(v) for k, v in data.items()}
        except Exception:
            return {}

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """删除匹配的所有 key"""
        r = _get_redis()
        if r is None:
            return 0
        try:
            keys = r.keys(pattern)
            if keys:
                return r.delete(*keys)
        except Exception:
            pass
        return 0


# 持仓共享 key 前缀
POSITION_KEY_PREFIX = "position:"
POSITION_TTL = 300  # 5分钟过期，实时更新


def cache_position(symbol: str, position_data: Dict) -> bool:
    """缓存持仓信息（多进程共享）"""
    return RedisCache.hset(
        f"{POSITION_KEY_PREFIX}{symbol}",
        "data",
        {**position_data, "cached_at": time.time()}
    )


def get_cached_position(symbol: str) -> Optional[Dict]:
    """获取缓存的持仓信息"""
    return RedisCache.hget(f"{POSITION_KEY_PREFIX}{symbol}", "data")


def invalidate_position(symbol: str) -> bool:
    """删除持仓缓存"""
    return RedisCache.delete(f"{POSITION_KEY_PREFIX}{symbol}")


# 价格缓存 key 前缀
PRICE_KEY_PREFIX = "price:"
PRICE_TTL = 5  # 5秒 TTL


def cache_price(symbol: str, price_data: Dict) -> bool:
    """缓存价格数据（减少交易所 API 调用）"""
    return RedisCache.set(
        f"{PRICE_KEY_PREFIX}{symbol}",
        {**price_data, "cached_at": time.time()},
        ttl=PRICE_TTL
    )


def get_cached_price(symbol: str) -> Optional[Dict]:
    """获取缓存的价格数据"""
    return RedisCache.get(f"{PRICE_KEY_PREFIX}{symbol}")