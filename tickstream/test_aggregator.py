import asyncio
import tempfile
import unittest
from pathlib import Path
from aiohttp import ClientSession
from aggregator import Aggregator, normalize, run_demo

class Tests(unittest.TestCase):
    def test_schemas(self):
        a=normalize('atlas',dict(id='1',symbol='BTC-USD',price=10,size=2,timestamp=1000))
        b=normalize('beacon',dict(trade_id='1',pair='BTC/USD',p='10',q='2',ts=1))
        c=normalize('cobalt',dict(seq='1',instrument='BTC_USD',last=10,amount=2,time_ms=1000))
        self.assertEqual({k:v for k,v in a.items() if k!='source'},{k:v for k,v in b.items() if k!='source'})
        self.assertEqual(c['timestamp'],1000)
    def test_invalid_duplicate_and_event_order(self):
        e=Aggregator(':memory:')
        raw=dict(id='1',symbol='BTC-USD',price=10,size=2,timestamp=1000)
        self.assertIsNotNone(e.process('atlas',raw))
        self.assertIsNone(e.process('atlas',raw))
        self.assertIsNotNone(e.process('atlas',dict(raw,id='2',timestamp=900)))
        for price in (-1, '', True, float('nan'), float('inf')):
            self.assertIsNone(e.process('atlas',dict(raw,id='3',price=price)))
        self.assertEqual(e.stats['duplicates'],1)
        self.assertEqual(e.stats['out_of_order'],1)
        self.assertEqual(e.latest[('atlas','BTC-USD')]['timestamp'],1000)
        e.db.close()
    def test_three_real_websocket_feeds_and_output(self):
        async def check(root, engine):
            async with ClientSession() as session:
                async with session.ws_connect(root+'/stream') as ws:
                    message=await ws.receive_json(timeout=3)
                    self.assertEqual(message['type'],'tick')
                    await asyncio.sleep(.35)
                async with session.get(root+'/api/snapshot') as response:
                    data=await response.json()
                    self.assertEqual({t['source'] for t in data['latest']},{'atlas','beacon','cobalt'})
        with tempfile.TemporaryDirectory() as directory:
            result=asyncio.run(run_demo(.5,str(Path(directory)/'test.sqlite'),ready=check))
            self.assertGreater(result['stats']['accepted'],10)

if __name__=='__main__':
    unittest.main()
