"""Synthetic WebSocket market aggregation. No exchange connections or trading."""
import argparse
import asyncio
import contextlib
import json
import math
import random
import sqlite3
import time
from collections import deque
from pathlib import Path
from aiohttp import ClientSession, ClientError, WSMsgType, web

SOURCES = ('atlas', 'beacon', 'cobalt')
SYMBOLS = ('BTC-USD', 'ETH-USD', 'SOL-USD')

def normalize(source, raw):
    if source not in SOURCES or not isinstance(raw, dict):
        raise ValueError('Unknown source or invalid object')
    try:
        if source == 'atlas':
            values = (raw['id'], raw['symbol'], raw['price'], raw['size'], raw['timestamp'])
        elif source == 'beacon':
            values = (raw['trade_id'], raw['pair'].replace('/', '-'), raw['p'], raw['q'], raw['ts'] * 1000)
        else:
            values = (raw['seq'], raw['instrument'].replace('_', '-'), raw['last'], raw['amount'], raw['time_ms'])
        ident, symbol, price, size, timestamp = values
        if isinstance(ident, bool) or not isinstance(ident, (str, int)) or not str(ident).strip():
            raise ValueError('Invalid tick id')
        if not isinstance(symbol, str):
            raise ValueError('Invalid symbol')
        symbol = symbol.upper()
        if symbol not in SYMBOLS:
            raise ValueError('Unsupported symbol')
        numbers = []
        for value in (price, size, timestamp):
            if isinstance(value, bool) or not isinstance(value, (int, float, str)) or (isinstance(value, str) and not value.strip()):
                raise ValueError('Invalid numeric field')
            number = float(value)
            if not math.isfinite(number) or number <= 0:
                raise ValueError('Numeric fields must be finite and positive')
            numbers.append(number)
        price, size, timestamp = numbers
        if timestamp > 8640000000000000:
            raise ValueError('Timestamp out of range')
        return dict(source=source, id=str(ident), symbol=symbol, price=price, size=size, timestamp=timestamp)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('Malformed source schema') from exc

class Aggregator:
    def __init__(self, database):
        self.db = sqlite3.connect(database)
        self.db.execute('CREATE TABLE IF NOT EXISTS ticks(source TEXT,id TEXT,symbol TEXT,price REAL,size REAL,timestamp REAL,PRIMARY KEY(source,id))')
        self.db.commit()
        self.queue = asyncio.Queue(maxsize=256)
        self.stats = dict(accepted=0, rejected=0, duplicates=0, out_of_order=0, reconnects=0)
        self.latest = {}
        self.processing_ms = deque(maxlen=2000)
        self.listeners = set()

    def process(self, source, raw):
        begin = time.perf_counter()
        try:
            tick = normalize(source, raw)
        except ValueError:
            self.stats['rejected'] += 1
            return None
        cursor = self.db.execute('INSERT OR IGNORE INTO ticks VALUES(?,?,?,?,?,?)', tuple(tick[k] for k in ('source','id','symbol','price','size','timestamp')))
        if cursor.rowcount == 0:
            self.stats['duplicates'] += 1
            return None
        key = (tick['source'], tick['symbol'])
        if key in self.latest and tick['timestamp'] < self.latest[key]['timestamp']:
            self.stats['out_of_order'] += 1
        else:
            self.latest[key] = tick
        self.stats['accepted'] += 1
        self.processing_ms.append((time.perf_counter()-begin)*1000)
        return tick

    async def consume(self):
        while True:
            source, raw = await self.queue.get()
            try:
                tick = self.process(source, raw)
                self.db.commit()
                if tick:
                    for listener in tuple(self.listeners):
                        if listener.full():
                            listener.get_nowait()
                        listener.put_nowait(tick)
            finally:
                self.queue.task_done()

    async def connect(self, session, source, url):
        delay = .1
        while True:
            try:
                async with session.ws_connect(url, heartbeat=20, max_msg_size=65536) as ws:
                    delay = .1
                    async for msg in ws:
                        if msg.type == WSMsgType.TEXT:
                            try:
                                raw = json.loads(msg.data)
                            except ValueError:
                                self.stats['rejected'] += 1
                                continue
                            await self.queue.put((source, raw))
                        elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSED):
                            break
            except (ClientError, OSError, asyncio.TimeoutError):
                pass
            self.stats['reconnects'] += 1
            await asyncio.sleep(delay)
            delay = min(delay*2, 5)

    def snapshot(self):
        samples = sorted(self.processing_ms)
        return dict(stats=self.stats.copy(), latest=list(self.latest.values()), queue_depth=self.queue.qsize(), processing_p95_ms=samples[min(len(samples)-1, int(len(samples)*.95))] if samples else None)

def create_app(engine):
    app = web.Application()
    async def health(request):
        return web.json_response({'status':'ok','mode':'synthetic'})
    async def snapshot(request):
        return web.json_response(engine.snapshot())
    async def feed(request):
        source = request.match_info['source']
        if source not in SOURCES:
            raise web.HTTPNotFound()
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        rng = random.Random(SOURCES.index(source)+7)
        sequence = 0
        session_id = time.time_ns()
        try:
            while not ws.closed:
                symbol = SYMBOLS[sequence % 3]
                price = [64000, 3200, 150][sequence % 3] * (1+rng.uniform(-.001,.001))
                size = round(rng.uniform(.01, 3), 3)
                timestamp = int(time.time()*1000)
                ident = f'{session_id}-{sequence}'
                if source == 'atlas':
                    raw = dict(id=ident, symbol=symbol, price=price, size=size, timestamp=timestamp)
                elif source == 'beacon':
                    raw = dict(trade_id=ident, pair=symbol.replace('-','/'), p=str(price), q=str(size), ts=timestamp/1000)
                else:
                    raw = dict(seq=ident, instrument=symbol.replace('-','_'), last=price, amount=size, time_ms=timestamp)
                await ws.send_json(raw)
                sequence += 1
                await asyncio.sleep([.04,.06,.08][SOURCES.index(source)])
        except (ConnectionError, RuntimeError):
            pass
        return ws
    async def stream(request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        queue = asyncio.Queue(maxsize=128)
        engine.listeners.add(queue)
        async def send():
            while True:
                tick = await queue.get()
                await ws.send_json({'type':'tick','tick':tick})
        sender = asyncio.create_task(send())
        try:
            async for _ in ws:
                pass
        finally:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError, ConnectionError):
                await sender
            engine.listeners.discard(queue)
        return ws
    app.router.add_get('/health', health)
    app.router.add_get('/api/snapshot', snapshot)
    app.router.add_get('/feed/{source}', feed)
    app.router.add_get('/stream', stream)
    app.router.add_static('/', Path(__file__).parent/'dist', show_index=True)
    return app

async def run_demo(duration=3, database=':memory:', port=0, ready=None):
    engine = Aggregator(database)
    runner = web.AppRunner(create_app(engine))
    await runner.setup()
    server = web.TCPSite(runner, '127.0.0.1', port)
    await server.start()
    address = runner.addresses[0]
    root = f'http://127.0.0.1:{address[1]}'
    print(f'Synthetic pipeline: {root}/index.html', flush=True)
    async with ClientSession() as session:
        consumer = asyncio.create_task(engine.consume())
        producers = [asyncio.create_task(engine.connect(session, s, root+'/feed/'+s)) for s in SOURCES]
        try:
            if ready:
                await ready(root, engine)
            else:
                await asyncio.sleep(duration)
        finally:
            for task in producers:
                task.cancel()
            await asyncio.gather(*producers, return_exceptions=True)
            await engine.queue.join()
            consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)
    result = engine.snapshot()
    await runner.cleanup()
    engine.db.close()
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--database', default='ticks.sqlite')
    args = parser.parse_args()
    if not 0 < args.seconds <= 86400:
        parser.error('--seconds must be between 0 and 86400')
    print(json.dumps(asyncio.run(run_demo(args.seconds, args.database, args.port)), indent=2))
