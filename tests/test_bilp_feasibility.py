"""Milestone 1 tests exercise real CBC without the engine or mock fallback."""

import copy
from typing import Any

import pulp
import pytest

from app.domain import models, validation
from app.engine import solvers


class FeasibilityStrategy(solvers.AssignmentStrategy):
    """Expose the shared solver without introducing a production strategy."""

    def __init__(self) -> None:
        """Name the test-only feasibility strategy."""
        super().__init__("TEST_FEASIBILITY", "Hard constraints only")

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Keep hard-constraint tests independent of scoring choices."""
        return 0.0


def assert_feasible(
    students: list[models.Student],
    projects: list[models.Project],
    locks: list[models.FixedAssignment] | None = None,
) -> list[models.Assignment]:
    """Check actual returned objects against the input hard constraints."""
    before = copy.deepcopy((students, projects, locks))
    status, assignments, objective, diagnostics = FeasibilityStrategy().solve(
        students, projects, locks
    )
    assert (students, projects, locks) == before
    assert status == "FEASIBLE", diagnostics
    assert objective == 0.0
    assert diagnostics["assignment_verified"] is True
    assert diagnostics["metrics_computed"] is False
    assert diagnostics["variables_count"] == len(students) * len(projects)
    assert len(assignments) == len(students)
    assigned = {a.student_id: a.project_id for a in assignments}
    assert set(assigned) == {s.id for s in students}
    for project in projects:
        members = [s for s in students if assigned[s.id] == project.id]
        assert project.min_capacity <= len(members) <= project.max_capacity
        for req in project.requirements:
            if members and req.is_mandatory:
                assert any(
                    s.skills.get(req.skill_id, 0) >= req.minimum_level
                    for s in members
                )
    for lock in locks or []:
        assert assigned[lock.student_id] == lock.project_id
        assert next(
            a for a in assignments if a.student_id == lock.student_id
        ).is_fixed
    return assignments


@pytest.mark.parametrize(
    "minimum,maximum,count", [(0, 1, 1), (2, 3, 2), (1, 2, 2), (2, 2, 2)]
)
def test_capacity_boundaries(minimum: int, maximum: int, count: int) -> None:
    """Exercise the four existing engine boundary cases directly in CBC."""
    students = [models.Student(f"S{i}", f"S{i}") for i in range(count)]
    projects = [
        models.Project("P", "P", min_capacity=minimum, max_capacity=maximum)
    ]
    assert_feasible(students, projects)


@pytest.mark.parametrize("status", validation.FIXED_ASSIGNMENT_STATUSES)
def test_locks_and_safe_solver_names(status: str) -> None:
    """Locks override preferences; IDs that sanitize alike stay distinct."""
    students = [models.Student("S-1", "A"), models.Student("S_1", "B")]
    students[0].preferences = [models.Preference("S-1", "P_1", 1)]
    projects = [models.Project("P-1", "A"), models.Project("P_1", "B")]
    assignments = assert_feasible(
        students, projects, [models.FixedAssignment("S-1", "P-1", status)]
    )
    assert (
        next(a for a in assignments if a.student_id == "S-1").preference_rank
        is None
    )


def test_split_team_coverage_and_soft_requirements() -> None:
    """Different members cover skills; missing optional skills do not block."""
    students = [
        models.Student("A", "A", {"py": 3}),
        models.Student("B", "B", {"sql": 5}),
    ]
    project = models.Project(
        "P",
        "P",
        min_capacity=2,
        max_capacity=2,
        requirements=[
            models.ProjectRequirement("P", "py", 3, True),
            models.ProjectRequirement("P", "sql", 4, True),
            models.ProjectRequirement("P", "other", 5, False),
        ],
    )
    assert_feasible(students, [project])


@pytest.mark.parametrize("minimum", [0, 1])
def test_used_project_requires_qualified_member(minimum: int) -> None:
    """Coverage applies even when a used project has minimum zero."""
    students = [
        models.Student("A", "A", {"py": 2}),
        models.Student("B", "B", {"py": 3}),
    ]
    projects = [
        models.Project(
            "P",
            "P",
            min_capacity=minimum,
            requirements=[models.ProjectRequirement("P", "py", 3, True)],
        ),
        models.Project("Q", "Q"),
    ]
    assignments = assert_feasible(students, projects)
    assert {a.student_id: a.project_id for a in assignments} == {
        "A": "Q",
        "B": "P",
    }


def test_unused_project_needs_no_coverage() -> None:
    """An optional project with no qualified students remains empty."""
    projects = [
        models.Project(
            "P",
            "P",
            requirements=[models.ProjectRequirement("P", "py", 3, True)],
        ),
        models.Project("Q", "Q"),
    ]
    assignments = assert_feasible([models.Student("S", "S")], projects)
    assert assignments[0].project_id == "Q"


@pytest.mark.parametrize("minimum,maximum,count", [(0, 1, 2), (2, 2, 1)])
def test_capacity_infeasible_no_partial(
    minimum: int,
    maximum: int,
    count: int,
) -> None:
    """Capacity deficits never yield partial assignments."""
    result = FeasibilityStrategy().solve(
        [models.Student(str(i), str(i)) for i in range(count)],
        [models.Project("P", "P", min_capacity=minimum, max_capacity=maximum)],
    )
    assert result[:3] == ("INFEASIBLE", [], None)
    assert result[3]["infeasibility_reasons"]


def test_joint_infeasibility_reaches_cbc() -> None:
    """One qualified student cannot cover two required projects."""
    students = [models.Student("A", "A", {"py": 3}), models.Student("B", "B")]
    projects = [
        models.Project(
            p,
            p,
            min_capacity=1,
            requirements=[models.ProjectRequirement(p, "py", 3, True)],
        )
        for p in ["P", "Q"]
    ]
    assert validation.validate_cohort(students, projects).is_valid
    status, assignments, objective, info = FeasibilityStrategy().solve(
        students, projects
    )
    assert (status, assignments, objective) == ("INFEASIBLE", [], None)
    assert info["solver_status"] == "Infeasible"


def test_invalid_input_does_not_invoke_cbc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structural errors take priority over simultaneous capacity failure."""

    def forbidden(*args: Any, **kwargs: Any) -> None:
        """Ensure invalid inputs never reach the solver."""
        raise AssertionError("Solver must not run")

    monkeypatch.setattr(pulp.LpProblem, "solve", forbidden)
    students = [
        models.Student(
            "A", "A", preferences=[models.Preference("A", "missing", 1)]
        ),
        models.Student("B", "B"),
    ]
    result = FeasibilityStrategy().solve(students, [models.Project("P", "P")])
    assert result[:3] == ("INVALID_INPUT", [], None)


def test_exclusions_are_not_silently_ignored() -> None:
    """Excluding the only full assignment proves exhaustion."""
    result = FeasibilityStrategy().solve(
        [models.Student("S", "S")],
        [models.Project("P", "P")],
        excluded_solutions=[[("S", "P")]],
    )
    assert result[:3] == ("INFEASIBLE", [], None)
    assert result[3]["excluded_solutions_count"] == 1


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("stopped", "NOT_SOLVED"),
        ("unknown", "NOT_SOLVED"),
        ("incumbent", "FEASIBLE"),
        ("fractional", "FAILED"),
        ("missing", "FAILED"),
        ("nan", "FAILED"),
        ("partial", "FAILED"),
        ("error", "FAILED"),
        ("unbounded", "FAILED"),
    ],
)
def test_solver_termination_and_extraction(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected: str,
) -> None:
    """Simulate termination reliably instead of relying on timeout timing."""

    def controlled_solve(problem: pulp.LpProblem, solver: Any) -> int:
        """Supply CBC-style status pairs and controlled variable values."""
        if mode == "error":
            raise pulp.PulpSolverError("CBC unavailable")
        problem.status = pulp.LpStatusOptimal
        problem.sol_status = pulp.LpSolutionOptimal
        for variable in problem.variables():
            variable.varValue = {
                "fractional": 0.5,
                "missing": None,
                "nan": float("nan"),
                "partial": 0,
            }.get(mode, 1)
        if mode == "incumbent":
            problem.sol_status = pulp.LpSolutionIntegerFeasible
        if mode in ("stopped", "unknown", "unbounded"):
            problem.status = {
                "stopped": pulp.LpStatusNotSolved,
                "unknown": pulp.LpStatusUndefined,
                "unbounded": pulp.LpStatusUnbounded,
            }[mode]
            problem.sol_status = pulp.LpSolutionNoSolutionFound
        return problem.status

    monkeypatch.setattr(pulp.LpProblem, "solve", controlled_solve)
    status, assignments, objective, info = FeasibilityStrategy().solve(
        [models.Student("S", "S")], [models.Project("P", "P")]
    )
    assert status == expected
    assert objective == (0.0 if expected == "FEASIBLE" else None)
    assert info["optimality_proven"] is False
    assert bool(assignments) is (expected == "FEASIBLE")
    if mode in ("stopped", "unknown", "incumbent"):
        assert info["warnings"]
        assert not info["infeasibility_reasons"]


@pytest.mark.parametrize(
    "violation", ["duplicate", "unknown", "capacity", "skill", "lock"]
)
def test_independent_verifier_rejects_violations(violation: str) -> None:
    """The post-solve check catches each hard-constraint violation."""
    students = [models.Student("A", "A"), models.Student("B", "B")]
    projects = [
        models.Project("P", "P", max_capacity=2),
        models.Project("Q", "Q"),
    ]
    assignments = [models.Assignment("A", "P"), models.Assignment("B", "P")]
    locks = []
    if violation == "duplicate":
        assignments[1].student_id = "A"
    elif violation == "unknown":
        assignments[0].project_id = "missing"
    elif violation == "capacity":
        projects[0].max_capacity = 1
    elif violation == "skill":
        projects[0].requirements = [
            models.ProjectRequirement("P", "py", 1, True)
        ]
    else:
        locks = [models.FixedAssignment("A", "Q")]
    with pytest.raises(ValueError):
        solvers._verify_assignment(students, projects, locks, assignments)


@pytest.mark.parametrize("lock_elsewhere", [False, True])
def test_mandatory_coverage_impossible(lock_elsewhere: bool) -> None:
    """Missing qualifications or locks elsewhere prevent required coverage."""
    students = [
        models.Student("A", "A", {"py": 3 if lock_elsewhere else 2}),
        models.Student("B", "B"),
    ]
    projects = [
        models.Project(
            "P",
            "P",
            min_capacity=1,
            requirements=[models.ProjectRequirement("P", "py", 3, True)],
        ),
        models.Project("Q", "Q"),
    ]
    locks = [models.FixedAssignment("A", "Q")] if lock_elsewhere else []
    result = FeasibilityStrategy().solve(students, projects, locks)
    assert result[:3] == ("INFEASIBLE", [], None)
    assert result[3]["infeasibility_reasons"]


def test_positive_minimum_cannot_be_evaded() -> None:
    """Spare capacity elsewhere cannot justify evading a positive minimum."""
    students = [models.Student("A", "A"), models.Student("B", "B")]
    projects = [
        models.Project("P", "P", min_capacity=1, max_capacity=2),
        models.Project("Q", "Q", max_capacity=2),
    ]
    locks = [models.FixedAssignment(s.id, "Q") for s in students]
    assert validation.validate_cohort(
        students, projects, fixed_assignments=locks
    ).is_valid
    result = FeasibilityStrategy().solve(students, projects, locks)
    assert result[:3] == ("INFEASIBLE", [], None)
    assert result[3]["solver_status"] == "Infeasible"
