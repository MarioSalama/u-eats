"""
NYC Food Delivery Market Opportunity — Streamlit Dashboard
Run: streamlit run dashboard.py
"""
import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import json
import base64
from pathlib import Path

st.set_page_config(
    page_title="NYC Food Delivery Market",
    page_icon="🍕",
    layout="wide",
)

# ── Uber Eats brand styling ────────────────────────────────────────────────────
UE_GREEN  = "#06C167"
UE_BLACK  = "#000000"
UE_WHITE  = "#FFFFFF"

FONT_DIR = Path(__file__).parent / "fonts"
def _font_b64(path):
    return base64.b64encode(path.read_bytes()).decode()

_css_fonts = ""
for weight, fname in [("400", "UberMove-Regular.ttf"), ("500", "UberMove-Medium.ttf"), ("700", "UberMove-Bold.ttf")]:
    fp = FONT_DIR / fname
    if fp.exists():
        _css_fonts += f"""
        @font-face {{
            font-family: 'UberMove';
            font-weight: {weight};
            src: url(data:font/truetype;base64,{_font_b64(fp)}) format('truetype');
        }}"""

st.markdown(f"""
<style>
{_css_fonts}

html, body, [class*="css"] {{
    font-family: 'UberMove', sans-serif !important;
}}
h1, h2, h3, h4 {{
    font-family: 'UberMove', sans-serif !important;
    font-weight: 700;
    color: {UE_BLACK} !important;
}}
/* Sidebar */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {{
    background-color: {UE_BLACK} !important;
}}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] .stMarkdown {{
    color: {UE_WHITE} !important;
    font-family: 'UberMove', sans-serif !important;
}}
section[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {{
    background-color: {UE_GREEN} !important;
}}
section[data-testid="stSidebar"] [data-baseweb="slider"] div[style*="background"] {{
    background-color: {UE_GREEN} !important;
}}
section[data-testid="stSidebar"] input[type="number"] {{
    background-color: #1a1a1a !important;
    color: {UE_WHITE} !important;
    border-color: {UE_GREEN} !important;
    font-family: 'UberMove', sans-serif !important;
}}
/* Metric cards */
[data-testid="metric-container"] {{
    background-color: {UE_BLACK};
    border-radius: 8px;
    padding: 16px;
}}
[data-testid="metric-container"] label,
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    color: {UE_WHITE} !important;
    font-family: 'UberMove', sans-serif !important;
}}
[data-testid="stMetricValue"] {{
    color: {UE_GREEN} !important;
    font-weight: 700;
}}
hr {{ border-color: {UE_GREEN}; }}
/* Hide sidebar collapse button */
button[data-testid="stSidebarCollapseButton"],
button[kind="header"],
[data-testid="stSidebarCollapseButton"],
section[data-testid="stSidebar"] button:first-of-type {{
    display: none !important;
    visibility: hidden !important;
}}
</style>
""", unsafe_allow_html=True)

UE_BOROUGH_COLORS = {
    "Brooklyn":     UE_GREEN,    # Uber Eats green — primary brand
    "Manhattan":    "#5B8DB8",   # steel blue
    "Queens":       "#E8A838",   # warm amber
    "Bronx":        "#A67DB8",   # soft purple
    "Staten Island":"#E07B5B",   # terracotta
}

DATA_DIR  = Path(__file__).parent / "data"
REST_CSV  = DATA_DIR / "Open_Restaurants_Inspections_20260611.csv"
CENSUS_CSV= DATA_DIR / "DECENNIALDHC2020.P1-Data.csv"
# SHP_PATH  = DATA_DIR / "tl_2020_us_zcta520" / "tl_2020_us_zcta520.shp"
SHP_PATH   = DATA_DIR / "tl_2020_us_zcta520_nyc" / "tl_2020_us_zcta520_nyc.shp"

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Model Assumptions")

st.sidebar.markdown("**Base spend (Statista 2025)**")
base_spend_input = st.sidebar.number_input(
    "Annual spend per capita (USD)", min_value=200, max_value=1000, value=560, step=10,
    help="Average annual food delivery spend per user in the US — Statista 2025"
)

st.sidebar.markdown("**NYC cost-of-living premium (C2ER / PayScale)**")
nyc_mult = st.sidebar.slider(
    "NYC Premium Multiplier", 1.0, 1.8, 1.39, 0.01,
    help="NYC cost of living vs US average. Source: PayScale C2ER index → 139% higher"
)

st.sidebar.markdown("**Online penetration rate (Deliverect 2024)**")
pen_rate = st.sidebar.slider(
    "Base Penetration Rate", 0.30, 1.0, 0.70, 0.05,
    help="Share of population that orders food delivery online. Source: Deliverect 2024 — 70%"
)

st.sidebar.markdown("**Borough penetration adjustment** *(income-indexed, Census Reporter ACS)*")
adj_manhattan     = st.sidebar.slider("Manhattan adj.",     0.5, 2.0, 1.31, 0.01)
adj_brooklyn      = st.sidebar.slider("Brooklyn adj.",      0.5, 2.0, 1.00, 0.01)
adj_queens        = st.sidebar.slider("Queens adj.",        0.5, 2.0, 1.05, 0.01)
adj_bronx         = st.sidebar.slider("Bronx adj.",         0.5, 2.0, 0.57, 0.01)
adj_staten_island = st.sidebar.slider("Staten Island adj.", 0.5, 2.0, 1.21, 0.01)

st.sidebar.markdown("**Restaurant density bonus cap**")
density_cap = st.sidebar.slider(
    "Density multiplier cap", 0.0, 0.60, 0.30, 0.05,
    help="Max uplift from restaurant density. 0 = no bonus, 0.30 = up to 30% more for densest ZIP"
)

st.sidebar.markdown("---")
top_n = st.sidebar.slider("Show Top N ZIP Codes", 10, 50, 20, 5)


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data
def load_raw():
    rest_raw = pd.read_csv(REST_CSV, dtype=str)
    rest_raw.columns = rest_raw.columns.str.strip()
    rest_raw["RestaurantName"]  = rest_raw["RestaurantName"].str.strip()
    rest_raw["BusinessAddress"] = rest_raw["BusinessAddress"].str.strip()
    rest_raw["Borough"]         = rest_raw["Borough"].str.strip()
    rest_raw["Postcode"]        = rest_raw["Postcode"].astype(str).str.strip().str.zfill(5)
    rest_raw = rest_raw[rest_raw["Postcode"].str.match(r"^\d{5}$")]

    zip_rest = (
        rest_raw.drop_duplicates(subset=["Postcode", "RestaurantName", "BusinessAddress"])
        .groupby("Postcode")
        .agg(
            unique_restaurants=("RestaurantName", "count"),
            borough=("Borough", lambda x: x.mode()[0]),
        )
        .reset_index()
    )

    pop_raw = pd.read_csv(CENSUS_CSV, dtype=str, encoding="utf-8-sig", skiprows=[1])
    pop_raw["zip"]        = pop_raw["NAME"].str.replace("ZCTA5 ", "", regex=False).str.strip().str.zfill(5)
    pop_raw["population"] = pd.to_numeric(pop_raw["P1_001N"], errors="coerce")
    pop = pop_raw[["zip", "population"]].dropna()

    df = zip_rest.merge(pop, left_on="Postcode", right_on="zip", how="left")
    df = df[df["unique_restaurants"] >= 5].copy()
    return df


@st.cache_data
def load_geo(postcodes):
    gdf = gpd.read_file(SHP_PATH)
    gdf = gdf[gdf["ZCTA5CE20"].isin(postcodes)].copy()
    gdf = gdf.to_crs("EPSG:4326").rename(columns={"ZCTA5CE20": "Postcode"})
    return gdf[["Postcode", "geometry"]]


def compute_market(df_raw, base_spend_input, nyc_mult, pen_rate,
                   adj_manhattan, adj_brooklyn, adj_queens, adj_bronx, adj_staten_island,
                   density_cap):
    df = df_raw.copy()
    borough_adj = {
        "Manhattan":    adj_manhattan,
        "Brooklyn":     adj_brooklyn,
        "Queens":       adj_queens,
        "Bronx":        adj_bronx,
        "Staten Island": adj_staten_island,
    }
    df["penetration_adj"]       = df["borough"].map(borough_adj).fillna(1.0)
    df["effective_penetration"] = pen_rate * df["penetration_adj"]
    df["density_score"]         = df["unique_restaurants"] / df["unique_restaurants"].max()
    df["density_multiplier"]    = 1.0 + density_cap * df["density_score"]
    base_spend = base_spend_input * nyc_mult
    df["annual_market_usd"] = (
        df["population"] * df["effective_penetration"] * base_spend * df["density_multiplier"]
    ).fillna(0).round(0).astype(int)
    df["rank"] = df["annual_market_usd"].rank(ascending=False, method="min").astype(int)
    return df.sort_values("rank").reset_index(drop=True)


# ── Compute ────────────────────────────────────────────────────────────────────
df_raw = load_raw()
df = compute_market(
    df_raw, base_spend_input, nyc_mult, pen_rate,
    adj_manhattan, adj_brooklyn, adj_queens, adj_bronx, adj_staten_island,
    density_cap,
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🍕 NYC Food Delivery Market Opportunity")
st.caption(
    "Estimated annual online food delivery market ($) by ZIP code · "
    "2020 Census + NYC DOT Restaurant Inspections · "
    "Assumptions: Statista 2025, Deliverect 2024, Census Reporter ACS, C2ER PayScale"
)

# ── KPIs ───────────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total NYC Market",    f"${df['annual_market_usd'].sum()/1e9:.2f}B")
k2.metric("ZIP Codes Analyzed",  f"{len(df)}")
k3.metric("Unique Restaurants",  f"{df['unique_restaurants'].sum():,}")
k4.metric("Median Market / ZIP", f"${df['annual_market_usd'].median()/1e6:.1f}M")
k5.metric("Spend / Active User", f"${base_spend_input * nyc_mult:,.0f}/yr")

st.markdown("---")

# ── Map + Table ────────────────────────────────────────────────────────────────
col_map, col_table = st.columns([3, 2])

with col_map:
    st.subheader("Market Opportunity Map")
    geo = load_geo(df["Postcode"].tolist())
    geo_merged = geo.merge(df, on="Postcode")
    geojson = json.loads(geo_merged.to_json())

    fig_map = px.choropleth_map(
        geo_merged,
        geojson=geojson,
        locations=geo_merged.index,
        color="annual_market_usd",
        hover_name="Postcode",
        hover_data={
            "borough": True,
            "population": ":,",
            "unique_restaurants": True,
            "annual_market_usd": ":,",
            "rank": True,
        },
        color_continuous_scale=[[0, "#FFFBCC"], [0.4, "#FEB24C"], [0.75, "#F03B20"], [1.0, "#BD0026"]],
        map_style="carto-positron",
        center={"lat": 40.7128, "lon": -74.006},
        zoom=9,
        labels={"annual_market_usd": "Annual Market ($)"},
    )
    fig_map.update_layout(
        margin={"r": 0, "t": 10, "l": 0, "b": 0},
        height=500,
        coloraxis_colorbar=dict(title="$ Annual"),
        font=dict(family="UberMove, sans-serif"),
    )
    st.plotly_chart(fig_map, use_container_width=True)

with col_table:
    st.subheader(f"Top {top_n} ZIP Codes")
    display_cols = ["rank", "Postcode", "borough", "population", "unique_restaurants", "annual_market_usd"]
    top_df = df[display_cols].head(top_n).copy()
    top_df["annual_market_usd"] = top_df["annual_market_usd"].apply(lambda x: f"${x:,.0f}")
    top_df["population"]        = top_df["population"].apply(lambda x: f"{int(x):,}")
    top_df.columns = ["Rank", "ZIP", "Borough", "Population", "Restaurants", "Est. Market ($)"]
    st.dataframe(top_df, use_container_width=True, hide_index=True)

# ── Borough breakdown ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Borough Breakdown")

borough_summary = (
    df.groupby("borough")
    .agg(
        total_market=("annual_market_usd", "sum"),
        zip_count=("Postcode", "count"),
        total_population=("population", "sum"),
        avg_restaurants=("unique_restaurants", "mean"),
    )
    .sort_values("total_market", ascending=False)
    .reset_index()
)
borough_summary["market_share_pct"] = (
    100 * borough_summary["total_market"] / borough_summary["total_market"].sum()
).round(1)

b1, b2 = st.columns(2)

with b1:
    fig_pie = px.pie(
        borough_summary, values="total_market", names="borough",
        title="Market Share by Borough",
        color="borough",
        color_discrete_map=UE_BOROUGH_COLORS,
    )
    fig_pie.update_layout(font=dict(family="UberMove, sans-serif"))
    st.plotly_chart(fig_pie, use_container_width=True)

with b2:
    fig_bar = px.bar(
        borough_summary, x="borough", y="total_market", color="borough",
        title="Total Market by Borough ($)",
        color_discrete_map=UE_BOROUGH_COLORS,
        labels={"total_market": "Annual Market ($)", "borough": "Borough"},
    )
    fig_bar.update_layout(showlegend=False, font=dict(family="UberMove, sans-serif"))
    st.plotly_chart(fig_bar, use_container_width=True)

st.dataframe(
    borough_summary.rename(columns={
        "borough": "Borough", "total_market": "Total Market ($)",
        "zip_count": "ZIP Codes", "total_population": "Population",
        "avg_restaurants": "Avg Restaurants/ZIP", "market_share_pct": "Market Share (%)",
    }).style.format({
        "Total Market ($)": "${:,.0f}",
        "Population": "{:,.0f}",
        "Avg Restaurants/ZIP": "{:.1f}",
    }),
    use_container_width=True, hide_index=True,
)

# ── Scatter ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Population × Restaurant Density → Market Size")
fig_scatter = px.scatter(
    df,
    x="population", y="annual_market_usd",
    size="unique_restaurants", color="borough",
    hover_name="Postcode",
    log_x=True,
    title="ZIP Code Market Size vs. Population (bubble = restaurant count)",
    labels={
        "population": "Population (log scale)",
        "annual_market_usd": "Annual Market ($)",
        "unique_restaurants": "# Restaurants",
    },
    color_discrete_map=UE_BOROUGH_COLORS,
)
fig_scatter.update_layout(font=dict(family="UberMove, sans-serif"))
st.plotly_chart(fig_scatter, use_container_width=True)

# ── Sensitivity analysis ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Sensitivity: Rank Stability Across Density Multiplier Scenarios")

sens_results = {}
base_spend_sens = base_spend_input * nyc_mult
for scenario, cap in [("No density bonus", 0.0), ("Base (30%)", 0.30), ("High (50%)", 0.50)]:
    d = df.copy()
    d["density_multiplier"] = 1.0 + cap * d["density_score"]
    d["annual_market_usd"] = (
        d["population"] * d["effective_penetration"] * base_spend_sens * d["density_multiplier"]
    ).round(0).astype(int)
    d["rank"] = d["annual_market_usd"].rank(ascending=False, method="min").astype(int)
    sens_results[scenario] = d.set_index("Postcode")["rank"]

sens = pd.DataFrame(sens_results).sort_values("Base (30%)")
sens["rank_shift"] = (sens["No density bonus"] - sens["High (50%)"]).abs()
sens = sens.reset_index()

st.caption(
    "Rank shift = absolute difference in rank between 'No density bonus' and 'High (50%)' scenarios. "
    "ZIPs with shift = 0 are robust regardless of how much weight restaurant density carries."
)
st.dataframe(
    sens.head(20).style.apply(
        lambda col: [
            f"background-color: {'#06C167' if v == 0 else '#FFD700' if v <= 2 else '#FF8C00' if v <= 4 else '#FF4500'}; color: #000"
            for v in col
        ],
        subset=["rank_shift"]
    ),
    use_container_width=True, hide_index=True,
)

# ── Download ───────────────────────────────────────────────────────────────────
st.markdown("---")
csv = df.to_csv(index=False).encode()
st.download_button("⬇️ Download full ranked table (CSV)", csv, "nyc_food_delivery_market.csv", "text/csv")
