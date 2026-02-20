from __future__ import annotations

import asyncio
import logging
import time

from airbyte_agent_pylon._vendored.connector_sdk import RateLimitError

logger = logging.getLogger(__name__)

PROCESS_TIMEOUT = 3600  # 1 hour
BASE_DELAY = 5.0  # seconds
MAX_DELAY = 120.0  # cap backoff at 2 minutes

_process_start: float | None = None


def reset_timer() -> None:
    """Start (or restart) the global process timer."""
    global _process_start
    _process_start = time.monotonic()


def _elapsed() -> float:
    """Seconds since the process started tracking time."""
    if _process_start is None:
        return 0.0
    return time.monotonic() - _process_start


async def with_retry(coro_fn, *args, **kwargs):
    """Call an async function with exponential backoff on rate-limit errors.

    Retries indefinitely until the call succeeds or the total process time
    exceeds 1 hour. Uses the Retry-After header when available, otherwise
    falls back to exponential backoff capped at 2 minutes.
    """
    attempt = 0
    while True:
        try:
            return await coro_fn(*args, **kwargs)
        except RateLimitError as exc:
            if _elapsed() >= PROCESS_TIMEOUT:
                raise SystemExit(
                    "Error: process has been running for over 1 hour. Aborting."
                ) from exc
            delay = exc.retry_after if exc.retry_after else min(BASE_DELAY * (2**attempt), MAX_DELAY)
            attempt += 1
            logger.warning(
                "Rate limited (attempt %d, %.0fs elapsed), retrying in %.1fs",
                attempt,
                _elapsed(),
                delay,
            )
            await asyncio.sleep(delay)
