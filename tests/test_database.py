
from app.db import (
    get_resume_profile,
    list_resume_profiles,
    save_resume_profile,
)


def test_save_and_retrieve_profile(tmp_path):
    db_path = tmp_path / "test.db"

    profile_id = save_resume_profile(
        "resume.pdf",
        [{"skill": "Python"}],
        [{"institution": "Example School"}],
        [{"name": "AXON"}],
        db_path,
    )

    result = get_resume_profile(profile_id, db_path)

    assert result is not None
    assert result["filename"] == "resume.pdf"
    assert result["skills"] == [{"skill": "Python"}]
    assert result["education"] == [{"institution": "Example School"}]
    assert result["projects"] == [{"name": "AXON"}]


def test_missing_profile_returns_none(tmp_path):
    assert get_resume_profile(999, tmp_path / "test.db") is None


def test_profile_list_excludes_resume_content(tmp_path):
    db_path = tmp_path / "test.db"

    save_resume_profile(
        "first.pdf", [{"skill": "Python"}], [], [], db_path
    )
    save_resume_profile(
        "second.pdf", [{"skill": "SQL"}], [], [], db_path
    )

    results = list_resume_profiles(db_path=db_path)

    assert len(results) == 2
    assert results[0]["filename"] == "second.pdf"
    assert "skills" not in results[0]
