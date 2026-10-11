"""Small, reusable client for Remotive's public remote-jobs feed."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape
import json
import re
from threading import Lock
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_INFO_URL = "https://remotive.com/remote-jobs/api"
_CACHE_SECONDS = 6 * 60 * 60
_REQUEST_TIMEOUT_SECONDS = 10
_MAX_RESULTS = 20


class MarketDataError(RuntimeError):
    """Raised when the upstream job feed cannot be used."""


@dataclass(frozen=True)
class MarketJob:
    """The small set of provider fields AXON displays to users."""

    title: str
    company: str
    category: str | None
    eligible_location: str | None
    salary: str | None
    publication_date: str | None
    url: str
    source: str = "Remotive"

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def normalize_job(raw: Any) -> MarketJob | None:
    """Normalize one Remotive record, skipping incomplete or unsafe entries."""
    if not isinstance(raw, dict):
        return None

    title = _optional_text(raw.get("title"))
    company = _optional_text(raw.get("company_name"))
    url = _optional_text(raw.get("url"))
    if not title or not company or not url:
        return None

    try:
        parsed_url = urlsplit(url)
    except ValueError:
        return None
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "remotive.com"
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        return None

    published = _optional_text(raw.get("publication_date"))
    if published:
        try:
            published = datetime.fromisoformat(
                published.replace("Z", "+00:00")
            ).isoformat()
        except ValueError:
            published = None

    return MarketJob(
        title=title,
        company=company,
        category=_optional_text(raw.get("category")),
        eligible_location=_optional_text(raw.get("candidate_required_location")),
        salary=_optional_text(raw.get("salary")),
        publication_date=published,
        url=url,
    )


def _searchable_text(raw: dict[str, Any]) -> str:
    parts = [raw.get("title"), raw.get("description")]
    tags = raw.get("tags")
    if isinstance(tags, list):
        parts.extend(tags)
    text = " ".join(part for part in parts if isinstance(part, str))
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", text))).casefold()


class RemotiveScanner:
    """Fetch and locally filter the public feed, caching it for six hours."""

    def __init__(self, cache_seconds: int = _CACHE_SECONDS) -> None:
        self._cache_seconds = cache_seconds
        self._cached_jobs: list[dict[str, Any]] | None = None
        self._cached_at = 0.0
        self._lock = Lock()

    def _load_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            now = time.monotonic()
            if self._cached_jobs is not None and now - self._cached_at < self._cache_seconds:
                return self._cached_jobs

            request = Request(
                REMOTIVE_API_URL,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "AXON-Market-Scanner/0.1",
                },
            )
            try:
                with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
                    payload = json.loads(response.read())
            except (URLError, TimeoutError, OSError) as exc:
                raise MarketDataError("Remotive is temporarily unavailable") from exc
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
                raise MarketDataError("Remotive returned invalid JSON") from exc

            if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
                raise MarketDataError("Remotive returned an invalid jobs response")

            jobs = [job for job in payload["jobs"] if isinstance(job, dict)]
            self._cached_jobs = jobs
            self._cached_at = now
            return jobs

    def search(self, keyword: str, limit: int = 5) -> list[MarketJob]:
        """Return the newest matching jobs, with a small caller-controlled cap."""
        keyword = keyword.strip()
        if not keyword:
            raise ValueError("keyword must not be blank")
        if not 1 <= limit <= _MAX_RESULTS:
            raise ValueError(f"limit must be between 1 and {_MAX_RESULTS}")

        needle = keyword.casefold()
        matches: list[MarketJob] = []
        for raw in self._load_jobs():
            if needle not in _searchable_text(raw):
                continue
            job = normalize_job(raw)
            if job is not None:
                matches.append(job)
                if len(matches) == limit:
                    break
        return matches
