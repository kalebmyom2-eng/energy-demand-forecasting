"""Run all six CRISP-DM phases with visible stage output and versioned evidence."""
# PHASE 1 — Load the already-written protocol before running any new model experiment.
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME',str(ROOT/'.cache'))
os.environ.setdefault('LOKY_MAX_CPU_COUNT','4')
import json
import hashlib
import platform
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sklearn
from lifecycle_data import prepare
from forecast_core import BASE,WEATHER,ALL_MODELS,SPECS,fit_bundle,predict_bundle,period_table,score
R=ROOT/'reports/v2'; F=R/'figures'

def stage(message): print('\n'+message,flush=True)

def experiment(df,cutoff,start,end,names=None):
    # Fit once at each fold boundary; later origins update features, not parameters.
    bundle,train_scores=fit_bundle(df,cutoff,names,stage)
    paths=predict_bundle(bundle,df,pd.date_range(pd.Timestamp(start)-pd.Timedelta(days=1),pd.Timestamp(end)-pd.Timedelta(days=1)))
    periods=period_table(paths,start,end)
    return bundle,train_scores,paths,periods,score(periods)

def run():
    stage('PHASE 1/6 | BUSINESS UNDERSTANDING: read fixed protocol and proposed acceptance criteria')
    protocol=ROOT/'docs/EXPERIMENT_PROTOCOL_V2.md'
    print('Protocol:',protocol,flush=True)
    protocol_hash=hashlib.sha256(protocol.read_bytes()).hexdigest()

    # PHASES 2–3 — Validate and integrate data; characterize development data only.
    stage('PHASE 2/6 | DATA UNDERSTANDING: schema, units, missingness, revisions and SQL joins')
    df=prepare()
    stage('PHASE 3/6 | PREPARATION: retain unknown targets; flag unusual values without deletion')
    dev=df.loc[:'2023-12-31'].copy()
    dev.describe(percentiles=[.01,.05,.5,.95,.99]).to_csv(R/'development_distribution.csv')
    median=dev.demand_mwh.rolling(28,min_periods=14).median().shift(1)
    deviation=(dev.demand_mwh-median).abs()
    robust_scale=deviation.rolling(56,min_periods=28).median().shift(1)*1.4826
    flagged=dev[deviation>6*robust_scale].copy()
    flagged['reason']='more than six rolling robust scales from prior median; retained'
    flagged.to_csv(R/'development_outlier_flags.csv')
    fig,axes=plt.subplots(2,2,figsize=(13,8))
    axes[0,0].plot(dev.index,dev.demand_mwh/1e6,lw=.7);axes[0,0].set(title='Development demand only (2019–2023)',ylabel='Million MWh')
    dev.demand_mwh.div(1e6).hist(bins=35,ax=axes[0,1],color='#167d9a');axes[0,1].set(title='Demand distribution',xlabel='Million MWh')
    axes[1,0].scatter(dev.temp,dev.demand_mwh/1e6,s=5,alpha=.3);axes[1,0].set(title='Weather association',xlabel='Temperature °C',ylabel='Million MWh')
    dev.groupby(dev.index.month).demand_mwh.mean().div(1e6).plot.bar(ax=axes[1,1],color='#167d9a');axes[1,1].set(title='Seasonal pattern',xlabel='Month',ylabel='Mean million MWh/day')
    fig.tight_layout();fig.savefig(F/'01_data_understanding.png',dpi=150);plt.close(fig)
    acf=pd.DataFrame({'lag_days':range(1,61),'demand_autocorrelation':[dev.demand_mwh.autocorr(i) for i in range(1,61)]})
    acf.to_csv(R/'development_autocorrelation.csv',index=False)

    # PHASE 4 — Tune only on two expanding development folds, then freeze winners.
    stage('PHASE 4/6 | MODELING: expanding folds 2022 and 2023; no random split')
    fold_metrics=[]; train_metrics=[]
    for year in [2022,2023]:
        _,train,_,_,metrics=experiment(df,f'{year-1}-12-31',f'{year}-01-01',f'{year}-12-31')
        metrics['fold']=year; train['fold']=year
        baseline=metrics[metrics.model=='repeat_week'].set_index('scale').mae_mwh
        metrics['relative_mae']=metrics.mae_mwh/metrics.scale.map(baseline)
        fold_metrics.append(metrics);train_metrics.append(train)
    folds=pd.concat(fold_metrics,ignore_index=True)
    folds.to_csv(R/'cross_validation_metrics.csv',index=False)
    training=pd.concat(train_metrics)
    training.to_csv(R/'training_metrics.csv',index=False)
    gaps=folds[folds.scale=='daily'].merge(training,on=['model','fold'],suffixes=('_validation','_training'))
    gaps['validation_to_training_mae']=gaps.mae_mwh/gaps.training_daily_mae
    gaps.to_csv(R/'train_validation_gap.csv',index=False)
    ranking=folds.groupby(['scale','model']).agg(mean_relative_mae=('relative_mae','mean'),worst_relative_mae=('relative_mae','max')).reset_index()
    ranking.to_csv(R/'candidate_ranking.csv',index=False)
    winners=ranking.loc[ranking.groupby('scale').mean_relative_mae.idxmin()].set_index('scale').model.to_dict()
    (R/'frozen_selection.json').write_text(json.dumps({'selection_folds':[2022,2023],'protocol_sha256':protocol_hash,'models':winners},indent=2)+'\n')
    print('Frozen selections:',winners,flush=True)
    print(ranking.round(3).to_string(index=False),flush=True)
    _,_,_,_,check=experiment(df,'2023-12-31','2024-01-01','2024-12-31')
    check.to_csv(R/'development_2024_metrics.csv',index=False)
    print('2024 development check saved; choices remain frozen.',flush=True)

    # PHASE 5 — Calibrate on previously inspected 2025, then open fresh 2026 test once.
    stage('PHASE 5/6 | EVALUATION: 2025 interval calibration; fresh Jan–Aug 2026 final test')
    _,_,_,calibration,_=experiment(df,'2024-12-31','2025-01-01','2025-12-31',set(winners.values()))
    calibration.to_csv(R/'calibration_periods.csv',index=False)
    widths={}
    for scale,name in winners.items():
        c=calibration[calibration.scale==scale].dropna(subset=['actual',name])
        residual=np.sort(abs(c[name]-c.actual))
        widths[scale]=float(residual[min(len(residual)-1,int(np.ceil((len(residual)+1)*.9))-1)])
    test_bundle,_,paths,periods,metrics=experiment(df,'2025-12-31','2026-01-01','2026-08-31')
    paths.to_csv(R/'test_paths.csv',index=False);periods.to_csv(R/'test_periods.csv',index=False)
    metrics.to_csv(R/'test_metrics.csv',index=False)
    selected=[];summary=[]
    for scale,name in winners.items():
        g=periods[periods.scale==scale].copy();g['model']=name;g['prediction']=g[name]
        g['lower90']=np.maximum(0,g.prediction-widths[scale]);g['upper90']=g.prediction+widths[scale]
        selected.append(g)
        row=metrics[(metrics.scale==scale)&(metrics.model==name)].iloc[0].to_dict()
        base=metrics[(metrics.scale==scale)&(metrics.model=='repeat_week')].iloc[0]
        row['improvement_pct']=100*(1-row['mae_mwh']/base.mae_mwh)
        observed=g.dropna(subset=['actual']); row['coverage_pct']=100*observed.actual.between(observed.lower90,observed.upper90).mean()
        row['proposed_gate_pass']=bool(row['improvement_pct']>=10 and abs(row['bias_pct'])<3)
        summary.append(row)
    selected=pd.concat(selected,ignore_index=True);summary=pd.DataFrame(summary)
    selected.to_csv(R/'selected_forecasts.csv',index=False);summary.to_csv(R/'management_scorecard.csv',index=False)
    print('\nFRESH TEST SCORECARD\n'+summary.round(2).to_string(index=False),flush=True)

    # PHASE 5b — Diagnose residual structure, difficult regimes and paired weather value.
    # These diagnostics do not trigger another tuning cycle on the test.
    daily=selected[selected.scale=='daily'].sort_values('start').copy()
    daily['error']=daily.prediction-daily.actual
    daily['month']=daily.start.dt.month;daily['weekday']=daily.start.dt.dayofweek
    high_threshold=df.loc[:'2025-12-31'].demand_mwh.quantile(.9)
    daily['demand_regime']=np.where(daily.actual>=high_threshold,'high (training p90)','normal')
    slices=[]
    for dimension in ['month','weekday','demand_regime']:
        for value,g in daily.groupby(dimension):
            g=g.dropna(subset=['actual'])
            slices.append({'dimension':dimension,'value':value,'n':len(g),'wape_pct':100*abs(g.error).sum()/g.actual.sum(),'bias_pct':100*g.error.sum()/g.actual.sum()})
    pd.DataFrame(slices).to_csv(R/'residual_slices.csv',index=False)
    pd.DataFrame({'lag':range(1,29),'residual_autocorrelation':[daily.error.autocorr(i) for i in range(1,29)]}).to_csv(R/'residual_autocorrelation.csv',index=False)
    daily.assign(abs_error=lambda x:abs(x.error)).nlargest(10,'abs_error').to_csv(R/'largest_daily_misses.csv',index=False)
    ablations=[]
    for scale in ['daily','weekly','monthly']:
        for family in ['ridge_1','ridge_100','trees']:
            pair=metrics[(metrics.scale==scale)&metrics.model.isin([family+'_calendar',family+'_weather'])].set_index('model')
            ablations.append({'scale':scale,'family':family,'weather_mae_change_pct':100*(pair.loc[family+'_weather','mae_mwh']/pair.loc[family+'_calendar','mae_mwh']-1)})
    pd.DataFrame(ablations).to_csv(R/'weather_ablation.csv',index=False)
    # Compare leads on common origins, avoiding a different seasonal sample at each lead.
    common=paths[(paths.origin+pd.Timedelta(days=31)<=pd.Timestamp('2026-08-31')) & (paths.target<=pd.Timestamp('2026-08-31'))]
    leads=[]
    for h,g in common.groupby('horizon'):
        g=g.dropna(subset=['actual',winners['daily']])
        leads.append({'lead':h,'n':len(g),'wape_pct':100*abs(g[winners['daily']]-g.actual).sum()/g.actual.sum()})
    pd.DataFrame(leads).to_csv(R/'common_origin_lead_metrics.csv',index=False)
    # Moving-block resampling retains short-range dependence better than shuffling individual days.
    paired=(abs(daily.repeat_week-daily.actual)-abs(daily.prediction-daily.actual)).dropna().to_numpy()
    rng=np.random.default_rng(42);means=[]
    for _ in range(1000):
        starts=rng.integers(0,len(paired)-6,size=int(np.ceil(len(paired)/7)))
        sample=np.concatenate([paired[i:i+7] for i in starts])[:len(paired)]
        means.append(sample.mean())
    stability={'mean_daily_mae_gain_mwh':float(paired.mean()),'block_bootstrap_95pct_mwh':np.quantile(means,[.025,.975]).tolist(),
        'block_days':7,'resamples':1000,'caution':'Descriptive stability interval, not proof across unseen regimes.'}
    (R/'daily_gain_stability.json').write_text(json.dumps(stability,indent=2)+'\n')

    # PHASE 5c — Report measured uncertainty and show remaining forecast failures.
    fig,axes=plt.subplots(3,1,figsize=(13,10))
    for ax,scale in zip(axes,['daily','weekly','monthly']):
        g=selected[selected.scale==scale].sort_values('start')
        ax.plot(g.start,g.actual/1e6,label='Actual',color='#233447')
        ax.plot(g.start,g.prediction/1e6,label='Forecast',color='#d27031')
        ax.fill_between(g.start,g.lower90/1e6,g.upper90/1e6,color='#d27031',alpha=.15,label='Approx. 90% interval')
        ax.set(title=f'Fresh 2026 test • {scale} • {winners[scale]}',ylabel='Million MWh');ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(F/'02_fresh_test.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    axes[0].plot(daily.start,daily.error/1e3);axes[0].axhline(0,color='black',lw=.7)
    axes[0].set(title='Daily residuals: forecast − actual',ylabel='Thousand MWh')
    from matplotlib.dates import MonthLocator, DateFormatter
    axes[0].xaxis.set_major_locator(MonthLocator(interval=2))
    axes[0].xaxis.set_major_formatter(DateFormatter('%b %Y'))
    daily.error.div(1e3).hist(bins=25,ax=axes[1]);axes[1].set(title='Error distribution',xlabel='Thousand MWh')
    axes[2].bar(range(1,29),[daily.error.autocorr(i) for i in range(1,29)]);axes[2].set(title='Residual autocorrelation',xlabel='Lag days')
    fig.tight_layout();fig.savefig(F/'03_residual_diagnostics.png',dpi=150);plt.close(fig)

    # PHASE 6 — Serialize selected models and training-only references for batch delivery.
    # A fitted artifact supports inference without rerunning the research notebook.
    stage('PHASE 6/6 | DELIVERY: save trusted local model bundle and monitoring evidence')
    bundle,_=fit_bundle(df,'2026-08-31',set(winners.values()),stage)
    bundle.update({'winners':winners,'interval_widths':widths,'version':'2','protocol_sha256':protocol_hash,
        'python':platform.python_version(),'sklearn':sklearn.__version__,
        'input_sha256':hashlib.sha256((ROOT/'data/processed/daily_v2.csv').read_bytes()).hexdigest()})
    joblib.dump(bundle,ROOT/'models/v2/forecast_bundle.joblib')
    manifest={k:v for k,v in bundle.items() if k not in ['models','climate','columns']}
    (ROOT/'models/v2/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Simulate monitoring on the test; no background job or notification is installed.
    daily['rolling_28_wape']=100*daily.error.abs().rolling(28,min_periods=28).sum()/daily.actual.rolling(28,min_periods=28).sum()
    daily['rolling_28_bias']=100*daily.error.rolling(28,min_periods=28).sum()/daily.actual.rolling(28,min_periods=28).sum()
    daily['review_flag']=(daily.rolling_28_wape>10)|(daily.rolling_28_bias.abs()>3)
    daily[['start','rolling_28_wape','rolling_28_bias','review_flag']].to_csv(R/'monitoring_simulation.csv',index=False)
    reference=df.loc[:'2025-12-31'][['demand_mwh','temp','humidity']]
    drift=[]
    for col in reference:
        ref=reference[col]; new=df.loc['2026-01-01':'2026-08-31',col]
        drift.append({'feature':col,'reference_mean':ref.mean(),'test_mean':new.mean(),
            'standardized_mean_shift':(new.mean()-ref.mean())/ref.std(),
            'note':'Seasonality confounds this crude drift indicator; review against matching seasons.'})
    pd.DataFrame(drift).to_csv(R/'drift_review.csv',index=False)
    write_brief(summary,winners,stability)
    stage('COMPLETE | Six lifecycle phases executed; models/v2 and reports/v2 are ready for verification')

def write_brief(summary,winners,stability):
    # Derive the management table from measured results rather than hard-coding headline scores.
    lines=['# ERCOT forecasting — CRISP-DM revision 2','',
        '## Business decision','Estimate next-day, next-calendar-week and next-calendar-month energy demand. This supports volume planning, not hourly capacity assurance. Criteria are analyst-proposed, not stakeholder-approved.','',
        '## Fresh final test: January–August 2026','',
        '| Scale | Selected model | Periods | WAPE | MAE gain vs repeat-week | Bias | Interval coverage | Proposed accuracy gate |',
        '|---|---|---:|---:|---:|---:|---:|---|']
    for r in summary.itertuples():
        lines.append(f'| {r.scale} | {r.model} | {r.n} | {r.wape_pct:.2f}% | {r.improvement_pct:.1f}% | {r.bias_pct:.2f}% | {r.coverage_pct:.1f}% | {"Pass" if r.proposed_gate_pass else "Review"} |')
    lines+=['','## Evidence and recommendation',
        'Models were selected on expanding 2022/2023 folds. 2024 was a development check; previously inspected 2025 was interval calibration. Selections remained fixed during the fresh 2026 test. Accuracy gates require ≥10% MAE improvement and absolute bias <3%.',
        'Use the local prototype for demonstration and planning research. Review any failed gate before considering operational use. No monetary benefit has been established.',
        f'Daily paired MAE-gain stability: {stability["mean_daily_mae_gain_mwh"]:,.0f} MWh; descriptive seven-day block-bootstrap 95% interval {stability["block_bootstrap_95pct_mwh"][0]:,.0f} to {stability["block_bootstrap_95pct_mwh"][1]:,.0f} MWh.',
        '', '## Limits that remain',
        '- Only eight test months; no autumn/winter-complete annual assessment. Monthly samples are especially small.',
        '- Historical revised demand and ERA5 reanalysis are not archived as-of operational feeds. Seven-day weather and one-day demand availability are assumptions.',
        '- Four-city weather is a spatial proxy; daylight-saving aggregation and load weighting remain unverified.',
        '- Weather ablations compare paired estimators. A weather model winning one scale does not prove causality or universal weather benefit.',
        '- Approximate intervals use 2025 residuals and refitted models; temporal dependence and drift can invalidate nominal coverage.',
        '- Independent scale-selected products may differ from coherent sums of one daily-model path. Both outputs are labeled.',
        '', '## Delivery',
        'Saved a versioned model bundle and inference CLI, tested locally. Monitoring is a retrospective simulation. No live service is deployed. September 2026 outputs are dated historical-snapshot forecasts issued August 31, not current forecasts.',
        '', '## Next decision',
        'Confirm stakeholder cost/accuracy tolerances and acquire archived weather forecasts and demand vintages. Any further model redesign must be tested on a later untouched period.',
        '', '![Fresh test](figures/02_fresh_test.png)']
    (R/'management_brief.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__': run()
