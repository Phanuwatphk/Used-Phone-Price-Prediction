import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from script.preparation.ennxo.audit_ennxo_raw import dump
from script.preparation.ennxo.finalize_ennxo_manual_review import finalize
from script.preparation.ennxo.cleaning_rules import apply_correction, clean_row
from script.tests.test_ennxo_cleaning import row, RULES


class ManualReviewTests(unittest.TestCase):
    def fixture(self, root):
        baseline, current = root / 'baseline', root / 'current'
        baseline.mkdir(); current.mkdir()
        evidence = {'title': 'phone', 'selected_price': 5000, 'selected_subfields': {},
                    'description_lines': [{'line': 1, 'text': 'จอแตก'}],
                    'page_file': 'pages/page_1.html', 'page_sha256': 'pagehash'}
        original = {'embedded_product': {'name': 'phone', 'price': 5000, 'subfields': {}, 'detail': 'จอแตก'},
                    'provenance': {'page_file': evidence['page_file'], 'page_sha256': evidence['page_sha256']}}
        before, after, reviews = [], [], []
        for n, reasons in enumerate(([], ['reported_damage_or_lock'], ['storage_conflict'])):
            old = {'url': str(n), 'product_id': str(n), 'input_sha256': 'same' + str(n), 'status': 'needs_review',
                   'hold_reasons': ['model_conflict'], 'exclusion_reasons': [], 'original': original, 'clean': {}}
            new = {**old, 'status': 'needs_review' if reasons else 'accepted', 'hold_reasons': reasons}
            before.append(old); after.append(new)
            reviews.append({'url': str(n), 'product_id': str(n), 'input_sha256': old['input_sha256'],
                            'reviewer': 'reviewer', 'reviewed_on': '2026-10-11', 'reason': 'source reviewed',
                            'evidence': copy.deepcopy(evidence)})
        for directory, rows in ((baseline, before), (current, after)):
            (directory / 'ennxo_cleaned.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        ledger = root / 'manual.json'
        dump(ledger, {'schema_version': 1, 'round': 'test', 'baseline': str(baseline), 'reviews': reviews})
        return current, ledger

    def test_reviewed_damage_is_distinct_from_usable_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp); current, ledger = self.fixture(root)
            before = (current / 'ennxo_cleaned.jsonl').read_bytes()
            result = finalize(current, ledger, root / 'output')
            self.assertEqual(result['disposition_counts'], {'accepted': 1, 'awaiting_evidence': 1, 'confirmed_damage_or_lock': 1})
            self.assertEqual(result['unreviewed_records'], 0)
            self.assertEqual(before, (current / 'ennxo_cleaned.jsonl').read_bytes())

    def test_incomplete_duplicate_or_stale_manual_coverage_is_rejected(self):
        for change in ('missing', 'duplicate', 'stale', 'misquote'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); current, ledger = self.fixture(root)
                value = json.loads(ledger.read_text())
                if change == 'missing': value['reviews'].pop()
                if change == 'duplicate': value['reviews'].append(value['reviews'][0])
                if change == 'stale': value['reviews'][0]['input_sha256'] = 'wrong'
                if change == 'misquote': value['reviews'][0]['evidence']['description_lines'][0]['text'] = 'ไม่แตก'
                dump(ledger, value)
                with self.assertRaises(ValueError): finalize(current, ledger, root / 'output')
                self.assertFalse((root / 'output').exists())

    def test_corrected_identity_preserves_newly_discovered_storage_hold(self):
        result = clean_row(row(), RULES, {})
        entry = {'action': 'correct', 'input_sha256': result['input_sha256'], 'values': {'model': 'iPhone 13'},
                 'additional_hold_reasons': ['reviewed_storage_unconfirmed'],
                 'reason': 'wrong source capacity', 'reviewer': 'reviewer', 'evidence': 'source text'}
        apply_correction(result, entry, RULES)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('reviewed_storage_unconfirmed', result['hold_reasons'])
        entry['additional_hold_reasons'] = ['unknown_reason']
        with self.assertRaisesRegex(ValueError, 'additional reviewed holds'):
            apply_correction(result, entry, RULES)
