import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from datetime import date, timedelta

# --- Interface ---
st.title("💹 Simulador de Portfólio: IA na China")
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
    max_value=date.today() - timedelta(days=1)
)
data_str = data_compra.strftime("%d-m%-Y%")
st.markdown(f"**Data de Compra:** {data_str}")

# --- Leitura do CSV de Preços Iniciais ---
arquivo_precos = f"precos_iniciais_{data_str}.csv"
if os.path.exists(arquivo_precos):
    df_precos_iniciais = pd.read_csv(arquivo_precos, index_col=0)
else:
    st.error(f"Arquivo não encontrado: {arquivo_precos}")
    st.stop()

# --- Definição de Ativos e Pesos ---
empresas = [
    "Baidu", "Alibaba", "Tencent", "SenseTime", "iFlytek",
    "SMIC", "Cambricon", "Estun Automation", "Siasun Robot", "Hygon"
]
tickers = {empresa: tick for empresa, tick in zip(empresas, [
    "BIDU", "BABA", "0700.HK", "0020.HK", "002230.SZ",
    "0981.HK", "688256.SS", "002747.SZ", "300024.SZ", "688041.SS"
])}
pesos = dict(zip(empresas, [15, 15, 10, 8, 7, 12, 8, 10, 7, 8]))

# --- Alocação otimizada via resíduos ---
dados_alloc = []
for empresa in empresas:
    ticker    = tickers[empresa]
    peso      = pesos[empresa]
    preco_ini = float(df_precos_iniciais.loc[ticker, "PrecoInicial"])
    valor_desejado = valor_total * peso / 100
    qtd_exata = valor_desejado / preco_ini
    parte_int = int(qtd_exata)
    residuo   = qtd_exata - parte_int
    dados_alloc.append({
        "Empresa": empresa,
        "Ticker": ticker,
        "Peso (%)": peso,
        "Quantidade": parte_int,
        "Preço Inicial (USD)": round(preco_ini, 2),
        "Resíduo": residuo
    })

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
    except:
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
total_atual     = df_alloc["Investimento Atual (USD)"].sum()
ganho_total     = total_atual - total_investido
variacao_total  = (ganho_total / total_investido) * 100

st.subheader("📈 Resumo do Portfólio")
col1, col2, col3 = st.columns(3)
col1.metric("Total Investido (USD)", f"${total_investido:,.2f}")
col2.metric("Valor Atual (USD)",      f"${total_atual:,.2f}")
col3.metric("Ganho/Perda Total",      f"${ganho_total:,.2f}", f"{variacao_total:.2f}%")

# --- Tabela de Alocação com Empresa como índice (pinned) ---
df_display = df_alloc.set_index("Empresa")[[
    "Ticker", "Peso (%)", "Quantidade",
    "Preço Inicial (USD)", "Preço Atual (USD)",
    "Investimento Inicial (USD)", "Investimento Atual (USD)",
    "Ganho/Perda (USD)", "Variação (%)"
]]

# Formatação para colunas USD e %
format_dict = {
    "Preço Inicial (USD)":        "{:,.2f}",
    "Preço Atual (USD)":          "{:,.2f}",
    "Investimento Inicial (USD)": "{:,.2f}",
    "Investimento Atual (USD)":   "{:,.2f}",
    "Ganho/Perda (USD)":          "{:,.2f}",
    "Peso (%)":                   "{:.2f}",
    "Variação (%)":               "{:.2f}%"
}

st.subheader("📋 Alocação Inteligente de Portfólio")
st.dataframe(
    df_display
      .style
      .format(format_dict)
      .set_properties(**{"text-align": "right"})
)

# --- Gráfico 1: Pizza da Alocação Inicial (ordenada, maior slice às 12h) ---
df_plot = df_alloc.sort_values("Investimento Inicial (USD)", ascending=False)
fig1, ax1 = plt.subplots()
ax1.pie(
    df_plot["Investimento Inicial (USD)"],
    labels=df_plot["Empresa"],
    autopct="%1.1f%%",
    startangle=90,
    counterclock=False
)
ax1.axis("equal")
st.subheader("🍰 Distribuição do Investimento Inicial")
st.pyplot(fig1)

# --- Gráfico 2: Evolução do Retorno (%) do Portfólio (ajustado) ---
prices = {}
for ticker in df_alloc["Ticker"]:
    hist = yf.Ticker(ticker).history(start=data_str, end=today_str)["Close"]
    hist.index = hist.index.tz_localize(None)
    prices[ticker] = hist

bd = pd.date_range(start=data_compra, end=date.today(), freq="B")
prices_df = pd.DataFrame(prices).reindex(bd).ffill()

quantidades = df_alloc.set_index("Ticker")["Quantidade"]
port_val = (prices_df * quantidades).sum(axis=1)

port_ret = (port_val / total_investido - 1) * 100

fig2, ax2 = plt.subplots()
ax2.plot(port_ret.index, port_ret.values, linewidth=2)
ax2.set_title("Evolução do Retorno do Portfólio (%)")
ax2.set_xlabel("Data")
ax2.set_ylabel("Retorno (%)")
ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
fig2.autofmt_xdate()

st.subheader("📈 Evolução do Retorno do Portfólio")
st.pyplot(fig2)
