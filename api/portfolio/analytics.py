"""Pure portfolio analytics.

No Django, no I/O, no database. Every function here is a deterministic function
of its arguments, which makes the domain rules cheap to unit-test exhaustively
and to check with property-based tests (see ``tests/``).

The API / ORM layer is responsible for loading data and passing plain
``Holding`` values in; it must not push query sets or serializers down here.
That keeps the business logic in one place, framework-free, and portable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

__all__ = [
    "Holding",
    "InvalidHolding",
    "PositionWeight",
    "allocations",
    "herfindahl_index",
    "largest_position_weight",
    "top_holdings",
    "total_value",
]

_ZERO = Decimal("0")


class InvalidHolding(ValueError):
    """A holding violates a domain invariant (negative quantity or price)."""


@dataclass(frozen=True)
class Holding:
    """A single line item in a portfolio: ``quantity`` units of ``symbol`` at
    ``price`` per unit, expressed in the portfolio's base currency."""

    symbol: str
    quantity: Decimal
    price: Decimal

    def __post_init__(self) -> None:
        if self.quantity < _ZERO:
            raise InvalidHolding(f"{self.symbol}: quantity must be >= 0, got {self.quantity}")
        if self.price < _ZERO:
            raise InvalidHolding(f"{self.symbol}: price must be >= 0, got {self.price}")

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.price


@dataclass(frozen=True)
class PositionWeight:
    """A symbol's aggregated market value and its share of the portfolio (0..1)."""

    symbol: str
    market_value: Decimal
    weight: Decimal


def _values_by_symbol(holdings: list[Holding]) -> dict[str, Decimal]:
    """Aggregate market value per symbol, so two lots of the same symbol combine."""
    totals: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for holding in holdings:
        totals[holding.symbol] += holding.market_value
    return dict(totals)


def total_value(holdings: list[Holding]) -> Decimal:
    """Sum of every holding's market value. ``0`` for an empty portfolio."""
    return sum((h.market_value for h in holdings), start=_ZERO)


def allocations(holdings: list[Holding]) -> dict[str, Decimal]:
    """Fraction of the portfolio held in each symbol, as a mapping ``symbol -> weight``
    with every weight in ``(0, 1]``.

    Only symbols that carry value appear: a held-but-worthless lot (zero price or
    zero quantity) is not a 0% slice of the portfolio, it is simply absent.
    Returns ``{}`` when the portfolio has no value at all.
    """
    total = total_value(holdings)
    if total == _ZERO:
        return {}
    return {
        symbol: value / total
        for symbol, value in _values_by_symbol(holdings).items()
        if value > _ZERO
    }


def herfindahl_index(holdings: list[Holding]) -> Decimal:
    """Herfindahl-Hirschman concentration index: the sum of squared symbol weights.

    ``1`` means everything sits in one symbol; a portfolio split evenly across
    ``n`` symbols scores ``1/n``. ``0`` for a portfolio with no value.
    """
    return sum((w * w for w in allocations(holdings).values()), start=_ZERO)


def largest_position_weight(holdings: list[Holding]) -> Decimal:
    """Weight of the single biggest symbol (0..1). ``0`` for a portfolio with no value.

    Useful for a "no position may exceed X%" style risk rule.
    """
    weights = allocations(holdings).values()
    return max(weights, default=_ZERO)


def top_holdings(holdings: list[Holding], n: int) -> list[PositionWeight]:
    """The ``n`` largest symbols by market value, biggest first.

    Ties break by symbol name so the order is deterministic. ``n <= 0`` returns
    an empty list; asking for more than exist returns all of them.
    """
    if n <= 0:
        return []
    weights = allocations(holdings)
    ranked = sorted(
        _values_by_symbol(holdings).items(),
        key=lambda item: (-item[1], item[0]),
    )
    return [
        PositionWeight(symbol=symbol, market_value=value, weight=weights.get(symbol, _ZERO))
        for symbol, value in ranked[:n]
    ]
