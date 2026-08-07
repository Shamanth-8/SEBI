"""
Anthropic API Adapter - Makes OpenRouter calls look like Anthropic calls
Allows existing code to work with both providers without modification.
"""
import logging
import threading
from typing import Any, List, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class KeyRotator:
    """
    Holds the OpenRouter keys and moves to the next one when the current is spent.

    The free tier allows 50 requests/day per key, and a single large circular can
    exhaust that mid-run. Rather than failing the run, the adapter rotates to the
    next configured key. State is process-wide and lock-protected because
    extraction fans out across a thread pool — without that, every worker thread
    would independently rediscover that the same key is dead.
    """

    _instance: Optional["KeyRotator"] = None
    _class_lock = threading.Lock()

    def __init__(self, keys: List[str]):
        self._keys = list(keys)
        self._index = 0
        self._exhausted: set = set()
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> "KeyRotator":
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls(get_settings().OPENROUTER_API_KEYS)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop cached state — used by tests and after changing configuration."""
        with cls._class_lock:
            cls._instance = None

    @property
    def keys(self) -> List[str]:
        return list(self._keys)

    def current(self) -> Optional[str]:
        with self._lock:
            return self._keys[self._index] if self._index < len(self._keys) else None

    def mark_exhausted(self, key: str) -> Optional[str]:
        """
        Retire `key` and return the next usable one, or None when all are spent.
        """
        with self._lock:
            if key in self._exhausted:
                # Another thread already rotated past this key.
                return self._keys[self._index] if self._index < len(self._keys) else None
            self._exhausted.add(key)
            masked = f"{key[:12]}…{key[-4:]}" if len(key) > 20 else "key"
            while self._index < len(self._keys) and self._keys[self._index] in self._exhausted:
                self._index += 1
            if self._index < len(self._keys):
                nxt = self._keys[self._index]
                logger.warning(
                    f"OpenRouter key {masked} is exhausted — switching to key "
                    f"{self._index + 1} of {len(self._keys)}"
                )
                return nxt
            logger.error(
                f"OpenRouter key {masked} is exhausted and no backup keys remain "
                f"({len(self._keys)} configured). Set OPENROUTER_API_KEY_BACKUP, "
                f"or run with EXTRACTION_MODE=ml to continue without the LLM."
            )
            return None

    def status(self) -> dict:
        with self._lock:
            return {
                "keys_configured": len(self._keys),
                "active_key_index": self._index if self._index < len(self._keys) else None,
                "keys_exhausted": len(self._exhausted),
                "keys_remaining": max(0, len(self._keys) - self._index),
            }


def _is_key_exhausted_error(exc: Exception) -> bool:
    """True for the failures that another key could plausibly survive."""
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None)
    if status in (401, 402, 429):
        return True
    text = str(exc).lower()
    return any(s in text for s in (
        "rate limit", "quota", "insufficient credit", "free-models-per-day",
        "invalid api key", "no auth credentials",
    ))


class AnthropicAdapter:
    """
    Adapter that wraps OpenAI/OpenRouter client to provide Anthropic-compatible interface.
    Allows using OpenRouter with code written for Anthropic SDK.
    """
    
    def __init__(self, openai_client: Any, rotate: bool = True):
        self.client = openai_client
        self.settings = get_settings()
        self._rotate = rotate
    
    def __getattr__(self, name):
        """Pass through attributes to the underlying client."""
        return getattr(self.client, name)
    
    @property
    def messages(self):
        """Provide Anthropic-style messages interface."""
        return MessageAPI(self.client, self.settings, rotate=self._rotate)


class MessageAPI:
    """Provides Anthropic-style messages.create() interface for OpenAI client."""

    def __init__(self, client: Any, settings: Any, rotate: bool = True):
        self.client = client
        self.settings = settings
        self._rotate = rotate
    
    def create(self, **kwargs) -> "AnthropicMessage":
        """
        Create a message using Anthropic-compatible parameters.
        Translates to OpenAI/OpenRouter format internally.
        
        Args:
            model: Model name (will use OPENROUTER_MODEL if not provided)
            messages: List of message dicts
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system: System prompt (Anthropic extension)
            
        Returns:
            AnthropicMessage object with Anthropic-compatible response format
        """
        # Extract Anthropic-compatible parameters
        model = kwargs.get("model", self.settings.OPENROUTER_MODEL)
        messages = kwargs.get("messages", [])
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 1.0)
        system = kwargs.get("system")
        timeout = kwargs.get("timeout", self.settings.LLM_TIMEOUT)
        
        # Handle system prompt (Anthropic uses separate system parameter)
        if system:
            messages = [{"role": "system", "content": system}] + messages
        
        # Try the active key; on a quota/auth failure rotate to the next configured
        # key and retry, so one exhausted free-tier key does not end the run.
        rotator = KeyRotator.get() if self._rotate else None
        attempts = len(rotator.keys) if rotator else 1

        last_exc: Optional[Exception] = None
        for _ in range(max(attempts, 1)):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
                return AnthropicMessage(response)
            except Exception as e:
                last_exc = e
                if not (rotator and _is_key_exhausted_error(e)):
                    logger.error(f"OpenRouter API call failed: {e}")
                    raise
                spent = getattr(self.client, "api_key", None)
                next_key = rotator.mark_exhausted(spent) if spent else None
                if not next_key:
                    logger.error(f"OpenRouter API call failed, no keys left: {e}")
                    raise
                self._swap_key(next_key)

        raise last_exc if last_exc else RuntimeError("OpenRouter call failed")

    def _swap_key(self, key: str) -> None:
        """Point this client at a different API key, in place."""
        try:
            self.client.api_key = key
        except Exception:            # older SDKs expose it read-only
            from openai import OpenAI
            self.client = OpenAI(api_key=key,
                                 base_url=self.settings.OPENROUTER_BASE_URL)


class AnthropicMessage:
    """
    Wraps OpenAI response to provide Anthropic-compatible interface.
    Maps OpenAI response format to Anthropic response format.
    """
    
    def __init__(self, openai_response: Any):
        self._response = openai_response
    
    @property
    def content(self) -> list:
        """Get content blocks in Anthropic format."""
        # OpenAI returns: response.choices[0].message.content (string)
        # Anthropic returns: response.content (list of content blocks)
        text_content = self._response.choices[0].message.content
        
        return [
            TextBlock(text=text_content)
        ]
    
    @property
    def stop_reason(self) -> str:
        """Get stop reason."""
        finish_reason = self._response.choices[0].finish_reason
        # Map OpenAI finish reasons to Anthropic stop reasons
        mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
        }
        return mapping.get(finish_reason, finish_reason)
    
    @property
    def id(self) -> str:
        """Get message ID."""
        return self._response.id
    
    @property
    def model(self) -> str:
        """Get model name."""
        return self._response.model
    
    @property
    def usage(self) -> "Usage":
        """Get token usage."""
        return Usage(
            input_tokens=self._response.usage.prompt_tokens,
            output_tokens=self._response.usage.completion_tokens
        )
    
    def __repr__(self):
        return f"<AnthropicMessage content_length={len(str(self.content))}>"


class TextBlock:
    """Represents a text content block in Anthropic format."""
    
    def __init__(self, text: str, type: str = "text"):
        self.text = text
        self.type = type
    
    def __repr__(self):
        return f"<TextBlock type={self.type} length={len(self.text)}>"


class Usage:
    """Token usage information in Anthropic format."""
    
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
    
    def __repr__(self):
        return f"<Usage input={self.input_tokens} output={self.output_tokens}>"


def create_anthropic_compatible_client(provider: str, **kwargs) -> Any:
    """
    Create an Anthropic-compatible client for the specified provider.
    
    Args:
        provider: "anthropic" or "openrouter"
        **kwargs: Additional arguments
        
    Returns:
        Anthropic-compatible client object
    """
    settings = get_settings()
    
    if provider.lower() == "anthropic":
        from anthropic import Anthropic
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    elif provider.lower() == "openrouter":
        from openai import OpenAI

        rotator = KeyRotator.get()
        active = rotator.current()
        if not active:
            raise ValueError(
                "No usable OPENROUTER_API_KEY. Set one in .env (optionally several, "
                "comma-separated, or via OPENROUTER_API_KEY_BACKUP), or run with "
                "EXTRACTION_MODE=ml to use the local model only."
            )
        logger.info(
            f"OpenRouter client using key {rotator.status()['active_key_index'] + 1} "
            f"of {len(rotator.keys)}"
        )
        openai_client = OpenAI(api_key=active, base_url=settings.OPENROUTER_BASE_URL)
        return AnthropicAdapter(openai_client)
    
    else:
        raise ValueError(f"Unknown provider: {provider}")
