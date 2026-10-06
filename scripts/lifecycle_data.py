"""CRISP-DM phases 2–3: audit, curate and integrate preserved source snapshots."""
# BLOCK 1 — Locate the project; keep version 1 snapshots and results intact.
from pathlib import Path
import json
import sqlite3
import hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/v2'
CITIES=['houston','dallas','austin','san_antonio']

def prepare():
    # BLOCK 2 — Validate keys, units and completeness before transformations.
    demand_payload=json.loads((ROOT/'data/raw/v2/eia.json').read_text())
    response=demand_payload['response']; demand=pd.DataFrame(response['data'])
    assert len(demand)==int(response['total']), 'API pagination incomplete'
    assert not demand.period.duplicated().any(), 'Duplicate demand keys'
    for col,value in [('respondent','ERCO'),('type','D'),('timezone','Central'),('value-units','megawatthours')]:
        assert demand[col].eq(value).all(), f'Unexpected {col}'
    demand=demand.rename(columns={'period':'date','value':'demand_mwh'})[['date','demand_mwh']]
    demand['demand_mwh']=pd.to_numeric(demand.demand_mwh,errors='coerce')
    issues=[]
    invalid=demand.demand_mwh.notna() & (demand.demand_mwh<=0)
    for date in demand.loc[invalid,'date']: issues.append({'date':date,'field':'demand_mwh','action':'set NULL','reason':'nonpositive value'})
    demand.loc[invalid,'demand_mwh']=np.nan
    weather_payload=json.loads((ROOT/'data/raw/v2/weather.json').read_text())
    assert len(weather_payload)==4
    weather=[]
    for city,payload in zip(CITIES,weather_payload):
        assert payload['timezone']=='America/Chicago'
        assert payload['daily_units']['temperature_2m_mean']=='°C'
        assert payload['daily_units']['relative_humidity_2m_mean']=='%'
        w=pd.DataFrame(payload['daily']).rename(columns={'time':'date','temperature_2m_mean':'temp_mean',
            'temperature_2m_min':'temp_min','temperature_2m_max':'temp_max','relative_humidity_2m_mean':'humidity'})
        assert not w.date.duplicated().any()
        w['city']=city
        for field,low,high in [('temp_mean',-90,65),('temp_min',-90,65),('temp_max',-90,65),('humidity',0,100)]:
            bad=w[field].notna() & ~w[field].between(low,high)
            for date in w.loc[bad,'date']: issues.append({'date':date,'field':city+'_'+field,'action':'set NULL','reason':'outside physical range'})
            w.loc[bad,field]=np.nan
        ordering=w.temp_min.gt(w.temp_mean)|w.temp_mean.gt(w.temp_max)
        for date in w.loc[ordering,'date']: issues.append({'date':date,'field':city+'_temperature','action':'set NULL','reason':'min/mean/max ordering'})
        w.loc[ordering,['temp_min','temp_mean','temp_max']]=np.nan
        weather.append(w)
    weather=pd.concat(weather,ignore_index=True)
    calendar=pd.DataFrame({'date':pd.date_range('2019-01-01','2026-08-31').strftime('%Y-%m-%d')})
    assert set(demand.date)<=set(calendar.date)
    assert all(set(g.date)==set(calendar.date) for _,g in weather.groupby('city'))

    # BLOCK 3 — Normalize into SQLite, then join through a calendar spine using SQL.
    # Database key constraints prevent fan-out duplicates that could inflate totals.
    with sqlite3.connect(ROOT/'data/energy_v2.sqlite') as con:
        for name,frame in [('calendar',calendar),('demand',demand),('weather',weather)]:
            frame.to_sql(name,con,if_exists='replace',index=False)
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS demand_key ON demand(date)')
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS weather_key ON weather(date,city)')
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS calendar_key ON calendar(date)')
        con.executescript((ROOT/'sql/lifecycle_v2.sql').read_text())
        df=pd.read_sql_query('SELECT * FROM daily_features ORDER BY date',con,parse_dates=['date']).set_index('date')
        for name in ['yearly_quality','complete_months','development_seasonality']:
            out=pd.read_sql_query('SELECT * FROM '+name,con)
            out.to_csv(REPORT/(name+'.csv'),index=False)
            if name=='yearly_quality': print(out.to_string(index=False),flush=True)
    df.to_csv(ROOT/'data/processed/daily_v2.csv')
    for date in df.index[df.demand_mwh.isna()]:
        issues.append({'date':str(date.date()),'field':'demand_mwh','action':'retain NULL; exclude target from scoring','reason':'missing target'})
    pd.DataFrame(issues,columns=['date','field','action','reason']).to_csv(REPORT/'cleaning_log.csv',index=False)

    # BLOCK 4 — Profile every field and record source revisions separately from cleaning.
    profiles=[]
    for name,series in df.items():
        profiles.append({'column':name,'dtype':str(series.dtype),'rows':len(series),'missing':int(series.isna().sum()),
            'min':series.min(),'max':series.max(),'mean':series.mean(),'std':series.std()})
    pd.DataFrame(profiles).to_csv(REPORT/'data_profile.csv',index=False)
    old=pd.read_csv(ROOT/'data/processed/daily_demand_weather.csv',parse_dates=['date']).set_index('date').demand_mwh
    comparison=pd.concat([old.rename('v1'),df.demand_mwh.reindex(old.index).rename('v2')],axis=1)
    same=np.isclose(comparison.v1,comparison.v2,equal_nan=True)
    comparison[~same].to_csv(REPORT/'source_revisions.csv')
    manifest={'retrieved':'2026-09-28','dates':len(df),'observed_demand':int(df.demand_mwh.count()),
        'missing_demand_dates':df.index[df.demand_mwh.isna()].strftime('%Y-%m-%d').tolist(),
        'overlap_revisions':int((~same).sum()),'raw_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/raw/v2').glob('*.json')}}
    (REPORT/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Data audit:',json.dumps(manifest),flush=True)
    return df

if __name__=='__main__': prepare()
