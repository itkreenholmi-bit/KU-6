import streamlit as st
import requests
import pandas as pd
import json
from io import StringIO
import folium
from streamlit_folium import st_folium

# ---------- CONSTANTS ----------
STATISTIKAAMETI_API_URL = "https://andmed.stat.ee/api/v1/et/stat/RV032"
GEOJSON_PATH = "maakonnad.geojson"

# API payload (same as before)
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

@st.cache_data
def load_data():
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
    """Load GeoJSON as a Python dict (no geopandas)."""
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def prepare_data(df):
    """Compute total natural increase and pivot for easy lookup."""
    df["Loomulik iive"] = df["Mehed Loomulik iive"] + df["Naised Loomulik iive"]
    return df

def create_map(geojson_data, year_data, metric_col, metric_name, year):
    """Create a folium choropleth map."""
    # Create base map centered on Estonia
    m = folium.Map(location=[58.6, 25.0], zoom_start=7, tiles="CartoDB positron")
    
    # Add choropleth layer
    folium.Choropleth(
        geo_data=geojson_data,
        name="choropleth",
        data=year_data,
        columns=["Maakond", metric_col],
        key_on="feature.properties.MNIMI",  # adjust to your GeoJSON property name
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f"{metric_name} ({year})",
        highlight=True,
    ).add_to(m)
    
    # Add tooltips
    folium.GeoJson(
        geojson_data,
        style_function=lambda x: {"fillOpacity": 0, "weight": 0.5},
        tooltip=folium.GeoJsonTooltip(
            fields=["MNIMI"],
            aliases=["Maakond:"],
            localize=True,
            sticky=False,
            labels=True,
        ),
    ).add_to(m)
    
    return m

def main():
    st.set_page_config(page_title="Eesti rahvastiku loomulik iive", layout="wide")
    st.title("📊 Eesti rahvastiku loomulik iive maakonniti")
    st.markdown("Allikas: [Statistikaamet](https://andmed.stat.ee/) (RV032)")
    
    with st.spinner("Laen andmeid..."):
        df = load_data()
        geojson_data = load_geojson()
        df = prepare_data(df)
    
    years = sorted(df['Aasta'].unique())
    metric_dict = {
        "Loomulik iive (kokku)": "Loomulik iive",
        "Mehed – loomulik iive": "Mehed Loomulik iive",
        "Naised – loomulik iive": "Naised Loomulik iive",
    }
    metric_names = list(metric_dict.keys())
    
    st.sidebar.header("⚙️ Valikud")
    selected_metric_name = st.sidebar.selectbox("Näitaja", metric_names, index=0)
    selected_metric_col = metric_dict[selected_metric_name]
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🗺️ Kaart", "📈 Trend", "🔄 Võrdle aastaid", "🏆 Edetabel", "ℹ️ Info"
    ])
    
    with tab1:
        st.subheader("Loomulik iive – interaktiivne kaart")
        map_year = st.select_slider("Vali aasta", options=years, value=years[-1])
        year_data = df[df['Aasta'] == map_year]
        
        m = create_map(geojson_data, year_data, selected_metric_col, selected_metric_name, map_year)
        st_folium(m, width=700, height=500)
    
    with tab2:
        st.subheader("Aegrea analüüs")
        col1, col2 = st.columns(2)
        with col1:
            counties = sorted(df['MNIMI'].unique())
            selected_county = st.selectbox("Vali maakond", counties)
        with col2:
            trend_metric = st.selectbox("Vali näitaja", metric_names, index=metric_names.index(selected_metric_name))
        
        trend_data = df[df['MNIMI'] == selected_county].sort_values('Aasta')
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
        
        data1 = df[df['Aasta'] == year1][['MNIMI', selected_metric_col]].rename(columns={selected_metric_col: f'val_{year1}'})
        data2 = df[df['Aasta'] == year2][['MNIMI', selected_metric_col]].rename(columns={selected_metric_col: f'val_{year2}'})
        scatter_df = pd.merge(data1, data2, on='MNIMI').set_index('MNIMI')
        st.subheader(f"{selected_metric_name}: {year1} vs {year2}")
        st.scatter_chart(scatter_df, x=f'val_{year1}', y=f'val_{year2}')
        scatter_df['Muutus'] = scatter_df[f'val_{year2}'] - scatter_df[f'val_{year1}']
        st.dataframe(scatter_df.sort_values('Muutus', ascending=False))
    
    with tab4:
        st.subheader("Maakondade edetabel")
        rank_year = st.selectbox("Vali aasta edetabeli jaoks", years, index=len(years)-1, key="rank_year")
        rank_data = df[df['Aasta'] == rank_year][['MNIMI', 'Mehed Loomulik iive', 'Naised Loomulik iive', 'Loomulik iive']]
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
        **Allikas:** Statistikaameti andmebaas (RV032).  
        **Kaart:** Interaktiivne Folium kaart, mis ei vaja geopandaseid ega GDAL-i.  
        **Funktsionaalsus:** trendid, võrdlused, edetabelid.
        """)

if __name__ == "__main__":
    main()
