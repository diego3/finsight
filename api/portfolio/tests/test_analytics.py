"""Example-based unit tests for the pure portfolio analytics.

These pin down concrete, human-checked numbers. The invariants that must hold for
*any* portfolio live next door in ``test_analytics_properties.py``.
"""

from decimal import Decimal

import pytest

from portfolio.analytics import (
    Holding,
    InvalidHolding,
    PositionWeight,
    allocations,
    herfindahl_index,
    largest_position_weight,
    top_holdings,
    total_value,
)


def h(symbol: str, quantity: str, price: str) -> Holding:
    return Holding(symbol=symbol, quantity=Decimal(quantity), price=Decimal(price))


# A simple three-symbol portfolio worth 1,000: AAA 500, BBB 300, CCC 200.
SAMPLE = [
    h("AAA", "5", "100"),
    h("BBB", "3", "100"),
    h("CCC", "2", "100"),
]


class TestHoldingValidation:
    @pytest.mark.parametrize("quantity", ["-1", "-0.0001", "-1000000"])
    def test_negative_quantity_is_rejected(self, quantity: str) -> None:
        with pytest.raises(InvalidHolding, match="quantity"):
            h("AAA", quantity, "10")

    @pytest.mark.parametrize("price", ["-1", "-0.01", "-999"])
    def test_negative_price_is_rejected(self, price: str) -> None:
        with pytest.raises(InvalidHolding, match="price"):
            h("AAA", "1", price)

    @pytest.mark.parametrize(("quantity", "price"), [("0", "0"), ("0", "10"), ("10", "0")])
    def test_zero_is_allowed(self, quantity: str, price: str) -> None:
        assert h("AAA", quantity, price).market_value == Decimal("0")


class TestTotalValue:
    @pytest.mark.parametrize(
        ("holdings", "expected"),
        [
            ([], "0"),
            ([h("AAA", "0", "0")], "0"),
            ([h("AAA", "10", "12.50")], "125.00"),
            (SAMPLE, "1000"),
            ([h("AAA", "2", "50"), h("AAA", "1", "50")], "150"),
        ],
    )
    def test_total_value(self, holdings: list[Holding], expected: str) -> None:
        assert total_value(holdings) == Decimal(expected)


class TestAllocations:
    def test_empty_portfolio_has_no_allocations(self) -> None:
        assert allocations([]) == {}

    def test_worthless_portfolio_has_no_allocations(self) -> None:
        assert allocations([h("AAA", "10", "0"), h("BBB", "0", "5")]) == {}

    def test_weights_match_hand_computed_values(self) -> None:
        assert allocations(SAMPLE) == {
            "AAA": Decimal("0.5"),
            "BBB": Decimal("0.3"),
            "CCC": Decimal("0.2"),
        }

    def test_same_symbol_in_two_lots_is_aggregated(self) -> None:
        holdings = [h("AAA", "1", "100"), h("AAA", "3", "100"), h("BBB", "6", "100")]
        assert allocations(holdings) == {"AAA": Decimal("0.4"), "BBB": Decimal("0.6")}


class TestConcentration:
    @pytest.mark.parametrize(
        ("holdings", "expected_hhi", "expected_largest"),
        [
            ([], "0", "0"),
            ([h("AAA", "1", "100")], "1", "1"),
            (SAMPLE, "0.38", "0.5"),  # 0.5^2 + 0.3^2 + 0.2^2 = 0.38
        ],
    )
    def test_indices(
        self, holdings: list[Holding], expected_hhi: str, expected_largest: str
    ) -> None:
        assert herfindahl_index(holdings) == Decimal(expected_hhi)
        assert largest_position_weight(holdings) == Decimal(expected_largest)

    def test_even_split_scores_one_over_n(self) -> None:
        holdings = [h(sym, "1", "100") for sym in ("AAA", "BBB", "CCC", "DDD")]
        assert herfindahl_index(holdings) == Decimal("0.25")


class TestTopHoldings:
    @pytest.mark.parametrize("n", [0, -1, -50])
    def test_non_positive_n_returns_empty(self, n: int) -> None:
        assert top_holdings(SAMPLE, n) == []

    def test_orders_by_market_value_descending(self) -> None:
        result = top_holdings(SAMPLE, 2)
        assert [p.symbol for p in result] == ["AAA", "BBB"]
        assert result[0].market_value == Decimal("500")
        assert result[0].weight == Decimal("0.5")

    def test_asking_for_more_than_exist_returns_all(self) -> None:
        assert len(top_holdings(SAMPLE, 99)) == 3

    def test_ties_break_by_symbol_name(self) -> None:
        holdings = [h("ZZZ", "1", "100"), h("AAA", "1", "100")]
        assert [p.symbol for p in top_holdings(holdings, 2)] == ["AAA", "ZZZ"]

    def test_worthless_portfolio_reports_zero_weight(self) -> None:
        result = top_holdings([h("AAA", "10", "0")], 1)
        assert result == [
            PositionWeight(symbol="AAA", market_value=Decimal("0"), weight=Decimal("0"))
        ]
