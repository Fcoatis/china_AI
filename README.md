# 💹 Simulador de Portfólio Temático: IA na China

## 🧠 Contexto: Empresas de IA e Modelos Fundacionais

A China tem impulsionado uma estratégia nacional ambiciosa para dominar setores-chave da Inteligência Artificial, semicondutores e automação. Em resposta às sanções tecnológicas e restrições de exportação de chips por parte dos EUA, o governo chinês tem financiado pesadamente empresas estratégicas locais.

A construção de modelos fundacionais, chips proprietários e a aplicação de IA em áreas como robótica, medicina, segurança e consumo tem gerado oportunidades de investimento temático relevantes.

Aqui está uma sugestão de portfólio temático com 10 empresas chinesas ligadas à estratégia nacional de IA, chips e automação, incluindo seus setores, preços aproximados em dólares e pesos sugeridos. Os pesos foram balanceados para refletir influência estratégica, liquidez e risco:

| Empresa              | Ticker      | Setor                | Peso (%) |
|----------------------|-------------|-----------------------|----------|
| Baidu               | BIDU        | Big Tech / IA         | 15%      |
| Alibaba             | BABA        | E-commerce / Cloud    | 15%      |
| Tencent             | 0700.HK     | IA / Entretenimento   | 10%      |
| SenseTime           | 0020.HK     | Visão Computacional   | 8%       |
| iFlytek             | 002230.SZ   | IA / NLP              | 7%       |
| SMIC                | 0981.HK     | Chips (foundry)       | 12%      |
| Cambricon           | 688256.SS   | Chips IA              | 8%       |
| Estun Automation    | 002747.SZ   | Robótica Industrial   | 10%      |
| Siasun Robot        | 300024.SZ   | Robótica Industrial   | 7%       |
| Hygon               | 688041.SS   | Chips / CPU           | 8%       |

---

## ⚙️ Operacional: Como usar o Simulador

Este projeto utiliza [Streamlit](https://streamlit.io/) para simular o desempenho de um portfólio temático com foco em IA na China.

### ▶️ Passo a passo

1. **Valor Investido**  
   Escolha o valor total disponível em dólares (mínimo de $1.000).

2. **Data da Compra**  
   Por padrão, o simulador assume a data retroativa de **15/07/2025**.  
   Você pode ajustar a data para qualquer outro dia **anterior ao dia atual**.

3. **Cálculo da Alocação**  
   Com base nos pesos e nos preços históricos da data escolhida, o simulador determina:
   - Quantidade de ações compradas por empresa
   - Investimento inicial
   - Valor atual
   - Ganho/perda e variação percentual

4. **Visualização**  
   O simulador apresenta:
   - 📊 **Tabela de Alocação Inteligente**
   - 📈 **Resumo do Portfólio**
   - 🧩 **Distribuição em Gráfico de Pizza**
   - 📉 **Gráfico de Evolução do Retorno (%)**

### 📁 Requisitos

- Python 3.12
- Bibliotecas:
  - `streamlit`
  - `yfinance`
  - `pandas`
  - `matplotlib`

---

✨ Esperamos que este simulador ajude você a explorar cenários de investimento em IA na China com uma abordagem prática e visual!
