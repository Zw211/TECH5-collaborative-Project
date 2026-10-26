"""Transparent recommendation generator distinguishing evidence from advice.

This module implements the decision-support engine required by Section 9 of the
TECH5 specification, providing inspectable recommendations with explicit
criteria, mathematical evidence, and policy-oriented advice.

Each priority ranks the feasible alternatives by an ordered list of
indicators. Missing indicators are never replaced by default values: an
alternative that does not report the primary indicator of a priority is not
considered for it, and missing secondary indicators rank last. The evidence
states the recommended alternative's values next to those of the other
alternatives so every recommendation can be checked.
"""

import dataclasses
from typing import Any

from app.domain import models

# Decimal places used when comparing indicator values for ties.
_TIE_PRECISION = 6


@dataclasses.dataclass(frozen=True)
class Criterion:
    """An indicator used to rank or describe alternative solutions.

    Attributes:
        label: Short display name of the indicator.
        group: Indicator group in Solution.indicators (e.g. "fairness").
        key: Indicator key within the group.
        lower_is_better: True when smaller values are preferred.
        description: Explanation shown in the list of criteria used.
        digits: Decimal places shown; 0 displays the value as an integer.
    """

    label: str
    group: str
    key: str
    lower_is_better: bool
    description: str
    digits: int = 2


UNRANKED = Criterion(
    "Students outside preferences",
    "fairness",
    "unranked_count",
    True,
    "Count of students assigned outside stated preferences",
    digits=0,
)
MEAN_RANK = Criterion(
    "Mean preference rank",
    "fairness",
    "mean_rank",
    True,
    "Average student preference rank (lower is better)",
)
WORST_RANK = Criterion(
    "Worst preference rank",
    "fairness",
    "worst_rank",
    True,
    "Worst individual student rank",
    digits=0,
)
SKILL_FIT = Criterion(
    "Mean skill fit",
    "efficiency",
    "mean_skill_fit",
    False,
    "Average student-project skill fit score (higher is better)",
)
UNMET_SOFT = Criterion(
    "Unmet soft requirements",
    "efficiency",
    "unmet_soft_requirements_count",
    True,
    "Total unmet soft skill requirements (lower is better)",
    digits=0,
)
RANK_GINI = Criterion(
    "Rank Gini coefficient",
    "fairness",
    "rank_gini",
    True,
    "Rank Gini coefficient (equality of outcome distribution)",
    digits=3,
)
RANK_VARIANCE = Criterion(
    "Rank variance",
    "fairness",
    "rank_variance",
    True,
    "Rank variance across students (lower is better)",
)

# Rows of the evidence table comparing all alternatives.
TABLE_CRITERIA = [
    UNRANKED,
    MEAN_RANK,
    WORST_RANK,
    SKILL_FIT,
    UNMET_SOFT,
    RANK_GINI,
    RANK_VARIANCE,
]


@dataclasses.dataclass(frozen=True)
class _Priority:
    """A decision priority and the indicators that rank alternatives for it.

    Attributes:
        focus: Name of the organizational objective.
        ranking: Indicators in order of importance; the first is required.
        context: Further indicators reported to show the trade-off.
        advice: Advice text with an {alt} placeholder for the alternative.
    """

    focus: str
    ranking: list[Criterion]
    context: list[Criterion]
    advice: str


_PRIORITIES = [
    _Priority(
        focus="Student Preference Maximization",
        ranking=[UNRANKED, MEAN_RANK, WORST_RANK],
        context=[SKILL_FIT],
        advice=(
            "Adopt Solution {alt} if student satisfaction, programme "
            "morale, and minimizing student appeals are the primary "
            "administrative goals."
        ),
    ),
    _Priority(
        focus="Project Skill Quality & Delivery Assurance",
        ranking=[SKILL_FIT, UNMET_SOFT],
        context=[MEAN_RANK],
        advice=(
            "Adopt Solution {alt} when partner organizations or client "
            "project deliverables demand rigorous technical and domain "
            "capabilities."
        ),
    ),
    _Priority(
        focus="Balanced & Egalitarian Allocation",
        ranking=[RANK_GINI, RANK_VARIANCE, MEAN_RANK],
        context=[SKILL_FIT],
        advice=(
            "Adopt Solution {alt} if the academic committee seeks a fair "
            "compromise that avoids extreme individual disadvantage."
        ),
    ),
]


@dataclasses.dataclass
class RecommendationItem:
    """An individual decision recommendation.

    Attributes:
        priority_focus: The organizational objective prioritized (e.g.
            Student Satisfaction, Project Skill Delivery, Egalitarian Balance).
        recommended_solution_id: Identifier of the top solution for this focus.
        recommended_alternative_number: 1-based index of recommended solution.
        criteria_used: Explicit list of analytical metrics evaluated.
        evidence: Objective calculated facts supporting the recommendation.
        advice: Practical normative advice describing operational trade-offs.
        tied_alternatives: Other alternatives equal on every criterion used.
        notes: Facts about the run as a whole, shared by all items.
    """

    priority_focus: str
    recommended_solution_id: str
    recommended_alternative_number: int
    criteria_used: list[str]
    evidence: list[str]
    advice: str
    tied_alternatives: list[int] = dataclasses.field(default_factory=list)
    notes: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes recommendation item to a dictionary.

        Returns:
            Dictionary containing recommendation fields.
        """
        return {
            "priority_focus": self.priority_focus,
            "recommended_solution_id": self.recommended_solution_id,
            "recommended_alternative_number": (
                self.recommended_alternative_number
            ),
            "criteria_used": list(self.criteria_used),
            "evidence": list(self.evidence),
            "advice": self.advice,
            "tied_alternatives": list(self.tied_alternatives),
            "notes": list(self.notes),
        }


def generate_recommendations(
    solutions: list[models.Solution],
) -> list[RecommendationItem]:
    """Generates policy-oriented recommendations from alternative solutions.

    Args:
        solutions: Alternative solutions from an assignment run. Solutions
            reported as infeasible are excluded.

    Returns:
        List of structured RecommendationItem instances, empty when no
        feasible solution exists.
    """
    feasible = [s for s in solutions if _is_feasible(s)]
    if not feasible:
        return []

    items: list[RecommendationItem] = []
    skipped: list[str] = []
    for priority in _PRIORITIES:
        item = _recommend(priority, feasible)
        if item is None:
            skipped.append(priority.focus)
        else:
            items.append(item)

    notes = _run_notes(solutions, feasible, items, skipped)
    for item in items:
        item.notes = list(notes)
    return items


def evidence_table(
    solutions: list[models.Solution],
) -> list[dict[str, Any]]:
    """Builds a table of every ranking indicator for every alternative.

    Args:
        solutions: Alternative solutions from an assignment run.

    Returns:
        One row per indicator with keys "label", "description" and
        "cells". Each cell holds "alternative", "text" and "best", where
        "best" marks the preferred value among feasible alternatives.
    """
    ordered = sorted(solutions, key=lambda s: s.alternative_number)
    rows = []
    for criterion in TABLE_CRITERIA:
        best = _best_value(
            criterion, [s for s in ordered if _is_feasible(s)]
        )
        cells = []
        for solution in ordered:
            value = _metric(solution, criterion)
            cells.append(
                {
                    "alternative": solution.alternative_number,
                    "text": _format(solution, criterion, value),
                    "best": (
                        best is not None
                        and _is_feasible(solution)
                        and value is not None
                        and round(value, _TIE_PRECISION) == best
                    ),
                }
            )
        rows.append(
            {
                "label": criterion.label,
                "description": criterion.description,
                "cells": cells,
            }
        )
    return rows


def _recommend(
    priority: _Priority, feasible: list[models.Solution]
) -> RecommendationItem | None:
    """Selects and explains the best alternative for one priority.

    Args:
        priority: The priority to evaluate.
        feasible: Feasible alternative solutions.

    Returns:
        The recommendation, or None if no alternative reports the primary
        indicator of the priority.
    """
    candidates = [
        s for s in feasible if _metric(s, priority.ranking[0]) is not None
    ]
    if not candidates:
        return None

    def sort_key(solution: models.Solution) -> tuple[Any, ...]:
        return tuple(_sort_value(solution, c) for c in priority.ranking)

    candidates.sort(key=lambda s: (sort_key(s), s.alternative_number))
    best = candidates[0]
    tied = [
        s.alternative_number
        for s in candidates[1:]
        if sort_key(s) == sort_key(best)
    ]
    others = [s for s in feasible if s.id != best.id]

    evidence = [
        _evidence_line(best, criterion, others)
        for criterion in priority.ranking + priority.context
    ]
    if MEAN_RANK in priority.ranking + priority.context:
        penalty_note = _penalty_note(best, feasible)
        if penalty_note:
            evidence.append(penalty_note)
    if tied:
        evidence.append(
            f"{_alternatives([best.alternative_number] + tied)} tie on "
            "all criteria; the lowest-numbered alternative is shown."
        )

    return RecommendationItem(
        priority_focus=priority.focus,
        recommended_solution_id=best.id,
        recommended_alternative_number=best.alternative_number,
        criteria_used=[c.description for c in priority.ranking],
        evidence=evidence,
        advice=priority.advice.format(alt=best.alternative_number),
        tied_alternatives=tied,
    )


def _run_notes(
    solutions: list[models.Solution],
    feasible: list[models.Solution],
    items: list[RecommendationItem],
    skipped: list[str],
) -> list[str]:
    """Describes facts about the run that affect every recommendation.

    Args:
        solutions: All alternative solutions of the run.
        feasible: The feasible subset of solutions.
        items: Recommendations generated for the run.
        skipped: Priorities that could not be evaluated.

    Returns:
        Human-readable notes, possibly empty.
    """
    notes = []
    excluded = sorted(
        s.alternative_number for s in solutions if not _is_feasible(s)
    )
    if excluded:
        notes.append(
            "Not recommended because hard constraints are violated: "
            f"{_alternatives(excluded)}."
        )
    if len(feasible) == 1:
        notes.append(
            "Only one feasible alternative was generated, so the "
            "recommendations cannot compare alternatives."
        )
    elif len(items) > 1 and len(
        {item.recommended_solution_id for item in items}
    ) == 1:
        notes.append(
            f"Alternative {items[0].recommended_alternative_number} is "
            "recommended for every priority, so this run shows no "
            "trade-off between the priorities."
        )
    for focus in skipped:
        notes.append(
            f"No recommendation for {focus}: the alternatives do not "
            "report the required indicators."
        )
    return notes


def _is_feasible(solution: models.Solution) -> bool:
    """Returns False only when the solution reports itself infeasible."""
    feasibility = solution.indicators.get("feasibility", {})
    return feasibility.get("is_feasible", True) is not False


def _metric(
    solution: models.Solution, criterion: Criterion
) -> float | None:
    """Returns a numeric indicator value, or None if it is missing."""
    value = solution.indicators.get(criterion.group, {}).get(criterion.key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _sort_value(
    solution: models.Solution, criterion: Criterion
) -> tuple[int, float]:
    """Returns an ascending sort key; missing values sort last."""
    value = _metric(solution, criterion)
    if value is None:
        return (1, 0.0)
    value = round(value, _TIE_PRECISION)
    return (0, value if criterion.lower_is_better else -value)


def _best_value(
    criterion: Criterion, solutions: list[models.Solution]
) -> float | None:
    """Returns the preferred rounded value among the given solutions."""
    values = [
        round(v, _TIE_PRECISION)
        for v in (_metric(s, criterion) for s in solutions)
        if v is not None
    ]
    if not values:
        return None
    return min(values) if criterion.lower_is_better else max(values)


def _format(
    solution: models.Solution, criterion: Criterion, value: float | None
) -> str:
    """Formats an indicator value for display.

    A worst rank above the number of preferences a student could state is
    the engine's penalty for an unranked student, not a real rank, and is
    shown as such.
    """
    if value is None:
        return "not reported"
    if criterion is WORST_RANK:
        max_preferences = solution.indicators.get("fairness", {}).get(
            "max_preferences"
        )
        if isinstance(max_preferences, int) and value > max_preferences:
            return "outside preferences"
    if criterion.digits == 0:
        return str(round(value))
    return f"{value:.{criterion.digits}f}"


def _evidence_line(
    solution: models.Solution,
    criterion: Criterion,
    others: list[models.Solution],
) -> str:
    """States one indicator of a solution next to the other alternatives."""
    text = (
        f"{criterion.label}: "
        f"{_format(solution, criterion, _metric(solution, criterion))}"
    )
    measured = sorted(
        (
            (v, s)
            for s in others
            if (v := _metric(s, criterion)) is not None
        ),
        key=lambda pair: pair[0],
    )
    if not measured:
        return text + "."
    shown = []
    for value, other in measured:
        formatted = _format(other, criterion, value)
        if formatted not in shown:
            shown.append(formatted)
    if len(shown) > 3:
        shown = [shown[0], shown[-1]]
        return f"{text} (other alternatives: {shown[0]} to {shown[1]})."
    return f"{text} (other alternatives: {', '.join(shown)})."


def _penalty_note(
    solution: models.Solution, feasible: list[models.Solution]
) -> str | None:
    """Explains how unranked students enter the mean rank, if relevant."""
    penalty = solution.indicators.get("fairness", {}).get("unranked_penalty")
    if not isinstance(penalty, int):
        return None
    if not any((_metric(s, UNRANKED) or 0) > 0 for s in feasible):
        return None
    return (
        f"Students outside their preferences count as rank {penalty} in "
        "the mean rank and rank statistics."
    )


def _alternatives(numbers: list[int]) -> str:
    """Formats alternative numbers, e.g. 'Alternatives 1, 2 and 3'."""
    labels = [str(n) for n in numbers]
    if len(labels) == 1:
        return f"Alternative {labels[0]}"
    return f"Alternatives {', '.join(labels[:-1])} and {labels[-1]}"
