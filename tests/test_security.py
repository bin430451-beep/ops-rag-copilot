import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.security import RateLimiter, ip_matches


def test_ip_matches_cidr():
    assert ip_matches("10.1.2.3", ["10.0.0.0/8"]) is True
    assert ip_matches("192.168.1.1", ["10.0.0.0/8"]) is False
    assert ip_matches("not-an-ip", ["10.0.0.0/8"]) is False
    assert ip_matches("172.16.0.5", ["172.16.0.0/12"]) is True
    assert ip_matches("8.8.8.8", ["bad-net", "10.0.0.0/8"]) is False


def test_rate_limiter_window():
    rl = RateLimiter(limit=2, window=60.0)
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    assert rl.allow("k") is False
    assert rl.allow("other") is True  # 不同 key 互不影响


def test_rate_limiter_sliding_reset():
    rl = RateLimiter(limit=1, window=0.05)
    assert rl.allow("k") is True
    assert rl.allow("k") is False
    time.sleep(0.08)
    assert rl.allow("k") is True
