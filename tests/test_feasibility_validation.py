"""Week 1 necessary feasibility checks; these do not generate assignments."""

import pytest

from app.domain import models
from app.domain import validation


def test_exact_allocation_capacity_deficit_is_explained() -> None:
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1"), models.Student("S2", "Student 2")],
        [models.Project("P1", "Project 1", max_capacity=1)],
    )

    assert result.is_feasible is False
    assert any("(2)" in reason and "(1)" in reason for reason in result.infeasibility_reasons)


@pytest.mark.parametrize("exact_allocation", [True, False])
def test_minimum_capacity_shortage_is_always_infeasible(exact_allocation: bool) -> None:
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")],
        [models.Project("P1", "Project 1", min_capacity=2, max_capacity=3)],
        enforce_exact_allocation=exact_allocation,
    )

    assert result.is_feasible is False
    assert any("below aggregate minimum" in reason for reason in result.infeasibility_reasons)


def test_uncovered_optional_project_can_stay_unused() -> None:
    project = models.Project(
        "P1", "Optional skilled project",
        requirements=[models.ProjectRequirement("P1", "py", 3, True)],
    )
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")],
        [project, models.Project("P2", "Other project")],
        [models.Skill("py", "Python")],
    )

    assert result.is_valid is True
    assert result.infeasibility_reasons == []
    assert any("P1" in warning and "must remain unused" in warning for warning in result.warnings)


@pytest.mark.parametrize("required_by", ["minimum", "lock", "demand"])
def test_unavailable_mandatory_skill_is_reported_when_project_must_be_used(required_by: str) -> None:
    project = models.Project(
        "P1", "Skilled project",
        requirements=[models.ProjectRequirement("P1", "py", 3, True)],
    )
    projects = [project]
    locks = []
    if required_by == "minimum":
        project.min_capacity = 1
        projects.append(models.Project("P2", "Other project"))
    elif required_by == "lock":
        locks = [models.FixedAssignment("S1", "P1")]
        projects.append(models.Project("P2", "Other project"))

    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")], projects, [models.Skill("py", "Python")], locks
    )

    assert result.is_feasible is False
    assert any("P1" in reason and "mandatory skill 'py'" in reason for reason in result.infeasibility_reasons)


def test_optional_unusable_projects_do_not_supply_places() -> None:
    projects = [
        models.Project(
            project_id, project_id,
            requirements=[models.ProjectRequirement(project_id, "py", 3, True)],
        )
        for project_id in ["P1", "P2"]
    ]
    projects.append(models.Project("P3", "Only usable place"))
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1"), models.Student("S2", "Student 2")],
        projects, [models.Skill("py", "Python")],
    )

    assert result.is_feasible is False
    assert any("usable project places (1)" in reason for reason in result.infeasibility_reasons)


@pytest.mark.parametrize("qualified_locked_elsewhere", [True, False])
def test_locks_can_prevent_mandatory_coverage(qualified_locked_elsewhere: bool) -> None:
    students = [models.Student("S1", "Qualified", skills={"py": 3}), models.Student("S2", "Other")]
    projects = [
        models.Project("P1", "Needs Python", min_capacity=1, requirements=[models.ProjectRequirement("P1", "py", 3, True)]),
        models.Project("P2", "Other project"),
    ]
    if qualified_locked_elsewhere:
        locks = [models.FixedAssignment("S1", "P2")]
    else:
        locks = [models.FixedAssignment("S2", "P1")]

    result = validation.validate_cohort(students, projects, [models.Skill("py", "Python")], locks)

    assert result.is_feasible is False
    assert any("P1" in reason and "py" in reason for reason in result.infeasibility_reasons)


def test_one_qualified_member_is_enough_for_team_coverage() -> None:
    students = [models.Student("S1", "Qualified", skills={"py": 3}), models.Student("S2", "Other")]
    project = models.Project(
        "P1", "Team project", min_capacity=2, max_capacity=2,
        requirements=[models.ProjectRequirement("P1", "py", 3, True)],
    )

    result = validation.validate_cohort(students, [project], [models.Skill("py", "Python")])

    assert result.is_valid is True
    assert result.infeasibility_reasons == []
    assert students[1].skills == {}


def test_uneven_preference_demand_is_valid_input() -> None:
    students = [
        models.Student(student_id, student_id, preferences=[models.Preference(student_id, "P1", 1)])
        for student_id in ["S1", "S2"]
    ]

    result = validation.validate_cohort(
        students, [models.Project("P1", "Popular"), models.Project("P2", "Unranked")]
    )

    assert result.is_valid is True
    assert result.infeasibility_reasons == []
