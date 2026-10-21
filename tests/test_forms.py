"""Unit tests for Component A form parsing (app/visualization/forms.py)."""

import pytest

from app.visualization import forms

SKILLS = ["py", "sql"]


def _form(**overrides: str) -> dict[str, str]:
    """Returns a valid project form submission with optional overrides."""
    data = {
        "id": "P1",
        "title": "FinTech Risk",
        "description": "  Risk analytics  ",
        "min_capacity": "1",
        "max_capacity": "3",
        "req_level_py": "4",
        "req_mand_py": "1",
        "req_level_sql": "0",
    }
    data.update(overrides)
    return data


def test_valid_form_builds_project() -> None:
    """Verifies a valid submission becomes a Project with requirements."""
    form = forms.ProjectForm(_form(), SKILLS)
    project = form.to_project()

    assert form.errors == []
    assert project is not None
    assert project.id == "P1"
    assert project.description == "Risk analytics"
    assert (project.min_capacity, project.max_capacity) == (1, 3)
    assert len(project.requirements) == 1
    req = project.requirements[0]
    assert (req.project_id, req.skill_id) == ("P1", "py")
    assert req.minimum_level == 4
    assert req.is_mandatory


def test_unticked_checkbox_is_optional_requirement() -> None:
    """Verifies a requirement without the checkbox is optional."""
    data = _form(req_level_sql="2")
    project = forms.ProjectForm(data, SKILLS).to_project()

    sql_req = [r for r in project.requirements if r.skill_id == "sql"][0]
    assert sql_req.minimum_level == 2
    assert not sql_req.is_mandatory


def test_missing_min_capacity_defaults_to_zero() -> None:
    """Verifies an empty minimum capacity is treated as 0."""
    project = forms.ProjectForm(_form(min_capacity=""), SKILLS).to_project()
    assert project.min_capacity == 0


def test_edit_uses_url_identifier() -> None:
    """Verifies the edited project's ID overrides the submitted one."""
    form = forms.ProjectForm(_form(id="HACKED"), SKILLS, project_id="P1")
    assert form.to_project().id == "P1"


@pytest.mark.parametrize("field", ["req_level_r", "req_mand_r"])
def test_skills_outside_catalog_are_rejected(field: str) -> None:
    """SKILL-04: Unknown requirement fields must not be silently discarded."""
    data = _form()
    data[field] = "1"
    form = forms.ProjectForm(data, SKILLS)

    assert form.to_project() is None
    assert any("unknown skill 'r'" in error for error in form.errors)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"id": "  "}, "identifier is required"),
        ({"title": ""}, "title is required"),
        ({"max_capacity": ""}, "Maximum capacity is required"),
        ({"max_capacity": "two"}, "Maximum capacity must be a whole number"),
        ({"min_capacity": "1.5"}, "Minimum capacity must be a whole number"),
        ({"min_capacity": "-1"}, "cannot be negative"),
        ({"max_capacity": "0", "min_capacity": "0"}, "at least 1"),
        ({"min_capacity": "4"}, "cannot exceed maximum capacity"),
        ({"req_level_py": "6"}, "between 1 and 5"),
        ({"req_level_py": "-2"}, "between 1 and 5"),
        ({"req_level_py": "x"}, "must be a whole number"),
        ({"req_level_py": "0"}, "marked mandatory but has no required level"),
    ],
)
def test_invalid_input_is_rejected(
    overrides: dict[str, str], message: str
) -> None:
    """Verifies each validation rule rejects bad input with a message."""
    form = forms.ProjectForm(_form(**overrides), SKILLS)

    assert form.to_project() is None
    assert any(message in error for error in form.errors), form.errors


def test_all_errors_are_reported_together() -> None:
    """Verifies several problems are reported in one submission."""
    form = forms.ProjectForm(
        _form(title="", min_capacity="5", req_level_py="9"), SKILLS
    )

    assert form.to_project() is None
    assert len(form.errors) == 3


@pytest.mark.parametrize("flag", ["false", "true", "0", "2", "yes", "off"])
def test_project_form_rejects_unsupported_mandatory_flags(flag: str) -> None:
    """SKILL-08: Nonempty text must not automatically become a checked box."""
    form = forms.ProjectForm(_form(req_mand_py=flag), SKILLS)

    assert form.to_project() is None
    assert any(
        "Mandatory flag" in error and "py" in error for error in form.errors
    )


@pytest.mark.parametrize(
    ("flag", "expected"), [("1", True), ("on", True), ("", False)]
)
def test_project_form_parses_supported_checkbox_values(
    flag: str, expected: bool
) -> None:
    """Parse supported checked and unchecked requirement flags."""
    form = forms.ProjectForm(_form(req_mand_py=flag), SKILLS)

    project = form.to_project()

    assert project is not None
    assert project.requirements[0].is_mandatory is expected


@pytest.mark.parametrize(
    "level", ["-1", "6", "1.5", "2.0", "bad", "true", "inf"]
)
def test_student_skill_form_rejects_invalid_levels(level: str) -> None:
    """SKILL-02: Form text must parse to a whole number between 1 and 5."""
    form = forms.StudentSkillsForm({"skill_py": level}, SKILLS)

    assert form.to_skills() is None
    assert any("py" in error for error in form.errors)


@pytest.mark.parametrize("omitted_level", ["0", "", " \t"])
def test_student_skill_form_omits_zero_or_blank_levels(
    omitted_level: str,
) -> None:
    """SKILL-01/02: Zero and blank form values mean no recorded skill."""
    form = forms.StudentSkillsForm(
        {"skill_py": " 5 ", "skill_sql": omitted_level, "id": "S1"}, SKILLS
    )

    assert form.to_skills() == {"py": 5}
    assert form.errors == []


def test_student_skill_form_rejects_unknown_skill() -> None:
    """SKILL-04: Skill fields must use an exact catalogue ID."""
    form = forms.StudentSkillsForm({"skill_ghost": "3"}, SKILLS)

    assert form.to_skills() is None
    assert any("unknown skill 'ghost'" in error for error in form.errors)


def test_student_skill_form_collects_errors_and_can_be_rechecked() -> None:
    """Clear previous form errors after the submitted data is corrected."""
    data = {"skill_py": "bad", "skill_sql": "6"}
    form = forms.StudentSkillsForm(data, SKILLS)

    assert form.to_skills() is None
    assert len(form.errors) == 2

    data.update(skill_py="1", skill_sql="5")
    assert form.to_skills() == {"py": 1, "sql": 5}
    assert form.errors == []
