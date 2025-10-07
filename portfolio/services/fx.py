"""Currency rate retrieval services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

import pandas as pd
import yfinance as yf

from ..config import CURRENCY_TO_PAIR
from ..messages import MessageLevel, ServiceMessage
from ..models import CurrencyPairConfig


@dataclass(frozen=True)
class CurrencyRatesResult:
    series_by_currency: Dict[str, pd.Series]
    messages: List[ServiceMessage]


class CurrencyRatesService:
    """Fetches currency rates and converts them into USD series."""

    def __init__(self, pair_config: Dict[str, CurrencyPairConfig] | None = None) -> None:
        self._pair_config = pair_config or CURRENCY_TO_PAIR

    def load_series(
        self,
        currencies: Iterable[str],
        start: str,
        end: str,
        index: pd.Index,
    ) -> CurrencyRatesResult:
        fx_map: Dict[str, pd.Series] = {}
        messages: List[ServiceMessage] = []

        for currency in currencies:
            if currency == "USD":
                fx_map[currency] = pd.Series(1.0, index=index, name=currency)
                continue

            config = self._pair_config.get(currency)
            if not config or not config.symbol:
                messages.append(
                    ServiceMessage(
                        MessageLevel.WARNING,
                        f"Sem par cambial configurado para {currency}; assumindo paridade 1.0.",
                    )
                )
                fx_map[currency] = pd.Series(1.0, index=index, name=currency)
                continue

            fx_map[currency] = self._fetch_currency_series(
                currency=config.currency,
                symbol=config.symbol,
                invert=config.invert,
                start=start,
                end=end,
                index=index,
                messages=messages,
            )

        return CurrencyRatesResult(series_by_currency=fx_map, messages=messages)

    def _fetch_currency_series(
        self,
        currency: str,
        symbol: str,
        invert: bool,
        start: str,
        end: str,
        index: pd.Index,
        messages: List[ServiceMessage],
    ) -> pd.Series:
        try:
            hist = yf.Ticker(symbol).history(start=start, end=end)
            if hist.empty or "Close" not in hist:
                raise ValueError("série vazia")

            serie = hist["Close"].copy()
            serie.index = serie.index.tz_localize(None)
            serie = serie.astype(float).replace(0.0, float("nan"))
            if invert:
                serie = 1 / serie
            serie = serie.sort_index()
            serie = serie.reindex(index).ffill()
            if serie.isna().all():
                raise ValueError("série sem dados úteis")
            serie = serie.bfill()
            return serie.rename(currency)
        except Exception as exc:  # noqa: BLE001 - registramos a mensagem
            messages.append(
                ServiceMessage(
                    MessageLevel.WARNING,
                    f"Falha ao obter câmbio {currency}/USD ({symbol}): {exc}. Assumindo 1.0.",
                )
            )
            return pd.Series(1.0, index=index, name=currency)
