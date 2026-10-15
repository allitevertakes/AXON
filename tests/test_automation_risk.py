from axon.automation_risk import analyze_automation_risk


def test_routine_digital_rule_based_task_has_explainable_high_potential() -> None:
    report = analyze_automation_risk(
        {
            "title": "Operations analyst",
            "tasks": [
                {
                    "name": "Reconcile standard records",
                    "routine": True,
                    "digital": True,
                    "rule_based": True,
                }
            ],
        }
    )

    result = report.tasks[0]
    assert result.assessment == "higher_exposure_potential"
    assert result.score == 3
    assert result.known_factor_count == 3
    assert {factor.name for factor in result.factors} == {
        "routine",
        "digital",
        "rule_based",
    }
    assert "automating parts" in result.explanation
    assert result.limitations


def test_human_centered_and_adaptive_task_has_lower_potential() -> None:
    report = analyze_automation_risk(
        {
            "tasks": [
                {
                    "name": "Support a distressed client",
                    "human_judgment": True,
                    "interpersonal": True,
                    "contextual_decisions": True,
                    "physical_adaptability": True,
                }
            ]
        }
    )

    result = report.tasks[0]
    assert result.assessment == "lower_exposure_potential"
    assert result.score == -4
    assert all(factor.direction == "decreases" for factor in result.factors)
    assert "tools may still assist" in result.explanation


def test_mixed_task_signals_are_not_hidden_by_the_net_score() -> None:
    report = analyze_automation_risk(
        {
            "tasks": [
                {
                    "name": "Review routine cases and escalate exceptions",
                    "routine": True,
                    "digital": True,
                    "rule_based": True,
                    "human_judgment": True,
                }
            ]
        }
    )

    result = report.tasks[0]
    assert result.assessment == "mixed_or_context_dependent"
    assert result.score == 2
    assert "both automation-supporting and human-centered" in result.explanation


def test_job_summary_keeps_different_task_assessments_visible() -> None:
    report = analyze_automation_risk(
        {
            "title": "Mixed work",
            "tasks": [
                {"name": "Data entry", "routine": True, "digital": True},
                {
                    "name": "Coach a teammate",
                    "interpersonal": True,
                    "human_judgment": True,
                },
            ],
        }
    )

    assert [task.assessment for task in report.tasks] == [
        "higher_exposure_potential",
        "lower_exposure_potential",
    ]
    assert "1 higher exposure potential" in report.overall_summary
    assert "1 lower exposure potential" in report.overall_summary
    assert "not an occupation-level score" in report.overall_summary


def test_incomplete_and_empty_inputs_return_safe_insufficient_results() -> None:
    empty_task = analyze_automation_risk({"tasks": [{}]})
    empty_job = analyze_automation_risk({"title": "No task detail", "tasks": []})

    assert empty_task.tasks[0].assessment == "insufficient_data"
    assert empty_task.tasks[0].score is None
    assert len(empty_task.tasks[0].unknown_factors) == 7
    assert "No valid task records" in empty_job.overall_summary
    assert empty_job.tasks == ()


def test_malformed_input_and_malformed_task_records_are_reported_safely() -> None:
    invalid = analyze_automation_risk("not a job mapping")
    partially_invalid = analyze_automation_risk(
        {"title": 42, "tasks": [None, "task", {"routine": "yes"}]}
    )

    assert invalid.tasks == ()
    assert "not a structured job mapping" in invalid.overall_summary
    assert partially_invalid.job_title is None
    assert partially_invalid.rejected_task_count == 2
    assert partially_invalid.tasks[0].assessment == "insufficient_data"
    assert "Skipped 2 malformed" in partially_invalid.overall_summary


def test_assessments_are_reproducible_and_non_boolean_values_are_unknown() -> None:
    job = {
        "tasks": [
            {"name": "Classify incoming forms", "routine": True, "digital": 1}
        ]
    }

    first = analyze_automation_risk(job)
    second = analyze_automation_risk(job)

    assert first == second
    assert first.tasks[0].assessment == "insufficient_data"
    assert first.tasks[0].score == 1
    assert "digital" in first.tasks[0].unknown_factors
