import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from script.preparation.shared.select_model_input import select



from script.artifacts import reference_sha, write_metadata

class ModelInputSelectionTests(unittest.TestCase):
    def fixture(self, root, unknown=False, wrong_count=False):
        fields = ['listing_id', 'source', 'price_thb', 'published_at', 'brand']
        rows = [{'listing_id': f'ennxo:{i}', 'source': 'ennxo', 'price_thb': 10000+i,
                 'published_at': '2026-10-05', 'brand': 'Apple'} for i in range(1, 5)]
        def csv_file(name, headers, content):
            p=root/name
            with p.open('w', encoding='utf-8-sig', newline='') as file:
                writer=csv.DictWriter(file,fieldnames=headers);writer.writeheader();writer.writerows(content)
            return p
        csv_file('dataset.csv',fields,rows)
        (root/'dataset.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        write_metadata(root, 'schema', {'fields':dict.fromkeys(fields,'fixture')})
        (root/'lineage.jsonl').write_text(''.join(json.dumps({'listing_id':row['listing_id'],'original_csv_row':row})+'\n' for row in rows))
        csv_file('outliers.csv',['listing_id'],[{'listing_id':'ennxo:1'}])
        csv_file('price_extremes.csv',['listing_id'],[{'listing_id':'ennxo:1'},{'listing_id':'ennxo:99' if unknown else 'ennxo:2'}])
        (root/'text_components.json').write_text(json.dumps([{'listing_ids':['ennxo:2','ennxo:3']}]))
        names={'dataset_csv':'dataset.csv','dataset_jsonl':'dataset.jsonl','schema':'metadata.json#schema',
               'lineage':'lineage.jsonl','outliers':'outliers.csv','price_extremes':'price_extremes.csv','text_components':'text_components.json'}
        paths={key:root/name for key,name in names.items()}
        policy={'version':1,'action':'exclude_all_queue_members','inputs':{key:str(path) for key,path in paths.items()},
                'input_sha256':{key:reference_sha(path) for key,path in paths.items()},
                'expected_counts':{'input':4,'excluded':2 if wrong_count else 3,'retained':2 if wrong_count else 1}}
        p=root/'policy.json';p.write_text(json.dumps(policy));return p,rows

    def test_union_accounts_overlap_preserves_values_and_lineage_and_repeats(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            root=Path(temp);policy,rows=self.fixture(root)
            before={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
            summary=select(policy,root/'final',root/'audit')
            self.assertEqual(summary['retained'],1);self.assertEqual(summary['excluded'],3)
            self.assertEqual(summary['overlapping_queue_memberships'],2)
            self.assertEqual(json.loads((root/'audit/dataset.jsonl').read_text()),rows[-1])
            self.assertEqual(json.loads((root/'audit/lineage.jsonl').read_text())['listing_id'],'ennxo:4')
            with (root/'audit/excluded_rows.csv').open(encoding='utf-8-sig',newline='') as f:excluded=list(csv.DictReader(f))
            self.assertEqual(excluded[0]['selection_reasons'],'outliers|price_extremes')
            self.assertEqual(excluded[1]['selection_reasons'],'price_extremes|text_candidates')
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir() if p.is_file()})
            select(policy,root/'repeat',root/'repeat-audit')
            self.assertEqual((root/'final/dataset.csv').read_bytes(),(root/'repeat/dataset.csv').read_bytes())

    def test_unknown_queue_id_rejected_before_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);policy,_=self.fixture(root,unknown=True)
            with self.assertRaisesRegex(ValueError,'unknown listing'):
                select(policy,root/'final',root/'audit')
            self.assertFalse((root/'final').exists())

    def test_changed_input_hash_and_wrong_counts_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);policy,_=self.fixture(root,wrong_count=True)
            with self.assertRaisesRegex(ValueError,'counts differ'):
                select(policy,root/'final',root/'audit')
            p=root/'outliers.csv';p.write_text(p.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'snapshot hashes'):
                select(policy,root/'final',root/'audit')
            self.assertFalse((root/'final').exists())

    def test_input_overlap_and_overlapping_outputs_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);policy,_=self.fixture(root)
            with self.assertRaisesRegex(ValueError,'protected input'):
                select(policy,root,root/'audit')
            with self.assertRaisesRegex(ValueError,'outputs overlap'):
                select(policy,root/'final',root/'final/audit')
