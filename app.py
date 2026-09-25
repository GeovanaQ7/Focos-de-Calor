"""
Dashboard de Focos de Calor na Amazônia - INPE (BDQueimadas)
Compara 2025 vs 2026. Lê todos os CSVs da pasta dados/.
Rode com: streamlit run app.py
"""
import glob
import unicodedata

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Focos de Calor no Brasil", page_icon="🔥", layout="wide")

# ---------------------------------------------------------
# ESTILO (tema claro padrão, só um leve destaque nos cards)
# ---------------------------------------------------------
st.markdown("""
<style>
[data-testid="stMetric"] {
    background-color: var(--secondary-background-color);
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 10px;
    padding: 14px 16px;
}
[data-testid="stMetricValue"] { color: var(--text-color) !important; }
[data-testid="stMetricLabel"] { color: var(--text-color) !important; opacity: 0.75; }
[data-testid="stMetricDelta"] { color: var(--text-color) !important; }
.insight-box {
    background-color: var(--secondary-background-color);
    border: 1px solid rgba(255, 122, 69, 0.35);
    border-left: 4px solid #ff7a45;
    border-radius: 10px;
    padding: 16px 20px;
    margin-top: 8px;
    color: var(--text-color);
}
.insight-box li { margin-bottom: 8px; color: var(--text-color); }
#MainMenu { visibility: hidden; }
[data-testid="stMainMenu"] { visibility: hidden; }
[data-testid="stToolbarActions"] { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_white"
PAPER_BG = "white"
ESCALA_CORES = "OrRd"
COR_2025 = "#4c8bf5"
COR_2026 = "#e34a33"


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c)).upper().strip()


@st.cache_data
def carregar_dados():
    arquivos = glob.glob("dados/*.csv")
    if not arquivos:
        return pd.DataFrame()
    partes = []
    for arq in arquivos:
        try:
            partes.append(pd.read_csv(arq, encoding="utf-8"))
        except UnicodeDecodeError:
            partes.append(pd.read_csv(arq, encoding="latin-1"))
    df = pd.concat(partes, ignore_index=True).drop_duplicates()
    df["DataHora"] = pd.to_datetime(df["DataHora"], errors="coerce")
    df = df.dropna(subset=["DataHora"])
    df["ano"] = df["DataHora"].dt.year
    df["mes"] = df["DataHora"].dt.month
    df["Estado"] = df["Estado"].str.title()
    df["estado_chave"] = df["Estado"].apply(normalizar)
    return df


@st.cache_data
def carregar_geojson():
    url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    gj = requests.get(url, timeout=30).json()
    for f in gj["features"]:
        f["properties"]["chave"] = normalizar(f["properties"]["name"])
    return gj


def estilizar(fig, altura=380):
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font_color="#333333", height=altura,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig


# ---------------------------------------------------------
# DADOS
# ---------------------------------------------------------
df = carregar_dados()
if df.empty:
    st.error("Nenhum CSV encontrado. Crie uma pasta 'dados' ao lado do app.py com os "
              "arquivos exportados do BDQueimadas.")
    st.stop()

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# ---------------------------------------------------------
# FILTROS (barra lateral)
# ---------------------------------------------------------
st.sidebar.header("Filtros")
biomas = sorted(df["Bioma"].dropna().unique())
biomas_sel = st.sidebar.multiselect(
    "Bioma", biomas, default=["Amazônia"] if "Amazônia" in biomas else biomas
)
so_ref = st.sidebar.checkbox("Só satélite de referência (AQUA)",
                              value="AQUA_M-T" in df["Satelite"].unique())

d = df[df["Bioma"].isin(biomas_sel)].copy()
if so_ref:
    d = d[d["Satelite"] == "AQUA_M-T"]

anos_disponiveis = sorted(d["ano"].unique())
if len(anos_disponiveis) == 0:
    st.warning("Nenhum foco com esses filtros.")
    st.stop()

ano_atual = max(anos_disponiveis)
ano_anterior = ano_atual - 1

# Comparação justa: mesmo intervalo de dia/mês em todos os anos
ultima = d[d["ano"] == ano_atual]["DataHora"].max()
d["md"] = d["DataHora"].dt.month * 100 + d["DataHora"].dt.day
periodo = d[d["md"] <= ultima.month * 100 + ultima.day]

df_atual = periodo[periodo["ano"] == ano_atual]
df_anterior = periodo[periodo["ano"] == ano_anterior]

total_atual = len(df_atual)
total_anterior = len(df_anterior)
variacao = ((total_atual - total_anterior) / total_anterior * 100) if total_anterior else None

ranking = (
    df_atual.groupby(["Estado", "estado_chave"]).size()
    .reset_index(name="focos").sort_values("focos", ascending=False)
)
ranking["pct"] = (ranking["focos"] / ranking["focos"].sum() * 100).round(1)
estado_top = ranking.iloc[0]

# ---------------------------------------------------------
# CABEÇALHO
# ---------------------------------------------------------
st.markdown(f"""
# Focos de Calor no Brasil
##### Monitoramento de queimadas e incêndios florestais &nbsp;·&nbsp;
Dados: INPE / Queimadas (Terra Brasilis) &nbsp;·&nbsp; Período: {ano_atual}
(comparativo com {ano_anterior}, até {ultima:%d/%m})
""")
st.divider()

# ---------------------------------------------------------
# 1. VISÃO GERAL
# ---------------------------------------------------------
st.subheader("1. Visão geral")
c1, c2, c3 = st.columns(3)
c1.metric(f"Total de focos em {ano_atual}", f"{total_atual:,}".replace(",", "."),
          help=f"Período: 01/01 a {ultima:%d/%m}")
if variacao is not None:
    c2.metric(f"Variação vs. {ano_anterior}", f"{variacao:+.1f}%")
else:
    c2.metric(f"Variação vs. {ano_anterior}", "sem dados")
c3.metric("Estado com mais focos", f"{estado_top['Estado']} ({estado_top['pct']}%)")

st.divider()

# ---------------------------------------------------------
# 2. MAPA  +  3. RANKING
# ---------------------------------------------------------
col_mapa, col_rank = st.columns([3, 2])

with col_mapa:
    st.subheader("2. Mapa por estado")
    try:
        fig = px.choropleth(
            ranking, geojson=carregar_geojson(), locations="estado_chave",
            featureidkey="properties.chave", color="focos",
            color_continuous_scale=ESCALA_CORES,
            hover_name="Estado", hover_data={"estado_chave": False, "focos": True},
        )
        fig.update_geos(fitbounds="locations", visible=False)
        st.plotly_chart(estilizar(fig, 420), width="stretch")
    except Exception as e:
        st.warning(f"Não foi possível carregar o mapa: {e}")

    st.caption("**Top 5 estados**")
    for i, row in ranking.head(5).reset_index(drop=True).iterrows():
        st.markdown(f"**{i+1}. {row['Estado']}** — {row['focos']:,} focos ({row['pct']}%)"
                    .replace(",", "."))

with col_rank:
    st.subheader("3. Ranking por estado")
    top = ranking.head(10).sort_values("focos")
    fig = px.bar(top, x="focos", y="Estado", orientation="h", text="focos",
                 color="focos", color_continuous_scale=ESCALA_CORES)
    fig.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title=None)
    fig.update_traces(textposition="outside")
    st.plotly_chart(estilizar(fig, 480), width="stretch")

st.divider()

# ---------------------------------------------------------
# 4. EVOLUÇÃO 2025 vs 2026
# ---------------------------------------------------------
st.subheader(f"4. Evolução mensal: {ano_anterior} vs {ano_atual}")
mensal = periodo[periodo["ano"].isin([ano_anterior, ano_atual])]
mensal = mensal.groupby(["ano", "mes"]).size().reset_index(name="focos")

fig = go.Figure()
cores = {ano_anterior: COR_2025, ano_atual: COR_2026}
for ano in [ano_anterior, ano_atual]:
    sub = mensal[mensal["ano"] == ano].sort_values("mes")
    fig.add_trace(go.Scatter(
        x=[MESES[m - 1] for m in sub["mes"]], y=sub["focos"],
        mode="lines+markers", name=str(ano),
        line=dict(color=cores.get(ano, "#8a99c5"), width=3),
    ))
st.plotly_chart(estilizar(fig, 380), width="stretch")

st.divider()

# ---------------------------------------------------------
# 5. O QUE OS DADOS MOSTRAM
# ---------------------------------------------------------
st.subheader("5. O que os dados mostram")

top3 = ranking.head(3)
pct_top3 = top3["pct"].sum().round(1)
variacao_txt = (f"alta de {variacao:.1f}%" if variacao and variacao >= 0
                else f"queda de {abs(variacao):.1f}%" if variacao else "sem comparação disponível")

st.markdown(f"""
<div class="insight-box">
<ul>
<li>{ano_atual} registra <b>{total_atual:,}</b> focos de calor até {ultima:%d/%m}, uma
<b>{variacao_txt}</b> em relação ao mesmo período de {ano_anterior}.</li>
<li><b>{top3.iloc[0]['Estado']}, {top3.iloc[1]['Estado']} e {top3.iloc[2]['Estado']}</b>
concentram <b>{pct_top3}%</b> de todos os focos do período.</li>
<li>O bioma monitorado é <b>{", ".join(biomas_sel)}</b>
{"— fase mais crítica costuma ser agosto a outubro, período de seca." if "Amazônia" in biomas_sel else ""}</li>
</ul>
</div>
""".replace(",", "."), unsafe_allow_html=True)

with st.expander("Ver amostra dos dados"):
    st.dataframe(df_atual.drop(columns=["md", "estado_chave"]).head(200))
