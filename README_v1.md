> Historical version 1. See README.md for the revised methodology and fresh test.

# ERCOT Electricity Demand Forecasting

A SQL and Python portfolio case study forecasting daily, weekly and monthly electricity demand using calendar seasonality, historical demand and weather features.

**Business question:** can we improve energy-volume planning over a repeat-week baseline, and does weather add reliable predictive value?

## Measured result

The ridge regression selected on 2024 validation data achieved the following results on the reserved 2025 test:

| Forecast product | WAPE | MAE reduction vs baseline | Scored periods |
|---|---:|---:|---:|
| Next day | 5.26% | 31.8% | 364 days |
| Next calendar week | 4.94% | 22.8% | 50 weeks |
| Next calendar month | 3.82% | 33.0% | 11 months |

Weather proxies did not beat the selected regression. A diagnostic using realized future weather improved daily results, but is explicitly excluded from selection because that information is unavailable in real forecasts. The result supports a forecasting prototype, not a claim of operational readiness or financial savings.

![Forecasts versus actual demand](reports/figures/02_test_forecasts.png)

## Start here

- [Step-by-step procedure](reports/STEP_BY_STEP.md): business framing, SQL, features, validation, outcomes and terminal commands.
- [Management brief](reports/management_brief.md): conclusions, uncertainty and practical limitations.
- [Annotated Python pipeline](scripts/run_project.py): eleven explanatory code blocks.
- [Annotated SQL](sql/analysis.sql): quality checks, seasonal summaries, date joins and complete monthly totals.
- [Executed review notebook](notebooks/portfolio_walkthrough.ipynb): SQL queries, actual results and charts from the completed run.
- [Terminal transcript](reports/terminal_run.log): the actual modeling run.

## Data and scope

Daily ERCOT demand, January 1, 2019–December 31, 2025, from [EIA's daily regional endpoint](https://www.eia.gov/opendata/browser/electricity/rto/daily-region-data). Filters: respondent `ERCO`, type `D`, timezone `Central`; units: MWh. Weather comes from [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api), ERA5 reanalysis, `America/Chicago`, for Houston, Dallas, Austin and San Antonio. Variables: daily temperature mean/min/max and mean humidity. Credit: Open-Meteo and Copernicus/ECMWF ERA5. Retrieved September 28, 2026.

Original responses are preserved in `data/raw/`. The prepared table has 2,557 calendar rows and 18 columns. December 5, 2025 lacks demand; it remains blank. Incomplete actual weekly/monthly totals are not scored. City weather averages are proxies rather than a load-weighted representation of ERCOT. The model currently uses city-average mean temperature and humidity; minimum/maximum temperature remain available for future studies.

## Reproduce

Tested with Python 3.13.9 and the versions in `requirements.txt`. SQLite is part of Python's standard library.

```sh
# From the project root, install the scientific stack in your chosen environment.
python -m pip install -r requirements.txt

# Rebuild the daily table from the preserved API snapshots.
python scripts/prepare_data.py

# Execute SQL, explore training data, fit models, evaluate and save forecasts.
# Keep the pipeline's exit status and save its terminal output.
set -o pipefail
python -u scripts/run_project.py 2>&1 | tee reports/terminal_run.log

# Verify forecast timing, missing values, selections, metrics and reconciliation.
python scripts/verify_results.py
```

On this Mac, `/opt/anaconda3/bin/python` was used successfully. Reading the optional notebook requires Jupyter; reproducing the pipeline does not.

```sh
# Optional refresh: this replaces the raw snapshots and can change results after source revisions.
# EIA's public DEMO_KEY has a limited quota; no personal key is stored in the repository.
sh scripts/download_data.sh
```

## Evaluation design

Train 2019–2023; select using 2024; refit through 2024; test on 2025. Parameters stay fixed during each evaluation year, while forecast origins and historical predictors advance. Direct predictions cover leads 1–31. Demand/weather lag features use issue date minus one day or earlier. Weekly forecasts are issued Sunday for Monday–Sunday; monthly forecasts are issued at month end for the following month. Actual within-period demand never becomes a predictor for that period's forecast.

The candidate set contains seasonal naive, ridge regression, calendar/demand gradient-boosted trees and trees with past/seasonal weather. A separate perfect-weather diagnostic cannot be selected. Approximate 90% intervals use validation residuals; 2025 coverage was 89.6% daily, 92.0% weekly and 90.9% monthly, with only 12 monthly calibration observations.

## Deliverables and limitations

The database is `data/energy.sqlite`. Reports include validation/test metrics, metrics by lead time, complete-period forecasts, largest errors, figures, and a version/data-hash manifest.

January 2026 CSVs are historical-snapshot forecasts issued December 31, 2025, not current forecasts. Their daily path reconciles to weekly/monthly totals; partial weeks are labeled. Next-day accuracy must not be attributed to every lead in that path.

Sharp winter demand spikes remain difficult. Historical demand revisions, weather reanalysis publication lags, exact daylight-saving day boundaries, and spatial coverage require validation before operational use. Daily energy cannot establish hourly peak-capacity accuracy. The next extension is archived forecast-weather and demand-vintage evaluation, with a new untouched test period for any model redesign.
