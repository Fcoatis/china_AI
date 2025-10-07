from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Sequence

import pandas as pd
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from portfolio import (
    DEFAULT_COMPANIES,
    InitialPriceRepository,
    MessageLevel,
    PortfolioAllocator,
    PriceHistoryService,
    CurrencyRatesService,
    ServiceMessage,
)


# ------------------ Config da página ------------------ #
st.set_page_config(page_title="Simulador de Portfólio: IA na China", layout="centered")
st.title("💹 Simulador de Portfólio: IA na China")


# ------------------ Utilidades ------------------ #
def formatar_periodo(dt_inicial: date, dt_final: date) -> str:
    """Formata a diferença entre dois dias em anos/meses/dias."""
    rd = relativedelta(dt_final, dt_inicial)
    partes: list[str] = []
    if rd.years:
        partes.append(f"{rd.years} ano" + ("s" if rd.years > 1 else ""))
    if rd.months:
        partes.append("1 mês" if rd.months == 1 else f"{rd.months} meses")
    if rd.days:
        partes.append(f"{rd.days} dia" + ("s" if rd.days > 1 else ""))

    if not partes:
        return "0 dia"
    if len(partes) == 1:
        return partes[0]
    if len(partes) == 2:
        return " e ".join(partes)
    return f"{partes[0]}, {partes[1]} e {partes[2]}"


def _hex_to_rgb(hexstr: str):
    h = hexstr.lstrip("#")
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return None


def _luma(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _theme_is_dark(force: bool | None = None) -> bool:
    if force is not None:
        return force

    base = st.get_option("theme.base")
    if isinstance(base, str):
        return base.lower() == "dark"

    bg = st.get_option("theme.backgroundColor")
    if isinstance(bg, str):
        rgb = _hex_to_rgb(bg)
        if rgb:
            return _luma(rgb) < 128

    txt = st.get_option("theme.textColor")
    if isinstance(txt, str):
        rgb = _hex_to_rgb(txt)
        if rgb:
            return _luma(rgb) > 200

    return False


def _display_messages(messages: Sequence[ServiceMessage], *, stop_on_error: bool = False) -> None:
    has_error = False
    for message in messages:
        if message.level == MessageLevel.ERROR:
            st.error(message.text)
            has_error = True
        elif message.level == MessageLevel.WARNING:
            st.warning(message.text)
        else:
            st.info(message.text)
    if stop_on_error and has_error:
        st.stop()


def _build_purchase_log(events: Iterable) -> pd.DataFrame:
    registros = []
    for event in events:
        delta = event.quantity_delta
        sufixo = "unidade" if abs(delta) == 1 else "unidades"
        prefixo = "+" if delta > 0 else ""
        registros.append(
            {
                "Empresa": event.company.name,
                "Ticker": event.company.ticker,
                "Preço Inicial (USD)": event.unit_price_usd,
                "Gap antes (USD)": event.gap_before_usd,
                "Gap depois (USD)": event.gap_after_usd,
                "Caixa antes (USD)": event.cash_before_usd,
                "Caixa depois (USD)": event.cash_after_usd,
                "Compra": f"{prefixo}{delta} {sufixo}",
            }
        )
    return pd.DataFrame(registros)


def main() -> None:
    # ------------------ Sidebar (override manual) ------------------ #
    force_dark_toggle = st.sidebar.toggle(
        "Forçar labels brancos no gráfico",
        value=False,
        help="Use se as labels da pizza não ficarem legíveis no modo escuro.",
    )

    # ------------------ Inputs ------------------ #
    valor_total = st.number_input(
        "Valor total disponível (USD)",
        min_value=1000,
        value=10000,
        step=500,
    )

    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")

    data_compra = st.date_input(
        "📅 Data da Compra (retroativa)",
        value=date(2025, 7, 15),
        max_value=hoje - timedelta(days=1),
    )
    data_str = data_compra.strftime("%Y-%m-%d")
    periodo_str = formatar_periodo(data_compra, hoje)

    col_dc, col_per = st.columns(2)
    with col_dc:
        st.markdown(f"**Data de Compra:** {data_str}")
    with col_per:
        st.markdown(f"**Período:** {periodo_str}")

    arquivo_precos = f"precos_iniciais_{data_str}.csv"

    indice_util = pd.date_range(start=data_compra, end=hoje, freq="B")
    if indice_util.empty:
        st.error("Não há dias úteis no período selecionado. Ajuste a data.")
        st.stop()

    companies = DEFAULT_COMPANIES

    # --- Preços iniciais ---
    repo = InitialPriceRepository()
    precos_local, repo_messages = repo.load_prices(companies, arquivo_precos)
    _display_messages(repo_messages, stop_on_error=True)

    # --- Séries de câmbio ---
    currencies_needed = {company.currency for company in companies}
    fx_service = CurrencyRatesService()
    fx_result = fx_service.load_series(
        currencies=currencies_needed,
        start=data_str,
        end=hoje_str,
        index=indice_util,
    )
    _display_messages(fx_result.messages)

    # --- Alocação inicial ---
    allocator = PortfolioAllocator()
    allocation_result = allocator.allocate(
        companies=companies,
        total_cash_usd=valor_total,
        business_days_index=indice_util,
        purchase_date=data_compra,
        initial_prices_local=precos_local,
        fx_series_by_currency=fx_result.series_by_currency,
    )
    _display_messages(allocation_result.messages)

    df_alloc = allocation_result.allocation_df.copy()
    if df_alloc.empty:
        st.error("Não foi possível gerar a alocação inicial do portfólio.")
        st.stop()

    df_compra_inicial = allocation_result.initial_purchase_df.copy()
    df_log = _build_purchase_log(allocation_result.purchase_events)
    caixa_inicial = allocation_result.initial_cash_usd
    caixa_final = allocation_result.final_cash_usd

    # --- Histórico de preços em USD ---
    history_service = PriceHistoryService()
    prices_usd_df, history_messages = history_service.load_usd_history(
        companies=companies,
        start=data_str,
        end=hoje_str,
        fx_series_by_currency=fx_result.series_by_currency,
    )
    _display_messages(history_messages)

    tickers = [company.ticker for company in companies]
    prices_usd_df = prices_usd_df.reindex(index=indice_util)
    prices_usd_df = prices_usd_df.reindex(columns=tickers)
    prices_usd_df = prices_usd_df.ffill()

    for ticker, preco_ini in allocation_result.initial_price_usd.items():
        if ticker in prices_usd_df.columns:
            prices_usd_df[ticker] = prices_usd_df[ticker].fillna(preco_ini)

    if not prices_usd_df.empty:
        latest_prices = prices_usd_df.iloc[-1]
    else:
        latest_prices = pd.Series(dtype=float)

    precos_atuais_series = df_alloc["Ticker"].map(latest_prices)
    precos_atuais_series = precos_atuais_series.fillna(df_alloc["Preço Inicial (USD)"])
    df_alloc["Preço Atual (USD)"] = precos_atuais_series.round(2)

    df_alloc["Investimento Atual (USD)"] = (
        df_alloc["Quantidade"] * precos_atuais_series
    ).round(2)
    df_alloc["Ganho/Perda (USD)"] = (
        df_alloc["Investimento Atual (USD)"] - df_alloc["Investimento Inicial (USD)"]
    ).round(2)
    variacao_base = df_alloc["Investimento Inicial (USD)"].replace(0, pd.NA)
    df_alloc["Variação (%)"] = (
        (df_alloc["Ganho/Perda (USD)"] / variacao_base) * 100
    ).fillna(0.0).round(2)

    total_investido = df_alloc["Investimento Inicial (USD)"].sum()
    total_atual = df_alloc["Investimento Atual (USD)"].sum()
    ganho_total = total_atual - total_investido
    variacao_total = (ganho_total / total_investido) * 100 if total_investido else 0.0

    st.subheader("📈 Resumo do Portfólio")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Investido (USD)", f"${total_investido:,.2f}")
    col2.metric("Valor Atual (USD)", f"${total_atual:,.2f}")
    col3.metric("Ganho/Perda Total", f"${ganho_total:,.2f}", f"{variacao_total:.2f}%")

    st.divider()
    mostrar_detalhes = st.toggle("🔎 Mostrar detalhes da alocação")

    if mostrar_detalhes:
        aba1, aba2, aba3 = st.tabs([
            "🛒 Compra Inicial",
            "📜 Log de distribuição",
            "📊 Gráficos",
        ])

        with aba1:
            st.markdown("**Compra Inicial (antes do loop de distribuição do caixa):**")
            fmt1 = {
                "Preço Local (na compra)": "{:,.4f}",
                "FX local→USD (compra)": "{:,.6f}",
                "Preço Inicial (USD)": "{:,.4f}",
                "Alvo USD": "{:,.2f}",
                "Qtd exata": "{:,.6f}",
                "Qtd inteira (inicial)": "{:,.0f}",
                "Resíduo (inicial)": "{:,.6f}",
            }
            st.dataframe(df_compra_inicial.set_index("Empresa").style.format(fmt1))
            st.caption(f"💵 Caixa inicial após arredondamento: **${caixa_inicial:,.2f}**")

        with aba2:
            st.markdown("**Log da distribuição do caixa (passo-a-passo):**")
            if df_log.empty:
                st.info(
                    "Nenhuma compra extra foi necessária; caixa insuficiente ou gaps já atendidos."
                )
            else:
                fmt2 = {
                    "Preço Inicial (USD)": "{:,.4f}",
                    "Gap antes (USD)": "{:,.2f}",
                    "Gap depois (USD)": "{:,.2f}",
                    "Caixa antes (USD)": "{:,.2f}",
                    "Caixa depois (USD)": "{:,.2f}",
                }
                st.dataframe(df_log.style.format(fmt2))
                st.download_button(
                    "Baixar log (.csv)",
                    data=df_log.to_csv(index=False).encode("utf-8"),
                    file_name="log_distribuicao_caixa.csv",
                    mime="text/csv",
                )

        with aba3:
            base = df_alloc.copy()
            base["Invest Inicial USD"] = base["Investimento Inicial (USD)"]
            fig_alvo = px.bar(
                base,
                x="Empresa",
                y=["Alvo USD", "Invest Inicial USD"],
                barmode="group",
                title="Alvo USD vs Investimento Inicial USD",
            )
            fig_alvo.update_layout(xaxis_title="", yaxis_title="USD")
            st.plotly_chart(fig_alvo, use_container_width=True)

            if not df_log.empty:
                labels = ["Caixa inicial"] + [
                    f"{row['Ticker']} (+{row['Compra'].split()[0].lstrip('+')})"
                    for _, row in df_log.iterrows()
                ] + ["Caixa final"]
                measures = [
                    "absolute",
                    *["relative"] * len(df_log),
                    "total",
                ]
                compras = df_log["Preço Inicial (USD)"].astype(float).tolist()
                values = [float(caixa_inicial)] + [-valor for valor in compras] + [
                    float(caixa_final)
                ]

                fig_wf = go.Figure(
                    go.Waterfall(
                        measure=measures,
                        x=labels,
                        y=values,
                        connector={"line": {"color": "rgba(128,128,128,0.4)"}},
                    )
                )
                fig_wf.update_layout(
                    title="Waterfall do Caixa (distribuição por compras)",
                    yaxis_title="USD",
                )
                st.plotly_chart(fig_wf, use_container_width=True)

    df_display = df_alloc.set_index("Empresa")[
        [
            "Ticker",
            "Peso (%)",
            "Quantidade",
            "Preço Inicial (USD)",
            "Preço Atual (USD)",
            "Investimento Inicial (USD)",
            "Investimento Atual (USD)",
            "Ganho/Perda (USD)",
            "Variação (%)",
        ]
    ]
    format_dict = {
        "Preço Inicial (USD)": "{:,.2f}",
        "Preço Atual (USD)": "{:,.2f}",
        "Investimento Inicial (USD)": "{:,.2f}",
        "Investimento Atual (USD)": "{:,.2f}",
        "Ganho/Perda (USD)": "{:,.2f}",
        "Peso (%)": "{:.2f}",
        "Variação (%)": "{:.2f}%",
    }
    st.subheader("📋 Alocação Inteligente de Portfólio")
    st.dataframe(
        df_display.style.format(format_dict).set_properties(**{"text-align": "right"})
    )

    # ------------------ Gráfico 1: Pizza ------------------ #
    is_dark = _theme_is_dark(force=True if force_dark_toggle else None)
    txt_col = "white" if is_dark else "black"
    edge_col = "white" if is_dark else "black"

    df_plot = df_alloc.sort_values("Investimento Inicial (USD)", ascending=False)

    plt.rcParams["savefig.transparent"] = True
    fig1, ax1 = plt.subplots(facecolor="none")
    ax1.set_facecolor("none")

    wedges, texts, autotexts = ax1.pie(
        df_plot["Investimento Inicial (USD)"],
        labels=df_plot["Empresa"],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": edge_col, "linewidth": 1.0},
    )

    for t in texts:
        t.set_color(txt_col)
        t.set_fontsize(11)
    for t in autotexts:
        t.set_color(txt_col)
        t.set_fontsize(11)

    ax1.axis("equal")

    st.subheader("🍰 Distribuição do Investimento Inicial")
    st.pyplot(fig1, transparent=True)

    # ------------------ Gráfico 2: Linha (Plotly) ------------------ #
    historico_portfolio = prices_usd_df.copy()

    quantidades = df_alloc.set_index("Ticker")["Quantidade"]
    port_val = (historico_portfolio * quantidades).sum(axis=1)
    if total_investido:
        port_ret = (port_val / total_investido - 1) * 100
    else:
        port_ret = pd.Series(0.0, index=port_val.index)

    df_ret = port_ret.rename("Retorno (%)").reset_index().rename(columns={"index": "Data"})
    df_ret["Período"] = df_ret["Data"].dt.date.map(
        lambda d: formatar_periodo(data_compra, d)
    )

    fig2 = px.line(
        df_ret,
        x="Data",
        y="Retorno (%)",
        title="Evolução do Retorno do Portfólio (%)",
        markers=True,
    )
    fig2.update_traces(
        customdata=df_ret["Período"],
        hovertemplate="<b>%{x|%d/%m/%Y}</b>"
        "<br>Retorno: %{y:.2f}%%"
        "<br>Período: %{customdata}"
        "<extra></extra>",
    )
    fig2.update_layout(
        xaxis_title="Data",
        yaxis_title="Retorno (%)",
        xaxis=dict(tickformat="%d/%m"),
        hovermode="x unified",
    )

    st.subheader("📈 Evolução do Retorno do Portfólio")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": True})


if __name__ == "__main__":
    main()
