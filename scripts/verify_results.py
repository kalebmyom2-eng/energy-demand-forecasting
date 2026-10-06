"""Check forecast timing, missing-data treatment, model selection and reconciliation."""
# BLOCK 1 — Load real saved outputs; fail visibly if required artifacts are absent.
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
r = ROOT / 'reports'
paths = pd.read_csv(r/'test_daily_paths.csv',parse_dates=['origin','target'])
periods = pd.read_csv(r/'test_period_forecasts.csv',parse_dates=['origin','start','end'])

# BLOCK 2 — Verify that every forecast precedes delivery, including long horizons.
assert ((paths.target-paths.origin).dt.days == paths.horizon).all()
assert paths.horizon.between(1,31).all()
assert (periods.origin < periods.start).all()
assert (periods.end-periods.start).dt.days.add(1).eq(periods.days).all()
weekly=periods[periods.scale=='weekly']
assert weekly.start.dt.dayofweek.eq(0).all() and weekly.days.eq(7).all()
monthly=periods[periods.scale=='monthly']
assert monthly.start.dt.is_month_start.all() and monthly.end.dt.is_month_end.all()
print('PASS: forecast issue dates and complete calendar-period definitions')

# BLOCK 3 — Missing demand must invalidate actuals for its containing periods.
missing=pd.Timestamp('2025-12-05')
affected=periods[(periods.start<=missing)&(periods.end>=missing)]
assert set(affected.scale)=={'daily','weekly','monthly'} and affected.actual.isna().all()
with sqlite3.connect(ROOT/'data/energy.sqlite') as con:
    assert con.execute("SELECT demand_mwh FROM monthly_actuals WHERE month='2025-12'").fetchone()[0] is None
print('PASS: missing daily demand is not scored or silently summed into totals')

# BLOCK 4 — Recompute the frozen selections independently from validation metrics.
validation=pd.read_csv(r/'validation_metrics.csv')
validation=validation[~validation.model.str.startswith('oracle')]
chosen=validation.loc[validation.groupby('scale').mae_mwh.idxmin()].set_index('scale').model
scorecard=pd.read_csv(r/'selected_model_summary.csv')
for row in scorecard.itertuples():
    assert row.model==chosen[row.scale]
assert dict(zip(scorecard.scale,scorecard.n_periods))=={'daily':364,'monthly':11,'weekly':50}
print('PASS: selection uses validation only; expected test coverage is preserved')

# BLOCK 5 — Recompute metrics and ensure intervals are ordered around forecasts.
selected=pd.read_csv(r/'selected_test_forecasts.csv')
assert (selected.lower_90<=selected.prediction).all()
assert (selected.prediction<=selected.upper_90).all()
for row in scorecard.itertuples():
    g=selected[selected.scale==row.scale].dropna(subset=['actual'])
    assert np.isclose(abs(g.prediction-g.actual).mean(),row.mae_mwh)
print('PASS: reported MAE independently reproduced; interval bounds valid')

# BLOCK 6 — Verify the demonstration's totals reconcile to its daily forecast path.
daily=pd.read_csv(r/'snapshot_daily_january_2026.csv')
week=pd.read_csv(r/'snapshot_weekly_january_2026.csv')
month=pd.read_csv(r/'snapshot_monthly_january_2026.csv')
assert len(daily)==31 and np.isfinite(daily.forecast_mwh).all()
assert np.isclose(daily.forecast_mwh.sum(),month.forecast_mwh.iloc[0])
assert np.isclose(daily.forecast_mwh.sum(),week.forecast_mwh.sum())
assert week.complete_week.eq(week.days.eq(7)).all()
print('PASS: daily/weekly/monthly snapshot totals reconcile; partial weeks labeled')
print('\nAll substantive verification checks passed.')
