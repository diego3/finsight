"""Property-based tests for the pure portfolio analytics.

Instead of pinning specific numbers, these assert invariants that must hold for
*every* portfolio Hypothesis can think up. This is the kind of net that catches
the input you did not imagine — the work a QA team would otherwise do by hand.
"""

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from portfolio.analytics import (
    Holding,
    allocations,
    herfindahl_index,
    largest_position_weight,
    top_holdings,
    total_value,
)

# Bounded, non-negative, 2-4 decimal places: realistic money, and cheap for Decimal.
symbols = st.text(alphabet="ABCDEFGHIJ", min_size=1, max_size=4)
quantities = st.decimals(min_value=0, max_value=10_000, places=4, allow_nan=False)
prices = st.decimals(min_value=0, max_value=1_000_000, places=2, allow_nan=False)

holdings_lists = st.lists(
    st.builds(Holding, symbol=symbols, quantity=quantities, price=prices),
    max_size=25,
)

# Portfolios that are guaranteed to have some value (at least one priced, held lot).
non_empty_value = st.lists(
    st.builds(
        Holding,
        symbol=symbols,
        quantity=st.decimals(min_value="0.0001", max_value=10_000, places=4, allow_nan=False),
        price=st.decimals(min_value="0.01", max_value=1_000_000, places=2, allow_nan=False),
    ),
    min_size=1,
    max_size=25,
)

TOLERANCE = Decimal("1e-12")


@given(holdings_lists)
def test_total_value_equals_sum_of_market_values(holdings: list[Holding]) -> None:
    assert total_value(holdings) == sum((h.market_value for h in holdings), start=Decimal(0))


@given(holdings_lists)
def test_total_value_is_never_negative(holdings: list[Holding]) -> None:
    assert total_value(holdings) >= 0


@given(holdings_lists)
def test_every_allocation_is_a_fraction(holdings: list[Holding]) -> None:
    for weight in allocations(holdings).values():
        assert Decimal(0) <= weight <= Decimal(1)


@given(non_empty_value)
def test_allocations_sum_to_one(holdings: list[Holding]) -> None:
    total_weight = sum(allocations(holdings).values(), start=Decimal(0))
    assert abs(total_weight - Decimal(1)) < TOLERANCE


@given(holdings_lists)
def test_allocations_have_one_entry_per_distinct_symbol(holdings: list[Holding]) -> None:
    weights = allocations(holdings)
    if total_value(holdings) == 0:
        assert weights == {}
    else:
        priced_symbols = {h.symbol for h in holdings if h.market_value > 0}
        assert set(weights) == priced_symbols


@given(holdings_lists)
def test_concentration_indices_are_fractions(holdings: list[Holding]) -> None:
    assert Decimal(0) <= herfindahl_index(holdings) <= Decimal(1) + TOLERANCE
    assert Decimal(0) <= largest_position_weight(holdings) <= Decimal(1)


@given(non_empty_value)
def test_hhi_is_at_least_largest_weight_squared(holdings: list[Holding]) -> None:
    largest = largest_position_weight(holdings)
    assert herfindahl_index(holdings) >= largest * largest - TOLERANCE


@given(
    st.lists(
        st.builds(Holding, symbol=st.just("AAA"), quantity=quantities, price=prices),
        min_size=1,
        max_size=10,
    )
)
def test_single_symbol_portfolio_is_fully_concentrated(holdings: list[Holding]) -> None:
    if total_value(holdings) > 0:
        assert largest_position_weight(holdings) == Decimal(1)
        assert abs(herfindahl_index(holdings) - Decimal(1)) < TOLERANCE


@given(holdings_lists, st.integers(min_value=1, max_value=30))
def test_top_holdings_is_a_sorted_prefix(holdings: list[Holding], n: int) -> None:
    result = top_holdings(holdings, n)
    assert len(result) <= n
    values = [p.market_value for p in result]
    assert values == sorted(values, reverse=True)


@given(non_empty_value, st.integers(min_value=1, max_value=30))
def test_top_holdings_weights_match_allocations(holdings: list[Holding], n: int) -> None:
    weights = allocations(holdings)
    for position in top_holdings(holdings, n):
        assert position.weight == weights[position.symbol]


@given(non_empty_value, symbols)
@settings(max_examples=200)
def test_adding_a_worthless_lot_changes_nothing(holdings: list[Holding], symbol: str) -> None:
    padded = [*holdings, Holding(symbol=symbol, quantity=Decimal(0), price=Decimal("123.45"))]
    assert total_value(padded) == total_value(holdings)
    assert allocations(padded) == allocations(holdings)
