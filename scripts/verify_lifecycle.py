"""Behavioral checks for leakage, period accounting, selection and local inference."""
# BLOCK 1 — Use actual saved outputs and the frozen model protocol.
from pathlib import Path
import json
import tempfile
import numpy as np
import pandas as pd
from forecast_core import BASE,WEATHER,make_examples,climatology,period_table
from predict import predict
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports/v2'
df=pd.read_csv(ROOT/'data/processed/daily_v2.csv',parse_dates=['date']).set_index('date')

# BLOCK 2 — Perturb unknown future data. Forecast features/baselines must remain identical.
# This catches target leakage rather than merely checking column names.
origin=pd.Timestamp('2023-06-30');climate=climatology(df.loc[:'2022-12-31'])
a=make_examples(df,[origin],climate)
changed=df.copy()
changed.loc[origin:,'demand_mwh']=999999999
changed.loc[origin-pd.Timedelta(days=6):,['temp','humidity']]=-999
b=make_examples(changed,[origin],climate)
pd.testing.assert_frame_equal(a[BASE+WEATHER+['repeat_week','persistence']],b[BASE+WEATHER+['repeat_week','persistence']])
print('PASS: changing unavailable demand/weather cannot change forecast inputs')

# BLOCK 3 — Confirm exact boundaries and missing-total propagation.
paths=pd.read_csv(R/'test_paths.csv',parse_dates=['origin','target'])
assert (paths.target-paths.origin).dt.days.eq(paths.horizon).all()
table=pd.read_csv(R/'test_periods.csv',parse_dates=['origin','start','end'])
assert (table.origin<table.start).all()
assert table[table.scale=='weekly'].days.eq(7).all()
monthly=table[table.scale=='monthly']
assert monthly.start.dt.is_month_start.all() and monthly.end.dt.is_month_end.all()
cal=pd.read_csv(R/'calibration_periods.csv',parse_dates=['start','end'])
missing=pd.Timestamp('2025-12-05')
affected=cal[(cal.start<=missing)&(cal.end>=missing)]
assert set(affected.scale)=={'daily','weekly','monthly'} and affected.actual.isna().all()
print('PASS: calendar periods are complete and missing actuals invalidate totals')

# BLOCK 4 — Independently reconstruct winners from development folds only.
cv=pd.read_csv(R/'cross_validation_metrics.csv')
rank=cv.groupby(['scale','model']).relative_mae.mean().reset_index()
expected=rank.loc[rank.groupby('scale').relative_mae.idxmin()].set_index('scale').model.to_dict()
actual=json.loads((R/'frozen_selection.json').read_text())['models']
assert actual==expected
selected=pd.read_csv(R/'selected_forecasts.csv')
summary=pd.read_csv(R/'management_scorecard.csv')
for row in summary.itertuples():
    g=selected[selected.scale==row.scale].dropna(subset=['actual'])
    assert row.model==expected[row.scale]
    assert np.isclose(abs(g.prediction-g.actual).mean(),row.mae_mwh)
print('PASS: model choices and reported MAE reproduce from recorded evidence')

# BLOCK 5 — Verify inference, coherent accounting and refusal of stale/duplicate inputs.
with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp)
    artifact=ROOT/'models/v2/forecast_bundle.joblib'
    source=ROOT/'data/processed/daily_v2.csv'
    predict(artifact,source,'2026-08-31',temp/'valid')
    daily=pd.read_csv(temp/'valid/daily_path.csv');weekly=pd.read_csv(temp/'valid/coherent_weekly.csv');monthly=pd.read_csv(temp/'valid/coherent_monthly.csv')
    assert len(daily)==31
    assert np.isclose(daily.coherent_daily_mwh.sum(),weekly.forecast_mwh.sum())
    assert np.isclose(daily.coherent_daily_mwh.sum(),monthly.forecast_mwh.sum())
    for failure,frame in [('stale',df.loc[:'2026-08-01']),('duplicate',pd.concat([df,df.tail(1)]))]:
        path=temp/(failure+'.csv');frame.to_csv(path)
        try: predict(artifact,path,'2026-08-31',temp/failure)
        except ValueError: pass
        else: raise AssertionError('Did not reject '+failure)
print('PASS: artifact inference reconciles and rejects stale/duplicate inputs')
print('All lifecycle verification checks passed.')
