import json

import pytest
from fastapi.testclient import TestClient

import axon.market_scanner as market_scanner
from axon.config import Settings
from axon.main import create_app
from axon.market_scanner import MarketDataError, RemotiveScanner


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
    mock_feed(monkeypatch, [sample_job()])
    import axon.main as api_main

    monkeypatch.setattr(api_main, "scanner", RemotiveScanner())
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/market/jobs", params={"keyword": "python"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "Remotive"
    assert payload["count"] == 1
    assert payload["jobs"][0]["url"].startswith("https://remotive.com/")


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
