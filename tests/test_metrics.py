"""Unit tests for analytical indicators, fairness, and comparison."""

import pytest

from app.domain import models
from app.engine import metrics


@pytest.mark.xfail(
    raises=NotImplementedError,
    reason="TODO (Team B): Implement calculate_gini",
)
def test_gini_calculation() -> None:
    """Verifies that Gini coefficient calculation matches expectations."""
    # Complete equality
    assert metrics.calculate_gini([2.0, 2.0, 2.0, 2.0]) == 0.0
    # Inequality
    gini = metrics.calculate_gini([1.0, 1.0, 1.0, 10.0])
    assert 0.0 < gini < 1.0


def test_skill_fit_calculation() -> None:
    """Verifies skill fit score computation for student and project."""
    student = models.Student(
        id="S1", display_name="S1", skills={"py": 3, "sql": 1}
    )
    project = models.Project(
        id="P1",
        title="P1",
        requirements=[
            models.ProjectRequirement(
                project_id="P1", skill_id="py", minimum_level=3
            ),
            models.ProjectRequirement(
                project_id="P1", skill_id="sql", minimum_level=2
            ),
        ],
    )

    fit, unmet = metrics.calculate_assignment_skill_fit(student, project)
    # py is 100% satisfied, sql is 1/2 = 50% satisfied. Average = 75%
    assert fit == 0.75
    assert unmet == ["sql"]


@pytest.mark.xfail(
    raises=NotImplementedError,
    reason="TODO (Team B): Implement compute_solution_indicators",
)
def test_solution_indicators_calculation() -> None:
    """Verifies full indicator computation for a solution."""
    students = [
        models.Student(
            id="S1",
            display_name="S1",
            preferences=[
                models.Preference(student_id="S1", project_id="P1", rank=1)
            ],
        ),
        models.Student(
            id="S2",
            display_name="S2",
            preferences=[
                models.Preference(student_id="S2", project_id="P1", rank=2)
            ],
        ),
    ]
    projects = [models.Project(id="P1", title="P1", max_capacity=2)]
    assignments = [
        models.Assignment(
            student_id="S1",
            project_id="P1",
            preference_rank=1,
            skill_fit_score=1.0,
        ),
        models.Assignment(
            student_id="S2",
            project_id="P1",
            preference_rank=2,
            skill_fit_score=0.8,
        ),
    ]

    indicators = metrics.compute_solution_indicators(
        students=students, projects=projects, assignments=assignments
    )

    assert indicators["feasibility"]["is_feasible"] is True
    assert indicators["efficiency"]["mean_skill_fit"] == 0.9
    assert indicators["fairness"]["mean_rank"] == 1.5
    assert indicators["fairness"]["worst_rank"] == 2
    assert indicators["fairness"]["unranked_count"] == 0
    assert indicators["capacity"]["overall_utilization_pct"] == 100.0


@pytest.mark.xfail(
    raises=NotImplementedError,
    reason="TODO (Team B): Implement compare_two_solutions",
)
def test_solution_comparison() -> None:
    """Verifies comparative trade-off calculation between two solutions."""
    sol_a = models.Solution(
        id="sol-a",
        run_id="run-1",
        alternative_number=1,
        strategy_name="PREFERENCE",
        assignments=[
            models.Assignment(
                student_id="S1",
                project_id="P1",
                preference_rank=1,
                skill_fit_score=0.5,
            ),
            models.Assignment(
                student_id="S2",
                project_id="P2",
                preference_rank=1,
                skill_fit_score=0.6,
            ),
        ],
        indicators={
            "efficiency": {"mean_skill_fit": 0.55},
            "fairness": {"mean_rank": 1.0, "unranked_count": 0},
        },
    )

    # In Solution B, S1 and S2 swapped projects
    sol_b = models.Solution(
        id="sol-b",
        run_id="run-1",
        alternative_number=2,
        strategy_name="SKILL_FIT",
        assignments=[
            models.Assignment(
                student_id="S1",
                project_id="P2",
                preference_rank=3,
                skill_fit_score=1.0,
            ),
            models.Assignment(
                student_id="S2",
                project_id="P1",
                preference_rank=2,
                skill_fit_score=0.9,
            ),
        ],
        indicators={
            "efficiency": {"mean_skill_fit": 0.95},
            "fairness": {"mean_rank": 2.5, "unranked_count": 0},
        },
    )

    comp = metrics.compare_two_solutions(sol_a, sol_b)
    assert comp["is_distinct"] is True
    assert comp["changed_students_count"] == 2
    assert comp["delta_mean_skill_fit"] == 0.4
    assert comp["delta_mean_rank"] == 1.5
    assert comp["rank_worsened_count"] == 2
