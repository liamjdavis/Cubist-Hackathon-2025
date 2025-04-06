# MTA Congestion Analysis Tool

A comprehensive visualization and analysis tool for monitoring and analyzing traffic patterns in Manhattan's Congestion Pricing Zone. This tool provides both historical analysis and real-time monitoring capabilities to help understand and manage traffic congestion in New York City.

## Features

### Historical Analysis
- **Interactive Dashboard**: View historical traffic patterns and congestion metrics
- **Data Visualization**: Analyze vehicle entries by type at major entry points
- **Time-based Analysis**: Filter and examine data across different time periods
- **Vehicle Type Breakdown**: Detailed analysis of different vehicle categories

### Real-time Monitoring
- **Live Traffic Heatmap**: Real-time visualization of congestion patterns
- **Entry Point Monitoring**: Track vehicle entries at key locations
- **Dynamic Updates**: Data refreshes every few seconds for current conditions
- **Anomaly Detection**: Real-Time and historical anomaly detection


### Map Visualization
- **Interactive Map**: Explore traffic patterns geographically
- **Multiple View Modes**: 
  - Historical view with column-based visualization
  - Live view with heatmap overlay
- **Entry Point Details**: View specific metrics for each congestion zone entry point

## Technical Stack

### Diagram
```mermaid
graph TD
    subgraph Frontend
        UI[User Interface]
        Map[Map Visualization]
        Dashboard[Dashboard]
        Chart[Anomolies Chart]
    end

    subgraph Backend
        Django[Django Server]
        DataProcessor[Data Processor]
        StreamHandler[Stream Handler]
    end

    subgraph Data Sources
        MTA[MTA Data API]
        RT[Real-time Stream]
        DB[(Database)]
    end

    %% Frontend connections
    UI --> Map
    UI --> Dashboard
    UI --> Chart
    Map --> Backend
    Dashboard --> Backend
    Chart --> Backend

    %% Backend connections
    Django --> DataProcessor
    Django --> StreamHandler
    DataProcessor --> DB
    StreamHandler --> RT

    %% Data source connections
    MTA --> DataProcessor
    RT --> StreamHandler
    DB --> DataProcessor
```

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant Django
    participant DataProcessor
    participant StreamHandler
    participant DB
    participant MTA
    participant RT

    %% Historical Data Flow
    User->>UI: Select Date Range
    UI->>Django: Request Historical Data
    Django->>DataProcessor: Process Query
    DataProcessor->>DB: Fetch Data
    DB-->>DataProcessor: Return Data
    DataProcessor-->>Django: Processed Data
    Django-->>UI: JSON Response
    UI->>Map: Update Visualization

    %% Real-time Data Flow
    loop Every 2 Seconds
        StreamHandler->>RT: Request Updates
        RT-->>StreamHandler: New Data
        StreamHandler->>Django: Push Updates
        Django-->>UI: WebSocket Update
        UI->>Map: Update Heatmap
    end

    %% MTA Data Integration
    loop Periodic Updates
        DataProcessor->>MTA: Request New Data
        MTA-->>DataProcessor: Latest Data
        DataProcessor->>DB: Store Updates
    end
```

- **Frontend**:
  - HTML5, CSS3, JavaScript
  - [deck.gl](https://deck.gl/) for interactive map visualizations
  - Bootstrap for responsive UI components
  - Bootstrap Icons for intuitive interface elements

- **Backend**:
  - Python
  - Django web framework
  - Perspective for data analysis
  - Panel for dashboard creation
  - DDSketch

## Data Sources

- MTA Congestion Pricing Data: https://data.ny.gov/Transportation/MTA-Congestion-Relief-Zone-Vehicle-Entries-Beginni/t6yz-b64h/about_data
- NYC Open Data: https://www.511ny.org/list/events/traffic?start=0&length=25&filters%5B0%5D%5Bi%5D=4&filters%5B0%5D%5Bs%5D=Lincoln+Tunnel&order%5Bi%5D=2&order%5Bdir%5D=asc

## Motivation

This tool was developed to address the critical need for data-driven insights in managing Manhattan's Congestion Pricing Zone. By visualizing traffic patterns and congestion metrics, this application enables:

- **Pattern Recognition**: Identify recurring traffic patterns and trends that might otherwise remain hidden in raw data
- **Anomaly Detection**: Quickly spot unusual traffic events or congestion patterns that deviate from historical norms
- **Signal Identification**: Extract meaningful signals from traffic noise to support evidence-based decision making
- **Predictive Analysis**: Use historical patterns and anomalies to anticipate future congestion scenarios
- **Performance Measurement**: Evaluate the effectiveness of congestion pricing policies through quantifiable metrics

The tool serves multiple stakeholders including transportation planners, city officials, researchers, and the general public by transforming complex traffic data into actionable intelligence. By revealing both obvious and subtle patterns in traffic behavior, it provides crucial insights for optimizing traffic flow, reducing congestion, and evaluating the environmental and economic impacts of congestion pricing initiatives.

## Future Improvements

With additional development time and resources, we envision the following enhancements to significantly improve data validation and analytical capabilities:

### Real-World Data Validation
- **NYC Traffic Camera Integration**: Leverage NYC's network of open traffic cameras to validate our traffic flow models and verify congestion patterns in real-time
- **Vehicle Tracking Enhancements**: Implement 1:1 vehicle tracking capabilities to precisely measure how long each vehicle remains within the congestion zone, providing accurate dwell-time metrics
- **Entry/Exit Correlation**: Create more sophisticated algorithms to match entry and exit events, producing comprehensive journey data within the congestion zone

### Advanced Sensing Technologies
- **Drone Imagery Analysis**: Incorporate aerial drone footage to assess actual road supply availability throughout the congestion zone
- **Computer Vision Processing**: Develop machine learning models to automatically analyze camera and drone imagery for real-time traffic density measurement
- **Sensor Network Expansion**: Add additional IoT sensors at key congestion points to supplement existing data sources

### Economic and Safety Modeling
- **Road Condition Assessment**: Build an economic evaluation model that factors in road infrastructure conditions and their impact on traffic flow
- **Accident Risk Prediction**: Develop predictive models to identify areas of Lower Manhattan with elevated crash risks based on traffic patterns and road conditions
- **Cost-Benefit Analysis Tools**: Create dashboard components that calculate and visualize the economic impacts of various congestion pricing scenarios

### Predictions Integration
- **Anomaly Detection Algorithms**: Implement more sophisticated models to automatically identify unusual traffic patterns and potential system gaming
- **Predictive Congestion Modeling**: Use historical data to forecast future congestion patterns under various conditions
- **Weather and Event Impact Analysis**: Incorporate external data sources to model how weather and major events affect congestion patterns

These improvements would transform the current analysis tool into a comprehensive urban mobility intelligence platform, providing deeper insights into the effectiveness of congestion pricing policies while identifying opportunities for infrastructure and policy optimization.

## Usage

### Historical Analysis
1. Navigate to the dashboard view
2. Select your desired date range
3. Explore vehicle type breakdowns and patterns
4. Use the interactive map to view specific entry points

### Real-time Monitoring
1. Switch to "Live Mode" in the map view
2. Monitor the heatmap for current congestion patterns
3. View real-time updates of entry point metrics

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/mta-congestion-analysis.git
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up the database:
   ```bash
   cd congestion_dashboard
   python manage.py makemigrations
   python manage.py migrate
   ```

4. Run the development server:
   ```bash
   python manage.py runserver
   ```

## Configuration

- Update the `settings.py` file with your database configuration
- Configure the real-time data endpoint in the frontend code
- Set up appropriate API keys and credentials


## Acknowledgments

- New York Metropolitan Transportation Authority (MTA)
- NYC Department of Transportation
- Open source community contributors
