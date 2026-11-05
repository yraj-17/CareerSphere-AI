"""Common job-provider interface, normalised record, and HTTP helper."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = "CareerSphereAI-JobSync/1.0 (+career matching; respects provider terms)"


class ProviderError(Exception):
    """A provider could not be read (network error, bad status, invalid payload)."""


class ProviderRateLimited(ProviderError):
    """The provider asked us to slow down (HTTP 429) and retries were exhausted."""


class ProviderNotConfigured(ProviderError):
    """Required credentials/configuration for a provider are missing."""


@dataclass
class NormalizedJob:
    """Provider-agnostic job record. ``None`` means the provider did not state it."""

    provider: str
    source_board: Optional[str]
    external_id: str
    title: str
    company: str
    description: str
    job_url: Optional[str]
    application_url: Optional[str]
    location: Optional[str] = None
    country: Optional[str] = None
    work_mode: Optional[str] = None  # remote | hybrid | onsite
    employment_type: Optional[str] = None  # full_time | part_time | contract | internship | temporary
    department: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    salary_text: Optional[str] = None
    posted_at: Optional[datetime] = None
    source_updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    attribution: Optional[str] = None
    provider_tags: list[str] = field(default_factory=list)

    def validation_errors(self) -> list[str]:
        errors = []
        if not self.external_id:
            errors.append("missing external_id")
        if not self.title or not self.title.strip():
            errors.append("missing title")
        if not self.company or not self.company.strip():
            errors.append("missing company")
        if not (self.application_url or self.job_url):
            errors.append("missing job/application URL")
        for url in (self.application_url, self.job_url):
            if url and not url.startswith("https://") and not url.startswith("http://"):
                errors.append("non-http URL")
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            errors.append("salary_min > salary_max")
        return errors


@dataclass(frozen=True)
class FetchResult:
    """Outcome of reading one source.

    ``complete`` is True only when the provider returned its full current listing
    set for the source (e.g. a company board). Only complete fetches may be used to
    deactivate listings that disappeared — a partial search result never is.
    """

    jobs: list[NormalizedJob]
    fetched: int
    complete: bool


class JobProvider(ABC):
    """One readable job source (a provider + a board/feed)."""

    provider: str = ""
    #: Human-readable attribution shown next to each listing.
    attribution_label: str = ""

    def __init__(self, source_board: Optional[str] = None, http: Optional[httpx.Client] = None):
        self.source_board = source_board
        self._http = http

    @property
    def source_key(self) -> str:
        return f"{self.provider}:{self.source_board}" if self.source_board else self.provider

    @abstractmethod
    def fetch(self) -> FetchResult:
        """Fetch and normalise every listing currently published by this source."""

    # ── HTTP helper ───────────────────────────────────────────────────────
    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                timeout=settings.JOB_SYNC_HTTP_TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                follow_redirects=True,
            )
        return self._http

    def get_json(self, url: str, params: Optional[dict[str, Any]] = None, max_retries: int = 3) -> Any:
        """GET JSON with bounded retries for transient failures and 429 back-off."""
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client().get(url, params=params)
            except httpx.HTTPError as exc:
                if attempt <= max_retries:
                    time.sleep(min(2 ** attempt, 10))
                    continue
                raise ProviderError(f"{self.source_key}: network error ({type(exc).__name__})") from exc

            if response.status_code == 429:
                if attempt <= max_retries:
                    retry_after = response.headers.get("Retry-After", "")
                    delay = float(retry_after) if retry_after.isdigit() else min(5 * attempt, 30)
                    time.sleep(min(delay, 60))
                    continue
                raise ProviderRateLimited(f"{self.source_key}: rate limited (HTTP 429)")
            if response.status_code in (502, 503, 504) and attempt <= max_retries:
                time.sleep(min(2 ** attempt, 10))
                continue
            if response.status_code == 404:
                raise ProviderError(f"{self.source_key}: board not found (HTTP 404)")
            if response.status_code in (401, 403):
                raise ProviderError(f"{self.source_key}: access denied (HTTP {response.status_code})")
            if response.status_code >= 400:
                raise ProviderError(f"{self.source_key}: HTTP {response.status_code}")
            try:
                return response.json()
            except ValueError as exc:
                raise ProviderError(f"{self.source_key}: response was not valid JSON") from exc

    def close(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None


def iter_capped(items: list[Any], cap: Optional[int] = None) -> Iterator[Any]:
    limit = cap if cap is not None else settings.JOB_SYNC_MAX_LISTINGS_PER_SOURCE
    for index, item in enumerate(items):
        if index >= limit:
            logger.warning("[JobSync] Listing cap (%d) reached; remaining items skipped.", limit)
            return
        yield item
