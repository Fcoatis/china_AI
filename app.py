from pathlib import Path
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

import streamlit as st
import pandas as pd
import yfinance as yf

# Matplotlib (pizza)
import matplotlib.pyplot as plt

# Plotly (linha interativa)
import plotly.express as px
import plotly.graph_objects as go

# ------------------ Config da página ------------------ #
st.set_page_config(page_title="Simulador de Portfólio: IA na China", layout="centered")
st.title("💹 Simulador de Portfólio: IA na China")


# ------------------ Utilidades ------------------ #
def formatar_periodo(dt_inicial, dt_final):
    """
    Diferença entre dt_inicial e dt_final em anos/meses/dias,
    em PT-BR, omitindo zeros e com singular/plural corretos.
    """
    rd = relativedelta(dt_final, dt_inicial)
    partes = []
    if rd.years:
        partes.append(f"{rd.years} ano" + ("s" if rd.years > 1 else ""))
    if rd.months:
        partes.append("1 mês" if rd.months == 1 else f"{rd.months} meses")
    if rd.days:
        partes.append(f"{rd.days} dia" + ("s" if rd.days > 1 else ""))

    if not partes:
        return "0 dia"  # ou "hoje"
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
    return 0.2126 * r + 0.7152 * g + 0.0722 * b  # luminância perceptual


def _theme_is_dark(force: bool | None = None) -> bool:
    """
    Detecta modo escuro com múltiplos fallbacks:
    1) theme.base, se existir.
    2) theme.backgroundColor (luma baixa => escuro).
    3) theme.textColor (texto muito claro => fundo escuro).
    4) fallback: claro.
    Se 'force' vier (True/False), usa o valor forçado.
    """
    if force is not None:
        return force

    base = st.get_option("theme.base")
    if isinstance(base, str):
        return base.lower() == "dark"

    bg = st.get_option("theme.backgroundColor")
    if isinstance(bg, str):
        rgb = _hex_to_rgb(bg)
        if rgb:
            return _luma(rgb) < 128  # fundo escuro => luma baixa

    txt = st.get_option("theme.textColor")
    if isinstance(txt, str):
        rgb = _hex_to_rgb(txt)
        if rgb:
            return _luma(rgb) > 200  # texto muito claro => fundo escuro

    return False


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

# --- Seleção de Data de Compra ---
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

# --- Leitura do CSV de Preços Iniciais ---
arquivo_precos = f"precos_iniciais_{data_str}.csv"
if Path(arquivo_precos).exists():
    df_precos_iniciais = pd.read_csv(arquivo_precos, index_col=0)
else:
    st.error(f"Arquivo não encontrado: {arquivo_precos}")
    st.stop()

indice_util = pd.date_range(start=data_compra, end=hoje, freq="B")
if indice_util.empty:
    st.error("Não há dias úteis no período selecionado. Ajuste a data.")
    st.stop()

# --- Definição de Ativos e Pesos ---
empresas = [
    "Baidu",
    "Alibaba",
    "Tencent",
    "SenseTime",
    "iFlytek",
    "SMIC",
    "Cambricon",
    "Estun Automation",
    "Siasun Robot",
    "Hygon",
]
tickers = {
    empresa: tick
    for empresa, tick in zip(
        empresas,
        [
            "BIDU",
            "BABA",
            "0700.HK",
            "0020.HK",
            "002230.SZ",
            "0981.HK",
            "688256.SS",
            "002747.SZ",
            "300024.SZ",
            "688041.SS",
        ],
    )
}
# Mapeamento estático das moedas dos tickers
TICKER_CURRENCY = {
    "BIDU": "USD",
    "BABA": "USD",
    "0700.HK": "HKD",
    "0020.HK": "HKD",
    "002230.SZ": "CNY",
    "0981.HK": "HKD",
    "688256.SS": "CNY",
    "002747.SZ": "CNY",
    "300024.SZ": "CNY",
    "688041.SS": "CNY",
}

# Paridade cambial -> símbolo do Yahoo Finance e se precisamos inverter (1/valor)
CURRENCY_TO_PAIR = {
    "USD": {"symbol": None, "invert": False},
    "HKD": {"symbol": "USDHKD=X", "invert": True},
    "CNY": {"symbol": "USDCNY=X", "invert": True},
}


def obter_moeda_ticker(ticker: str) -> str:
    """Retorna a moeda do ticker, assumindo USD se não configurado."""
    currency = TICKER_CURRENCY.get(ticker)
    if currency:
        return currency
    st.warning(f"Moeda do ticker {ticker} não definida; assumindo USD.")
    return "USD"


def carregar_series_fx(currencies, start: str, end: str, index) -> dict:
    """Baixa séries cambiais para converter moedas locais em USD."""
    fx_map = {}
    for currency in currencies:
        if currency == "USD":
            fx_map[currency] = pd.Series(1.0, index=index, name=currency)
            continue

        info = CURRENCY_TO_PAIR.get(currency)
        if not info or not info.get("symbol"):
            st.warning(
                f"Sem par cambial configurado para {currency}; assumindo paridade 1.0."
            )
            fx_map[currency] = pd.Series(1.0, index=index, name=currency)
            continue

        symbol = info["symbol"]
        invert = info.get("invert", False)
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
            fx_map[currency] = serie.rename(currency)
        except Exception as exc:
            st.warning(
                f"Falha ao obter câmbio {currency}/USD ({symbol}): {exc}. Assumindo 1.0."
            )
            fx_map[currency] = pd.Series(1.0, index=index, name=currency)

    return fx_map
pesos = dict(zip(empresas, [15, 15, 10, 8, 7, 12, 8, 10, 7, 8]))

currencies_needed = {obter_moeda_ticker(tick) for tick in tickers.values()}
fx_series = carregar_series_fx(currencies_needed, data_str, hoje_str, indice_util)
precos_iniciais_usd = {}

# --- Alocação otimizada via resíduos ---
# --- Alocação inicial e captura de dados auxiliares ---
dados_alloc = []
for empresa in empresas:
    ticker = tickers[empresa]
    peso = pesos[empresa]
    preco_ini_local = float(df_precos_iniciais.loc[ticker, "PrecoInicial"])
    currency = obter_moeda_ticker(ticker)
    fx_serie = fx_series.get(currency)
    fx_no_dia = None
    if fx_serie is not None:
        fx_no_dia = fx_serie.asof(pd.Timestamp(data_compra))
    fx_utilizado = fx_no_dia
    if fx_utilizado is None or pd.isna(fx_utilizado):
        st.warning(
            "Sem câmbio disponível para "
            f"{currency} em {data_str}; usando último valor disponível."
        )
        if fx_serie is not None and not fx_serie.empty:
            fx_utilizado = fx_serie.iloc[-1]
        else:
            fx_utilizado = 1.0

    fx_utilizado = float(fx_utilizado if fx_utilizado is not None else 1.0)

    preco_ini = preco_ini_local * fx_utilizado
    if pd.isna(preco_ini) or preco_ini <= 0:
        st.error(f"Preço inicial inválido para {ticker}.")
        st.stop()

    precos_iniciais_usd[ticker] = preco_ini
    valor_desejado = valor_total * peso / 100
    qtd_exata = valor_desejado / preco_ini
    parte_int = int(qtd_exata)
    residuo = qtd_exata - parte_int
    dados_alloc.append(
        {
            "Empresa": empresa,
            "Ticker": ticker,
            "Moeda": currency,
            "Peso (%)": peso,
            "Quantidade": parte_int,
            "Qtd inteira (inicial)": parte_int,
            "Preço Local (na compra)": preco_ini_local,
            "FX local→USD (compra)": fx_utilizado,
            "Preço Inicial (USD)": preco_ini,
            "Resíduo": residuo,
        }
    )

df_alloc = pd.DataFrame(dados_alloc)

valor_desejado_series = valor_total * df_alloc["Peso (%)"] / 100.0
df_alloc["Alvo USD"] = valor_desejado_series
qtd_exata_inicial = valor_desejado_series / df_alloc["Preço Inicial (USD)"]
df_alloc["Qtd exata"] = qtd_exata_inicial
df_alloc["Qtd inteira (inicial)"] = df_alloc["Qtd inteira (inicial)"].astype(int)
df_alloc["Resíduo (inicial)"] = (
    qtd_exata_inicial - df_alloc["Qtd inteira (inicial)"]
).round(6)

df_compra_inicial = df_alloc[
    [
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
].copy()
if not df_compra_inicial.empty:
    df_compra_inicial["FX local→USD (compra)"] = (
        df_compra_inicial["FX local→USD (compra)"].astype(float)
    )

# Ajuste do caixa remanescente
caixa = valor_total - (df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]).sum()
caixa_inicial = caixa
min_price = df_alloc["Preço Inicial (USD)"].min()
eventos = []
EPS = 1e-6

while caixa + EPS >= min_price:
    alvo_usd = valor_total * df_alloc["Peso (%)"] / 100.0
    invest_atual_usd = df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]
    gap_usd = alvo_usd - invest_atual_usd

    affordable_mask = df_alloc["Preço Inicial (USD)"] <= (caixa + EPS)
    if not affordable_mask.any():
        break

    candidatos = df_alloc.loc[affordable_mask, ["Preço Inicial (USD)"]].copy()
    candidatos["Gap USD"] = gap_usd.loc[affordable_mask]
    candidatos = candidatos.sort_values(
        by=["Gap USD", "Preço Inicial (USD)"], ascending=[False, True]
    )

    idx_escolhido = candidatos.index[0]
    if candidatos.loc[idx_escolhido, "Gap USD"] <= 0:
        break

    caixa_antes = caixa
    gap_antes = gap_usd.loc[idx_escolhido]
    preco_compra = df_alloc.loc[idx_escolhido, "Preço Inicial (USD)"]
    df_alloc.loc[idx_escolhido, "Quantidade"] += 1
    caixa -= preco_compra

    invest_atual_usd = df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]
    gap_depois = (
        valor_total * df_alloc.loc[idx_escolhido, "Peso (%)"] / 100.0
    ) - invest_atual_usd.loc[idx_escolhido]

    eventos.append(
        {
            "Empresa": df_alloc.loc[idx_escolhido, "Empresa"],
            "Ticker": df_alloc.loc[idx_escolhido, "Ticker"],
            "Preço Inicial (USD)": float(preco_compra),
            "Gap antes (USD)": float(gap_antes),
            "Gap depois (USD)": float(gap_depois),
            "Caixa antes (USD)": float(caixa_antes),
            "Caixa depois (USD)": float(caixa),
            "Compra": "+1 unidade",
        }
    )

caixa_final = caixa
valor_desejado_series = valor_total * df_alloc["Peso (%)"] / 100.0
qtd_exata_final = valor_desejado_series / df_alloc["Preço Inicial (USD)"]
df_alloc["Resíduo"] = (qtd_exata_final - df_alloc["Quantidade"]).round(6)
df_log = pd.DataFrame(eventos)

# --- Preço Atual via yfinance ---
historicos_usd = {}
for ticker in tickers.values():
    currency = obter_moeda_ticker(ticker)
    try:
        hist = yf.Ticker(ticker).history(start=data_str, end=hoje_str)
        if hist.empty or "Close" not in hist:
            raise ValueError("sem dados de fechamento")
        serie = hist["Close"].copy()
        serie.index = serie.index.tz_localize(None)
        fx_alinhado = fx_series[currency].reindex(serie.index, method="ffill")
        fx_alinhado = fx_alinhado.bfill()
        serie_usd = serie * fx_alinhado
        historicos_usd[ticker] = serie_usd
    except Exception as exc:
        st.warning(f"Falha ao obter histórico para {ticker}: {exc}")
        historicos_usd[ticker] = pd.Series(dtype=float)

prices_usd_df = pd.DataFrame(historicos_usd)
prices_usd_df = prices_usd_df.reindex(index=indice_util)
prices_usd_df = prices_usd_df.reindex(columns=list(tickers.values()))
prices_usd_df = prices_usd_df.ffill()
for ticker, preco_ini in precos_iniciais_usd.items():
    if ticker in prices_usd_df.columns:
        prices_usd_df[ticker] = prices_usd_df[ticker].fillna(preco_ini)

precos_atuais_series = df_alloc["Ticker"].map(prices_usd_df.iloc[-1])
precos_atuais_series = precos_atuais_series.fillna(df_alloc["Preço Inicial (USD)"])
df_alloc["Preço Atual (USD)"] = precos_atuais_series.round(2)

# --- Investimentos inicial e atual ---
df_alloc["Investimento Inicial (USD)"] = (
    df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]
).round(2)
df_alloc["Investimento Atual (USD)"] = (
    df_alloc["Quantidade"] * precos_atuais_series
).round(2)

# --- Ganho/Perda e Variação ---
df_alloc["Ganho/Perda (USD)"] = (
    df_alloc["Investimento Atual (USD)"] - df_alloc["Investimento Inicial (USD)"]
).round(2)
variacao_base = df_alloc["Investimento Inicial (USD)"].replace(0, pd.NA)
df_alloc["Variação (%)"] = (
    (df_alloc["Ganho/Perda (USD)"] / variacao_base) * 100
).fillna(0.0).round(2)

# --- Totais e Métricas ---
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
    aba1, aba2, aba3 = st.tabs(
        ["🛒 Compra Inicial", "📜 Log de distribuição", "📊 Gráficos"]
    )

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
        st.dataframe(
            df_compra_inicial.set_index("Empresa").style.format(fmt1)
        )
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
                f"{row['Ticker']} (+1)" for _, row in df_log.iterrows()
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

# --- Tabela de Alocação (Empresa como índice) ---
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
# Detecta tema (com override manual do sidebar)
is_dark = _theme_is_dark(force=True if force_dark_toggle else None)
txt_col = "white" if is_dark else "black"
edge_col = "white" if is_dark else "black"

# ordena para manter maior fatia “às 12h”
df_plot = df_alloc.sort_values("Investimento Inicial (USD)", ascending=False)

# fundo transparente
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

# Força cor/tamanho das labels (nomes) e percentuais
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
# Série histórica do portfólio
historico_portfolio = prices_usd_df.copy()

quantidades = df_alloc.set_index("Ticker")["Quantidade"]
port_val = (historico_portfolio * quantidades).sum(axis=1)
if total_investido:
    port_ret = (port_val / total_investido - 1) * 100
else:
    port_ret = pd.Series(0.0, index=port_val.index)

df_ret = port_ret.rename("Retorno (%)").reset_index().rename(columns={"index": "Data"})
# período por ponto (da data de compra até cada data)
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
