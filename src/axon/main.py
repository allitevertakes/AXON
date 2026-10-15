
"""Minimal FastAPI application entry point."""

from io import BytesIO
from typing import Annotated

import pdfplumber
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from axon.config import Settings
from axon.market_scanner import (
    MarketDataError,
    RemotiveScanner,
    REMOTIVE_INFO_URL,
)
from axon.resume import extract_education, extract_projects, extract_skills

scanner = RemotiveScanner()
MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MB


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

    @app.post("/profile/resume", tags=["profile"])
    async def upload_resume(
        file: Annotated[UploadFile, File(description="PDF resume, maximum 5 MB")],
    ) -> dict[str, object]:
        """Extract text and identify skills mentioned in a PDF resume."""
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

            return {
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

    return app


app = create_app()
