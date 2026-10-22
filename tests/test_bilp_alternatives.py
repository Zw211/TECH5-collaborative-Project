"""Distinct alternatives, honest exhaustion, and interrupted searches."""

import copy
from typing import Any

import pytest

from app.domain import models
from app.engine import solvers


@pytest.mark.parametrize("count", [1, 3, 4])
@pytest.mark.parametrize(
    "strategy_class",
    [
        solvers.PreferenceOrientedSolver,
        solvers.SkillFitOrientedSolver,
        solvers.BalancedTradeoffSolver,
    ],
)
def test_k_distinct_with_locks_and_skills(
    count: int,
    strategy_class: type[solvers.AssignmentStrategy],
) -> None:
    """Every alternative preserves locks, capacities, and mandatory coverage."""
    students = [models.Student(str(i), str(i), {"py": 3}) for i in range(4)]
    projects = [
        models.Project(
            p,
            p,
            min_capacity=1,
            max_capacity=3,
            requirements=[models.ProjectRequirement(p, "py", 3, True)],
        )
        for p in ["P", "Q"]
    ]
    locks = [models.FixedAssignment("0", "P", "CONDITIONAL")]
    before = copy.deepcopy((students, projects, locks))
    results, info = solvers._generate_alternatives(
        strategy_class(), students, projects, locks, count
    )
    assert (students, projects, locks) == before
    assert len(results) == count
    assert info["stop_reason"] == "K_REACHED"
    seen = set()
    for assignments, score, diagnostics in results:
        solvers._verify_assignment(students, projects, locks, assignments)
        assert diagnostics["optimality_proven"]
        assert next(a for a in assignments if a.student_id == "0").is_fixed
        pairs = frozenset((a.student_id, a.project_id) for a in assignments)
        assert pairs not in seen
        seen.add(pairs)
        assert score is not None


@pytest.mark.parametrize("project_count", [1, 2])
def test_fewer_than_default_k(project_count: int) -> None:
    """Return fewer than K solutions without padding or false infeasibility."""
    results, info = solvers._generate_alternatives(
        solvers.PreferenceOrientedSolver(),
        [models.Student("S", "S")],
        [models.Project(str(i), str(i)) for i in range(project_count)],
    )
    assert len(results) == project_count
    assert info["requested_count"] == 3
    assert info["stop_reason"] == "EXHAUSTED"
    assert info["attempts"][-1]["status"] == "INFEASIBLE"


def test_ranked_alternatives_and_final_exhaustion() -> None:
    """Known scores descend under accumulated cuts; ties remain distinct."""
    student = models.Student(
        "S",
        "S",
        preferences=[
            models.Preference("S", "P", 1),
            models.Preference("S", "Q", 2),
        ],
    )
    projects = [models.Project(p, p) for p in ["P", "Q", "R", "T"]]
    results, info = solvers._generate_alternatives(
        solvers.PreferenceOrientedSolver(),
        [student],
        projects,
        max_alternatives=4,
    )
    assert [score for _, score, _ in results] == [1.0, 0.5, 0.0, 0.0]
    assert (
        info["stop_reason"] == "K_REACHED"
    )  # No fifth solve, no exhaustion claim.
    exclusions = [
        [(a.student_id, a.project_id) for a in assignments]
        for assignments, _, _ in results
    ]
    before = copy.deepcopy(exclusions)
    result = solvers.PreferenceOrientedSolver().solve(
        [student], projects, excluded_solutions=exclusions
    )
    assert result[0] == "INFEASIBLE"
    assert exclusions == before


@pytest.mark.parametrize(
    "exclusions",
    [
        [[]],
        [[("S", "P"), ("S", "Q")]],
        [[("other", "P")]],
        [[("S", "unknown")]],
        [[("S",)]],
        [[(["S"], "P")]],
        "invalid",
    ],
)
def test_malformed_exclusions(exclusions: Any) -> None:
    """Malformed cuts are invalid input, not mathematical infeasibility."""
    result = solvers.PreferenceOrientedSolver().solve(
        [models.Student("S", "S")],
        [models.Project("P", "P")],
        excluded_solutions=exclusions,
    )
    assert result[:3] == ("INVALID_INPUT", [], None)
    assert result[3]["solver_status"] == "NOT_RUN"


def test_duplicate_exclusions_are_one_cut() -> None:
    """Pair ordering does not create distinct exclusions."""
    students = [models.Student(s, s) for s in ["A", "B"]]
    projects = [models.Project(p, p) for p in ["P", "Q"]]
    result = solvers.PreferenceOrientedSolver().solve(
        students,
        projects,
        excluded_solutions=[[("A", "P"), ("B", "Q")], [("B", "Q"), ("A", "P")]],
    )
    assert result[0] == "FEASIBLE"
    assert result[3]["excluded_solutions_count"] == 1
    assert {(a.student_id, a.project_id) for a in result[1]} == {
        ("A", "Q"),
        ("B", "P"),
    }


@pytest.mark.parametrize("count", [0, 5, True, 1.5])
def test_invalid_k(count: Any) -> None:
    """Preserve the existing integer 1-to-4 request limit."""
    results, info = solvers._generate_alternatives(
        solvers.PreferenceOrientedSolver(), [], [], max_alternatives=count
    )
    assert results == []
    assert info["stop_reason"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "stop", ["NOT_SOLVED", "FAILED", "DUPLICATE", "NON_OPTIMAL_INCUMBENT"]
)
def test_stop_preserves_earlier_solutions(
    monkeypatch: pytest.MonkeyPatch,
    stop: str,
) -> None:
    """Keep earlier results and distinguish interruption from exhaustion."""
    strategy = solvers.PreferenceOrientedSolver()
    original = strategy.solve
    calls = 0
    first = None

    def controlled(*args: Any, **kwargs: Any) -> Any:
        """Use real solutions before a simulated interruption or duplicate."""
        nonlocal calls, first
        calls += 1
        if calls == 1:
            first = original(*args, **kwargs)
            return first
        if stop == "DUPLICATE":
            return first
        if stop == "NON_OPTIMAL_INCUMBENT":
            result = original(*args, **kwargs)
            result[3]["optimality_proven"] = False
            return result
        return stop, [], None, {"solver_status": stop}

    monkeypatch.setattr(strategy, "solve", controlled)
    results, info = solvers._generate_alternatives(
        strategy,
        [models.Student("S", "S")],
        [models.Project(p, p) for p in ["P", "Q"]],
    )
    assert calls == 2
    assert len(results) == (2 if stop == "NON_OPTIMAL_INCUMBENT" else 1)
    assert info["stop_reason"] == stop


def test_original_problem_infeasible() -> None:
    """Initial infeasibility has no feasible alternatives to preserve."""
    results, info = solvers._generate_alternatives(
        solvers.PreferenceOrientedSolver(),
        [models.Student(s, s) for s in ["A", "B"]],
        [models.Project("P", "P")],
    )
    assert results == []
    assert info["stop_reason"] == "INFEASIBLE"
