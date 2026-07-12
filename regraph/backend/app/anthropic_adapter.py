"""
Anthropic API Adapter - Makes OpenRouter calls look like Anthropic calls
Allows existing code to work with both providers without modification.
"""
import logging
from typing import Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class AnthropicAdapter:
    """
    Adapter that wraps OpenAI/OpenRouter client to provide Anthropic-compatible interface.
    Allows using OpenRouter with code written for Anthropic SDK.
    """
    
    def __init__(self, openai_client: Any):
        self.client = openai_client
        self.settings = get_settings()
    
    def __getattr__(self, name):
        """Pass through attributes to the underlying client."""
        return getattr(self.client, name)
    
    @property
    def messages(self):
        """Provide Anthropic-style messages interface."""
        return MessageAPI(self.client, self.settings)


class MessageAPI:
    """Provides Anthropic-style messages.create() interface for OpenAI client."""
    
    def __init__(self, client: Any, settings: Any):
        self.client = client
        self.settings = settings
    
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
        
        try:
            # Call OpenAI/OpenRouter API
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
            
            # Convert to Anthropic response format
            return AnthropicMessage(response)
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {e}")
            raise


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
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY not set")
        
        openai_client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL
        )
        return AnthropicAdapter(openai_client)
    
    else:
        raise ValueError(f"Unknown provider: {provider}")
