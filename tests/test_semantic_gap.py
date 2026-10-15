import pytest

from axon.semantic_gap import analyze_explicit_skill_gap, analyze_skill_gap


def test_skill_gap_normalizes_variants_and_scores_unique_requirements() -> None:
    result = analyze_skill_gap(
        known_skills=[" Python ", "JS", "Postgres", "Postgres", "Custom Tool"],
        required_skills=["python", "JavaScript", "POSTGRESQL", "AWS", "C++", "AWS"],
    )

    assert result.matched_skills == ("JavaScript", "PostgreSQL", "Python")
    assert result.missing_skills == ("AWS", "C++")
    assert result.required_skill_count == 5
    assert result.coverage_score == pytest.approx(3 / 5)


def test_empty_requirements_have_no_undefined_coverage_score() -> None:
    result = analyze_skill_gap([], [])

    assert result.matched_skills == ()
    assert result.missing_skills == ()
    assert result.required_skill_count == 0
    assert result.coverage_score is None


def test_no_known_skills_means_zero_coverage_for_valid_requirements() -> None:
    result = analyze_skill_gap([], ["Python", "AWS"])

    assert result.matched_skills == ()
    assert result.missing_skills == ("AWS", "Python")
    assert result.required_skill_count == 2
    assert result.coverage_score == 0.0


def test_unknown_skills_match_only_after_safe_text_normalization() -> None:
    result = analyze_skill_gap(
        known_skills=[" Internal Tool ", "Kubernetes-ish"],
        required_skills=["internal   tool", "kubernetes ish", "Other"],
    )

    assert result.matched_skills == ("internal tool",)
    assert result.missing_skills == ("kubernetes ish", "other")
    assert result.coverage_score == pytest.approx(1 / 3)


def test_blank_and_non_string_values_are_ignored() -> None:
    result = analyze_skill_gap(
        ["Python", "", None],  # type: ignore[list-item]
        [" ", None],  # type: ignore[list-item]
    )

    assert result.required_skill_count == 0
    assert result.coverage_score is None


def test_scalar_strings_are_single_skills_not_character_iterables() -> None:
    result = analyze_skill_gap("Python", "python")

    assert result.matched_skills == ("Python",)
    assert result.missing_skills == ()
    assert result.required_skill_count == 1
    assert result.coverage_score == 1.0


def test_non_iterable_inputs_are_treated_as_empty_skill_sets() -> None:
    result = analyze_skill_gap(None, 42)  # type: ignore[arg-type]

    assert result.matched_skills == ()
    assert result.missing_skills == ()
    assert result.required_skill_count == 0
    assert result.coverage_score is None


def test_explicit_caller_boundary_delegates_normal_inputs_unchanged() -> None:
    known = ["Python", "JS", "Postgres"]
    required = ["Python", "JavaScript", "PostgreSQL", "AWS"]

    result = analyze_explicit_skill_gap(known, required)

    assert result == analyze_skill_gap(known, required)
    assert result.matched_skills == ("JavaScript", "PostgreSQL", "Python")
    assert result.missing_skills == ("AWS",)
    assert result.coverage_score == pytest.approx(0.75)


def test_explicit_caller_boundary_handles_missing_inputs_like_core() -> None:
    no_inputs = analyze_explicit_skill_gap()
    missing_known = analyze_explicit_skill_gap(required_skills=["Python"])

    assert no_inputs == analyze_skill_gap(None, None)
    assert no_inputs.coverage_score is None
    assert missing_known == analyze_skill_gap(None, ["Python"])
    assert missing_known.missing_skills == ("Python",)
    assert missing_known.coverage_score == 0.0


def test_explicit_caller_boundary_ignores_invalid_inputs_like_core() -> None:
    result = analyze_explicit_skill_gap(
        known_skills=["Python", None, 42],
        required_skills=["Python", None, " "],
    )

    assert result == analyze_skill_gap(
        ["Python", None, 42], ["Python", None, " "]
    )
    assert result.matched_skills == ("Python",)
    assert result.missing_skills == ()
    assert result.coverage_score == 1.0


def test_configured_synonyms_are_used_without_fuzzy_equivalences() -> None:
    result = analyze_skill_gap(
        known_skills=["Acme Data Platform", "Kubernetes-ish"],
        required_skills=["ADP", "Kubernetes ish"],
        synonyms={"Acme Data Platform": ["ADP"]},
    )

    assert result.matched_skills == ("Acme Data Platform",)
    assert result.missing_skills == ("kubernetes ish",)


def test_optional_skills_are_reported_and_prioritized_after_required_gaps() -> None:
    result = analyze_skill_gap(
        known_skills=["Python"],
        required_skills=["Python", "AWS"],
        optional_skills=["Docker", "Git", "Python"],
    )

    assert result.optional_matched_skills == ()
    assert result.optional_missing_skills == ("Docker", "git")
    assert [(gap.skill, gap.priority) for gap in result.prioritized_gaps] == [
        ("AWS", "high"),
        ("Docker", "medium"),
        ("git", "medium"),
    ]
    details = {detail.skill: detail for detail in result.required_skill_details}
    assert details["Python"].reason.startswith("A supplied")
    assert details["AWS"].reason.startswith("No supplied")


def test_optional_matched_skills_and_empty_or_mapping_inputs_are_safe() -> None:
    result = analyze_skill_gap(
        known_skills=["Python"],
        required_skills={"skills": ["Python"]},  # type: ignore[arg-type]
        optional_skills="Python",
    )

    assert result.required_skill_count == 0
    assert result.optional_matched_skills == ("Python",)
    assert result.coverage_score is None
