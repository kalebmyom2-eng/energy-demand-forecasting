"""Batch inference from a trusted, locally created model artifact; no retraining."""
# BLOCK 1 — Parse explicit inputs so the issue date and artifact vintage cannot be hidden.
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from forecast_core import predict_bundle,period_table
ROOT=Path(__file__).resolve().parents[1]

def predict(artifact,input_path,origin,output):
    # BLOCK 2 — Reject stale, duplicate, non-contiguous or future-contaminated inference data.
    # Load only artifacts you created/trust: joblib is a Python object format.
    bundle=joblib.load(artifact)
    origin=pd.Timestamp(origin)
    if origin<pd.Timestamp(bundle['cutoff']): raise ValueError('Artifact was trained after this issue date')
    if origin.year>=2035: raise ValueError('Holiday calendar must be extended for this issue date')
    df=pd.read_csv(input_path,parse_dates=['date']).set_index('date').sort_index()
    if not df.index.is_unique: raise ValueError('Duplicate input dates')
    required={'demand_mwh','temp','humidity'}
    if not required<=set(df): raise ValueError('Missing required input columns')
    df=df.loc[:origin]
    if df.empty or df.index.max()<origin-pd.Timedelta(days=1): raise ValueError('Stale demand inputs')
    if len(df)<35 or len(df)!=len(pd.date_range(df.index.min(),df.index.max())): raise ValueError('Need a continuous history with at least 35 calendar days')
    known=origin-pd.Timedelta(days=1); weather_known=origin-pd.Timedelta(days=7)
    if pd.isna(df.demand_mwh.get(known)): raise ValueError('Latest available demand is missing; review before publishing')
    if df.reindex([weather_known])[['temp','humidity']].isna().any().any(): raise ValueError('Required lagged weather is missing')
    if (df.demand_mwh.dropna()<=0).any(): raise ValueError('Nonpositive demand in input')

    # BLOCK 3 — Predict a full path, retaining the issue date and each model's identity.
    paths=predict_bundle(bundle,df,[origin])
    daily_name=bundle['winners']['daily']
    paths['coherent_daily_mwh']=paths[daily_name]
    if not np.isfinite(paths.coherent_daily_mwh).all(): raise ValueError('Nonfinite predictions')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    cols=['origin','target','horizon','coherent_daily_mwh']
    paths[cols].to_csv(output/'daily_path.csv',index=False)
    # BLOCK 4 — Coherent totals share one daily model; they are not separately optimized products.
    paths['week_start']=paths.target-pd.to_timedelta(paths.target.dt.dayofweek,unit='D')
    paths['month']=paths.target.dt.to_period('M').astype(str)
    weeks=paths.groupby('week_start').agg(days=('target','size'),forecast_mwh=('coherent_daily_mwh','sum')).reset_index()
    weeks['complete_period']=weeks.days.eq(7)
    weeks.to_csv(output/'coherent_weekly.csv',index=False)
    months=paths.groupby('month').agg(days=('target','size'),forecast_mwh=('coherent_daily_mwh','sum')).reset_index()
    months['complete_period']=[n==pd.Period(m,'M').days_in_month for m,n in zip(months.month,months.days)]
    months.to_csv(output/'coherent_monthly.csv',index=False)
    # BLOCK 5 — Publish independently selected products only on their evaluated issue schedule.
    # Weekly runs on Sunday; monthly on month end. This preserves the backtest definition.
    products=period_table(paths,origin+pd.Timedelta(days=1),origin+pd.Timedelta(days=31))
    rows=[]
    for row in products.itertuples():
        name=bundle['winners'][row.scale];value=getattr(row,name);width=bundle['interval_widths'][row.scale]
        rows.append({'scale':row.scale,'origin':origin,'start':row.start,'end':row.end,'model':name,
            'forecast_mwh':value,'lower90':max(0,value-width),'upper90':value+width})
    pd.DataFrame(rows).to_csv(output/'selected_products.csv',index=False)
    metadata={'issue_date':str(origin.date()),'trained_through':bundle['cutoff'],'coherent_path_model':daily_name,
        'product_models':bundle['winners'],'note':'Historical-snapshot demonstration. Coherent path totals and independently selected products differ by design. Partial periods are labeled. Intervals are calibrated on 2025, not a coverage guarantee.'}
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('Saved daily path, coherent aggregates, scheduled selected products and metadata to',output)
    return paths

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path,default=ROOT/'models/v2/forecast_bundle.joblib')
    parser.add_argument('--input',type=Path,default=ROOT/'data/processed/daily_v2.csv')
    parser.add_argument('--origin',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/v2/inference_demo')
    args=parser.parse_args()
    predict(args.artifact,args.input,args.origin,args.output)
