"""Domain models for the portfolio simulator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Company:
    """Represents a company that can appear in the portfolio."""

    name: str
    ticker: str
    target_weight: float
    currency: str = "USD"


@dataclass(frozen=True)
class CurrencyPairConfig:
    """Configuration for converting a local currency into USD."""

    currency: str
    symbol: Optional[str]
    invert: bool = False


@dataclass
class PurchaseEvent:
    """Records a purchase performed during the rebalancing loop."""

    company: Company
    unit_price_usd: float
    cash_before_usd: float
    cash_after_usd: float
    gap_before_usd: float
    gap_after_usd: float
    quantity_delta: int = 1


@dataclass
class AllocationSnapshot:
    """Represents the state of a company allocation at a specific moment."""

    company: Company
    quantity: int
    initial_price_usd: float
    current_price_usd: float
    initial_investment_usd: float
    current_investment_usd: float
    currency: str


@dataclass
class PortfolioSummary:
    """Aggregated totals for the entire portfolio."""

    invested_usd: float
    current_value_usd: float

    @property
    def gain_usd(self) -> float:
        return self.current_value_usd - self.invested_usd

    @property
    def variation_pct(self) -> float:
        if not self.invested_usd:
            return 0.0
        return (self.gain_usd / self.invested_usd) * 100
