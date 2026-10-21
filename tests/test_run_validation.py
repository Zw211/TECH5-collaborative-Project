"""RUN-01/02: settings validation does not require an assignment solver."""

import pytest

from app.contract import contract
from app.domain import models
from app.engine import solvers
from app.visualization import forms


@pytest.mark.parametrize("strategy", ["PREFERENCE", "SKILL_FIT", "BALANCED"])
@pytest.mark.parametrize("count", [1, 4])
def test_dashboard_run_settings_are_accepted(strategy: str, count: int) -> None:
    """Accept supported strategies and dashboard alternative counts."""
    request = contract.RunRequest(
        students=[models.Student("S1", "Student 1")],
        projects=[models.Project("P1", "Project 1")],
        strategy_key=strategy,
        max_alternatives=count,
    )

    result = solvers.AssignmentEngine().validate_inputs(request)

    assert result.is_valid is True


@pytest.mark.parametrize(
    "strategy", [None, "", "preference", "UNKNOWN", True, 1, [], {}]
)
def test_unknown_run_strategy_is_rejected(strategy: object) -> None:
    """Reject unknown strategy names and non-text values."""
    request = contract.RunRequest(
        students=[models.Student("S1", "Student 1")],
        projects=[models.Project("P1", "Project 1")],
        strategy_key=strategy,  # type: ignore[arg-type]
    )

    result = solvers.AssignmentEngine().validate_inputs(request)

    assert result.is_valid is False
    assert any("strategy" in error for error in result.errors)
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize(
    "count",
    [
        None,
        0,
        -1,
        5,
        10**12,
        1.5,
        2.0,
        "3",
        "",
        True,
        False,
        float("nan"),
        float("inf"),
        [],
        {},
    ],
)
def test_invalid_alternative_count_is_rejected(count: object) -> None:
    """Reject counts outside the supported integer range."""
    request = contract.RunRequest(
        students=[models.Student("S1", "Student 1")],
        projects=[models.Project("P1", "Project 1")],
        max_alternatives=count,  # type: ignore[arg-type]
    )

    result = solvers.AssignmentEngine().validate_inputs(request)

    assert result.is_valid is False
    assert any(
        "alternatives" in error and "1 to 4" in error for error in result.errors
    )
    assert result.infeasibility_reasons == []


@pytest.mark.parametrize("raw", ["", "bad", "2.0", "true", "0", "5"])
def test_run_form_rejects_bad_count(raw: str) -> None:
    """Report malformed dashboard counts without starting a run."""
    form = forms.RunSettingsForm({"max_alternatives": raw})

    assert form.to_settings() is None
    assert form.errors


def test_run_form_parses_text_and_uses_default_strategy() -> None:
    """Parse a textual count and preserve the default strategy."""
    form = forms.RunSettingsForm({"max_alternatives": " 3 "})

    assert form.to_settings() == ("PREFERENCE", 3)
    assert form.errors == []
