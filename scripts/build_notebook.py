"""Build a runnable review notebook from the verified pipeline outputs."""
# BLOCK 1 — Create notebook cells with explanations before every code block.
from pathlib import Path
import nbformat as nbf
ROOT=Path(__file__).resolve().parents[1]
nb=nbf.v4.new_notebook()
nb.cells=[nbf.v4.new_markdown_cell('# ERCOT forecasting: portfolio walkthrough\n\nThis notebook reviews the completed SQL/Python study. Model fitting is in the eleven annotated blocks of `scripts/run_project.py`; see `reports/STEP_BY_STEP.md` for the full procedure. Run that pipeline before this notebook. No models are silently retrained here.')]
sections=[
('1. Locate the project', 'Use a portable project path and import analysis tools.', '''# Locate the repository from the project root or notebooks directory.
from pathlib import Path
import sqlite3
import pandas as pd
from IPython.display import display, Image
ROOT=Path.cwd()
if ROOT.name=='notebooks': ROOT=ROOT.parent
assert (ROOT/'data/energy.sqlite').exists()
'''),
('2. Audit with SQL','COUNT(column) excludes missing values. The annual total remains NULL when demand is incomplete.', '''# Query real SQL views created by sql/analysis.sql.
with sqlite3.connect(ROOT/'data/energy.sqlite') as con:
    display(pd.read_sql_query('SELECT * FROM quality_summary',con))
    display(pd.read_sql_query('SELECT * FROM annual_summary',con))
'''),
('3. Explore training data','Study trend, annual/weekly seasonality and weather associations using 2019–2023 only. Weather is an equal-city proxy, not a load-weighted measurement.', '''# Display the training-period figure saved by the completed analysis.
display(Image(filename=str(ROOT/'reports/figures/01_training_exploration.png')))
'''),
('4. Select on validation','Direct models predict leads 1–31 from issue-date features. Select on 2024 MAE before inspecting 2025. The oracle uses realized future weather and is ineligible.', '''# Inspect validation evidence and reproduce the eligible selection.
v=pd.read_csv(ROOT/'reports/validation_metrics.csv')
display(v.round(2))
e=v[~v.model.str.startswith('oracle')]
display(e.loc[e.groupby('scale').mae_mwh.idxmin(),['scale','model','mae_mwh']])
'''),
('5. Evaluate frozen choices','Test on 2025 after refitting through 2024. Weekly/monthly paths are issued before each period. Missing December 5 invalidates its containing totals; only 11 months are scored.', '''# Read measured scores without changing the selected models.
display(pd.read_csv(ROOT/'reports/selected_model_summary.csv').round(2))
display(Image(filename=str(ROOT/'reports/figures/02_test_forecasts.png')))
'''),
('6. Inspect failures and lead times','The selected model misses sharp winter spikes. Next-day accuracy must not be attributed to every day in a 31-day forecast path. Approximate intervals have limited monthly calibration evidence.', '''# Show difficult next-day cases and distinguish individual forecast leads.
e=pd.read_csv(ROOT/'reports/largest_errors.csv')
display(e.loc[e.scale=='daily',['start','actual','prediction','abs_error_mwh']].round(0))
h=pd.read_csv(ROOT/'reports/test_metrics_by_horizon.csv')
display(h[(h.model=='ridge_calendar') & h.horizon_days.isin([1,7,14,31])].round(2))
'''),
('7. Deliver a dated forecast','January 2026 predictions are a historical snapshot issued December 31, 2025, not a current forecast. A common daily path reconciles to weekly/monthly totals. Recommend archived-weather evaluation before operational use; no financial savings are established.', '''# Inspect the dated outputs and the partial-week flags.
display(pd.read_csv(ROOT/'reports/snapshot_daily_january_2026.csv').head())
display(pd.read_csv(ROOT/'reports/snapshot_weekly_january_2026.csv'))
display(pd.read_csv(ROOT/'reports/snapshot_monthly_january_2026.csv'))
''')]
for title,explanation,code in sections:
    nb.cells.extend([nbf.v4.new_markdown_cell(f'## {title}\n\n{explanation}'),nbf.v4.new_code_cell(code)])
# BLOCK 2 — Save before execution so a kernel startup problem cannot discard the source.
nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
nbf.write(nb,ROOT/'notebooks/portfolio_walkthrough.ipynb')
print('Saved review notebook: 7 annotated code cells.')
