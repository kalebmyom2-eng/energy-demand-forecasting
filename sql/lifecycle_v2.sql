-- PHASE 2: Audit completeness before calculating targets or business summaries.
-- A calendar spine preserves absent records; NULL never becomes zero demand.
DROP VIEW IF EXISTS daily_features;
CREATE VIEW daily_features AS
SELECT c.date, d.demand_mwh,
       CASE WHEN COUNT(w.temp_mean)=4 THEN AVG(w.temp_mean) END AS temp,
       CASE WHEN COUNT(w.humidity)=4 THEN AVG(w.humidity) END AS humidity,
       COUNT(w.temp_mean) AS weather_cities_present
FROM calendar c
LEFT JOIN demand d ON c.date=d.date
LEFT JOIN weather w ON c.date=w.date
GROUP BY c.date,d.demand_mwh;

-- PHASE 2: Report missing values and join coverage by year, including partial years.
DROP VIEW IF EXISTS yearly_quality;
CREATE VIEW yearly_quality AS
SELECT substr(date,1,4) AS year, COUNT(*) AS days_in_snapshot,
       COUNT(demand_mwh) AS observed_demand_days,
       SUM(demand_mwh IS NULL) AS missing_demand_days,
       SUM(weather_cities_present<4) AS incomplete_weather_days
FROM daily_features GROUP BY year;

-- PHASE 3: Monthly actual totals require every expected calendar day.
DROP VIEW IF EXISTS complete_months;
CREATE VIEW complete_months AS
SELECT substr(date,1,7) AS month, COUNT(demand_mwh) AS observed_days,
       CAST(strftime('%d',date(date,'start of month','+1 month','-1 day')) AS INTEGER) AS expected_days,
       CASE WHEN COUNT(demand_mwh)=CAST(strftime('%d',date(date,'start of month','+1 month','-1 day')) AS INTEGER)
            THEN SUM(demand_mwh) END AS demand_mwh
FROM daily_features GROUP BY month;

-- PHASE 2: Explore only development dates; protect the later test from EDA-driven tuning.
DROP VIEW IF EXISTS development_seasonality;
CREATE VIEW development_seasonality AS
SELECT strftime('%m',date) AS month, strftime('%w',date) AS weekday_sunday_zero,
       AVG(demand_mwh) AS mean_demand_mwh, AVG(temp) AS mean_temperature_c,
       COUNT(demand_mwh) AS n
FROM daily_features WHERE date<'2024-01-01' GROUP BY month,weekday_sunday_zero;
