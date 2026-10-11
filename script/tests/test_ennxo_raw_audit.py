import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from preparation.ennxo.audit_ennxo_raw import audit, inventory, read_records


class RawAuditTests(unittest.TestCase):
    def fixture(self, root):
        raw = root / 'raw'
        (raw / 'pages').mkdir(parents=True)
        rows = [{'url': f'https://www.ennxo.com/product/{i}', 'name': 'ชื่อเหมือนกัน\u2028แต่คนละประกาศ',
                 'brand': None, 'model': 'Samsung', 'storage': '128GB', 'price': 1,
                 'source': 'ennxo', 'currency': 'THB', 'page': 1} for i in (1, 2)]
        (raw / 'listings.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
        (raw / 'ennxo_summary.json').write_text(json.dumps({'raw_records': 2, 'unique_product_urls': 2, 'completed_pages': 1, 'complete': True}))
        (raw / 'pages/page_1.html').write_text(''.join(f'<div class="product-card-top-div"><a href="/product/{i}">สินค้า</a></div>' for i in (1, 2)))
        return raw

    def test_repeatable_preserves_raw_and_does_not_exclude_same_titles_or_low_prices(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            raw = self.fixture(root)
            before = inventory(raw)
            first = audit(raw, root / 'first')
            audit(raw, root / 'second')
            self.assertEqual(inventory(raw), before)
            self.assertEqual(first['records'], 2)
            self.assertEqual(first['records_excluded'], 0)
            self.assertEqual(len(first['repeated_titles']), 1)
            self.assertEqual(first['duplicate_urls'], [])
            self.assertEqual(first['prices']['min'], 1)
            self.assertEqual(first['issue_counts']['missing_brand'], 2)
            for path in (root / 'first').iterdir():
                if path.name != 'run_metadata.json':
                    self.assertEqual(path.read_bytes(), (root / 'second' / path.name).read_bytes())

    def test_html_mismatch_fails_with_report_instead_of_declaring_complete(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            raw = self.fixture(root)
            page = raw / 'pages/page_1.html'
            page.write_text(page.read_text().replace('/product/2', '/product/3'))
            with self.assertRaisesRegex(ValueError, 'accounting failed'):
                audit(raw, root / 'result')
            self.assertFalse(json.loads((root / 'result/profile.json').read_text())['accounting']['passed'])

    def test_refuses_output_in_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = self.fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError, 'separate'):
                audit(raw, raw / 'audit')
            self.assertFalse((raw / 'audit').exists())

    def test_json_line_boundaries_and_nonstandard_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = self.fixture(Path(tmp))
            self.assertEqual(len(read_records(raw / 'listings.jsonl')), 2)
            (raw / 'listings.jsonl').write_text('{"price":NaN}\n')
            with self.assertRaisesRegex(ValueError, 'line 1'):
                read_records(raw / 'listings.jsonl')


if __name__ == '__main__':
    unittest.main()
