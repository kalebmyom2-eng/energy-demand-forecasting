# Delivery, monitoring and iteration

## Local delivery completed

The saved model bundle runs without retraining. The batch CLI produces dated daily forecasts, coherent weekly/monthly sums, independently selected scheduled products, and metadata. August 31, 2026 is the demonstrated historical issue date; it produces a 31-day path starting September 1, including a one-day partial October period. This is not a current forecast.

## Proposed operational checks

| Check | Evidence / threshold | Action |
|---|---|---|
| Data contract | Unique dates, required columns, correct units, continuous spine | Reject invalid input; repair upstream |
| Freshness | Demand available through issue−1 and weather through issue−7 | Hold publication; verify release delays |
| Missing targets | NULL actuals and incomplete totals | Exclude from scoring; disclose counts |
| Accuracy | 28-day WAPE >10% | Review against baseline and seasonal context |
| Bias | Absolute 28-day bias >3% | Investigate systematic over/underprediction |
| Coverage | Indicative 85–95% daily/weekly coverage | Review interval width and calibration regime |
| Drift | Distribution shift versus a training reference | Check comparable seasons before interpreting |
| High demand | Errors above development p90 demand | Review event exposure and underforecasting |
| Publication | Artifact cutoff ≤ issue date; version and hash attached | Reject mismatched artifact; roll back if needed |

Thresholds are analyst-proposed, not approved operational policy. Monitoring is demonstrated retrospectively in reports/v2/monitoring_simulation.csv. No scheduler, live feed, notification channel or cloud deployment was created.

## Fallback and iteration

A baseline is already selected for two products. For a failing monthly model, compare the last approved monthly model with repeat-week; do not publish an automatic substitution without recording its identity and evaluating the planning implications. Stale input is not fixed by using a different model with the same stale input.

Before live use: confirm business costs and acceptable error, verify date boundaries and availability delays, obtain archived forecast weather/demand vintages, and assign an owner. For retraining: open a versioned experiment, train/tune only on development history, freeze the candidate, evaluate on a new untouched period, and document the promotion decision. Keep prior artifacts and a rollback path.

## Suggested manager presentation

1. Define the decision and units: energy planning at three time scales.
2. Show the data audit and why one missing day cannot become zero demand.
3. Explain the temporal experiment and the move to a fresh 2026 test.
4. Show the scorecard, including the weekly failed improvement gate.
5. Explain uncertainty, high-demand failures and the limited monthly sample.
6. Demonstrate local inference; state what must be validated before production.
