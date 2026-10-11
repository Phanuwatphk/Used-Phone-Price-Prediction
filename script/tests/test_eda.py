import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.eda.eda_statistics import analyze, duplicate_candidates, outlier_candidates, percentile, spearman, source_comparisons
from analysis.eda.run_eda import DEFAULT_RULES, run, sha, attach_descriptions, body_html
from preparation.shared.prepare_combined_dataset import DEFAULT_SCHEMA, prepare
from script.tests.test_combined_dataset import fixture as source_fixture

RULES = json.loads(DEFAULT_RULES.read_text())


def row(identifier, price, source='ennxo', year=2026):
    return {'listing_id': f'{source}:{identifier}', 'source': source, 'brand': 'Apple', 'model': 'iPhone 13',
            'storage_gb': 128, 'condition': 'used', 'price_thb': float(price),
            'publication_year': year, 'published_at': f'{year}-01-01'}


class EDAStatisticsTests(unittest.TestCase):
    def test_percentiles_and_rank_ties(self):
        self.assertEqual(percentile([0, 10, 20, 30], .25), 7.5)
        self.assertAlmostEqual(spearman([1, 1, 2], [2, 2, 3]), 1)
        self.assertAlmostEqual(spearman([1, 2, 3], [3, 2, 1]), -1)
        self.assertIsNone(spearman([1, 1], [2, 3]))

    def test_outliers_compare_same_year_source_model_and_keep_originals(self):
        rows = [row(i, price) for i, price in enumerate([100, 101, 102, 103, 104, 105, 106, 107, 108, 1000])]
        before = copy.deepcopy(rows)
        flags, fences, summary = outlier_candidates(rows, RULES)
        self.assertEqual(len(flags), 1); self.assertEqual(flags[0]['price_thb'], 1000)
        self.assertEqual(summary['eligible_rows'], 10)
        self.assertEqual(rows, before)
        rows[-1]['publication_year'] = 2025
        flags, fences, summary = outlier_candidates(rows, RULES)
        self.assertFalse(flags); self.assertEqual(summary['skipped_small_group_rows'], 10)

    def test_zero_iqr_is_not_used_to_mark_every_different_price(self):
        rows = [row(i, 100 if i < 9 else 1000) for i in range(10)]
        flags, _, summary = outlier_candidates(rows, RULES)
        self.assertFalse(flags); self.assertEqual(summary['skipped_zero_iqr_rows'], 10)

    def test_source_comparison_requires_same_attributes_and_minimum_each(self):
        rows = [row(i, 100, 'ennxo') for i in range(3)] + [row(i, 200, 'mac2hand') for i in range(3)]
        comparison = source_comparisons(rows, RULES)
        self.assertEqual(len(comparison), 1)
        self.assertEqual(comparison[0]['ennxo_minus_mac2hand_percent'], -50)
        rows[-1]['condition'] = 'new'
        self.assertFalse(source_comparisons(rows, RULES))

    def test_cross_source_text_is_candidate_and_different_price_is_not_match(self):
        rows = [row(1, 100), row(2, 100, 'mac2hand'), row(3, 200)]
        lineage = {r['listing_id']: {'original_csv_row': {}} for r in rows}
        descriptions = {r['listing_id']: 'Phone condition and full product description ' * 5 for r in rows}
        groups, components = duplicate_candidates(rows, lineage, descriptions, RULES)
        self.assertEqual(len(groups), 1); self.assertTrue(groups[0]['cross_source'])
        self.assertFalse(groups[0]['physical_identity_confirmed'])
        self.assertEqual(components[0]['n'], 2)

    def test_overlapping_text_groups_use_components_but_images_stay_separate(self):
        rows = [row(i, 100) for i in range(4)]
        lineage = {r['listing_id']: {'original_csv_row': {'candidate_image_group': 'shared-photo'}} for r in rows}
        for r in rows[:2]:
            lineage[r['listing_id']]['original_csv_row']['candidate_duplicate_group'] = 'pair'
        descriptions = {r['listing_id']: '' for r in rows}
        for r in rows[1:3]:
            descriptions[r['listing_id']] = 'Long exact description ' * 6
        groups, components = duplicate_candidates(rows, lineage, descriptions, RULES)
        self.assertEqual(len(components), 1); self.assertEqual(components[0]['n'], 3)
        self.assertTrue(any(g['method'] == 'source_image_candidate' and g['n'] == 4 for g in groups))

    def test_sensitivity_does_not_modify_or_drop_actual_rows(self):
        rows = [row(1, 100), row(2, 100, 'mac2hand')]
        lineage = {r['listing_id']: {'original_csv_row': {}} for r in rows}
        descriptions = {r['listing_id']: 'Long exact phone condition ' * 5 for r in rows}
        before = copy.deepcopy(rows)
        summary, _, _, _, _ = analyze(rows, lineage, descriptions, RULES)
        self.assertEqual(summary['records'], 2)
        self.assertEqual(summary['sensitivity'][2]['n'], 1)
        self.assertEqual(rows, before)
        self.assertFalse(summary['dataset_modified'])


class EDAWorkflowTests(unittest.TestCase):
    def build_input(self, root):
        datasets = {}
        for source in ('ennxo', 'mac2hand'):
            path = root / f'{source}.csv'; record = source_fixture(source)
            record['price_thb'] = '15000.0' if source == 'ennxo' else '17000.0'
            with path.open('w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=list(record)); writer.writeheader(); writer.writerow(record)
            datasets[source] = {'usable_csv': str(path), 'usable_records': 1, 'snapshot': f'{source}_20261005T120000'}
        registry = root / 'registry.json'; registry.write_text(json.dumps({'datasets': datasets}))
        prepare(registry, DEFAULT_SCHEMA, root / 'input')
        return root / 'input'

    def test_workflow_preserves_inputs_exports_figures_and_separates_private_rows(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary); inputs = self.build_input(root)
            evidence = root / 'evidence'; evidence.mkdir()
            for name in ('lineage.jsonl', 'ennxo_audit.json', 'mac2hand_audit.json',
                         'normalization_changes.json', 'price_review.csv'):
                (inputs / name).rename(evidence / name)
            before = {p.name: sha(p) for p in inputs.iterdir() if p.is_file()}
            evidence_before = {p.name: sha(p) for p in evidence.iterdir()}
            summary = run(inputs, root / 'report', root / 'private', evidence_dir=evidence)
            self.assertEqual(summary['records'], 2)
            self.assertEqual(before, {p.name: sha(p) for p in inputs.iterdir() if p.is_file()})
            self.assertEqual(evidence_before, {p.name: sha(p) for p in evidence.iterdir()})
            self.assertEqual(len(list((root / 'report/figures').glob('*.png'))), 8)
            self.assertEqual(len(list((root / 'report/figures').glob('*.svg'))), 8)
            self.assertTrue((root / 'report/report.html').exists())
            self.assertTrue((root / 'private/outlier_candidates.csv').exists())
            self.assertFalse((root / 'report/outlier_candidates.csv').exists())
            self.assertTrue(json.loads((root / 'private/validation.json').read_text())['row_data_not_in_public_tables'])
            with self.assertRaisesRegex(ValueError, 'overlap'):
                run(inputs, root / 'report', root / 'report/private')

    def test_jsonl_csv_mismatch_is_rejected_before_outputs(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary); inputs = self.build_input(root)
            rows = [json.loads(line) for line in (inputs / 'dataset.jsonl').read_text().splitlines()]
            rows[0]['price_thb'] += 100
            (inputs / 'dataset.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'JSONL differs'):
                run(inputs, root / 'report', root / 'private')
            self.assertFalse((root / 'report').exists())

    def test_supplementary_descriptions_must_match_original_source_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); record = source_fixture('mac2hand')
            normalized = {**record, 'listing_id': 'mac2hand:123'}
            lineage = {'mac2hand:123': {'original_csv_row': record}}
            detail = {'product_id': '123', 'disposition': 'accepted',
                      'clean': {k: record[k] for k in ('brand', 'model', 'condition', 'storage_gb', 'price_thb', 'published_at')},
                      'original': {'detail': {'description': 'Source description'}}}
            path = root / 'details.jsonl'; path.write_text(json.dumps(detail)+'\n')
            self.assertEqual(attach_descriptions([normalized], lineage, path)['mac2hand:123'], 'Source description')
            detail['clean']['price_thb'] = '99999'; path.write_text(json.dumps(detail)+'\n')
            with self.assertRaisesRegex(ValueError, 'price/storage differs'):
                attach_descriptions([normalized], lineage, path)

    def test_html_uses_tables_and_escapes_content(self):
        result = body_html('| Name | Value |\n|---|---|\n| Price | <script> |')
        self.assertIn('<table>', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('<script>', result)


if __name__ == '__main__':
    unittest.main()
