
"""Deterministic learning recommendations from AXON skill-gap analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from axon.semantic_gap import SkillGapAnalysis, analyze_skill_gap


@dataclass(frozen=True)
class LearningRecommendation:
    skill: str
    priority: str
    reason: str
    suggested_action: str


def _suggested_action(skill: str) -> str:
    """Return a practical starting point without claiming mastery."""
    return (
        f"Study the fundamentals of {skill}, complete a guided tutorial, "
        f"and build a small project using {skill}."
    )


def recommend_learning_path(
    analysis: SkillGapAnalysis,
) -> list[LearningRecommendation]:
    """Convert identified skill gaps into ordered learning recommendations."""
    recommendations = [
        LearningRecommendation(
            skill=gap.skill,
            priority=gap.priority,
            reason=gap.reason,
            suggested_action=_suggested_action(gap.skill),
        )
        for gap in analysis.prioritized_gaps
    ]

    priority_order = {"high": 0, "medium": 1}
    return sorted(
        recommendations,
        key=lambda item: (
            priority_order.get(item.priority, 2),
            item.skill.casefold(),
        ),
    )


def build_learning_path(
    known_skills: Any = None,
    required_skills: Any = None,
    optional_skills: Any = None,
) -> dict[str, Any]:
    """Build a serializable skill-gap summary and learning recommendations."""
    analysis = analyze_skill_gap(
        known_skills,
        required_skills,
        optional_skills,
    )
    recommendations = recommend_learning_path(analysis)

    return {
        "matched_skills": list(analysis.matched_skills),
        "missing_skills": list(analysis.missing_skills),
        "optional_missing_skills": list(analysis.optional_missing_skills),
        "required_skill_count": analysis.required_skill_count,
        "coverage_score": analysis.coverage_score,
        "recommendations": [asdict(item) for item in recommendations],
    }
