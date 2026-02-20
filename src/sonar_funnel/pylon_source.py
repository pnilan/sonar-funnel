from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

from airbyte_agent_pylon import PylonAuthConfig, PylonConnector
from airbyte_agent_pylon._vendored.connector_sdk import RateLimitError

from sonar_funnel.models import PylonIssueBundle

logger = logging.getLogger(__name__)

PROCESS_TIMEOUT = 3600  # 1 hour
BASE_DELAY = 5.0  # seconds
MAX_DELAY = 120.0  # cap backoff at 2 minutes

_process_start: float | None = None


def _elapsed() -> float:
    """Seconds since the process started tracking time."""
    if _process_start is None:
        return 0.0
    return time.monotonic() - _process_start


async def _with_retry(coro_fn, *args, **kwargs):
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


def get_connector() -> PylonConnector:
    """Create a PylonConnector in local execution mode."""
    api_token = os.environ.get("PYLON_API_TOKEN")
    if not api_token:
        raise SystemExit("Error: PYLON_API_TOKEN environment variable must be set.")

    logger.info("Creating Pylon connector (local mode)")
    return PylonConnector(auth_config=PylonAuthConfig(api_token=api_token))


def _strip_html(html: str) -> str:
    """Rough HTML-to-text conversion for message bodies."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


async def _fetch_messages(connector: PylonConnector, issue_id: str) -> str:
    """Fetch all messages for an issue and return concatenated plain text."""
    parts: list[str] = []
    cursor = None

    while True:
        kwargs: dict = {"id": issue_id}
        if cursor:
            kwargs["cursor"] = cursor

        result = await _with_retry(connector.messages.list, **kwargs)

        for msg in result.data:
            body = getattr(msg, "message_html", None) or ""
            author_obj = getattr(msg, "author", None)
            author = "Unknown"
            if author_obj:
                author = (
                    getattr(author_obj, "name", None)
                    or getattr(author_obj, "email", None)
                    or "Unknown"
                )
            text = _strip_html(body) if body else ""
            if text:
                parts.append(f"{author}: {text}")

        if not result.meta.has_next_page:
            break
        cursor = result.meta.next_cursor

    return "\n\n".join(parts)


async def fetch_recent_issues(
    connector: PylonConnector,
    days_back: int = 7,
) -> list[PylonIssueBundle]:
    """Fetch recent Pylon issues with their messages, bundled for analysis."""
    global _process_start
    _process_start = time.monotonic()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)

    start_time = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Paginate through all issues in the time window
    issues_raw = []
    cursor = None

    while True:
        kwargs: dict = {"start_time": start_time, "end_time": end_time}
        if cursor:
            kwargs["cursor"] = cursor

        logger.info("issues.list: %s", kwargs)
        result = await _with_retry(connector.issues.list, **kwargs)
        logger.info(
            "issues.list: got %d issue(s), has_next_page=%s",
            len(result.data),
            result.meta.has_next_page,
        )

        issues_raw.extend(result.data)

        if not result.meta.has_next_page:
            break
        cursor = result.meta.next_cursor

    logger.info("Fetching messages for %d issue(s)", len(issues_raw))

    bundles: list[PylonIssueBundle] = []
    for issue in issues_raw:
        issue_id = issue.id
        message_text = await _fetch_messages(connector, issue_id)

        # Extract tag names
        tags: list[str] = []
        raw_tags = getattr(issue, "tags", None) or []
        for tag in raw_tags:
            name = tag.get("name") if isinstance(tag, dict) else getattr(tag, "name", None)
            if name:
                tags.append(name)

        bundles.append(
            PylonIssueBundle(
                issue_id=issue_id,
                issue_number=getattr(issue, "number", None),
                title=getattr(issue, "title", "") or "",
                state=getattr(issue, "state", None),
                created_at=getattr(issue, "created_at", None),
                tags=tags,
                message_text=message_text,
            )
        )

    return bundles
