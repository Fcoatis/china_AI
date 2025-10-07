"""Market data history services."""
from __future__ import annotations

from typing import Dict, Iterable, List

import pandas as pd
import yfinance as yf

from ..messages import MessageLevel, ServiceMessage
from ..models import Company


class PriceHistoryService:
    """Loads price history in USD for a collection of companies."""

    def load_usd_history(
        self,
        companies: Iterable[Company],
        start: str,
        end: str,
        fx_series_by_currency: Dict[str, pd.Series],
    ) -> tuple[pd.DataFrame, List[ServiceMessage]]:
        tickers = {company.ticker: company for company in companies}
        price_series: Dict[str, pd.Series] = {}
        messages: List[ServiceMessage] = []

        for ticker, company in tickers.items():
            currency = company.currency
            fx_series = fx_series_by_currency.get(currency)
            if fx_series is None:
                messages.append(
                    ServiceMessage(
                        MessageLevel.WARNING,
                        f"Sem série de câmbio encontrada para {currency}; assumindo 1.0 para {ticker}.",
                    )
                )
                fx_series = pd.Series(1.0, dtype=float)

            series = self._load_single_history(
                ticker=ticker,
                currency=currency,
                start=start,
                end=end,
                fx_series=fx_series,
                messages=messages,
            )
            price_series[ticker] = series

        prices_df = pd.DataFrame(price_series)
        return prices_df, messages

    def _load_single_history(
        self,
        ticker: str,
        currency: str,
        start: str,
        end: str,
        fx_series: pd.Series,
        messages: List[ServiceMessage],
    ) -> pd.Series:
        try:
            hist = yf.Ticker(ticker).history(start=start, end=end)
            if hist.empty or "Close" not in hist:
                raise ValueError("sem dados de fechamento")
            serie = hist["Close"].copy()
            serie.index = serie.index.tz_localize(None)
            serie = serie.astype(float)
            fx_alinhado = fx_series.reindex(serie.index, method="ffill").bfill()
            serie_usd = serie * fx_alinhado
            return serie_usd.rename(ticker)
        except Exception as exc:  # noqa: BLE001 - mensagem catalogada
            messages.append(
                ServiceMessage(
                    MessageLevel.WARNING,
                    f"Falha ao obter histórico para {ticker}: {exc}",
                )
            )
            return pd.Series(dtype=float, name=ticker)
