"""Check scoring and optimality against independent tiny enumerations."""

import itertools
from typing import Any

import pulp
import pytest

from app.domain import models
from app.engine import metrics, solvers

STRATEGIES = [
    solvers.PreferenceOrientedSolver,
    solvers.SkillFitOrientedSolver,
    solvers.BalancedTradeoffSolver,
]


@pytest.mark.parametrize(
    "level,expected,unmet",
    [
        (0, 0.0, ["py"]),
        (1, 0.25, ["py"]),
        (4, 1.0, []),
        (5, 1.0, []),
    ],
)
def test_skill_fit_boundaries(
    level: int,
    expected: float,
    unmet: list[str],
) -> None:
    """Missing skills score zero; meeting and exceeding a level score one."""
    student = models.Student("S", "S", {"py": level} if level else {})
    project = models.Project(
        "P", "P", requirements=[models.ProjectRequirement("P", "py", 4, True)]
    )
    fit, missing = metrics.calculate_assignment_skill_fit(student, project)
    assert fit == expected
    assert missing == unmet


def test_equal_requirement_weights_and_empty_requirements() -> None:
    """Mandatory flags do not change scoring weights; empty requirements fit."""
    student = models.Student("S", "S", {"py": 5, "sql": 1})
    project = models.Project(
        "P",
        "P",
        requirements=[
            models.ProjectRequirement("P", "py", 2, True),
            models.ProjectRequirement("P", "sql", 2),
            models.ProjectRequirement("P", "web", 1),
        ],
    )
    assert metrics.calculate_assignment_skill_fit(student, project) == (
        0.5,
        ["sql", "web"],
    )
    assert metrics.calculate_assignment_skill_fit(
        student, models.Project("Q", "Q")
    ) == (1.0, [])


@pytest.mark.parametrize(
    "rank,expected", [(1, 1.0), (2, 2 / 3), (3, 1 / 3), (None, 0.0)]
)
def test_preference_scores(rank: int | None, expected: float) -> None:
    """The shared cohort scale gives ranked projects the agreed utility."""
    student = models.Student(
        "S",
        "S",
        preferences=([models.Preference("S", "P", rank)] if rank else []),
    )
    assert solvers.PreferenceOrientedSolver().calculate_cost_or_utility(
        student, models.Project("P", "P"), 3
    ) == pytest.approx(expected)


@pytest.mark.parametrize("strategy_class", STRATEGIES)
def test_no_preferences_and_no_requirements(
    strategy_class: type[solvers.AssignmentStrategy],
) -> None:
    """An all-zero preference objective is valid and never divides by zero."""
    strategy = strategy_class()
    status, assignments, value, info = strategy.solve(
        [models.Student("S", "S")], [models.Project("P", "P")]
    )
    assert status == "FEASIBLE"
    assert (
        value
        == {"PREFERENCE": 0.0, "SKILL_FIT": 1.0, "BALANCED": 0.5}[strategy.name]
    )
    assert info["optimality_proven"] is True
    assert info["max_preferences"] == 0
    assert assignments[0].skill_fit_score == 1.0
    assert assignments[0].unmet_requirements == []


@pytest.mark.parametrize("strategy_class", STRATEGIES)
@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("mandatory", [False, True])
def test_optimum_against_exhaustive_enumeration(
    strategy_class: type[solvers.AssignmentStrategy],
    locked: bool,
    mandatory: bool,
) -> None:
    """Enumerate every allocation and independently score each feasible one."""
    students = [
        models.Student(
            "A",
            "A",
            {"py": 4, "sql": 1},
            preferences=[
                models.Preference("A", "Q", 1),
                models.Preference("A", "P", 2),
                models.Preference("A", "R", 3),
            ],
        ),
        models.Student(
            "B", "B", {"sql": 4}, preferences=[models.Preference("B", "P", 1)]
        ),
        models.Student("C", "C", {"py": 1, "sql": 2}),
    ]
    projects = [
        models.Project(
            "P",
            "P",
            min_capacity=1,
            max_capacity=2,
            requirements=[models.ProjectRequirement("P", "py", 4, mandatory)],
        ),
        models.Project(
            "Q",
            "Q",
            max_capacity=2,
            requirements=[models.ProjectRequirement("Q", "sql", 4)],
        ),
        models.Project("R", "R"),
    ]
    locks = [models.FixedAssignment("B", "P")] if locked else []
    strategy = strategy_class()
    scores = {}
    # Three students and three projects: only 27 possibilities, no solver used.
    for choices in itertools.product(range(3), repeat=3):
        if not 1 <= choices.count(0) <= 2 or choices.count(1) > 2:
            continue
        if choices.count(2) > 1 or (locked and choices[1] != 0):
            continue
        if mandatory and choices[0] != 0:  # A alone meets Python level 4.
            continue
        preference_scores = [
            [2 / 3, 1.0, 1 / 3],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
        skill_scores = [[1.0, 0.25, 1.0], [0.0, 1.0, 1.0], [0.25, 0.5, 1.0]]
        preference = sum(preference_scores[i][p] for i, p in enumerate(choices))
        skill = sum(skill_scores[i][p] for i, p in enumerate(choices))
        scores[choices] = {
            "PREFERENCE": preference,
            "SKILL_FIT": skill,
            "BALANCED": (preference + skill) / 2,
        }[strategy.name]
    assert scores
    status, assignments, value, info = strategy.solve(students, projects, locks)
    assert status == "FEASIBLE", info
    project_index = {project.id: i for i, project in enumerate(projects)}
    assigned = {a.student_id: project_index[a.project_id] for a in assignments}
    choices = tuple(assigned[s.id] for s in students)
    assert choices in scores
    assert value == pytest.approx(max(scores.values()))
    assert value == pytest.approx(scores[choices])
    assert info["max_preferences"] == 3  # B's short list uses the same scale.
    assert info["optimality_proven"] is True
    assert info["assignment_skill_fit_computed"] is True
    for assignment in assignments:
        student = next(s for s in students if s.id == assignment.student_id)
        project = projects[project_index[assignment.project_id]]
        fit, unmet = metrics.calculate_assignment_skill_fit(student, project)
        assert assignment.skill_fit_score == fit
        assert assignment.unmet_requirements == unmet


def test_strategies_can_choose_different_assignments() -> None:
    """Skill advantage can outweigh a second-choice penalty in balanced mode."""
    students = [
        models.Student(
            "A",
            "A",
            {"sql": 4},
            preferences=[
                models.Preference("A", "P", 1),
                models.Preference("A", "Q", 2),
            ],
        ),
        models.Student(
            "B",
            "B",
            {"py": 4},
            preferences=[
                models.Preference("B", "Q", 1),
                models.Preference("B", "P", 2),
            ],
        ),
    ]
    projects = [
        models.Project(
            "P", "P", requirements=[models.ProjectRequirement("P", "py", 4)]
        ),
        models.Project(
            "Q", "Q", requirements=[models.ProjectRequirement("Q", "sql", 4)]
        ),
    ]
    expected = [("P", "Q", 2.0), ("Q", "P", 2.0), ("Q", "P", 1.5)]
    for strategy_class, (a, b, score) in zip(STRATEGIES, expected):
        status, assignments, value, info = strategy_class().solve(
            students, projects
        )
        assert status == "FEASIBLE", info
        assert {x.student_id: x.project_id for x in assignments} == {
            "A": a,
            "B": b,
        }
        assert value == score


def test_incumbent_score_does_not_claim_optimality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid incumbent retains its score without a false optimality claim."""
    original_solve = pulp.LpProblem.solve

    def stopped_solve(problem: pulp.LpProblem, solver: Any) -> int:
        """Keep CBC values but simulate a stopped solve with an incumbent."""
        original_solve(problem, solver)
        problem.status = pulp.LpStatusOptimal
        problem.sol_status = pulp.LpSolutionIntegerFeasible
        return problem.status

    monkeypatch.setattr(pulp.LpProblem, "solve", stopped_solve)
    status, assignments, value, info = solvers.PreferenceOrientedSolver().solve(
        [
            models.Student(
                "S", "S", preferences=[models.Preference("S", "P", 1)]
            )
        ],
        [models.Project("P", "P")],
    )
    assert status == "FEASIBLE"
    assert len(assignments) == 1
    assert value == 1.0
    assert info["optimality_proven"] is False
    assert any("optimality is not proven" in w for w in info["warnings"])
