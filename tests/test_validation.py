"""Unit tests for domain validation and feasibility checking."""

import pytest

from app.domain import models
from app.domain import validation


# Each label makes the deliberately invalid input clear in pytest's output.
INVALID_CAPACITIES = [
    pytest.param(None, id="missing"),
    pytest.param("", id="empty-text"),
    pytest.param(" ", id="spaces-only"),
    pytest.param("2", id="number-as-text"),
    pytest.param("two", id="word"),
    pytest.param(1.5, id="fraction"),
    pytest.param(2.0, id="whole-number-as-float"),
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
    pytest.param(float("nan"), id="not-a-number"),
    pytest.param(float("inf"), id="positive-infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
]


def test_empty_cohort_validation() -> None:
    """Verifies that empty cohort data is flagged as invalid."""
    res = validation.validate_cohort(students=[], projects=[])
    assert res.is_valid is False
    assert any("Student cohort cannot be empty" in err for err in res.errors)
    assert any("Project catalog cannot be empty" in err for err in res.errors)


def test_duplicate_identifiers() -> None:
    """Verifies detection of duplicate student and project IDs."""
    students = [
        models.Student(id="S01", display_name="Student 1"),
        models.Student(id="S01", display_name="Student 1 Duplicate"),
    ]
    projects = [
        models.Project(id="P1", title="Project 1"),
        models.Project(id="P1", title="Project 1 Duplicate"),
    ]
    res = validation.validate_cohort(students=students, projects=projects)
    assert res.is_valid is False
    assert any("Duplicate student identifier" in err for err in res.errors)
    assert any("Duplicate project identifier" in err for err in res.errors)


def test_capacity_errors() -> None:
    """CAP-03: Rejects a minimum capacity above the maximum capacity."""
    students = [models.Student(id="S01", display_name="Student 1")]
    projects = [
        models.Project(
            id="P1", title="Invalid Project", min_capacity=5, max_capacity=2
        )
    ]
    res = validation.validate_cohort(students=students, projects=projects)
    assert res.is_valid is False
    assert any(
        "P1" in err
        and "exceeding max capacity" in err
        and "5" in err
        and "2" in err
        for err in res.errors
    ), res.errors


@pytest.mark.parametrize("capacity", INVALID_CAPACITIES)
def test_minimum_capacity_must_be_an_integer(capacity: object) -> None:
    """CAP-01: Reports a bad minimum without crashing or calculating totals."""
    students = [models.Student(id="S01", display_name="Student 1")]
    project = models.Project(
        id="P1",
        title="Project 1",
        min_capacity=capacity,  # type: ignore[arg-type]
        max_capacity=3,
    )

    result = validation.validate_cohort(students, [project])

    assert result.is_valid is False
    assert any(
        "P1" in error
        and "minimum capacity" in error.lower()
        and "whole number" in error.lower()
        for error in result.errors
    ), result.errors
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("capacity", INVALID_CAPACITIES)
def test_maximum_capacity_must_be_an_integer(capacity: object) -> None:
    """CAP-01: Reports a bad maximum without crashing or calculating totals."""
    students = [models.Student(id="S01", display_name="Student 1")]
    project = models.Project(
        id="P1",
        title="Project 1",
        min_capacity=0,
        max_capacity=capacity,  # type: ignore[arg-type]
    )

    result = validation.validate_cohort(students, [project])

    assert result.is_valid is False
    assert any(
        "P1" in error
        and "maximum capacity" in error.lower()
        and "whole number" in error.lower()
        for error in result.errors
    ), result.errors
    assert result.infeasibility_reasons == []


def test_capacity_type_errors_are_reported_together() -> None:
    """CAP-01: Reports every bad field without using partial capacity totals."""
    students = [
        models.Student(id="S01", display_name="Student 1"),
        models.Student(id="S02", display_name="Student 2"),
    ]
    projects = [
        models.Project(
            id="P1",
            title="Project 1",
            min_capacity=None,  # type: ignore[arg-type]
            max_capacity="two",  # type: ignore[arg-type]
        ),
        models.Project(
            id="P2",
            title="Project 2",
            min_capacity="1",  # type: ignore[arg-type]
            max_capacity=None,  # type: ignore[arg-type]
        ),
        models.Project(
            id="P3", title="Project 3", min_capacity=0, max_capacity=1
        ),
    ]

    result = validation.validate_cohort(students, projects)

    assert result.is_valid is False
    assert len(result.errors) == 4
    for project_id in ["P1", "P2"]:
        assert any(
            project_id in error and "minimum capacity" in error
            for error in result.errors
        ), result.errors
        assert any(
            project_id in error and "maximum capacity" in error
            for error in result.errors
        ), result.errors
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("min_capacity", [-1, -2])
def test_negative_minimum_capacity_is_rejected(min_capacity: int) -> None:
    """CAP-02: Rejects a negative minimum and identifies the project."""
    students = [models.Student(id="S01", display_name="Student 1")]
    project = models.Project(
        id="P1",
        title="Project 1",
        min_capacity=min_capacity,
        max_capacity=3,
    )

    result = validation.validate_cohort(students, [project])

    assert result.is_valid is False
    assert any(
        "P1" in error and "negative min capacity" in error
        for error in result.errors
    ), result.errors


@pytest.mark.parametrize("max_capacity", [0, -1])
def test_non_positive_maximum_capacity_is_rejected(
    max_capacity: int,
) -> None:
    """CAP-02: Rejects a zero or negative maximum and identifies the project."""
    students = [models.Student(id="S01", display_name="Student 1")]
    project = models.Project(
        id="P1",
        title="Project 1",
        min_capacity=0,
        max_capacity=max_capacity,
    )

    result = validation.validate_cohort(students, [project])

    assert result.is_valid is False
    assert any(
        "P1" in error and "non-positive max capacity" in error
        for error in result.errors
    ), result.errors


def test_zero_minimum_capacity_is_allowed() -> None:
    """CAP-04: Allows minimum zero and the smallest valid maximum, one."""
    students = [models.Student(id="S01", display_name="Student 1")]
    project = models.Project(
        id="P1", title="Project 1", min_capacity=0, max_capacity=1
    )

    result = validation.validate_cohort(students, [project])

    assert result.is_valid is True
    assert result.is_feasible is True
    assert result.errors == []
    assert result.infeasibility_reasons == []


def test_cohort_at_minimum_capacity_is_allowed() -> None:
    """CAP-04: Allows two students when the project's minimum is two."""
    students = [
        models.Student(id="S01", display_name="Student 1"),
        models.Student(id="S02", display_name="Student 2"),
    ]
    project = models.Project(
        id="P1", title="Project 1", min_capacity=2, max_capacity=3
    )

    result = validation.validate_cohort(students, [project])

    assert result.is_valid is True
    assert result.is_feasible is True
    assert result.errors == []
    assert result.infeasibility_reasons == []


def test_cohort_at_maximum_capacity_is_allowed() -> None:
    """CAP-04: Allows two locked students when the maximum is two."""
    students = [
        models.Student(id="S01", display_name="Student 1"),
        models.Student(id="S02", display_name="Student 2"),
    ]
    project = models.Project(
        id="P1", title="Project 1", min_capacity=1, max_capacity=2
    )
    fixed_assignments = [
        models.FixedAssignment(student_id="S01", project_id="P1"),
        models.FixedAssignment(student_id="S02", project_id="P1"),
    ]

    result = validation.validate_cohort(
        students, [project], fixed_assignments=fixed_assignments
    )

    assert result.is_valid is True
    assert result.is_feasible is True
    assert result.errors == []
    assert result.infeasibility_reasons == []


def test_equal_minimum_and_maximum_capacity_is_allowed() -> None:
    """CAP-04: Allows two students when both capacity bounds are two."""
    students = [
        models.Student(id="S01", display_name="Student 1"),
        models.Student(id="S02", display_name="Student 2"),
    ]
    project = models.Project(
        id="P1", title="Project 1", min_capacity=2, max_capacity=2
    )

    result = validation.validate_cohort(students, [project])

    assert result.is_valid is True
    assert result.is_feasible is True
    assert result.errors == []
    assert result.infeasibility_reasons == []


def test_contradictory_fixed_assignments() -> None:
    """Verifies detection of contradictory fixed assignments."""
    students = [
        models.Student(id="S01", display_name="S1"),
        models.Student(id="S02", display_name="S2"),
    ]
    projects = [
        models.Project(id="P1", title="P1", max_capacity=1),
        models.Project(id="P2", title="P2", max_capacity=2),
    ]
    # S01 fixed to both P1 and P2
    fixed = [
        models.FixedAssignment(student_id="S01", project_id="P1"),
        models.FixedAssignment(student_id="S01", project_id="P2"),
    ]
    res = validation.validate_cohort(
        students=students, projects=projects, fixed_assignments=fixed
    )
    assert res.is_valid is False
    assert any("Contradictory fixed assignment" in err for err in res.errors)


def test_fixed_exceeding_capacity() -> None:
    """Verifies that fixed assignments exceeding capacity cause error."""
    students = [
        models.Student(id="S01", display_name="S1"),
        models.Student(id="S02", display_name="S2"),
    ]
    projects = [
        models.Project(id="P1", title="P1", max_capacity=1),
    ]
    # 2 fixed assignments to P1 which has max_capacity 1
    fixed = [
        models.FixedAssignment(student_id="S01", project_id="P1"),
        models.FixedAssignment(student_id="S02", project_id="P1"),
    ]
    res = validation.validate_cohort(
        students=students, projects=projects, fixed_assignments=fixed
    )
    assert res.is_feasible is False
    assert any("exceed its maximum capacity" in err for err in res.errors)


def test_aggregate_capacity_deficit() -> None:
    """Verifies detection of aggregate capacity deficit."""
    students = [
        models.Student(id="S01", display_name="S1"),
        models.Student(id="S02", display_name="S2"),
        models.Student(id="S03", display_name="S3"),
    ]
    projects = [
        models.Project(id="P1", title="P1", max_capacity=2),
    ]
    # 3 students, but total capacity is only 2
    res = validation.validate_cohort(students=students, projects=projects)
    assert res.is_feasible is False
    assert any("Insufficient overall capacity" in err for err in res.errors)
