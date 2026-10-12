"""Temporal isolation, training-only encoders, input validation and inference contracts."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from script.modeling.features import features, prices
from script.modeling.predict import predict_rows, load_model
from script.modeling.split_dataset import read_dataset, sha, split_rows, protected_output
from script.modeling.model_v1.train_models import build_model, metrics, train



from script.artifacts import read_metadata

def listing(i, day=None):
    source = 'ennxo' if i % 2 else 'mac2hand'
    return {'listing_id': f'{source}:{i}', 'product_id': str(i), 'url': f'https://example.org/{source}/{i}',
            'source': source, 'source_snapshot': 'fixture', 'brand': 'Apple', 'model': 'iPhone 12',
            'storage_gb': '128', 'condition': 'used', 'price_thb': str(10000 + 50*i),
            'published_at': day or f'2024-01-{1+i//2:02d}', 'published_at_raw': 'fixture', 'published_at_precision': 'day'}


class ModelingTests(unittest.TestCase):
    def test_same_day_never_crosses_split_and_input_order_does_not_matter(self):
        rows = [listing(i) for i in range(40)]
        a = split_rows(rows, .7, .15)
        b = split_rows(list(reversed(rows)), .7, .15)
        self.assertEqual(a, b)
        self.assertEqual(sum(map(len, a.values())), len(rows))
        self.assertLess(max(r['published_at'] for r in a['train']), min(r['published_at'] for r in a['validation']))
        self.assertLess(max(r['published_at'] for r in a['validation']), min(r['published_at'] for r in a['test']))
        with self.assertRaises(ValueError):
            split_rows([listing(i, '2024-01-01') for i in range(10)])

    def test_features_do_not_read_target_identifiers_or_other_source_metadata(self):
        row = listing(1)
        changed = {**row, 'price_thb': '99999999', 'product_id': 'other', 'listing_id': 'other', 'url': 'changed', 'source_snapshot': 'future'}
        self.assertTrue(features([row]).equals(features([changed])))
        self.assertNotIn('price_thb', features([row]).columns)

    def test_unseen_model_does_not_fit_encoder_to_validation(self):
        training = [listing(i) for i in range(20)]
        model = build_model({'kind': 'ridge', 'parameters': {'alpha': 10}})
        model.fit(features(training), np.array([float(r['price_thb']) for r in training]))
        category_before = copy.deepcopy(model.named_steps['features'].named_transformers_['categorical'].categories_)
        new = {**listing(21), 'model': 'Never seen model 99', 'brand': 'Honor'}
        predicted = prices(model, features([new]))
        self.assertTrue(np.isfinite(predicted).all())
        category_after = model.named_steps['features'].named_transformers_['categorical'].categories_
        self.assertTrue(all(np.array_equal(a, b) for a, b in zip(category_before, category_after)))
        self.assertFalse(any('Never seen model 99' in x for x in category_after))

    def test_invalid_inputs_and_protected_output_are_rejected(self):
        for change in [{'storage_gb': 'nan'}, {'storage_gb': '-1'}, {'published_at': '2024-99-01'}, {'condition': 'broken'}]:
            with self.assertRaises(ValueError):
                features([{**listing(1), **change}])
        with tempfile.TemporaryDirectory() as temp:
            dataset = Path(temp)/'dataset.csv'
            rows = [listing(1), listing(1)]
            with dataset.open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
            with self.assertRaises(ValueError):
                read_dataset(dataset)
            with self.assertRaises(ValueError):
                read_dataset(dataset, 'incorrect-checksum')
            with self.assertRaises(ValueError):
                protected_output(dataset, [dataset])

    def test_metrics_are_in_baht(self):
        result = metrics([1000, 2000], [1100, 1800])
        self.assertEqual(result['mae_thb'], 150)
        self.assertEqual(result['bias_thb'], -50)

    def test_pipeline_saves_loadable_artifact_without_training_on_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root/'dataset.csv'
            rows = [listing(i) for i in range(40)]
            with dataset.open('w', newline='') as handle:
                w = csv.DictWriter(handle, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
            config = {'run':'fixture','dataset':str(dataset),'dataset_sha256':sha(dataset),'expected_rows':40,
                      'required_training_sources':['ennxo','mac2hand'],'random_seed':42,'threads':1,
                      'split':{'train_fraction':.7,'validation_fraction':.15},'selection_metric':'validation_mae_thb',
                      'selection_bias':'fixture', 'candidates':[{'name':'median','kind':'median','parameters':{}}]}
            config_path = root/'config.json'; config_path.write_text(json.dumps(config))
            before = dataset.read_bytes()
            summary = train(config_path, root/'report', root/'model', root/'private')
            artifact = load_model(root/'model/model.joblib')
            fit = split_rows(rows,.7,.15)
            target = float(np.median([float(r['price_thb']) for r in fit['train']+fit['validation']]))
            result = predict_rows(artifact, [fit['test'][0]])[0]
            self.assertEqual(result['predicted_price_thb'], target)
            self.assertEqual(summary['test']['rows'], len(fit['test']))
            self.assertEqual(dataset.read_bytes(), before)
            validation = read_metadata(root/'report', 'validation')
            self.assertFalse(validation['test_used_for_fit'])
            self.assertIn('date_outside_training_range', result['coverage_flags'])
            (root/'model/model.joblib').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                load_model(root/'model/model.joblib')


if __name__ == '__main__':
    unittest.main()
