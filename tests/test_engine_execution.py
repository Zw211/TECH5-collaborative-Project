"""Real contract execution and atomic SQLite persistence without Flask."""

import copy
import dataclasses
import pathlib
import sqlite3
from typing import Any

import pytest

from app.contract import contract
from app.domain import models
from app.engine import solvers
from app.persistence import database, repositories


@pytest.fixture
def engine(tmp_path: pathlib.Path) -> solvers.AssignmentEngine:
    """Construct a headless engine with an isolated initialized repository."""
    db = database.DatabaseManager(tmp_path / "engine.db")
    db.initialize_schema()
    return solvers.AssignmentEngine(repositories.RunRepository(db))


def request() -> contract.RunRequest:
    """Provide two feasible alternatives, a skill reference, and run notes."""
    return contract.RunRequest(
        students=[
            models.Student(
                "S",
                "Student",
                {"py": 3},
                preferences=[models.Preference("S", "P", 1)],
            )
        ],
        projects=[models.Project("P", "Project"), models.Project("Q", "Other")],
        skills=[models.Skill("py", "Python")],
        notes="Week 2 test",
    )


@pytest.mark.parametrize("strategy", ["PREFERENCE", "SKILL_FIT", "BALANCED"])
def test_execute_round_trip(
    engine: solvers.AssignmentEngine, strategy: str
) -> None:
    """Validate real solving, metrics, parent IDs, retrieval, and comparison."""
    req = dataclasses.replace(request(), strategy_key=strategy)
    original = copy.deepcopy(req)
    run = engine.execute_run(req)
    assert req == original
    assert run.status == "COMPLETED"
    assert len(run.solutions) == 2
    assert run.diagnostics["search"]["stop_reason"] == "EXHAUSTED"
    assert run.diagnostics["reasons"] == []
    assert run.configuration["notes"] == req.notes
    assert run.configuration["primary_strategy"] == strategy
    assert engine.get_run(run.id).to_dict() == run.to_dict()
    for i, solution in enumerate(run.solutions, start=1):
        assert solution.run_id == run.id and solution.alternative_number == i
        assert solution.indicators["feasibility"]["is_feasible"]
        assert engine.get_solution(solution.id).to_dict() == solution.to_dict()
    assert engine.list_runs(limit=1)[0].id == run.id
    assert engine.compare_solutions(*[s.id for s in run.solutions]).is_distinct


@pytest.mark.parametrize("invalid", [True, False])
def test_rejected_run_never_solves_or_saves_cohort(
    engine: solvers.AssignmentEngine,
    monkeypatch: pytest.MonkeyPatch,
    invalid: bool,
) -> None:
    """Distinguish structural errors from infeasibility; save diagnostics."""
    req = request()
    req.students.append(models.Student("T", "T"))
    req = dataclasses.replace(req, projects=[models.Project("P", "P")])
    if invalid:
        req.students[0].preferences = [models.Preference("S", "unknown", 1)]

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        """Fail if validation rejection reaches optimization."""
        raise AssertionError("must not solve")

    monkeypatch.setattr(solvers, "_generate_alternatives", forbidden)
    run = engine.execute_run(req)
    assert run.status == ("INVALID_INPUT" if invalid else "INFEASIBLE")
    assert not run.solutions
    assert engine.get_run(run.id) is not None
    assert repositories.StudentRepository(engine.run_repo.db).list_all() == []


@pytest.mark.parametrize("existing", [False, True])
def test_omitted_catalog(
    engine: solvers.AssignmentEngine, existing: bool
) -> None:
    """Only pre-existing skill rows may satisfy an omitted catalog."""
    if existing:
        repositories.SkillRepository(engine.run_repo.db).save(
            models.Skill("py", "Python")
        )
    run = engine.execute_run(dataclasses.replace(request(), skills=None))
    assert run.status == ("COMPLETED" if existing else "INVALID_INPUT")
    if not existing:
        assert "py" in run.diagnostics["errors"][0]
        assert repositories.SkillRepository(engine.run_repo.db).list_all() == []


def test_explicit_empty_catalog_rejects_references(
    engine: solvers.AssignmentEngine,
) -> None:
    """An empty catalog is not a request to load the database catalog."""
    repositories.SkillRepository(engine.run_repo.db).save(
        models.Skill("py", "Python")
    )
    run = engine.execute_run(dataclasses.replace(request(), skills=[]))
    assert run.status == "INVALID_INPUT"


@pytest.mark.parametrize(
    "stop,expected",
    [
        ("NOT_SOLVED", "WARNING"),
        ("FAILED", "FAILED"),
        ("NON_OPTIMAL_INCUMBENT", "WARNING"),
        ("DUPLICATE", "FAILED"),
    ],
)
def test_interrupted_search_retains_results(
    engine: solvers.AssignmentEngine,
    monkeypatch: pytest.MonkeyPatch,
    stop: str,
    expected: str,
) -> None:
    """Keep earlier verified solutions when later search is interrupted."""
    original = solvers._generate_alternatives

    def interrupted(*args: Any, **kwargs: Any) -> Any:
        """Keep the first real result and simulate later interruption."""
        results, info = original(*args, **kwargs)
        info["stop_reason"] = stop
        info["returned_count"] = 1
        return results[:1], info

    monkeypatch.setattr(solvers, "_generate_alternatives", interrupted)
    run = engine.execute_run(request())
    assert run.status == expected
    assert len(run.solutions) == 1
    assert engine.get_solution(run.solutions[0].id) is not None


@pytest.mark.parametrize(
    "stop,expected", [("NOT_SOLVED", "WARNING"), ("FAILED", "FAILED")]
)
def test_no_incumbent(
    engine: solvers.AssignmentEngine,
    monkeypatch: pytest.MonkeyPatch,
    stop: str,
    expected: str,
) -> None:
    """Unknown/failed solving must never be presented as infeasibility."""
    monkeypatch.setattr(
        solvers,
        "_generate_alternatives",
        lambda *args, **kwargs: ([], {"stop_reason": stop, "attempts": []}),
    )
    run = engine.execute_run(request())
    assert run.status == expected
    assert run.solutions == []
    assert engine.get_run(run.id) is not None


def test_rollback_preserves_old_cohort_and_history(
    engine: solvers.AssignmentEngine,
) -> None:
    """A failure inserting the new run rolls back preceding entity updates."""
    old_run = engine.execute_run(request())
    db = engine.run_repo.db
    before = repositories.StudentRepository(db).list_all()
    db.execute_statement(
        "CREATE TRIGGER fail_run BEFORE INSERT ON assignment_runs "
        "BEGIN SELECT RAISE(ABORT, 'test failure'); END;"
    )
    req = request()
    req.students[0].display_name = "Changed name"
    req.students.append(models.Student("T", "New student"))
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        engine.execute_run(req)
    assert repositories.StudentRepository(db).list_all() == before
    assert engine.get_run(old_run.id).to_dict() == old_run.to_dict()
    assert len(engine.list_runs()) == 1


def test_lock_rerun_preserves_history(engine: solvers.AssignmentEngine) -> None:
    """Apply locks to the new run without changing historical choices."""
    first = engine.execute_run(request())
    req = dataclasses.replace(
        request(), fixed_assignments=[models.FixedAssignment("S", "Q")]
    )
    second = engine.execute_run(req)
    assert second.id != first.id
    assert len(second.solutions) == 1
    assert second.solutions[0].assignments[0].project_id == "Q"
    assert second.solutions[0].assignments[0].is_fixed
    assert engine.get_run(first.id).to_dict() == first.to_dict()
