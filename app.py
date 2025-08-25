from pathlib import Path
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import plotly.express as px

# ------------------ Config da página ------------------ #
st.set_page_config(page_title="Simulador de Portfólio: IA na China", layout="centered")
st.title("💹 Simulador de Portfólio: IA na China")


# ------------------ Funções de Utilidade e Lógica ------------------ #

def formatar_periodo(dt_inicial, dt_final):
    """Diferença entre datas em anos/meses/dias (PT-BR)."""
    if not isinstance(dt_inicial, date) or not isinstance(dt_final, date):
        return ""
    rd = relativedelta(dt_final, dt_inicial)
    partes = []
    if rd.years:
        partes.append(f"{rd.years} ano" + ("s" if rd.years > 1 else ""))
    if rd.months:
        partes.append("1 mês" if rd.months == 1 else f"{rd.months} meses")
    if rd.days:
        partes.append(f"{rd.days} dia" + ("s" if rd.days > 1 else ""))

    if not partes:
        return "0 dias"
    if len(partes) == 1:
        return partes[0]
    if len(partes) == 2:
        return " e ".join(partes)
    return f"{partes[0]}, {partes[1]} e {partes[2]}"

# --- Funções de Tema para Gráfico Matplotlib ---
def _hex_to_rgb(hexstr: str):
    h = hexstr.lstrip("#")
    if len(h) != 6: return None
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return None

def _luma(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _theme_is_dark(force: bool | None = None) -> bool:
    """Detecta o tema escuro do Streamlit com fallbacks."""
    if force is not None: return force
    try:
        base = st.get_option("theme.base")
        if isinstance(base, str): return base.lower() == "dark"
        bg = st.get_option("theme.backgroundColor")
        if isinstance(bg, str) and (rgb := _hex_to_rgb(bg)): return _luma(rgb) < 128
        txt = st.get_option("theme.textColor")
        if isinstance(txt, str) and (rgb := _hex_to_rgb(txt)): return _luma(rgb) > 200
    except Exception:
        pass
    return False

# ------------------ Funções de Busca de Dados (com Cache) ------------------ #

@st.cache_data
def get_initial_prices(data_compra, tickers_list):
    """Busca ou carrega os preços iniciais, salvando em CSV se não existir."""
    data_str = data_compra.strftime("%Y-%m-%d")
    arquivo_precos = f"precos_iniciais_{data_str}.csv"

    if Path(arquivo_precos).exists():
        return pd.read_csv(arquivo_precos, index_col=0)

    with st.spinner(f"Baixando dados de preços para {data_str}..."):
        try:
            end_date_fetch = data_compra + timedelta(days=7)
            dados = yf.download(
                tickers_list, start=data_compra, end=end_date_fetch,
                progress=False, auto_adjust=False
            )['Close']

            if dados.empty:
                st.error(f"Não foi possível obter dados de preços para {data_str}. Tente outra data.")
                st.stop()

            precos_iniciais = dados.bfill().iloc[0]
            df_precos = precos_iniciais.to_frame(name="PrecoInicial")
            df_precos.to_csv(arquivo_precos)
            st.success(f"Dados salvos com sucesso em '{arquivo_precos}'")
            return df_precos
        except Exception as e:
            st.error(f"Ocorreu um erro ao baixar os dados: {e}")
            st.stop()

@st.cache_data
def get_current_prices(tickers_list):
    """Busca os preços atuais para uma lista de tickers de forma otimizada."""
    try:
        start_fetch = date.today() - timedelta(days=5)
        end_fetch = date.today() + timedelta(days=1)
        dados = yf.download(
            tickers_list, start=start_fetch, end=end_fetch,
            progress=False, auto_adjust=False
        )['Close']
        return dados.ffill().iloc[-1]
    except Exception:
        return pd.Series(dtype=float)

@st.cache_data
def get_historical_prices(tickers_list, start_date):
    """Busca o histórico de preços para o gráfico de evolução."""
    prices_df = yf.download(
        tickers_list, start=start_date, end=date.today() + timedelta(days=1),
        progress=False, auto_adjust=False
    )['Close']
    prices_df.index = prices_df.index.tz_localize(None)
    return prices_df.ffill().bfill()


# ------------------ Sidebar e Inputs ------------------ #
force_dark_toggle = st.sidebar.toggle(
    "Forçar labels brancos no gráfico", value=False,
    help="Use se as labels da pizza não ficarem legíveis no modo escuro."
)

valor_total = st.number_input(
    "Valor total disponível (USD)", min_value=1000, value=10000, step=500
)

data_compra = st.date_input(
    "📅 Data da Compra (retroativa)", value=date(2025, 7, 15),
    max_value=date.today() - timedelta(days=1)
)

# ------------------ Definição de Ativos e Pesos ------------------ #
empresas = [
    "Baidu", "Alibaba", "Tencent", "SenseTime", "iFlytek", "SMIC",
    "Cambricon", "Estun Automation", "Siasun Robot", "Hygon",
]
tickers_list = [
    "BIDU", "BABA", "0700.HK", "0020.HK", "002230.SZ", "0981.HK",
    "688256.SS", "002747.SZ", "300024.SZ", "688041.SS",
]
tickers = dict(zip(empresas, tickers_list))
pesos = dict(zip(empresas, [15, 15, 10, 8, 7, 12, 8, 10, 7, 8]))

# ------------------ Processamento Principal ------------------ #
df_precos_iniciais = get_initial_prices(data_compra, tickers_list)

# --- Alocação otimizada via resíduos ---
dados_alloc = []
for empresa in empresas:
    ticker = tickers[empresa]
    if ticker in df_precos_iniciais.index and not pd.isna(df_precos_iniciais.loc[ticker, "PrecoInicial"]):
        preco_ini = float(df_precos_iniciais.loc[ticker, "PrecoInicial"])
        valor_desejado = valor_total * pesos[empresa] / 100
        qtd_exata = valor_desejado / preco_ini
        dados_alloc.append({
            "Empresa": empresa, "Ticker": ticker, "Peso (%)": pesos[empresa],
            "Quantidade": int(qtd_exata), "Preço Inicial (USD)": round(preco_ini, 2),
            "Resíduo": qtd_exata - int(qtd_exata),
        })
df_alloc = pd.DataFrame(dados_alloc)

# Ajuste com caixa remanescente
caixa = valor_total - (df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]).sum()
df_alloc = df_alloc.sort_values("Resíduo", ascending=False).reset_index(drop=True)
for i in range(len(df_alloc)):
    preco_compra = df_alloc.loc[i, "Preço Inicial (USD)"]
    if caixa >= preco_compra:
        df_alloc.loc[i, "Quantidade"] += 1
        caixa -= preco_compra

# --- Busca de Preços Atuais e Cálculos ---
precos_atuais_series = get_current_prices(df_alloc["Ticker"].tolist())
df_alloc["Preço Atual (USD)"] = df_alloc["Ticker"].map(precos_atuais_series).round(2)
df_alloc.dropna(subset=["Preço Atual (USD)"], inplace=True)

df_alloc["Investimento Inicial (USD)"] = (df_alloc["Quantidade"] * df_alloc["Preço Inicial (USD)"]).round(2)
df_alloc["Investimento Atual (USD)"] = (df_alloc["Quantidade"] * df_alloc["Preço Atual (USD)"]).round(2)
df_alloc["Ganho/Perda (USD)"] = (df_alloc["Investimento Atual (USD)"] - df_alloc["Investimento Inicial (USD)"]).round(2)
df_alloc["Variação (%)"] = ((df_alloc["Ganho/Perda (USD)"] / df_alloc["Investimento Inicial (USD)"]) * 100).round(2)

# ------------------ Exibição dos Resultados ------------------ #
total_investido = df_alloc["Investimento Inicial (USD)"].sum()
total_atual = df_alloc["Investimento Atual (USD)"].sum()
ganho_total = total_atual - total_investido
variacao_total = (ganho_total / total_investido) * 100 if total_investido else 0

st.subheader("📈 Resumo do Portfólio")
periodo_str = formatar_periodo(data_compra, date.today())
st.markdown(f"**Período do Investimento:** {periodo_str}")

col1, col2, col3 = st.columns(3)
col1.metric("Total Investido (USD)", f"${total_investido:,.2f}")
col2.metric("Valor Atual (USD)", f"${total_atual:,.2f}")
col3.metric("Ganho/Perda Total", f"${ganho_total:,.2f}", f"{variacao_total:.2f}%")

st.subheader("📋 Alocação Inteligente de Portfólio")
df_display = df_alloc.set_index("Empresa")[[
    "Ticker", "Peso (%)", "Quantidade", "Preço Inicial (USD)", "Preço Atual (USD)",
    "Investimento Inicial (USD)", "Investimento Atual (USD)", "Ganho/Perda (USD)", "Variação (%)"
]]
st.dataframe(df_display.style.format({
    "Preço Inicial (USD)": "{:,.2f}", "Preço Atual (USD)": "{:,.2f}",
    "Investimento Inicial (USD)": "{:,.2f}", "Investimento Atual (USD)": "{:,.2f}",
    "Ganho/Perda (USD)": "{:,.2f}", "Peso (%)": "{:.2f}", "Variação (%)": "{:.2f}%"
}).set_properties(**{"text-align": "right"}))

# ------------------ Gráfico 1: Pizza (Matplotlib) ------------------ #
st.subheader("🍰 Distribuição do Investimento Inicial")
is_dark = _theme_is_dark(force=True if force_dark_toggle else None)
txt_col = "white" if is_dark else "black"
df_plot = df_alloc.sort_values("Investimento Inicial (USD)", ascending=False)

plt.rcParams["savefig.transparent"] = True
fig1, ax1 = plt.subplots(facecolor="none")
wedges, texts, autotexts = ax1.pie(
    df_plot["Investimento Inicial (USD)"], labels=df_plot["Empresa"], autopct="%1.1f%%",
    startangle=90, counterclock=False, wedgeprops={"edgecolor": txt_col, "linewidth": 1.0}
)
plt.setp(texts, color=txt_col, fontsize=11)
plt.setp(autotexts, color=txt_col, fontsize=11)
ax1.axis("equal")
st.pyplot(fig1, transparent=True)

# ------------------ Gráfico 2: Linha (Plotly) ------------------ #
if not df_alloc.empty:
    st.subheader("📈 Evolução do Retorno do Portfólio")
    prices_df = get_historical_prices(df_alloc["Ticker"].tolist(), data_compra)

    quantidades = df_alloc.set_index("Ticker")["Quantidade"]
    port_val = (prices_df[quantidades.index] * quantidades).sum(axis=1)
    port_ret = (port_val / total_investido - 1) * 100 if total_investido else 0

    # --- Preparação do DataFrame para o Gráfico (CORREÇÃO DO KEYERROR) ---
    df_ret = port_ret.rename("Retorno (%)").reset_index()
    df_ret.rename(columns={"Date": "Data"}, inplace=True) # Renomeia 'Date' para 'Data'
    df_ret.dropna(inplace=True)
    df_ret["Período"] = df_ret["Data"].dt.date.map(lambda d: formatar_periodo(data_compra, d))

    fig2 = px.line(
        df_ret, x="Data", y="Retorno (%)",
        title="Evolução do Retorno do Portfólio (%)"
    )
    fig2.update_traces(
        customdata=df_ret["Período"],
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Retorno: %{y:.2f}%%<br>Período: %{customdata}<extra></extra>"
    )
    fig2.update_layout(
        xaxis_title="Data", yaxis_title="Retorno (%)",
        xaxis=dict(tickformat="%d/%m/%y"), hovermode="x unified"
    )
    st.plotly_chart(fig2, use_container_width=True)