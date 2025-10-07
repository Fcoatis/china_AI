"""Allocation services for building the initial portfolio."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Mapping

import pandas as pd

from ..messages import MessageLevel, ServiceMessage
from ..models import Company, PurchaseEvent


@dataclass(frozen=True)
class AllocationResult:
    allocation_df: pd.DataFrame
    initial_purchase_df: pd.DataFrame
    purchase_events: List[PurchaseEvent]
    initial_cash_usd: float
    final_cash_usd: float
    initial_price_usd: Dict[str, float]
    messages: List[ServiceMessage]


class PortfolioAllocator:
    """Distributes the available cash following target weights and rounding rules."""

    EPS = 1e-6

    def allocate(
        self,
        *,
        companies: Iterable[Company],
        total_cash_usd: float,
        business_days_index: pd.DatetimeIndex,
        purchase_date: date,
        initial_prices_local: Mapping[str, float],
        fx_series_by_currency: Mapping[str, pd.Series],
    ) -> AllocationResult:
        rows = []
        messages: List[ServiceMessage] = []
        precos_iniciais_usd: Dict[str, float] = {}

        purchase_ts = pd.Timestamp(purchase_date)

        for company in companies:
            ticker = company.ticker
            peso = company.target_weight
            preco_ini_local = initial_prices_local.get(ticker)
            if preco_ini_local is None:
                messages.append(
                    ServiceMessage(
                        MessageLevel.ERROR,
                        f"Ticker {ticker} não possui preço inicial no CSV; ignorando.",
                    )
                )
                continue

            fx_series = fx_series_by_currency.get(company.currency)
            if fx_series is None or fx_series.empty:
                messages.append(
                    ServiceMessage(
                        MessageLevel.WARNING,
                        f"Sem série de câmbio para {company.currency}; usando 1.0 para {ticker}.",
                    )
                )
                fx_rate = 1.0
            else:
                fx_rate = self._extract_fx_rate(
                    fx_series=fx_series,
                    purchase_ts=purchase_ts,
                    messages=messages,
                    currency=company.currency,
                )

            preco_ini_usd = float(preco_ini_local) * float(fx_rate)
            if pd.isna(preco_ini_usd) or preco_ini_usd <= 0:
                messages.append(
                    ServiceMessage(
                        MessageLevel.ERROR,
                        f"Preço inicial inválido para {ticker}.",
                    )
                )
                continue

            valor_desejado = total_cash_usd * peso / 100
            qtd_exata = valor_desejado / preco_ini_usd
            qtd_inteira = int(qtd_exata)
            residuo = qtd_exata - qtd_inteira

            precos_iniciais_usd[ticker] = preco_ini_usd
            rows.append(
                {
                    "Empresa": company.name,
                    "Ticker": ticker,
                    "Moeda": company.currency,
                    "Peso (%)": peso,
                    "Preço Local (na compra)": float(preco_ini_local),
                    "FX local→USD (compra)": float(fx_rate),
                    "Preço Inicial (USD)": preco_ini_usd,
                    "Alvo USD": valor_desejado,
                    "Qtd exata": qtd_exata,
                    "Qtd inteira (inicial)": qtd_inteira,
                    "Quantidade": qtd_inteira,
                    "Resíduo (inicial)": round(residuo, 6),
                    "Resíduo": round(residuo, 6),
                }
            )

        df_alloc = pd.DataFrame(rows)
        if df_alloc.empty:
            return AllocationResult(
                allocation_df=df_alloc,
                initial_purchase_df=df_alloc.copy(),
                purchase_events=[],
                initial_cash_usd=total_cash_usd,
                final_cash_usd=total_cash_usd,
                initial_price_usd=precos_iniciais_usd,
                messages=messages,
            )

        df_alloc["Quantidade"] = df_alloc["Quantidade"].astype(int)
        df_alloc["Qtd inteira (inicial)"] = df_alloc["Qtd inteira (inicial)"].astype(int)

        coluna_investimento = df_alloc["Preço Inicial (USD)"]
        caixa = total_cash_usd - (df_alloc["Quantidade"] * coluna_investimento).sum()
        caixa_inicial = caixa
        min_price = coluna_investimento.min()
        eventos: List[PurchaseEvent] = []

        while caixa + self.EPS >= min_price:
            alvo_usd = df_alloc["Alvo USD"]
            invest_atual = df_alloc["Quantidade"] * coluna_investimento
            gap_usd = alvo_usd - invest_atual

            affordable = coluna_investimento <= (caixa + self.EPS)
            if not affordable.any():
                break

            candidatos = df_alloc.loc[affordable, ["Preço Inicial (USD)"]].copy()
            candidatos["Gap USD"] = gap_usd.loc[affordable]
            candidatos = candidatos.sort_values(
                by=["Gap USD", "Preço Inicial (USD)"], ascending=[False, True]
            )

            idx = candidatos.index[0]
            if candidatos.loc[idx, "Gap USD"] <= 0:
                break

            preco_compra = coluna_investimento.loc[idx]
            caixa_antes = caixa
            gap_antes = gap_usd.loc[idx]

            df_alloc.loc[idx, "Quantidade"] += 1
            caixa -= preco_compra

            invest_atual = df_alloc["Quantidade"] * coluna_investimento
            gap_depois = alvo_usd.loc[idx] - invest_atual.loc[idx]

            eventos.append(
                PurchaseEvent(
                    company=Company(
                        name=df_alloc.loc[idx, "Empresa"],
                        ticker=df_alloc.loc[idx, "Ticker"],
                        target_weight=float(df_alloc.loc[idx, "Peso (%)"]),
                        currency=df_alloc.loc[idx, "Moeda"],
                    ),
                    unit_price_usd=float(preco_compra),
                    cash_before_usd=float(caixa_antes),
                    cash_after_usd=float(caixa),
                    gap_before_usd=float(gap_antes),
                    gap_after_usd=float(gap_depois),
                )
            )

        df_alloc["Investimento Inicial (USD)"] = (
            df_alloc["Quantidade"] * coluna_investimento
        ).round(2)
        df_alloc["Resíduo"] = (
            df_alloc["Alvo USD"] / coluna_investimento - df_alloc["Quantidade"]
        ).round(6)

        initial_columns = [
            "Empresa",
            "Ticker",
            "Moeda",
            "Preço Local (na compra)",
            "FX local→USD (compra)",
            "Preço Inicial (USD)",
            "Peso (%)",
            "Alvo USD",
            "Qtd exata",
            "Qtd inteira (inicial)",
            "Resíduo (inicial)",
        ]
        df_compra_inicial = df_alloc[initial_columns].copy()

        return AllocationResult(
            allocation_df=df_alloc,
            initial_purchase_df=df_compra_inicial,
            purchase_events=eventos,
            initial_cash_usd=float(caixa_inicial),
            final_cash_usd=float(caixa),
            initial_price_usd=precos_iniciais_usd,
            messages=messages,
        )

    def _extract_fx_rate(
        self,
        *,
        fx_series: pd.Series,
        purchase_ts: pd.Timestamp,
        messages: List[ServiceMessage],
        currency: str,
    ) -> float:
        fx_no_dia = fx_series.asof(purchase_ts)
        if fx_no_dia is None or pd.isna(fx_no_dia):
            messages.append(
                ServiceMessage(
                    MessageLevel.WARNING,
                    "Sem câmbio disponível para "
                    f"{currency} na data selecionada; usando último valor disponível.",
                )
            )
            fx_no_dia = fx_series.dropna().iloc[-1] if not fx_series.dropna().empty else 1.0
        return float(fx_no_dia)
