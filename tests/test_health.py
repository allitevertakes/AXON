import pytest
from fastapi.testclient import TestClient

from axon.config import Settings
from axon.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_default_to_development(monkeypatch) -> None:
    monkeypatch.delenv("AXON_ENV", raising=False)

    assert Settings.from_env().environment == "development"


def test_settings_accept_valid_environment(monkeypatch) -> None:
    monkeypatch.setenv("AXON_ENV", "production")

    assert Settings.from_env().environment == "production"


def test_settings_reject_invalid_environment(monkeypatch) -> None:
    monkeypatch.setenv("AXON_ENV", "prod-ish")

    with pytest.raises(ValueError, match="AXON_ENV must be one of:"):
        Settings.from_env()


def test_docs_are_disabled_in_production() -> None:
    app = create_app(Settings(environment="production"))

    assert app.docs_url is None
    assert app.redoc_url is None
