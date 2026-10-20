"""Tests verifying the internal component contract and AssignmentEngine.

This module validates that AssignmentEngine strictly fulfills the
contract.AssignmentEngineContract interface, adhering to expected DTOs,
return types, status values, and persistence guarantees.
"""

import pathlib

import pytest

from app import create_app
from app.contract import contract
from app.contract import mocks
from app.domain import models
from app.engine import solvers
from app.samples import demo_data


def test_engine_implements_contract(tmp_path: pathlib.Path) -> None:
    """Verifies that AssignmentEngine inherits and implements the contract."""
    db_file = tmp_path / "test_contract.db"
    create_app({"TESTING": True, "DATABASE_PATH": db_file})

    engine = solvers.AssignmentEngine()
    assert isinstance(engine, contract.AssignmentEngineContract)


def test_contract_validate_inputs(tmp_path: pathlib.Path) -> None:
    """Tests validate_inputs through the contract interface."""
    db_file = tmp_path / "test_val_contract.db"
    create_app({"TESTING": True, "DATABASE_PATH": db_file})

    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()

    # Valid scenario
    scenario = demo_data.get_standard_scenario()
    req = contract.RunRequest(
        students=scenario["students"],
        projects=scenario["projects"],
        skills=scenario["skills"],
        fixed_assignments=scenario["fixed_assignments"],
    )
    outcome = engine.validate_inputs(req)
    assert isinstance(outcome, contract.ValidationOutcome)
    assert outcome.is_valid
    assert outcome.is_feasible
    assert not outcome.errors

    # Infeasible scenario: deficit capacity
    bad_projects = [
        models.Project(
            id="P_TINY",
            title="Tiny Project",
            min_capacity=1,
            max_capacity=1,
        )
    ]
    bad_req = contract.RunRequest(
        students=scenario["students"],
        projects=bad_projects,
        skills=scenario["skills"],
    )
    bad_outcome = engine.validate_inputs(bad_req)
    assert not bad_outcome.is_feasible
    assert bad_outcome.infeasibility_reasons


def test_contract_rejects_non_integer_capacity() -> None:
    """CAP-01: The engine returns a clear input error to its caller."""
    request = contract.RunRequest(
        students=[models.Student(id="S01", display_name="Student 1")],
        projects=[
            models.Project(
                id="P1",
                title="Project 1",
                min_capacity=0,
                max_capacity="2",  # type: ignore[arg-type]
            )
        ],
    )
    engine = solvers.AssignmentEngine()

    outcome = engine.validate_inputs(request)

    assert isinstance(outcome, contract.ValidationOutcome)
    assert outcome.is_valid is False
    assert any(
        "P1" in error
        and "maximum capacity" in error
        and "whole number" in error
        for error in outcome.errors
    ), outcome.errors
    assert outcome.infeasibility_reasons == []


def test_contract_execute_and_retrieval(tmp_path: pathlib.Path) -> None:
    """Tests execute_run, get_run, get_solution, and list_runs via contract."""
    db_file = tmp_path / "test_exec_contract.db"
    create_app({"TESTING": True, "DATABASE_PATH": db_file})

    scenario = demo_data.get_standard_scenario()
    request = contract.RunRequest(
        students=scenario["students"],
        projects=scenario["projects"],
        skills=scenario["skills"],
        fixed_assignments=scenario["fixed_assignments"],
        strategy_key="PREFERENCE",
        max_alternatives=2,
    )

    # 1. AssignmentEngine skeleton raises NotImplementedError for Team B
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    with pytest.raises(NotImplementedError):
        engine.execute_run(request)

    # 2. MockAssignmentEngine fulfills contract execution and persistence
    mock_engine: contract.AssignmentEngineContract = (
        mocks.MockAssignmentEngine()
    )
    run = mock_engine.execute_run(request)
    assert run.status == "COMPLETED"
    assert len(run.solutions) >= 1

    # Verify retrieval of run
    fetched_run = mock_engine.get_run(run.id)
    assert fetched_run is not None
    assert fetched_run.id == run.id
    assert len(fetched_run.solutions) == len(run.solutions)

    # Verify list_runs
    runs_list = mock_engine.list_runs(limit=10)
    assert any(r.id == run.id for r in runs_list)

    # Verify get_solution
    sol_id = run.solutions[0].id
    solution = mock_engine.get_solution(sol_id)
    assert solution is not None
    assert solution.id == sol_id
    assert len(solution.assignments) == len(scenario["students"])


def test_contract_compare_solutions(tmp_path: pathlib.Path) -> None:
    """Tests compare_solutions via contract."""
    db_file = tmp_path / "test_comp_contract.db"
    create_app({"TESTING": True, "DATABASE_PATH": db_file})

    scenario = demo_data.get_standard_scenario()
    request = contract.RunRequest(
        students=scenario["students"],
        projects=scenario["projects"],
        skills=scenario["skills"],
        fixed_assignments=scenario["fixed_assignments"],
        strategy_key="PREFERENCE",
        max_alternatives=2,
    )

    mock_engine: contract.AssignmentEngineContract = (
        mocks.MockAssignmentEngine()
    )
    run = mock_engine.execute_run(request)
    assert len(run.solutions) >= 2

    sol_a = run.solutions[0]
    sol_b = run.solutions[1]

    # Mock engine performs valid comparison
    comparison = mock_engine.compare_solutions(sol_a.id, sol_b.id)
    assert isinstance(comparison, models.RunComparison)
    assert comparison.solution_a_id == sol_a.id
    assert comparison.solution_b_id == sol_b.id
    assert isinstance(comparison.changed_assignments, list)
    assert isinstance(comparison.delta_metrics, dict)

    # Test non-existent solution raises KeyError
    with pytest.raises(KeyError):
        mock_engine.compare_solutions(sol_a.id, "non_existent_id")

    # AssignmentEngine delegates to metrics which raises NotImplementedError
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    with pytest.raises(NotImplementedError):
        engine.compare_solutions(sol_a.id, sol_b.id)


def test_mock_engine_provided() -> None:
    """Verifies that MockAssignmentEngine implements the contract out of the box."""
    mock_engine = mocks.MockAssignmentEngine()
    assert isinstance(mock_engine, contract.AssignmentEngineContract)

    scenario = demo_data.get_standard_scenario()
    val = mock_engine.validate_inputs(
        contract.RunRequest(
            students=scenario["students"], projects=scenario["projects"]
        )
    )
    assert isinstance(val, contract.ValidationOutcome)
    assert val.is_valid
    assert val.is_feasible

    # Empty cohort
    val_empty = mock_engine.validate_inputs(
        contract.RunRequest(students=[], projects=[])
    )
    assert not val_empty.is_feasible
