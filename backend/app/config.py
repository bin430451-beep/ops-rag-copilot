from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "dev"
    log_level: str = "INFO"
    allowed_ips: str = "127.0.0.1"
    api_keys: str = "dev-key"
    trusted_proxies: str = "127.0.0.1,172.16.0.0/12"
    rate_limit_per_min: int = 60
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "ops_kb"
    embedding_base_url: str = "http://localhost:8081/v1"
    embedding_model: str = "Qwen3-Embedding-0.6B"
    embedding_api_key: str = "EMPTY"
    embedding_dim: int = 1024
    llm_base_url: str = "http://localhost:8000/v1"
    llm_model: str = "Qwen2.5-14B-Instruct"
    llm_api_key: str = "EMPTY"
    llm_timeout: int = 120
    rerank_enabled: bool = True
    rerank_url: str = "http://localhost:8082/rerank"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_n: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieve_top_k: int = 20
    meta_db_path: str = "/data/meta.db"
    upload_dir: str = "/data/uploads"
    @property
    def ip_whitelist(self) -> List[str]:
        return [x.strip() for x in self.allowed_ips.split(",") if x.strip()]
    @property
    def api_key_set(self) -> set[str]:
        return {x.strip() for x in self.api_keys.split(",") if x.strip()}
@lru_cache
def get_settings() -> Settings:
    return Settings()
