# Eesti rahvastiku loomulik iive – Streamlit Dashboard

Interactive dashboard visualising natural increase (births minus deaths) by Estonian county, 2014–2023.

## Features
- Choropleth map (static Matplotlib)
- Time series trend for any county
- Year‑to‑year comparison scatter plot
- Ranked table with filtering

## Data source
[Statistics Estonia](https://andmed.stat.ee/) – table RV032

## Run locally

1. Clone the repository  
   `git clone https://github.com/itkreenholmi-bit/KU-6`

2. Install dependencies  
   `pip install -r requirements.txt`

3. Run the app  
   `streamlit run app.py`
