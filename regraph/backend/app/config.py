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
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-sonnet")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
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
    
    # Feature Flags
    ENABLE_SEMANTIC_SEARCH: bool = os.getenv("ENABLE_SEMANTIC_SEARCH", "true").lower() == "true"
    ENABLE_GRAPH_VISUALIZATION: bool = os.getenv("ENABLE_GRAPH_VISUALIZATION", "true").lower() == "true"
    ENABLE_IMPACT_ANALYSIS: bool = os.getenv("ENABLE_IMPACT_ANALYSIS", "true").lower() == "true"


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()
