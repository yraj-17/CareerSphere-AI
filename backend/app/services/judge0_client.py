"""
Asynchronous Judge0 CE client (httpx).

* Every request carries X-Auth-Token; the token is never logged or returned.
* A fresh connection is opened per operation, so the client is safe to use from
  any event loop (a long-lived module-level client binds to the first loop).
* Retries are bounded and conservative:
    GET  — retried on transport errors and 502/503/504.
    POST — retried only when the request provably did not reach Judge0
           (connect errors) or Judge0 refused it before queueing (503 queue full,
           429). A POST that may have been accepted is never resent, so retries
           cannot create duplicate executions.
* Submissions are always asynchronous (wait=false); results are polled.
* Source, stdin and outputs travel base64-encoded so arbitrary bytes are safe.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.core.config import settings
from app.data.coding_languages import LANGUAGE_BY_KEY, LANGUAGES

logger = logging.getLogger(__name__)

# Judge0 status ids (1.13.x)
STATUS_IN_QUEUE = 1
STATUS_PROCESSING = 2
MAX_OUTPUT_CHARS = 64 * 1024
RESULT_FIELDS = "token,status,stdout,stderr,compile_output,message,time,memory,exit_code,exit_signal"


class Judge0Error(Exception):
    """
    kind:
      not_configured  JUDGE0_API_URL / JUDGE0_AUTH_TOKEN missing
      auth            Judge0 rejected the credentials (server misconfiguration)
      rejected        Judge0 refused the request (e.g. a limit above its ceiling)
      unavailable     network failure, timeout, or 5xx after retries
      protocol        unexpected response shape
    The message is safe to log; it never contains the token or test data.
    """

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


@dataclass
class ExecutionRequest:
    language_id: int
    source_code: str
    stdin: str = ""
    cpu_time_limit: float = 2.0
    wall_time_limit: float = 5.0
    memory_limit_kb: int = 256_000
    compiler_options: Optional[str] = None

    def to_payload(self) -> dict:
        payload = {
            "language_id": self.language_id,
            "source_code": _b64(self.source_code),
            "stdin": _b64(self.stdin),
            "cpu_time_limit": self.cpu_time_limit,
            "wall_time_limit": self.wall_time_limit,
            "memory_limit": self.memory_limit_kb,
            # Networking stays disabled server-side (ALLOW_ENABLE_NETWORK=false); never request it.
            "enable_network": False,
        }
        if self.compiler_options:
            payload["compiler_options"] = self.compiler_options
        return payload


@dataclass
class ExecutionResult:
    token: str
    status_id: int
    status_description: str
    stdout: str = ""
    stderr: str = ""
    compile_output: str = ""
    message: str = ""
    time: Optional[float] = None
    memory: Optional[int] = None  # KB
    exit_code: Optional[int] = None
    exit_signal: Optional[int] = None

    @property
    def finished(self) -> bool:
        return self.status_id not in (STATUS_IN_QUEUE, STATUS_PROCESSING)

    @classmethod
    def from_api(cls, data: dict) -> "ExecutionResult":
        status = data.get("status") or {}
        return cls(
            token=data.get("token", ""),
            status_id=int(status.get("id", 0)),
            status_description=str(status.get("description", "")),
            stdout=_unb64(data.get("stdout")),
            stderr=_unb64(data.get("stderr")),
            compile_output=_unb64(data.get("compile_output")),
            message=_unb64(data.get("message")),
            time=float(data["time"]) if data.get("time") not in (None, "") else None,
            memory=int(data["memory"]) if data.get("memory") not in (None, "") else None,
            exit_code=data.get("exit_code"),
            exit_signal=data.get("exit_signal"),
        )


def _b64(text: str) -> str:
    return base64.b64encode((text or "").encode("utf-8")).decode("ascii")


def _unb64(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        decoded = base64.b64decode(value).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        decoded = ""
    return decoded[:MAX_OUTPUT_CHARS]


class Judge0Client:
    def __init__(self, base_url: str, token: str):
        if not base_url or not token:
            raise Judge0Error("not_configured", "Judge0 is not configured.")
        self.base_url = base_url.rstrip("/")
        self._headers = {"X-Auth-Token": token, "Content-Type": "application/json"}
        self._timeout = httpx.Timeout(
            connect=settings.JUDGE0_CONNECT_TIMEOUT_SECONDS,
            read=settings.JUDGE0_READ_TIMEOUT_SECONDS,
            write=settings.JUDGE0_READ_TIMEOUT_SECONDS,
            pool=settings.JUDGE0_CONNECT_TIMEOUT_SECONDS,
        )

    @classmethod
    def from_settings(cls) -> "Judge0Client":
        return cls(settings.JUDGE0_API_URL, settings.JUDGE0_AUTH_TOKEN)

    async def _request(self, method: str, path: str, *, json: Optional[dict] = None, params: Optional[dict] = None) -> httpx.Response:
        attempts = max(1, settings.JUDGE0_MAX_RETRIES + 1)
        last_error = "unknown error"
        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(base_url=self.base_url, headers=self._headers, timeout=self._timeout) as http:
                    response = await http.request(method, path, json=json, params=params)
            except httpx.ConnectError as exc:  # never reached Judge0: safe to retry any method
                last_error = f"connect error ({type(exc).__name__})"
            except httpx.TransportError as exc:
                last_error = f"transport error ({type(exc).__name__})"
                if method != "GET":
                    break  # a POST may have been accepted; do not risk a duplicate execution
            else:
                if response.status_code == 401:
                    raise Judge0Error("auth", "Judge0 rejected the configured credentials.")
                if response.status_code in (502, 503, 504) or response.status_code == 429:
                    if method != "GET" and response.status_code not in (503, 429):
                        last_error = f"HTTP {response.status_code}"
                        break
                    last_error = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise Judge0Error("rejected", f"Judge0 rejected the request (HTTP {response.status_code}).")
                else:
                    return response
            if attempt < attempts:
                await asyncio.sleep(0.4 * attempt)
        logger.warning("[Judge0] %s %s failed after %d attempt(s): %s", method, path, attempt, last_error)
        raise Judge0Error("unavailable", "The code execution service is temporarily unavailable.")

    async def languages(self) -> list[dict]:
        response = await self._request("GET", "/languages")
        data = response.json()
        if not isinstance(data, list):
            raise Judge0Error("protocol", "Unexpected /languages response.")
        return data

    async def submit_batch(self, requests: list[ExecutionRequest]) -> list[str]:
        """Create submissions (asynchronously) and return their tokens, in order."""
        tokens: list[str] = []
        size = max(1, settings.JUDGE0_BATCH_SIZE)
        for start in range(0, len(requests), size):
            chunk = requests[start : start + size]
            response = await self._request(
                "POST",
                "/submissions/batch",
                params={"base64_encoded": "true"},
                json={"submissions": [r.to_payload() for r in chunk]},
            )
            data = response.json()
            if not isinstance(data, list) or len(data) != len(chunk) or not all(isinstance(i, dict) and i.get("token") for i in data):
                raise Judge0Error("rejected", "Judge0 did not accept every submission in the batch.")
            tokens.extend(item["token"] for item in data)
        return tokens

    async def fetch_batch(self, tokens: list[str]) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        size = max(1, settings.JUDGE0_BATCH_SIZE)
        for start in range(0, len(tokens), size):
            chunk = tokens[start : start + size]
            response = await self._request(
                "GET",
                "/submissions/batch",
                params={"tokens": ",".join(chunk), "base64_encoded": "true", "fields": RESULT_FIELDS},
            )
            data = response.json()
            items = data.get("submissions") if isinstance(data, dict) else None
            if not isinstance(items, list) or len(items) != len(chunk):
                raise Judge0Error("protocol", "Unexpected batch result response.")
            by_token = {i.get("token"): i for i in items if isinstance(i, dict)}
            results.extend(ExecutionResult.from_api(by_token.get(t) or {"token": t}) for t in chunk)
        return results

    async def wait(self, tokens: list[str], max_seconds: float) -> list[ExecutionResult]:
        """Poll until every submission finished or max_seconds elapsed (then return current states)."""
        deadline = time.monotonic() + max(0.0, max_seconds)
        interval = max(0.1, settings.JUDGE0_POLL_INTERVAL_SECONDS)
        while True:
            results = await self.fetch_batch(tokens)
            if all(r.finished for r in results) or time.monotonic() >= deadline:
                return results
            await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# Language resolution (cached)
# ---------------------------------------------------------------------------

_language_cache: dict = {"expires": 0.0, "value": None}


async def resolve_languages(client: Judge0Client) -> dict[str, dict]:
    """
    Map CareerSphere language keys to {"judge0_id", "label"} using the server's own
    /languages list. Falls back to the verified IDs/labels only if the list cannot be read.
    """
    now = time.monotonic()
    if _language_cache["value"] is not None and now < _language_cache["expires"]:
        return _language_cache["value"]
    try:
        available = await client.languages()
        resolved = {}
        for lang in LANGUAGES:
            matches = [a for a in available if str(a.get("name", "")).startswith(lang.judge0_name_prefix)]
            if matches:
                best = max(matches, key=lambda a: int(a["id"]))
                resolved[lang.key] = {"judge0_id": int(best["id"]), "label": str(best["name"])}
        source = "judge0"
    except Judge0Error:
        resolved = {}
        source = "fallback"
    for lang in LANGUAGES:
        resolved.setdefault(lang.key, {"judge0_id": lang.fallback_judge0_id, "label": lang.fallback_label})
    if source == "judge0":
        _language_cache.update(expires=now + settings.JUDGE0_LANGUAGES_CACHE_SECONDS, value=resolved)
    return resolved


def language_config(key: str):
    return LANGUAGE_BY_KEY.get(key)
