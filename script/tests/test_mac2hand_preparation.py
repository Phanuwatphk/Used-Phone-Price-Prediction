import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from script.preparation.mac2hand.prepare_mac2hand import prepare, checksums
from script.preparation.mac2hand.clean_mac2hand import clean_dataset
from script.scraper.mac2hand.mac2hand import parse_detail
from script.tests.test_mac2hand import detail_html


class MacPreparationTests(unittest.TestCase):
    def snapshot(self, folder):
        raw = Path(folder) / 'raw'; (raw / 'details').mkdir(parents=True); (raw / 'pages').mkdir()
        (raw / 'pages/page_1.html').write_text('saved category', encoding='utf-8')
        html = detail_html()
        (raw / 'details/product_123.html').write_text(html, encoding='utf-8')
        card = {'product_id': '123', 'url': 'https://mac2hand.com/detail/123/',
                'name': 'iPhone 13', 'badges': ['128GB'], 'price': 15000,
                'published_date': None, 'scraped_at': '2026-10-06T00:00:00+07:00'}
        (raw / 'listings.jsonl').write_text(json.dumps(card) + '\n', encoding='utf-8')
        (raw / 'mac2hand_summary.json').write_text(json.dumps({'complete': True, 'records': 1, 'pages': 1}))
        (raw / 'collection_progress.json').write_text(json.dumps({'status': 'collection_finished'}))
        (raw / 'details/manifest.json').write_text(json.dumps({'123': {'status': 'ok', 'detail': parse_detail(html, '123')}}))
        return raw

    def test_full_offline_workflow_preserves_raw_and_accounts_for_every_row(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = self.snapshot(folder); before = checksums(raw); output = Path(folder) / 'processed'
            with contextlib.redirect_stdout(io.StringIO()):
                audit = prepare(raw, output)
                result = clean_dataset(raw, output / 'extraction', output / 'clean')
            self.assertEqual(audit['parsed_details'], 1)
            self.assertEqual(result['input_records'], 1)
            self.assertEqual(sum(result['status_counts'].values()), 1)
            self.assertEqual(checksums(raw), before)
            self.assertTrue((output / 'clean/needs_review.csv').exists())

    def test_active_collection_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = self.snapshot(folder)
            (raw / 'collection_progress.json').write_text(json.dumps({'status': 'running'}))
            with self.assertRaisesRegex(ValueError, 'has not finished'):
                prepare(raw, Path(folder) / 'processed')

    def test_raw_mutation_after_extraction_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = self.snapshot(folder); output = Path(folder) / 'processed'
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(raw, output)
            (raw / 'details/product_123.html').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'audited snapshot'):
                clean_dataset(raw, output / 'extraction', output / 'clean')

    def test_manifest_mismatch_is_held(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = self.snapshot(folder); output = Path(folder) / 'processed'
            path = raw / 'details/manifest.json'; manifest = json.loads(path.read_text())
            manifest['123']['detail']['price_thb'] = 999; path.write_text(json.dumps(manifest))
            with contextlib.redirect_stdout(io.StringIO()):
                audit = prepare(raw, output)
            self.assertEqual(audit['rows_with_errors'], 1)
            row = json.loads((output / 'extraction/mac2hand_extracted.jsonl').read_text())
            self.assertIn('manifest_detail_mismatch', row['extraction_errors'])


if __name__ == '__main__':
    unittest.main()
