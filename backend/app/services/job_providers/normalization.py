"""Helpers that turn provider fields into normalised values without inventing data."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.core.config import settings

_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_RE = re.compile(r"</?(?:p|div|br|li|ul|ol|h[1-6]|tr|section)[^>]*>", re.IGNORECASE)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL = re.compile(r"\n{3,}")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([,.;:!?)])")

INDIA_MARKERS = (
    "india", "bengaluru", "bangalore", "mumbai", "pune", "hyderabad", "chennai", "new delhi", "delhi", "gurgaon",
    "gurugram", "noida", "kolkata", "ahmedabad", "jaipur", "kochi", "coimbatore", "indore", "chandigarh",
    "thiruvananthapuram", "mysore", "mysuru", "vadodara", "nagpur", "lucknow", "bhubaneswar", "visakhapatnam",
)

_COUNTRY_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    ("India", INDIA_MARKERS),
    ("United States", ("united states", "usa", "u.s.", "new york", "san francisco", "seattle", "austin", "boston", "chicago")),
    ("United Kingdom", ("united kingdom", " uk", "london", "england")),
    ("Canada", ("canada", "toronto", "vancouver")),
    ("Germany", ("germany", "berlin", "munich")),
    ("Ireland", ("ireland", "dublin")),
    ("Singapore", ("singapore",)),
    ("Australia", ("australia", "sydney", "melbourne")),
    ("Netherlands", ("netherlands", "amsterdam")),
    ("France", ("france", "paris")),
    ("Japan", ("japan", "tokyo")),
]

def html_to_text(raw: Optional[str]) -> str:
    """Convert (possibly entity-escaped) HTML to readable plain text."""
    if not raw:
        return ""
    text = html.unescape(raw)
    if "&lt;" in raw or "&gt;" in raw:  # Greenhouse double-escapes content
        text = html.unescape(text)
    text = _BLOCK_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)  # "<b>Python</b>," → "Python,"
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _MULTI_NL.sub("\n\n", text).strip()


def clean_text(value: Optional[str], limit: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    cleaned = _WS_RE.sub(" ", str(value)).strip()
    if not cleaned:
        return None
    if limit and len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


def parse_datetime(value) -> Optional[datetime]:
    """Parse ISO-8601 strings or epoch milliseconds into aware UTC datetimes."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = value / 1000 if value > 10_000_000_000 else value
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def detect_country(*values: Optional[str]) -> Optional[str]:
    blob = " ".join(v.lower() for v in values if v)
    if not blob.strip():
        return None
    for country, markers in _COUNTRY_MARKERS:
        # Word boundaries so "Indianapolis" is not India.
        if any(re.search(rf"(?<![a-z]){re.escape(marker.strip())}(?![a-z])", blob) for marker in markers):
            return country
    return None


def normalize_work_mode(raw: Optional[str] = None, *, is_remote: Optional[bool] = None, location: Optional[str] = None) -> Optional[str]:
    """Return remote | hybrid | onsite, or None when the provider does not say."""
    value = (raw or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    if value in ("remote", "fullyremote"):
        return "remote"
    if value == "hybrid":
        return "hybrid"
    if value in ("onsite", "inoffice", "office", "inperson"):
        return "onsite"
    if is_remote is True:
        return "remote"
    loc = (location or "").lower()
    if "hybrid" in loc:
        return "hybrid"
    if re.search(r"\bremote\b", loc):
        return "remote"
    return None


_EMPLOYMENT_MAP = {
    "fulltime": "full_time", "permanent": "full_time", "regular": "full_time",
    "parttime": "part_time",
    "contract": "contract", "contractor": "contract", "freelance": "contract", "fixedterm": "contract",
    "intern": "internship", "internship": "internship",
    "temporary": "temporary", "temp": "temporary", "seasonal": "temporary",
}


def normalize_employment_type(raw: Optional[str], title: Optional[str] = None) -> Optional[str]:
    key = re.sub(r"[^a-z]", "", (raw or "").lower())
    if key in _EMPLOYMENT_MAP:
        return _EMPLOYMENT_MAP[key]
    for token, value in _EMPLOYMENT_MAP.items():
        if key and token in key:
            return value
    if title and re.search(r"\b(?:intern|internship)\b", title, re.IGNORECASE):
        return "internship"
    return None


def _keywords() -> list[str]:
    return [k.strip().lower() for k in settings.JOB_SYNC_LOCATION_KEYWORDS.split(",") if k.strip()]


def location_is_relevant(locations: Iterable[Optional[str]], work_mode: Optional[str]) -> bool:
    """Import filter: keep listings located in a configured region (India by default)
    or remote listings open globally. An empty keyword list keeps everything."""
    keywords = _keywords()
    if not keywords:
        return True
    blob = " ".join((loc or "").lower() for loc in locations)
    if any(re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", blob) for k in keywords):
        return True
    if settings.JOB_SYNC_INCLUDE_GLOBAL_REMOTE and work_mode == "remote":
        stripped = blob.replace("remote", "").replace("-", " ").replace(",", " ").replace("(", " ").replace(")", " ").strip()
        # Purely "Remote"/"Worldwide"/"Anywhere"/"APAC" with no other country named.
        if not stripped or all(token in ("worldwide", "anywhere", "global", "apac", "asia", "emea") for token in stripped.split()):
            return True
    return False


def combine_locations(primary: Optional[str], others: Iterable[Optional[str]], limit: int = 160) -> tuple[Optional[str], Optional[str]]:
    """Display location + country for a listing published in several places.

    Locations in the configured import region (India by default) are listed first,
    so a posting whose primary location is "Australia - Remote" but which is also
    open in "Mumbai, India" is shown — and matched — as available in Mumbai.
    """
    seen: list[str] = []
    for loc in [primary, *others]:
        cleaned = clean_text(loc)
        if cleaned and cleaned.lower() not in {s.lower() for s in seen}:
            seen.append(cleaned)
    if not seen:
        return None, None
    keywords = _keywords()
    def _in_region(loc: str) -> bool:
        return any(re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", loc.lower()) for k in keywords)
    ordered = [loc for loc in seen if _in_region(loc)] + [loc for loc in seen if not _in_region(loc)]
    shown: list[str] = []
    for loc in ordered[:3]:
        if len(" / ".join([*shown, loc])) > limit - 12:
            break
        shown.append(loc)
    display = " / ".join(shown)
    if len(ordered) > len(shown):
        display = f"{display} (+{len(ordered) - len(shown)} more)"
    return display[:limit], detect_country(ordered[0])


def parse_salary_number(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return int(round(number))
