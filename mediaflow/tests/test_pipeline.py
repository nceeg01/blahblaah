import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from pipeline import read_source, transform, save_database

class PipelineTests(unittest.TestCase):
    def test_database_and_quarantine(self):
        row = dict(id='a', title=' A  title ', platform='WEB', published_at='2024-02-29', views='1,000', engagements='50')
        result = transform([dict(row, published_at='2025-02-29'), row, row])
        self.assertEqual([len(result[k]) for k in ('accepted', 'rejected', 'duplicates')], [1, 1, 1])
        self.assertEqual(result['accepted'][0]['engagement_rate'], 5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.sqlite'
            self.assertEqual(save_database(path, result), 1)
            self.assertEqual(save_database(path, result), 2)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM content').fetchone()[0], 2)
                self.assertEqual(db.execute('SELECT count(*) FROM quarantine').fetchone()[0], 4)
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.json'
            for value in ({}, [], [None]):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    read_source(path)
        with self.assertRaises(ValueError):
            transform([{'no': 'columns'}])

if __name__ == '__main__':
    unittest.main()
