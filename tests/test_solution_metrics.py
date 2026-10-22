"""Milestone 4 rank penalties, individual gaps, and domain integration."""

import copy
import json

import pytest

from app.domain import models
from app.engine import metrics, solvers


def cohort() -> tuple[list[models.Student], list[models.Project]]:
    """Provide unequal preference lists and one member covering both skills."""
    students = [
        models.Student(
            "A",
            "A",
            {"py": 3, "sql": 3},
            preferences=[
                models.Preference("A", "P", 1),
                models.Preference("A", "Q", 2),
                models.Preference("A", "R", 3),
            ],
        ),
        models.Student("B", "B", preferences=[models.Preference("B", "P", 1)]),
    ]
    projects = [
        models.Project(
            "P",
            "P",
            max_capacity=2,
            requirements=[
                models.ProjectRequirement("P", "py", 3, True),
                models.ProjectRequirement("P", "sql", 3),
            ],
        ),
        models.Project("Q", "Q", max_capacity=2),
        models.Project("R", "R"),
    ]
    return students, projects


def build(choices: tuple[str, str], number: int = 1) -> models.Solution:
    """Create a solution using the complete shared cohort and real metrics."""
    students, projects = cohort()
    return solvers._build_solution(
        "run",
        number,
        "PREFERENCE",
        students,
        projects,
        (
            [models.Assignment(s.id, p) for s, p in zip(students, choices)],
            None,
            {"warnings": ["Existing warning"]},
        ),
    )


def test_individual_soft_gaps_not_team_coverage() -> None:
    """B lacks both skills; only SQL is soft, and A covers both for the team."""
    solution = build(("P", "P"))
    efficiency = solution.indicators["efficiency"]
    assert solution.indicators["feasibility"]["is_feasible"]
    assert efficiency["individual_unmet_soft_requirements_count"] == 1
    assert efficiency["unmet_soft_requirements_count"] == 1
    assert (
        efficiency["soft_requirement_count_scope"]
        == "individual_student_project_requirement"
    )
    assert efficiency["mean_skill_fit"] == 0.5
    assert solution.assignments[1].unmet_requirements == ["py", "sql"]
    assert any("not unmet team-level" in w for w in solution.warnings)


def test_ranked_and_unranked_statistics() -> None:
    """Actual ranks stay None while numerical statistics use shared M+1=4."""
    solution = build(("P", "Q"))
    assert solution.assignments[1].preference_rank is None
    fair = solution.indicators["fairness"]
    assert fair["max_preferences"] == 3
    assert fair["unranked_penalty"] == 4
    assert fair["rank_distribution"] == {"rank_1": 1}
    assert fair["unranked_count"] == 1
    assert fair["unranked_pct"] == 50.0
    assert fair["mean_rank"] == 2.5
    assert fair["worst_rank"] == 4
    assert fair["rank_variance"] == 2.25
    assert fair["rank_gini"] == pytest.approx(0.3)
    assert any("not an actual rank" in w for w in solution.warnings)
    capacity = solution.indicators["capacity"]
    assert capacity["overall_utilization_pct"] == 40.0
    assert capacity["projects"]["R"]["assigned_count"] == 0


def test_alternatives_use_same_cohort_penalty() -> None:
    """M is not inferred from ranks selected by a particular solution."""
    a, b = build(("P", "P")), build(("P", "Q"), 2)
    assert a.indicators["fairness"]["unranked_penalty"] == 4
    assert b.indicators["fairness"]["unranked_penalty"] == 4
    compared = metrics.compare_two_solutions(a, b)
    assert compared["delta_mean_rank"] == 1.5
    assert compared["delta_unranked_count"] == 1
    assert compared["rank_worsened_count"] == 1
    assert compared["changed_assignments"][0]["rank_delta"] == 3
    assert compared["changed_assignments"][0]["rank_b"] is None
    assert compared["delta_metrics"]["gini_delta"] == pytest.approx(0.3)
    reverse = metrics.compare_two_solutions(b, a)
    assert reverse["rank_improved_count"] == 1
    assert reverse["delta_mean_rank"] == -1.5
    same = metrics.compare_two_solutions(a, a)
    assert not same["is_distinct"]
    assert same["changed_assignments"] == []


def test_all_preferences_empty() -> None:
    """M=0 gives penalty one without pretending anyone submitted rank one."""
    students = [models.Student(s, s) for s in ["A", "B"]]
    assignments = [models.Assignment(s.id, "P") for s in students]
    indicators = metrics.compute_solution_indicators(
        students, [models.Project("P", "P", max_capacity=2)], assignments
    )
    fair = indicators["fairness"]
    assert fair["max_preferences"] == 0
    assert fair["unranked_penalty"] == 1
    assert fair["mean_rank"] == fair["worst_rank"] == 1
    assert fair["rank_gini"] == fair["rank_variance"] == 0
    assert fair["unranked_count"] == 2
    assert fair["rank_distribution"] == {}
    assert all(a.preference_rank is None for a in assignments)


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "unknown_student",
        "unknown_project",
        "missing",
        "capacity",
        "mandatory",
        "lock",
    ],
)
def test_invalid_assignments_are_not_feasible(case: str) -> None:
    """Diagnostics inspect actual decisions, not the solver success flag."""
    students, projects = cohort()
    assignments = [models.Assignment("A", "P"), models.Assignment("B", "P")]
    locks = []
    if case == "duplicate":
        assignments.append(models.Assignment("A", "Q"))
    elif case == "unknown_student":
        assignments[0].student_id = "missing"
    elif case == "unknown_project":
        assignments[0].project_id = "missing"
    elif case == "missing":
        assignments.pop()
    elif case == "capacity":
        projects[0].max_capacity = 1
    elif case == "mandatory":
        students[0].skills = {}
    else:
        locks = [models.FixedAssignment("B", "Q")]
    result = metrics.compute_solution_indicators(
        students, projects, assignments, locks
    )
    assert not result["feasibility"]["is_feasible"]
    assert result["feasibility"]["violations"]


def test_unused_optional_project_needs_no_mandatory_coverage() -> None:
    """The metrics agree with the solver's project-use policy."""
    students, projects = cohort()
    indicators = metrics.compute_solution_indicators(
        students,
        projects,
        [models.Assignment("A", "Q"), models.Assignment("B", "Q")],
    )
    assert indicators["feasibility"]["is_feasible"]


def test_empty_inputs_are_not_a_feasible_solution() -> None:
    """Empty invalid data does not crash or create a false feasibility claim."""
    indicators = metrics.compute_solution_indicators([], [], [])
    assert not indicators["feasibility"]["is_feasible"]
    assert indicators["capacity"]["overall_utilization_pct"] == 0
    assert indicators["fairness"]["mean_rank"] == 0


def test_real_alternatives_convert_and_serialize() -> None:
    """Exercise solver -> metrics -> Solution -> JSON -> RunComparison."""
    students, projects = cohort()
    locks = [models.FixedAssignment("A", "P")]
    results, _ = solvers._generate_alternatives(
        solvers.BalancedTradeoffSolver(), students, projects, locks
    )
    original = copy.deepcopy(results)
    solutions = [
        solvers._build_solution(
            "run", i, "BALANCED", students, projects, result, locks
        )
        for i, result in enumerate(results, start=1)
    ]
    assert results == original
    assert len({s.id for s in solutions}) == len(solutions)
    assert len(solutions) == 3
    for solution in solutions:
        assert solution.diagnostics["metrics_computed"]
        assert solution.indicators["feasibility"]["is_feasible"]
        assert solution.assignments[0].is_fixed
        assert solution.indicators["fairness"]["unranked_penalty"] == 4
        restored = models.Solution.from_dict(
            json.loads(json.dumps(solution.to_dict()))
        )
        assert restored.to_dict() == solution.to_dict()
    comparison = metrics.compare_two_solutions(solutions[0], solutions[1])
    restored_comparison = models.RunComparison.from_dict(comparison)
    assert restored_comparison.to_dict() == comparison


def test_solution_builder_rejects_invalid_assignment() -> None:
    """Reject a partial allocation instead of constructing a Solution."""
    students, projects = cohort()
    with pytest.raises(ValueError, match="every student"):
        solvers._build_solution(
            "run",
            1,
            "PREFERENCE",
            students,
            projects,
            ([models.Assignment("A", "P")], None, {}),
        )


def test_different_penalties_are_not_silently_compared() -> None:
    """Recorded rank scales must match for valid numerical comparisons."""
    a, b = build(("P", "P")), build(("P", "Q"), 2)
    b.indicators["fairness"]["unranked_penalty"] = 2
    with pytest.raises(ValueError, match="same cohort penalty"):
        metrics.compare_two_solutions(a, b)


def test_both_unranked_is_same_outcome() -> None:
    """Different unranked projects do not imply a preference improvement."""
    a, b = build(("P", "Q")), build(("P", "R"), 2)
    comparison = metrics.compare_two_solutions(a, b)
    row = comparison["changed_assignments"][0]
    assert row["rank_a"] is row["rank_b"] is None
    assert row["rank_delta"] == 0
    assert row["rank_change"] == "SAME"
    assert comparison["rank_improved_count"] == 0
    assert comparison["rank_worsened_count"] == 0


def test_legacy_missing_penalty_does_not_invent_rank_delta() -> None:
    """Legacy solutions keep stored metrics without an invented rank 99."""
    a, b = build(("P", "P")), build(("P", "Q"), 2)
    for solution in (a, b):
        del solution.indicators["fairness"]["unranked_penalty"]
    result = metrics.compare_two_solutions(a, b)
    assert result["changed_assignments"][0]["rank_delta"] is None
    assert any(
        "unavailable" in message for message in result["trade_off_summary"]
    )


@pytest.mark.parametrize("duplicate", [False, True])
def test_comparison_requires_same_unique_students(duplicate: bool) -> None:
    """Do not silently drop missing students or overwrite duplicate rows."""
    a, b = build(("P", "P")), build(("P", "Q"), 2)
    if duplicate:
        b.assignments.append(b.assignments[0])
    else:
        b.assignments.pop()
    with pytest.raises(ValueError, match="same uniquely assigned students"):
        metrics.compare_two_solutions(a, b)
