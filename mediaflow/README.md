# MediaFlow

A functioning media ETL portfolio MVP by Yubraj Chaulagain. Inspired by the ingestion, schema normalization, data cleaning and quality validation responsibilities in the Kosis Multimedia resume entry. This is a newly built demonstration, not the company's original system or evidence of production outcomes. All included records are synthetic. Woodcrest/CrestMind and OM Produce are excluded.

## Use

Open the deployed workspace, load the synthetic sample or choose a CSV/JSON file, review automatic field mappings, then run the pipeline. Inspect accepted, rejected and duplicate records; filter and paginate results; export clean CSV/JSON or the complete quality report. Run history stores the last 20 summaries in your browser, not source data.

## Local development

Requires Node.js 20+ for tests and Python 3 for the static development server. No npm dependencies or API keys.

```sh
npm test
npm start
```

Visit http://localhost:8000. Production assets are authored in `dist/`; no compilation is required. Any static host, including GitHub Pages or Vercel with output directory `dist`, can serve them. The separate Sites manifest identifies the deployed workspace.

## Data contract

Six required columns: `id`, `title`, `platform`, `published_at`, `views`, `engagements`. Auto-mapping recognizes aliases and manual mapping supports other headers. Dates must be actual YYYY-MM-DD dates; metrics are nonnegative safe integers, optionally with correctly grouped thousands separators. Text whitespace is normalized and platform values lowercased. Duplicates use `(platform,id)` and keep the first valid record. Invalid earlier rows do not reserve an ID. Engagement rate is null for zero views. Rejected rows preserve their original data and reasons. Row numbers count data records, excluding CSV headers.

CSV parsing supports quoted fields, embedded commas/newlines and escaped quotes. Duplicate or empty headers, malformed quoting and inconsistent row widths fail explicitly. CSV exports prefix potentially executable spreadsheet formulas with an apostrophe; JSON preserves text. Downloads contain all accepted records, regardless of the current table filter.

## Architecture and limits

`dist/pipeline.js` is a pure, independently tested JavaScript ETL engine shared by the browser and Node. `dist/app.js` handles mapping, result views, downloads and local run summaries. `dist/index.html` and `dist/style.css` provide a responsive, accessible workspace. Processing runs on the user's device. There is no remote database, scheduler, authentication service, live company integration or background worker. Files are limited to 2 MB and each run to 10,000 records. Pasted input shares the record limit. Browser history may be unavailable if storage is blocked; processing and downloads continue.

## Resume alignment

| Resume responsibility | Demonstrated implementation |
| --- | --- |
| Structured media ingestion | CSV/JSON parsing and file import |
| Schema normalization | Alias detection and editable field mapping |
| Cleaning and quality validation | Whitespace/case normalization, numeric/date validation, quarantine |
| Consistent downstream analytics | Canonical dataset, engagement rates, platform aggregates, exports |

The web interface uses JavaScript for portable in-browser execution. A separate standard-library Python CLI implements normalization, validation, deduplication, JSON exports and transactional SQLite loading. Neither implementation reproduces the company's original code or claims equivalent production scale. Automated tests cover malformed input, calendar and number validation, deduplication, formula-safe CSV export, record limits, normalization idempotence, SQLite integrity and retention of earlier runs. Browser visual testing has not been performed.

## Python ETL and SQL output

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 pipeline.py examples/synthetic.json --database mediaflow.sqlite --output mediaflow-output
```

The SQLite database stores `runs`, normalized `content`, and `quarantine` records. Each run is appended in a transaction; existing runs are retained. The CLI recognizes the documented aliases automatically. Rename custom columns to canonical names before CLI use; arbitrary manual mapping is available in the browser. Reports are written per run. Browser results and CLI databases are independent. The Python CLI is for local/batch use and is not executed by the static web host. Both implementations use the same schema, but language-specific text coercion and percentage rounding can differ for unusual values; this is not a guaranteed byte-for-byte parity claim.
