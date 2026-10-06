# Portfolio and application copy

These drafts describe the saved project evidence. Before using first-person statements in an application, confirm that they accurately represent your contribution and that you can explain the methods. Add a repository URL only after confirming the published location.

## Portfolio card

**Electricity Demand Forecasting | Python, SQL, scikit-learn**

Evaluated daily, weekly and monthly ERCOT electricity-demand forecasts using chronological validation and simple baselines. Selected methods differed by horizon: persistence for daily, repeat-week for weekly and ridge regression with weather proxies for monthly demand. The monthly method reduced MAE by 57.7% against repeat-week over eight test months. Includes executed notebooks, data-quality checks, local inference and documented limitations.

## CV bullets — use after confirming your contribution

- Analyzed 2,800 calendar days of ERCOT demand and regional weather using Python and SQL, preserving missing demand and validating calendar-period totals.
- Compared baseline, regression and tree forecasting methods using expanding chronological validation; the selected monthly model achieved 2.46% WAPE over eight test months.
- Prepared reproducible notebooks, a local forecasting CLI and behavioral checks for unavailable-data leakage, model selection and forecast aggregation.

## Interview explanation — adapt to your own words

“The project asks how to forecast electricity demand at daily, weekly and monthly scales. I compared simple baselines with more complex models and used earlier years for model selection before evaluating on January through August 2026. A useful result was that simple methods won two horizons. Ridge regression worked best for monthly demand, reducing MAE by 57.7% against repeat-week, but that result covers only eight months. I would validate on more untouched data and check operational data availability before recommending live use.”

## Be ready to explain

1. Why random train/test splitting is unsuitable for this experiment.
2. How MAE differs from WAPE, and why monthly MAE is larger in MWh.
3. Why missing demand is not zero and invalidates containing period totals.
4. How weather information is restricted at forecast time.
5. Why the weekly result and eight-month test limit are part of the conclusion.
6. Why the final delivered model is refitted after evaluation, while reported test scores come from earlier fits.

## Repository

Project repository: https://github.com/kalebmyom2-eng/energy-demand-forecasting

Use the repository link with the portfolio card or CV bullets above.
