"""FIX-01 to FIX-05: reject bad locks without silently changing assignments."""

import pytest

from app.domain import models
from app.domain import validation


def test_conflicting_locks_name_both_projects() -> None:
    locks = [models.FixedAssignment("S1", "P1"), models.FixedAssignment("S1", "P2")]

    result = validation.validate_fixed_assignments(locks, {"S1"}, {"P1": 1, "P2": 1})

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert all(value in result.errors[0] for value in ["S1", "P1", "P2"])
    assert "Contradictory fixed assignment" in result.errors[0]
    assert result.infeasibility_reasons == []
    assert [lock.project_id for lock in locks] == ["P1", "P2"]


def test_duplicate_lock_is_rejected_without_counting_twice() -> None:
    lock = models.FixedAssignment("S1", "P1")

    result = validation.validate_fixed_assignments([lock, lock], {"S1"}, {"P1": 1})

    assert result.is_valid is False
    assert result.errors == ["Duplicate fixed assignment: student 'S1' is locked to project 'P1' more than once."]
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize(
    ("student_id", "project_id", "message"),
    [("ghost", "P1", "unknown student 'ghost'"), ("S1", "ghost", "unknown project 'ghost'")],
)
def test_unknown_lock_reference_is_rejected(student_id: str, project_id: str, message: str) -> None:
    result = validation.validate_fixed_assignments(
        [models.FixedAssignment(student_id, project_id)], {"S1"}, {"P1": 1}
    )

    assert result.is_valid is False
    assert any(message in error for error in result.errors)
    assert result.infeasibility_reasons == []


def test_unique_locks_exceeding_capacity_are_infeasible() -> None:
    result = validation.validate_fixed_assignments(
        [models.FixedAssignment("S1", "P1"), models.FixedAssignment("S2", "P1")],
        {"S1", "S2"}, {"P1": 1},
    )

    assert result.is_valid is False
    assert result.is_feasible is False
    assert len(result.infeasibility_reasons) == 1
    assert "(2)" in result.errors[0] and "P1" in result.errors[0] and "(1)" in result.errors[0]


@pytest.mark.parametrize("status", ["APPROVED", "MANDATORY", "CONDITIONAL"])
def test_supported_statuses_are_active_locks(status: str) -> None:
    result = validation.validate_fixed_assignments(
        [models.FixedAssignment("S1", "P1", status=status)], {"S1"}, {"P1": 1}
    )

    assert result.is_valid is True
    assert result.errors == []


@pytest.mark.parametrize("status", [None, "", "approved", "PENDING", "REJECTED", True, 1, [], {}])
def test_unsupported_lock_status_is_rejected(status: object) -> None:
    result = validation.validate_fixed_assignments(
        [models.FixedAssignment("S1", "P1", status=status)],  # type: ignore[arg-type]
        {"S1"}, {"P1": 1},
    )

    assert result.is_valid is False
    assert any("S1" in error and "unsupported status" in error for error in result.errors)


def test_invalid_lock_ids_do_not_crash_focused_validation() -> None:
    result = validation.validate_fixed_assignments(
        [models.FixedAssignment([], None)], {"S1"}, {"P1": 1}  # type: ignore[arg-type]
    )

    assert result.is_valid is False
    assert len(result.errors) == 2
    assert all("must be text" in error for error in result.errors)


def test_contract_rejects_bad_lock_status() -> None:
    from app.contract import contract
    from app.engine import solvers

    request = contract.RunRequest(
        students=[models.Student("S1", "Student 1")], projects=[models.Project("P1", "Project 1")],
        fixed_assignments=[models.FixedAssignment("S1", "P1", status="PENDING")],
    )

    result = solvers.AssignmentEngine().validate_inputs(request)

    assert result.is_valid is False
    assert any("unsupported status" in error for error in result.errors)


@pytest.mark.parametrize("capacity", [None, "1", 1.5, 0, True])
def test_focused_lock_validation_rejects_bad_saved_capacity(capacity: object) -> None:
    result = validation.validate_fixed_assignments(
        [models.FixedAssignment("S1", "P1")], {"S1"}, {"P1": capacity}  # type: ignore[dict-item]
    )

    assert result.is_valid is False
    assert any("P1" in error and "capacity" in error for error in result.errors)
    assert result.infeasibility_reasons == []
