"""ID-03 to ID-08: identifiers, skill names, and record ownership."""

import pytest

from app.domain import models
from app.domain import validation


INVALID_IDENTIFIERS = [
    pytest.param("", "empty", id="empty-text"),
    pytest.param(" \t\n", "empty", id="whitespace-only"),
    pytest.param(None, "must be text", id="missing"),
    pytest.param(7, "must be text", id="integer"),
    pytest.param(1.5, "must be text", id="fraction"),
    pytest.param(True, "must be text", id="boolean"),
    pytest.param([], "must be text", id="list"),
    pytest.param({}, "must be text", id="dictionary"),
    pytest.param(" S1", "whitespace", id="leading-space"),
    pytest.param("S1\t", "whitespace", id="trailing-tab"),
]


@pytest.mark.parametrize("record_type", ["student", "project", "skill"])
@pytest.mark.parametrize(("identifier", "problem"), INVALID_IDENTIFIERS)
def test_invalid_catalogue_identifier_is_rejected(
    record_type: str, identifier: object, problem: str
) -> None:
    """Blank, non-text, or padded catalogue IDs give a useful input error."""
    student = models.Student(id="S1", display_name="Student 1")
    project = models.Project(id="P1", title="Project 1")
    skill = models.Skill(id="py", name="Python")
    if record_type == "student":
        student.id = identifier  # type: ignore[assignment]
    elif record_type == "project":
        project.id = identifier  # type: ignore[assignment]
    else:
        skill = models.Skill(id=identifier, name="Python")  # type: ignore[arg-type]

    result = validation.validate_cohort([student], [project], [skill])

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert record_type.capitalize() in result.errors[0]
    assert "identifier" in result.errors[0]
    assert problem in result.errors[0]
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("identifier", [None, 7, True, "", " \t", " py "])
def test_invalid_reference_identifiers_are_reported_together(
    identifier: object,
) -> None:
    """Check all seven reference fields, including skill dictionary keys."""
    student = models.Student(
        id="S1",
        display_name="Student 1",
        skills={identifier: 3},  # type: ignore[dict-item]
        preferences=[
            models.Preference(identifier, identifier, 1),  # type: ignore[arg-type]
        ],
    )
    project = models.Project(
        id="P1",
        title="Project 1",
        requirements=[
            models.ProjectRequirement(identifier, identifier),  # type: ignore[arg-type]
        ],
    )
    fixed = models.FixedAssignment(identifier, identifier)  # type: ignore[arg-type]

    result = validation.validate_cohort(
        [student], [project], fixed_assignments=[fixed]
    )

    assert result.is_valid is False
    assert len(result.errors) == 7
    for field in [
        "preference #1 student identifier",
        "preference #1 project identifier",
        "skill identifier",
        "requirement #1 project identifier",
        "requirement #1 skill identifier",
        "Fixed assignment #1 student identifier",
        "Fixed assignment #1 project identifier",
    ]:
        assert any(field in error for error in result.errors), result.errors
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("identifier", [[], {}], ids=["list", "dictionary"])
def test_unhashable_reference_identifiers_do_not_crash(identifier: object) -> None:
    """Lists and dictionaries must be rejected before sets or lookups use them."""
    student = models.Student(
        id="S1",
        display_name="Student 1",
        preferences=[
            models.Preference(identifier, identifier, 1),  # type: ignore[arg-type]
        ],
    )
    project = models.Project(
        id="P1",
        title="Project 1",
        requirements=[
            models.ProjectRequirement(identifier, identifier),  # type: ignore[arg-type]
        ],
    )
    fixed = models.FixedAssignment(identifier, identifier)  # type: ignore[arg-type]

    result = validation.validate_cohort(
        [student], [project], fixed_assignments=[fixed]
    )

    assert result.is_valid is False
    assert len(result.errors) == 6
    assert all("must be text" in error for error in result.errors)
    assert result.infeasibility_reasons == []


def test_duplicate_skill_identifiers_are_rejected() -> None:
    """Different names cannot make two records with the same skill ID valid."""
    skills = [models.Skill("py", "Python"), models.Skill("py", "Programming")]

    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")],
        [models.Project("P1", "Project 1")],
        skills,
    )

    assert result.is_valid is False
    assert result.errors == ["Duplicate skill identifier detected: 'py'."]
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize(
    ("first_name", "second_name"),
    [
        ("Python", "Python"),
        ("Python", "PYTHON"),
        (" Python ", "Python"),
        ("Python", " python "),
        ("Straße", "STRASSE"),
    ],
)
def test_duplicate_skill_names_are_rejected(
    first_name: str, second_name: str
) -> None:
    """Skill names are compared without edge spaces or case differences."""
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")],
        [models.Project("P1", "Project 1")],
        [models.Skill("py", first_name), models.Skill("other", second_name)],
    )

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "Duplicate skill name" in result.errors[0]
    assert "py" in result.errors[0] and "other" in result.errors[0]
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("name", [None, 7, "", " \t"])
def test_skill_name_must_be_nonempty_text(name: object) -> None:
    """Check the name before comparing it with other skill names."""
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")],
        [models.Project("P1", "Project 1")],
        [models.Skill("py", name)],  # type: ignore[arg-type]
    )

    assert result.is_valid is False
    assert result.errors == ["Skill 'py': name must be nonempty text."]


@pytest.mark.parametrize("parent_id", ["S2", "S99", "s1"])
def test_preference_must_belong_to_containing_student(parent_id: str) -> None:
    """Reject a different owner even if that student exists in the cohort."""
    students = [
        models.Student(
            "S1", "Student 1", preferences=[models.Preference(parent_id, "P1", 1)]
        ),
        models.Student("S2", "Student 2"),
    ]

    result = validation.validate_cohort(
        students, [models.Project("P1", "Project 1", max_capacity=2)]
    )

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "Preference in student 'S1'" in result.errors[0]
    assert f"references student '{parent_id}'" in result.errors[0]
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("parent_id", ["P2", "P99", "p1"])
def test_requirement_must_belong_to_containing_project(parent_id: str) -> None:
    """Reject a different owner even if that project exists in the catalogue."""
    projects = [
        models.Project(
            "P1", "Project 1", requirements=[models.ProjectRequirement(parent_id, "py")]
        ),
        models.Project("P2", "Project 2"),
    ]

    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")], projects, [models.Skill("py", "Python")]
    )

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "Requirement in project 'P1'" in result.errors[0]
    assert f"references project '{parent_id}'" in result.errors[0]
    assert result.infeasibility_reasons == []


def test_identifiers_are_case_sensitive_and_display_names_need_not_be_unique() -> None:
    """Keep case-distinct records and their exact references separate."""
    students = [
        models.Student(
            "S1", "Same name", skills={"py": 3},
            preferences=[models.Preference("S1", "P1", 1)],
        ),
        models.Student(
            "s1", "Same name", skills={"PY": 2},
            preferences=[models.Preference("s1", "p1", 1)],
        ),
    ]
    projects = [
        models.Project("P1", "Same title", requirements=[models.ProjectRequirement("P1", "py")]),
        models.Project("p1", "Same title", requirements=[models.ProjectRequirement("p1", "PY")]),
    ]
    skills = [models.Skill("py", "Python"), models.Skill("PY", "Advanced Python")]
    fixed = [models.FixedAssignment("S1", "P1"), models.FixedAssignment("s1", "p1")]

    result = validation.validate_cohort(students, projects, skills, fixed)

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == []
    assert [student.id for student in students] == ["S1", "s1"]
    assert [project.id for project in projects] == ["P1", "p1"]
    assert [skill.id for skill in skills] == ["py", "PY"]


def test_identifier_may_be_numeric_text_and_reused_in_another_catalogue() -> None:
    """Text '7' is valid; student, project, and skill IDs have separate scopes."""
    result = validation.validate_cohort(
        [models.Student("7", "Student 7")],
        [models.Project("7", "Project 7")],
        [models.Skill("7", "Skill 7")],
    )

    assert result.is_valid is True
    assert result.errors == []


def test_unmatched_reference_case_is_explained_without_changing_ids() -> None:
    """Do not guess the intended project, student, or skill in engine inputs."""
    student = models.Student(
        "S1", "Student 1", skills={"PY": 3},
        preferences=[models.Preference("S1", "p1", 1)],
    )
    project = models.Project(
        "P1", "Project 1", requirements=[models.ProjectRequirement("P1", "PY")]
    )
    fixed = models.FixedAssignment("s1", "p1")

    result = validation.validate_cohort(
        [student], [project], [models.Skill("py", "Python")], [fixed]
    )

    assert result.is_valid is False
    assert len(result.errors) == 3
    assert all("case-sensitive" in error for error in result.errors)
    assert len(result.warnings) == 2
    assert all("case-sensitive" in warning for warning in result.warnings)
    assert student.preferences[0].project_id == "p1"
    assert fixed.student_id == "s1"
    assert student.skills == {"PY": 3}


def test_bad_identifier_stops_feasibility_checks() -> None:
    """Duplicate student records must be corrected before counting demand."""
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1"), models.Student("S1", "Duplicate")],
        [models.Project("P1", "Only one place", max_capacity=1)],
    )

    assert result.is_valid is False
    assert result.errors == ["Duplicate student identifier detected: 'S1'."]
    assert result.infeasibility_reasons == []
