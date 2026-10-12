"""Public release contracts: documentation, data registry and report provenance."""
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import unittest
import zipfile
from script.artifacts import read_metadata, reference_json, reference_sha

ROOT = Path(__file__).resolve().parents[2]


def read_json(path):
    return reference_json(path)


def digest(path):
    return reference_sha(path)


def anchors(text):
    result = set(re.findall(r'<a id="([^"]+)"', text))
    for heading in re.findall(r'^#+ (.+)$', text, re.MULTILINE):
        cleaned = ''.join(character for character in heading.strip().lower()
                          if character.isalnum() or character in ' -_'
                          or unicodedata.category(character).startswith('M'))
        result.add(re.sub(r'\s', '-', cleaned))
    return result


class ProjectIntegrityTests(unittest.TestCase):
    def test_reader_documents_use_online_website_without_setup_instructions(self):
        readme = (ROOT / 'README.md').read_text()
        self.assertIn('https://secondhand-phone-price-prediction.streamlit.app/', readme)
        paths = [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md')),
                 ROOT / 'docs/assets/eda/report.html', ROOT / 'docs/assets/modeling/report.html']
        for path in paths:
            content = path.read_text()
            if path.suffix == '.md':
                headings = re.findall(r'^#{1,6} (.+)$', content, flags=re.MULTILINE)
                for heading in headings:
                    self.assertNotRegex(heading, r'อะไร|ไหน|อย่างไร|ทำไม|หรือไม่|ไหม|มั้ย')
            for instruction in ['localhost', 'Main file path', 'pip install',
                                'streamlit run', '.venv/bin/python', '```bash']:
                with self.subTest(file=str(path.relative_to(ROOT)), instruction=instruction):
                    self.assertNotIn(instruction, content)

    def assert_local_reference(self, target, base):
        if target.startswith(('http:', 'https:', 'mailto:')):
            return
        name, _, fragment = target.partition('#')
        path = (base / name).resolve()
        self.assertTrue(path.exists(), f'Missing reference: {target} from {base}')
        if fragment and path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                self.assertTrue(fragment in archive.namelist() or any(n.startswith(fragment+'/') for n in archive.namelist()))
        elif fragment and path.suffix == '.json':
            self.assertIn(fragment, read_json(path))
        elif fragment and path.suffix == '.md':
            self.assertIn(fragment, anchors(path.read_text()), f'Missing anchor: {target}')

    def test_documents_and_registry_point_to_existing_files(self):
        documents = [ROOT / 'README.md', *sorted((ROOT / 'docs').rglob('*.md'))]
        for document in documents:
            for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', document.read_text()):
                with self.subTest(document=str(document.relative_to(ROOT)), target=target):
                    self.assert_local_reference(target, document.parent if not target.startswith('#') else document)

        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in ('documentation', 'report') and isinstance(child, str):
                        self.assert_local_reference(child, ROOT)
                    else:
                        visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(read_json(ROOT / 'data/datasets.json'))

    def test_active_dataset_and_model_match_the_registry(self):
        registry = read_json(ROOT / 'data/datasets.json')
        dataset = registry[registry['default_dataset']]
        with (ROOT / dataset['usable_csv']).open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        fields = list(read_json(ROOT / 'data/final/metadata.json#schema')['fields'])
        self.assertEqual(list(rows[0]), fields)
        self.assertEqual(len(rows), dataset['records'])
        self.assertEqual(len({row['listing_id'] for row in rows}), len(rows))
        self.assertEqual(len({row['url'] for row in rows}), len(rows))
        self.assertEqual({source: sum(row['source'] == source for row in rows)
                          for source in dataset['source_counts']}, dataset['source_counts'])
        from script.modeling.split_dataset import read_dataset
        self.assertEqual(read_dataset(ROOT / dataset['usable_csv']), rows)
        with (ROOT / 'data/final/condition_features.csv').open(newline='') as handle:
            sidecar = list(csv.DictReader(handle))
        self.assertEqual(len(sidecar), len(rows))
        self.assertEqual({row['listing_id'] for row in sidecar}, {row['listing_id'] for row in rows})
        run = registry['modeling_run']
        config = read_json(ROOT / run['config'])
        metadata = read_json(ROOT / run['metadata'])
        summary = read_json(ROOT / run['summary'])
        self.assertTrue(run['model_included_in_git'])
        self.assertEqual(run['selected_model'], summary['selected_model'])
        self.assertEqual(metadata['selected_model'], summary['selected_model'])
        for key in ('deployment_fit_rows', 'evaluation_fit_rows'):
            self.assertEqual(run[key], summary[key])
        self.assertEqual(run['retrospective_evaluation_rows'], summary['retrospective_rows'])
        self.assertEqual(digest(ROOT / dataset['usable_csv']), config['core_dataset_sha256'])
        self.assertEqual(metadata['dataset_sha256'], config['core_dataset_sha256'])
        self.assertEqual(digest(ROOT / run['config']), metadata['config_sha256'])
        self.assertEqual(digest(ROOT / config['condition_features']), config['condition_features_sha256'])
        self.assertEqual(digest(ROOT / config['catalog']), config['catalog_sha256'])
        self.assertEqual(digest(ROOT / run['deployment_model']), metadata['model_hashes']['model.joblib'])

    def test_report_files_match_recorded_output_hashes(self):
        for index in sorted((ROOT / 'docs/assets').rglob('metadata.json')):
            hashes = read_json(index).get('hashes', {})
            for name, expected in hashes.items():
                with self.subTest(index=str(index.relative_to(ROOT)), name=name):
                    self.assertEqual(digest(index.parent / name), expected)



if __name__ == '__main__':
    unittest.main()
