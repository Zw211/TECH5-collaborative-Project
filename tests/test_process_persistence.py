"""Verify the real application survives a complete Python process restart."""

import dataclasses
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

from app import create_app
from app.engine import metrics, solvers
from app.persistence import database, repositories


def _application_phase(mode: str, directory: pathlib.Path) -> None:
    """Write or retrieve one run using a fresh application and connections."""
    app = create_app(
        {"TESTING": True, "DATABASE_PATH": directory / "restart.db"}
    )
    assert not app.config["DATABASE_STARTUP_FAILED"]
    snapshot_path = directory / "expected.json"
    engine = solvers.AssignmentEngine()
    with app.test_client() as client:
        if mode == "write":
            assert client.post("/load-scenario/standard").status_code == 302
            response = client.post(
                "/runs/trigger",
                data={
                    "primary_strategy": "PREFERENCE",
                    "max_alternatives": 3,
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            run = engine.get_run(engine.list_runs()[0].id)
            assert run is not None
            assert run.status == "COMPLETED"
            assert run.configuration["engine"] == "AssignmentEngine"
            assert len(run.solutions) == 3
            assert all(len(s.assignments) == 10 for s in run.solutions)
            snapshot_path.write_text(
                json.dumps(dataclasses.asdict(run)), encoding="utf-8"
            )
        else:
            expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
            run = engine.get_run(expected["id"])
            assert run is not None
            assert json.loads(json.dumps(dataclasses.asdict(run))) == expected
            assert engine.list_runs()[0].id == run.id
            assert client.get(f"/runs/{run.id}").status_code == 200
            students = repositories.StudentRepository().list_all()
            projects = repositories.ProjectRepository().list_all()
            locks = repositories.FixedAssignmentRepository().list_all()
            for solution in run.solutions:
                assert engine.get_solution(solution.id) == solution
                assert (
                    client.get(f"/solutions/{solution.id}").status_code == 200
                )
                calculated = metrics.compute_solution_indicators(
                    students, projects, solution.assignments, locks
                )
                assert json.loads(json.dumps(calculated)) == solution.indicators
        with database.db_manager.connection() as conn:
            for table, count in (
                ("assignment_runs", 1),
                ("solutions", 3),
                ("assignments", 30),
            ):
                assert (
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    == count
                )
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            for column in ("solution_id", "student_id", "project_id"):
                conn.execute("SAVEPOINT invalid_reference")
                try:
                    conn.execute(
                        f"UPDATE assignments SET {column} = ? "
                        "WHERE id = (SELECT MIN(id) FROM assignments)",
                        ("nonexistent",),
                    )
                except sqlite3.IntegrityError:
                    pass
                else:
                    raise AssertionError(f"Foreign key not enforced: {column}")
                finally:
                    conn.execute("ROLLBACK TO invalid_reference")
                    conn.execute("RELEASE invalid_reference")


def test_persistence_across_python_processes(tmp_path: pathlib.Path) -> None:
    """Exit the writer before reopening its SQLite file in a new process."""
    root = pathlib.Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        for mode in ("write", "read"):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tests.test_process_persistence",
                    mode,
                    directory,
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
    assert not pathlib.Path(directory).exists()


if __name__ == "__main__":
    _application_phase(sys.argv[1], pathlib.Path(sys.argv[2]))
