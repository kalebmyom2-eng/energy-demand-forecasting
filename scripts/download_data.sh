#!/bin/sh
# Run from the project root. EIA DEMO_KEY has a limited request quota.
set -eu
mkdir -p data/raw
curl -g -L --fail --max-time 120 'https://api.eia.gov/v2/electricity/rto/daily-region-data/data/?api_key=DEMO_KEY&frequency=daily&data[0]=value&facets[respondent][]=ERCO&facets[type][]=D&facets[timezone][]=Central&start=2019-01-01&end=2025-12-31&sort[0][column]=period&sort[0][direction]=asc&offset=0&length=5000' -o data/raw/eia_erco_daily_2019_2025.json
curl -g -L --fail --max-time 120 'https://archive-api.open-meteo.com/v1/archive?latitude=29.7604,32.7767,30.2672,29.4241&longitude=-95.3698,-96.7970,-97.7431,-98.4936&start_date=2019-01-01&end_date=2025-12-31&daily=temperature_2m_mean,temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean&timezone=America%2FChicago&models=era5' -o data/raw/weather_texas_2019_2025.json
