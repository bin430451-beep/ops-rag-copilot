import hmac
import ipaddress
import logging
import threading
import time
from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import get_settings
log = logging.getLogger(__name__)
_settings = get_settings()


def ip_matches(ip: str, nets: list[str]) -> bool:
    """判断 ip 是否命中任一网段/单 IP（nets 中非法条目自动忽略）。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in nets:
        try:
            if addr in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False


def _ip_allowed(client_ip: str) -> bool:
    if not _settings.ip_whitelist:
        return True
    return ip_matches(client_ip, _settings.ip_whitelist)


def _is_trusted_proxy(peer_ip: str) -> bool:
    return ip_matches(peer_ip, _settings.trusted_proxy_set)


def _client_ip(request: Request) -> str:
    """取真实客户端 IP：仅当对端为可信代理时才信任 X-Forwarded-For 首段，
    否则直接使用连接 IP——防止攻击者绕过 Nginx 伪造 X-Forwarded-For 穿透白名单。"""
    peer = request.client.host if request.client else ""
    if peer and _is_trusted_proxy(peer):
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return peer


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """内网 IP 白名单。仅信任来自可信反向代理的 X-Forwarded-For。"""

    async def dispatch(self, request: Request, call_next):
        client_ip = _client_ip(request)
        if not _ip_allowed(client_ip):
            log.warning("Blocked request from %s %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "forbidden: ip not in whitelist"},
            )
        return await call_next(request)


class RateLimiter:
    """进程内固定窗口限流器（单实例部署足够；多实例请外置 Redis）。"""

    def __init__(self, limit: int = 60, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


_limiter = RateLimiter(limit=_settings.rate_limit_per_min)


async def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """API Key 鉴权（恒定时间比较）+ 按客户端 IP 限流。"""
    client_ip = _client_ip(request)
    if not _limiter.allow(client_ip or "unknown"):
        raise HTTPException(status_code=429, detail="too many requests, slow down")
    if not _settings.api_key_set:
        return
    if not x_api_key or not any(hmac.compare_digest(x_api_key, k) for k in _settings.api_key_set):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
