"""Offline UI contracts with a temporary, checked model rather than private artifacts."""
import csv
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import joblib
from sklearn.dummy import DummyRegressor
from streamlit.testing.v1 import AppTest

from script.modeling.features_v2 import FEATURES, features
from script.modeling.predict import predict_rows
from script.modeling.split_dataset import sha

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'script/app/app.py'


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / 'model.joblib'
        rows = [{'source': 'mac2hand', 'brand': brand, 'model': model, 'storage_gb': 128,
                 'condition': 'used', 'published_at': '2026-10-06'}
                for brand, model in [('Apple', 'iPhone 12'), ('Apple', 'iPhone 13'), ('Samsung', 'Galaxy S22')]]
        model = DummyRegressor(strategy='median').fit(features(rows, {}), [10000, 12000, 14000])
        artifact = {'model': model, 'feature_version': 2, 'feature_names': FEATURES,
                    'reference_catalog': {}, 'candidate_name': 'fixture',
                    'fitted_brands': ['Apple', 'Samsung'],
                    'fitted_models': [r['brand'] + ':' + r['model'] for r in rows],
                    'fit_date_min': '2024-01-01', 'fit_date_max': '2026-10-06'}
        joblib.dump(artifact, path)
        path.with_name('metadata.json').write_text(json.dumps({'model_hashes': {path.name: sha(path)}}))
        self.dataset = Path(self.temp.name) / 'dataset.csv'
        dataset_rows = [dict(row, price_thb=price) for row, price in zip(rows, [10000, 12000, 14000])]
        dataset_rows[1]['source'] = 'ennxo'
        with self.dataset.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(dataset_rows[0]))
            writer.writeheader()
            writer.writerows(dataset_rows)
        self.env = patch.dict(os.environ, {'PHONE_PRICE_MODEL_PATH': str(path),
                                          'PHONE_PRICE_DATASET_PATH': str(self.dataset)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_submission_preserves_unknowns_and_returns_price(self):
        with patch('script.modeling.predict.predict_rows', wraps=predict_rows) as predict:
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertIsNone(app.number_input(key='battery').value)
            self.assertIsNone(app.number_input(key='warranty').value)
            self.assertIsNone(app.selectbox(key='box').value)
            self.assertNotIn('source', [widget.key for widget in app.selectbox])
            self.assertNotIn('condition', [widget.key for widget in app.selectbox])
            app.session_state['source'] = 'ennxo'
            app.session_state['condition'] = 'new'
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, '12,000 บาท')
            row = predict.call_args.args[1][0]
            self.assertIsNone(row['battery_health_pct'])
            self.assertIsNone(row['warranty_days'])
            self.assertIsNone(row['box_mentioned'])
            self.assertEqual(row['model'], 'iPhone 13')
            self.assertEqual(row['source'], 'mac2hand')
            self.assertEqual(row['condition'], 'used')

    def test_changing_brand_resets_model_and_removes_old_result(self):
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.button[0].click().run()
        self.assertEqual(len(app.metric), 1)
        app.selectbox(key='brand').select('Samsung').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='phone_model').options, ['Galaxy S22'])
        self.assertEqual(app.selectbox(key='phone_model').value, 'Galaxy S22')
        self.assertEqual(len(app.metric), 0)

    def test_explicit_zero_date_and_fixed_defaults_reach_inference(self):
        from datetime import date
        with patch('script.modeling.predict.predict_rows', wraps=predict_rows) as predict:
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            app.number_input(key='battery').set_value(90)
            app.number_input(key='warranty').set_value(0)
            app.selectbox(key='box').select(0)
            app.date_input(key='day').set_value(date(2026, 10, 7))
            app.button[0].click().run()
            self.assertFalse(app.exception)
            row = predict.call_args.args[1][0]
            self.assertEqual(row['battery_health_pct'], 90)
            self.assertEqual(row['warranty_days'], 0)
            self.assertEqual(row['box_mentioned'], 0)
            self.assertEqual(row['source'], 'mac2hand')
            self.assertEqual(row['condition'], 'used')
            self.assertEqual(row['published_at'], '2026-10-07')
            self.assertEqual(len(app.info), 1)

    def test_missing_model_shows_recovery_message(self):
        with patch.dict(os.environ, {'PHONE_PRICE_MODEL_PATH': str(Path(self.temp.name) / 'missing.joblib')}):
            with patch('logging.Logger.exception'):
                app = AppTest.from_file(str(APP), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertIn('ผู้ดูแล', app.error[0].value)
        self.assertEqual(len(app.button), 0)

    def test_launcher_runs_from_another_directory(self):
        result = subprocess.run([sys.executable, str(ROOT / 'script/app/run_app.py'), '--help'],
                                cwd=self.temp.name, capture_output=True, text=True, check=True)
        self.assertIn('--port', result.stdout)

    def test_explorer_filters_and_empty_state_preserve_input(self):
        before = self.dataset.read_bytes()
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.radio(key='navigation').set_value('สำรวจข้อมูล').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '3')
        app.multiselect(key='filter_sources').set_value(['ennxo']).run()
        self.assertEqual(app.metric[0].value, '1')
        self.assertEqual(app.dataframe[0].value.iloc[0]['เว็บ'], 'ENNXO')
        app.text_input(key='filter_query').set_value('ไม่มีรุ่นนี้').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertIn('ไม่พบประกาศ', app.info[0].value)
        self.assertEqual(self.dataset.read_bytes(), before)

    def test_other_pages_work_without_model_binary(self):
        with patch.dict(os.environ, {'PHONE_PRICE_MODEL_PATH': str(Path(self.temp.name) / 'missing.joblib')}):
            with patch('logging.Logger.exception'):
                app = AppTest.from_file(str(APP), default_timeout=20).run()
            app.radio(key='navigation').set_value('สำรวจข้อมูล').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, '3')
            app.radio(key='navigation').set_value('ผลโมเดล').run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 3)
            self.assertIn('ผลย้อนหลัง', app.info[0].value)
            self.assertEqual(set(app.dataframe[0].value['เว็บ']), {'ENNXO', 'Mac2Hand'})
            self.assertTrue(any('ใช้ตัววัดสถิติ' in item.label for item in app.expander))
            rendered = '\n'.join(item.value for item in app.markdown)
            self.assertIn('Median absolute error', rendered)
            self.assertIn('ยังไม่ได้ทำ t-test', rendered)
            self.assertEqual(len(app.get('image')), 5)

    def test_explorer_axes_start_at_zero_for_full_and_filtered_data(self):
        import pandas as pd
        from script.app.dashboard import explorer_charts

        frame = pd.read_csv(self.dataset)
        frame['year'] = pd.to_datetime(frame['published_at']).dt.year
        for selected in [frame, frame[frame['source'] == 'ennxo']]:
            bars, line = (chart.to_dict() for chart in explorer_charts(selected))
            count_scale = bars['encoding']['x']['scale']
            price_scale = line['encoding']['y']['scale']
            for scale in [count_scale, price_scale]:
                self.assertEqual(scale['domain'][0], 0)
                self.assertFalse(scale['nice'])
            self.assertGreater(count_scale['domain'][1], selected['brand'].value_counts().max())
            self.assertGreater(price_scale['domain'][1], selected.groupby('year')['price_thb'].median().max())
            self.assertEqual(bars['encoding']['y']['sort'], '-x')


class DeploymentTests(unittest.TestCase):
    def test_shipped_model_predicts_without_private_outputs_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / 'checkout'
            scripts = checkout / 'script'
            scripts.mkdir(parents=True)
            shutil.copy2(ROOT / 'script/__init__.py', scripts / '__init__.py')
            shutil.copytree(ROOT / 'script/modeling', scripts / 'modeling',
                            ignore=shutil.ignore_patterns('__pycache__'))
            modeldir = checkout / 'models/asking_price_v2'
            modeldir.mkdir(parents=True)
            for name in ['model.joblib', 'metadata.json']:
                shutil.copy2(ROOT / 'models/asking_price_v2' / name, modeldir / name)
            result = subprocess.run(
                [sys.executable, '-B', str(scripts / 'modeling/predict.py'),
                 '--source', 'mac2hand', '--brand', 'Apple', '--model', 'iPhone 13',
                 '--storage-gb', '128', '--condition', 'used', '--published-at', '2026-10-06'],
                cwd=directory, capture_output=True, text=True, check=True, timeout=30,
            )
            prediction = json.loads(result.stdout)[0]
            self.assertTrue(math.isfinite(prediction['predicted_price_thb']))
            self.assertGreater(prediction['predicted_price_thb'], 0)
            self.assertEqual(prediction['model'], 'age_hist_log_half_2')

    def test_deployment_dependencies_match_shipped_artifact(self):
        manifest = (ROOT / 'requirements.txt').read_text().splitlines()
        self.assertIn('-r requirements-lock.txt', manifest)
        locked = dict(line.split('==', 1) for line in (ROOT / 'requirements-lock.txt').read_text().splitlines()
                      if '==' in line and not line.startswith('#'))
        metadata = json.loads((ROOT / 'models/asking_price_v2/metadata.json').read_text())
        for package, expected in metadata['versions'].items():
            self.assertEqual(locked[package], expected, package)
            self.assertEqual(version(package), expected, package)


if __name__ == '__main__':
    unittest.main()
