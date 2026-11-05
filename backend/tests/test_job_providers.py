"""Job-provider adapters: normalisation, pagination, errors, rate limits (mocked HTTP only)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import settings
from app.services import job_providers as jp
from app.services.job_providers import base as provider_base
from app.services.job_providers.normalization import (
    detect_country,
    html_to_text,
    location_is_relevant,
    normalize_employment_type,
    normalize_work_mode,
    parse_datetime,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(provider_base.time, "sleep", lambda *_: None)


# ── Greenhouse ───────────────────────────────────────────────────────────────

GREENHOUSE_PAYLOAD = {
    "jobs": [
        {
            "id": 111, "title": "Software Engineer - Backend (Python)", "company_name": "Acme Payments Pvt Ltd",
            "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/111",
            "location": {"name": "Bengaluru, India"}, "offices": [{"name": "Bengaluru", "location": "Bengaluru, India"}],
            "first_published": "2026-10-01T10:00:00-04:00", "updated_at": "2026-10-05T10:00:00-04:00",
            "content": "&lt;p&gt;We use &lt;b&gt;Python&lt;/b&gt;, PostgreSQL and Kafka. 2-4 years of experience.&lt;/p&gt;",
            "departments": [{"name": "Engineering"}],
            "metadata": [{"name": "Employment Type", "value": "Full-time"}],
        },
        {
            "id": 222, "title": "Account Executive", "company_name": "Acme Payments Pvt Ltd",
            "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/222",
            "location": {"name": "New York, NY"}, "offices": [], "content": "<p>Sales</p>",
        },
        {
            "id": 333, "title": "Site Reliability Engineer", "company_name": "Acme Payments Pvt Ltd",
            "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/333",
            "location": {"name": "Remote"}, "offices": [], "content": "<p>Kubernetes</p>",
            "pay_input_ranges": [{"min_cents": 250000000, "max_cents": 400000000, "currency_type": "INR", "title": "Base"}],
        },
    ]
}


def test_greenhouse_normalises_and_filters_by_location():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=GREENHOUSE_PAYLOAD)

    result = jp.GreenhouseProvider("acme", "Acme Payments", http=_client(handler)).fetch()
    assert "boards-api.greenhouse.io/v1/boards/acme/jobs" in seen["url"] and "content=true" in seen["url"]
    assert result.fetched == 3 and result.complete is True
    ids = {job.external_id for job in result.jobs}
    assert ids == {"111", "333"}  # New York listing filtered out; global remote kept
    job = next(j for j in result.jobs if j.external_id == "111")
    assert job.company == "Acme Payments"
    assert job.application_url == "https://job-boards.greenhouse.io/acme/jobs/111"
    assert job.country == "India" and job.employment_type == "full_time"
    assert "Python, PostgreSQL and Kafka" in job.description and "<" not in job.description
    assert job.posted_at is not None and job.posted_at.tzinfo is not None
    assert job.salary_min is None and job.salary_max is None  # not published → not invented
    remote = next(j for j in result.jobs if j.external_id == "333")
    assert remote.work_mode == "remote"
    assert (remote.salary_min, remote.salary_max, remote.salary_currency) == (2500000, 4000000, "INR")


def test_zero_records_is_a_successful_complete_fetch():
    result = jp.GreenhouseProvider("acme", "Acme", http=_client(lambda r: httpx.Response(200, json={"jobs": []}))).fetch()
    assert result.jobs == [] and result.fetched == 0 and result.complete is True


def test_greenhouse_404_is_a_provider_error():
    provider = jp.GreenhouseProvider("missing-board", "X", http=_client(lambda r: httpx.Response(404, json={})))
    with pytest.raises(jp.ProviderError, match="not found"):
        provider.fetch()


def test_unexpected_shape_and_invalid_json_are_errors():
    with pytest.raises(jp.ProviderError, match="unexpected response shape"):
        jp.GreenhouseProvider("a", "A", http=_client(lambda r: httpx.Response(200, json={"oops": 1}))).fetch()
    with pytest.raises(jp.ProviderError, match="not valid JSON"):
        jp.GreenhouseProvider("a", "A", http=_client(lambda r: httpx.Response(200, text="<html>"))).fetch()


def test_rate_limit_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"jobs": []})

    result = jp.GreenhouseProvider("a", "A", http=_client(handler)).fetch()
    assert calls["n"] == 3 and result.complete


def test_rate_limit_exhausted_raises_rate_limited():
    provider = jp.GreenhouseProvider("a", "A", http=_client(lambda r: httpx.Response(429)))
    with pytest.raises(jp.ProviderRateLimited):
        provider.fetch()


def test_network_errors_are_retried_then_reported():
    def handler(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(jp.ProviderError, match="network error"):
        jp.GreenhouseProvider("a", "A", http=_client(handler)).fetch()


# ── Lever ────────────────────────────────────────────────────────────────────

def _lever_posting(i: int, location: str = "Bengaluru", country: str = "IN") -> dict:
    return {
        "id": f"uuid-{i}", "text": f"Backend Developer {i}",
        "categories": {"commitment": "Full Time", "location": location, "allLocations": [location], "team": "Platform"},
        "country": country, "workplaceType": "hybrid",
        "hostedUrl": f"https://jobs.lever.co/acme/uuid-{i}", "applyUrl": f"https://jobs.lever.co/acme/uuid-{i}/apply",
        "createdAt": 1790573982021, "descriptionPlain": "Build APIs in Go and Python.",
        "lists": [{"text": "Requirements", "content": "<li>3+ years of experience with Docker</li>"}],
        "additionalPlain": "", "salaryRange": {"min": 1500000, "max": 2500000, "currency": "INR", "interval": "per-year-salary"},
    }


def test_lever_paginates_until_short_page():
    pages = {0: [_lever_posting(i) for i in range(100)], 100: [_lever_posting(100 + i) for i in range(5)]}
    requested = []

    def handler(request):
        skip = int(request.url.params["skip"])
        requested.append(skip)
        return httpx.Response(200, json=pages[skip])

    result = jp.LeverProvider("acme", "Acme", http=_client(handler)).fetch()
    assert requested == [0, 100]
    assert result.fetched == 105 and len(result.jobs) == 105 and result.complete
    job = result.jobs[0]
    assert job.company == "Acme" and job.country == "India" and job.work_mode == "hybrid"
    assert job.application_url.endswith("/apply") and job.job_url == "https://jobs.lever.co/acme/uuid-0"
    assert job.employment_type == "full_time"
    assert (job.salary_min, job.salary_max, job.salary_currency, job.salary_period) == (1500000, 2500000, "INR", "year")
    assert "3+ years of experience with Docker" in job.description


def test_lever_filters_non_india_listing():
    handler = lambda r: httpx.Response(200, json=[_lever_posting(1, "Austin, TX", "US")])  # noqa: E731
    assert jp.LeverProvider("acme", "Acme", http=_client(handler)).fetch().jobs == []


# ── Ashby ────────────────────────────────────────────────────────────────────

def test_ashby_skips_unlisted_and_reads_compensation():
    payload = {"jobs": [
        {"id": "a1", "title": "Data Analyst", "employmentType": "FullTime", "location": "Mumbai", "isListed": True,
         "isRemote": False, "workplaceType": "OnSite",
         "address": {"postalAddress": {"addressLocality": "Mumbai", "addressCountry": "India"}},
         "jobUrl": "https://jobs.ashbyhq.com/acme/a1", "applyUrl": "https://jobs.ashbyhq.com/acme/a1/application",
         "descriptionPlain": "SQL and Tableau.", "publishedAt": "2026-10-01T00:00:00.000+00:00",
         "compensation": {"summaryComponents": [{"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "INR",
                                                 "minValue": 900000, "maxValue": 1400000}]}},
        {"id": "a2", "title": "Hidden", "isListed": False, "location": "Mumbai",
         "jobUrl": "https://jobs.ashbyhq.com/acme/a2"},
        {"id": "a3", "title": "Intern - ML", "employmentType": "Intern", "location": "Remote", "isRemote": True,
         "workplaceType": "Remote", "isListed": True, "jobUrl": "https://jobs.ashbyhq.com/acme/a3", "descriptionPlain": "ML"},
    ]}
    result = jp.AshbyProvider("acme", "Acme", http=_client(lambda r: httpx.Response(200, json=payload))).fetch()
    assert [j.external_id for j in result.jobs] == ["a1", "a3"]
    analyst, intern = result.jobs
    assert analyst.work_mode == "onsite" and analyst.country == "India"
    assert (analyst.salary_min, analyst.salary_max, analyst.salary_period) == (900000, 1400000, "year")
    assert intern.employment_type == "internship" and intern.work_mode == "remote"
    assert intern.application_url == "https://jobs.ashbyhq.com/acme/a3"


# ── Remotive ─────────────────────────────────────────────────────────────────

def test_remotive_links_back_and_never_parses_salary_text():
    payload = {"0-legal-notice": "…", "jobs": [
        {"id": 9, "url": "https://remotive.com/remote-jobs/software-dev/python-dev-9", "title": "Python Developer",
         "company_name": "RemoteCo", "job_type": "full_time", "publication_date": "2026-11-01T10:00:00",
         "candidate_required_location": "Worldwide", "salary": "$40k - $60k", "description": "<p>Django</p>", "tags": ["python"]},
        {"id": 10, "url": "https://remotive.com/remote-jobs/x-10", "title": "Engineer", "company_name": "USCo",
         "job_type": "contract", "publication_date": "2026-11-01T10:00:00", "candidate_required_location": "USA Only",
         "description": "x"},
    ]}
    result = jp.RemotiveProvider("software-dev", http=_client(lambda r: httpx.Response(200, json=payload))).fetch()
    assert [j.external_id for j in result.jobs] == ["9"]
    job = result.jobs[0]
    assert job.application_url == job.job_url == "https://remotive.com/remote-jobs/software-dev/python-dev-9"
    assert job.attribution and "Remotive" in job.attribution
    assert job.salary_text == "$40k - $60k" and job.salary_min is None and job.salary_max is None
    assert job.work_mode == "remote"


def test_remotive_disabled_by_default(monkeypatch):
    from app.core.config import Settings

    assert Settings.model_fields["REMOTIVE_ENABLED"].default is False
    monkeypatch.setattr(settings, "REMOTIVE_ENABLED", False)
    remotive = {c.provider: c for c in jp.configured_providers()}["remotive"]
    assert remotive.enabled is False and "terms" in (remotive.note or "")
    assert not [p for p in jp.build_providers() if p.provider == "remotive"]


# ── Adzuna ───────────────────────────────────────────────────────────────────

def test_adzuna_requires_credentials(monkeypatch):
    monkeypatch.setattr(settings, "ADZUNA_APP_ID", "")
    monkeypatch.setattr(settings, "ADZUNA_APP_KEY", "")
    with pytest.raises(jp.ProviderNotConfigured):
        jp.AdzunaProvider("python developer", http=_client(lambda r: httpx.Response(200, json={}))).fetch()


def test_adzuna_drops_predicted_salary_and_is_never_complete(monkeypatch):
    monkeypatch.setattr(settings, "ADZUNA_APP_ID", "id")
    monkeypatch.setattr(settings, "ADZUNA_APP_KEY", "key")
    monkeypatch.setattr(settings, "ADZUNA_MAX_PAGES", 1)
    payload = {"results": [
        {"id": "z1", "title": "<strong>Python</strong> Developer", "company": {"display_name": "Zed"},
         "location": {"display_name": "Pune, Maharashtra", "area": ["India", "Maharashtra", "Pune"]},
         "description": "Python Django", "redirect_url": "https://www.adzuna.in/land/ad/z1", "created": "2026-11-01T00:00:00Z",
         "salary_min": 600000, "salary_max": 600000, "salary_is_predicted": "1", "contract_time": "full_time"},
        {"id": "z2", "title": "Data Analyst", "company": {"display_name": "Yak"},
         "location": {"display_name": "Mumbai", "area": ["India"]}, "description": "SQL",
         "redirect_url": "https://www.adzuna.in/land/ad/z2", "created": "2026-11-01T00:00:00Z",
         "salary_min": 500000, "salary_max": 700000, "salary_is_predicted": "0", "contract_type": "contract"},
    ]}
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=payload)

    result = jp.AdzunaProvider("python developer", country="in", http=_client(handler)).fetch()
    assert "/jobs/in/search/1" in seen["url"]
    assert result.complete is False
    predicted, real = result.jobs
    assert predicted.title == "Python Developer"
    assert predicted.salary_min is None and predicted.salary_max is None and predicted.salary_currency is None
    assert (real.salary_min, real.salary_max, real.salary_currency) == (500000, 700000, "INR")
    assert real.employment_type == "contract"
    assert predicted.attribution and "Adzuna" in predicted.attribution


# ── Registry / configuration ─────────────────────────────────────────────────

def test_board_list_parsing_skips_invalid_slugs():
    assert jp.parse_board_list("acme=Acme Inc, bad slug!=X ,zeta") == [("acme", "Acme Inc"), ("zeta", "zeta")]
    assert jp.parse_board_list("") == []


def test_configured_providers_never_expose_credentials(monkeypatch):
    monkeypatch.setattr(settings, "ADZUNA_APP_ID", "secret-id-123")
    monkeypatch.setattr(settings, "ADZUNA_APP_KEY", "secret-key-456")
    dumped = json.dumps([c.__dict__ for c in jp.configured_providers()], default=str)
    assert "secret-id-123" not in dumped and "secret-key-456" not in dumped


def test_build_providers_from_config(monkeypatch):
    monkeypatch.setattr(settings, "JOB_GREENHOUSE_BOARDS", "acme=Acme")
    monkeypatch.setattr(settings, "JOB_LEVER_BOARDS", "")
    monkeypatch.setattr(settings, "JOB_ASHBY_BOARDS", "beta=Beta")
    monkeypatch.setattr(settings, "ADZUNA_APP_ID", "")
    monkeypatch.setattr(settings, "REMOTIVE_ENABLED", False)
    keys = [p.source_key for p in jp.build_providers()]
    assert keys == ["greenhouse:acme", "ashby:beta"]
    assert [p.source_key for p in jp.build_providers(only="ashby")] == ["ashby:beta"]


# ── Normalisation helpers ────────────────────────────────────────────────────

def test_normalisation_helpers():
    assert html_to_text("&lt;p&gt;Hello &amp;amp; bye&lt;/p&gt;") == "Hello & bye"
    assert normalize_work_mode("OnSite") == "onsite" and normalize_work_mode(None, location="Hybrid - Pune") == "hybrid"
    assert normalize_work_mode(None, location="Bengaluru") is None  # unknown stays unknown
    assert normalize_employment_type("FullTime") == "full_time"
    assert normalize_employment_type(None, "Summer Intern 2027") == "internship"
    assert normalize_employment_type(None, "Engineer") is None
    assert detect_country("Indianapolis, IN") != "India"
    assert detect_country("Gurugram, Haryana") == "India"
    assert parse_datetime(1790573982021).year == 2026 and parse_datetime("garbage") is None
    assert location_is_relevant(["Remote"], "remote") is True
    assert location_is_relevant(["Remote - US"], "remote") is False
    assert location_is_relevant(["Pune, India"], None) is True


def test_security_skill_vocabulary_and_soc2_false_positive():
    from app.data.job_taxonomy import extract_skills

    found = extract_skills("Monitor Splunk SIEM alerts, run Nessus vulnerability scans, analyse packets in Wireshark, "
                           "manage firewalls and encryption, incident response. We are SOC 2 compliant.")
    assert {"siem", "vulnerability_management", "wireshark", "network_security", "cryptography", "incident_response"} <= set(found)
    assert "incident_response" not in extract_skills("We are SOC 2 Type II compliant.")


def test_multi_location_listing_shows_india_locations_first():
    from app.services.job_providers.normalization import combine_locations

    display, country = combine_locations("Australia - Remote", ["Tokyo, Japan", "India - Remote", "Mumbai, India", "Singapore"])
    assert display.startswith("India - Remote / Mumbai, India") and country == "India"
    assert combine_locations(None, []) == (None, None)


def test_ashby_secondary_india_location_is_kept():
    payload = {"jobs": [{"id": "x1", "title": "Incident Commander, Detection & Response - APAC", "isListed": True,
                         "location": "Australia - Remote", "isRemote": True, "workplaceType": "Remote",
                         "address": {"postalAddress": {"addressCountry": "Australia"}},
                         "secondaryLocations": [{"location": "Mumbai, India", "address": {"postalAddress": {"addressCountry": "India"}}}],
                         "jobUrl": "https://jobs.ashbyhq.com/acme/x1", "descriptionPlain": "SOC"}]}
    job = jp.AshbyProvider("acme", "Acme", http=_client(lambda r: httpx.Response(200, json=payload))).fetch().jobs[0]
    assert job.location.startswith("Mumbai, India") and job.country == "India"
