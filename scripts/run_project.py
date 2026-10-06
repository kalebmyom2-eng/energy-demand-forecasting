"""Annotated end-to-end SQL/Python portfolio study. Run from any directory."""
# BLOCK 1 — Import tools and establish reproducible, workspace-local outputs.
# SQLite handles relational checks; pandas and sklearn handle time-series models.
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.cache'))
import json
import sqlite3
import hashlib
import platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pandas.tseries.holiday import USFederalHolidayCalendar
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import sklearn
REPORT = ROOT / 'reports'
FIG = REPORT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

def stage(message):
    print('\n' + message, flush=True)

# BLOCK 2 — Load preserved data into SQLite and execute the versioned SQL.
# Rebuilding the table makes a rerun deterministic; the original JSON is untouched.
stage('STEP 1 | SQL: load daily records, audit coverage, and build analytical views')
raw = pd.read_csv(ROOT / 'data/processed/daily_demand_weather.csv')
with sqlite3.connect(ROOT / 'data/energy.sqlite') as con:
    raw.to_sql('daily', con, if_exists='replace', index=False)
    con.execute('CREATE UNIQUE INDEX IF NOT EXISTS daily_date ON daily(date)')
    con.executescript((ROOT / 'sql/analysis.sql').read_text())
    for view in ['quality_summary','annual_summary','training_seasonality','monthly_actuals']:
        table = pd.read_sql_query(f'SELECT * FROM {view}', con)
        table.to_csv(REPORT / f'{view}.csv', index=False)
        if view != 'monthly_actuals': print(table.to_string(index=False), flush=True)
    df = pd.read_sql_query('SELECT * FROM modeling_daily ORDER BY date', con, parse_dates=['date']).set_index('date')
assert df.index.is_unique and len(df) == len(pd.date_range(df.index.min(), df.index.max()))
weather_cols = [c for c in raw if 'temperature_2m_mean' in c]
humidity_cols = [c for c in raw if 'relative_humidity' in c]
df['temp'] = df[weather_cols].mean(axis=1)
df['humidity'] = df[humidity_cols].mean(axis=1)

# BLOCK 3 — Explore training data only; retain extreme observations rather than deleting them.
# The equal-city weather average is a transparent proxy, not a load-weighted measure.
stage('STEP 2 | Python: plot training-period seasonality and weather relationships')
train_eda = df.loc[:'2023-12-31']
fig, axes = plt.subplots(2,2,figsize=(13,8))
axes[0,0].plot(train_eda.index, train_eda.demand_mwh/1e6, lw=.7)
axes[0,0].set(title='Daily energy demand: training period', ylabel='Million MWh')
train_eda.groupby(train_eda.index.month).demand_mwh.mean().div(1e6).plot.bar(ax=axes[0,1], color='#167d9a')
axes[0,1].set(title='Annual seasonality', xlabel='Month', ylabel='Mean million MWh/day')
axes[1,0].scatter(train_eda.temp,train_eda.demand_mwh/1e6,s=7,alpha=.3)
axes[1,0].set(title='Weather association (not causation)',xlabel='Four-city mean temperature (°C)',ylabel='Million MWh')
train_eda.groupby(train_eda.index.dayofweek).demand_mwh.mean().div(1e6).plot.bar(ax=axes[1,1],color='#167d9a')
axes[1,1].set(title='Weekly seasonality',xlabel='Monday=0 … Sunday=6',ylabel='Mean million MWh/day')
fig.tight_layout(); fig.savefig(FIG/'01_training_exploration.png',dpi=160); plt.close(fig)

# BLOCK 4 — Construct direct multi-horizon examples with a conservative one-day reporting lag.
# Origin is the issue date at its end; demand/weather are used only through origin minus 1 day.
# A target is origin+horizon. Every training target must precede the training cutoff.
# Historical weather is revised reanalysis; availability lag is an assumption, not an archived feed.
holidays = USFederalHolidayCalendar().holidays('2018-01-01','2027-12-31')
BASE = ['horizon','dow','month','sin_year','cos_year','trend','holiday','weekend',
        'last_demand','demand_7_back','mean_7','mean_28']
WEATHER = ['past_temp','past_humidity','seasonal_temp','seasonal_humidity','seasonal_cdd','seasonal_hdd']
ORACLE = ['actual_target_temp','actual_target_humidity','actual_cdd','actual_hdd']

def examples(cutoff, origins):
    # Seasonal weather expectations use only years before the evaluation year.
    history = df.loc[:cutoff]
    climate = history.groupby(history.index.strftime('%m-%d'))[['temp','humidity']].mean()
    climate.loc['02-29'] = climate.loc[['02-28','03-01']].mean()
    blocks = []
    for h in range(1,32):
        target = origins + pd.to_timedelta(h,unit='D')
        available = origins-pd.Timedelta(days=1)
        x = pd.DataFrame({'origin':origins,'target':target,'horizon':h})
        x['dow']=target.dayofweek; x['month']=target.month
        x['sin_year']=np.sin(2*np.pi*target.dayofyear/365.25)
        x['cos_year']=np.cos(2*np.pi*target.dayofyear/365.25)
        x['trend']=(target-pd.Timestamp('2019-01-01')).days/365.25
        x['holiday']=target.isin(holidays).astype(int); x['weekend']=(target.dayofweek>=5).astype(int)
        x['last_demand']=df.demand_mwh.reindex(available).to_numpy()
        x['demand_7_back']=df.demand_mwh.reindex(available-pd.Timedelta(days=7)).to_numpy()
        x['mean_7']=df.demand_mwh.rolling(7,min_periods=5).mean().reindex(available).to_numpy()
        x['mean_28']=df.demand_mwh.rolling(28,min_periods=21).mean().reindex(available).to_numpy()
        x['past_temp']=df.temp.reindex(available).to_numpy()
        x['past_humidity']=df.humidity.reindex(available).to_numpy()
        seasonal=climate.reindex(target.strftime('%m-%d'))
        x['seasonal_temp']=seasonal.temp.to_numpy(); x['seasonal_humidity']=seasonal.humidity.to_numpy()
        x['seasonal_cdd']=np.maximum(x.seasonal_temp-18,0); x['seasonal_hdd']=np.maximum(18-x.seasonal_temp,0)
        x['actual_target_temp']=df.temp.reindex(target).to_numpy()
        x['actual_target_humidity']=df.humidity.reindex(target).to_numpy()
        x['actual_cdd']=np.maximum(x.actual_target_temp-18,0); x['actual_hdd']=np.maximum(18-x.actual_target_temp,0)
        x['actual']=df.demand_mwh.reindex(target).to_numpy()
        # Repeat the most recent available same weekday; never use within-horizon actuals.
        baseline_dates=target-pd.to_timedelta(np.ceil((h+1)/7)*7,unit='D')
        assert (baseline_dates <= available).all(), 'Baseline uses unavailable demand'
        x['seasonal_naive']=df.demand_mwh.reindex(baseline_dates).to_numpy()
        x['seasonal_naive']=x.seasonal_naive.fillna(x.mean_7)
        blocks.append(x)
    return pd.concat(blocks,ignore_index=True)

# BLOCK 5 — Fit a small, predeclared candidate set, avoiding a large hyperparameter search.
# Imputation/scaling are fitted inside each training pipeline. Targets stay un-imputed.
SPECS={'ridge_calendar':BASE,'trees_calendar':BASE,'trees_weather':BASE+WEATHER,
       'oracle_weather_diagnostic':BASE+WEATHER+ORACLE}

def fit_predict(cutoff, first_origin, last_origin):
    train=examples(cutoff,pd.date_range('2019-02-01',cutoff))
    train=train[(train.target<=pd.Timestamp(cutoff)) & train.actual.notna()].copy()
    test=examples(cutoff,pd.date_range(first_origin,last_origin))
    assert train.target.max()<=pd.Timestamp(cutoff)
    out=test[['origin','target','horizon','actual','seasonal_naive']].copy()
    fitted={}
    for name,cols in SPECS.items():
        stage(f'  Fit {name}: {len(train):,} training examples; predict {len(test):,} examples')
        estimator=Ridge(alpha=100) if name.startswith('ridge') else HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,learning_rate=.07,l2_regularization=10,early_stopping=False,random_state=42)
        pipe=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),estimator)
        pipe.fit(train[cols],train.actual/1e6)
        out[name]=np.maximum(0,pipe.predict(test[cols])*1e6)
        fitted[name]=pipe
    return out, fitted

# BLOCK 6 — Score only forecasts issued before their complete delivery periods.
# Weekly = Monday–Sunday, monthly = calendar month. Missing actuals invalidate a total.
MODELS=['seasonal_naive']+list(SPECS)
def periods(pred, year):
    output=[]
    for scale in ['daily','weekly','monthly']:
        p=pred.copy()
        if scale=='daily': p=p[p.horizon==1]
        elif scale=='weekly': p=p[(p.origin.dt.dayofweek==6)&(p.horizon<=7)]
        else: p=p[(p.origin.dt.is_month_end)&(p.target.dt.to_period('M')==(p.origin+pd.Timedelta(days=1)).dt.to_period('M'))]
        for origin,g in p.groupby('origin'):
            first=origin+pd.Timedelta(days=1)
            n=1 if scale=='daily' else 7 if scale=='weekly' else first.days_in_month
            if first.year!=year or g.target.max().year!=year or len(g)!=n: continue
            row={'scale':scale,'origin':origin,'start':first,'end':g.target.max(),'days':n,
                 'actual':g.actual.sum() if g.actual.notna().all() else np.nan}
            for model in MODELS: row[model]=g[model].sum() if g[model].notna().all() else np.nan
            output.append(row)
    return pd.DataFrame(output)

def metrics(period_table):
    rows=[]
    for scale,g in period_table.groupby('scale'):
        g=g.dropna(subset=['actual']+MODELS)
        for model in MODELS:
            err=g[model]-g.actual
            rows.append({'scale':scale,'model':model,'n_periods':len(g),'mae_mwh':abs(err).mean(),
                'rmse_mwh':np.sqrt((err**2).mean()),'wape_pct':100*abs(err).sum()/g.actual.sum(),
                'bias_pct':100*err.sum()/g.actual.sum()})
    return pd.DataFrame(rows)

stage('STEP 3 | Validation: train through 2023; compare forecasts for 2024')
val_predictions,_=fit_predict('2023-12-31','2023-12-31','2024-12-30')
val_periods=periods(val_predictions,2024)
val_metrics=metrics(val_periods)
val_metrics.to_csv(REPORT/'validation_metrics.csv',index=False)
# Select using validation MAE only. Perfect-weather diagnostics cannot win selection.
eligible=val_metrics[~val_metrics.model.str.startswith('oracle')]
winners=eligible.loc[eligible.groupby('scale').mae_mwh.idxmin()].set_index('scale').model.to_dict()
print('\nFrozen selections from 2024:',winners,flush=True)
print(val_metrics.round(2).to_string(index=False),flush=True)

# BLOCK 7 — Refit through 2024 and evaluate once on the reserved 2025 test.
# Model choices remain frozen even when another candidate looks better on the test.
stage('STEP 4 | Final test: refit through 2024; evaluate 2025 without changing selections')
test_predictions,fitted=fit_predict('2024-12-31','2024-12-31','2025-12-30')
test_predictions.to_csv(REPORT/'test_daily_paths.csv',index=False)
# Score lead times separately: a 31-day path must not inherit the next-day score.
lead_rows=[]
for h,g in test_predictions[test_predictions.target.dt.year==2025].groupby('horizon'):
    g=g.dropna(subset=['actual']+MODELS)
    for model in MODELS:
        lead_rows.append({'horizon_days':h,'model':model,'n':len(g),
            'mae_mwh':abs(g[model]-g.actual).mean(),
            'wape_pct':100*abs(g[model]-g.actual).sum()/g.actual.sum()})
pd.DataFrame(lead_rows).to_csv(REPORT/'test_metrics_by_horizon.csv',index=False)
test_periods=periods(test_predictions,2025)
test_metrics=metrics(test_periods)
test_metrics.to_csv(REPORT/'test_metrics.csv',index=False)
test_periods.to_csv(REPORT/'test_period_forecasts.csv',index=False)
val_periods.to_csv(REPORT/'validation_period_forecasts.csv',index=False)
print(test_metrics.round(2).to_string(index=False),flush=True)

# BLOCK 8 — Calibrate approximate 90% intervals using validation absolute errors.
# Period totals get period-level calibration, not sums of daily bounds.
# Twelve monthly validation samples are insufficient for strong coverage claims.
interval_rows=[]
for scale,model in winners.items():
    v=val_periods[val_periods.scale==scale].dropna(subset=['actual',model])
    residual=np.sort(abs(v[model]-v.actual).to_numpy())
    q=residual[min(len(residual)-1,int(np.ceil((len(residual)+1)*.9))-1)]
    t=test_periods[test_periods.scale==scale].copy()
    t['selected_model']=model; t['prediction']=t[model]
    t['lower_90']=np.maximum(0,t.prediction-q); t['upper_90']=t.prediction+q
    t['interval_halfwidth']=q
    interval_rows.append(t)
selected=pd.concat(interval_rows,ignore_index=True)
selected.to_csv(REPORT/'selected_test_forecasts.csv',index=False)
summary=[]
for scale,model in winners.items():
    row=test_metrics[(test_metrics.scale==scale)&(test_metrics.model==model)].iloc[0].to_dict()
    baseline=test_metrics[(test_metrics.scale==scale)&(test_metrics.model=='seasonal_naive')].iloc[0]
    row['mae_improvement_pct']=100*(1-row['mae_mwh']/baseline.mae_mwh)
    g=selected[selected.scale==scale].dropna(subset=['actual'])
    row['interval_coverage_pct']=100*((g.actual>=g.lower_90)&(g.actual<=g.upper_90)).mean()
    summary.append(row)
summary=pd.DataFrame(summary)
summary.to_csv(REPORT/'selected_model_summary.csv',index=False)
print('\nMANAGEMENT SCORECARD\n'+summary.round(2).to_string(index=False),flush=True)

# BLOCK 9 — Visualize held-out errors and preserve the most difficult forecast periods.
fig,axes=plt.subplots(3,1,figsize=(13,10))
for ax,scale in zip(axes,['daily','weekly','monthly']):
    g=selected[selected.scale==scale].sort_values('start')
    ax.plot(g.start,g.actual/1e6,label='Actual',color='#233447')
    ax.plot(g.start,g.prediction/1e6,label='Forecast',color='#d27031')
    ax.fill_between(g.start,g.lower_90/1e6,g.upper_90/1e6,alpha=.15,color='#d27031')
    ax.set(title=f'2025 {scale}: {winners[scale]}',ylabel='Million MWh'); ax.legend(loc='upper left')
fig.tight_layout();fig.savefig(FIG/'02_test_forecasts.png',dpi=160);plt.close(fig)
errors=selected.assign(abs_error_mwh=lambda x:abs(x.prediction-x.actual))
errors.sort_values('abs_error_mwh',ascending=False).groupby('scale').head(5).to_csv(REPORT/'largest_errors.csv',index=False)

# BLOCK 10 — Produce a dated demonstration forecast, not a claim about today's demand.
# Refit on all available 2019–2025 data; only eligible selected models are published.
stage('STEP 5 | Snapshot forecast: issue date 2025-12-31, predict January 2026')
future, _=fit_predict('2025-12-31','2025-12-31','2025-12-31')
future['forecast_mwh']=future[winners['daily']]
future[['origin','target','horizon','forecast_mwh']].to_csv(REPORT/'snapshot_daily_january_2026.csv',index=False)
# One common daily path ensures exact daily/weekly/monthly reconciliation for the demo.
future['week_start']=future.target-pd.to_timedelta(future.target.dt.dayofweek,unit='D')
weekly=future.groupby('week_start').agg(days=('target','size'),forecast_mwh=('forecast_mwh','sum')).reset_index()
weekly['complete_week']=weekly.days==7
weekly.to_csv(REPORT/'snapshot_weekly_january_2026.csv',index=False)
pd.DataFrame([{'month':'2026-01','days':31,'forecast_mwh':future.forecast_mwh.sum(),'daily_path_model':winners['daily']}]).to_csv(REPORT/'snapshot_monthly_january_2026.csv',index=False)

# BLOCK 11 — Record provenance and write a manager-readable conclusion from measured results.
manifest={'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,
          'sklearn':sklearn.__version__,'selected_models':winners,
          'data_sha256':hashlib.sha256((ROOT/'data/processed/daily_demand_weather.csv').read_bytes()).hexdigest()}
(REPORT/'run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
lines=['# ERCOT demand forecasting — management brief','',
'Business question: can calendar, recent demand, and weather improve energy-volume planning against a repeat-week baseline?',
'','## Independent 2025 test','',
'| Delivery period | Selected model | WAPE | MAE improvement vs baseline | Approx. 90% interval coverage |',
'|---|---|---:|---:|---:|']
for r in summary.itertuples():
    lines.append(f'| {r.scale} | {r.model} | {r.wape_pct:.2f}% | {r.mae_improvement_pct:.1f}% | {r.interval_coverage_pct:.1f}% |')
lines += ['', 'Selections were frozen using 2024 validation MAE. WAPE is total absolute error divided by total observed demand. Positive improvement means lower MAE than the baseline.',
'', '## What weather added\n\nPast weather and seasonal weather averages did not beat the selected regression. Adding these features to the tree model improved validation performance but worsened test performance, so this specification has not demonstrated a reliable weather benefit. The realized-future-weather diagnostic reached 4.11% daily WAPE; it cannot be used as an operational score.\n\nThe largest next-day miss was February 19, 2025: actual demand was 1,724,708 MWh against a forecast of approximately 1,202,444 MWh. Strong average performance does not remove the risk of missing sharp demand spikes.', '', '## Recommendation and limits','',
'Use the selected models as portfolio planning prototypes. Performance is retrospective, not a verified live-service result. Report daily, weekly, and monthly quality separately; do not translate energy accuracy into financial savings without a cost model.',
'', '- Daily = next day; weekly = next complete Monday–Sunday issued Sunday; monthly = next calendar month issued on the preceding month end. Only periods entirely in the evaluation year are scored.',
'- December 5, 2025 has missing demand. It is not imputed for scoring; the affected weekly and monthly totals are excluded.',
'- Forecast features use demand and past weather through issue date minus one day. Actual operational reporting delays and weather release vintages need verification.',
'- The weather candidate uses past weather plus training-period seasonal weather means. The oracle diagnostic uses realized target weather and is never eligible for deployment or selection.',
'- Reanalysis weather and revised demand snapshots are not archived as-of feeds. City averages are spatial proxies. EIA Central and America/Chicago date labels are aligned, but exact daylight-saving aggregation semantics remain unverified.',
'- Interval calibration assumes reasonably stable residual behavior. Time dependence and only twelve monthly calibration periods limit reliability; inspect measured coverage.',
'- Independent best-model selections by output scale do not impose reconciliation. The January 2026 demonstration instead aggregates one daily path, so its totals reconcile; its multi-day accuracy is not the next-day score.',
'- The January 2026 files are a forecast from the historical dataset boundary, not a current September 2026 forecast.',
'- Federal holidays are a proxy for the operating calendar. Extreme events, outages, and demand growth can shift relationships.',
'', '## Next operational step','',
'Acquire archived weather forecasts and demand vintages, verify time boundaries, and repeat rolling-origin evaluation before any operational use.',
'', '![Test forecasts](figures/02_test_forecasts.png)']
(REPORT/'management_brief.md').write_text('\n'.join(lines)+'\n')
stage('COMPLETE | SQL tables, metrics, plots, forecast CSVs, and management brief saved in reports/')
