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
data_compra = st.date_input(
    "📅 Data da Compra (retroativa)",
    value=date(2025, 7, 15),
    max_value=date.today() - timedelta(days=1),
)
data_str = data_compra.strftime("%Y-%m-%d")
periodo_str = formatar_periodo(data_compra, date.today())

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
pesos = dict(zip(empresas, [15, 15, 10, 8, 7, 12, 8, 10, 7, 8]))

# --- Alocação otimizada via resíduos ---
dados_alloc = []
for empresa in empresas:
    ticker = tickers[empresa]
    peso = pesos[empresa]
    preco_ini = float(df_precos_iniciais.loc[ticker, "PrecoInicial"])
    valor_desejado = valor_total * peso / 100
    qtd_exata = valor_desejado / preco_ini
    parte_int = int(qtd_exata)
    residuo = qtd_exata - parte_int
    dados_alloc.append(
        {
            "Empresa": empresa,
            "Ticker": ticker,
            "Peso (%)": peso,
            "Quantidade": parte_int,
            "Preço Inicial (USD)": round(preco_ini, 2),
            "Resíduo": residuo,
        }
    )

df_alloc = pd.DataFrame(dados_alloc)

# Ajuste do caixa remanescente
caixa = valor_total - (df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]).sum()
df_alloc = df_alloc.sort_values("Resíduo", ascending=False).reset_index(drop=True)
for i in range(len(df_alloc)):
    preco_compra = df_alloc.loc[i, "Preço Inicial (USD)"]
    if caixa >= preco_compra:
        df_alloc.loc[i, "Quantidade"] += 1
        caixa -= preco_compra

# --- Preço Atual via yfinance ---
precos_atuais = {}
today_str = date.today().strftime("%Y-%m-%d")
for ticker in df_alloc["Ticker"]:
    try:
        hist = yf.Ticker(ticker).history(start=data_str, end=today_str)["Close"]
        hist.index = hist.index.tz_localize(None)
        precos_atuais[ticker] = hist.iloc[-1]
    except Exception:
        precos_atuais[ticker] = None

df_alloc["Preço Atual (USD)"] = df_alloc["Ticker"].map(precos_atuais).round(2)

# --- Investimentos inicial e atual ---
df_alloc["Investimento Inicial (USD)"] = (
    df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]
).round(2)
df_alloc["Investimento Atual (USD)"] = (
    df_alloc["Quantidade"] * df_alloc["Preço Atual (USD)"]
).round(2)

# --- Ganho/Perda e Variação ---
df_alloc["Ganho/Perda (USD)"] = (
    df_alloc["Investimento Atual (USD)"] - df_alloc["Investimento Inicial (USD)"]
).round(2)
df_alloc["Variação (%)"] = (
    (df_alloc["Ganho/Perda (USD)"] / df_alloc["Investimento Inicial (USD)"]) * 100
).round(2)

# --- Totais e Métricas ---
total_investido = df_alloc["Investimento Inicial (USD)"].sum()
total_atual = df_alloc["Investimento Atual (USD)"].sum()
ganho_total = total_atual - total_investido
variacao_total = (ganho_total / total_investido) * 100

st.subheader("📈 Resumo do Portfólio")
col1, col2, col3 = st.columns(3)
col1.metric("Total Investido (USD)", f"${total_investido:,.2f}")
col2.metric("Valor Atual (USD)", f"${total_atual:,.2f}")
col3.metric("Ganho/Perda Total", f"${ganho_total:,.2f}", f"{variacao_total:.2f}%")

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
prices = {}
for ticker in df_alloc["Ticker"]:
    hist = yf.Ticker(ticker).history(start=data_str, end=today_str)["Close"]
    hist.index = hist.index.tz_localize(None)
    prices[ticker] = hist

# Apenas dias úteis
bd = pd.date_range(start=data_compra, end=date.today(), freq="B")
prices_df = pd.DataFrame(prices).reindex(bd).ffill()

quantidades = df_alloc.set_index("Ticker")["Quantidade"]
port_val = (prices_df * quantidades).sum(axis=1)
port_ret = (port_val / total_investido - 1) * 100

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
