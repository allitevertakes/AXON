"""Minimal FastAPI application entry point."""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from axon.config import Settings
from axon.market_scanner import (
    MarketDataError,
    RemotiveScanner,
    REMOTIVE_INFO_URL,
    skill_frequency,
)

scanner = RemotiveScanner()


class MarketJobResponse(BaseModel):
    """Stable job fields returned to AXON modules and API clients."""

    title: str
    company: str
    category: str | None
    eligible_location: str | None
    salary: str | None
    publication_date: str | None
    url: str
    source: str


class MarketJobsResponse(BaseModel):
    """Search metadata and matching Remotive listings."""

    keyword: str
    source: str
    source_info_url: str
    count: int
    jobs: list[MarketJobResponse]


class EnrichedMarketJobResponse(MarketJobResponse):
    skills: list[str]
    publication_date_quality: str
    duplicate_of: str | None


class SkillFrequencyResponse(BaseModel):
    basis: str
    sample_size: int
    job_counts: dict[str, int]


class MarketInsightsResponse(BaseModel):
    keyword: str
    source: str
    source_info_url: str
    count: int
    jobs: list[EnrichedMarketJobResponse]
    skill_frequency: SkillFrequencyResponse


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

    @app.get("/market/jobs", response_model=MarketJobsResponse, tags=["market"])
    def market_jobs(
        keyword: Annotated[str, Query(min_length=2, max_length=100)],
        limit: Annotated[int, Query(ge=1, le=20)] = 5,
    ) -> MarketJobsResponse:
        """Search Remotive's remote listings and return a small result set."""
        try:
            jobs = scanner.search(keyword, limit=limit)
        except MarketDataError as exc:
            raise HTTPException(
                status_code=502,
                detail="The job-data provider is temporarily unavailable.",
            ) from exc

        return MarketJobsResponse(
            keyword=keyword.strip(),
            source="Remotive",
            source_info_url=REMOTIVE_INFO_URL,
            count=len(jobs),
            jobs=[MarketJobResponse(**job.to_dict()) for job in jobs],
        )

    @app.get(
        "/market/insights", response_model=MarketInsightsResponse, tags=["market"]
    )
    def market_insights(
        keyword: Annotated[str, Query(min_length=2, max_length=100)],
        limit: Annotated[int, Query(ge=1, le=20)] = 5,
    ) -> MarketInsightsResponse:
        """Return conservative skill signals for this Remotive result sample."""
        try:
            jobs = scanner.search_enriched(keyword, limit=limit)
        except MarketDataError as exc:
            raise HTTPException(
                status_code=502,
                detail="The job-data provider is temporarily unavailable.",
            ) from exc

        enriched_jobs = [job.to_dict() for job in jobs]
        return MarketInsightsResponse(
            keyword=keyword.strip(),
            source="Remotive",
            source_info_url=REMOTIVE_INFO_URL,
            count=len(jobs),
            jobs=[EnrichedMarketJobResponse(**job) for job in enriched_jobs],
            skill_frequency=SkillFrequencyResponse(**skill_frequency(jobs)),
        )

    return app


app = create_app()
