"""Unit tests for optimization solvers and distinct alternative generation."""

import pathlib

import pytest

from app import create_app
from app.contract import contract
from app.domain import models
from app.engine import solvers
from app.persistence import database, repositories
from app.samples import demo_data


@pytest.mark.parametrize(
    ("min_capacity", "max_capacity", "student_count"),
    [
        pytest.param(0, 1, 1, id="zero-minimum"),
        pytest.param(2, 3, 2, id="at-minimum"),
        pytest.param(1, 2, 2, id="at-maximum"),
        pytest.param(2, 2, 2, id="equal-bounds"),
    ],
)
def test_real_engine_accepts_capacity_boundaries(
    tmp_path: pathlib.Path,
    min_capacity: int,
    max_capacity: int,
    student_count: int,
) -> None:
    """CAP-04: The real engine must assign every student within the bounds."""
    create_app(
        {"TESTING": True, "DATABASE_PATH": tmp_path / "capacity_test.db"}
    )
    students = []
    fixed_assignments = []
    for number in range(1, student_count + 1):
        student_id = f"S{number}"
        student = models.Student(
            id=student_id,
            display_name=f"Student {number}",
            preferences=[models.Preference(student_id, "P1", 1)],
        )
        students.append(student)
        fixed_assignments.append(
            models.FixedAssignment(student_id=student_id, project_id="P1")
        )
    project = models.Project(
        id="P1",
        title="Project 1",
        min_capacity=min_capacity,
        max_capacity=max_capacity,
    )
    projects = [project]
    if min_capacity == 0:
        projects.append(
            models.Project(
                id="P2", title="Unused project", min_capacity=0, max_capacity=1
            )
        )
    request = contract.RunRequest(
        students=students,
        projects=projects,
        fixed_assignments=fixed_assignments,
        max_alternatives=1,
    )
    engine = solvers.AssignmentEngine()

    run = engine.execute_run(request)

    assert run.status == "COMPLETED"
    assert len(run.solutions) == 1
    assignments = run.solutions[0].assignments
    assert len(assignments) == student_count
    assert {assignment.student_id for assignment in assignments} == {
        student.id for student in students
    }
    for assignment in assignments:
        assert assignment.project_id == "P1"
    assert min_capacity <= len(assignments) <= max_capacity


def test_assignment_strategy_abc() -> None:
    """Verifies that AssignmentStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        solvers.AssignmentStrategy()  # type: ignore[abstract]


def test_assignment_engine_initialization() -> None:
    """Initialize an engine with all supported solver strategies."""
    engine = solvers.AssignmentEngine()
    assert isinstance(engine, contract.AssignmentEngineContract)
    assert isinstance(engine.strategies, dict)
    assert set(engine.strategies) == {"PREFERENCE", "SKILL_FIT", "BALANCED"}


def test_distinct_alternatives_generation(tmp_path: pathlib.Path) -> None:
    """Verifies AssignmentEngine produces distinct alternatives."""
    benchmark = demo_data.get_standard_scenario()
    db = database.DatabaseManager(tmp_path / "alternatives.db")
    db.initialize_schema()
    engine = solvers.AssignmentEngine(repositories.RunRepository(db))

    run = engine.run_assignment(
        students=benchmark["students"],
        projects=benchmark["projects"],
        skills=benchmark["skills"],
        max_alternatives=3,
    )

    assert run.status == "COMPLETED"
    assert len(run.solutions) >= 2

    # Check distinctness: verify that each pair of solutions differs
    for i in range(len(run.solutions)):
        for j in range(i + 1, len(run.solutions)):
            pairs_i = {
                (a.student_id, a.project_id)
                for a in run.solutions[i].assignments
            }
            pairs_j = {
                (a.student_id, a.project_id)
                for a in run.solutions[j].assignments
            }
            assert pairs_i != pairs_j, (
                f"Solution {i + 1} and {j + 1} are duplicate allocations!"
            )
