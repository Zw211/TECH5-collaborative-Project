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


def test_skills_outside_catalog_are_ignored() -> None:
    """Verifies requirement fields for unknown skills are not parsed."""
    project = forms.ProjectForm(
        _form(req_level_r="5"), SKILLS
    ).to_project()
    assert {r.skill_id for r in project.requirements} == {"py"}


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
