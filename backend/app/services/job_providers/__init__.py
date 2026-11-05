"""Job-provider adapters and the registry that builds them from configuration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.job_providers.adzuna import AdzunaProvider
from app.services.job_providers.ashby import AshbyProvider
from app.services.job_providers.base import (
    FetchResult,
    JobProvider,
    NormalizedJob,
    ProviderError,
    ProviderNotConfigured,
    ProviderRateLimited,
)
from app.services.job_providers.greenhouse import GreenhouseProvider
from app.services.job_providers.lever import LeverProvider
from app.services.job_providers.remotive import RemotiveProvider

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")

__all__ = [
    "AdzunaProvider", "AshbyProvider", "FetchResult", "GreenhouseProvider", "JobProvider", "LeverProvider",
    "NormalizedJob", "ProviderError", "ProviderNotConfigured", "ProviderRateLimited", "RemotiveProvider",
    "ProviderConfig", "configured_providers", "build_providers", "parse_board_list",
]


def parse_board_list(raw: str) -> list[tuple[str, str]]:
    """Parse "slug=Company Name,slug2=Other" into [(slug, name)]. Invalid slugs are skipped."""
    boards: list[tuple[str, str]] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        slug, _, name = item.partition("=")
        slug, name = slug.strip(), name.strip()
        if not _SLUG_RE.match(slug):
            logger.warning("[JobSync] Ignoring invalid board slug %r", slug)
            continue
        boards.append((slug, name or slug))
    return boards


def _csv(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


@dataclass(frozen=True)
class ProviderConfig:
    """Public (non-secret) description of a configured provider."""

    provider: str
    enabled: bool
    sources: tuple[str, ...]
    attribution: str
    note: str = ""


def configured_providers() -> list[ProviderConfig]:
    """Every supported provider and whether it is active — never includes credentials."""
    adzuna_ready = bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)
    return [
        ProviderConfig("greenhouse", bool(parse_board_list(settings.JOB_GREENHOUSE_BOARDS)),
                       tuple(s for s, _ in parse_board_list(settings.JOB_GREENHOUSE_BOARDS)), GreenhouseProvider.attribution_label),
        ProviderConfig("lever", bool(parse_board_list(settings.JOB_LEVER_BOARDS)),
                       tuple(s for s, _ in parse_board_list(settings.JOB_LEVER_BOARDS)), LeverProvider.attribution_label),
        ProviderConfig("ashby", bool(parse_board_list(settings.JOB_ASHBY_BOARDS)),
                       tuple(s for s, _ in parse_board_list(settings.JOB_ASHBY_BOARDS)), AshbyProvider.attribution_label),
        ProviderConfig("adzuna", adzuna_ready, tuple(_csv(settings.ADZUNA_QUERIES)) if adzuna_ready else (),
                       AdzunaProvider.attribution_label,
                       "" if adzuna_ready else "Not configured: set ADZUNA_APP_ID and ADZUNA_APP_KEY (licence required for commercial use)."),
        ProviderConfig("remotive", settings.REMOTIVE_ENABLED,
                       tuple(_csv(settings.REMOTIVE_CATEGORIES)) if settings.REMOTIVE_ENABLED else (),
                       RemotiveProvider.attribution_label,
                       "" if settings.REMOTIVE_ENABLED else "Disabled: Remotive's terms forbid showing its jobs behind sign-up without permission."),
    ]


def build_providers(only: str | None = None) -> list[JobProvider]:
    """Instantiate one provider per configured source. ``only`` limits to one provider key."""
    providers: list[JobProvider] = []
    if only in (None, "greenhouse"):
        providers += [GreenhouseProvider(slug, name) for slug, name in parse_board_list(settings.JOB_GREENHOUSE_BOARDS)]
    if only in (None, "lever"):
        providers += [LeverProvider(slug, name) for slug, name in parse_board_list(settings.JOB_LEVER_BOARDS)]
    if only in (None, "ashby"):
        providers += [AshbyProvider(slug, name) for slug, name in parse_board_list(settings.JOB_ASHBY_BOARDS)]
    if only in (None, "adzuna") and settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY:
        providers += [AdzunaProvider(query) for query in _csv(settings.ADZUNA_QUERIES)]
    if only in (None, "remotive") and settings.REMOTIVE_ENABLED:
        providers += [RemotiveProvider(category) for category in _csv(settings.REMOTIVE_CATEGORIES)]
    return providers
