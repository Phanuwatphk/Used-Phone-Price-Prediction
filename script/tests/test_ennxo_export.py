import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from script.preparation.ennxo.export_ennxo_dataset import export



from script.artifacts import write_metadata

class ENNXOExportTests(unittest.TestCase):
    def test_direct_cli_exports_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            output = root / 'accepted'
            entry = Path(__file__).resolve().parents[1] / 'preparation/ennxo/export_ennxo_dataset.py'
            result = subprocess.run([sys.executable, '-B', str(entry), '--input', str(source),
                                     '--output', str(output)], cwd=root, capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / 'dataset.csv').read_bytes(), (source / 'accepted.csv').read_bytes())
            self.assertEqual(sorted(path.name for path in output.iterdir()), ['dataset.csv', 'metadata.json'])

    def fixture(self, root):
        source = root / 'clean'; source.mkdir()
        row = {'product_id': '123', 'source': 'ennxo', 'status': 'accepted',
               'url': 'https://www.ennxo.com/product/123', 'brand': 'Apple',
               'model': 'iPhone 13', 'storage_gb': 128, 'condition': 'used',
               'price_thb': 10000, 'published_at': '2026-10-05T10:00:00Z'}
        with (source / 'accepted.csv').open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
        cleaned = {k: row[k] for k in ('product_id', 'source', 'status', 'url')}
        cleaned.update(clean={k: row[k] for k in ('brand', 'model', 'storage_gb', 'condition', 'price_thb', 'published_at')},
                       hold_reasons=[], exclusion_reasons=[])
        (source / 'ennxo_cleaned.jsonl').write_text(json.dumps(cleaned) + '\n')
        write_metadata(source, 'summary', {'snapshot': 'fixture', 'input_records': 1,
                                                        'status_counts': {'accepted': 1}})
        return source

    def test_export_preserves_csv_bytes_and_inputs(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary); source = self.fixture(root)
            before = {p.name: p.read_bytes() for p in source.iterdir()}
            self.assertEqual(export(source, root / 'final')['records'], 1)
            self.assertEqual((root / 'final/dataset.csv').read_bytes(), before['accepted.csv'])
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})

    def test_rejects_changed_accepted_value_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = self.fixture(root)
            path = source / 'accepted.csv'; path.write_text(path.read_text().replace('10000', '20000'))
            with self.assertRaisesRegex(ValueError, 'differ from cleaned evidence'):
                export(source, root / 'final')
            self.assertFalse((root / 'final').exists())

    def test_rejects_output_overlapping_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'overlaps'):
                export(source, root)
