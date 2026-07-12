"""
LLM Client Factory - Unified interface for both Anthropic and OpenRouter APIs
Automatically routes to the configured provider.
"""
import logging
from typing import Optional, Any
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client that supports both Anthropic and OpenRouter.
    Automatically routes API calls to the configured provider.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize the appropriate LLM client based on configuration."""
        provider = self.settings.LLM_PROVIDER.lower()
        
        if provider == "openrouter":
            self._init_openrouter()
        elif provider == "anthropic":
            self._init_anthropic()
        else:
            logger.warning(f"Unknown LLM_PROVIDER: {provider}, defaulting to OpenRouter")
            self._init_openrouter()
    
    def _init_anthropic(self):
        """Initialize Anthropic client."""
        try:
            from anthropic import Anthropic
            
            if not self.settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not set in .env file")
            
            self._client = Anthropic(api_key=self.settings.ANTHROPIC_API_KEY)
            self.provider = "anthropic"
            logger.info(f"✓ Initialized Anthropic client with model: {self.settings.ANTHROPIC_MODEL}")
        except ImportError:
            logger.error("Anthropic library not installed. Install with: pip install anthropic")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            raise
    
    def _init_openrouter(self):
        """Initialize OpenRouter client via OpenAI SDK."""
        try:
            from openai import OpenAI
            
            if not self.settings.OPENROUTER_API_KEY:
                raise ValueError("OPENROUTER_API_KEY not set in .env file")
            
            self._client = OpenAI(
                api_key=self.settings.OPENROUTER_API_KEY,
                base_url=self.settings.OPENROUTER_BASE_URL
            )
            self.provider = "openrouter"
            logger.info(f"✓ Initialized OpenRouter client with model: {self.settings.OPENROUTER_MODEL}")
        except ImportError:
            logger.error("OpenAI library not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {e}")
            raise
    
    def create_message(self, messages: list, **kwargs) -> Any:
        """
        Create a message using the configured LLM provider.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            Response from the LLM
        """
        if self.provider == "anthropic":
            return self._call_anthropic(messages, **kwargs)
        elif self.provider == "openrouter":
            return self._call_openrouter(messages, **kwargs)
    
    def _call_anthropic(self, messages: list, **kwargs) -> Any:
        """Call Anthropic API with Anthropic SDK."""
        try:
            # Extract Anthropic-specific parameters
            params = {
                "model": self.settings.ANTHROPIC_MODEL,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "timeout": self.settings.LLM_TIMEOUT,
            }
            
            # Optional parameters
            if "temperature" in kwargs:
                params["temperature"] = kwargs["temperature"]
            if "system" in kwargs:
                params["system"] = kwargs["system"]
            
            response = self._client.messages.create(**params)
            return response
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise
    
    def _call_openrouter(self, messages: list, **kwargs) -> Any:
        """Call OpenRouter API via OpenAI SDK."""
        try:
            # Extract OpenAI-compatible parameters
            params = {
                "model": self.settings.OPENROUTER_MODEL,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "timeout": self.settings.LLM_TIMEOUT,
            }
            
            # Optional parameters
            if "temperature" in kwargs:
                params["temperature"] = kwargs["temperature"]
            if "system" in kwargs:
                messages_copy = messages.copy()
                messages_copy.insert(0, {"role": "system", "content": kwargs["system"]})
                params["messages"] = messages_copy
            
            response = self._client.chat.completions.create(**params)
            return response
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {e}")
            raise
    
    def get_client(self) -> Any:
        """Get the underlying client object."""
        return self._client
    
    def get_provider_info(self) -> dict:
        """Get information about the current provider and model."""
        return {
            "provider": self.provider,
            "model": self.settings.LLM_MODEL,
            "api_key_configured": bool(self.settings.LLM_API_KEY),
            "timeout": self.settings.LLM_TIMEOUT,
        }


# Global client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Get or create the global LLM client instance.
    
    Returns:
        LLMClient instance
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
