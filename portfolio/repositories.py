"""Repositories responsible for loading persisted data."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from .messages import MessageLevel, ServiceMessage
from .models import Company


class InitialPriceRepository:
    """Loads initial prices for the companies using CSV snapshots."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base_path = base_path or Path.cwd()

    def load_prices(
        self,
        companies: Iterable[Company],
        snapshot_filename: str,
    ) -> tuple[Mapping[str, float], list[ServiceMessage]]:
        csv_path = self._base_path / snapshot_filename
        messages: list[ServiceMessage] = []

        if not csv_path.exists():
            messages.append(
                ServiceMessage(
                    MessageLevel.ERROR,
                    f"Arquivo não encontrado: {snapshot_filename}",
                )
            )
            return {}, messages

        df = pd.read_csv(csv_path, index_col=0)
        prices: dict[str, float] = {}
        for company in companies:
            if company.ticker not in df.index:
                messages.append(
                    ServiceMessage(
                        MessageLevel.WARNING,
                        f"Ticker {company.ticker} ausente no CSV {snapshot_filename}; ignorando.",
                    )
                )
                continue
            preco = float(df.loc[company.ticker, "PrecoInicial"])
            prices[company.ticker] = preco

        return prices, messages
