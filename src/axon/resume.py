
"""Extract skills, education, and project experience from resume text."""

import re
from typing import TypedDict


class DetectedSkill(TypedDict):
    skill: str
    evidence: str
    detection_method: str
    status: str


class EducationEntry(TypedDict):
    institution: str | None
    qualification: str | None
    start_date: str | None
    end_date: str | None
    evidence: str
    status: str


class ProjectEntry(TypedDict):
    name: str | None
    description: str
    technologies: list[str]
    evidence: str
    status: str


SKILL_KEYWORDS = {
    "Python": [r"\bpython\b"],
    "Java": [r"\bjava\b"],
    "SQL": [r"\bsql\b"],
    "Excel": [r"\bexcel\b", r"\bspreadsheets?\b"],
    "Communication": [r"\bcommunication skills?\b"],
    "Leadership": [r"\bleadership\b", r"\bteam lead(?:er|ership)?\b"],
    "Project Management": [r"\bproject management\b"],
    "Data Analysis": [r"\bdata analysis\b", r"\bdata analytics\b"],
    "Machine Learning": [r"\bmachine learning\b"],
    "HTML": [r"\bhtml\b"],
    "CSS": [r"\bcss\b"],
    "JavaScript": [r"\bjavascript\b"],
}

# Only technologies explicitly mentioned in project descriptions are extracted.
TECHNOLOGY_KEYWORDS = {
    "Python": r"\bpython\b",
    "Java": r"\bjava\b",
    "SQL": r"\bsql\b",
    "Excel": r"\bexcel\b",
    "HTML": r"\bhtml\b",
    "CSS": r"\bcss\b",
    "JavaScript": r"\bjavascript\b",
    "scikit-learn": r"\bscikit[\s-]?learn\b",
}

EDUCATION_HEADINGS = {
    "education",
    "educational background",
    "academic background",
    "academic qualifications",
    "educational qualifications",
}

PROJECT_HEADINGS = {
    "projects",
    "project experience",
    "academic projects",
    "personal projects",
}

OTHER_SECTION_HEADINGS = {
    "experience",
    "work experience",
    "professional experience",
    "skills",
    "technical skills",
    "projects",
    "project experience",
    "academic projects",
    "personal projects",
    "certifications",
    "certificates",
    "achievements",
    "interests",
    "references",
    "activities",
    "languages",
    "summary",
    "professional summary",
}


def find_evidence(text: str, start: int, end: int) -> str:
    """Return concise, skill-specific evidence from resume text."""
    boundaries = re.compile(r"[.!?;\n]+")

    left = 0
    right = len(text)

    for boundary in boundaries.finditer(text):
        if boundary.end() <= start:
            left = boundary.end()
        elif boundary.start() >= end:
            right = boundary.start()
            break

    sentence = re.sub(r"\s+", " ", text[left:right]).strip()

    if sentence.count(",") >= 2:
        for item in sentence.split(","):
            item = item.strip()
            if re.search(
                r"\b" + re.escape(text[start:end]) + r"\b",
                item,
                flags=re.IGNORECASE,
            ):
                return item.strip(" ,")

    if sentence and len(sentence) <= 180:
        return sentence

    snippet_start = max(left, start - 35)
    snippet_end = min(right, end + 45)
    snippet = re.sub(
        r"\s+",
        " ",
        text[snippet_start:snippet_end],
    ).strip()

    return snippet or text[start:end]


def extract_skills(text: str) -> list[DetectedSkill]:
    """Return detected skills with evidence and verification status."""
    results: list[DetectedSkill] = []

    for skill, patterns in SKILL_KEYWORDS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)

            if match:
                results.append({
                    "skill": skill,
                    "evidence": find_evidence(
                        text,
                        match.start(),
                        match.end(),
                    ),
                    "detection_method": "keyword_match",
                    "status": "mentioned_not_verified",
                })
                break

    return results


def _normalise_heading(line: str) -> str:
    """Normalise a possible resume section heading."""
    return re.sub(r"[:\s]+$", "", line.strip()).casefold()


def _extract_year_range(
    text: str,
) -> tuple[str | None, str | None]:
    """Extract a simple year or year range without guessing."""
    match = re.search(
        r"\b((?:19|20)\d{2})\s*"
        r"(?:-|–|—|to)\s*"
        r"((?:19|20)\d{2}|present|current)\b",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        start_date = match.group(1)
        end_date = match.group(2)

        if end_date.casefold() in {"present", "current"}:
            end_date = end_date.title()

        return start_date, end_date

    single_year = re.search(r"\b((?:19|20)\d{2})\b", text)

    if single_year:
        return single_year.group(1), None

    return None, None


def extract_education(text: str) -> list[EducationEntry]:
    """Extract basic education entries from a labelled resume section."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    education_lines: list[str] = []
    in_education_section = False

    for line in lines:
        heading = _normalise_heading(line)

        if heading in EDUCATION_HEADINGS:
            in_education_section = True
            continue

        if in_education_section and heading in OTHER_SECTION_HEADINGS:
            break

        if in_education_section:
            education_lines.append(line)

    entries: list[EducationEntry] = []

    for line in education_lines:
        parts = [part.strip() for part in line.split("|") if part.strip()]

        if not parts:
            continue

        if parts[0].casefold().startswith(
            ("relevant interests:", "coursework:", "subjects:")
        ):
            continue

        institution: str | None = None
        qualification: str | None = None
        date_text = ""

        if len(parts) >= 2:
            institution = parts[0]
            qualification = parts[1]
            date_text = " ".join(parts[2:])
        else:
            start_date, end_date = _extract_year_range(parts[0])
            if start_date is not None and entries:
                entries[-1]["start_date"] = start_date
                entries[-1]["end_date"] = end_date
                entries[-1]["evidence"] += " | " + parts[0]
            continue

        start_date, end_date = _extract_year_range(date_text)

        if start_date is None:
            start_date, end_date = _extract_year_range(line)

        entries.append({
            "institution": institution,
            "qualification": qualification,
            "start_date": start_date,
            "end_date": end_date,
            "evidence": line,
            "status": "extracted_not_verified",
        })

    return entries


def extract_projects(text: str) -> list[ProjectEntry]:
    """Extract project activities from a labelled resume section.

    Each sentence becomes an entry. Project names are left as None
    because this format does not explicitly provide project titles.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    project_lines: list[str] = []
    in_project_section = False

    for line in lines:
        heading = _normalise_heading(line)

        if heading in PROJECT_HEADINGS:
            in_project_section = True
            continue

        if in_project_section and (
            heading in OTHER_SECTION_HEADINGS
            or heading in EDUCATION_HEADINGS
        ):
            break

        if in_project_section:
            project_lines.append(line)

    if not project_lines:
        return []

    section_text = " ".join(project_lines)

    # Split on sentence endings, not commas, so technology lists stay together.
    sentences = re.split(r"(?<=[.!?])\s+", section_text)

    results: list[ProjectEntry] = []

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        technologies = [
            technology
            for technology, pattern in TECHNOLOGY_KEYWORDS.items()
            if re.search(pattern, sentence, flags=re.IGNORECASE)
        ]

        results.append({
            "name": None,
            "description": sentence,
            "technologies": technologies,
            "evidence": sentence,
            "status": "extracted_not_verified",
        })

    return results


def test_extracts_project_experience_sentences():
    text = (
        "PROJECT EXPERIENCE\n"
        "Built a sample website using HTML, CSS, and JavaScript. "
        "Used Python to organise a small dataset and perform basic "
        "data analysis. Practised SQL queries to retrieve and filter records."
    )

    projects = extract_projects(text)

    assert len(projects) == 3
    assert projects[0]["name"] is None
    assert projects[0]["technologies"] == [
        "HTML",
        "CSS",
        "JavaScript",
    ]
    assert projects[1]["technologies"] == ["Python"]
    assert projects[2]["technologies"] == ["SQL"]
    assert all(
        project["status"] == "extracted_not_verified"
        for project in projects
    )


def test_project_extraction_stops_at_next_section():
    text = (
        "PROJECTS\n"
        "Built a website using HTML and CSS.\n"
        "EDUCATION\n"
        "Sample School | Higher Secondary Student"
    )

    projects = extract_projects(text)

    assert len(projects) == 1
    assert "website" in projects[0]["description"]


def test_no_project_section_returns_empty_list():
    text = "Built a website using HTML and CSS."
    assert extract_projects(text) == []


def test_project_without_technologies_does_not_invent_them():
    text = (
        "PROJECT EXPERIENCE\n"
        "Organised a school event and coordinated volunteers."
    )

    projects = extract_projects(text)

    assert len(projects) == 1
    assert projects[0]["technologies"] == []
    assert projects[0]["name"] is None
