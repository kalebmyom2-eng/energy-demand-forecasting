"""Build an executable methodology notebook from the same tested pipeline blocks."""
# BLOCK 1 — Extract the run function body so notebook and terminal logic stay consistent.
# This notebook executes modeling; it is not just a viewer of precomputed CSVs.
import ast
import re
import textwrap
from pathlib import Path
import nbformat as nbf
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/run_lifecycle.py').read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='run')
body=textwrap.dedent('\n'.join(source.splitlines()[node.lineno:node.end_lineno]))
blocks=[b for b in re.split(r'(?=^# PHASE)',body,flags=re.M) if b.strip()]
explanations=[
('1. Business understanding','Read the protocol first: stakeholder assumptions, energy-volume decisions, proposed 10% MAE-improvement and <3% bias gates. These criteria are analyst-proposed. The fresh test has not been used to tune this revision.'),
('2–3. Data understanding and preparation','Validate source keys, units and date coverage; preserve unknown targets through SQL calendar joins. Inspect development-only distributions and flag outliers without deleting grid events. See the data dictionary and cleaning log. The code executes the actual curation and EDA.'),
('4. Modeling and temporal validation','Fit two expanding development folds, compare baselines and six candidates, and freeze scale-specific winners. All imputers/scalers are training-fitted. Features use issue−1 demand and issue−7 weather. A later 2024 check does not change selection. This cell trains the models and prints progress.'),
('5. Calibration and fresh evaluation','Previously inspected 2025 is calibration, not a new holdout. Refit through 2025 and evaluate January–August 2026 only after selection. Weekly and monthly totals must come from one pre-period issue date. Missing actuals invalidate entire containing totals.'),
('5b. Diagnostics and interpretation','Examine residual slices, high demand, paired weather ablations and errors by lead on common origins. A block bootstrap is a descriptive stability check. These findings do not cause retuning on the test.'),
('5c. Visual evaluation','Inspect actual versus predicted demand and uncertainty. Residual structure can reveal unresolved patterns. The small monthly sample cannot prove calibration even with high measured coverage.'),
('6. Delivery and monitoring','Refit the selected models after evaluation, save a reusable artifact, and simulate monitoring. Test scores belong to earlier fits, not this final refit. Local batch inference is demonstrated; no live service is deployed.')]
assert len(blocks)==len(explanations),(len(blocks),len(explanations))
nb=nbf.v4.new_notebook()
nb.cells=[nbf.v4.new_markdown_cell('# Electricity demand forecasting — complete CRISP-DM lifecycle\n\nThis notebook executes the revised project from business understanding to local delivery. It preserves the earlier study as version 1 and uses a fresh 2026 test. Run cells in order. SQL and Python helpers contain explanatory code-block comments; methodology and decisions are documented alongside the outputs.'),
nbf.v4.new_code_cell('''# Setup: locate the repository and import reusable, side-effect-free analysis helpers.
# Importing run_lifecycle defines functions but does not launch the experiment.
import sys
from pathlib import Path
project=Path.cwd()
if project.name=='notebooks': project=project.parent
sys.path.insert(0,str(project/'scripts'))
from run_lifecycle import *
from IPython.display import display, Image
''')]
for (title,explanation),block in zip(explanations,blocks):
    nb.cells.append(nbf.v4.new_markdown_cell('## '+title+'\n\n'+explanation))
    nb.cells.append(nbf.v4.new_code_cell(block))
    if title.startswith('2–3'):
        nb.cells.append(nbf.v4.new_code_cell('''# Inspect real SQL quality results and the data-understanding figure.
display(pd.read_csv(R/'yearly_quality.csv'))
display(pd.read_csv(R/'cleaning_log.csv'))
display(Image(filename=str(F/'01_data_understanding.png')))
'''))
    if title.startswith('5c'):
        nb.cells.append(nbf.v4.new_code_cell('''# Display saved plots to assess uncertainty and unresolved residual patterns.
display(Image(filename=str(F/'02_fresh_test.png')))
display(Image(filename=str(F/'03_residual_diagnostics.png')))
'''))
nb.cells += [nbf.v4.new_markdown_cell('## 7. Verify and hand off\n\nExercise saved-model inference and behavioral checks: perturb unknown future values, reproduce model selection, verify period completeness, check reconciliation and reject stale/duplicate input. Review all failed business gates before proposing production use.'),
nbf.v4.new_code_cell('''# Run the real inference CLI and verification suite with the notebook interpreter.
import subprocess
subprocess.run([sys.executable,str(ROOT/'scripts/predict.py'),'--origin','2026-08-31'],check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/verify_lifecycle.py')],check=True)
display(pd.read_csv(R/'management_scorecard.csv').round(2))
display(pd.read_csv(R/'weather_ablation.csv').round(2))
''')]
nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
nbf.write(nb,ROOT/'notebooks/01_complete_data_science_methodology.ipynb')
print('Saved full executable lifecycle notebook:',len(nb.cells),'cells')
