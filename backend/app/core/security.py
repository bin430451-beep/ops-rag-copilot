import ipaddress
import logging
from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import get_settings
log = logging.getLogger(__name__)
_settings = get_settings()
def _ip_allowed(client_ip: str) -> bool:
    if not _settings.ip_whitelist:
        return True
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for net in _settings.ip_whitelist:
        try:
            if ip in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False
class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """内网 IP 白名单。反向代理场景下优先读取 X-Forwarded-For 首段。"""
    async def dispatch(self, request: Request, call_next):
        fwd = request.headers.get("x-forwarded-for")
        client_ip = fwd.split(",")[0].strip() if fwd else (
            request.client.host if request.client else ""
        )
        if not _ip_allowed(client_ip):
            log.warning("Blocked request from %s %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "forbidden: ip not in whitelist"},
            )
        return await call_next(request)
async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not _settings.api_key_set:
        return
    if not x_api_key or x_api_key not in _settings.api_key_set:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
