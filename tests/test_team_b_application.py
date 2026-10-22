"""Team B integration checks through the real Flask application and SQLite."""

import dataclasses
import pathlib
from typing import Any

import flask.testing
import pytest

from app import create_app
from app.contract import mocks
from app.domain import models
from app.engine import recommendations, solvers
from app.persistence import database, repositories


@pytest.fixture
def client(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> flask.testing.FlaskClient:
    """Use a disposable database and reject any mock-engine fallback."""
    monkeypatch.setattr(database, "db_manager", database.db_manager)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        """Fail loudly if a route substitutes mock results."""
        raise AssertionError("Real-engine integration must not use mocks")

    monkeypatch.setattr(mocks.MockAssignmentEngine, "execute_run", forbidden)
    monkeypatch.setattr(
        mocks.MockAssignmentEngine, "compare_solutions", forbidden
    )
    app = create_app(
        {"TESTING": True, "DATABASE_PATH": tmp_path / "application.db"}
    )
    return app.test_client()


def verify_assignments(run: models.AssignmentRun) -> None:
    """Independently check persisted allocations against current inputs."""
    students = {s.id: s for s in repositories.StudentRepository().list_all()}
    projects = repositories.ProjectRepository().list_all()
    locks = repositories.FixedAssignmentRepository().list_all()
    signatures = set()
    for solution in run.solutions:
        assignments = solution.assignments
        assert len(assignments) == len(students)
        allocation = {a.student_id: a.project_id for a in assignments}
        assert set(allocation) == set(students)
        assert set(allocation.values()) <= {p.id for p in projects}
        signature = frozenset(allocation.items())
        assert signature not in signatures
        signatures.add(signature)
        for project in projects:
            members = [
                students[s] for s, p in allocation.items() if p == project.id
            ]
            assert project.min_capacity <= len(members) <= project.max_capacity
            if members:
                for requirement in project.requirements:
                    if requirement.is_mandatory:
                        assert any(
                            s.get_skill_level(requirement.skill_id)
                            >= requirement.minimum_level
                            for s in members
                        )
        for lock in locks:
            assert allocation[lock.student_id] == lock.project_id
            assert next(
                a for a in assignments if a.student_id == lock.student_id
            ).is_fixed
        assert {
            "mean_rank",
            "worst_rank",
            "unranked_count",
            "rank_gini",
            "rank_variance",
        } <= solution.indicators["fairness"].keys()
        assert {
            "mean_skill_fit",
            "unmet_soft_requirements_count",
            "individual_unmet_soft_requirements_count",
        } <= solution.indicators["efficiency"].keys()


@pytest.mark.parametrize("strategy", ["PREFERENCE", "SKILL_FIT", "BALANCED"])
def test_real_application_lifecycle(
    client: flask.testing.FlaskClient, strategy: str
) -> None:
    """Seed, optimize, render, recommend, compare, lock and rerun for real."""
    assert client.post("/load-scenario/standard").status_code == 302
    # Ensure mandatory coverage is exercised, not just vacuously checked.
    project = repositories.ProjectRepository().get_by_id("P1")
    project.requirements[0] = dataclasses.replace(
        project.requirements[0], is_mandatory=True
    )
    repositories.ProjectRepository().save(project)
    settings = {"primary_strategy": strategy, "max_alternatives": 3}
    response = client.post(
        "/runs/trigger", data=settings, follow_redirects=True
    )
    assert response.status_code == 200
    repo = repositories.RunRepository()
    first = repo.get_run(repo.list_runs()[0].id)
    assert first.status == "COMPLETED"
    assert first.configuration["engine"] == "AssignmentEngine"
    assert first.configuration["primary_strategy"] == strategy
    assert len(first.solutions) == 3
    verify_assignments(first)
    snapshot = first.to_dict()
    for solution in first.solutions:
        page = client.get(f"/solutions/{solution.id}")
        assert page.status_code == 200
        assert b"Student-to-Project Allocations" in page.data
    advice = recommendations.generate_recommendations(first.solutions)
    assert len(advice) == 3
    for item in advice:
        assert item.recommended_solution_id in {s.id for s in first.solutions}
        assert item.criteria_used and item.evidence and item.advice
    page = client.get(f"/recommendations/{first.id}")
    assert page.status_code == 200
    assert b"Calculated Evidence" in page.data
    a, b = first.solutions[:2]
    page = client.get(f"/compare?sol1={a.id}&sol2={b.id}")
    assert page.status_code == 200
    assert b"Changed Student Allocations" in page.data
    response = client.post(
        "/fixed-assignments/new",
        data={
            "student_id": "S02",
            "project_id": "P2",
            "status": "APPROVED",
            "reason": "Integration test lock",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Fixed assignment created" in response.data
    assert client.post("/runs/trigger", data=settings).status_code == 302
    runs = repo.list_runs()
    assert len(runs) == 2
    second = repo.get_run(next(r.id for r in runs if r.id != first.id))
    assert second.status == "COMPLETED"
    assert second.solutions
    verify_assignments(second)
    assert repo.get_run(first.id).to_dict() == snapshot


def test_infeasible_application_run(client: flask.testing.FlaskClient) -> None:
    """Persist an infeasible run without creating partial assignments."""
    assert client.post("/load-scenario/infeasible").status_code == 302
    response = client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 3},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"INFEASIBLE" in response.data
    repo = repositories.RunRepository()
    run = repo.get_run(repo.list_runs()[0].id)
    assert run.status == "INFEASIBLE"
    assert run.solutions == []
    assert run.diagnostics.get("reasons") or run.diagnostics.get("errors")


def test_warning_retains_visible_solution(
    client: flask.testing.FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate interruption after one real solution and check its UI access."""
    original = solvers.PreferenceOrientedSolver.solve
    calls = 0

    def interrupted(self: Any, *args: Any, **kwargs: Any) -> Any:
        """Solve once with CBC, then simulate a search without an incumbent."""
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(self, *args, **kwargs)
        return "NOT_SOLVED", [], None, {"solver_status": "Not Solved"}

    monkeypatch.setattr(solvers.PreferenceOrientedSolver, "solve", interrupted)
    client.post("/load-scenario/standard")
    response = client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 3},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"WARNING" in response.data
    repo = repositories.RunRepository()
    run = repo.get_run(repo.list_runs()[0].id)
    assert run.status == "WARNING"
    assert len(run.solutions) == 1
    verify_assignments(run)
    assert client.get(f"/solutions/{run.solutions[0].id}").status_code == 200
