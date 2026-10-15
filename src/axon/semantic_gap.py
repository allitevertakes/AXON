"""Deterministic comparison of known and target-job skill names."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re

SkillInput = Iterable[object] | str | None
SynonymMap = Mapping[str, Iterable[str]] | None


_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "AWS": ("aws", "amazon web services"),
    "C#": ("c#", "c sharp"),
    "C++": ("c++", "c plus plus"),
    "Docker": ("docker",),
    "Java": ("java",),
    "JavaScript": ("javascript", "java script", "js"),
    "Kubernetes": ("kubernetes", "k8s"),
    "Node.js": ("node.js", "nodejs", "node js"),
    "PostgreSQL": ("postgresql", "postgres"),
    "Python": ("python",),
    "React": ("react", "react.js", "reactjs"),
    "SQL": ("sql",),
    "TypeScript": ("typescript", "type script"),
}

_ALIAS_TO_CANONICAL = {
    alias: canonical
    for canonical, aliases in _SKILL_ALIASES.items()
    for alias in aliases
}


@dataclass(frozen=True)
class SkillGapAnalysis:
    """Transparent comparison of supplied skills with a target job."""

    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]
    required_skill_count: int
    coverage_score: float | None
    optional_matched_skills: tuple[str, ...] = ()
    optional_missing_skills: tuple[str, ...] = ()
    required_skill_details: tuple["SkillClassification", ...] = ()
    optional_skill_details: tuple["SkillClassification", ...] = ()
    prioritized_gaps: tuple["LearningGap", ...] = ()


@dataclass(frozen=True)
class SkillClassification:
    """One skill's classification and the input-based reason for it."""

    skill: str
    status: str
    reason: str


@dataclass(frozen=True)
class LearningGap:
    """A missing skill and its deterministic priority tier."""

    skill: str
    priority: str
    reason: str


def _alias_map(synonyms: SynonymMap) -> dict[str, str]:
    aliases = dict(_ALIAS_TO_CANONICAL)
    if not isinstance(synonyms, Mapping):
        return aliases
    for canonical, variants in synonyms.items():
        normalized_name = _normalize_text(canonical)
        if normalized_name is None or not isinstance(variants, Iterable):
            continue
        display_name = canonical.strip()
        aliases[normalized_name] = display_name
        if isinstance(variants, str):
            variants = (variants,)
        for variant in variants:
            normalized_alias = _normalize_text(variant)
            if normalized_alias is not None:
                aliases[normalized_alias] = display_name
    return aliases


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value.strip().casefold())
    return normalized or None


def _canonical_skill(value: object, aliases: dict[str, str]) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    return aliases.get(normalized, normalized)


def _canonical_skills(values: object, aliases: dict[str, str]) -> set[str]:
    if isinstance(values, str):
        values = (values,)
    if isinstance(values, (bytes, bytearray, Mapping)) or not isinstance(
        values, Iterable
    ):
        return set()
    return {
        skill
        for value in values
        if (skill := _canonical_skill(value, aliases)) is not None
    }


def analyze_skill_gap(
    known_skills: SkillInput,
    required_skills: SkillInput,
    optional_skills: SkillInput = None,
    *,
    synonyms: SynonymMap = None,
) -> SkillGapAnalysis:
    """Compare names without inferring qualifications.

    Coverage is the number of unique required skills matched, divided by the
    number of unique valid required skills. It is ``None`` when there are no
    valid requirements, since that case has no meaningful denominator.
    """
    aliases = _alias_map(synonyms)
    known = _canonical_skills(known_skills, aliases)
    required = _canonical_skills(required_skills, aliases)
    optional = _canonical_skills(optional_skills, aliases) - required

    ordered_required = sorted(required, key=str.casefold)
    ordered_optional = sorted(optional, key=str.casefold)
    matched = tuple(skill for skill in ordered_required if skill in known)
    missing = tuple(skill for skill in ordered_required if skill not in known)
    optional_matched = tuple(skill for skill in ordered_optional if skill in known)
    optional_missing = tuple(skill for skill in ordered_optional if skill not in known)
    required_count = len(ordered_required)
    required_details = tuple(
        SkillClassification(
            skill=skill,
            status="matched" if skill in known else "missing",
            reason=(
                "A supplied candidate skill has the same normalized name."
                if skill in known
                else "No supplied candidate skill has the same normalized name."
            ),
        )
        for skill in ordered_required
    )
    optional_details = tuple(
        SkillClassification(
            skill=skill,
            status="matched" if skill in known else "missing",
            reason=(
                "A supplied candidate skill has the same normalized name."
                if skill in known
                else "No supplied candidate skill has the same normalized name."
            ),
        )
        for skill in ordered_optional
    )
    prioritized_gaps = tuple(
        [
            LearningGap(skill, "high", "Missing required job skill.")
            for skill in missing
        ]
        + [
            LearningGap(skill, "medium", "Missing optional job skill.")
            for skill in optional_missing
        ]
    )

    return SkillGapAnalysis(
        matched_skills=matched,
        missing_skills=missing,
        required_skill_count=required_count,
        coverage_score=(
            len(matched) / required_count if required_count else None
        ),
        optional_matched_skills=optional_matched,
        optional_missing_skills=optional_missing,
        required_skill_details=required_details,
        optional_skill_details=optional_details,
        prioritized_gaps=prioritized_gaps,
    )


def analyze_explicit_skill_gap(
    known_skills: SkillInput = None,
    required_skills: SkillInput = None,
    optional_skills: SkillInput = None,
    *,
    synonyms: SynonymMap = None,
) -> SkillGapAnalysis:
    """Caller boundary for explicitly supplied known and required skills.

    This function deliberately delegates without transforming either input or
    the result, so future API or partner callers share the existing behavior.
    """
    return analyze_skill_gap(
        known_skills, required_skills, optional_skills, synonyms=synonyms
    )
