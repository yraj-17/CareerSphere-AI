"""Lever public Postings API adapter.

Endpoint: GET https://api.lever.co/v0/postings/{site}?mode=json
Public, unauthenticated. Pages with ``skip``/``limit`` until a short page is returned.
Lever does not return the company name, so it comes from verified configuration.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.services.job_providers.base import FetchResult, JobProvider, NormalizedJob, ProviderError
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

BASE_URL = "https://api.lever.co/v0/postings"
PAGE_SIZE = 100

_COUNTRY_CODES = {"IN": "India", "US": "United States", "GB": "United Kingdom", "CA": "Canada", "SG": "Singapore",
                  "DE": "Germany", "IE": "Ireland", "AU": "Australia", "NL": "Netherlands", "FR": "France", "JP": "Japan"}

_INTERVALS = {"per-year-salary": "year", "per-month-salary": "month", "per-hour-wage": "hour", "per-day-wage": "day",
              "per-week-wage": "week", "one-time": "one_time"}


class LeverProvider(JobProvider):
    provider = "lever"
    attribution_label = "Lever job board"

    def __init__(self, site: str, company_name: str, http=None):
        super().__init__(source_board=site, http=http)
        self.company_name = company_name

    def fetch(self) -> FetchResult:
        raw_jobs: list[dict] = []
        skip = 0
        cap = settings.JOB_SYNC_MAX_LISTINGS_PER_SOURCE
        complete = True
        while True:
            page = self.get_json(f"{BASE_URL}/{self.source_board}", params={"mode": "json", "skip": skip, "limit": PAGE_SIZE})
            if not isinstance(page, list):
                raise ProviderError(f"{self.source_key}: unexpected response shape")
            raw_jobs.extend(page)
            if len(page) < PAGE_SIZE:
                break
            skip += PAGE_SIZE
            if len(raw_jobs) >= cap:
                complete = False
                break
        jobs = [job for job in (self.normalize(raw) for raw in raw_jobs[:cap]) if job is not None]
        return FetchResult(jobs=jobs, fetched=len(raw_jobs), complete=complete)

    def normalize(self, raw: dict) -> Optional[NormalizedJob]:
        categories = raw.get("categories") or {}
        all_locations = [loc for loc in categories.get("allLocations") or [] if loc]
        location = clean_text(categories.get("location") or ", ".join(all_locations), 160)
        work_mode = normalize_work_mode(raw.get("workplaceType"), location=location)
        if not location_is_relevant([location, *all_locations, _COUNTRY_CODES.get(raw.get("country") or "", "")], work_mode):
            return None

        sections = [raw.get("openingPlain") or "", raw.get("descriptionBodyPlain") or raw.get("descriptionPlain") or ""]
        for block in raw.get("lists") or []:
            heading = clean_text(block.get("text")) or ""
            body = html_to_text(block.get("content"))
            if heading or body:
                sections.append(f"{heading}\n{body}".strip())
        sections.append(raw.get("additionalPlain") or "")
        description = "\n\n".join(s.strip() for s in sections if s and s.strip())

        display_location, display_country = combine_locations(categories.get("location"), all_locations)
        salary = raw.get("salaryRange") or {}
        title = clean_text(raw.get("text"), 200) or ""
        return NormalizedJob(
            provider=self.provider,
            source_board=self.source_board,
            external_id=str(raw.get("id") or ""),
            title=title,
            company=self.company_name,
            description=description,
            job_url=raw.get("hostedUrl"),
            application_url=raw.get("applyUrl") or raw.get("hostedUrl"),
            location=display_location or location,
            country=display_country or _COUNTRY_CODES.get(raw.get("country") or "") or detect_country(location, *all_locations),
            work_mode=work_mode,
            employment_type=normalize_employment_type(categories.get("commitment"), title),
            department=clean_text(categories.get("team") or categories.get("department"), 120),
            salary_min=parse_salary_number(salary.get("min")),
            salary_max=parse_salary_number(salary.get("max")),
            salary_currency=clean_text(salary.get("currency"), 10),
            salary_period=_INTERVALS.get(str(salary.get("interval") or ""), None),
            posted_at=parse_datetime(raw.get("createdAt")),
            source_updated_at=parse_datetime(raw.get("updatedAt")),
            attribution=f"Listed on {self.company_name}'s Lever job board",
        )
