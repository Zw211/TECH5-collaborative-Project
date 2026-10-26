"""Unit tests for transparent recommendations (app/engine/recommendations)."""

import pathlib
from typing import Any

from app import create_app
from app.domain import models
from app.engine import recommendations
from app.persistence import repositories


def _sol(
    alt: int,
    *,
    feasible: bool = True,
    fairness: dict[str, Any] | None = None,
    efficiency: dict[str, Any] | None = None,
) -> models.Solution:
    """Returns a solution whose indicators default to a neutral profile."""
    fair = {
        "unranked_count": 0,
        "mean_rank": 2.0,
        "worst_rank": 3,
        "rank_gini": 0.2,
        "rank_variance": 0.5,
    }
    eff = {"mean_skill_fit": 0.5, "unmet_soft_requirements_count": 2}
    fair.update(fairness or {})
    eff.update(efficiency or {})
    return models.Solution(
        id=f"sol{alt}",
        run_id="run",
        alternative_number=alt,
        strategy_name="test",
        indicators={
            "feasibility": {"is_feasible": feasible},
            "fairness": fair,
            "efficiency": eff,
        },
    )


def _by_focus(
    items: list[recommendations.RecommendationItem],
) -> dict[str, recommendations.RecommendationItem]:
    """Indexes recommendations by the first word of their focus."""
    return {item.priority_focus.split()[0]: item for item in items}


def test_trade_off_gives_different_recommendations() -> None:
    """Verifies each priority picks the alternative that is best for it."""
    items = recommendations.generate_recommendations(
        [
            _sol(1, fairness={"mean_rank": 1.2}),
            _sol(2, efficiency={"mean_skill_fit": 0.9}),
            _sol(3, fairness={"rank_gini": 0.05}),
        ]
    )
    by_focus = _by_focus(items)

    assert by_focus["Student"].recommended_alternative_number == 1
    assert by_focus["Project"].recommended_alternative_number == 2
    assert by_focus["Balanced"].recommended_alternative_number == 3
    assert items[0].notes == []


def test_evidence_compares_with_other_alternatives() -> None:
    """Verifies evidence shows rounded values next to the alternatives."""
    items = recommendations.generate_recommendations(
        [
            _sol(1, fairness={"mean_rank": 4 / 3}),
            _sol(2, fairness={"mean_rank": 2.5}),
        ]
    )
    evidence = _by_focus(items)["Student"].evidence

    assert "Mean preference rank: 1.33 (other alternatives: 2.50)." in (
        evidence
    )


def test_missing_indicator_is_not_treated_as_a_score() -> None:
    """Verifies a missing primary indicator excludes the alternative."""
    missing = _sol(1)
    del missing.indicators["efficiency"]["mean_skill_fit"]
    items = recommendations.generate_recommendations([missing, _sol(2)])
    skill = _by_focus(items)["Project"]

    assert skill.recommended_alternative_number == 2
    text = " ".join(skill.evidence)
    assert "999" not in text and "N/A" not in text


def test_priority_skipped_when_nobody_reports_it() -> None:
    """Verifies a priority without data is skipped and explained."""
    solutions = [_sol(1), _sol(2)]
    for solution in solutions:
        del solution.indicators["fairness"]["rank_gini"]
    items = recommendations.generate_recommendations(solutions)

    assert "Balanced" not in _by_focus(items)
    assert any("No recommendation for Balanced" in n for n in items[0].notes)


def test_infeasible_solutions_are_excluded() -> None:
    """Verifies infeasible alternatives are never recommended."""
    items = recommendations.generate_recommendations(
        [
            _sol(1, feasible=False, fairness={"mean_rank": 1.0}),
            _sol(2),
        ]
    )

    assert all(i.recommended_alternative_number == 2 for i in items)
    assert any("Alternative 1" in n for n in items[0].notes)


def test_all_infeasible_gives_no_recommendations() -> None:
    """Verifies no recommendation is made without a feasible solution."""
    assert recommendations.generate_recommendations(
        [_sol(1, feasible=False)]
    ) == []
    assert recommendations.generate_recommendations([]) == []


def test_ties_are_reported() -> None:
    """Verifies identical alternatives are reported as tied."""
    items = recommendations.generate_recommendations(
        [_sol(1), _sol(2), _sol(3, fairness={"mean_rank": 2.5})]
    )
    student = _by_focus(items)["Student"]

    assert student.recommended_alternative_number == 1
    assert student.tied_alternatives == [2]
    assert any("Alternatives 1 and 2 tie" in e for e in student.evidence)


def test_dominant_alternative_is_noted() -> None:
    """Verifies the run notes when one alternative wins every priority."""
    items = recommendations.generate_recommendations(
        [
            _sol(
                1,
                fairness={"mean_rank": 1.0, "rank_gini": 0.0},
                efficiency={"mean_skill_fit": 1.0},
            ),
            _sol(2),
        ]
    )

    assert any("recommended for every priority" in n for n in items[0].notes)


def test_single_alternative_is_noted() -> None:
    """Verifies a run with one alternative says it cannot compare."""
    items = recommendations.generate_recommendations([_sol(1)])

    assert len(items) == 3
    assert any("Only one feasible alternative" in n for n in items[0].notes)
    notes = " ".join(items[0].notes)
    assert "recommended for every priority" not in notes


def test_unranked_penalty_is_not_shown_as_a_rank() -> None:
    """Verifies the engine's penalty rank is explained, not printed."""
    penalty = {"max_preferences": 3, "unranked_penalty": 4}
    items = recommendations.generate_recommendations(
        [
            _sol(1, fairness={**penalty, "unranked_count": 1, "worst_rank": 4}),
            _sol(2, fairness={**penalty, "unranked_count": 2, "worst_rank": 4}),
        ]
    )
    evidence = _by_focus(items)["Student"].evidence

    assert "Worst preference rank: outside preferences" in evidence[2]
    assert any("count as rank 4" in e for e in evidence)


def test_evidence_table_highlights_best_feasible_values() -> None:
    """Verifies the table lists every alternative and marks the best."""
    rows = recommendations.evidence_table(
        [
            _sol(2, efficiency={"mean_skill_fit": 0.7}),
            _sol(1, feasible=False, efficiency={"mean_skill_fit": 0.9}),
        ]
    )
    fit = next(r for r in rows if r["label"] == "Mean skill fit")

    assert [c["alternative"] for c in fit["cells"]] == [1, 2]
    assert [c["best"] for c in fit["cells"]] == [False, True]
    assert fit["cells"][1]["text"] == "0.70"


def test_recommendations_page_shows_evidence_table(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies the page renders the evidence table for a real run."""
    app = create_app(
        {"TESTING": True, "DATABASE_PATH": tmp_path / "recs.db"}
    )
    client = app.test_client()
    client.post("/load-scenario/standard")
    client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 3},
    )
    run = repositories.RunRepository().list_runs(limit=1)[0]

    res = client.get(f"/recommendations/{run.id}")

    assert res.status_code == 200
    assert b"Evidence Across All Alternatives" in res.data
    assert b"Mean preference rank" in res.data
    assert b"mathematically optimal" not in res.data
