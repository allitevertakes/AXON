
from io import BytesIO

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from axon.main import app
from axon.resume import extract_education, extract_projects, extract_skills

client = TestClient(app)


def make_pdf(text: str) -> bytes:
    """Create a small PDF in memory for testing."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def test_resume_detects_skills():
    pdf_bytes = make_pdf("Python SQL HTML CSS JavaScript data analysis")

    response = client.post(
        "/profile/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["skills_detected"] == 6

    detected = {item["skill"] for item in data["skills"]}
    assert {
        "Python", "SQL", "HTML", "CSS", "JavaScript", "Data Analysis"
    } <= detected


def test_resume_rejects_non_pdf():
    response = client.post(
        "/profile/resume",
        files={"file": ("resume.txt", b"Python and SQL", "text/plain")},
    )

    assert response.status_code == 415


def test_resume_rejects_invalid_pdf():
    response = client.post(
        "/profile/resume",
        files={"file": ("resume.pdf", b"not a real PDF", "application/pdf")},
    )

    assert response.status_code == 415


def test_resume_rejects_empty_pdf_text():
    pdf_bytes = make_pdf("")

    response = client.post(
        "/profile/resume",
        files={"file": ("empty.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 422


def test_resume_rejects_oversized_file():
    oversized_content = b"%PDF-" + b"x" * (5 * 1024 * 1024)

    response = client.post(
        "/profile/resume",
        files={
            "file": (
                "large.pdf",
                oversized_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413


def test_detected_skills_include_evidence_and_status():
    skills = extract_skills("I used Python for data analysis.")

    assert len(skills) == 2

    for item in skills:
        assert item["evidence"]
        assert item["detection_method"] == "keyword_match"
        assert item["status"] == "mentioned_not_verified"


def test_unmentioned_skills_are_not_detected():
    skills = extract_skills("Interested in learning new technologies.")

    assert skills == []

def test_extracts_education_without_inventing_dates():
    text = (
        "EDUCATION\n"
        "Sample Senior Secondary School | Higher Secondary Student\n"
        "Relevant interests: computer science, technology, "
        "and problem-solving."
    )

    education = extract_education(text)

    assert len(education) == 1
    assert education[0]["institution"] == "Sample Senior Secondary School"
    assert education[0]["qualification"] == "Higher Secondary Student"
    assert education[0]["start_date"] is None
    assert education[0]["end_date"] is None
    assert education[0]["evidence"] == (
        "Sample Senior Secondary School | Higher Secondary Student"
    )
    assert education[0]["status"] == "extracted_not_verified"


def test_education_extraction_stops_at_next_section():
    text = (
        "EDUCATION\n"
        "Sample School | Higher Secondary Student\n"
        "SKILLS\n"
        "Python SQL"
    )

    education = extract_education(text)

    assert len(education) == 1
    assert education[0]["institution"] == "Sample School"


def test_no_education_section_returns_empty_list():
    text = "Python developer with experience in SQL and HTML."

    assert extract_education(text) == []


def test_extracts_education_year_range():
    text = (
        "EDUCATION\n"
        "Sample University | Bachelor of Technology | 2024-2028"
    )

    education = extract_education(text)

    assert len(education) == 1
    assert education[0]["start_date"] == "2024"
    assert education[0]["end_date"] == "2028"

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
        assert projects[0]["technologies"] == ["HTML", "CSS", "JavaScript"]
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
    assert projects[0]["technologies"] == ["HTML", "CSS", "JavaScript"]
    assert projects[1]["technologies"] == ["Python"]
    assert projects[2]["technologies"] == ["SQL"]
    assert all(
        project["status"] == "extracted_not_verified"
        for project in projects
    )