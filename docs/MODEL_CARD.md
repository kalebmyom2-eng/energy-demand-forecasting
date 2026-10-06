# Model card — ERCOT portfolio revision 2

## Purpose and status

Local research prototype for energy-volume forecasting. No live system is deployed. Intended users are portfolio reviewers and planning analysts. Do not use daily energy accuracy as evidence of peak-capacity, reserve-margin or outage prediction performance.

## Training and selection

Candidates and gates are documented in EXPERIMENT_PROTOCOL_V2.md. The search includes two baselines and six model/feature configurations. Expanding 2022 and 2023 validation folds select each scale by equal-fold average relative MAE. A 2024 development check does not change selection. Previously inspected 2025 calibrates approximate intervals. January–August 2026 is the new final test. Model choices remain frozen afterward.

Selected products: daily persistence, weekly repeat-week, monthly ridge regression (alpha 100) with historical/seasonal weather proxies. Simple methods are legitimate winners; the project does not force an advanced model to win. All historical-demand inputs are subject to the same one-day issue-date lag.

The delivered bundle is refitted through August 31, 2026, after evaluation. Its measured test scores belong to earlier fits through 2025, not to in-sample predictions from the delivered fit. Artifact manifest records versions, feature columns, cutoff and data hash.

## Evidence and limitations

Read reports/v2/management_scorecard.csv for the fresh test, candidate_ranking.csv for selection, and weather_ablation.csv for paired feature comparisons. Daily/weekly/monthly sample sizes are 243/34/8. There is no complete annual 2026 test.

Daily and monthly meet the proposed accuracy gate; weekly does not improve on repeat-week. Weekly interval coverage exceeds the indicative review band, suggesting that width/coverage should be reviewed. Eight monthly observations cannot establish reliable 90% interval calibration.

Weather is lagged reanalysis plus training climatology, not target-period weather forecasts. City means are not load-weighted; holiday coverage uses US federal dates. Large shocks and demand growth can change relationships. Drift, bias and high-demand errors need review. Feature association and ablation do not establish causal weather effects.

## Inference contract

Run scripts/predict.py with an explicit origin date, local trusted artifact and daily input CSV. It refuses origins before model training, duplicate dates, stale/short/discontinuous histories, missing required recent observations and nonpositive demand. Unknown target values are never read as features. Do not load untrusted joblib artifacts.

Daily path and coherent weekly/monthly sums use the daily-selected model. Independently selected products are issued on their evaluated schedules: daily, Sunday for next week, month end for next month. These outputs can differ; they are not presented as reconciled with one another. Approximate intervals attach to selected products, not arbitrary partial totals.

## Maintenance and ownership

This portfolio has no appointed operational owner. A production planning owner would approve metrics and operational decisions; a data owner would own feed quality; a model owner would review drift and retraining. Assign these roles before live use. Retraining must be evaluated against a baseline on a later untouched period, not automatically promoted because it is newer.
