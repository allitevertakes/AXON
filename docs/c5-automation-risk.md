# C5 Automation Risk Analysis

`axon.automation_risk.analyze_automation_risk` is a deterministic, task-level
heuristic. It uses only caller-supplied structured task descriptions. It does
not need a job-description parser, resume extraction, network service, or
database, and it does not modify an API contract.

## Input contract

Pass a mapping with an optional `title` and a `tasks` sequence. Each task is a
mapping with an optional `name` and boolean flags:

```python
from axon.automation_risk import analyze_automation_risk

report = analyze_automation_risk(
    {
        "title": "Example role",
        "tasks": [
            {
                "name": "Reconcile standard records",
                "routine": True,
                "digital": True,
                "rule_based": True,
            },
            {
                "name": "Resolve an unusual customer concern",
                "human_judgment": True,
                "interpersonal": True,
                "contextual_decisions": True,
            },
        ],
    }
)

for task in report.tasks:
    print(task.task_name, task.assessment, task.score, task.factors)
print(report.overall_summary)
```

Recognized fields are `routine`, `digital`, `rule_based`, `human_judgment`,
`interpersonal`, `contextual_decisions`, and `physical_adaptability`. Only
actual booleans count as known evidence; missing or malformed values are listed
in `unknown_factors`. Non-mapping task entries are skipped and counted.

## Method

Each true automation-supporting flag contributes +1: routine/repeatable work,
digital inputs and outputs, and explicit rules. Each true human-centered flag
contributes -1: substantial human judgment, interpersonal interaction,
context-dependent decisions, and physical adaptability. False flags contribute
0. The raw integer `score` is the sum of these visible contributions; it is
not a probability, percentage, or validated outcome measure.

Fewer than two recognized flags yields `insufficient_data`. With at least two
known flags, simultaneous positive and negative signals yield
`mixed_or_context_dependent`, regardless of the net score, so opposing task
characteristics remain visible. Otherwise, scores of +2 or more are
`higher_exposure_potential`, scores of -2 or less are
`lower_exposure_potential`, and the remaining results are
`mixed_or_context_dependent`. Each factor includes its direction and rationale.

The report keeps every task assessment separate. Its summary counts the
qualitative categories without averaging tasks into an occupation-level score.
These labels indicate only how supplied task features line up with the stated
heuristic. They do not claim that an occupation will disappear or that an
individual task will be automated. The heuristic is not validated against
real-world automation outcomes; technology, economics, regulation, reliability,
and organizational changes are outside its scope.
