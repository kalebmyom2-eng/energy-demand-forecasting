# Electricity demand forecasting: choosing the method for each planning horizon

## Problem

Energy-volume planning requires estimates at different timescales. This project asks whether calendar, historical demand and weather information improve forecasts of ERCOT electricity demand over simple baselines. Targets are next-day energy, next-calendar-week energy and next-calendar-month energy, all in MWh.

## Data and preparation

The advanced study uses 2,800 calendar days from January 2019 through August 2026. EIA supplies demand; Open-Meteo supplies ERA5 weather for Houston, Dallas, Austin and San Antonio. There are 2,799 observed demand values. December 5, 2025 remains unknown rather than being replaced with zero; weekly and monthly actual totals containing that date are invalidated.

SQL and Python create and audit daily tables, check completeness, preserve raw snapshots and record source revisions. Weather averages across four cities are regional proxies, not load-weighted measures. See the [data dictionary](DATA_DICTIONARY.md) and [source notes](../data/README.md).

## Modeling decisions

Two simple baselines compete with six model and feature configurations. Expanding validation folds for 2022 and 2023 choose a method independently for each product. A 2024 development check follows; previously inspected 2025 data calibrates approximate intervals. January–August 2026 supplies the final evaluation under the recorded protocol.

Features use demand available through issue date minus one day and weather through issue date minus seven days. Future weather is represented by training-fitted climatology and historical proxies. Weekly and monthly predictions are issued before the whole period, rather than assembled from forecasts updated during that period.

## Results

| Product | Selected method | Test observations | MAE (MWh) | WAPE | MAE improvement over repeat-week |
|---|---|---:|---:|---:|---:|
| Daily | Persistence | 243 | 74,397 | 5.26% | 23.0% |
| Weekly | Repeat-week | 34 | 481,088 | 4.85% | 0.0% |
| Monthly | Ridge with weather proxies | 8 | 1,058,432 | 2.46% | 57.7% |

MAE is the mean absolute prediction error. WAPE is total absolute error divided by total actual demand, expressed as a percentage. MAE values across scales measure different energy volumes and should not be compared directly.

Source: [saved scorecard](../reports/v2/management_scorecard.csv), with individual predictions in [selected forecasts](../reports/v2/selected_forecasts.csv).

![Actual demand and forecasts](../reports/v2/figures/02_fresh_test.png)

The practical finding is that added model complexity did not win every product. Daily and monthly methods met the proposed improvement and bias criteria; weekly did not. The monthly 57.7% improvement compares the selected model with repeat-week. It is not the isolated contribution of weather.

## What the project demonstrates

- Auditing time-series data with Python and SQL while preserving missing targets.
- Comparing simple baselines with regression and tree candidates using chronological validation.
- Checking that unavailable future observations cannot change forecast features.
- Reporting results by planning horizon, including an unsuccessful improvement target.
- Delivering a local prediction command, saved model, model card and monitoring simulation.

## Limits and next steps

Eight monthly test observations do not establish year-round reliability. Weather reanalysis is not an operational weather forecast feed, and source publication delays need validation. The project measures energy volume, not hourly peak demand, avoided outages or financial savings. Monitoring is retrospective and no live service is deployed.

The next research step is to evaluate frozen methods on a later untouched period, then investigate weekly errors without using the existing final test to select a replacement model. Operational use would also need validated source timing, approved performance thresholds and assigned ownership.

## Reproduce and inspect

Follow the [README setup](../README.md#quick-start), then run `python scripts/run_lifecycle.py` to rebuild the excluded model and databases, followed by `python scripts/verify_lifecycle.py` from the project root. The [methodology notebook](../notebooks/01_complete_data_science_methodology.ipynb) presents the analysis; the [model card](MODEL_CARD.md) explains inference boundaries.
