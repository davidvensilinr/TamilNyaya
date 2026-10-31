"""
robots_checker.py — Robots.txt compliance checker.

Before fetching any page from a domain, we check robots.txt and record
the result in the audit log.  If automated access is disallowed, we stop
and tell the operator which documents to download manually.

This is required by the spec: "Check robots.txt and the terms of use of
every website before fetching."
"""

from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from backend.app.config import settings
from backend.app import audit as audit_mod

# Cache parsed robots.txt per domain (for the lifetime of the process)
_robots_cache: dict[str, RobotFileParser] = {}


def _get_robots(domain_url: str) -> RobotFileParser:
    """Fetch and parse robots.txt for the given domain URL."""
    parsed = urlparse(domain_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    if base in _robots_cache:
        return _robots_cache[base]

    robots_url = urljoin(base, "/robots.txt")
    rp = RobotFileParser(robots_url)

    try:
        with httpx.Client(
            timeout=settings.fetcher_timeout_seconds,
            headers={"User-Agent": settings.fetcher_user_agent},
        ) as client:
            response = client.get(robots_url)
            if response.status_code == 200:
                rp.parse(response.text.splitlines())
            else:
                # No robots.txt or inaccessible — treat as permissive
                rp.allow_all = True

        audit_mod.log(
            action="fetch_robots",
            detail=f"Fetched robots.txt from {robots_url} (status={response.status_code})",
            source_url=robots_url,
        )
    except Exception as exc:
        # Network failure reading robots.txt — err on the side of caution: disallow
        audit_mod.log_error(
            action="fetch_robots",
            detail=f"Could not fetch robots.txt from {robots_url}; treating as disallowed",
            exc=exc,
            source_url=robots_url,
        )
        rp.disallow_all = True

    _robots_cache[base] = rp
    return rp


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt prohibits automated access to a URL."""


def check_allowed(url: str) -> None:
    """
    Check whether the User-Agent is allowed to fetch `url`.

    Raises RobotsDisallowedError if not allowed, with a message explaining
    which URL to download manually.
    """
    rp = _get_robots(url)
    if not rp.can_fetch(settings.fetcher_user_agent, url):
        raise RobotsDisallowedError(
            f"robots.txt disallows automated access to: {url}\n"
            f"User-Agent used: {settings.fetcher_user_agent}\n\n"
            "ACTION REQUIRED: Download this document manually and place it in:\n"
            "  ingest/manual_drop/\n"
            "The ingestion pipeline will pick it up from there."
        )


def polite_delay(requests_per_minute: int = 10) -> None:
    """Sleep long enough to respect a simple rate limit."""
    time.sleep(60.0 / requests_per_minute)
