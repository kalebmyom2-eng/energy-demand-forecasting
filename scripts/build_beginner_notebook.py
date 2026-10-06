"""Create the short, beginner-first learning notebook."""
from pathlib import Path
import nbformat as nbf
ROOT=Path(__file__).resolve().parents[1]
b=nbf.v4.new_notebook()
b.cells=[nbf.v4.new_markdown_cell('''# My first electricity demand forecasting project

**Question:** Can we predict daily electricity demand using calendar patterns and temperature?

We will make one forecast for January 2025, pretending we are at the end of December 2024 and that December 31 demand is available. This is a historical learning exercise, not a live forecast or a fresh independent test. We already studied 2025 in the earlier project.

We will use Python for analysis, SQLite for two simple checks, and linear regression for prediction. No parameter search, bootstrap or uncertainty intervals are needed for this first version.

Run one code cell at a time. Read the explanation, run the cell, and inspect its output before moving on.''')]
def section(title, explanation, code):
 b.cells.extend([nbf.v4.new_markdown_cell('## '+title+'\n\n'+explanation),nbf.v4.new_code_cell(code)])
section('1. Load the data','''`pandas` helps us work with tables. `read_csv()` opens the prepared dataset. A DataFrame is simply Python's table of rows and columns.

The data was already downloaded from EIA and Open-Meteo. We use the preserved file rather than learning API access at the same time. EIA demand is daily energy in **MWh**. Temperature comes from four Texas cities.''','''# Import the tools we will use and find the project folder.
from pathlib import Path
import os
import sqlite3
import pandas as pd
import numpy as np

# Find the repository when launched from its root or notebooks folder.
ROOT = Path.cwd()
if ROOT.name == 'notebooks':
    ROOT = ROOT.parent
assert (ROOT / 'data/processed/daily_demand_weather.csv').exists(), 'Start Jupyter from the repository root.'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

# Load the existing file and convert date text into real dates.
data_file = ROOT / 'data/processed/daily_demand_weather.csv'
print('Loading:', data_file)
df = pd.read_csv(data_file)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)
print('Rows and columns:', df.shape)
display(df.head())
''')
section('2. Check the data with SQL','''Before modeling, check that the dates and values make sense. SQL is a language for asking questions about tables.

We copy the data into a temporary SQLite database. `COUNT(*)` counts rows; `COUNT(demand_mwh)` counts rows with known demand. The second query shows the missing demand date. We do not replace unknown demand with zero.''','''# Store a copy in a temporary database; the source CSV remains unchanged.
connection = sqlite3.connect(':memory:')
df.to_sql('electricity', connection, index=False, if_exists='replace')

# Compare the number of calendar days with the number of known demand values.
quality = pd.read_sql_query("""
SELECT COUNT(*) AS calendar_days,
       COUNT(demand_mwh) AS days_with_demand
FROM electricity
""", connection)
display(quality)

# Find the dates where demand is unknown.
missing = pd.read_sql_query("""
SELECT date FROM electricity WHERE demand_mwh IS NULL
""", connection)
display(missing)
connection.close()

# A duplicate date would confuse the daily sequence, so stop if we find one.
assert not df['date'].duplicated().any()
''')
section('3. Prepare a small table','''We only need a date, demand and temperature. To keep this exercise simple, average the four cities' mean temperatures. This is an approximation of regional weather.

Training data teaches the model. Test data checks its predictions. We train on 2019–2024 and predict the 31 days in January 2025. The known missing demand date is outside these periods.''','''# Select the four daily mean-temperature columns and calculate their average.
temperature_columns = [column for column in df.columns if column.endswith('temperature_2m_mean')]
assert len(temperature_columns) == 4
assert df[temperature_columns].notna().all().all()
df['temperature_c'] = df[temperature_columns].mean(axis=1)

# Keep only the columns needed for this first project.
data = df[['date', 'demand_mwh', 'temperature_c']].copy()
train = data[data['date'] < '2025-01-01'].copy()
test = data[(data['date'] >= '2025-01-01') & (data['date'] <= '2025-01-31')].copy()
assert train['demand_mwh'].notna().all()
assert len(test) == 31 and test['demand_mwh'].notna().all()
print('Training days:', len(train))
print('Test days:', len(test))
display(train.head())
''')
section('4. Explore before predicting','''Look at demand over time and how it relates to temperature. We use only the training data here.

The temperature relationship can curve: both very hot and very cold days may need more electricity. A chart shows an association; it does not prove that temperature alone caused the changes.''','''# Plot the history and temperature relationship using training data only.
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(train['date'], train['demand_mwh'] / 1_000_000, linewidth=0.7)
axes[0].set(title='Historical demand', xlabel='Date', ylabel='Million MWh per day')
axes[1].scatter(train['temperature_c'], train['demand_mwh'] / 1_000_000, s=6, alpha=0.3)
axes[1].set(title='Temperature and demand', xlabel='Temperature (°C)', ylabel='Million MWh per day')
plt.tight_layout()
plt.show()
''')
section('5. Create model inputs','''A **feature** is information the model uses to predict demand. Our features are temperature, temperature squared, month and weekday.

Squaring temperature lets the regression represent a curved relationship. `get_dummies()` gives each month/weekday its own indicator column rather than treating weekdays as a numeric ranking.

We do not know January's actual weather at the forecast date. For this beginner exercise, use the average January temperature from training data. This is a weather assumption, not a real weather forecast. The model learns from historical observed temperatures but receives estimated temperatures when forecasting.''','''# Make a reusable function that converts the small table into model inputs.
def make_features(table):
    features = pd.DataFrame(index=table.index)
    features['temperature_c'] = table['temperature_c']
    features['temperature_squared'] = table['temperature_c'] ** 2
    features['month'] = table['date'].dt.month.astype(str)
    features['weekday'] = table['date'].dt.dayofweek.astype(str)
    return pd.get_dummies(features, columns=['month', 'weekday'], dtype=float)

# Learn the weather assumption from training data only.
monthly_temperature = train.groupby(train['date'].dt.month)['temperature_c'].mean()
forecast_inputs = test[['date']].copy()
forecast_inputs['temperature_c'] = forecast_inputs['date'].dt.month.map(monthly_temperature)

# Ensure training and prediction tables have exactly the same feature columns.
X_train = make_features(train)
y_train = train['demand_mwh']
X_test = make_features(forecast_inputs).reindex(columns=X_train.columns, fill_value=0)
print('Assumed January temperature:', round(monthly_temperature.loc[1], 1), '°C')
display(X_train.head())
''')
section('6. Train one model and a simple baseline','''Linear regression learns how the input features relate to demand. `fit()` learns from training data; `predict()` produces estimates for new inputs.

We also need a simple comparison, called a **baseline**. Repeat the final seven days of 2024 across January. All 31 predictions are made from the same December 31 starting point. We do not use January demand to update these forecasts.''','''# Fit one model without a parameter search.
model = LinearRegression()
model.fit(X_train, y_train)

# Predict January demand, keeping physically impossible negative estimates out.
results = test[['date', 'demand_mwh']].copy()
results['regression_forecast_mwh'] = np.maximum(0, model.predict(X_test))

# Repeat the last available week for a fair, simple comparison.
last_week = train.tail(7)['demand_mwh'].to_numpy()
results['baseline_forecast_mwh'] = np.resize(last_week, len(results))
display(results.head())
''')
section('7. Check the forecasts using MAE','''**MAE** means mean absolute error: the average size of the prediction errors, in MWh. Lower is better.

If actual demand is 100 MWh and a prediction is 110 MWh, its absolute error is 10 MWh. We average that kind of error across January. A model does not have to win: an honest explanation of its result is part of data science.''','''# Compare both methods using the same 31 actual daily values.
model_mae = mean_absolute_error(results['demand_mwh'], results['regression_forecast_mwh'])
baseline_mae = mean_absolute_error(results['demand_mwh'], results['baseline_forecast_mwh'])
scores = pd.DataFrame({'method': ['Linear regression', 'Repeat-week baseline'],
                       'MAE_MWh': [model_mae, baseline_mae]})
display(scores.round(0))
print('Lower MAE:', 'Linear regression' if model_mae < baseline_mae else 'Repeat-week baseline')

# Plot actual and predicted daily demand on the same dates.
results.set_index('date')[['demand_mwh', 'regression_forecast_mwh', 'baseline_forecast_mwh']].div(1_000_000).plot(figsize=(11, 4))
plt.title('January 2025: one forecast made at the end of 2024')
plt.xlabel('Date')
plt.ylabel('Million MWh per day')
plt.tight_layout()
plt.show()
''')
section('8. Produce daily, weekly and monthly outputs','''The daily predictions already exist. To obtain weekly or monthly energy, add the daily values.

January starts and ends partway through calendar weeks. We label those partial weeks so nobody mistakes them for seven-day totals. We evaluate only daily MAE here: one month is too little evidence to claim reliable monthly performance.''','''# Group daily results into Monday–Sunday weeks and a calendar month.
value_columns = ['demand_mwh', 'regression_forecast_mwh', 'baseline_forecast_mwh']
results['week_start'] = results['date'] - pd.to_timedelta(results['date'].dt.dayofweek, unit='D')
weekly = results.groupby('week_start')[value_columns].sum()
weekly['days'] = results.groupby('week_start').size()
weekly['complete_week'] = weekly['days'] == 7
monthly = results.groupby(results['date'].dt.to_period('M'))[value_columns].sum()

# Check that aggregation has not lost or added energy.
assert np.isclose(monthly['regression_forecast_mwh'].sum(), results['regression_forecast_mwh'].sum())
display(weekly.round(0))
display(monthly.round(0))

# Save the results for a simple portfolio write-up.
output = ROOT / 'reports/beginner'
output.mkdir(parents=True, exist_ok=True)
results.to_csv(output / 'daily_forecasts.csv', index=False)
weekly.to_csv(output / 'weekly_forecasts.csv')
monthly.to_csv(output / 'monthly_forecasts.csv')
scores.to_csv(output / 'model_comparison.csv', index=False)
print('Saved files to:', output)
''')
b.cells.append(nbf.v4.new_markdown_cell('''## 9. Explain the outcome in your own words

Use four sentences:

1. **Problem:** “I forecast January electricity demand for ERCOT using calendar features and temperature.”
2. **Method:** “I used SQL to check the data and Python to compare linear regression with repeating the previous week.”
3. **Result:** State the two MAE values printed above and which was lower.
4. **Limitation:** “This is a one-month historical exercise using average expected weather. I would test more months and better weather estimates before relying on it.”

You have now completed a small data science project: question → data checks → preparation → exploration → modeling → evaluation → saved results. Understand this version first; the advanced project can wait.'''))
b.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
nbf.write(b,ROOT/'notebooks/00_beginner_energy_forecasting.ipynb')
print('Created beginner notebook with 8 short code cells.')
