# Revision 2: CRISP-DM experiment protocol

Written before inspecting January–August 2026 prediction errors. Version 1 remains preserved as the initial experiment. This revision is a portfolio research workflow, not a production grid-control system.

## 1. Business understanding

**Stakeholder assumption:** an electricity planning manager estimating energy purchases and budgeting volumes. No real stakeholder interview or tariff/cost data was supplied.

**Decision:** expected ERCOT demand tomorrow, during the next Monday–Sunday week, and during the next calendar month. Units are MWh, not peak MW. Daily forecasts support near-term energy planning; weekly/monthly totals support volume planning. These data do not support claims about hourly adequacy, reserve capacity, outages prevented, or money saved.

**Proposed acceptance criteria:** at least 10% lower MAE than the repeat-week baseline at each scale and absolute aggregate bias below 3%. These are analyst-proposed portfolio criteria, not manager-approved targets. Approximate 90% interval coverage is reported, with 85–95% an indicative daily/weekly review band; monthly coverage is descriptive because samples are small. A missed criterion means review, not automatic deployment. Also report performance against a persistence baseline.

**Hypotheses:** calendar/demand features outperform repeat-week; weather proxies add incremental value to the same estimator; improvements remain reasonably stable across seasons and high-demand periods. Findings may reject these hypotheses.

## 2. Data understanding

Use preserved EIA daily demand and Open-Meteo ERA5 snapshots. Verify schema, units, keys, date continuity, missingness, numeric ranges, city/date joins and source revisions. Audit all dates structurally; explore target distributions only through 2023 before selection. Document provenance and hashes. Do not infer weather causality from correlation.

## 3. Data preparation

Build normalized SQLite demand, weather and calendar tables. Retain missing calendar dates explicitly. Invalid nonpositive demand or impossible humidity/temperature becomes NULL in curated tables and is recorded in a cleaning log; raw files are untouched. Flag robust outliers for investigation without deleting them. No interpolation of targets. Require all four city values for a daily weather mean. Training-only median imputation handles predictor gaps.

Use daily demand through issue date minus one day and weather through issue date minus seven days. These are assumptions to test, not verified as-of feeds. Calendar features are known in advance. Seasonal weather averages are fitted only on each training snapshot. Exact EIA versus weather daylight-saving aggregation remains an operational validation item.

## 4. Modeling

Use direct pooled forecasts for leads 1–31. Forecast origins are end of day. Candidate set is fixed before the fresh test:

- Persistence and last available same-weekday baselines.
- Ridge regression, alpha 1 or 100, each with/without weather proxies.
- Histogram gradient boosting, 15 leaves, 100 iterations, learning rate .07, L2=10, with/without weather.

Ridge calendar encoding uses weekday indicators and annual Fourier terms, not an artificial numeric ordering of weekdays. Add trend, holidays, recent demand summaries, horizon and lead-decay interactions. Weather uses lagged temperature/humidity and training climatology degree-day terms. No actual target weather is an eligible input. Use a fixed seed; no random time-series split.

**Selection:** expanding-window folds: train 2019–2021 / validate 2022; train 2019–2022 / validate 2023. Rank each scale by mean fold MAE divided by repeat-week MAE, weighting folds equally. Baselines are eligible. Freeze scale-specific selections after these folds. No tuning after viewing 2024/2025/2026 results.

**Development check:** refit through 2023, evaluate 2024. **Calibration:** refit through 2024, predict 2025; use the selected models' absolute period errors for approximate intervals. **Fresh final test:** refit through 2025, evaluate January–August 2026. The latter is untouched by the earlier project, but covers only eight months and is a revised-data retrospective test. Never rename the previously inspected 2025 period an untouched holdout.

## 5. Evaluation

MAE is primary; report RMSE, WAPE, bias, baseline improvement, coverage and scored counts. Aggregate all weekly/monthly predictions from a single pre-period issue date. Do not sum separate next-day predictions into a fake week-ahead result. Exclude incomplete actual totals explicitly. Assess lead-time performance on common origins with all 31 leads observable, residual autocorrelation, weekday/month/high-demand slices, largest misses, train–validation gaps and paired weather ablations.

Use a seven-day moving-block bootstrap on daily paired error differences for a descriptive stability interval; dependence and few extreme events limit statistical conclusions. Do not tune in response to test diagnostics. Any redesign requires a future untouched test.

## 6. Delivery and monitoring

Save a local trusted model artifact with fitted preprocessing, selected features, climatology, cutoff, versions and source hashes. Provide a CLI that loads it and produces daily/weekly/monthly CSVs from new historical input; refuse stale or duplicate inputs. Demonstrate it locally and verify that its daily path reconciles to complete-period sums. Separate independently selected forecast products from coherent sums of one path.

Create a model card, management brief, annotated executable notebook and terminal transcript. Simulate monitoring using recorded test forecasts: missing inputs, date freshness, drift reference, rolling WAPE/bias, interval coverage, with review actions and a baseline fallback. Monitoring flags are retrospective; no service or recurring job is deployed. Live readiness remains gated on archived forecast weather, demand vintages, time-boundary verification, and stakeholder acceptance.
