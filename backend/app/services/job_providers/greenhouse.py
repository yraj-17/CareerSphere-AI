"""Greenhouse public Job Board API adapter.

Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
Public, unauthenticated, returns the board's full current listing set in one response.
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
)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


def _metadata_value(job: dict, *names: str) -> Optional[str]:
    for item in job.get("metadata") or []:
        name = str(item.get("name") or "").strip().lower()
        if name in names and item.get("value"):
            value = item["value"]
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value if v)
            return str(value)
    return None


class GreenhouseProvider(JobProvider):
    provider = "greenhouse"
    attribution_label = "Greenhouse job board"

    def __init__(self, board_token: str, company_name: Optional[str] = None, http=None):
        super().__init__(source_board=board_token, http=http)
        self.company_name = company_name

    def fetch(self) -> FetchResult:
        payload = self.get_json(f"{BASE_URL}/{self.source_board}/jobs", params={"content": "true", "pay_transparency": "true"})
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ProviderError(f"{self.source_key}: unexpected response shape")
        raw_jobs = payload["jobs"]
        jobs = [job for job in (self.normalize(raw) for raw in iter_capped(raw_jobs)) if job is not None]
        return FetchResult(jobs=jobs, fetched=len(raw_jobs), complete=len(raw_jobs) <= settings.JOB_SYNC_MAX_LISTINGS_PER_SOURCE)

    def normalize(self, raw: dict) -> Optional[NormalizedJob]:
        location = clean_text((raw.get("location") or {}).get("name"), 160)
        office_locations = [o.get("location") or o.get("name") for o in raw.get("offices") or []]
        workplace = _metadata_value(raw, "workplace type", "workplace", "work type", "location type", "remote")
        work_mode = normalize_work_mode(workplace, location=location)
        if not location_is_relevant([location, *office_locations], work_mode):
            return None

        display_location, display_country = combine_locations(location, office_locations)

        salary_min = salary_max = None
        currency = period = salary_text = None
        ranges = raw.get("pay_input_ranges") or []
        if ranges:
            first = ranges[0]
            try:
                salary_min = int(first["min_cents"]) // 100 if first.get("min_cents") else None
                salary_max = int(first["max_cents"]) // 100 if first.get("max_cents") else None
            except (TypeError, ValueError):
                salary_min = salary_max = None
            currency = clean_text(first.get("currency_type"), 10)
            salary_text = clean_text(first.get("title"), 200)

        departments = [d.get("name") for d in raw.get("departments") or [] if d.get("name")]
        url = raw.get("absolute_url")
        return NormalizedJob(
            provider=self.provider,
            source_board=self.source_board,
            external_id=str(raw.get("id") or ""),
            title=clean_text(raw.get("title"), 200) or "",
            company=self.company_name or clean_text(raw.get("company_name"), 200) or "",
            description=html_to_text(raw.get("content")),
            job_url=url,
            application_url=url,  # the hosted Greenhouse posting page carries the application form
            location=display_location,
            country=display_country or detect_country(location, *office_locations),
            work_mode=work_mode,
            employment_type=normalize_employment_type(
                _metadata_value(raw, "employment type", "job type", "employment", "type of employment", "time type"),
                raw.get("title"),
            ),
            department=departments[0] if departments else None,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            salary_text=salary_text,
            posted_at=parse_datetime(raw.get("first_published")),
            source_updated_at=parse_datetime(raw.get("updated_at")),
            expires_at=parse_datetime(raw.get("application_deadline")),
            attribution=f"Listed on {self.company_name or raw.get('company_name') or self.source_board}'s Greenhouse job board",
        )
