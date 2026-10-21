"""Tests verifying the internal component contract and AssignmentEngine.

This module validates that AssignmentEngine strictly fulfills the
contract.AssignmentEngineContract interface, adhering to expected DTOs,
return types, status values, and persistence guarantees.
"""

import pathlib

import pytest

from app import create_app
from app.contract import contract, mocks
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


@pytest.mark.parametrize(
    ("has_students", "has_projects", "expected_errors"),
    [
        pytest.param(
            False,
            True,
            ["Student cohort cannot be empty."],
            id="no-students",
        ),
        pytest.param(
            True,
            False,
            ["Project catalog cannot be empty."],
            id="no-projects",
        ),
        pytest.param(
            False,
            False,
            [
                "Student cohort cannot be empty.",
                "Project catalog cannot be empty.",
            ],
            id="both-missing",
        ),
    ],
)
def test_contract_rejects_empty_datasets(
    has_students: bool,
    has_projects: bool,
    expected_errors: list[str],
) -> None:
    """ID-01/ID-02: The engine returns clear errors for missing datasets."""
    students = [models.Student(id="S01", display_name="Student 1")]
    projects = [
        models.Project(
            id="P1", title="Project 1", min_capacity=1, max_capacity=2
        )
    ]
    if not has_students:
        students = []
    if not has_projects:
        projects = []
    request = contract.RunRequest(students=students, projects=projects)
    engine = solvers.AssignmentEngine()

    outcome = engine.validate_inputs(request)

    assert isinstance(outcome, contract.ValidationOutcome)
    assert outcome.is_valid is False
    assert outcome.errors == expected_errors
    assert outcome.infeasibility_reasons == []


def test_contract_reports_identifier_and_parent_errors() -> None:
    """ID-04 to ID-07: Team A receives all structural errors without a crash."""
    request = contract.RunRequest(
        students=[
            models.Student(
                "S1",
                "Student 1",
                preferences=[models.Preference("S2", "P1", 1)],
            )
        ],
        projects=[
            models.Project(
                "P1",
                "Project 1",
                requirements=[models.ProjectRequirement("P2", "py")],
            )
        ],
        skills=[models.Skill("py", "Python"), models.Skill("py", " python ")],
        fixed_assignments=[
            models.FixedAssignment([], "P1"),  # type: ignore[arg-type]
        ],
    )
    engine = solvers.AssignmentEngine()

    outcome = engine.validate_inputs(request)

    assert isinstance(outcome, contract.ValidationOutcome)
    assert outcome.is_valid is False
    assert len(outcome.errors) == 5
    for message in [
        "Preference in student 'S1' references student 'S2'",
        "Requirement in project 'P1' references project 'P2'",
        "Duplicate skill identifier",
        "Duplicate skill name",
        "Fixed assignment #1 student identifier must be text",
    ]:
        assert any(message in error for error in outcome.errors), outcome.errors
    assert outcome.infeasibility_reasons == []


@pytest.mark.parametrize(
    ("choices", "expected_valid", "message"),
    [
        pytest.param([("P1", 1)], True, "at least 3", id="short-list"),
        pytest.param([], True, "unranked project", id="no-choices"),
        pytest.param(
            [("P1", 1), ("P1", 2)],
            False,
            "project 'P1' more than once",
            id="repeated-project",
        ),
        pytest.param(
            [("P1", 1), ("P2", 1)],
            False,
            "rank 1 more than once",
            id="tied-rank",
        ),
        pytest.param(
            [("P1", True)],
            False,
            "positive whole number",
            id="invalid-rank",
        ),
        pytest.param([("P1", 2)], False, "without gaps", id="rank-gap"),
        pytest.param(
            [("P99", 1)],
            False,
            "unknown project 'P99'",
            id="unknown-project",
        ),
    ],
)
def test_contract_returns_preference_diagnostics(
    choices: list[tuple[str, int]], expected_valid: bool, message: str
) -> None:
    """Return preference diagnostics through the existing contract."""
    student = models.Student(
        "S1",
        "Student 1",
        preferences=[
            models.Preference("S1", project_id, rank)
            for project_id, rank in choices
        ],
    )
    request = contract.RunRequest(
        students=[student],
        projects=[
            models.Project("P1", "Project 1"),
            models.Project("P2", "Project 2"),
            models.Project("P3", "Project 3"),
        ],
    )

    outcome = solvers.AssignmentEngine().validate_inputs(request)

    assert isinstance(outcome, contract.ValidationOutcome)
    assert outcome.is_valid is expected_valid
    messages = outcome.warnings if expected_valid else outcome.errors
    assert any("S1" in item and message in item for item in messages), messages
    assert outcome.infeasibility_reasons == []


def test_contract_reports_skill_errors_without_claiming_infeasibility() -> None:
    """Return several skill errors without claiming infeasibility."""
    request = contract.RunRequest(
        students=[models.Student("S1", "Student 1", skills={"py": True})],
        projects=[
            models.Project(
                "P1",
                "Project 1",
                requirements=[
                    models.ProjectRequirement(
                        "P1",
                        "py",
                        None,
                        "false",
                    ),  # type: ignore[arg-type]
                    models.ProjectRequirement("P1", "py", 2, True),
                ],
            )
        ],
        skills=[models.Skill("py", "Python")],
    )

    outcome = solvers.AssignmentEngine().validate_inputs(request)

    assert isinstance(outcome, contract.ValidationOutcome)
    assert outcome.is_valid is False
    assert len(outcome.errors) == 4
    assert any("Student 'S1'" in error for error in outcome.errors)
    assert any("Project 'P1'" in error for error in outcome.errors)
    assert outcome.infeasibility_reasons == []


@pytest.mark.parametrize("catalogue", [None, []])
def test_contract_distinguishes_omitted_and_empty_skill_catalogues(
    catalogue: list[models.Skill] | None,
) -> None:
    """Reject unknown skills when the supplied catalogue is empty."""
    request = contract.RunRequest(
        students=[models.Student("S1", "Student 1", skills={"py": 3})],
        projects=[
            models.Project(
                "P1",
                "Project 1",
                requirements=[models.ProjectRequirement("P1", "py", 2)],
            )
        ],
        skills=catalogue,
    )

    outcome = solvers.AssignmentEngine().validate_inputs(request)

    assert outcome.is_valid is (catalogue is None)
    if catalogue is None:
        assert any(
            "catalogue was omitted" in warning for warning in outcome.warnings
        )
    else:
        assert len(outcome.errors) == 2
        assert all("unknown skill 'py'" in error for error in outcome.errors)


@pytest.mark.parametrize("catalogue", [None, []])
def test_convenience_run_preserves_skill_catalogue_policy(
    catalogue: list[models.Skill] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve catalogue validation through the convenience API."""
    engine = solvers.AssignmentEngine()

    def validate_only(request: contract.RunRequest) -> models.AssignmentRun:
        """Validate the constructed request without executing a solver."""
        outcome = engine.validate_inputs(request)
        return models.AssignmentRun(
            "validation-only", diagnostics=outcome.to_dict()
        )

    monkeypatch.setattr(engine, "execute_run", validate_only)
    run = engine.run_assignment(
        students=[models.Student("S1", "Student 1", skills={"py": 3})],
        projects=[models.Project("P1", "Project 1")],
        skills=catalogue,
    )

    assert run.diagnostics["is_valid"] is (catalogue is None)
    if catalogue is None:
        assert any(
            "catalogue was omitted" in warning
            for warning in run.diagnostics["warnings"]
        )
    else:
        assert any(
            "unknown skill 'py'" in error for error in run.diagnostics["errors"]
        )
    assert run.solutions == []


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
    """Verify the mock engine implements the component contract."""
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
