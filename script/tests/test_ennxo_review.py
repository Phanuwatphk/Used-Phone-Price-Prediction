import contextlib
import copy
import io
import tempfile
import unittest
from pathlib import Path

from script.preparation.ennxo.audit_ennxo_raw import dump
from script.preparation.ennxo.review_ennxo_queue import review
import json


class ReviewTests(unittest.TestCase):
    def test_accounts_for_resolved_queue_and_new_holds(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            old, current = root / 'old', root / 'current'
            old.mkdir(); current.mkdir()
            row = {'url': 'u1', 'product_id': '1', 'input_sha256': 'same', 'status': 'needs_review',
                   'hold_reasons': ['model_conflict'], 'exclusion_reasons': [], 'clean': {}, 'evidence': {},
                   'original': {'provenance': {'page_file': 'page_1.html'}}}
            extra = copy.deepcopy(row); extra.update(url='u2', product_id='2', status='accepted', hold_reasons=[])
            changed = copy.deepcopy(row); changed.update(status='accepted', hold_reasons=[], review_correction={'action': 'correct'})
            new_hold = copy.deepcopy(extra); new_hold.update(status='needs_review', hold_reasons=['reported_damage_or_lock'])
            for directory, rows in [(old, [row, extra]), (current, [changed, new_hold])]:
                (directory / 'ennxo_cleaned.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            before = (current / 'ennxo_cleaned.jsonl').read_bytes()
            summary = review(old, current, root / 'report')
            self.assertEqual(summary['reported_rows'], 2)
            self.assertEqual(summary['transitions']['needs_review -> accepted'], 1)
            self.assertEqual(summary['transitions']['accepted -> needs_review'], 1)
            self.assertEqual(summary['current_evidence_corrections'], 1)
            self.assertEqual(before, (current / 'ennxo_cleaned.jsonl').read_bytes())

    def test_changed_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old, current = root / 'old', root / 'current'
            old.mkdir(); current.mkdir()
            for directory, fingerprint in [(old, 'old'), (current, 'changed')]:
                (directory / 'ennxo_cleaned.jsonl').write_text(json.dumps({'url': 'u', 'input_sha256': fingerprint})+'\n')
            with self.assertRaisesRegex(ValueError, 'Evidence changed'):
                review(old, current, root / 'report')
