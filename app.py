import streamlit as st
import requests
import pandas as pd
import json
from io import StringIO
import geopandas as gpd
import matplotlib.pyplot as plt

# ---------- CONSTANTS ----------
STATISTIKAAMETI_API_URL = "https://andmed.stat.ee/api/v1/et/stat/RV032"
GEOJSON_PATH = "maakonnad.geojson"

# API payload – years 2014–2023, all counties, both sexes
JSON_PAYLOAD_STR = """{
  "query": [
    {
      "code": "Aasta",
      "selection": {
        "filter": "item",
        "values": [
          "2014", "2015", "2016", "2017", "2018",
          "2019", "2020", "2021", "2022", "2023"
        ]
      }
    },
    {
      "code": "Maakond",
      "selection": {
        "filter": "item",
        "values": [
          "39", "44", "49", "51", "57", "59", "65",
          "67", "70", "74", "78", "82", "84", "86", "37"
        ]
      }
    },
    {
      "code": "Sugu",
      "selection": {
        "filter": "item",
        "values": ["2", "3"]
      }
    }
  ],
  "response": {
    "format": "csv"
  }
}"""

# ---------- DATA LOADING (CACHED) ----------
@st.cache_data
def load_data():
    """Fetch data from Statistics Estonia API and return as pandas DataFrame."""
    headers = {'Content-Type': 'application/json'}
    payload = json.loads(JSON_PAYLOAD_STR)
    response = requests.post(STATISTIKAAMETI_API_URL, json=payload, headers=headers)
    if response.status_code != 200:
        st.error(f"API error: {response.status_code}")
        st.stop()
    text = response.content.decode('utf-8-sig')
    df = pd.read_csv(StringIO(text))
    return df

@st.cache_data
def load_geojson():
    """Load Estonian county GeoJSON."""
    return gpd.read_file(GEOJSON_PATH)

# ⚠️ NO @st.cache_data HERE – that was the problem!
def prepare_data(df, gdf):
    """Merge demographic data with geometry, compute total natural increase."""
    merged = gdf.merge(df, left_on='MNIMI', right_on='Maakond')
    merged["Loomulik iive"] = merged["Mehed Loomulik iive"] + merged["Naised Loomulik iive"]
    return merged

# ---------- HELPER FUNCTIONS ----------
def plot_static_map(gdf_year, year, metric_col, metric_name):
    """Create a static matplotlib choropleth map."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    gdf_year.plot(column=metric_col,
                  ax=ax,
                  legend=True,
                  cmap='viridis',
                  legend_kwds={'label': metric_name, 'shrink': 0.6})
    ax.set_title(f'{metric_name} maakonniti - {year}')
    ax.axis('off')
    plt.tight_layout()
    return fig

def get_metric_columns():
    """Return available demographic metrics for selection."""
    return {
        "Loomulik iive (kokku)": "Loomulik iive",
        "Mehed – loomulik iive": "Mehed Loomulik iive",
        "Naised – loomulik iive": "Naised Loomulik iive",
    }

# ---------- MAIN APP ----------
def main():
    st.set_page_config(page_title="Eesti rahvastiku loomulik iive", layout="wide")
    st.title("📊 Eesti rahvastiku loomulik iive maakonniti")
    st.markdown("Allikas: [Statistikaamet](https://andmed.stat.ee/) (RV032)")

    # Load data
    with st.spinner("Laen andmeid..."):
        df = load_data()
        gdf = load_geojson()
        merged = prepare_data(df, gdf)   # ← no caching here

    years = sorted(merged['Aasta'].unique())
    metric_dict = get_metric_columns()
    metric_names = list(metric_dict.keys())

    st.sidebar.header("⚙️ Valikud")
    selected_metric_name = st.sidebar.selectbox("Näitaja", metric_names, index=0)
    selected_metric_col = metric_dict[selected_metric_name]

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🗺️ Kaart", "📈 Trend", "🔄 Võrdle aastaid", "🏆 Edetabel", "ℹ️ Info"
    ])

    with tab1:
        st.subheader("Loomulik iive – kaart")
        map_year = st.select_slider("Vali aasta", options=years, value=years[-1])
        map_data = merged[merged['Aasta'] == map_year].copy()
        fig = plot_static_map(map_data, map_year, selected_metric_col, selected_metric_name)
        st.pyplot(fig)

    with tab2:
        st.subheader("Aegrea analüüs")
        col1, col2 = st.columns(2)
        with col1:
            counties = sorted(merged['MNIMI'].unique())
            selected_county = st.selectbox("Vali maakond", counties)
        with col2:
            trend_metric = st.selectbox("Vali näitaja", metric_names, index=metric_names.index(selected_metric_name))

        trend_data = merged[merged['MNIMI'] == selected_county].sort_values('Aasta')
        trend_col = metric_dict[trend_metric]
        st.subheader(f"{trend_metric} - {selected_county}")
        st.line_chart(trend_data.set_index('Aasta')[trend_col])
        st.dataframe(trend_data[['Aasta', trend_col]].set_index('Aasta'))

    with tab3:
        st.subheader("Aastate võrdlus")
        col1, col2 = st.columns(2)
        with col1:
            year1 = st.selectbox("Esimene aasta", years, index=years.index(2019) if 2019 in years else 0)
        with col2:
            year2 = st.selectbox("Teine aasta", years, index=years.index(2023) if 2023 in years else len(years)-1)

        data1 = merged[merged['Aasta'] == year1][['MNIMI', selected_metric_col]].rename(
            columns={selected_metric_col: f'val_{year1}'}
        )
        data2 = merged[merged['Aasta'] == year2][['MNIMI', selected_metric_col]].rename(
            columns={selected_metric_col: f'val_{year2}'}
        )
        scatter_df = pd.merge(data1, data2, on='MNIMI').set_index('MNIMI')
        st.subheader(f"{selected_metric_name}: {year1} vs {year2}")
        st.scatter_chart(scatter_df, x=f'val_{year1}', y=f'val_{year2}')
        scatter_df['Muutus'] = scatter_df[f'val_{year2}'] - scatter_df[f'val_{year1}']
        st.dataframe(scatter_df.sort_values('Muutus', ascending=False))

    with tab4:
        st.subheader("Maakondade edetabel")
        rank_year = st.selectbox("Vali aasta edetabeli jaoks", years, index=len(years)-1, key="rank_year")
        rank_data = merged[merged['Aasta'] == rank_year][['MNIMI', 'Mehed Loomulik iive', 'Naised Loomulik iive', 'Loomulik iive']]
        rank_data = rank_data.sort_values('Loomulik iive', ascending=False)
        filter_counties = st.multiselect("Filtreeri maakondi", options=rank_data['MNIMI'].unique(), default=[])
        if filter_counties:
            rank_data = rank_data[rank_data['MNIMI'].isin(filter_counties)]
        st.dataframe(
            rank_data.set_index('MNIMI').style.format("{:.0f}"),
            use_container_width=True,
            column_config={
                "Mehed Loomulik iive": st.column_config.NumberColumn("Mehed"),
                "Naised Loomulik iive": st.column_config.NumberColumn("Naised"),
                "Loomulik iive": st.column_config.NumberColumn("Kokku"),
            }
        )

    with tab5:
        st.subheader("Andmete selgitus")
        st.markdown("""
        **Näitaja:** Loomulik iive = sündide ja surmade vahe (mehed + naised).  
        **Allikas:** Statistikaameti andmebaas (RV032 – Sündinud, surnud ja loomulik iive maakonna järgi).  
        **GeoJSON:** Eesti maakondade piirid (avaldatud vabas kasutuses).  

        **Funktsionaalsus:**  
        - **Kaart:** staatiline koropleetkaart aasta kaupa (matplotlib).  
        - **Trend:** joondiagramm ühe maakonna aegrea kohta.  
        - **Võrdlus:** hajuvusdiagramm kahe aasta vaheliste muutuste visualiseerimiseks.  
        - **Edetabel:** sorteeritav tabel, võimalus filtreerida maakondi.  

        Rakendus laeb automaatselt uusimad andmed Statistikaameti API-st.
        """)

if __name__ == "__main__":
    main()