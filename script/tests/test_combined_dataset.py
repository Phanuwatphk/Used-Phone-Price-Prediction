import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from script.preparation.shared.prepare_combined_dataset import DEFAULT_SCHEMA, normalize, prepare, standard_date

SCHEMA = json.loads(DEFAULT_SCHEMA.read_text())


def fixture(source='ennxo'):
    path = 'product' if source == 'ennxo' else 'detail'
    return {'source': source, 'product_id': '123', 'url': f'https://{source}.com/{path}/123/',
            'brand': 'Apple', 'model': 'iPhone SE 2020', 'storage_gb': '128',
            'condition': 'used', 'price_thb': '15000.0', 'published_at': '2026-10-04',
            'hold_reasons': '', 'exclusion_reasons': ''}


class CombinedDatasetTests(unittest.TestCase):
    def test_source_present_or_filled_only_after_url_verification(self):
        row = fixture(); row.pop('source')
        result = normalize(row, 'ennxo', 'ennxo_20261005T120000_Asia-Bangkok', SCHEMA)
        self.assertEqual(result['source'], 'ennxo')
        self.assertEqual(result['listing_id'], 'ennxo:123')
        row['url'] = 'https://mac2hand.com/detail/123/'
        with self.assertRaisesRegex(ValueError, 'domain mismatch'):
            normalize(row, 'ennxo', 'snapshot', SCHEMA)

    def test_contradictory_source_or_identity_never_overwritten(self):
        row = fixture(); row['source'] = 'mac2hand'
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            normalize(row, 'ennxo', 'snapshot', SCHEMA)
        row = fixture(); row['product_id'] = '456'
        with self.assertRaisesRegex(ValueError, 'ID/URL'):
            normalize(row, 'ennxo', 'snapshot', SCHEMA)

    def test_dates_keep_original_precision_and_convert_utc_to_thai_date(self):
        self.assertEqual(standard_date('2026-10-04T21:17:56Z', 'Asia/Bangkok'), ('2026-10-05', 'timestamp'))
        self.assertEqual(standard_date('2010-04-02', 'Asia/Bangkok'), ('2010-04-02', 'day'))
        with self.assertRaisesRegex(ValueError, 'timezone'):
            standard_date('2026-10-04T21:17:56', 'Asia/Bangkok')
        row = fixture(); row['published_at'] = '2026-10-04T21:17:56Z'
        result = normalize(row, 'ennxo', 'snapshot', SCHEMA)
        self.assertEqual(result['published_at_raw'], row['published_at'])

    def test_numeric_types_aliases_and_variants_preserved(self):
        row = fixture(); result = normalize(row, 'ennxo', 'snapshot', SCHEMA)
        self.assertIsInstance(result['product_id'], str)
        self.assertIsInstance(result['storage_gb'], int)
        self.assertEqual(result['model'], 'iPhone SE 2')
        row.update(brand='Samsung', model='Galaxy Z Flip4')
        self.assertEqual(normalize(row, 'ennxo', 'snapshot', SCHEMA)['model'], 'Galaxy Z Flip 4')
        row.update(brand='Samsung', model='Galaxy S23 FE')
        self.assertEqual(normalize(row, 'ennxo', 'snapshot', SCHEMA)['model'], 'Galaxy S23 FE')

    def test_invalid_rows_are_not_silently_included(self):
        for key, value in [('storage_gb', '128.5'), ('price_thb', 'NaN'), ('price_thb', '-1'),
                           ('price_thb', '1.001'), ('condition', 'unknown'), ('model', ''),
                           ('status', 'needs_review'), ('hold_reasons', 'conflict'),
                           ('published_at', '2026-10-07')]:
            with self.subTest(key=key, value=value):
                row = fixture(); row[key] = value
                with self.assertRaises(ValueError):
                    normalize(row, 'ennxo', 'ennxo_20261005T120000_Asia-Bangkok', SCHEMA)

    def fixture_registry(self, root):
        datasets = {}
        for source in ('ennxo', 'mac2hand'):
            path = root / f'{source}.csv'; row = fixture(source)
            with path.open('w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
            datasets[source] = {'usable_csv': str(path), 'usable_records': 1, 'snapshot': f'{source}_20261005T120000'}
        registry = root / 'datasets.json'; registry.write_text(json.dumps({'datasets': datasets}))
        return registry, datasets

    def test_merge_namespaces_ids_keeps_lineage_inputs_and_repeats(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary); registry, datasets = self.fixture_registry(root)
            before = {site: Path(info['usable_csv']).read_bytes() for site, info in datasets.items()}
            for name in ('first', 'second'):
                summary = prepare(registry, DEFAULT_SCHEMA, root / name)
                self.assertEqual(summary['source_counts'], {'ennxo': 1, 'mac2hand': 1})
                self.assertFalse(summary['deduplicated'])
            for site, info in datasets.items():
                self.assertEqual(Path(info['usable_csv']).read_bytes(), before[site])
            self.assertEqual((root / 'first/dataset.csv').read_bytes(), (root / 'second/dataset.csv').read_bytes())
            rows = [json.loads(line) for line in (root / 'first/lineage.jsonl').read_text().splitlines()]
            self.assertEqual({r['listing_id'] for r in rows}, {'ennxo:123', 'mac2hand:123'})
            self.assertTrue(all(r['original_csv_row']['model'] == 'iPhone SE 2020' for r in rows))

    def test_registry_count_and_output_overlap_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); registry, datasets = self.fixture_registry(root)
            with self.assertRaisesRegex(ValueError, 'overlaps'):
                prepare(registry, DEFAULT_SCHEMA, root)
            value = json.loads(registry.read_text()); value['datasets']['ennxo']['usable_records'] = 2
            registry.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'count differs'):
                prepare(registry, DEFAULT_SCHEMA, root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_separate_audit_directory_keeps_final_dataset_and_protects_inputs(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary); registry, _ = self.fixture_registry(root)
            prepare(registry, DEFAULT_SCHEMA, root / 'final', root / 'intermediate')
            self.assertTrue((root / 'final/dataset.jsonl').exists())
            self.assertFalse((root / 'final/lineage.jsonl').exists())
            self.assertTrue((root / 'intermediate/lineage.jsonl').exists())
            self.assertTrue((root / 'intermediate/price_review.csv').exists())
            with self.assertRaisesRegex(ValueError, 'overlap'):
                prepare(registry, DEFAULT_SCHEMA, root / 'out', root)

    def test_duplicate_source_product_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); registry, datasets = self.fixture_registry(root)
            path = Path(datasets['ennxo']['usable_csv']); row = fixture()
            with path.open('w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=list(row)); writer.writeheader(); writer.writerows([row, row])
            value = json.loads(registry.read_text()); value['datasets']['ennxo']['usable_records'] = 2
            registry.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'duplicate product identities'):
                prepare(registry, DEFAULT_SCHEMA, root / 'out')


if __name__ == '__main__':
    unittest.main()
