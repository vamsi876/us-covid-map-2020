import folium
import pandas as pd
import json
import requests
import os

# Download US counties GeoJSON data
counties_geojson_url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
counties_geojson = requests.get(counties_geojson_url).json()

# Function to get county centroid from GeoJSON
def get_county_centroid(fips, geojson_data):
    for feature in geojson_data['features']:
        if feature['id'] == fips:
            # Get the first coordinate pair as an approximation of the center
            coordinates = feature['geometry']['coordinates']
            if feature['geometry']['type'] == 'Polygon':
                # For single polygon, get the first point
                return coordinates[0][0][1], coordinates[0][0][0]
            elif feature['geometry']['type'] == 'MultiPolygon':
                # For multiple polygons, get the first point of the first polygon
                return coordinates[0][0][0][1], coordinates[0][0][0][0]
    return None, None

# Load and process COVID data
def load_covid_data(csv_path='us-counties.csv'):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found!")
        return None
    
    # Read the CSV file
    print("Loading COVID-19 data...")
    df = pd.read_csv(csv_path)
    
    # Filter for 2020 data and continental US states
    df['date'] = pd.to_datetime(df['date'])
    df_2020 = df[df['date'].dt.year == 2020]
    df_2020 = df_2020[~df_2020['state'].isin(['Alaska', 'Hawaii'])]
    
    # Get the last record for each county in 2020 to get final case count
    print("Processing county data...")
    latest_county_data = df_2020.sort_values('date').groupby('fips').last().reset_index()
    
    # Drop rows with missing FIPS codes
    latest_county_data = latest_county_data.dropna(subset=['fips'])
    
    # Convert FIPS to string and ensure 5 digits with leading zeros
    latest_county_data['fips'] = latest_county_data['fips'].astype(int).astype(str).str.zfill(5)
    
    # Add coordinates for each county
    print("Adding county coordinates...")
    coordinates = []
    for fips in latest_county_data['fips']:
        lat, lon = get_county_centroid(fips, counties_geojson)
        coordinates.append((lat, lon))
    
    latest_county_data['latitude'] = [coord[0] for coord in coordinates]
    latest_county_data['longitude'] = [coord[1] for coord in coordinates]
    
    # Drop rows with missing coordinates
    latest_county_data = latest_county_data.dropna(subset=['latitude', 'longitude'])
    
    return latest_county_data

# Load the COVID data
covid_data = load_covid_data()

if covid_data is None:
    print("Failed to load data. Exiting...")
    exit(1)

print(f"Creating map with {len(covid_data)} counties...")

# Create the base map centered on US with specific bounds
m = folium.Map(
    location=[39.8283, -98.5795],  # Center of continental US
    zoom_start=5,
    tiles='cartodbpositron',
    min_zoom=4,  # Restrict minimum zoom level
    max_bounds=True,  # Restrict panning to bounds
    min_lat=24.396308,  # Continental US bounds
    max_lat=49.384358,
    min_lon=-125.000000,
    max_lon=-66.934570
)

# Add US state boundaries
folium.GeoJson(
    'https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/us-states.json',
    name='States',
    style_function=lambda x: {
        'fillColor': 'transparent',
        'color': 'black',
        'weight': 1,
        'fillOpacity': 0
    }
).add_to(m)

# Create a choropleth layer
choropleth = folium.Choropleth(
    geo_data=counties_geojson,
    name='Counties',
    data=covid_data,
    columns=['fips', 'cases'],
    key_on='feature.id',
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name='Total COVID-19 Cases',
    highlight=True
).add_to(m)

# Add circles for each county with cases
for idx, row in covid_data.iterrows():
    # Calculate circle radius based on number of cases (with log scaling for better visualization)
    radius = (row['cases'] + 1) ** 0.5 * 50  # Reduced scaling factor for better visibility
    
    # Add circle
    folium.Circle(
        location=[row['latitude'], row['longitude']],
        radius=radius,
        color='red',
        fill=True,
        popup=f"<b>{row['county']}, {row['state']}</b><br>Cases: {row['cases']:,}<br>Deaths: {row['deaths']:,}",
        fill_opacity=0.3,
        weight=1
    ).add_to(m)

# Add title
title_html = '''
<div style="position: fixed; 
    top: 20px; left: 50%;
    transform: translateX(-50%);
    background-color: white;
    padding: 10px;
    border-radius: 5px;
    z-index: 1000;
    font-family: Arial;
    font-size: 16px;
    font-weight: bold;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
    Total Number of Covid Cases by County in 2020
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))

# Add layer control
folium.LayerControl().add_to(m)

# Save the map
m.save('covid_map.html')

print("Map has been created as 'covid_map.html'") 