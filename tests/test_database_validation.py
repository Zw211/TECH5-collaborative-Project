"""DB-01 to DB-03: invalid saved inputs and operational failures are explained."""

import pathlib
import sqlite3

import pytest

from app import create_app
from app.domain import models
from app.persistence import database
from app.persistence import repositories


@pytest.mark.parametrize("column", ["profile", "requirement", "rank", "capacity"])
def test_invalid_saved_values_cannot_start_a_mock_run(tmp_path: pathlib.Path, column: str) -> None:
    app = create_app({"TESTING": True, "DATABASE_PATH": tmp_path / "bad_values.db"})
    repositories.SkillRepository().save(models.Skill("py", "Python"))
    repositories.ProjectRepository().save(models.Project(
        "P1", "Project 1", requirements=[models.ProjectRequirement("P1", "py", 2)]
    ))
    repositories.StudentRepository().save(models.Student(
        "S1", "Student 1", skills={"py": 3}, preferences=[models.Preference("S1", "P1", 1)]
    ))
    statements = {
        "profile": "UPDATE student_skills SET level = 6;",
        "requirement": "UPDATE project_requirements SET minimum_level = 2.5;",
        "rank": "UPDATE preferences SET rank = 1.5;",
        "capacity": "UPDATE projects SET max_capacity = 'many';",
    }
    database.db_manager.execute_statement(statements[column])

    response = app.test_client().post("/runs/trigger", data={"max_alternatives": "2"}, follow_redirects=True)

    assert response.status_code == 200
    runs = repositories.RunRepository().list_runs()
    assert len(runs) == 1 and runs[0].status == "INVALID_INPUT"
    assert runs[0].solutions == []
    assert any("S1" in error or "P1" in error for error in runs[0].diagnostics["errors"])


def test_invalid_saved_mandatory_flag_is_not_coerced_to_true(tmp_path: pathlib.Path) -> None:
    db_file = tmp_path / "bad_flag.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    repositories.SkillRepository().save(models.Skill("py", "Python"))
    repositories.ProjectRepository().save(models.Project(
        "P1", "Project 1", requirements=[models.ProjectRequirement("P1", "py", 2)]
    ))
    with database.db_manager.connection() as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON;")
        connection.execute("UPDATE project_requirements SET is_mandatory = 'false';")

    with pytest.raises(database.InvalidDatabaseRecords, match="mandatory flag"):
        repositories.ProjectRepository().get_by_id("P1")

    response = app.test_client().post("/runs/trigger", data={"max_alternatives": "2"}, follow_redirects=True)

    assert response.status_code == 422
    assert b"P1" in response.data and b"py" in response.data
    assert b"mandatory flag" in response.data
    assert repositories.RunRepository().list_runs() == []


def test_orphaned_saved_reference_is_identified(tmp_path: pathlib.Path) -> None:
    db_file = tmp_path / "orphan.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    repositories.StudentRepository().save(models.Student("S1", "Student 1"))
    with database.db_manager.connection() as connection:
        connection.execute("PRAGMA foreign_keys = OFF;")
        connection.execute("INSERT INTO student_skills VALUES ('S1', 'ghost', 2);")

    response = app.test_client().post("/runs/trigger", data={"max_alternatives": "2"}, follow_redirects=True)

    assert response.status_code == 422
    assert b"student_skills" in response.data and b"skills" in response.data
    assert b"row" in response.data
    assert repositories.RunRepository().list_runs() == []


@pytest.mark.parametrize("failure", ["damaged", "unavailable-folder"])
def test_unavailable_database_at_startup_has_a_useful_page(tmp_path: pathlib.Path, failure: str) -> None:
    if failure == "damaged":
        db_file = tmp_path / "damaged.db"
        db_file.write_bytes(b"this is not a SQLite database")
    else:
        blocked_folder = tmp_path / "a_file"
        blocked_folder.write_text("not a folder", encoding="utf-8")
        db_file = blocked_folder / "unavailable.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 503
    assert b"Database unavailable" in response.data
    assert b"INFEASIBLE" not in response.data
    assert client.get("/static/css/style.css").status_code == 200


def test_locked_database_write_is_reported(tmp_path: pathlib.Path) -> None:
    db_file = tmp_path / "locked.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    database.db_manager.timeout_seconds = 0.01
    connection = sqlite3.connect(db_file)
    try:
        connection.execute("BEGIN IMMEDIATE;")
        response = app.test_client().post("/skills/new", data={"id": "py", "name": "Python"})
    finally:
        connection.rollback()
        connection.close()

    assert response.status_code == 503
    assert b"Database unavailable" in response.data
    assert repositories.SkillRepository().list_all() == []


def test_read_only_database_write_is_reported(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "read_only.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})

    def read_only_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(db_file.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(database.db_manager, "get_connection", read_only_connection)
    response = app.test_client().post("/skills/new", data={"id": "py", "name": "Python"})

    assert response.status_code == 503
    assert b"Database unavailable" in response.data
    assert repositories.SkillRepository().list_all() == []


def test_invalid_saved_capacity_does_not_crash_dashboard(tmp_path: pathlib.Path) -> None:
    app = create_app({"TESTING": True, "DATABASE_PATH": tmp_path / "dashboard.db"})
    repositories.ProjectRepository().save(models.Project("P1", "Project 1"))
    database.db_manager.execute_statement("UPDATE projects SET max_capacity = 'many';")

    response = app.test_client().get("/")

    assert response.status_code == 422
    assert b"P1" in response.data and b"capacity" in response.data


def test_invalid_saved_capacity_cannot_crash_the_lock_form(tmp_path: pathlib.Path) -> None:
    app = create_app({"TESTING": True, "DATABASE_PATH": tmp_path / "bad_lock_capacity.db"})
    repositories.StudentRepository().save(models.Student("S1", "Student 1"))
    repositories.ProjectRepository().save(models.Project("P1", "Project 1"))
    database.db_manager.execute_statement("UPDATE projects SET max_capacity = 'many';")

    response = app.test_client().post(
        "/fixed-assignments/new", data={"student_id": "S1", "project_id": "P1"}, follow_redirects=True
    )

    assert response.status_code == 200
    assert b"positive whole number" in response.data
    assert repositories.FixedAssignmentRepository().list_all() == []


def test_failed_student_save_rolls_back_existing_profile(tmp_path: pathlib.Path) -> None:
    db = database.DatabaseManager(tmp_path / "student_rollback.db")
    db.initialize_schema()
    repositories.SkillRepository(db).save(models.Skill("py", "Python"))
    repo = repositories.StudentRepository(db)
    repo.save(models.Student("S1", "Original", skills={"py": 2}))

    with pytest.raises(sqlite3.IntegrityError):
        repo.save(models.Student("S1", "Changed", skills={"py": 4, "ghost": 3}))

    saved = repo.get_by_id("S1")
    assert saved is not None
    assert saved.display_name == "Original" and saved.skills == {"py": 2}


def test_failed_run_save_rolls_back_every_related_row(tmp_path: pathlib.Path) -> None:
    db = database.DatabaseManager(tmp_path / "run_rollback.db")
    db.initialize_schema()
    repo = repositories.RunRepository(db)
    solution = models.Solution(
        "solution", "run", 1, "PREFERENCE", assignments=[models.Assignment("ghost", "missing")]
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.save_run(models.AssignmentRun("run", status="COMPLETED", solutions=[solution]))

    assert repo.get_run("run") is None
    assert repo.get_solution("solution") is None
    assert db.execute_query("SELECT * FROM assignments;") == []


def test_failed_cohort_replacement_restores_old_data(tmp_path: pathlib.Path) -> None:
    db = database.DatabaseManager(tmp_path / "cohort_rollback.db")
    db.initialize_schema()
    repositories.StudentRepository(db).save(models.Student("OLD", "Original"))

    with pytest.raises(sqlite3.IntegrityError):
        repositories.CohortRepository(db).replace(
            [models.Student("NEW", "New", skills={"ghost": 2})],
            [models.Project("P1", "New project")], [], [],
        )

    assert repositories.StudentRepository(db).get_by_id("OLD") is not None
    assert repositories.StudentRepository(db).get_by_id("NEW") is None
    assert repositories.ProjectRepository(db).list_all() == []


def test_unknown_scenario_does_not_clear_existing_inputs(tmp_path: pathlib.Path) -> None:
    app = create_app({"TESTING": True, "DATABASE_PATH": tmp_path / "unknown_scenario.db"})
    repositories.StudentRepository().save(models.Student("S1", "Keep me"))

    response = app.test_client().post("/load-scenario/unknown", follow_redirects=True)

    assert response.status_code == 200
    assert repositories.StudentRepository().get_by_id("S1") is not None


def test_failed_mock_run_also_rolls_back_its_new_lock(tmp_path: pathlib.Path) -> None:
    app = create_app({"TESTING": True, "DATABASE_PATH": tmp_path / "mock_rollback.db"})
    repositories.StudentRepository().save(models.Student("S1", "Student 1"))
    repositories.ProjectRepository().save(models.Project("P1", "Project 1"))
    source = models.Solution(
        "source-solution", "source-run", 1, "PREFERENCE", assignments=[models.Assignment("S1", "P1")]
    )
    repositories.RunRepository().save_run(models.AssignmentRun("source-run", status="COMPLETED", solutions=[source]))
    database.db_manager.execute_statement(
        "CREATE TRIGGER reject_new_run BEFORE INSERT ON assignment_runs "
        "WHEN NEW.id != 'source-run' BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END;"
    )

    response = app.test_client().post(
        "/solutions/source-solution/lock-and-rerun", data={"student_id": "S1", "project_id": "P1"}
    )

    assert response.status_code == 503
    assert repositories.FixedAssignmentRepository().list_all() == []
    assert [run.id for run in repositories.RunRepository().list_runs()] == ["source-run"]
    assert len(repositories.RunRepository().get_solution(source.id).assignments) == 1
