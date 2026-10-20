"""SKILL-01 to SKILL-08: skill profiles, requirements, and catalogue checks."""

import pytest

from app.domain import models
from app.domain import validation
from app.engine import metrics


INVALID_LEVELS = [
    pytest.param(0, id="zero"),
    pytest.param(-1, id="negative"),
    pytest.param(6, id="above-five"),
    pytest.param(1.5, id="fraction"),
    pytest.param(2.0, id="whole-looking-float"),
    pytest.param("3", id="numeric-text"),
    pytest.param("bad", id="text"),
    pytest.param("", id="blank"),
    pytest.param(None, id="missing"),
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
    pytest.param(float("nan"), id="not-a-number"),
    pytest.param(float("inf"), id="infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
    pytest.param([], id="list"),
    pytest.param({}, id="dictionary"),
]


@pytest.mark.parametrize("profile", [{}, {"sql": 3}])
def test_missing_student_skill_is_level_zero(profile: dict[str, int]) -> None:
    """SKILL-01: Missing skills do not make an optional requirement invalid."""
    student = models.Student("S1", "Student 1", skills=profile.copy())
    project = models.Project(
        "P1", "Project 1", requirements=[models.ProjectRequirement("P1", "py", 2)]
    )

    result = validation.validate_cohort(
        [student], [project], [models.Skill("py", "Python"), models.Skill("sql", "SQL")]
    )

    assert result.is_valid is True
    assert result.is_feasible is True
    assert student.get_skill_level("py") == 0
    assert student.skills == profile
    assert result.infeasibility_reasons == []


def test_missing_skill_does_not_relax_a_mandatory_requirement() -> None:
    """SKILL-01: A missing profile cannot supply unavailable mandatory coverage."""
    project = models.Project(
        "P1", "Project 1", min_capacity=1,
        requirements=[models.ProjectRequirement("P1", "py", 1, True)],
    )

    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")], [project], [models.Skill("py", "Python")]
    )

    assert result.is_feasible is False
    assert any("mandatory skill 'py'" in reason for reason in result.infeasibility_reasons)


@pytest.mark.parametrize("level", INVALID_LEVELS)
def test_student_skill_level_must_be_an_integer_from_one_to_five(level: object) -> None:
    """SKILL-02: Stored profile levels must be usable before any matching."""
    student = models.Student("S1", "Student 1", skills={"py": level})  # type: ignore[dict-item]
    project = models.Project(
        "P1", "Project 1", min_capacity=1,
        requirements=[models.ProjectRequirement("P1", "py", 2, True)],
    )

    result = validation.validate_cohort([student], [project], [models.Skill("py", "Python")])

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "Student 'S1'" in result.errors[0] and "py" in result.errors[0]
    assert "whole number from 1 to 5" in result.errors[0]
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("level", INVALID_LEVELS)
def test_requirement_level_must_be_an_integer_from_one_to_five(level: object) -> None:
    """SKILL-03: Reject bad requirements before comparing proficiency levels."""
    project = models.Project(
        "P1", "Project 1", min_capacity=1,
        requirements=[models.ProjectRequirement("P1", "py", level, True)],  # type: ignore[arg-type]
    )

    result = validation.validate_cohort(
        [models.Student("S1", "Student 1", skills={"py": 5})],
        [project], [models.Skill("py", "Python")],
    )

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "Project 'P1'" in result.errors[0] and "py" in result.errors[0]
    assert "whole number from 1 to 5" in result.errors[0]
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("level", [1, 5])
@pytest.mark.parametrize("mandatory", [False, True])
def test_skill_level_boundaries_and_boolean_flags_are_valid(level: int, mandatory: bool) -> None:
    """SKILL-02/03/08: Both level boundaries and real booleans are allowed."""
    project = models.Project(
        "P1", "Project 1",
        requirements=[models.ProjectRequirement("P1", "py", level, mandatory)],
    )
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1", skills={"py": level})],
        [project], [models.Skill("py", "Python")],
    )

    assert result.is_valid is True
    assert result.errors == []
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("owner", ["student", "project"])
@pytest.mark.parametrize("catalogue", [None, [], [models.Skill("py", "Python")]])
def test_skill_reference_checks_distinguish_omitted_and_empty_catalogues(
    owner: str, catalogue: list[models.Skill] | None
) -> None:
    """SKILL-04/05: Omitted catalogue warns; supplied catalogues enforce membership."""
    student = models.Student("S1", "Student 1")
    project = models.Project("P1", "Project 1")
    if owner == "student":
        student.skills = {"ghost": 2}
    else:
        project.requirements = [models.ProjectRequirement("P1", "ghost", 2, True)]
        student.skills = {"ghost": 2}

    result = validation.validate_cohort([student], [project], catalogue)

    if catalogue is None:
        assert result.is_valid is True
        assert any("catalogue was omitted" in warning for warning in result.warnings)
    else:
        assert result.is_valid is False
        owner_id = "S1" if owner == "student" else "P1"
        assert any(
            owner_id in error and "unknown skill 'ghost'" in error
            for error in result.errors
        ), result.errors
        assert result.infeasibility_reasons == []


@pytest.mark.parametrize("catalogue", [None, []])
def test_no_catalogue_is_needed_when_no_skills_are_used(catalogue: list[models.Skill] | None) -> None:
    """SKILL-05/06: Skill-free data need no catalogue or missing-catalogue warning."""
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")], [models.Project("P1", "Project 1")], catalogue
    )

    assert result.is_valid is True
    assert not any("catalogue was omitted" in warning for warning in result.warnings)


@pytest.mark.parametrize("profile", [{}, {"py": 5}])
def test_project_without_requirements_has_full_skill_fit(profile: dict[str, int]) -> None:
    """SKILL-06: With no requirements there is nothing unmet or to divide by."""
    student = models.Student("S1", "Student 1", skills=profile)
    project = models.Project("P1", "Project 1")

    assert metrics.calculate_assignment_skill_fit(student, project) == (1.0, [])


@pytest.mark.parametrize(("second_level", "second_flag"), [(2, False), (3, False), (2, True)])
def test_repeated_requirements_are_rejected(second_level: int, second_flag: bool) -> None:
    """SKILL-07: Identical and conflicting rows both need correction."""
    requirements = [
        models.ProjectRequirement("P1", "py", 2, False),
        models.ProjectRequirement("P1", "py", second_level, second_flag),
    ]
    project = models.Project("P1", "Project 1", requirements=requirements.copy())

    result = validation.validate_cohort(
        [models.Student("S1", "Student 1", skills={"py": 5})],
        [project], [models.Skill("py", "Python")],
    )

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "Project 'P1'" in result.errors[0]
    assert "skill 'py' more than once" in result.errors[0]
    assert project.requirements == requirements
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize(
    "flag", [None, 0, 1, -1, 2, "true", "false", "0", "1", "", [], {}, 0.0, 1.0],
)
def test_mandatory_skill_flag_must_be_a_boolean(flag: object) -> None:
    """SKILL-08: Truthy strings or numbers are not accepted as domain booleans."""
    project = models.Project(
        "P1", "Project 1", min_capacity=1,
        requirements=[models.ProjectRequirement("P1", "py", 1, flag)],  # type: ignore[arg-type]
    )

    result = validation.validate_cohort(
        [models.Student("S1", "Student 1")], [project], [models.Skill("py", "Python")]
    )

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "Project 'P1'" in result.errors[0] and "py" in result.errors[0]
    assert "mandatory flag must be True or False" in result.errors[0]
    assert result.infeasibility_reasons == []


def test_skill_errors_are_reported_together_before_mandatory_matching() -> None:
    """Several bad fields must not cause a crash or a false skill-infeasibility claim."""
    project = models.Project(
        "P1", "Project 1",
        requirements=[
            models.ProjectRequirement("P1", "py", None, "false"),  # type: ignore[arg-type]
            models.ProjectRequirement("P1", "py", 2, True),
        ],
    )
    result = validation.validate_cohort(
        [models.Student("S1", "Student 1", skills={"py": "bad"})],  # type: ignore[dict-item]
        [project], [models.Skill("py", "Python")],
    )

    assert result.is_valid is False
    assert len(result.errors) == 4
    assert result.infeasibility_reasons == []
