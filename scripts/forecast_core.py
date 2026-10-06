"""Reusable forecasting functions. Importing this module never trains a model."""
# BLOCK 1 — Declare the data contract and deterministic candidate set.
# Small, predeclared searches reduce selection noise on a short annual series.
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

BASE=['horizon','trend','holiday','weekend','latest','lag7','mean7','mean28','std7','recent_change','decayed_change']
BASE += [f'dow_{i}' for i in range(1,7)]
BASE += [f'{trig}_{k}' for k in range(1,4) for trig in ['sin','cos']]
WEATHER=['past_temp','past_humidity','climate_temp','climate_humidity','cdd','hdd','temperature_anomaly_decay']
SPECS={f'ridge_{alpha}_{suffix}':{'kind':'ridge','alpha':alpha,'weather':suffix=='weather'}
       for alpha in [1,100] for suffix in ['calendar','weather']}
SPECS.update({f'trees_{suffix}':{'kind':'trees','weather':suffix=='weather'} for suffix in ['calendar','weather']})
BASELINES=['repeat_week','persistence']
ALL_MODELS=BASELINES+list(SPECS)
HOLIDAYS=USFederalHolidayCalendar().holidays('2018-01-01','2035-12-31')

def climatology(history):
    """Fit month/day weather expectations on the training snapshot only."""
    out=history.groupby(history.index.strftime('%m-%d'))[['temp','humidity']].mean()
    out.loc['02-29']=out.loc[['02-28','03-01']].mean()
    return out

# BLOCK 2 — Build direct forecast examples with explicit information cutoffs.
# Demand is available through origin-1; reanalysis weather is conservatively lagged 7 days.
# No feature reads target demand or target realized weather.
def make_examples(df,origins,climate):
    origins=pd.DatetimeIndex(origins)
    y=df.demand_mwh
    roll7=y.rolling(7,min_periods=5).mean()
    roll28=y.rolling(28,min_periods=21).mean()
    std7=y.rolling(7,min_periods=5).std()
    blocks=[]
    for h in range(1,32):
        targets=origins+pd.Timedelta(days=h)
        known=origins-pd.Timedelta(days=1)
        weather_known=origins-pd.Timedelta(days=7)
        x=pd.DataFrame({'origin':origins,'target':targets,'horizon':h})
        x['trend']=(targets-pd.Timestamp('2019-01-01')).days/365.25
        x['holiday']=targets.isin(HOLIDAYS).astype(int)
        x['weekend']=(targets.dayofweek>=5).astype(int)
        for i in range(1,7): x[f'dow_{i}']=(targets.dayofweek==i).astype(int)
        for k in range(1,4):
            x[f'sin_{k}']=np.sin(2*np.pi*k*targets.dayofyear/365.25)
            x[f'cos_{k}']=np.cos(2*np.pi*k*targets.dayofyear/365.25)
        for name,series,dates in [('latest',y,known),('lag7',y,known-pd.Timedelta(days=7)),
                                  ('mean7',roll7,known),('mean28',roll28,known),('std7',std7,known)]:
            x[name]=series.reindex(dates).to_numpy()
        x['recent_change']=x.latest-x.mean28
        x['decayed_change']=x.recent_change*np.exp(-h/7)
        x['past_temp']=df.temp.reindex(weather_known).to_numpy()
        x['past_humidity']=df.humidity.reindex(weather_known).to_numpy()
        normal=climate.reindex(targets.strftime('%m-%d'))
        x['climate_temp']=normal.temp.to_numpy(); x['climate_humidity']=normal.humidity.to_numpy()
        x['cdd']=np.maximum(x.climate_temp-18,0); x['hdd']=np.maximum(18-x.climate_temp,0)
        x['temperature_anomaly_decay']=(x.past_temp-x.climate_temp)*np.exp(-h/7)
        previous_weekday=targets-pd.to_timedelta(int(np.ceil((h+1)/7))*7,unit='D')
        assert (previous_weekday<=known).all()
        x['repeat_week']=y.reindex(previous_weekday).to_numpy()
        x['repeat_week']=x.repeat_week.fillna(x.mean7)
        x['persistence']=x.latest.fillna(x.mean7)
        x['actual']=y.reindex(targets).to_numpy()
        blocks.append(x)
    return pd.concat(blocks,ignore_index=True)

# BLOCK 3 — Fit all preprocessing inside the training partition and save it with the model.
# Target values remain missing rather than being imputed. Scaling is learned, never global.
def fit_bundle(df,cutoff,names=None,announce=print):
    history=df.loc[:cutoff]
    climate=climatology(history)
    train=make_examples(history,pd.date_range('2019-02-01',cutoff),climate)
    train=train[(train.target<=pd.Timestamp(cutoff)) & train.actual.notna()]
    names=list(SPECS) if names is None else [n for n in names if n in SPECS]
    bundle={'cutoff':str(cutoff),'climate':climate,'models':{},'columns':{},'demand_lag_days':1,'weather_lag_days':7}
    train_scores=[]
    for name in names:
        spec=SPECS[name]; columns=BASE+(WEATHER if spec['weather'] else [])
        estimator=Ridge(alpha=spec['alpha']) if spec['kind']=='ridge' else HistGradientBoostingRegressor(
            max_iter=100,max_leaf_nodes=15,learning_rate=.07,l2_regularization=10,early_stopping=False,random_state=42)
        pipe=make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),estimator)
        announce(f'    Fit {name}: {len(train):,} origin/target examples through {cutoff}')
        pipe.fit(train[columns],train.actual/1e6)
        bundle['models'][name]=pipe; bundle['columns'][name]=columns
        one=train[train.horizon==1]
        error=pipe.predict(one[columns])*1e6-one.actual
        train_scores.append({'model':name,'training_daily_mae':abs(error).mean(),'n':len(one)})
    return bundle,pd.DataFrame(train_scores)

def predict_bundle(bundle,df,origins):
    """Predict from a fitted artifact without updating parameters or climatology."""
    x=make_examples(df,origins,bundle['climate'])
    out=x[['origin','target','horizon','actual']+BASELINES].copy()
    for name,pipe in bundle['models'].items():
        out[name]=np.maximum(0,pipe.predict(x[bundle['columns'][name]])*1e6)
    return out

# BLOCK 4 — Aggregate one issue date's forecasts into complete delivery periods.
# Actuals are NULL when any day is absent; no sum hides a missing observation.
def period_table(paths,start,end):
    names=[n for n in ALL_MODELS if n in paths]
    rows=[]
    for scale in ['daily','weekly','monthly']:
        if scale=='daily': p=paths[paths.horizon==1]
        elif scale=='weekly': p=paths[(paths.origin.dt.dayofweek==6)&(paths.horizon<=7)]
        else: p=paths[paths.origin.dt.is_month_end & (paths.target.dt.to_period('M')==(paths.origin+pd.Timedelta(days=1)).dt.to_period('M'))]
        for origin,g in p.groupby('origin'):
            first=origin+pd.Timedelta(days=1)
            n=1 if scale=='daily' else 7 if scale=='weekly' else first.days_in_month
            if len(g)!=n or first<pd.Timestamp(start) or g.target.max()>pd.Timestamp(end): continue
            row={'scale':scale,'origin':origin,'start':first,'end':g.target.max(),'days':n,
                 'actual':g.actual.sum() if g.actual.notna().all() else np.nan}
            for name in names: row[name]=g[name].sum() if g[name].notna().all() else np.nan
            rows.append(row)
    return pd.DataFrame(rows)

def score(table,names=None):
    """Compare candidates on the same observed periods within each scale."""
    names=[n for n in ALL_MODELS if n in table] if names is None else names
    rows=[]
    for scale,g in table.groupby('scale'):
        g=g.dropna(subset=['actual']+names)
        for name in names:
            error=g[name]-g.actual
            rows.append({'scale':scale,'model':name,'n':len(g),'mae_mwh':abs(error).mean(),
                'rmse_mwh':np.sqrt((error**2).mean()),'wape_pct':100*abs(error).sum()/g.actual.sum(),
                'bias_pct':100*error.sum()/g.actual.sum()})
    return pd.DataFrame(rows)
