"""Small, reusable client for Remotive's public remote-jobs feed."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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

# Intentionally small, explicit vocabulary. Skills are detected only in the
# provider's title, description, and tags fields; category/company are excluded.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "AWS": ("aws", "amazon web services"),
    "C#": ("c#", "c sharp"),
    "C++": ("c++", "c plus plus"),
    "Docker": ("docker",),
    "Java": ("java",),
    "JavaScript": ("javascript", "java script"),
    "Kubernetes": ("kubernetes", "k8s"),
    "Node.js": ("node.js", "nodejs", "node js"),
    "PostgreSQL": ("postgresql", "postgres"),
    "Python": ("python",),
    "React": ("react", "react.js", "reactjs"),
    "SQL": ("sql",),
    "TypeScript": ("typescript", "type script"),
}


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


@dataclass(frozen=True)
class EnrichedMarketJob:
    """A listing plus conservative, source-grounded enrichment metadata."""

    job: MarketJob
    skills: tuple[str, ...]
    publication_date_quality: str
    duplicate_of: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.job.to_dict(),
            "skills": list(self.skills),
            "publication_date_quality": self.publication_date_quality,
            "duplicate_of": self.duplicate_of,
        }


def extract_skills(raw: Any) -> tuple[str, ...]:
    """Find recognized skills in Remotive title, description, and tags only."""
    if not isinstance(raw, dict):
        return ()

    parts = [raw.get("title"), raw.get("description")]
    tags = raw.get("tags")
    if isinstance(tags, list):
        parts.extend(tags)
    text = unescape(re.sub(r"<[^>]*>", " ", " ".join(
        part for part in parts if isinstance(part, str)
    ))).casefold()

    found = []
    for skill, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            pattern = rf"(?<!\w){re.escape(alias.casefold())}(?!\w)"
            if re.search(pattern, text):
                found.append(skill)
                break
    return tuple(found)


def _date_quality(value: Any) -> str:
    """Describe the precision supplied by Remotive without inventing dates."""
    published = _optional_text(value)
    if published is None:
        return "missing"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        try:
            datetime.fromisoformat(published)
        except ValueError:
            return "invalid"
        return "date_only"
    try:
        parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return "invalid"
    return "timezone_present" if parsed.tzinfo is not None else "timezone_unspecified"


def enrich_jobs(raw_jobs: list[dict[str, Any]], jobs: list[MarketJob]) -> list[EnrichedMarketJob]:
    """Enrich returned listings; duplicates require the same Remotive URL."""
    seen_urls: dict[str, str] = {}
    enriched = []
    for raw, job in zip(raw_jobs, jobs, strict=True):
        parsed = urlsplit(job.url)
        canonical_url = f"{parsed.netloc.casefold()}{parsed.path.rstrip('/')}"
        duplicate_of = seen_urls.get(canonical_url)
        seen_urls.setdefault(canonical_url, job.url)
        date_quality = _date_quality(raw.get("publication_date"))
        if date_quality == "date_only":
            job = replace(job, publication_date=_optional_text(raw.get("publication_date")))
        enriched.append(
            EnrichedMarketJob(
                job=job,
                skills=extract_skills(raw),
                publication_date_quality=date_quality,
                duplicate_of=duplicate_of,
            )
        )
    return enriched


def skill_frequency(jobs: list[EnrichedMarketJob]) -> dict[str, Any]:
    """Count listings containing each recognized skill in this returned sample."""
    counts: dict[str, int] = {}
    for enriched in jobs:
        for skill in enriched.skills:
            counts[skill] = counts.get(skill, 0) + 1
    return {
        "basis": "sample_based_returned_listings",
        "sample_size": len(jobs),
        "job_counts": dict(sorted(counts.items())),
    }


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
        return [job for _, job in self._search_matches(keyword, limit)]

    def search_enriched(self, keyword: str, limit: int = 5) -> list[EnrichedMarketJob]:
        """Search and enrich only the source records returned to the caller."""
        matches = self._search_matches(keyword, limit)
        return enrich_jobs(
            [raw for raw, _ in matches], [job for _, job in matches]
        )

    def _search_matches(self, keyword: str, limit: int) -> list[tuple[dict[str, Any], MarketJob]]:
        keyword = keyword.strip()
        if not keyword:
            raise ValueError("keyword must not be blank")
        if not 1 <= limit <= _MAX_RESULTS:
            raise ValueError(f"limit must be between 1 and {_MAX_RESULTS}")

        needle = keyword.casefold()
        matches: list[tuple[dict[str, Any], MarketJob]] = []
        for raw in self._load_jobs():
            if needle not in _searchable_text(raw):
                continue
            job = normalize_job(raw)
            if job is not None:
                matches.append((raw, job))
                if len(matches) == limit:
                    break
        return matches
