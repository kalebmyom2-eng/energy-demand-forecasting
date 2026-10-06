# Electricity demand forecasting: a guided case study

## 1. Translate the business problem into measurable decisions

A planning manager needs an estimate of energy volume for tomorrow, next week, and next month. Our target is **energy in MWh**, not peak power in MW. The case study cannot answer an hourly capacity or reserve-margin question from daily totals alone.

We define three products: next-day energy, Monday–Sunday weekly energy issued the preceding Sunday, and calendar-month energy issued at the preceding month end. The issue-date convention is end of day, with a conservative one-day lag: at the December 31 issue date, the latest historical demand feature is December 30. Data publication timing remains an operational assumption.

The success measure is reduced mean absolute error (MAE) versus repeating the latest available week. MAE is readable in MWh. RMSE gives more weight to large misses. WAPE divides total absolute error by total actual energy, making scales easier to compare. Bias shows systematic over- or under-prediction.

## 2. Preserve evidence and audit before modeling

Raw EIA and Open-Meteo JSON responses stay unchanged. `scripts/prepare_data.py` checks identities, units, duplicate dates, coverage and weather completeness, then builds a daily table.

There are 2,557 dates and 2,556 demand observations. December 5, 2025 is missing. We preserve a blank rather than invent a target. Predictor gaps may be imputed using a training-fitted median, but a missing test target is never imputed for scoring.

## 3. Use SQL for relational work

`sql/analysis.sql` contains five annotated blocks. Python loads the prepared data into SQLite and executes them.

- `quality_summary`: count calendar rows and observed demand separately.
- `annual_summary`: compare average daily demand; return NULL for incomplete annual totals.
- `training_seasonality`: group by month within the training period.
- `modeling_daily`: use date joins to retrieve the previous day and previous week. These illustrative lags are available in the SQL view; the multi-horizon model builds its own issue-date-aligned predictors.
- `monthly_actuals`: return a monthly total only if every expected day is observed.

```sql
-- COUNT(column) ignores NULL; COUNT(*) counts every calendar row.
-- Their difference exposes missing observations before any averages or totals.
SELECT COUNT(*) AS calendar_days,
       COUNT(demand_mwh) AS observed_days,
       COUNT(*) - COUNT(demand_mwh) AS missing_days
FROM daily;
```

The database is local at `data/energy.sqlite`; no server or credentials are required.

## 4. Explore seasonality without looking at the final test

Python plots 2019–2023 demand, month-of-year averages, day-of-week averages, and temperature versus demand. See `figures/01_training_exploration.png`.

The goal is to check whether feature choices make sense, not to infer causation from a scatterplot. Weather is represented by four city locations, averaged equally. Extreme values are retained; unusual grid events may be economically meaningful.

## 5. Establish a baseline and construct safe features

The baseline repeats the latest same weekday available at the issue date, reusing that historical week for longer horizons. It is stronger and fairer than predicting one overall average.

`examples()` in `scripts/run_project.py` creates an origin–target pair for each lead from 1 to 31 days. For every row, target date = issue date + lead. Inputs include:

- Known future calendar information: day of week, month, sine/cosine annual seasonality, trend, weekend and federal-holiday indicator.
- Demand available at the issue date: latest available value, seven days before that, and 7-/28-day rolling means.
- Weather candidate: past temperature/humidity plus a month-day seasonal average estimated from the training period, and heating/cooling degree-day proxies using a fixed 18°C threshold.

```python
# Only values through issue date minus one day are treated as available.
# This prevents accidentally feeding target-period actuals into long forecasts.
available = origins - pd.Timedelta(days=1)
last_demand = df.demand_mwh.reindex(available)
```

A direct model predicts each target from issue-date information. It does not replace lag values with actual demand discovered later in the delivery week or month. Temperature and humidity reanalysis are revised historical estimates; the study does not assert that those exact weather values were published at that issue time.

## 6. Compare models without choosing on test performance

We predeclare a small candidate set: seasonal baseline, ridge regression, calendar/demand trees, and trees with weather proxies. Ridge penalizes large coefficients; the pipeline fits median imputation and scaling on training examples only. Tree settings are fixed, and their internal random early-stopping split is disabled.

A separate oracle experiment supplies realized target weather. It measures a favorable information scenario, not a deployable forecast, and is barred from model selection. It is not a mathematical bound on every possible model.

Train through 2023, validate on 2024, then freeze the lowest-MAE eligible model for each delivery scale. Refit through 2024 and score 2025 once. Forecast origins advance through the test year, while fitted parameters remain fixed; known historical observations update the predictors at each origin. Do not randomly shuffle the series.

## 7. Evaluate daily values and complete period totals

Weekly and monthly predictions are summed from forecasts made at the same issue date. Adding seven independently issued next-day forecasts would answer a different, easier question.

A weekly/monthly period crossing the evaluation-year boundary is excluded. Missing December 5 invalidates its daily score and the containing weekly/monthly actual totals. Final counts: 364 daily observations, 50 full weeks and 11 full months.

Read `validation_metrics.csv`, `test_metrics.csv`, and `test_metrics_by_horizon.csv`. The last file distinguishes a 31-day lead from a next-day prediction. Do not attach a next-day score to the full January forecast path.

## 8. Quantify uncertainty and inspect failures

Approximate 90% intervals use a finite-sample adjusted quantile of absolute 2024 validation errors. Weekly/monthly totals are calibrated on their own total errors; we do not sum daily interval bounds. Evaluate their observed coverage in 2025 rather than assuming 90% coverage.

Time dependence, drift and model refitting limit a formal coverage claim. Only 12 validation months are available. `largest_errors.csv` identifies the hardest periods, and `figures/02_test_forecasts.png` exposes missed demand spikes. These are planning limitations even when average error improves.

## 9. Read the measured outcome

The validation-selected model was ridge regression for all three scales. In 2025 it achieved WAPE of approximately 5.26% daily, 4.94% weekly and 3.82% monthly. MAE decreased by 31.8%, 22.8% and 33.0% against the repeat-week baseline respectively.

Weather proxies did not beat the selected regression. Compared with the same tree architecture without weather, the weather candidate improved validation results but worsened test results. That is evidence against claiming a reliable improvement from this weather specification. The ideal-weather diagnostic improved daily results, which motivates a future experiment with archived forecast-weather inputs.

The model generally follows seasonal volume changes but misses some sharp daily peaks. A manager should see both the error reduction and this remaining weakness. No financial savings or operational readiness have been established.

## 10. Deliver forecasts with an explicit timestamp

The final demonstration refits through 2025 and issues a 31-day path on December 31, 2025 for January 2026. It aggregates the same path to weekly and monthly totals, so the numbers reconcile. Partial boundary weeks are labeled. These are historical-snapshot predictions, not current September 2026 forecasts.

The best models could differ across scales in a future rerun. The management comparison allows independent scale selections; the demonstration deliberately uses one daily path for reconciliation. Its full-month output is not the independently selected monthly model product.

## 11. Reproduce in the terminal

Run from the project root. `/opt/anaconda3/bin/python` is the verified interpreter on this Mac; another environment can install `requirements.txt` and use `python` instead.

```sh
# Rebuild the table from preserved source snapshots without requesting fresh data.
/opt/anaconda3/bin/python scripts/prepare_data.py

# Print each SQL/modeling stage and preserve the same output as a terminal transcript.
# pipefail ensures a Python error is not hidden by tee's successful exit.
set -o pipefail
/opt/anaconda3/bin/python -u scripts/run_project.py 2>&1 | tee reports/terminal_run.log

# Check timing, missing-target handling, model selection, metrics and reconciliation.
/opt/anaconda3/bin/python scripts/verify_results.py
```

Start a portfolio presentation with `management_brief.md`, then use the plots and this walkthrough to explain how the result was obtained. Before operational use, obtain archived weather forecasts and demand vintages, verify day boundaries and release delays, then repeat the evaluation.
