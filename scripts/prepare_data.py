"""Audit preserved API responses and build a daily modeling table (stdlib only)."""
import csv
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raw = ROOT / 'data/raw'
response = json.loads((raw / 'eia_erco_daily_2019_2025.json').read_text())['response']
records = response['data']
assert len(records) == int(response['total']), 'Incomplete API download'
counts = Counter(r['period'] for r in records)
duplicates = [d for d, n in counts.items() if n > 1]
assert not duplicates, f'Duplicate demand dates: {duplicates}'
start, end = date(2019, 1, 1), date(2025, 12, 31)
expected = {(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)}
missing = sorted(expected - set(counts))
assert set(counts) <= expected
weather = json.loads((raw / 'weather_texas_2019_2025.json').read_text())
cities = ['houston', 'dallas', 'austin', 'san_antonio']
assert len(weather) == len(cities)
weather_by_city = {}
for city, payload in zip(cities, weather):
    daily = payload['daily']
    assert len(set(daily['time'])) == len(daily['time'])
    assert set(daily['time']) == expected
    assert all(len(v) == len(daily['time']) for v in daily.values())
    weather_by_city[city] = {
        day: {key: values[i] for key, values in daily.items() if key != 'time'}
        for i, day in enumerate(daily['time'])
    }
rows = []
by_date = {r['period']: r for r in records}
for day in sorted(expected):
    record = by_date.get(day)
    if record is not None:
        assert (record['respondent'], record['type'], record['timezone'], record['value-units']) == ('ERCO', 'D', 'Central', 'megawatthours')
    row = {'date': day, 'demand_mwh': float(record['value']) if record else None}
    assert row['demand_mwh'] is None or row['demand_mwh'] > 0
    for city in cities:
        for feature, value in weather_by_city[city][row['date']].items():
            assert value is not None, f'Missing weather: {city} {row["date"]}'
            row[f'{city}_{feature}'] = value
    rows.append(row)
output = ROOT / 'data/processed/daily_demand_weather.csv'
with output.open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
audit = {
    'rows': len(rows), 'columns': len(rows[0]), 'start': rows[0]['date'], 'end': rows[-1]['date'],
    'duplicate_demand_dates': len(duplicates), 'missing_dates': missing,
    'missing_weather_values': 0, 'nonpositive_demand_values': 0,
    'demand_min_mwh': min(r['demand_mwh'] for r in rows if r['demand_mwh'] is not None),
    'demand_max_mwh': max(r['demand_mwh'] for r in rows if r['demand_mwh'] is not None),
    'note': 'Structural validation only; outliers, reporting revisions, and day-boundary alignment need further investigation.'
}
(ROOT / 'reports/data_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps(audit, indent=2))
