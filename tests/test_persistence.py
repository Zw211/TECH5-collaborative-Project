"""Unit tests for SQLite relational persistence and SQL queries."""

import pathlib

from app.domain import models
from app.persistence import database, repositories


def test_schema_init_and_skill_repo(tmp_path: pathlib.Path) -> None:
    """Verifies DDL schema initialization and SkillRepository CRUD."""
    db_file = tmp_path / "test_persistence.db"
    db_mgr = database.DatabaseManager(db_file)
    db_mgr.initialize_schema()

    skill_repo = repositories.SkillRepository(db_mgr)
    skill_repo.save(
        models.Skill(id="py", name="Python", description="Python dev")
    )
    skill_repo.save(models.Skill(id="sql", name="SQL", description="SQL db"))

    all_skills = skill_repo.list_all()
    assert len(all_skills) == 2
    assert skill_repo.get_by_id("py") is not None

    skill_repo.delete("sql")
    assert len(skill_repo.list_all()) == 1


def test_student_and_project_persistence(tmp_path: pathlib.Path) -> None:
    """Verifies relational persistence of students and projects."""
    db_file = tmp_path / "test_student_proj.db"
    db_mgr = database.DatabaseManager(db_file)
    db_mgr.initialize_schema()

    skill_repo = repositories.SkillRepository(db_mgr)
    skill_repo.save(models.Skill(id="py", name="Python"))

    proj_repo = repositories.ProjectRepository(db_mgr)
    project = models.Project(
        id="P1",
        title="FinTech Project",
        min_capacity=1,
        max_capacity=3,
        requirements=[
            models.ProjectRequirement(
                project_id="P1", skill_id="py", minimum_level=2
            )
        ],
    )
    proj_repo.save(project)

    retrieved_proj = proj_repo.get_by_id("P1")
    assert retrieved_proj is not None
    assert retrieved_proj.max_capacity == 3
    assert len(retrieved_proj.requirements) == 1

    stud_repo = repositories.StudentRepository(db_mgr)
    student = models.Student(
        id="S1",
        display_name="Alice",
        skills={"py": 3},
        preferences=[
            models.Preference(student_id="S1", project_id="P1", rank=1)
        ],
    )
    stud_repo.save(student)

    retrieved_stud = stud_repo.get_by_id("S1")
    assert retrieved_stud is not None
    assert retrieved_stud.get_skill_level("py") == 3
    assert retrieved_stud.get_preference_rank("P1") == 1


def test_run_and_solution_persistence(tmp_path: pathlib.Path) -> None:
    """Verifies full optimization run, solution, and assignment persistence."""
    db_file = tmp_path / "test_runs.db"
    db_mgr = database.DatabaseManager(db_file)
    db_mgr.initialize_schema()

    stud_repo = repositories.StudentRepository(db_mgr)
    proj_repo = repositories.ProjectRepository(db_mgr)
    stud_repo.save(models.Student(id="S1", display_name="S1"))
    proj_repo.save(models.Project(id="P1", title="P1", max_capacity=2))

    run_repo = repositories.RunRepository(db_mgr)
    assignment = models.Assignment(
        student_id="S1",
        project_id="P1",
        is_fixed=False,
        preference_rank=1,
        skill_fit_score=1.0,
    )
    solution = models.Solution(
        id="sol-100",
        run_id="run-100",
        alternative_number=1,
        strategy_name="PREFERENCE",
        objective_value=50.0,
        assignments=[assignment],
        indicators={"fairness": {"mean_rank": 1.0}},
    )
    run = models.AssignmentRun(
        id="run-100",
        status="COMPLETED",
        configuration={"strategy": "PREFERENCE"},
        solutions=[solution],
        diagnostics={"solution_count": 1},
    )

    run_repo.save_run(run)

    retrieved_run = run_repo.get_run("run-100")
    assert retrieved_run is not None
    assert retrieved_run.status == "COMPLETED"
    assert len(retrieved_run.solutions) == 1

    retrieved_sol = run_repo.get_solution("sol-100")
    assert retrieved_sol is not None
    assert retrieved_sol.assignments[0].student_id == "S1"
