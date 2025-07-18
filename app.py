import streamlit as st
import yfinance as yf
import pandas as pd
import os
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date

# --- Interface ---
st.title("💹 Simulador de Portfólio Temático: IA na China")
valor_total = st.number_input("Valor total investido (USD)", min_value=1000, value=10000, step=500)

# Selecionar a data da compra
#data_compra = st.date_input("📅 Data da Compra (retroativa)", value=date.today() - timedelta(days=30), max_value=date.today() - timedelta(days=1))
data_compra = st.date_input("📅 Data da Compra (retroativa)", value=date(2025, 7, 15), max_value=date.today() - timedelta(days=1))

empresas = [
    "Baidu", "Alibaba", "Tencent", "SenseTime", "iFlytek",
    "SMIC", "Cambricon", "Estun Automation", "Siasun Robot", "Hygon"
]
tickers = {
    "Baidu": "BIDU",
    "Alibaba": "BABA",
    "Tencent": "0700.HK",
    "SenseTime": "0020.HK",
    "iFlytek": "002230.SZ",
    "SMIC": "0981.HK",
    "Cambricon": "688256.SS",
    "Estun Automation": "002747.SZ",
    "Siasun Robot": "300024.SZ",
    "Hygon": "688041.SS"
}
pesos = {
    "Baidu": 15, "Alibaba": 15, "Tencent": 10, "SenseTime": 8, "iFlytek": 7,
    "SMIC": 12, "Cambricon": 8, "Estun Automation": 10, "Siasun Robot": 7, "Hygon": 8
}

# Arquivo com preços salvos com base na data
data_str = data_compra.strftime("%Y-%m-%d")
arquivo_precos = f"precos_iniciais_{data_str}.csv"
if os.path.exists(arquivo_precos):
    df_precos_iniciais = pd.read_csv(arquivo_precos, index_col=0)
else:
    df_precos_iniciais = pd.DataFrame(columns=["PrecoInicial"])

dados = []

# --- Coleta dados e simula ---
for empresa in empresas:
    ticker = tickers[empresa]
    peso = pesos[empresa]
    investimento = valor_total * peso / 100

    # Buscar preço inicial da data escolhida
    if ticker in df_precos_iniciais.index:
        try:
            preco_inicial = float(df_precos_iniciais.loc[ticker, "PrecoInicial"])
        except:
            preco_inicial = None
    else:
        try:
            df_hist = yf.download(ticker, start=data_compra - timedelta(days=5), end=data_compra + timedelta(days=1))
            if not df_hist.empty:
                preco_inicial = float(df_hist["Close"].ffill().iloc[-1])
                df_precos_iniciais.loc[ticker, "PrecoInicial"] = preco_inicial
                df_precos_iniciais.to_csv(arquivo_precos)
            else:
                preco_inicial = None
        except Exception:
            preco_inicial = None

    # Buscar preço atual
    try:
        df_atual = yf.download(ticker, period="5d")
        preco_atual = float(df_atual["Close"].dropna().iloc[-1]) if not df_atual.empty else None
    except Exception:
        preco_atual = None

    # Cálculo final
    if preco_inicial is not None and preco_atual is not None:
        qtd = round(investimento / preco_inicial)
        invest_atual = qtd * preco_atual
        ganho = invest_atual - investimento
        variacao_pct = (preco_atual - preco_inicial) / preco_inicial * 100

        dados.append({
            "Empresa": empresa,
            "Ticker": ticker,
            "Peso (%)": peso,
            "Preço Inicial (USD)": round(preco_inicial, 2),
            "Preço Atual (USD)": round(preco_atual, 2),
            "Quantidade": qtd,
            "Investimento Inicial (USD)": round(investimento, 2),
            "Investimento Atual (USD)": round(invest_atual, 2),
            "Ganho/Perda (USD)": round(ganho, 2),
            "Variação (%)": round(variacao_pct, 2)
        })

# Exibição
df = pd.DataFrame(dados)

st.subheader("📊 Tabela de Investimentos")
st.dataframe(df.set_index("Empresa"))

total_investido = df["Investimento Inicial (USD)"].sum()
total_atual = df["Investimento Atual (USD)"].sum()
ganho_total = total_atual - total_investido
variacao_total = (ganho_total / total_investido) * 100

st.subheader("📈 Resumo do Portfólio")
st.metric("Total Investido (USD)", f"${total_investido:,.2f}")
st.metric("Valor Atual (USD)", f"${total_atual:,.2f}")
st.metric("Ganho/Perda Total", f"${ganho_total:,.2f} ({variacao_total:.2f}%)")

st.subheader("🧩 Distribuição por Empresa")
fig, ax = plt.subplots(figsize=(6, 6))
df.set_index("Empresa")["Investimento Atual (USD)"].plot.pie(autopct='%1.1f%%', ax=ax)
st.pyplot(fig)
