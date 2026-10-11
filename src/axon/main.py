"""Minimal FastAPI application entry point."""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from axon.config import Settings
from axon.market_scanner import MarketDataError, RemotiveScanner, REMOTIVE_INFO_URL

scanner = RemotiveScanner()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API app, optionally with explicit settings for tests."""
    app_settings = settings or Settings.from_env()
    app = FastAPI(
        title="AXON API",
        version="0.1.0",
        docs_url="/docs" if app_settings.environment != "production" else None,
        redoc_url="/redoc" if app_settings.environment != "production" else None,
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Report that the API process is responding."""
        return {"status": "ok"}

    @app.get("/market/jobs", tags=["market"])
    def market_jobs(
        keyword: Annotated[str, Query(min_length=2, max_length=100)],
        limit: Annotated[int, Query(ge=1, le=20)] = 5,
    ) -> dict[str, object]:
        """Search Remotive's remote listings and return a small result set."""
        try:
            jobs = scanner.search(keyword, limit=limit)
        except MarketDataError as exc:
            raise HTTPException(
                status_code=502,
                detail="The job-data provider is temporarily unavailable.",
            ) from exc

        return {
            "keyword": keyword.strip(),
            "source": "Remotive",
            "source_info_url": REMOTIVE_INFO_URL,
            "count": len(jobs),
            "jobs": [job.to_dict() for job in jobs],
        }

    return app


app = create_app()
