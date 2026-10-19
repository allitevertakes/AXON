import json

import pytest
from fastapi.testclient import TestClient

import axon.market_scanner as market_scanner
from axon.config import Settings
from axon.main import create_app
from axon.market_scanner import MarketDataError, RemotiveScanner, extract_skills


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def sample_job(**overrides: object) -> dict[str, object]:
    job: dict[str, object] = {
        "title": "Python Platform Engineer",
        "company_name": "Example Co",
        "category": "Software Development",
        "candidate_required_location": "Worldwide",
        "salary": "$100,000 - $120,000",
        "publication_date": "2026-10-01T09:30:00",
        "url": "https://remotive.com/remote-jobs/software-dev/python-engineer-123",
        "description": "<p>Build Python systems</p>",
    }
    job.update(overrides)
    return job


def mock_feed(monkeypatch: pytest.MonkeyPatch, jobs: list[object]) -> None:
    monkeypatch.setattr(
        market_scanner,
        "urlopen",
        lambda request, timeout: FakeResponse({"jobs": jobs}),
    )


def test_search_filters_and_normalizes_provider_fields(monkeypatch) -> None:
    mock_feed(
        monkeypatch,
        [sample_job(), sample_job(title="Designer", description="Design experiences")],
    )

    jobs = RemotiveScanner().search("PYTHON", limit=3)

    assert len(jobs) == 1
    assert jobs[0].title == "Python Platform Engineer"
    assert jobs[0].company == "Example Co"
    assert jobs[0].category == "Software Development"
    assert jobs[0].eligible_location == "Worldwide"
    assert jobs[0].salary == "$100,000 - $120,000"
    assert jobs[0].publication_date == "2026-10-01T09:30:00"
    assert jobs[0].url.startswith("https://remotive.com/")
    assert jobs[0].source == "Remotive"


def test_skill_extraction_uses_only_available_text_and_known_variants() -> None:
    raw = sample_job(
        title="JavaScript and AWS Engineer",
        description="<p>Uses Postgres, PostgreSQL, NodeJS, and pythonic patterns.</p>",
        tags=["K8s", "React.js", "SQL"],
        category="Docker",
        company_name="Kubernetes Inc.",
    )

    assert extract_skills(raw) == (
        "AWS",
        "JavaScript",
        "Kubernetes",
        "Node.js",
        "PostgreSQL",
        "React",
        "SQL",
    )
    assert extract_skills(
        {"title": "Engineer", "category": "Python", "company_name": "Java"}
    ) == ()
    assert extract_skills({"title": "Pythonic engineer"}) == ()


@pytest.mark.parametrize(
    ("publication_date", "expected"),
    [
        ("2026-10-01T09:30:00Z", "timezone_present"),
        ("2026-10-01T09:30:00", "timezone_unspecified"),
        ("2026-10-01", "date_only"),
        (None, "missing"),
        ("soon", "invalid"),
    ],
)
def test_enrichment_reports_date_precision_honestly(
    monkeypatch, publication_date, expected
) -> None:
    mock_feed(monkeypatch, [sample_job(publication_date=publication_date)])

    result = RemotiveScanner().search_enriched("python")[0]

    assert result.publication_date_quality == expected
    if expected == "date_only":
        assert result.job.publication_date == "2026-10-01"
    if expected in {"missing", "invalid"}:
        assert result.job.publication_date is None


def test_enrichment_flags_only_same_listing_url_and_counts_sample_skills(
    monkeypatch,
) -> None:
    duplicate_url = "https://remotive.com/remote-jobs/python/one"
    mock_feed(
        monkeypatch,
        [
            sample_job(url=duplicate_url, tags=["Python"]),
            sample_job(url=f"{duplicate_url}?utm_source=test", tags=["AWS"]),
            sample_job(
                title="Python Support Engineer",
                url="https://remotive.com/remote-jobs/python/two",
                tags=["Python", "Python"],
            ),
        ],
    )

    results = RemotiveScanner().search_enriched("python", limit=3)

    assert len(results) == 3
    assert results[0].duplicate_of is None
    assert results[1].duplicate_of == results[0].job.url
    assert results[2].duplicate_of is None
    assert results[0].skills.count("Python") == 1
    assert results[2].job.title == "Python Support Engineer"


def test_missing_optional_fields_are_normalized_to_none(monkeypatch) -> None:
    mock_feed(
        monkeypatch,
        [sample_job(category="", candidate_required_location=None, salary=None)],
    )

    job = RemotiveScanner().search("python")[0]

    assert job.category is None
    assert job.eligible_location is None
    assert job.salary is None


def test_invalid_provider_listing_is_skipped(monkeypatch) -> None:
    mock_feed(
        monkeypatch,
        [
            sample_job(url="http://remotive.com/unsafe"),
            sample_job(url="https://other.example/job"),
            sample_job(url="https://[malformed"),
            {"title": "incomplete"},
        ],
    )

    assert RemotiveScanner().search("python") == []


def test_empty_results_are_returned_as_empty_list(monkeypatch) -> None:
    mock_feed(monkeypatch, [sample_job()])

    assert RemotiveScanner().search("accountant") == []


def test_timeout_becomes_market_data_error(monkeypatch) -> None:
    def timeout(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(market_scanner, "urlopen", timeout)

    with pytest.raises(MarketDataError, match="temporarily unavailable"):
        RemotiveScanner().search("python")


def test_malformed_json_becomes_market_data_error(monkeypatch) -> None:
    class InvalidJsonResponse(FakeResponse):
        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr(
        market_scanner,
        "urlopen",
        lambda request, timeout: InvalidJsonResponse({}),
    )

    with pytest.raises(MarketDataError, match="invalid JSON"):
        RemotiveScanner().search("python")


def test_invalid_response_shape_becomes_market_data_error(monkeypatch) -> None:
    monkeypatch.setattr(
        market_scanner,
        "urlopen",
        lambda request, timeout: FakeResponse({"jobs": "not-a-list"}),
    )

    with pytest.raises(MarketDataError, match="invalid jobs response"):
        RemotiveScanner().search("python")


def test_results_are_capped_and_feed_is_cached(monkeypatch) -> None:
    calls = 0

    def response(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse({"jobs": [sample_job() for _ in range(4)]})

    monkeypatch.setattr(market_scanner, "urlopen", response)
    scanner = RemotiveScanner()

    assert len(scanner.search("python", limit=2)) == 2
    assert len(scanner.search("python", limit=2)) == 2
    assert calls == 1


def test_market_endpoint_returns_attribution_and_small_result_set(monkeypatch) -> None:
    mock_feed(
        monkeypatch,
        [
            sample_job(),
            sample_job(
                title="Python Support Engineer",
                category=None,
                candidate_required_location="",
                salary=None,
            ),
        ],
    )
    import axon.main as api_main

    monkeypatch.setattr(api_main, "scanner", RemotiveScanner())
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get(
        "/market/jobs", params={"keyword": "  Python  ", "limit": 2}
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "keyword",
        "source",
        "source_info_url",
        "count",
        "jobs",
    }
    assert payload["keyword"] == "Python"
    assert payload["source"] == "Remotive"
    assert payload["source_info_url"] == "https://remotive.com/remote-jobs/api"
    assert payload["count"] == len(payload["jobs"]) == 2
    assert set(payload["jobs"][0]) == {
        "title",
        "company",
        "category",
        "eligible_location",
        "salary",
        "publication_date",
        "url",
        "source",
    }
    assert payload["jobs"][0] == {
        "title": "Python Platform Engineer",
        "company": "Example Co",
        "category": "Software Development",
        "eligible_location": "Worldwide",
        "salary": "$100,000 - $120,000",
        "publication_date": "2026-10-01T09:30:00",
        "url": "https://remotive.com/remote-jobs/software-dev/python-engineer-123",
        "source": "Remotive",
    }
    assert payload["jobs"][1]["category"] is None
    assert payload["jobs"][1]["eligible_location"] is None
    assert payload["jobs"][1]["salary"] is None


def test_market_endpoint_maps_provider_errors_to_502(monkeypatch) -> None:
    def unavailable(request, timeout):
        raise OSError("offline")

    monkeypatch.setattr(market_scanner, "urlopen", unavailable)
    import axon.main as api_main

    monkeypatch.setattr(api_main, "scanner", RemotiveScanner())
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/market/jobs", params={"keyword": "python"})

    assert response.status_code == 502
    assert response.json()["detail"] == "The job-data provider is temporarily unavailable."


def test_market_insights_endpoint_labels_sample_statistics(monkeypatch) -> None:
    mock_feed(
        monkeypatch,
        [
            sample_job(tags=["Python", "AWS"]),
            sample_job(
                title="Python Support Engineer",
                url="https://remotive.com/remote-jobs/python/support-456",
                tags=["Python", "Python"],
            ),
        ],
    )
    import axon.main as api_main

    monkeypatch.setattr(api_main, "scanner", RemotiveScanner())
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get(
        "/market/insights", params={"keyword": "python", "limit": 2}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "Remotive"
    assert payload["count"] == 2
    assert payload["skill_frequency"] == {
        "basis": "sample_based_returned_listings",
        "sample_size": 2,
        "job_counts": {"AWS": 1, "Python": 2},
    }
    assert payload["jobs"][0]["skills"] == ["AWS", "Python"]
    assert payload["jobs"][0]["publication_date_quality"] == "timezone_unspecified"
    assert payload["jobs"][0]["duplicate_of"] is None
