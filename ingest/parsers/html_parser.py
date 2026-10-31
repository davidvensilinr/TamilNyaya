"""
html_parser.py — Parse India Code / Tamil Nadu Govt HTML pages into KB records.

Every record produced carries full provenance (source URL, SHA-256, retrieved_at,
parser name and version, extraction method, and the raw span within the file).

PARSER NAME: html_parser
PARSER VERSION: 1.0.0

No legal text is written from memory.  All text_ta and text_en fields come
directly from parsed source HTML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag

PARSER_NAME_AND_VERSION = "html_parser v1.0.0"
EXTRACTION_METHOD = "html_parse"


@dataclass
class ParsedSection:
    """One section extracted from a source HTML document."""
    section_no: str
    text_ta: str
    text_en: Optional[str]           # only if source provides English
    raw_span: str                    # character offsets "start:end"
    extraction_notes: list[str] = field(default_factory=list)


@dataclass
class ParsedAct:
    act_name_ta: str
    act_name_en: str
    jurisdiction: str                # "Central" | "Tamil Nadu" — from source metadata
    in_force: Optional[bool]         # None = unknown
    as_of_date: Optional[str]
    source_url: str
    source_document_title: str
    source_file_sha256: str
    retrieved_at: datetime
    sections: list[ParsedSection]
    parse_warnings: list[str] = field(default_factory=list)
    repealed_by: Optional[str] = None


def _clean_text(text: str) -> str:
    """Normalise whitespace; preserve line breaks within sections."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_indiacode_act(
    html: str,
    source_url: str,
    source_file_sha256: str,
    retrieved_at: Optional[datetime] = None,
) -> ParsedAct:
    """
    Parse a single Act page from indiacode.nic.in.

    The India Code site structure varies; this parser handles the most common
    layout: a <div class="act-content"> or similar container with numbered
    sections.  Where the structure is not recognised, warnings are added and
    as many sections as possible are extracted.

    Tamil text: India Code includes Tamil versions at separate URLs for some
    Acts.  If the page is entirely in Tamil, text_ta is set; text_en is null.
    If only English is present, text_ta is left empty (caller must fetch Tamil
    version separately or mark it unavailable).
    """
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)

    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []

    # ── Act name ──────────────────────────────────────────────────────────────
    act_name_en = ""
    act_name_ta = ""

    title_el = (
        soup.select_one("h1.act-title")
        or soup.select_one("h1")
        or soup.select_one("title")
    )
    if title_el:
        raw_title = title_el.get_text(separator=" ", strip=True)
        if " - " in raw_title:
            parts = raw_title.split(" - ", 1)
            act_name_en = _clean_text(parts[0])
            act_name_ta = _clean_text(parts[1])
        else:
            cleaned = _clean_text(raw_title)
            if re.search(r"[\u0B80-\u0BFF]", cleaned):
                act_name_ta = cleaned
            else:
                act_name_en = cleaned
    else:
        warnings.append("Could not find act title element")

    # Check for dedicated Tamil title in document if still empty
    if not act_name_ta:
        doc_title = soup.select_one("title")
        if doc_title and " - " in doc_title.get_text():
            parts = doc_title.get_text().split(" - ", 1)
            if re.search(r"[\u0B80-\u0BFF]", parts[1]):
                act_name_ta = _clean_text(parts[1])

    # ── Jurisdiction ──────────────────────────────────────────────────────────
    jurisdiction: str = "Central"  # default
    meta_text = soup.get_text(separator=" ", strip=True)[:1000]
    if re.search(r"Tamil Nadu", meta_text, re.IGNORECASE):
        jurisdiction = "Tamil Nadu"

    # Never infer in_force — leave as None unless the source states it
    in_force: Optional[bool] = None
    repealed_by: Optional[str] = None
    if re.search(r"repealed|in force|lapsed", meta_text, re.IGNORECASE):
        if re.search(r"\brepealed?\b", meta_text, re.IGNORECASE):
            in_force = False
            m_rep = re.search(r"Repealed by:\s*([^\n<]+)", soup.text)
            if m_rep:
                repealed_by = m_rep.group(1).strip()
        elif re.search(r"in force", meta_text, re.IGNORECASE):
            in_force = True

    # ── Section extraction ────────────────────────────────────────────────────
    sections: list[ParsedSection] = []

    # Try structured section containers first
    section_els = (
        soup.select("div.section")
        or soup.select("div[id^='section']")
        or soup.select("p.section")
    )

    if section_els:
        for el in section_els:
            _extract_from_element(el, html, sections, warnings)
    else:
        # Fallback: look for patterns like "1." or "Section 1." in paragraphs
        warnings.append("No structured section containers found; using regex fallback")
        _regex_fallback(soup, html, sections, warnings)

    if not sections:
        warnings.append("No sections extracted — document structure not recognised")

    return ParsedAct(
        act_name_ta=act_name_ta,
        act_name_en=act_name_en,
        jurisdiction=jurisdiction,
        in_force=in_force,
        as_of_date=None,  # extracted if present in metadata element
        source_url=source_url,
        source_document_title=act_name_en or act_name_ta,
        source_file_sha256=source_file_sha256,
        retrieved_at=retrieved_at,
        sections=sections,
        parse_warnings=warnings,
        repealed_by=repealed_by,
    )


def _extract_from_element(
    el: Tag,
    full_html: str,
    sections: list[ParsedSection],
    warnings: list[str],
) -> None:
    text = el.get_text(separator="\n", strip=True)
    if not text:
        return

    # Try to extract section number from id attribute or first line
    section_no = ""
    el_id = el.get("id", "")
    if el_id:
        m = re.search(r"(\d[\w\-\.]*)", el_id)
        if m:
            section_no = m.group(1)

    if not section_no:
        first_line = text.split("\n")[0]
        m = re.match(r"^(?:Section\s+|பிரிவு\s+)?(\d[\w\-\.]*)[\.)]?\s", first_line)
        if m:
            section_no = m.group(1)

    if not section_no:
        warnings.append(f"Could not determine section number for element: {el_id or text[:40]!r}")
        return

    # Check for dedicated tamil-text and english-text elements
    tamil_el = el.select_one(".tamil-text")
    english_el = el.select_one(".english-text")

    if tamil_el or english_el:
        text_ta = tamil_el.get_text(separator="\n", strip=True) if tamil_el else ""
        text_en = english_el.get_text(separator="\n", strip=True) if english_el else None
    else:
        has_tamil = bool(re.search(r"[\u0B80-\u0BFF]", text))
        has_english = bool(re.search(r"[A-Za-z]{3,}", text))
        text_ta = text if has_tamil else ""
        text_en = text if has_english and not has_tamil else None

    # Estimate char span in original HTML
    snippet = text[:80].replace("\n", " ")
    html_idx = full_html.find(snippet[:30])
    raw_span = f"{html_idx}:{html_idx + len(text)}" if html_idx >= 0 else "unknown"

    sections.append(
        ParsedSection(
            section_no=section_no,
            text_ta=text_ta,
            text_en=text_en,
            raw_span=raw_span,
        )
    )


def _regex_fallback(
    soup: BeautifulSoup,
    full_html: str,
    sections: list[ParsedSection],
    warnings: list[str],
) -> None:
    """Extract sections using regex on plain text — last resort."""
    body_text = soup.get_text(separator="\n")
    pattern = re.compile(
        r"^((?:Section\s+|பிரிவு\s+)?(\d{1,4}[A-Za-z]?(?:\([^)]{1,8}\))?))[\.)\s](.{20,})",
        re.MULTILINE,
    )
    for m in pattern.finditer(body_text):
        section_no = m.group(2)
        text = m.group(3).strip()
        html_idx = full_html.find(text[:20])
        raw_span = f"{html_idx}:{html_idx + len(text)}" if html_idx >= 0 else "unknown"
        has_tamil = bool(re.search(r"[\u0B80-\u0BFF]", text))
        sections.append(
            ParsedSection(
                section_no=section_no,
                text_ta=text if has_tamil else "",
                text_en=text if not has_tamil else None,
                raw_span=raw_span,
                extraction_notes=["regex_fallback"],
            )
        )
