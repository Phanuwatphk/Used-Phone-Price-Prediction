import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from script.preparation.mac2hand.review_mac2hand_queue import apply_decision, fingerprint, next_action, review, sha
from script.preparation.mac2hand.clean_mac2hand import clean_row
from script.tests.test_mac2hand_cleaning import extracted, RULES


def held():
    source = extracted(); source['detail']['title'] = source['raw_listing']['name'] = 'iPhone 13 Pro Max 256 สีดำ'
    row = clean_row(source, RULES)
    assert row['hold_reasons'] == ['storage_missing']
    return row


def decision(row):
    return {'product_id': row['product_id'], 'url': row['url'], 'input_sha256': fingerprint(row),
            'disposition': 'corrected', 'patch': {'storage_gb': 256}, 'resolved_reasons': ['storage_missing'],
            'rationale': 'Reviewed abbreviated capacity after model and before color',
            'evidence': [{'path': 'detail.title', 'quote': '256 สีดำ'}]}


class MacReviewTests(unittest.TestCase):
    def test_evidenced_patch_preserves_original_and_baseline(self):
        row = held(); original = copy.deepcopy(row)
        result = apply_decision(row, decision(row))
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['clean']['storage_gb'], 256)
        self.assertEqual(result['original'], row['original'])
        self.assertEqual(row, original)

    def test_other_holds_cannot_be_silently_removed(self):
        row = held(); row['hold_reasons'].append('possible_damage_or_lock')
        result = apply_decision(row, decision(row))
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['hold_reasons'], ['possible_damage_or_lock'])
        bad = decision(row); bad['resolved_reasons'] = ['possible_damage_or_lock']
        with self.assertRaises(ValueError): apply_decision(row, bad)

    def test_hash_and_literal_evidence_required(self):
        row = held(); bad = decision(row); bad['input_sha256'] = 'wrong'
        with self.assertRaises(ValueError): apply_decision(row, bad)
        bad = decision(row); bad['evidence'][0]['quote'] = 'not in source'
        with self.assertRaises(ValueError): apply_decision(row, bad)

    def test_unknown_storage_and_unresolved_patch_rejected(self):
        row = held(); bad = decision(row); bad['patch']['storage_gb'] = 999
        with self.assertRaises(ValueError): apply_decision(row, bad)
        bad = decision(row); bad['disposition'] = 'awaiting_evidence'
        with self.assertRaises(ValueError): apply_decision(row, bad)

    def test_awaiting_evidence_retains_values_and_holds(self):
        row = held(); d = decision(row); d.update(disposition='awaiting_evidence', patch={}, resolved_reasons=[])
        result = apply_decision(row, d)
        self.assertEqual(result['clean'], row['clean'])
        self.assertEqual(result['hold_reasons'], row['hold_reasons'])
        self.assertEqual(result['status'], 'needs_review')

    def test_full_workflow_and_duplicate_decision_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); raw = root/'input'; raw.mkdir(); path = raw/'clean.jsonl'; ledger = root/'ledger.json'
            row = held(); passed = clean_row(extracted(), RULES); passed['product_id'] = '456'; passed['url'] += '456'
            path.write_text('\n'.join(json.dumps(r) for r in [row, passed])+'\n')
            baseline = sha(path)
            data = {'baseline_sha256': baseline, 'reviews': [decision(row)]}; ledger.write_text(json.dumps(data))
            with contextlib.redirect_stdout(io.StringIO()): result = review(path, ledger, root/'output')
            self.assertEqual(result['newly_accepted'], 1)
            self.assertEqual(result['final_status_counts']['accepted'], 2)
            self.assertEqual(sha(path), baseline)
            with (root/'output/mac2hand_reviewed.jsonl').open() as file:
                outputs=[json.loads(l) for l in file]
            self.assertEqual(outputs[1], passed)
            data['reviews'] *= 2; ledger.write_text(json.dumps(data))
            with self.assertRaises(ValueError): review(path, ledger, root/'output')

    def test_missing_source_has_priority_over_model_conflict(self):
        row = held(); row['hold_reasons'] += ['detail_unavailable_or_unverified', 'multiple_or_conflicting_models']
        self.assertEqual(next_action(row)[0], 'missing_source')

    def test_baseline_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=root/'input/data.jsonl'; path.parent.mkdir()
            path.write_text(json.dumps(held())+'\n'); ledger=root/'ledger.json'
            ledger.write_text(json.dumps({'baseline_sha256':'wrong','reviews':[]}))
            with self.assertRaises(ValueError): review(path,ledger,root/'output')


if __name__ == '__main__': unittest.main()
