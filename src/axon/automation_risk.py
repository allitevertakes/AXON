"""Explainable, task-level automation exposure heuristic.

This module identifies task characteristics that may make parts of a task
more or less amenable to automation. It does not predict job loss or estimate
the probability that a task or occupation will be automated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


_SIGNALS: tuple[tuple[str, int, str], ...] = (
    (
        "routine",
        1,
        "Routine, repeatable work can be easier to specify and automate.",
    ),
    (
        "digital",
        1,
        "Work performed through digital inputs and outputs may suit software automation.",
    ),
    (
        "rule_based",
        1,
        "Explicit rules and stable procedures can make task steps easier to encode.",
    ),
    (
        "human_judgment",
        -1,
        "Substantial human judgment can require nuanced evaluation and accountability.",
    ),
    (
        "interpersonal",
        -1,
        "Interpersonal interaction can depend on trust, communication, and social context.",
    ),
    (
        "contextual_decisions",
        -1,
        "Context-dependent decisions can require adapting to circumstances not captured by fixed rules.",
    ),
    (
        "physical_adaptability",
        -1,
        "Physical work in changing environments can require flexible perception and action.",
    ),
)

_COMMON_LIMITATIONS = (
    "This is a qualitative heuristic based only on the supplied task description and flags.",
    "It is not validated against real-world automation outcomes and is not a probability or job-loss prediction.",
    "Feasibility also depends on technology, cost, regulation, reliability, and work redesign, which are not modeled.",
)


@dataclass(frozen=True)
class FactorAssessment:
    """An observed input characteristic and its directional contribution."""

    name: str
    present: bool
    direction: str
    points: int
    explanation: str


@dataclass(frozen=True)
class TaskRiskAssessment:
    """Transparent heuristic result for one task."""

    task_name: str
    assessment: str
    score: int | None
    known_factor_count: int
    factors: tuple[FactorAssessment, ...]
    unknown_factors: tuple[str, ...]
    explanation: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class AutomationRiskReport:
    """Per-task results and a non-averaged summary for one job description."""

    job_title: str | None
    tasks: tuple[TaskRiskAssessment, ...]
    rejected_task_count: int
    overall_summary: str
    limitations: tuple[str, ...]


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _assess_task(task: Mapping[str, object], index: int) -> TaskRiskAssessment:
    name = _clean_text(task.get("name")) or _clean_text(task.get("title"))
    task_name = name or f"Task {index}"

    observed: list[FactorAssessment] = []
    unknown: list[str] = []
    for field, points, explanation in _SIGNALS:
        value = task.get(field)
        if not isinstance(value, bool):
            unknown.append(field)
            continue
        observed.append(
            FactorAssessment(
                name=field,
                present=value,
                direction=("increases" if points > 0 else "decreases")
                if value
                else "no_signal",
                points=points if value else 0,
                explanation=explanation,
            )
        )

    known_count = len(observed)
    score = sum(factor.points for factor in observed)
    positive = any(factor.points > 0 for factor in observed)
    negative = any(factor.points < 0 for factor in observed)

    if known_count < 2:
        assessment = "insufficient_data"
        explanation = (
            "Fewer than two recognized task characteristics were supplied, "
            "so the evidence is insufficient for a directional assessment."
        )
        score_value: int | None = score if known_count else None
    elif positive and negative:
        assessment = "mixed_or_context_dependent"
        explanation = (
            "The task has both automation-supporting and human-centered signals; "
            "the factors are shown separately because a net score would hide that mix."
        )
        score_value = score
    elif score >= 2:
        assessment = "higher_exposure_potential"
        explanation = (
            "Several supplied characteristics support automating parts of this task; "
            "this does not imply the whole task or occupation can be automated."
        )
        score_value = score
    elif score <= -2:
        assessment = "lower_exposure_potential"
        explanation = (
            "Several supplied characteristics point to human-centered or adaptive work; "
            "tools may still assist parts of the task."
        )
        score_value = score
    else:
        assessment = "mixed_or_context_dependent"
        explanation = (
            "The supplied characteristics do not show a strong directional signal."
        )
        score_value = score

    return TaskRiskAssessment(
        task_name=task_name,
        assessment=assessment,
        score=score_value,
        known_factor_count=known_count,
        factors=tuple(observed),
        unknown_factors=tuple(unknown),
        explanation=explanation,
        limitations=_COMMON_LIMITATIONS,
    )


def analyze_automation_risk(job_info: object) -> AutomationRiskReport:
    """Assess supplied tasks independently without predicting job displacement.

    Expected input is a mapping with optional ``title`` and a ``tasks`` list.
    Each task is a mapping with an optional ``name`` and zero or more boolean
    fields named in :data:`_SIGNALS`. Unknown or non-boolean flags are treated
    as missing evidence. Malformed task records are counted and skipped.
    """
    if not isinstance(job_info, Mapping):
        return AutomationRiskReport(
            job_title=None,
            tasks=(),
            rejected_task_count=0,
            overall_summary="Input was not a structured job mapping; no tasks were assessed.",
            limitations=_COMMON_LIMITATIONS,
        )

    title = _clean_text(job_info.get("title"))
    task_values = job_info.get("tasks")
    if not isinstance(task_values, Sequence) or isinstance(
        task_values, (str, bytes, bytearray)
    ):
        task_values = ()

    assessments: list[TaskRiskAssessment] = []
    rejected = 0
    for index, task in enumerate(task_values, start=1):
        if not isinstance(task, Mapping):
            rejected += 1
            continue
        assessments.append(_assess_task(task, index))

    if not assessments:
        summary = "No valid task records were supplied; no task-level assessment is available."
    else:
        counts: dict[str, int] = {}
        for result in assessments:
            counts[result.assessment] = counts.get(result.assessment, 0) + 1
        labels = (
            ("higher_exposure_potential", "higher exposure potential"),
            ("mixed_or_context_dependent", "mixed or context-dependent"),
            ("lower_exposure_potential", "lower exposure potential"),
            ("insufficient_data", "insufficient data"),
        )
        parts = [
            f"{counts[key]} {label}"
            for key, label in labels
            if counts.get(key, 0)
        ]
        summary = (
            f"{len(assessments)} tasks assessed: "
            + ", ".join(parts)
            + ". Tasks are reported individually; this summary is not an occupation-level score."
        )
        if rejected:
            summary += f" Skipped {rejected} malformed task record(s)."

    return AutomationRiskReport(
        job_title=title,
        tasks=tuple(assessments),
        rejected_task_count=rejected,
        overall_summary=summary,
        limitations=_COMMON_LIMITATIONS,
    )
