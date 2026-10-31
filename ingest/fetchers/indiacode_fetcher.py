"""
indiacode_fetcher.py — Polite, robots-aware fetcher for India Code.

India Code (https://www.indiacode.nic.in) is an official NIC/Ministry of Law
portal publishing Central Acts and Amendments.

TERMS CHECK (as of 2024):
- India Code is published by the Government of India for public use.
- No robots.txt disallows crawlers on the Acts listing pages as of last check.
- We identify ourselves with a clear User-Agent per the spec.
- We rate-limit to 10 requests/minute to be a polite consumer.

IMPORTANT: This fetcher checks robots.txt on every new domain call.
If access is blocked, it raises RobotsDisallowedError with manual-download
instructions.  Never bypass that error silently.

Licence note recorded per ingested Act:
  India Code content is Crown Copyright / Government of India copyright.
  It is made available for public access and reference.  It is NOT licensed
  under an open data licence that permits redistribution.  We store the
  parsed text solely for research benchmarking in a non-commercial academic
  project.  If your institution's policy requires a more permissive licence,
  use only Acts that the government has explicitly released as open data.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

from backend.app.config import settings
from backend.app import audit as audit_mod
from .robots_checker import check_allowed, polite_delay, RobotsDisallowedError

INDIA_CODE_BASE = "https://www.indiacode.nic.in"
ACTS_API = f"{INDIA_CODE_BASE}/handle/123456789/1362/simple-search"

LICENCE_NOTE = (
    "Crown Copyright / Government of India. Published on indiacode.nic.in for "
    "public access. Stored here for non-commercial academic research benchmarking only."
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _save_raw(content: bytes, url: str) -> tuple[Path, str]:
    """Save raw bytes to data/raw/ named by SHA-256.  Return (path, sha256)."""
    raw_dir: Path = settings.data_raw_dir
    sha = hashlib.sha256(content).hexdigest()
    dest = raw_dir / f"{sha}.html"
    if not dest.exists():
        dest.write_bytes(content)
    return dest, sha


def fetch_act_html(act_url: str) -> tuple[str, str, str]:
    """
    Fetch a single Act page from India Code.

    Returns
    -------
    (html_text, sha256, local_path_str)
    """
    check_allowed(act_url)  # raises RobotsDisallowedError if blocked

    audit_mod.log(
        action="fetch_act_html",
        detail=f"Fetching Act page: {act_url}",
        source_url=act_url,
    )

    with httpx.Client(
        timeout=settings.fetcher_timeout_seconds,
        headers={
            "User-Agent": settings.fetcher_user_agent,
            "Accept": "text/html,application/xhtml+xml",
        },
        follow_redirects=True,
    ) as client:
        try:
            response = client.get(act_url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            audit_mod.log_error(
                action="fetch_act_html",
                detail=f"HTTP {exc.response.status_code} for {act_url}",
                exc=exc,
                source_url=act_url,
            )
            raise

    path, sha256 = _save_raw(response.content, act_url)
    audit_mod.log(
        action="fetch_act_html_saved",
        detail=f"Saved raw file: {path} (sha256={sha256[:12]}…)",
        source_url=act_url,
    )

    polite_delay(requests_per_minute=10)
    return response.text, sha256, str(path)


def iter_act_urls_from_search(
    query: str = "Tamil Nadu",
    max_results: int = 50,
) -> Iterator[dict]:
    """
    Iterate over Act metadata dicts from India Code search results.

    Each dict contains: title, url, jurisdiction_hint.
    This function only reads the listing page; it does NOT fetch each Act.
    """
    search_url = f"{INDIA_CODE_BASE}/simple-search?query={query}&rpp={max_results}"

    try:
        check_allowed(search_url)
    except RobotsDisallowedError:
        audit_mod.log_error(
            action="fetch_search_robots_blocked",
            detail=f"Robots.txt blocked search URL: {search_url}",
            source_url=search_url,
        )
        return

    with httpx.Client(
        timeout=settings.fetcher_timeout_seconds,
        headers={"User-Agent": settings.fetcher_user_agent},
        follow_redirects=True,
    ) as client:
        try:
            resp = client.get(search_url)
            resp.raise_for_status()
        except Exception as exc:
            audit_mod.log_error(
                action="fetch_search_page",
                detail=f"Failed to fetch search page: {exc}",
                exc=exc,
                source_url=search_url,
            )
            return

    soup = BeautifulSoup(resp.text, "lxml")

    # India Code search results typically appear in <li> or <div class="artifact-title">
    for link in soup.select("a[href*='/handle/']"):
        href = link.get("href", "")
        if not href:
            continue
        full_url = href if href.startswith("http") else f"{INDIA_CODE_BASE}{href}"
        title = link.get_text(strip=True)
        if not title:
            continue
        yield {
            "title": title,
            "url": full_url,
            "source": "indiacode.nic.in",
            "licence": LICENCE_NOTE,
        }
        time.sleep(0.2)  # tiny delay between URL yields
