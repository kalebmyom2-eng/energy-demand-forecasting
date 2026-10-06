# Beginner project plan

## Our question

Can we predict January electricity demand using calendar patterns and temperature?

## Our small first version

Use ERCOT demand and weather already downloaded. Train on 2019–2024 and forecast January 2025 from one starting point at the end of December 2024. Assume December 31 demand is available. This is a historical learning exercise; January 2025 is not new, untouched data in this project.

## Steps

1. Load the CSV with pandas and look at its first rows.
2. Use two SQL queries to count observations and find missing demand.
3. Create a small table containing date, demand and average temperature.
4. Draw two charts to understand the training data.
5. Create calendar and temperature features. Use training-period monthly average temperature as the forecast weather assumption.
6. Train one linear regression and compare it with repeating the last week.
7. Calculate MAE: average prediction error in MWh. Lower is better.
8. Save daily predictions and sum them into weekly/monthly energy totals. Label partial weeks.
9. Write a short conclusion explaining the result and its limitations.

## What to learn first

A DataFrame is a table. A feature is a model input. Training is learning patterns from past data. Prediction applies those patterns to new inputs. A baseline is a simple method we try to improve. MAE measures average error.

We do not need parameter tuning, bootstrap intervals, model deployment or monitoring for this first learning version. These remain in the advanced project for later.

## What a good result means

The goal is a project you can run and explain yourself. A model does not need to beat the baseline to be useful for learning. Explain the observed result honestly. One test month and assumed weather are not enough to establish reliable year-round forecasting.

## Start

Open notebooks/00_beginner_energy_forecasting.ipynb. Run one cell at a time. Read its explanation, inspect the output, and explain what happened before moving to the next cell.
