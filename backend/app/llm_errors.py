"""
LLM error classification and retry helpers.

The extraction pipeline used to swallow every LLM exception and return an empty
list, so an unreachable model produced a "successful" run with zero obligations.
These helpers make the distinction explicit:

  * fatal      — config is wrong (bad model id, bad key). Retrying cannot help.
  * transient  — rate limited or a server hiccup. Worth retrying with backoff.
"""
import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class LLMError(Exception):
    """Base for LLM failures that must not be silently swallowed."""

    def __init__(self, message: str, *, kind: str, status_code: int | None = None):
        super().__init__(message)
        self.kind = kind                 # "fatal" | "transient" | "unknown"
        self.status_code = status_code


class LLMFatalError(LLMError):
    """Configuration-level failure — retrying will not help."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, kind="fatal", status_code=status_code)


class LLMTransientError(LLMError):
    """Rate limit or transient server error — retry may succeed."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, kind="transient", status_code=status_code)


def _status_of(exc: Exception) -> int | None:
    """Best-effort HTTP status extraction across openai/anthropic SDK shapes."""
    for attr in ("status_code", "http_status"):
        code = getattr(exc, attr, None)
        if isinstance(code, int):
            return code
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    return code if isinstance(code, int) else None


def classify(exc: Exception) -> LLMError:
    """Map a raw SDK exception onto a fatal/transient LLMError."""
    status = _status_of(exc)
    text = str(exc)

    if status in (401, 403):
        return LLMFatalError(
            f"LLM auth rejected (HTTP {status}). Check OPENROUTER_API_KEY. — {text}",
            status,
        )
    if status == 404:
        return LLMFatalError(
            f"Configured model does not exist on the provider (HTTP 404). "
            f"Check OPENROUTER_MODEL. — {text}",
            status,
        )
    if status == 400 and ("not a valid model" in text.lower() or "model" in text.lower() and "invalid" in text.lower()):
        return LLMFatalError(
            f"Provider rejected the model id (HTTP 400). Check OPENROUTER_MODEL. — {text}",
            status,
        )
    if status == 429:
        return LLMTransientError(f"LLM rate limit / quota exceeded (HTTP 429). — {text}", status)
    if status is not None and 500 <= status < 600:
        return LLMTransientError(f"LLM provider server error (HTTP {status}). — {text}", status)

    # No usable status code — fall back to matching the message text.
    low = text.lower()
    if "rate limit" in low or "quota" in low:
        return LLMTransientError(f"LLM rate limit / quota exceeded. — {text}", status)
    if "no endpoints found" in low or "not found" in low:
        return LLMFatalError(f"Configured model is unavailable. — {text}", status)

    err = LLMError(f"LLM call failed: {text}", kind="unknown", status_code=status)
    return err


def call_with_retry(fn: Callable[[], T], *, max_retries: int, label: str = "LLM call") -> T:
    """
    Run fn(), retrying only transient failures with exponential backoff.

    Fatal errors are raised immediately — failing 17 identical times against a
    model that does not exist is pure waste.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 - re-raised as a classified LLMError
            err = classify(exc)
            if isinstance(err, LLMFatalError) or attempt >= max_retries:
                logger.error("%s failed (%s): %s", label, err.kind, err)
                raise err from exc
            delay = 2 ** attempt
            attempt += 1
            logger.warning(
                "%s failed (%s), retry %d/%d in %ds: %s",
                label, err.kind, attempt, max_retries, delay, err,
            )
            time.sleep(delay)
