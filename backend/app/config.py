"""
Configuration module for RegGraph backend.
Supports both OpenRouter and Direct Claude API.
"""
import os
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()


class Settings:
    """Application settings."""
    # API Configuration
    API_TITLE: str = "RegGraph API"
    API_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("ENVIRONMENT", "development") == "development"
    
    # LLM Provider Configuration
    # Options: "openrouter" or "anthropic"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")
    
    # OpenRouter Configuration
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    # Additional keys used only when the primary is exhausted. Accepts a
    # comma-separated list, and OPENROUTER_API_KEY itself may also be a list.
    # The free tier is 50 requests/day per key, which one 400-page circular can
    # burn through, so failover is the difference between a demo and a 429.
    OPENROUTER_API_KEY_BACKUP: str = os.getenv("OPENROUTER_API_KEY_BACKUP", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-sonnet")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    @property
    def OPENROUTER_API_KEYS(self) -> list:
        """Primary key(s) first, then backups, de-duplicated, blanks dropped."""
        raw = f"{self.OPENROUTER_API_KEY},{self.OPENROUTER_API_KEY_BACKUP}"
        keys, seen = [], set()
        for k in (part.strip() for part in raw.split(",")):
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
        return keys
    
    # Direct Anthropic Configuration
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
    
    # Get the appropriate model based on provider
    @property
    def LLM_MODEL(self) -> str:
        if self.LLM_PROVIDER == "openrouter":
            return self.OPENROUTER_MODEL
        else:
            return self.ANTHROPIC_MODEL
    
    # Get the appropriate API key based on provider
    @property
    def LLM_API_KEY(self) -> str:
        if self.LLM_PROVIDER == "openrouter":
            return self.OPENROUTER_API_KEY
        else:
            return self.ANTHROPIC_API_KEY
    
    # Paths
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index")
    GRAPH_DB_PATH: str = os.getenv("GRAPH_DB_PATH", "./data/obligation_graph.pkl")
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    CACHE_DIR: str = os.getenv("CACHE_DIR", "./cache")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Timeouts
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "120"))
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "60"))

    # LLM reliability / cost controls
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    # How many chunks to extract concurrently. Kept low so we don't amplify 429s.
    LLM_CONCURRENCY: int = int(os.getenv("LLM_CONCURRENCY", "4"))
    # Characters per extraction chunk. Larger = fewer LLM calls per circular.
    EXTRACTION_CHUNK_SIZE: int = int(os.getenv("EXTRACTION_CHUNK_SIZE", "6000"))
    # Output budget per chunk. Must be large enough for the whole JSON array —
    # a truncated array used to make the model's entire answer unparseable.
    EXTRACTION_MAX_TOKENS: int = int(os.getenv("EXTRACTION_MAX_TOKENS", "4000"))

    # ── Local model (trained on the synthetic corpus) ────────────────────────
    # hybrid : local model always extracts; the LLM enriches when reachable (default)
    # ml     : local model only — fully offline, no API key needed
    # llm    : LLM only (original behaviour; fails when the provider is down)
    EXTRACTION_MODE: str = os.getenv("EXTRACTION_MODE", "hybrid").lower()
    MODEL_DIR: str = os.getenv("MODEL_DIR", "./data/models")
    # Probability above which a sentence is treated as an obligation. Lower =
    # higher recall and more noise; 0.55 was tuned against the real 38-page circular.
    ML_OBLIGATION_THRESHOLD: float = float(os.getenv("ML_OBLIGATION_THRESHOLD", "0.55"))
    # One extra LLM call per circular for the narrative insight layer.
    ENABLE_AI_INSIGHTS: bool = os.getenv("ENABLE_AI_INSIGHTS", "true").lower() == "true"

    # Feature Flags
    ENABLE_SEMANTIC_SEARCH: bool = os.getenv("ENABLE_SEMANTIC_SEARCH", "true").lower() == "true"
    ENABLE_GRAPH_VISUALIZATION: bool = os.getenv("ENABLE_GRAPH_VISUALIZATION", "true").lower() == "true"
    ENABLE_IMPACT_ANALYSIS: bool = os.getenv("ENABLE_IMPACT_ANALYSIS", "true").lower() == "true"
    # Each LLM-generated SOP costs one extra call per obligation. Off by default.
    ENABLE_LLM_SOP: bool = os.getenv("ENABLE_LLM_SOP", "false").lower() == "true"

    # ── Notification settings ────────────────────────────────────────────────
    # Email (SMTP)
    NOTIFY_EMAIL_TO: str   = os.getenv("NOTIFY_EMAIL_TO", "")          # recipient
    NOTIFY_EMAIL_FROM: str = os.getenv("NOTIFY_EMAIL_FROM", "")        # sender address
    SMTP_HOST: str         = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int         = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str         = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str     = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool     = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Slack / generic webhook
    NOTIFY_WEBHOOK_URL: str = os.getenv("NOTIFY_WEBHOOK_URL", "")      # Slack webhook or any HTTP endpoint

    # Alert thresholds
    NOTIFY_DUE_SOON_DAYS: int = int(os.getenv("NOTIFY_DUE_SOON_DAYS", "7"))   # alert if due within N days
    NOTIFY_MIN_SEVERITY: str  = os.getenv("NOTIFY_MIN_SEVERITY", "medium")    # low | medium | high

    @property
    def notifications_enabled(self) -> bool:
        """True if at least one notification channel is configured."""
        return bool(self.NOTIFY_EMAIL_TO or self.NOTIFY_WEBHOOK_URL)


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()
