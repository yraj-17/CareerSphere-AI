"""Adzuna Search API adapter (requires ADZUNA_APP_ID / ADZUNA_APP_KEY).

Endpoint: GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Search results are partial by nature, so an Adzuna fetch is never "complete":
missing listings are not deactivated by absence — they expire through
``JOB_LISTING_MAX_AGE_DAYS`` instead.

Licensing: Adzuna's API terms require a licence agreement for use in a product
that generates revenue or leads, and every displayed advert must carry an
"Adzuna" label hyperlinked to adzuna.co.uk. Descriptions are snippets only.
Predicted salaries (``salary_is_predicted == 1``) are estimates and are NOT stored.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.services.job_providers.base import (
    FetchResult,
    JobProvider,
    NormalizedJob,
    ProviderError,
    ProviderNotConfigured,
)
from app.services.job_providers.normalization import (
    clean_text,
    detect_country,
    html_to_text,
    normalize_employment_type,
    normalize_work_mode,
    parse_datetime,
    parse_salary_number,
)

BASE_URL = "https://api.adzuna.com/v1/api/jobs"
RESULTS_PER_PAGE = 50
_CURRENCY = {"in": "INR", "gb": "GBP", "us": "USD", "sg": "SGD", "au": "AUD", "ca": "CAD"}


class AdzunaProvider(JobProvider):
    provider = "adzuna"
    attribution_label = "Jobs by Adzuna"

    def __init__(self, query: str, country: Optional[str] = None, http=None):
        super().__init__(source_board=query, http=http)
        self.country = (country or settings.ADZUNA_COUNTRY or "in").lower()

    def fetch(self) -> FetchResult:
        if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
            raise ProviderNotConfigured("adzuna: ADZUNA_APP_ID / ADZUNA_APP_KEY are not set")
        raw_jobs: list[dict] = []
        for page in range(1, max(1, settings.ADZUNA_MAX_PAGES) + 1):
            payload = self.get_json(
                f"{BASE_URL}/{self.country}/search/{page}",
                params={
                    "app_id": settings.ADZUNA_APP_ID,
                    "app_key": settings.ADZUNA_APP_KEY,
                    "results_per_page": RESULTS_PER_PAGE,
                    "what": self.source_board,
                    "max_days_old": settings.JOB_LISTING_MAX_AGE_DAYS,
                    "sort_by": "date",
                    "content-type": "application/json",
                },
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise ProviderError(f"{self.source_key}: unexpected response shape")
            results = payload["results"]
            raw_jobs.extend(results)
            if len(results) < RESULTS_PER_PAGE:
                break
        jobs = [job for job in (self.normalize(raw) for raw in raw_jobs) if job is not None]
        return FetchResult(jobs=jobs, fetched=len(raw_jobs), complete=False)

    def normalize(self, raw: dict) -> Optional[NormalizedJob]:
        location_obj = raw.get("location") or {}
        location = clean_text(location_obj.get("display_name"), 160)
        area = [str(a) for a in location_obj.get("area") or []]
        predicted = str(raw.get("salary_is_predicted") or "0") == "1"
        title = html_to_text(raw.get("title")) or ""
        contract = raw.get("contract_type") if raw.get("contract_type") == "contract" else raw.get("contract_time")
        redirect = raw.get("redirect_url")
        return NormalizedJob(
            provider=self.provider,
            source_board=self.source_board,
            external_id=str(raw.get("id") or ""),
            title=clean_text(title, 200) or "",
            company=clean_text((raw.get("company") or {}).get("display_name"), 200) or "",
            description=html_to_text(raw.get("description")),
            job_url=redirect,
            application_url=redirect,
            location=location,
            country=detect_country(location, *area),
            work_mode=normalize_work_mode(None, location=f"{location or ''} {title}"),
            employment_type=normalize_employment_type(contract, title),
            salary_min=None if predicted else parse_salary_number(raw.get("salary_min")),
            salary_max=None if predicted else parse_salary_number(raw.get("salary_max")),
            salary_currency=None if predicted or raw.get("salary_min") is None else _CURRENCY.get(self.country),
            salary_period=None if predicted or raw.get("salary_min") is None else "year",
            posted_at=parse_datetime(raw.get("created")),
            attribution="Jobs by Adzuna (adzuna.co.uk)",
        )
