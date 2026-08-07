"""
LLM health / preflight endpoint.

Turns a silent 30-minute failure into a one-second check: it makes one tiny
completion call against the configured model and reports exactly why it failed.
"""
import logging
import time

from fastapi import APIRouter

from app.anthropic_adapter import create_anthropic_compatible_client
from app.config import get_settings
from app.llm_errors import classify

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/llm")
async def llm_health():
    """Check that the configured LLM model is actually reachable."""
    settings = get_settings()
    result = {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "ok": False,
        "kind": None,
        "status_code": None,
        "detail": None,
        "latency_seconds": None,
    }

    if settings.LLM_PROVIDER == "openrouter":
        from app.anthropic_adapter import KeyRotator
        result["keys"] = KeyRotator.get().status()

    if not settings.LLM_API_KEY:
        result["kind"] = "fatal"
        result["detail"] = (
            f"No API key set for provider '{settings.LLM_PROVIDER}'. "
            "Set OPENROUTER_API_KEY (or ANTHROPIC_API_KEY) in .env."
        )
        return result

    started = time.perf_counter()
    try:
        client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
        client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=5,
            messages=[{"role": "user", "content": "ping"}],
        )
        result["ok"] = True
        result["detail"] = "Model reachable."
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        err = classify(exc)
        result["kind"] = err.kind
        result["status_code"] = err.status_code
        result["detail"] = str(err)
        if err.status_code == 429:
            result["detail"] += (
                "  (This is a quota limit, not a code bug — the free tier allows "
                "50 requests/day PER ACCOUNT. Extra keys from the same OpenRouter "
                "account share that limit and will not help; use a key from a "
                "different account, add credit, or run with EXTRACTION_MODE=ml "
                "to keep working without the LLM.)"
            )
        logger.warning("LLM health check failed: %s", err)

    result["latency_seconds"] = round(time.perf_counter() - started, 3)
    return result
