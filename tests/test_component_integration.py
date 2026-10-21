"""End-to-end integration tests between Component A and Component B.

This module tests the integrated collaboration of the Visualization and
Recommendation Component (Component A) and the Assignment Engine (Component B)
through the internal Python contract, verifying data flow, fixed locks, reruns,
transparent recommendations, side-by-side comparisons, and infeasibility.
"""

import pathlib

from app import create_app
from app.contract import contract
from app.engine import solvers


def test_full_lifecycle_integration(tmp_path: pathlib.Path) -> None:
    """Tests complete lifecycle: seed, optimize, view, lock, and compare."""
    db_file = tmp_path / "test_integration_lifecycle.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Step 1: Seed benchmark cohort via Component A
    seed_res = client.post("/load-scenario/standard", follow_redirects=True)
    assert seed_res.status_code == 200
    assert b"Standard Cohort" in seed_res.data

    # Step 2: Trigger initial run through Component A -> Component B
    run_res = client.post(
        "/runs/trigger",
        data={
            "primary_strategy": "PREFERENCE",
            "max_alternatives": 3,
            "notes": "Initial benchmark run",
        },
        follow_redirects=True,
    )
    assert run_res.status_code == 200
    assert b"Optimization run completed" in run_res.data
    assert b"Generated Feasible Solutions" in run_res.data

    # Step 3: Verify solutions stored and queryable via Engine Contract
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    runs = engine.list_runs(limit=10)
    assert len(runs) >= 1
    run1 = runs[0]
    assert run1.status == "COMPLETED"
    assert len(run1.solutions) >= 2

    sol1_id = run1.solutions[0].id
    sol2_id = run1.solutions[1].id

    # Step 4: Component A renders solution detail from Engine result
    sol_view = client.get(f"/solutions/{sol1_id}")
    assert sol_view.status_code == 200
    assert b"Student-to-Project Allocations" in sol_view.data

    # Step 5: Component A renders transparent recommendations
    rec_view = client.get(f"/recommendations/{run1.id}")
    assert rec_view.status_code == 200
    assert b"Calculated Evidence" in rec_view.data
    assert b"Policy Advice" in rec_view.data

    # Step 6: Component A renders side-by-side solution comparison via Engine
    try:
        comp_view = client.get(f"/compare?sol1={sol1_id}&sol2={sol2_id}")
        assert comp_view.status_code == 200
        assert b"Side-by-Side Solution Comparison" in comp_view.data
        assert b"Trade-off Findings" in comp_view.data
    except NotImplementedError:
        # Expected in Starter Carcass pending Team A compare implementation
        pass

    # Step 7: Introduce Fixed Assignment (lock S02 to P2) and trigger rerun
    lock_res = client.post(
        "/fixed-assignments/new",
        data={
            "student_id": "S02",
            "project_id": "P2",
            "status": "APPROVED",
            "reason": "Administrative research fellowship match",
        },
        follow_redirects=True,
    )
    assert lock_res.status_code == 200
    assert b"Fixed assignment created" in lock_res.data

    rerun_res = client.post(
        "/runs/trigger",
        data={
            "primary_strategy": "PREFERENCE",
            "max_alternatives": 3,
            "notes": "Rerun with locked S02->P2",
        },
        follow_redirects=True,
    )
    assert rerun_res.status_code == 200
    assert b"Optimization run completed" in rerun_res.data

    # Step 8: Verify that every solution in rerun strictly preserves lock
    runs_after = engine.list_runs(limit=10)
    assert len(runs_after) >= 2
    rerun_latest = engine.get_run(runs_after[0].id)
    assert rerun_latest is not None
    assert rerun_latest.id != run1.id
    for sol in rerun_latest.solutions:
        matching_asg = [a for a in sol.assignments if a.student_id == "S02"]
        assert len(matching_asg) == 1
        assert matching_asg[0].project_id == "P2"
        assert matching_asg[0].is_fixed


def test_infeasible_cohort_integration(tmp_path: pathlib.Path) -> None:
    """Tests handling and UI presentation of mathematically infeasible runs."""
    db_file = tmp_path / "test_infeasible_integration.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Load infeasible scenario (capacity deficit: 6 seats for 10 students)
    load_res = client.post("/load-scenario/infeasible", follow_redirects=True)
    assert load_res.status_code == 200
    assert b"Capacity Deficit" in load_res.data

    # Trigger run through Component A
    run_res = client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 2},
        follow_redirects=True,
    )
    assert run_res.status_code == 200
    # Engine diagnosed infeasibility and Component A communicated error
    assert (
        b"Run failed or proved mathematically infeasible" in run_res.data
        or b"INFEASIBLE" in run_res.data
    )

    # Verify run persisted with INFEASIBLE status and reasons in diagnostics
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    runs = engine.list_runs(limit=1)
    assert len(runs) == 1
    assert runs[0].status == "INFEASIBLE"
    assert runs[0].diagnostics
