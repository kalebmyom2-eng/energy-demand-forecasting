# ERCOT forecasting — CRISP-DM revision 2

## Business decision
Estimate next-day, next-calendar-week and next-calendar-month energy demand. This supports volume planning, not hourly capacity assurance. Criteria are analyst-proposed, not stakeholder-approved.

## Fresh final test: January–August 2026

| Scale | Selected model | Periods | WAPE | MAE gain vs repeat-week | Bias | Interval coverage | Proposed accuracy gate |
|---|---|---:|---:|---:|---:|---:|---|
| daily | persistence | 243 | 5.26% | 23.0% | -0.28% | 86.8% | Pass |
| monthly | ridge_100_weather | 8 | 2.46% | 57.7% | -0.97% | 100.0% | Pass |
| weekly | repeat_week | 34 | 4.85% | 0.0% | -1.38% | 97.1% | Review |

## Evidence and recommendation
Models were selected on expanding 2022/2023 folds. 2024 was a development check; previously inspected 2025 was interval calibration. Selections remained fixed during the fresh 2026 test. Accuracy gates require ≥10% MAE improvement and absolute bias <3%.
Use the local prototype for demonstration and planning research. Review any failed gate before considering operational use. No monetary benefit has been established.
Daily paired MAE-gain stability: 22,241 MWh; descriptive seven-day block-bootstrap 95% interval 9,786 to 37,668 MWh.

## Limits that remain
- Only eight test months; no autumn/winter-complete annual assessment. Monthly samples are especially small.
- Historical revised demand and ERA5 reanalysis are not archived as-of operational feeds. Seven-day weather and one-day demand availability are assumptions.
- Four-city weather is a spatial proxy; daylight-saving aggregation and load weighting remain unverified.
- Weather ablations compare paired estimators. A weather model winning one scale does not prove causality or universal weather benefit.
- Approximate intervals use 2025 residuals and refitted models; temporal dependence and drift can invalidate nominal coverage.
- Independent scale-selected products may differ from coherent sums of one daily-model path. Both outputs are labeled.

## Delivery
Saved a versioned model bundle and inference CLI, tested locally. Monitoring is a retrospective simulation. No live service is deployed. September 2026 outputs are dated historical-snapshot forecasts issued August 31, not current forecasts.

## Next decision
Confirm stakeholder cost/accuracy tolerances and acquire archived weather forecasts and demand vintages. Any further model redesign must be tested on a later untouched period.

![Fresh test](figures/02_fresh_test.png)
