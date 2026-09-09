# TickStream — Real-Time Market Data Aggregator

Python asyncio/WebSocket aggregation pipeline and interactive synthetic market-data workspace by Yubraj Chaulagain. Newly built portfolio implementation aligned with the market-data project in the supplied resume. All included prices and trades are generated; there are no exchange connections, credentials, order execution or client data.

## What works

- Three actual local WebSocket feeds with different payload schemas, consumed concurrently through one aiohttp client session.
- Normalization of source IDs, symbols, prices, sizes and timestamps; finite-positive numeric validation; SQLite-backed deduplication and persistence.
- Bounded ingestion queue, reconnect/backoff loop, event-time quote selection, out-of-order counts, health/snapshot HTTP APIs and normalized WebSocket fan-out.
- Deployed browser workspace with three synthetic sources, adjustable speed, source toggles, consolidated quotes, event-time price chart, recent tick log and data-quality counters.
- Invalid/duplicate/late-tick fault injection, normalized JSON replay and downloadable accepted ticks.
- The same UI can connect to the local Python application's normalized WebSocket output.

## Run the Python pipeline

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 -m unittest test_aggregator.py
python3 aggregator.py --seconds 3600 --port 8000 --database ticks.sqlite
```

Open http://127.0.0.1:8000/index.html, expand **Data contract & Python connection**, then choose **Connect same-origin Python stream**. The process runs for the requested duration (maximum one day) and prints a final snapshot. It binds only to localhost. A local virtual environment is recommended. Dependencies were tested with aiohttp 3.13.5.

Endpoints: `/health`, `/api/snapshot`, `/feed/atlas`, `/feed/beacon`, `/feed/cobalt`, `/stream`. The SQLite `ticks` table stores accepted events with a unique `(source,id)` key across restarts. Late events remain in storage but do not replace a newer per-source quote. Recent quote state and counters reset on process restart. Display subscribers have a 128-tick queue; a slow display drops its oldest pending update. Database ingestion uses a separate bounded 256-item queue with backpressure. This is a single-process demonstration, not a distributed trading service.

## Run only the browser workspace

```sh
npm test
npm start
```

Requires Node 20+ for model tests, Python 3 for static serving. The deployed static demo generates and processes synthetic streams on the device; it does **not** host the Python process. Python connection is available when served locally by `aggregator.py`, not on the static host. Browser simulation functions without a backend.

## Contract and limits

Normalized fields: `source`, `id`, `symbol`, `price`, `size`, `timestamp`. Supported symbols are BTC-USD, ETH-USD and SOL-USD; these are synthetic instruments, not real market quotes. Unix milliseconds are used after converting Beacon's seconds. Price and size must be finite positive numbers. Latest consolidated price is selected by event timestamp, not a volume-weighted average.

The browser keeps the last 2,000 accepted ticks, 10,000 deduplication IDs, 2,000 processing samples and 50 validation errors. Imports accept up to 2 MB and 10,000 normalized records. Exports include the retained accepted window, independent of the current UI filter. Replay runs immediately rather than honoring original timestamp delays. Processing p95 measures normalization/insertion in the relevant runtime, not end-to-end network latency. Browser session rate includes accepted injected and replayed ticks and uses elapsed active processing time.

The Python writer commits each processed item; its reported processing duration measures normalization/insert, excluding the commit. It uses SQLite synchronously and is intended for a local MVP, not high-frequency production throughput. No claim of sub-10ms delivery or a 40% improvement is made. Clock ordering across real providers and live exchange adapters are outside this synthetic implementation.

## Verification

Passed: three Python tests covering adapters, invalid values, duplicate and late events, three concurrent real local WebSocket feeds, normalized WebSocket output and the snapshot API; three JavaScript tests covering schemas, quote ordering, deduplication, malformed values and bounded storage; JavaScript syntax checks. Browser interaction/visual QA and reconnect fault tests were not performed.

Sources used for API implementation: [aiohttp client documentation](https://docs.aiohttp.org/en/stable/client_quickstart.html). Woodcrest/CrestMind and OM Produce were excluded.
