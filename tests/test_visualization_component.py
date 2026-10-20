"""Tests for Component A (Visualization & Recommendation) web workflows."""

import copy
import pathlib
from typing import Any

import pytest

from app import create_app
from app.contract import mocks
from app.domain import models
from app.persistence import repositories
from app.visualization import routes


def test_dashboard_loads(tmp_path: pathlib.Path) -> None:
    """Verifies dashboard overview page rendering."""
    db_file = tmp_path / "test_ui_dash.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    dash_res = client.get("/")
    assert dash_res.status_code == 200
    assert b"TECH5" in dash_res.data


def test_role_switcher(tmp_path: pathlib.Path) -> None:
    """Verifies role switching in session."""
    db_file = tmp_path / "test_role.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    res = client.post(
        "/set-role", data={"role": "STUDENT"}, follow_redirects=True
    )
    assert res.status_code == 200
    assert b"Switched role to Student Viewer" in res.data


def test_student_and_fixed_assignment_workflow(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies student and fixed-assignment creation workflows."""
    db_file = tmp_path / "test_stud_fixed.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Seed project P1 so student preference foreign key is valid
    repositories.ProjectRepository().save(
        models.Project(
            id="P1",
            title="FinTech Risk",
            min_capacity=1,
            max_capacity=2,
        )
    )

    # Create student
    res_stud = client.post(
        "/students/new",
        data={
            "id": "S1",
            "display_name": "Alice Chen",
            "preferences_text": "P1",
        },
        follow_redirects=True,
    )
    assert res_stud.status_code == 200
    assert b"Alice Chen" in res_stud.data

    # Create fixed assignment
    res_fixed = client.post(
        "/fixed-assignments/new",
        data={
            "student_id": "S1",
            "project_id": "P1",
            "status": "APPROVED",
            "reason": "Pre-matched",
        },
        follow_redirects=True,
    )
    assert res_fixed.status_code == 200
    assert b"Pre-matched" in res_fixed.data


def test_scenario_loading_and_optimization_trigger(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies benchmark scenario loading, execution, and result views."""
    db_file = tmp_path / "test_scenario_run.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Load standard benchmark
    load_res = client.post("/load-scenario/standard", follow_redirects=True)
    assert load_res.status_code == 200
    assert b"Standard Cohort" in load_res.data

    # Trigger optimization run (falls back to mock engine if solver unimplemented)
    run_res = client.post(
        "/runs/trigger",
        data={
            "primary_strategy": "PREFERENCE",
            "max_alternatives": 3,
        },
        follow_redirects=True,
    )
    assert run_res.status_code == 200
    assert b"Optimization run completed" in run_res.data

    runs = repositories.RunRepository().list_runs(limit=1)
    assert len(runs) == 1
    run = runs[0]
    assert len(run.solutions) >= 1

    # View solution detail
    sol_id = run.solutions[0].id
    sol_res = client.get(f"/solutions/{sol_id}")
    assert sol_res.status_code == 200
    assert b"Student-to-Project Allocations" in sol_res.data

    # View recommendations
    recs_res = client.get(f"/recommendations/{run.id}")
    assert recs_res.status_code == 200
    assert b"Transparent Decision Recommendations" in recs_res.data
    assert b"Calculated Evidence" in recs_res.data
    assert b"Policy Advice" in recs_res.data


def test_create_student_preference_validation(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies preference validation when creating a student."""
    db_file = tmp_path / "test_stud_pref_val.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    repositories.ProjectRepository().save(
        models.Project(
            id="P1",
            title="Project One",
            min_capacity=1,
            max_capacity=2,
        )
    )

    # 1. Invalid project preference should flash error and not crash
    res_invalid = client.post(
        "/students/new",
        data={
            "id": "S10",
            "display_name": "Test Student",
            "preferences_text": "P99, P100",
        },
        follow_redirects=True,
    )
    assert res_invalid.status_code == 200
    assert b"Invalid project ID(s) in preferences" in res_invalid.data

    # 2. Case-insensitive project preference should normalize and succeed
    res_valid = client.post(
        "/students/new",
        data={
            "id": "S10",
            "display_name": "Test Student",
            "preferences_text": "p1",
        },
        follow_redirects=True,
    )
    assert res_valid.status_code == 200
    assert b"created successfully" in res_valid.data

    saved = repositories.StudentRepository().get_by_id("S10")
    assert saved is not None
    assert len(saved.preferences) == 1
    assert saved.preferences[0].project_id == "P1"


def _make_client(tmp_path: pathlib.Path, name: str) -> Any:
    """Creates a test client backed by a fresh temporary database."""
    app = create_app(
        {"TESTING": True, "DATABASE_PATH": tmp_path / f"{name}.db"}
    )
    return app.test_client()


def _skill_form(skill_id: str, name: str, description: str = "") -> dict:
    """Builds the form payload of the add-skill form."""
    return {"id": skill_id, "name": name, "description": description}


def test_skills_crud_workflow(tmp_path: pathlib.Path) -> None:
    """Verifies skill creation and deletion workflow."""
    client = _make_client(tmp_path, "test_skill")

    res = client.post(
        "/skills/new",
        data=_skill_form("  PY ", " Python ", " Python Programming "),
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"created successfully" in res.data
    assert b"Python Programming" in res.data

    saved = repositories.SkillRepository().get_by_id("py")
    assert saved is not None
    assert saved.name == "Python"
    assert saved.description == "Python Programming"

    list_res = client.get("/skills")
    assert b"<code>py</code>" in list_res.data
    assert b"Unused" in list_res.data

    del_res = client.post("/skills/py/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert b"Skill &#39;py&#39; deleted." in del_res.data
    assert repositories.SkillRepository().get_by_id("py") is None


def test_create_skill_duplicate_id_does_not_overwrite(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies a duplicate ID is rejected and the original is kept."""
    client = _make_client(tmp_path, "test_skill_dup_id")
    client.post("/skills/new", data=_skill_form("py", "Python", "Original"))

    res = client.post(
        "/skills/new",
        data=_skill_form("PY", "Another Name", "Overwritten"),
        follow_redirects=True,
    )
    assert b"already exists" in res.data

    skills = repositories.SkillRepository().list_all()
    assert len(skills) == 1
    assert skills[0].name == "Python"
    assert skills[0].description == "Original"


def test_create_skill_duplicate_name_case_insensitive(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies skill names are unique regardless of case."""
    client = _make_client(tmp_path, "test_skill_dup_name")
    client.post("/skills/new", data=_skill_form("py", "Python"))

    res = client.post(
        "/skills/new",
        data=_skill_form("python3", "  PYTHON "),
        follow_redirects=True,
    )
    assert b"Skill name &#39;PYTHON&#39; already exists." in res.data
    assert repositories.SkillRepository().get_by_id("python3") is None


@pytest.mark.parametrize("bad_id", ["my skill", "py-3", "pyé", "a/b"])
def test_create_skill_invalid_id_format(
    tmp_path: pathlib.Path, bad_id: str
) -> None:
    """Verifies IDs with characters outside [a-z0-9_] are rejected."""
    client = _make_client(tmp_path, "test_skill_bad_id")

    res = client.post(
        "/skills/new",
        data=_skill_form(bad_id, "Some Skill"),
        follow_redirects=True,
    )
    assert b"Invalid skill ID" in res.data
    assert repositories.SkillRepository().list_all() == []


def test_create_skill_missing_name(tmp_path: pathlib.Path) -> None:
    """Verifies a skill without a name is rejected."""
    client = _make_client(tmp_path, "test_skill_no_name")

    res = client.post(
        "/skills/new",
        data=_skill_form("py", "   "),
        follow_redirects=True,
    )
    assert b"Skill name cannot be empty." in res.data
    assert repositories.SkillRepository().list_all() == []


def test_student_role_cannot_create_or_delete_skill(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies the STUDENT role is denied skill modifications."""
    client = _make_client(tmp_path, "test_skill_perm")
    client.post("/skills/new", data=_skill_form("py", "Python"))
    client.post("/set-role", data={"role": "STUDENT"})

    create_res = client.post(
        "/skills/new",
        data=_skill_form("java", "Java"),
        follow_redirects=True,
    )
    assert b"Permission denied" in create_res.data
    assert repositories.SkillRepository().get_by_id("java") is None

    delete_res = client.post("/skills/py/delete", follow_redirects=True)
    assert b"Permission denied" in delete_res.data
    assert repositories.SkillRepository().get_by_id("py") is not None


def test_delete_unknown_skill(tmp_path: pathlib.Path) -> None:
    """Verifies deleting an unknown skill flashes a warning."""
    client = _make_client(tmp_path, "test_skill_unknown")

    res = client.post("/skills/nope/delete", follow_redirects=True)
    assert res.status_code == 200
    assert b"Skill &#39;nope&#39; not found." in res.data


def _seed_skill_usage() -> None:
    """Seeds skills used by projects (one mandatory) and a student."""
    skill_repo = repositories.SkillRepository()
    skill_repo.save(models.Skill(id="py", name="Python"))
    skill_repo.save(models.Skill(id="sql", name="SQL"))
    project_repo = repositories.ProjectRepository()
    project_repo.save(
        models.Project(
            id="P1",
            title="Project One",
            min_capacity=1,
            max_capacity=2,
            requirements=[
                models.ProjectRequirement("P1", "py", 2, is_mandatory=True),
                models.ProjectRequirement("P1", "sql", 1, is_mandatory=False),
            ],
        )
    )
    project_repo.save(
        models.Project(
            id="P2",
            title="Project Two",
            min_capacity=1,
            max_capacity=2,
            requirements=[models.ProjectRequirement("P2", "py", 1)],
        )
    )
    repositories.StudentRepository().save(
        models.Student(id="S1", display_name="Student One", skills={"py": 3})
    )


def test_skills_page_shows_usage(tmp_path: pathlib.Path) -> None:
    """Verifies the 'Used by' column reflects projects and students."""
    client = _make_client(tmp_path, "test_skill_usage")
    _seed_skill_usage()

    res = client.get("/skills")
    assert b"Used by" in res.data
    assert b"2 projects, of which 1 mandatory" in res.data
    assert b"2 project(s) (1 mandatory), 1 student(s)" in res.data


def test_delete_mandatory_skill_warns_and_removes_requirement(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies deleting a mandatory requirement warns and cascades."""
    client = _make_client(tmp_path, "test_skill_mandatory")
    _seed_skill_usage()

    res = client.post("/skills/py/delete", follow_redirects=True)
    assert b"Removed from project(s): P1, P2." in res.data
    assert b"1 student(s) lost this proficiency." in res.data
    assert b"MANDATORY requirement" in res.data
    assert b"changes feasibility" in res.data

    project = repositories.ProjectRepository().get_by_id("P1")
    assert project is not None
    assert [r.skill_id for r in project.requirements] == ["sql"]
    student = repositories.StudentRepository().get_by_id("S1")
    assert student is not None
    assert "py" not in student.skills


def test_delete_non_mandatory_skill_has_no_mandatory_warning(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies no mandatory warning appears for optional requirements."""
    client = _make_client(tmp_path, "test_skill_optional")
    _seed_skill_usage()

    res = client.post("/skills/sql/delete", follow_redirects=True)
    assert b"Removed from project(s): P1." in res.data
    assert b"MANDATORY requirement" not in res.data


def test_validate_skill_input_helper() -> None:
    """Verifies the validation helper without the web layer."""
    existing = [models.Skill(id="py", name="Python")]

    assert routes._validate_skill_input(" SQL_2 ", " SQL ", existing) == (
        "sql_2",
        [],
    )

    _, errors = routes._validate_skill_input("py", "python", existing)
    assert len(errors) == 2

    norm_id, errors = routes._validate_skill_input("", "", existing)
    assert norm_id == ""
    assert errors == [
        "Skill ID cannot be empty.",
        "Skill name cannot be empty.",
    ]


def test_projects_crud_workflow(tmp_path: pathlib.Path) -> None:
    """Verifies project creation, validation, editing and deletion."""
    db_file = tmp_path / "test_proj.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()
    repositories.SkillRepository().save(
        models.Skill(id="py", name="Python", description="")
    )
    project_data = {
        "id": "P1",
        "title": "FinTech Risk",
        "description": "Risk analytics",
        "min_capacity": 1,
        "max_capacity": 2,
        "req_level_py": 3,
        "req_mand_py": "1",
    }

    # 1. Valid project is created with its requirement and shown
    res = client.post("/projects/new", data=project_data, follow_redirects=True)
    assert b"created successfully" in res.data
    assert b"Python &ge; 3" in res.data
    saved = repositories.ProjectRepository().get_by_id("P1")
    assert saved is not None
    assert saved.max_capacity == 2
    assert saved.requirements[0].minimum_level == 3
    assert saved.requirements[0].is_mandatory

    # 2. Duplicate identifier is rejected and does not overwrite
    res_dup = client.post(
        "/projects/new",
        data={**project_data, "title": "Overwritten"},
        follow_redirects=True,
    )
    assert b"already exists" in res_dup.data
    assert repositories.ProjectRepository().get_by_id("P1").title == (
        "FinTech Risk"
    )

    # 3. Invalid capacities and mandatory-without-level are rejected
    res_bad = client.post(
        "/projects/new",
        data={
            "id": "P2",
            "title": "Bad",
            "min_capacity": 3,
            "max_capacity": 2,
            "req_level_py": 0,
            "req_mand_py": "1",
        },
        follow_redirects=True,
    )
    assert b"cannot exceed maximum" in res_bad.data
    assert b"marked mandatory but has no required level" in res_bad.data
    assert repositories.ProjectRepository().get_by_id("P2") is None

    # 4. Edit form shows saved values; update replaces requirements
    res_form = client.get("/projects/P1/edit")
    assert b'name="req_level_py" min="0" max="5"' in res_form.data
    assert b'value="3"' in res_form.data
    assert b"checked" in res_form.data
    client.post(
        "/projects/P1/edit",
        data={
            "id": "IGNORED",
            "title": "FinTech Risk II",
            "min_capacity": 0,
            "max_capacity": 4,
            "req_level_py": 0,
        },
        follow_redirects=True,
    )
    updated = repositories.ProjectRepository().get_by_id("P1")
    assert updated.title == "FinTech Risk II"
    assert updated.max_capacity == 4
    assert updated.requirements == []
    assert repositories.ProjectRepository().get_by_id("IGNORED") is None

    # 5. Student viewers cannot create, edit or delete projects
    client.post("/set-role", data={"role": "STUDENT"})
    client.post(
        "/projects/new", data={**project_data, "id": "P3"},
        follow_redirects=True,
    )
    client.post("/projects/P1/delete", follow_redirects=True)
    assert repositories.ProjectRepository().get_by_id("P3") is None
    assert repositories.ProjectRepository().get_by_id("P1") is not None
    client.post("/set-role", data={"role": "ADMIN"})

    # 6. Catalog warns about cascading records before deleting
    repositories.StudentRepository().save(
        models.Student(
            id="S1",
            display_name="Alice",
            preferences=[models.Preference("S1", "P1", 1)],
        )
    )
    res_list = client.get("/projects")
    assert b"1 student preference(s), 0 fixed assignment(s)" in res_list.data

    # 7. Deleting removes the project; deleting again reports not found
    res_del = client.post("/projects/P1/delete", follow_redirects=True)
    assert b"removed" in res_del.data
    assert repositories.ProjectRepository().get_by_id("P1") is None
    res_missing = client.post("/projects/P1/delete", follow_redirects=True)
    assert b"not found" in res_missing.data


def _create_mock_run(client: Any) -> models.AssignmentRun:
    """Loads the standard scenario and triggers one run; returns that run."""
    client.post("/load-scenario/standard")
    client.post("/runs/trigger", data={"max_alternatives": 3})
    return repositories.RunRepository().list_runs()[0]


def test_compare_solutions_view(tmp_path: pathlib.Path) -> None:
    """Verifies unknown solution IDs are reported gracefully."""
    client = _make_client(tmp_path, "test_comp")

    res = client.get("/compare?sol1=S1&sol2=S2")
    assert res.status_code == 200
    assert b"Cannot compare" in res.data
    assert b"not found" in res.data


def test_compare_empty_database_shows_guidance(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies the page explains what to do when there are no solutions."""
    client = _make_client(tmp_path, "test_comp_empty")

    res = client.get("/compare")
    assert res.status_code == 200
    assert b"No solutions to compare yet." in res.data


def test_compare_two_alternatives_of_a_run(tmp_path: pathlib.Path) -> None:
    """Verifies a mock run's alternatives can be compared side by side."""
    client = _make_client(tmp_path, "test_comp_run")
    run = _create_mock_run(client)
    alt1, alt2 = run.solutions[0], run.solutions[1]

    res = client.get(f"/compare?sol1={alt1.id}&sol2={alt2.id}")
    assert res.status_code == 200
    assert b"Changed Student Allocations" in res.data
    assert b"Rank Gini" in res.data
    assert b"Choice #None" not in res.data

    # Names and titles come from the repositories, not the raw IDs.
    comparison = mocks.MockAssignmentEngine().compare_solutions(
        alt1.id, alt2.id
    )
    first = comparison.changed_assignments[0]
    student = repositories.StudentRepository().get_by_id(first["student_id"])
    project = repositories.ProjectRepository().get_by_id(
        first["project_b_id"]
    )
    assert student is not None and project is not None
    assert student.display_name.encode() in res.data
    assert project.title.encode() in res.data


def test_compare_same_solution_twice_is_identical(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies comparing a solution with itself is flagged as identical."""
    client = _make_client(tmp_path, "test_comp_same")
    alt1 = _create_mock_run(client).solutions[0]

    res = client.get(f"/compare?sol1={alt1.id}&sol2={alt1.id}")
    assert res.status_code == 200
    assert b"are identical" in res.data
    assert b"Identical allocation outcomes" in res.data


def test_compare_only_sol1_preselects_second_alternative(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies sol2 defaults to another alternative of the same run."""
    client = _make_client(tmp_path, "test_comp_preselect")
    run = _create_mock_run(client)
    alt1, alt2 = run.solutions[0], run.solutions[1]

    res = client.get(f"/compare?sol1={alt1.id}")
    assert res.status_code == 200
    assert f'value="{alt2.id}" selected'.encode() in res.data
    assert b"Changed Student Allocations" in res.data


def test_compare_unknown_second_id(tmp_path: pathlib.Path) -> None:
    """Verifies one unknown ID gives an error flash and no crash."""
    client = _make_client(tmp_path, "test_comp_unknown")
    alt1 = _create_mock_run(client).solutions[0]

    res = client.get(f"/compare?sol1={alt1.id}&sol2=nope")
    assert res.status_code == 200
    assert b"Cannot compare" in res.data
    assert b"Changed Student Allocations" not in res.data


def test_compare_solutions_from_different_runs_warns(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies a cross-run comparison is allowed but flagged."""
    client = _make_client(tmp_path, "test_comp_cross")
    client.post("/load-scenario/standard")
    client.post("/runs/trigger", data={"max_alternatives": 2})
    client.post("/runs/trigger", data={"max_alternatives": 2})
    newer, older = repositories.RunRepository().list_runs()[:2]

    res = client.get(
        f"/compare?sol1={older.solutions[0].id}"
        f"&sol2={newer.solutions[0].id}"
    )
    assert res.status_code == 200
    assert b"different runs" in res.data
    assert b"Changed Student Allocations" in res.data


def test_run_detail_links_to_comparisons(tmp_path: pathlib.Path) -> None:
    """Verifies the run page links the first alternative to the others."""
    client = _make_client(tmp_path, "test_comp_links")
    run = _create_mock_run(client)

    res = client.get(f"/runs/{run.id}")
    assert b"Compare Alt 1 vs Alt 2" in res.data
    assert b"Compare Alt 1 vs Alt 3" in res.data
    assert f"sol2={run.solutions[1].id}".encode() in res.data


def test_enrich_changed_assignments_handles_unranked() -> None:
    """Verifies enrichment labels unranked ranks and leaves input intact."""
    changed = [
        {
            "student_id": "S1",
            "student_name": "S1",
            "project_a_id": "P1",
            "project_a_title": "P1",
            "rank_a": None,
            "project_b_id": "P9",
            "project_b_title": "P9",
            "rank_b": 2,
            "rank_delta": -97,
        }
    ]
    snapshot = copy.deepcopy(changed)
    students = {"S1": models.Student(id="S1", display_name="Alice")}
    projects = {"P1": models.Project(id="P1", title="Project One")}

    rows = routes._enrich_changed_assignments(changed, students, projects)

    assert changed == snapshot
    assert rows[0]["student_name"] == "Alice"
    assert rows[0]["project_a_title"] == "Project One"
    assert rows[0]["project_b_title"] == "P9"
    assert rows[0]["rank_a_label"] == "Unranked"
    assert rows[0]["rank_b_label"] == "Choice #2"
    assert rows[0]["shift_text"] == "Ranked in B (was unranked)"
    assert rows[0]["shift_class"] == "success"


@pytest.mark.parametrize(
    ("rank_a", "rank_b", "text", "css"),
    [
        (3, 1, "\u25b2 2 ranks better", "success"),
        (1, 2, "\u25bc 1 rank worse", "danger"),
        (2, 2, "Lateral move", "secondary"),
        (2, None, "Unranked in B", "danger"),
        (None, None, "Both unranked", "secondary"),
    ],
)
def test_describe_rank_shift(
    rank_a: int | None, rank_b: int | None, text: str, css: str
) -> None:
    """Verifies the rank shift wording for ranked and unranked moves."""
    assert routes._describe_rank_shift(rank_a, rank_b) == (text, css)


def test_pick_default_partner() -> None:
    """Verifies the partner is the next alternative of the same run."""
    options = [
        {"id": "a1", "run_id": "R1", "alternative_number": 1},
        {"id": "a2", "run_id": "R1", "alternative_number": 2},
        {"id": "a3", "run_id": "R1", "alternative_number": 3},
        {"id": "b1", "run_id": "R2", "alternative_number": 1},
    ]
    assert routes._pick_default_partner("a1", options) == "a2"
    assert routes._pick_default_partner("a3", options) == "a1"
    assert routes._pick_default_partner("b1", options) is None
    assert routes._pick_default_partner("zzz", options) is None
