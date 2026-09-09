"""MediaFlow: standard-library CSV/JSON ETL with transactional SQLite output."""
import argparse
import csv
import datetime as dt
import io
import json
import re
import sqlite3
from pathlib import Path

ALIASES = {
    'id': ['id', 'content_id', 'video_id'],
    'title': ['title', 'name', 'headline'],
    'platform': ['platform', 'channel', 'source'],
    'published_at': ['published_at', 'date', 'publish_date'],
    'views': ['views', 'view_count', 'plays'],
    'engagements': ['engagements', 'interactions', 'likes'],
}

def normalize(value):
    return ' '.join(str(value if value is not None else '').split())

def read_source(path):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Maximum input size is 2 MB')
    text = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.json':
        rows = json.loads(text)
    elif path.suffix.lower() == '.csv':
        data = list(csv.reader(io.StringIO(text), strict=True))
        if len(data) < 2:
            raise ValueError('Include headers and data rows')
        headers = [v.strip() for v in data[0]]
        if not all(headers) or len(set(headers)) != len(headers):
            raise ValueError('Headers must be unique and nonempty')
        rows = []
        for i, row in enumerate(data[1:], 2):
            if not row or not any(v.strip() for v in row):
                continue
            if len(row) != len(headers):
                raise ValueError(f'Row {i} has the wrong column count')
            rows.append(dict(zip(headers, row)))
    else:
        raise ValueError('Input must be .csv or .json')
    if not isinstance(rows, list) or not rows or len(rows) > 10000 or not all(isinstance(r, dict) for r in rows):
        raise ValueError('Provide 1 to 10,000 record objects')
    return rows

def transform(rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    mapping = {f: next((k for k in keys if k.strip().lower() in names), None) for f, names in ALIASES.items()}
    missing = [f for f, k in mapping.items() if k is None]
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    result = {'input': len(rows), 'accepted': [], 'rejected': [], 'duplicates': []}
    seen = set()
    for i, raw in enumerate(rows, 1):
        row = {f: normalize(raw.get(k)) for f, k in mapping.items()}
        row['platform'] = row['platform'].lower()
        errors = [f'{f} is required' for f in ('id', 'title', 'platform') if not row[f]]
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['published_at']):
                raise ValueError()
            dt.date.fromisoformat(row['published_at'])
        except ValueError:
            errors.append('published_at must be a real YYYY-MM-DD date')
        for f in ('views', 'engagements'):
            value = row[f]
            if not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)', value, re.ASCII) or len(value) > 24:
                errors.append(f'{f} must be a nonnegative whole number')
            else:
                row[f] = int(value.replace(',', ''))
                if row[f] > 9007199254740991:
                    errors.append(f'{f} exceeds safe integer range')
        if errors:
            result['rejected'].append({'row': i, 'errors': errors, 'raw': raw})
            continue
        key = (row['platform'], row['id'])
        if key in seen:
            result['duplicates'].append({'row': i, 'errors': ['Duplicate platform + id; first valid record kept'], 'raw': raw})
            continue
        seen.add(key)
        row['engagement_rate'] = round(row['engagements'] / row['views'] * 100, 2) if row['views'] else None
        result['accepted'].append(row)
    return result

def save_database(path, result):
    """Append an isolated run; never overwrite prior runs or source records."""
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('CREATE TABLE IF NOT EXISTS runs (run_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, input INTEGER NOT NULL, accepted INTEGER NOT NULL, rejected INTEGER NOT NULL, duplicates INTEGER NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS content (run_id INTEGER NOT NULL REFERENCES runs(run_id), id TEXT NOT NULL, title TEXT NOT NULL, platform TEXT NOT NULL, published_at TEXT NOT NULL, views INTEGER NOT NULL CHECK(views>=0), engagements INTEGER NOT NULL CHECK(engagements>=0), engagement_rate REAL, PRIMARY KEY(run_id, platform, id))')
        db.execute('CREATE TABLE IF NOT EXISTS quarantine (run_id INTEGER NOT NULL REFERENCES runs(run_id), source_row INTEGER NOT NULL, kind TEXT NOT NULL, errors_json TEXT NOT NULL, raw_json TEXT NOT NULL)')
        run_id = db.execute('INSERT INTO runs(created_at,input,accepted,rejected,duplicates) VALUES(?,?,?,?,?)', (dt.datetime.now(dt.timezone.utc).isoformat(), result['input'], *(len(result[k]) for k in ('accepted', 'rejected', 'duplicates')))).lastrowid
        for row in result['accepted']:
            db.execute('INSERT INTO content VALUES(?,?,?,?,?,?,?,?)', (run_id, *(row[k] for k in ALIASES), row['engagement_rate']))
        for kind in ('rejected', 'duplicates'):
            for row in result[kind]:
                db.execute('INSERT INTO quarantine VALUES(?,?,?,?,?)', (run_id, row['row'], kind, json.dumps(row['errors']), json.dumps(row['raw'])))
    return run_id

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--database', type=Path, default=Path('mediaflow.sqlite'))
    parser.add_argument('--output', type=Path, default=Path('mediaflow-output'))
    args = parser.parse_args()
    try:
        result = transform(read_source(args.input))
        args.output.mkdir(parents=True, exist_ok=True)
        run_id = save_database(args.database, result)
        (args.output / f'run-{run_id}-clean.json').write_text(json.dumps(result['accepted'], indent=2), encoding='utf-8')
        (args.output / f'run-{run_id}-report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'run_id': run_id, 'input': result['input'], **{k: len(result[k]) for k in ('accepted', 'rejected', 'duplicates')}}))
    except (ValueError, OSError, sqlite3.Error, csv.Error) as exc:
        parser.exit(1, f'MediaFlow error: {exc}\n')

if __name__ == '__main__':
    main()
