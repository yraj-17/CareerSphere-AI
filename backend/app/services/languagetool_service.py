"""Reusable LanguageTool client for grammar / spelling / style checks."""
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import settings


class LanguageToolError(Exception):
    """Raised when LanguageTool cannot be reached or returns an invalid payload."""


def _check_url() -> str:
    base = (settings.LANGUAGETOOL_URL or "").rstrip("/") + "/"
    if base.rstrip("/").endswith("/v2/check"):
        return base.rstrip("/")
    return urljoin(base, "v2/check")


def _safe_replacements(raw: Any, limit: int = 5) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, str) and item:
            values.append(item)
        elif isinstance(item, dict):
            value = item.get("value")
            if isinstance(value, str) and value:
                values.append(value)
        if len(values) >= limit:
            break
    return values


def apply_top_replacements(text: str, matches: list[dict]) -> str:
    """Apply the first replacement of each non-overlapping match, from the end."""
    result = text
    occupied: list[tuple[int, int]] = []
    ordered = sorted(matches, key=lambda item: int(item.get("offset") or 0), reverse=True)
    for match in ordered:
        offset = int(match.get("offset") or 0)
        length = int(match.get("length") or 0)
        replacements = match.get("replacements") or []
        if offset < 0 or length < 0 or not replacements:
            continue
        end = offset + length
        if any(not (end <= start or offset >= stop) for start, stop in occupied):
            continue
        replacement = replacements[0]
        result = result[:offset] + replacement + result[end:]
        occupied.append((offset, end))
    return result


def normalize_matches(text: str, raw_matches: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for raw in raw_matches:
        if not isinstance(raw, dict):
            continue
        offset = int(raw.get("offset") or 0)
        length = int(raw.get("length") or 0)
        if offset < 0 or length < 0 or offset + length > len(text):
            continue
        rule = raw.get("rule") if isinstance(raw.get("rule"), dict) else {}
        category = rule.get("category") if isinstance(rule.get("category"), dict) else {}
        replacements = _safe_replacements(raw.get("replacements"))
        normalized.append(
            {
                "offset": offset,
                "length": length,
                "message": str(raw.get("message") or "Possible writing issue."),
                "short_message": str(raw.get("shortMessage") or raw.get("short_message") or ""),
                "original": text[offset : offset + length],
                "replacements": replacements,
                "rule_id": str(rule.get("id") or ""),
                "category": str(category.get("name") or category.get("id") or ""),
            }
        )
    return normalized


async def check_text(text: str, language: str | None = None) -> dict:
    """
    Check text with LanguageTool and return a frontend-friendly payload.
    Does not rewrite text unless the caller applies corrected_text.
    """
    payload = {
        "language": language or settings.LANGUAGETOOL_LANGUAGE,
        "text": text,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LANGUAGETOOL_TIMEOUT_SECONDS) as client:
            response = await client.post(_check_url(), data=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise LanguageToolError("LanguageTool rejected the grammar-check request.") from exc
    except Exception as exc:
        raise LanguageToolError("LanguageTool is currently unavailable.") from exc

    raw_matches = data.get("matches") if isinstance(data, dict) else None
    if not isinstance(raw_matches, list):
        raw_matches = []

    matches = normalize_matches(text, raw_matches)
    return {
        "original_text": text,
        "corrected_text": apply_top_replacements(text, matches),
        "matches": matches,
    }
