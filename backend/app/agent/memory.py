"""进程内会话记忆（多轮对话上下文）。单实例部署足够；重启即清空，多实例请外置 Redis。"""
import threading
import time


class SessionMemory:
    def __init__(self, ttl: float = 1800.0, max_sessions: int = 200) -> None:
        self.ttl = ttl
        self.max_sessions = max_sessions
        self._store: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> list[dict]:
        with self._lock:
            self._cleanup()
            rec = self._store.get(session_id)
            if not rec:
                return []
            rec["ts"] = time.monotonic()
            return [dict(m) for m in rec["messages"]]

    def save(self, session_id: str, messages: list[dict]) -> None:
        with self._lock:
            self._cleanup()
            self._store[session_id] = {
                "ts": time.monotonic(),
                "messages": [dict(m) for m in messages],
            }

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now - v["ts"] > self.ttl]
        for k in expired:
            del self._store[k]
        if len(self._store) > self.max_sessions:
            oldest = sorted(self._store, key=lambda x: self._store[x]["ts"])
            for k in oldest[: len(self._store) - self.max_sessions]:
                del self._store[k]


memory = SessionMemory()
