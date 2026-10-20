"""PREF-01 to PREF-08: warnings and errors for ranked project choices."""

import pytest

from app.domain import models
from app.domain import validation


def _projects(count: int = 3) -> list[models.Project]:
    """Builds a small catalogue with enough total places for these examples."""
    return [
        models.Project(f"P{number}", f"Project {number}", max_capacity=2)
        for number in range(1, count + 1)
    ]


@pytest.mark.parametrize("ranked_count", [1, 2])
def test_short_preference_list_warns(ranked_count: int) -> None:
    """PREF-01: One or two choices are accepted with an explanatory warning."""
    preferences = [
        models.Preference("S1", f"P{rank}", rank)
        for rank in range(1, ranked_count + 1)
    ]
    student = models.Student("S1", "Student 1", preferences=preferences)

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is True
    assert result.errors == []
    assert any(
        "S1" in warning and f"ranked {ranked_count}" in warning
        and "at least 3" in warning
        for warning in result.warnings
    ), result.warnings
    assert student.preferences == preferences


@pytest.mark.parametrize("project_count", [1, 2])
def test_small_project_catalogue_is_explained(project_count: int) -> None:
    """PREF-01: Explain why three choices are impossible in a small catalogue."""
    student = models.Student(
        "S1", "Student 1",
        preferences=[
            models.Preference("S1", f"P{rank}", rank)
            for rank in range(1, project_count + 1)
        ],
    )

    result = validation.validate_cohort([student], _projects(project_count))

    assert result.is_valid is True
    assert any(
        f"{project_count} available" in warning
        and "Fewer than 3 projects are offered" in warning
        for warning in result.warnings
    ), result.warnings


def test_no_preferences_warns_about_unranked_assignment() -> None:
    """PREF-02: An empty list is a warning, without invented choices."""
    student = models.Student("S1", "Student 1")

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is True
    assert result.errors == []
    assert len(result.warnings) == 1
    assert "S1" in result.warnings[0]
    assert "no ranked preferences" in result.warnings[0]
    assert "at least 3" in result.warnings[0]
    assert "unranked project" in result.warnings[0]
    assert student.preferences == []


@pytest.mark.parametrize("project_count", [3, 4])
def test_three_or_more_valid_preferences_need_no_warning(project_count: int) -> None:
    """PREF-01: Complete lists are accepted; more than three choices are allowed."""
    student = models.Student(
        "S1", "Student 1",
        preferences=[
            models.Preference("S1", f"P{rank}", rank)
            for rank in range(1, project_count + 1)
        ],
    )

    result = validation.validate_cohort([student], _projects(project_count))

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == []


@pytest.mark.parametrize("last_project", ["P1", "P99"])
def test_bad_entries_do_not_count_as_three_choices(last_project: str) -> None:
    """PREF-01/03/08: Count distinct known projects, not duplicate or unknown IDs."""
    student = models.Student(
        "S1", "Student 1",
        preferences=[
            models.Preference("S1", "P1", 1),
            models.Preference("S1", "P2", 2),
            models.Preference("S1", last_project, 3),
        ],
    )

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is False
    assert any("S1" in warning and "ranked 2" in warning for warning in result.warnings)


def test_repeated_project_is_rejected() -> None:
    """PREF-03: Two positions cannot refer to the same project for one student."""
    preferences = [
        models.Preference("S1", "P1", 1), models.Preference("S1", "P1", 2)
    ]
    student = models.Student("S1", "Student 1", preferences=preferences)

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is False
    assert any(
        "S1" in error and "P1" in error and "more than once" in error
        for error in result.errors
    ), result.errors
    assert student.preferences == preferences
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("rank", [1, 2])
def test_tied_ranks_within_one_student_are_rejected(rank: int) -> None:
    """PREF-04: Reject ties until the application can store them consistently."""
    student = models.Student(
        "S1", "Student 1",
        preferences=[
            models.Preference("S1", "P1", rank), models.Preference("S1", "P2", rank)
        ],
    )

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is False
    assert any(
        "S1" in error and f"rank {rank}" in error and "more than once" in error
        for error in result.errors
    ), result.errors
    assert result.infeasibility_reasons == []


def test_students_can_compete_for_the_same_first_choice() -> None:
    """PREF-05: Demand exceeding one project's places is not an input error."""
    students = []
    for student_id in ["S1", "S2"]:
        students.append(models.Student(
            student_id, student_id,
            preferences=[
                models.Preference(student_id, "P1", 1),
                models.Preference(student_id, "P2", 2),
                models.Preference(student_id, "P3", 3),
            ],
        ))
    projects = _projects()
    projects[0].max_capacity = 1

    result = validation.validate_cohort(students, projects)

    assert result.is_valid is True
    assert result.is_feasible is True
    assert result.errors == []
    assert result.warnings == []


@pytest.mark.parametrize(
    "rank",
    [
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative"),
        pytest.param(1.5, id="fraction"),
        pytest.param(2.0, id="whole-looking-float"),
        pytest.param("1", id="numeric-text"),
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
    ],
)
def test_preference_rank_must_be_a_positive_integer(rank: object) -> None:
    """PREF-06: Reject bad values before comparing ranks or adding them to sets."""
    student = models.Student(
        "S1", "Student 1",
        preferences=[models.Preference("S1", "P1", rank)],  # type: ignore[arg-type]
    )

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "S1" in result.errors[0] and "P1" in result.errors[0]
    assert "positive whole number" in result.errors[0]
    assert result.infeasibility_reasons == []


def test_multiple_preference_errors_are_reported_together() -> None:
    """PREF-03/04/06/08: A bad rank does not hide other preference errors."""
    student = models.Student(
        "S1", "Student 1",
        preferences=[
            models.Preference("S1", "P1", []),  # type: ignore[arg-type]
            models.Preference("S1", "P2", 1),
            models.Preference("S1", "P2", 1),
            models.Preference("S1", "P99", 2),
        ],
    )

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is False
    assert len(result.errors) == 4
    for message in [
        "positive whole number", "project 'P2' more than once",
        "rank 1 more than once", "unknown project 'P99'",
    ]:
        assert any(message in error for error in result.errors), result.errors


@pytest.mark.parametrize("ranks", [[1, 3, 7], [2], [2, 3, 4], [1, 2, 10**12]])
def test_rank_gaps_are_rejected_without_renumbering(ranks: list[int]) -> None:
    """PREF-07: Require positions 1 through N, including for very large ranks."""
    preferences = [
        models.Preference("S1", f"P{number}", rank)
        for number, rank in enumerate(ranks, start=1)
    ]
    student = models.Student("S1", "Student 1", preferences=preferences)

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is False
    assert len(result.errors) == 1
    assert "S1" in result.errors[0] and "without gaps" in result.errors[0]
    assert [pref.rank for pref in student.preferences] == ranks
    assert result.infeasibility_reasons == []


def test_valid_ranks_need_not_arrive_in_sorted_order() -> None:
    """PREF-07: Rank values determine order; input list order need not match."""
    preferences = [
        models.Preference("S1", "P3", 3),
        models.Preference("S1", "P1", 1),
        models.Preference("S1", "P2", 2),
    ]
    student = models.Student("S1", "Student 1", preferences=preferences)

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is True
    assert result.warnings == []
    assert [pref.rank for pref in student.preferences] == [3, 1, 2]


def test_unknown_preference_project_identifies_student_and_project() -> None:
    """PREF-08: Tell the caller which reference must be corrected."""
    student = models.Student(
        "S1", "Student 1", preferences=[models.Preference("S1", "P99", 1)]
    )

    result = validation.validate_cohort([student], _projects())

    assert result.is_valid is False
    assert any("S1" in error and "unknown project 'P99'" in error for error in result.errors)
    assert student.preferences[0].project_id == "P99"
