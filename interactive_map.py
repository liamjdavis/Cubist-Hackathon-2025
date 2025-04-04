import streamlit as st
import pandas as pd
import folium
from folium import plugins
import numpy as np
from datetime import datetime
from streamlit_folium import st_folium

# Define the coordinates for each entry point
ENTRY_POINTS = {
    'Queensboro Bridge': [40.7561, -73.9525],
    'Queens-Midtown Tunnel': [40.7527, -73.9675],
    'Williamsburg Bridge': [40.7127, -73.9707],
    'Manhattan Bridge': [40.7074, -73.9891],
    'Brooklyn Bridge': [40.7061, -73.9969],
    'Hugh Carey Tunnel': [40.7007, -74.0178],
    'Holland Tunnel': [40.7282, -74.0287],
    'Lincoln Tunnel': [40.7614, -73.9536],
    'FDR Drive at 60th Street': [40.7614, -73.9536],
    'East 60th Street': [40.7614, -73.9536],
    'West 60th Street': [40.7714, -73.9836]
}

def load_data():
    """Load and preprocess the data"""
    df = pd.read_csv('MTA.csv')
    df['Toll Date'] = pd.to_datetime(df['Toll Date'])
    return df

def filter_data(df, vehicle_class, time_period, day_of_week, peak_time):
    """Filter the data based on user selections"""
    filtered_df = df.copy()
    
    if vehicle_class != 'All':
        filtered_df = filtered_df[filtered_df['Vehicle Class'] == vehicle_class]
    
    if time_period != 'All':
        filtered_df = filtered_df[filtered_df['Time Period'] == time_period]
    
    if day_of_week != 'All':
        filtered_df = filtered_df[filtered_df['Day of Week'] == day_of_week]
    
    if peak_time:
        filtered_df = filtered_df[filtered_df['Time Period'].isin(['AM Peak', 'PM Peak'])]
    
    return filtered_df

def create_map(filtered_df, entry_type):
    """Create an interactive map with the filtered data"""
    # Calculate the center of NYC
    center_lat = 40.7128
    center_lon = -74.0060
    
    # Create base map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    
    # Add a layer control
    layer_control = folium.LayerControl()
    
    # Calculate max value for normalization
    if entry_type == 'CRZ Entries':
        max_value = filtered_df['CRZ Entries'].max()
    else:
        max_value = filtered_df['Excluded Roadway Entries'].max()
    
    # Add markers for each entry point
    for entry_point, coords in ENTRY_POINTS.items():
        # Filter data for this entry point
        point_data = filtered_df[filtered_df['Detection Region'] == entry_point]
        
        if not point_data.empty:
            # Calculate total entries
            if entry_type == 'CRZ Entries':
                total_entries = point_data['CRZ Entries'].sum()
            else:
                total_entries = point_data['Excluded Roadway Entries'].sum()
            
            # Calculate color based on congestion level
            color = get_color(total_entries, max_value)
            
            # Create popup content
            popup_content = f"""
            <b>{entry_point}</b><br>
            Total {entry_type}: {total_entries:,.0f}<br>
            """
            
            # Add marker
            folium.CircleMarker(
                location=coords,
                radius=15,
                popup=popup_content,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7
            ).add_to(m)
            
            # Add label
            folium.map.Marker(
                location=coords,
                icon=folium.DivIcon(
                    html=f'<div style="font-size: 10pt; color: black">{total_entries:,.0f}</div>'
                )
            ).add_to(m)
    
    return m

def get_color(value, max_value):
    """Get color based on congestion level"""
    if value == 0:
        return '#gray'
    elif value < max_value * 0.33:
        return '#green'
    elif value < max_value * 0.66:
        return '#yellow'
    else:
        return '#red'

def main():
    st.title('NYC Congestion Relief Zone Analysis')
    
    try:
        # Load data directly from MTA.csv
        df = load_data()
        
        # Sidebar filters
        st.sidebar.header('Filters')
        
        # Entry type selection
        entry_type = st.sidebar.selectbox(
            'Select Entry Type',
            ['CRZ Entries', 'Excluded Roadway Entries']
        )
        
        # Vehicle class filter
        vehicle_classes = ['All'] + sorted(df['Vehicle Class'].unique().tolist())
        vehicle_class = st.sidebar.selectbox('Vehicle Class', vehicle_classes)
        
        # Time period filter
        time_periods = ['All'] + sorted(df['Time Period'].unique().tolist())
        time_period = st.sidebar.selectbox('Time Period', time_periods)
        
        # Day of week filter
        days = ['All'] + sorted(df['Day of Week'].unique().tolist())
        day_of_week = st.sidebar.selectbox('Day of Week', days)
        
        # Peak time filter
        peak_time = st.sidebar.checkbox('Show only peak times')
        
        # Filter data
        filtered_df = filter_data(df, vehicle_class, time_period, day_of_week, peak_time)
        
        # Create and display map
        m = create_map(filtered_df, entry_type)
        
        # Display the map
        st_folium(m, width=800, height=600)
        
        # Display summary statistics
        st.subheader('Summary Statistics')
        if entry_type == 'CRZ Entries':
            st.write(f"Total CRZ Entries: {filtered_df['CRZ Entries'].sum():,.0f}")
        else:
            st.write(f"Total Excluded Roadway Entries: {filtered_df['Excluded Roadway Entries'].sum():,.0f}")
            
    except Exception as e:
        st.error(f"Error loading the data: {str(e)}")
        st.info("Please make sure MTA.csv is in the same directory as this script.")
