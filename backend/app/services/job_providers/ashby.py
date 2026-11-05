"""Ashby public Job Posting API adapter.

Endpoint: GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true
Public, unauthenticated, returns the board's full listing set. Unlisted postings
(``isListed == false``) are skipped. Company name comes from verified configuration.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.services.job_providers.base import FetchResult, JobProvider, NormalizedJob, ProviderError, iter_capped
from app.services.job_providers.normalization import (
    clean_text,
    combine_locations,
    detect_country,
    html_to_text,
    location_is_relevant,
    normalize_employment_type,
    normalize_work_mode,
    parse_datetime,
    parse_salary_number,
)

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"
_INTERVALS = {"1 YEAR": "year", "1 MONTH": "month", "1 HOUR": "hour", "1 WEEK": "week", "1 DAY": "day"}


def _address_text(address: Optional[dict]) -> str:
    postal = (address or {}).get("postalAddress") or {}
    parts = [postal.get("addressLocality"), postal.get("addressRegion"), postal.get("addressCountry")]
    return ", ".join(p for p in parts if p)


class AshbyProvider(JobProvider):
    provider = "ashby"
    attribution_label = "Ashby job board"

    def __init__(self, board: str, company_name: str, http=None):
        super().__init__(source_board=board, http=http)
        self.company_name = company_name

    def fetch(self) -> FetchResult:
        payload = self.get_json(f"{BASE_URL}/{self.source_board}", params={"includeCompensation": "true"})
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ProviderError(f"{self.source_key}: unexpected response shape")
        raw_jobs = payload["jobs"]
        jobs = [job for job in (self.normalize(raw) for raw in iter_capped(raw_jobs)) if job is not None]
        return FetchResult(jobs=jobs, fetched=len(raw_jobs), complete=len(raw_jobs) <= settings.JOB_SYNC_MAX_LISTINGS_PER_SOURCE)

    def normalize(self, raw: dict) -> Optional[NormalizedJob]:
        if raw.get("isListed") is False:
            return None
        address_text = _address_text(raw.get("address"))
        secondary = []
        secondary_names = [item.get("location") for item in raw.get("secondaryLocations") or []]
        for item in raw.get("secondaryLocations") or []:
            secondary.append(item.get("location") or "")
            secondary.append(_address_text(item.get("address")))
        location = clean_text(raw.get("location"), 160)
        work_mode = normalize_work_mode(raw.get("workplaceType"), is_remote=raw.get("isRemote"), location=location)
        if not location_is_relevant([location, address_text, *secondary], work_mode):
            return None

        display_location, display_country = combine_locations(location, secondary_names)

        salary_min = salary_max = None
        currency = period = None
        compensation = raw.get("compensation") or {}
        for component in compensation.get("summaryComponents") or []:
            if str(component.get("compensationType") or "").lower() == "salary":
                salary_min = parse_salary_number(component.get("minValue"))
                salary_max = parse_salary_number(component.get("maxValue"))
                currency = clean_text(component.get("currencyCode"), 10)
                period = _INTERVALS.get(str(component.get("interval") or "").upper())
                break
        salary_text = clean_text(compensation.get("scrapeableCompensationSalarySummary") or compensation.get("compensationTierSummary"), 200)

        title = clean_text(raw.get("title"), 200) or ""
        return NormalizedJob(
            provider=self.provider,
            source_board=self.source_board,
            external_id=str(raw.get("id") or ""),
            title=title,
            company=self.company_name,
            description=raw.get("descriptionPlain") or html_to_text(raw.get("descriptionHtml")),
            job_url=raw.get("jobUrl"),
            application_url=raw.get("applyUrl") or raw.get("jobUrl"),
            location=display_location or clean_text(address_text, 160),
            country=display_country or detect_country(address_text, location),
            work_mode=work_mode,
            employment_type=normalize_employment_type(raw.get("employmentType"), title),
            department=clean_text(raw.get("department") or raw.get("team"), 120),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            salary_text=salary_text,
            posted_at=parse_datetime(raw.get("publishedAt")),
            source_updated_at=parse_datetime(raw.get("updatedAt")),
            attribution=f"Listed on {self.company_name}'s Ashby job board",
        )
