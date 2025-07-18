import streamlit as st
import yfinance as yf
import pandas as pd

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

st.title("💹 Simulador de Portfólio Temático: IA na China")
valor_total = st.number_input("Valor total investido (USD)", min_value=1000, value=10000, step=500)

dados = []
for empresa in empresas:
    ticker = tickers[empresa]
    peso = pesos[empresa]
    investimento = valor_total * peso / 100

    try:
        df = yf.download(ticker, period="5d")
        preco_atual = df["Close"].dropna().iloc[-1]
    except Exception:
        preco_atual = None

    if preco_atual:
        qtd = round(investimento / preco_atual)
        invest_atual = qtd * preco_atual
        dados.append({
            "Empresa": empresa,
            "Ticker": ticker,
            "Peso (%)": peso,
            "Preço Atual (USD)": round(preco_atual, 2),
            "Quantidade": qtd,
            "Investimento Inicial (USD)": round(investimento, 2),
            "Investimento Atual (USD)": round(invest_atual, 2),
            "Ganho/Perda (USD)": round(invest_atual - investimento, 2)
        })

df = pd.DataFrame(dados)
total_investido = df["Investimento Inicial (USD)"].sum()
total_atual = df["Investimento Atual (USD)"].sum()
ganho_total = total_atual - total_investido
variacao_pct = (ganho_total / total_investido) * 100

st.subheader("📊 Tabela de Investimentos")
st.dataframe(df.set_index("Empresa"))

st.subheader("📈 Resumo do Portfólio")
st.metric("Total Investido (USD)", f"${total_investido:,.2f}")
st.metric("Valor Atual (USD)", f"${total_atual:,.2f}")
st.metric("Ganho/Perda Total", f"${ganho_total:,.2f} ({variacao_pct:.2f}%)")

st.subheader("🧩 Distribuição por Empresa")
st.pyplot(df.set_index("Empresa")["Investimento Atual (USD)"].plot.pie(autopct='%1.1f%%', figsize=(6, 6)).get_figure())
