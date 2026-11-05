"""Remotive public API adapter (disabled by default).

Endpoint: GET https://remotive.com/api/remote-jobs?category={category}

Remotive's API legal notice requires: link back to the Remotive URL, mention
Remotive as the source, no redistribution to other aggregators, at most ~4
requests/day, and it forbids "displaying our jobs in order to collect
signups/email addresses to show a listing". CareerSphere's Career Matching is
behind sign-up, so this adapter only runs when the operator sets
REMOTIVE_ENABLED=true after obtaining Remotive's permission (or its paid API).
Every listing links to the Remotive page (``url``), never to a scraped target.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.services.job_providers.base import FetchResult, JobProvider, NormalizedJob, ProviderError, iter_capped
from app.services.job_providers.normalization import (
    clean_text,
    detect_country,
    html_to_text,
    location_is_relevant,
    normalize_employment_type,
    parse_datetime,
)

BASE_URL = "https://remotive.com/api/remote-jobs"
# Remotive asks for at most ~4 fetches a day.
MIN_INTERVAL_HOURS = 6


class RemotiveProvider(JobProvider):
    provider = "remotive"
    attribution_label = "Remotive"

    def __init__(self, category: str, http=None):
        super().__init__(source_board=category, http=http)

    def fetch(self) -> FetchResult:
        payload = self.get_json(BASE_URL, params={"category": self.source_board}, max_retries=1)
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ProviderError(f"{self.source_key}: unexpected response shape")
        raw_jobs = payload["jobs"]
        jobs = [job for job in (self.normalize(raw) for raw in iter_capped(raw_jobs)) if job is not None]
        return FetchResult(jobs=jobs, fetched=len(raw_jobs), complete=len(raw_jobs) <= settings.JOB_SYNC_MAX_LISTINGS_PER_SOURCE)

    def normalize(self, raw: dict) -> Optional[NormalizedJob]:
        location = clean_text(raw.get("candidate_required_location"), 160)
        if not location_is_relevant([location or "Worldwide"], "remote"):
            return None
        title = clean_text(raw.get("title"), 200) or ""
        url = raw.get("url")
        return NormalizedJob(
            provider=self.provider,
            source_board=self.source_board,
            external_id=str(raw.get("id") or ""),
            title=title,
            company=clean_text(raw.get("company_name"), 200) or "",
            description=html_to_text(raw.get("description")),
            job_url=url,
            application_url=url,  # Remotive requires linking to its own listing page
            location=location,
            country=detect_country(location),
            work_mode="remote",
            employment_type=normalize_employment_type(raw.get("job_type"), title),
            salary_text=clean_text(raw.get("salary"), 200),  # free text; never parsed into numbers
            posted_at=parse_datetime(raw.get("publication_date")),
            attribution="Source: Remotive (remotive.com)",
            provider_tags=[str(tag) for tag in raw.get("tags") or []],
        )
