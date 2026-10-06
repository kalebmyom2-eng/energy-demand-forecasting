# Data provenance and reuse

This repository includes small public-source snapshots used to reproduce the reported study.

- **Electricity demand:** US Energy Information Administration (EIA), ERCO daily regional demand, in MWh. Source: https://www.eia.gov/opendata/browser/electricity/rto/daily-region-data
- **Weather:** Open-Meteo Historical Weather API, ERA5 data from Copernicus/ECMWF, for Houston, Dallas, Austin and San Antonio. Source: https://open-meteo.com/en/docs/historical-weather-api
- Credit Open-Meteo and Copernicus/ECMWF ERA5 when reusing weather data. Source providers retain their applicable terms; this repository does not relicense their data.

`raw/` preserves source responses; `processed/` contains modeling tables. SQLite databases are generated locally by the preparation pipelines and are excluded from the published repository. V1 covers 2019–2025; V2 extends through August 2026. See `docs/DATA_DICTIONARY.md` and `reports/v2/data_manifest.json` for schema and recorded provenance. December 5, 2025 demand is missing and remains unknown.

Run `sh scripts/download_data.sh` or `sh scripts/download_v2.sh` from the repository root only to deliberately refresh snapshots. Downloads use EIA's public DEMO_KEY, may be rate limited, and can change results when source values are revised. The included files allow offline analysis.
