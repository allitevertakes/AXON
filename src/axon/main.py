
"""Minimal FastAPI application entry point."""

from dataclasses import asdict
from io import BytesIO
from typing import Annotated

import pdfplumber
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.db import (
    get_resume_profile,
    list_resume_profiles,
    save_resume_profile,
)
from axon.automation_risk import analyze_automation_risk
from axon.config import Settings
from axon.learning_path import build_learning_path
from axon.market_scanner import (
    MarketDataError,
    RemotiveScanner,
    REMOTIVE_INFO_URL,
    skill_frequency,
)
from axon.resume import extract_education, extract_projects, extract_skills
from axon.semantic_gap import analyze_explicit_skill_gap

scanner = RemotiveScanner()
MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MB


class SkillGapRequest(BaseModel):
    known_skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    optional_skills: list[str] = Field(default_factory=list)


class AutomationRiskRequest(BaseModel):
    title: str | None = None
    tasks: list[dict[str, object]] = Field(default_factory=list)


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

    @app.get("/market/insights", tags=["market"])
    def market_insights(
        keyword: Annotated[str, Query(min_length=2, max_length=100)],
        limit: Annotated[int, Query(ge=1, le=20)] = 5,
    ) -> dict[str, object]:
        """Return skill-frequency signals for the current job sample."""
        try:
            jobs = scanner.search_enriched(keyword, limit=limit)
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
            "skill_frequency": skill_frequency(jobs),
        }

    @app.post("/analysis/skill-gap", tags=["analysis"])
    def skill_gap(request: SkillGapRequest) -> dict[str, object]:
        """Compare explicit candidate skills with job requirements."""
        result = analyze_explicit_skill_gap(
            request.known_skills,
            request.required_skills,
            request.optional_skills,
        )
        return asdict(result)

    @app.post("/analysis/learning-path", tags=["analysis"])
    def learning_path(request: SkillGapRequest) -> dict[str, object]:
        """Recommend learning actions for missing job skills."""
        return build_learning_path(
            known_skills=request.known_skills,
            required_skills=request.required_skills,
            optional_skills=request.optional_skills,
        )

    @app.post("/analysis/automation-risk", tags=["analysis"])
    def automation_risk(request: AutomationRiskRequest) -> dict[str, object]:
        """Assess supplied task flags with a qualitative heuristic."""
        return asdict(analyze_automation_risk(request.model_dump()))

    @app.post("/profile/resume", tags=["profile"])
    async def upload_resume(
        file: Annotated[
            UploadFile, File(description="PDF resume, maximum 5 MB")
        ],
    ) -> dict[str, object]:
        """Extract resume details and persist the resulting profile."""
        try:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=415,
                    detail="Please upload a PDF file.",
                )

            content = await file.read(MAX_RESUME_SIZE + 1)

            if len(content) > MAX_RESUME_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Resume exceeds the 5 MB size limit.",
                )

            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=415,
                    detail="The uploaded file is not a valid PDF.",
                )

            try:
                with pdfplumber.open(BytesIO(content)) as pdf:
                    text = "\n".join(
                        page.extract_text() or "" for page in pdf.pages
                    )
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail="Could not read this PDF. Please try another file.",
                ) from exc

            if not text.strip():
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "No readable text found. "
                        "Scanned PDFs are not supported yet."
                    ),
                )

            skills = extract_skills(text)
            education = extract_education(text)
            projects = extract_projects(text)

            profile_id = save_resume_profile(
                filename=file.filename,
                skills=skills,
                education=education,
                projects=projects,
            )

            return {
                "profile_id": profile_id,
                "filename": file.filename,
                "extraction_method": "pdf_text_extraction",
                "skills_detected": len(skills),
                "skills": skills,
                "education_count": len(education),
                "education": education,
                "project_count": len(projects),
                "projects": projects,
                "notice": (
                    "Skills are keyword matches from resume text, "
                    "not verified qualifications."
                ),
            }
        finally:
            await file.close()

    @app.get("/profile/saved", tags=["profile"])
    def saved_profiles(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> dict[str, object]:
        """List saved resume profiles without returning their extracted content."""
        return {"profiles": list_resume_profiles(limit=limit)}

    @app.get("/profile/saved/{profile_id}", tags=["profile"])
    def saved_profile(profile_id: int) -> dict[str, object]:
        """Retrieve one saved resume profile."""
        result = get_resume_profile(profile_id)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Saved resume profile not found.",
            )
        return result

    return app


app = create_app()
