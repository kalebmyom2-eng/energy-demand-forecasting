# Data dictionary and preparation decisions

## Source tables in data/energy_v2.sqlite

| Table / field | Meaning | Type / unit | Key / rule |
|---|---|---|---|
| calendar.date | Complete date spine, 2019-01-01–2026-08-31 | ISO date text | Unique; 2,800 rows |
| demand.date | EIA Central date for ERCO demand | ISO date text | Unique |
| demand.demand_mwh | Reported daily electricity demand | Numeric MWh | Positive or NULL; not peak MW |
| weather.date | America/Chicago weather date | ISO date text | Unique with city |
| weather.city | Houston, Dallas, Austin or San Antonio | Text | Four location proxies |
| weather.temp_mean/min/max | ERA5 daily air-temperature summary | °C | -90 to 65 sanity range; min ≤ mean ≤ max |
| weather.humidity | ERA5 daily mean relative humidity | Percent | 0–100 or NULL |
| daily_features.temp | Equal-city daily mean temperature | °C | Requires all four city means |
| daily_features.humidity | Equal-city daily mean humidity | Percent | Requires all four city values |
| daily_features.weather_cities_present | Non-null temperature city count | Integer | Expected 4 |

Latitude/longitude requested: Houston (29.7604,-95.3698), Dallas (32.7767,-96.7970), Austin (30.2672,-97.7431), San Antonio (29.4241,-98.4936). Returned grid coordinates remain in raw JSON. These are city/grid proxies, not a full ERCOT footprint.

## Missingness, validity and outliers

- December 5, 2025 has no demand observation. Preserve NULL; never use it as an imputed scoring target.
- Raw snapshots are immutable during curation. Curated nonpositive demand and impossible weather values become NULL with a cleaning-log entry. None should be silently discarded.
- Duplicate source keys or wrong units stop the pipeline. Calendar gaps stay explicit through left joins.
- All four cities must be present for weather aggregation; avoid silently changing the spatial mix.
- Robust outliers are flags only. A real grid event can look statistically unusual. Flags use past rolling medians/scales within development data, not test thresholds.
- Median imputation is for predictors only and is fitted within each training fold. It does not make missing targets valid.
- Complete weekly/monthly actuals require every day. Partial inference periods are labeled.

## Feature availability

| Group | Features | Available when? |
|---|---|---|
| Calendar | weekday indicators, weekend, federal holiday, annual Fourier terms, trend | Known for target date |
| Horizon | days ahead, 1–31 | Known at issue |
| Demand | latest, lag seven days behind latest, past 7-/28-day means, 7-day standard deviation, recent change | Through issue minus 1 day |
| Weather | past temperature/humidity | Through issue minus 7 days |
| Climate | target month/day averages and 18°C degree-day proxies | Fitted on training snapshot only |
| Interactions | recent-demand/temperature anomalies attenuated by lead | Derived only from the above inputs |
| Target | actual target-day MWh | Training labels and scoring only |

A one-day demand lag and seven-day weather lag are operational assumptions. Revised EIA data and ERA5 are not archived as-of feeds; historical revisions can still influence retrospective results. Exact Central/Chicago daylight-saving day definitions require verification before live use.

## Provenance

EIA: https://www.eia.gov/opendata/browser/electricity/rto/daily-region-data

Weather: https://open-meteo.com/en/docs/historical-weather-api — credit Open-Meteo and Copernicus/ECMWF ERA5. Retrieval: 2026-09-28. Raw hashes and overlap revisions are recorded in reports/v2/data_manifest.json and source_revisions.csv. The refreshed overlap had zero demand revisions relative to version 1.
