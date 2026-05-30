"""速率限制中间件 - 防止 API DoS 攻击"""
import time
from collections import defaultdict
from typing import Dict, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 简单内存存储：IP -> (请求时间戳列表, 已拒绝计数)
_rate_limits: Dict[str, Dict] = defaultdict(lambda: {
    "timestamps": [],
    "rejected": 0,
    "blocked_until": 0
})

# 配置
MAX_REQUESTS = 60          # 时间窗口内最大请求数
WINDOW_SECONDS = 60        # 时间窗口（秒）
BLOCK_DURATION = 300       # 触发限制后屏蔽时长（秒）
SLOW_KEY_PREFIX = "@"      # 慢速客户端额外限制前缀

_cleanup_last = time.time()


def _cleanup_old_entries():
    """清理过期条目，每分钟执行一次"""
    global _cleanup_last
    now = time.time()
    if now - _cleanup_last < 60:
        return
    _cleanup_last = now
    for ip, data in list(_rate_limits.items()):
        # 删除窗口外的旧时间戳
        cutoff = now - WINDOW_SECONDS
        data["timestamps"] = [t for t in data["timestamps"] if t > cutoff]
        if data["blocked_until"] > 0 and now > data["blocked_until"]:
            data["blocked_until"] = 0
            data["rejected"] = 0


def _check_rate_limit(ip: str) -> Tuple[bool, int]:
    """
    检查 IP 是否超限。
    返回 (是否允许, 剩余时间秒)
    """
    _cleanup_old_entries()
    now = time.time()
    data = _rate_limits[ip]

    # 已在屏蔽中
    if data["blocked_until"] > now:
        return False, int(data["blocked_until"] - now)

    # 清理过期的请求时间戳
    cutoff = now - WINDOW_SECONDS
    data["timestamps"] = [t for t in data["timestamps"] if t > cutoff]

    if len(data["timestamps"]) >= MAX_REQUESTS:
        # 触发限制，开始屏蔽
        data["blocked_until"] = now + BLOCK_DURATION
        data["rejected"] += 1
        return False, BLOCK_DURATION

    # 记录本次请求
    data["timestamps"].append(now)
    return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API 速率限制中间件"""

    async def dispatch(self, request: Request, call_next):
        # 仅限制 /api/ 路径
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = _check_rate_limit(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"请求过于频繁，请 {remaining} 秒后重试",
                    "retry_after": remaining
                },
                headers={"Retry-After": str(remaining)}
            )

        response = await call_next(request)
        # 添加速率限制信息头
        remaining_reqs = MAX_REQUESTS - len(_rate_limits[client_ip]["timestamps"])
        response.headers["X-RateLimit-Remaining"] = str(remaining_reqs)
        response.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS)
        return response