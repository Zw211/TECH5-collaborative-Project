"""Known Gini values and input boundaries, independent of rank policy."""

import pytest

from app.engine import metrics


@pytest.mark.parametrize(
    "values,expected",
    [
        ([], 0.0),
        ([0.0, 0.0], 0.0),
        ([7.0], 0.0),
        ([2.0, 2.0, 2.0], 0.0),
        ([0.0, 1.0], 0.5),
        ([1.0, 2.0, 3.0], 2 / 9),
        ([0.0, 0.0, 1.0], 2 / 3),
        ([1e308, 1e308], 0.0),
    ],
)
def test_known_gini(values: list[float], expected: float) -> None:
    """Check equality, small analytical examples, and overflow resistance."""
    original = list(values)
    assert metrics.calculate_gini(values) == pytest.approx(expected)
    assert values == original


@pytest.mark.parametrize(
    "values", [[1.0, -1.0], [float("nan")], [float("inf")], [-float("inf")]]
)
def test_invalid_gini(values: list[float]) -> None:
    """Reject values for which the promised Gini definition does not apply."""
    with pytest.raises(ValueError, match="finite and non-negative"):
        metrics.calculate_gini(values)


def test_order_and_scale_invariance() -> None:
    """Sorting or scaling the data must not change measured inequality."""
    expected = metrics.calculate_gini([1.0, 2.0, 7.0])
    assert metrics.calculate_gini([7.0, 1.0, 2.0]) == pytest.approx(expected)
    assert metrics.calculate_gini([10.0, 20.0, 70.0]) == pytest.approx(expected)
