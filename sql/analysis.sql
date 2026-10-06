-- BLOCK 1: Measure coverage before calculating any business summaries.
-- COUNT(demand_mwh) excludes NULL, so a missing day cannot masquerade as zero.
CREATE VIEW IF NOT EXISTS quality_summary AS
SELECT COUNT(*) AS calendar_days, COUNT(demand_mwh) AS observed_days,
       SUM(demand_mwh IS NULL) AS missing_demand_days,
       MIN(date) AS first_date, MAX(date) AS last_date
FROM daily;

-- BLOCK 2: Compare annual average demand, retaining the completeness count.
-- Average daily demand is comparable across leap years; incomplete totals are NULL.
CREATE VIEW IF NOT EXISTS annual_summary AS
SELECT substr(date,1,4) AS year, COUNT(*) AS calendar_days,
       COUNT(demand_mwh) AS observed_days, AVG(demand_mwh) AS avg_daily_mwh,
       CASE WHEN COUNT(demand_mwh)=COUNT(*) THEN SUM(demand_mwh) END AS total_mwh
FROM daily GROUP BY year;

-- BLOCK 3: Explore seasonality on training data only, leaving the test untouched.
CREATE VIEW IF NOT EXISTS training_seasonality AS
SELECT CAST(strftime('%m',date) AS INTEGER) AS month,
       AVG(demand_mwh) AS avg_daily_mwh, COUNT(demand_mwh) AS observed_days
FROM daily WHERE date < '2024-01-01' GROUP BY month;

-- BLOCK 4: Create daily lag features with explicit date joins.
-- Date joins preserve calendar-day meaning even when an observation is missing.
CREATE VIEW IF NOT EXISTS modeling_daily AS
SELECT d.*, p.demand_mwh AS demand_lag_1, w.demand_mwh AS demand_lag_7
FROM daily d
LEFT JOIN daily p ON p.date=date(d.date,'-1 day')
LEFT JOIN daily w ON w.date=date(d.date,'-7 days');

-- BLOCK 5: Summarize full calendar months without summing incomplete demand.
CREATE VIEW IF NOT EXISTS monthly_actuals AS
SELECT substr(date,1,7) AS month, COUNT(*) AS calendar_days,
       COUNT(demand_mwh) AS observed_days,
       CASE WHEN COUNT(demand_mwh)=CAST(strftime('%d',date(date,'start of month','+1 month','-1 day')) AS INTEGER)
       THEN SUM(demand_mwh) END AS demand_mwh
FROM daily GROUP BY month;
