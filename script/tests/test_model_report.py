"""The canonical report and portable export contain the actual recorded metrics."""
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[2]




from script.artifacts import has_metadata, read_metadata

class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.headings = 0
        self.tables = 0
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if 'id' in attributes:
            self.ids.add(attributes['id'])
        if tag == 'a':
            self.links.append(attributes.get('href', ''))
        if tag == 'img':
            self.images.append(dict(attrs)['src'])
        elif tag == 'h2':
            self.headings += 1
        elif tag == 'table':
            self.tables += 1


class ModelReportTests(unittest.TestCase):
    def test_learning_curves_have_five_sizes_and_reproduce_full_size_errors(self):
        import csv
        import math
        from script.modeling.model_v2.learning_curve import FRACTIONS, temporal_prefix
        from script.modeling.split_dataset import read_dataset
        report = ROOT / 'docs/assets/modeling'
        config = read_metadata(report, 'config')
        metadata = read_metadata(report, 'learning_curve')
        with (report / 'tables/learning_curve.csv').open() as handle:
            curves = list(csv.DictReader(handle))
        with (report / 'tables/train_validation_errors.csv').open() as handle:
            reference = list(csv.DictReader(handle))
        rows = [row for row in read_dataset(ROOT / config['dataset'], config['dataset_sha256'])
                if row['condition'] in config['training_conditions']]
        self.assertEqual(len(curves), 25)
        self.assertEqual(metadata['fresh_fits'], 25)
        content = (ROOT / 'docs/modeling.md').read_text()
        self.assertIn('### 5.2 Learning curve', content)
        for fold, old in zip(read_metadata(report, 'folds'), reference):
            points = [row for row in curves if int(row['fold']) == fold['fold']]
            self.assertEqual([float(row['requested_fraction']) for row in points], list(FRACTIONS))
            training = [row for row in rows if row['published_at'] < fold['window_start']]
            for point in points:
                prefix = temporal_prefix(training, float(point['requested_fraction']))
                self.assertEqual(int(point['train_rows']), len(prefix))
                self.assertEqual(point['train_max'], prefix[-1]['published_at'])
                self.assertEqual(int(point['validation_rows']), fold['validation_rows'])
                self.assertLess(point['train_max'], fold['window_start'])
                for partition in ['train', 'validation']:
                    for metric in ['mae_thb', 'rmse_thb']:
                        number = float(point[partition + '_' + metric])
                        self.assertTrue(math.isfinite(number) and number >= 0)
            for partition in ['train', 'validation']:
                for metric in ['mae_thb', 'rmse_thb']:
                    key = partition + '_' + metric
                    self.assertAlmostEqual(float(points[-1][key]), float(old[key]), places=6)
        with (report / 'tables/learning_curve_summary.csv').open() as handle:
            summary = list(csv.DictReader(handle))
        self.assertEqual(len(summary), 5)
        section = content.split('### 5.2', 1)[1].split('## 6.', 1)[0]
        self.assertEqual(section.count('!['), 1)
        self.assertNotIn('learning_curve_fold_', section)
        for row in summary:
            points = [point for point in curves if point['requested_fraction'] == row['requested_fraction']]
            self.assertEqual(int(row['folds']), 5)
            for key in ['train_mae_thb', 'validation_mae_thb', 'train_rmse_thb', 'validation_rmse_thb']:
                self.assertAlmostEqual(float(row[key]), sum(float(point[key]) for point in points) / 5)
            self.assertIn(f"{float(row['validation_mae_thb']):,.2f}", section)
        for suffix in ['png', 'svg']:
            self.assertTrue((report / 'figures' / f'learning_curve_summary.{suffix}').exists())

    def test_train_validation_errors_cover_original_folds_and_match_scores(self):
        import csv
        import math
        report = ROOT / 'docs/assets/modeling'
        summary = read_metadata(report, 'summary')
        with (report / 'tables/train_validation_errors.csv').open() as handle:
            errors = list(csv.DictReader(handle))
        with (report / 'tables/fold_metrics.csv').open() as handle:
            recorded = [row for row in csv.DictReader(handle) if row['candidate'] == summary['selected_model']]
        folds = read_metadata(report, 'folds')
        self.assertEqual(len(errors), 5)
        self.assertEqual(len(recorded), 5)
        content = (ROOT / 'docs/modeling.md').read_text()
        self.assertIn('### 5.1 เปรียบเทียบ training กับ validation', content)
        self.assertIn('gap = validation error − training error', content)
        for row, old, fold in zip(errors, recorded, folds):
            self.assertEqual(int(row['fold']), fold['fold'])
            self.assertEqual(int(row['train_rows']), fold['train_rows'])
            self.assertEqual(int(row['validation_rows']), fold['validation_rows'])
            self.assertEqual(row['window_start'], fold['window_start'])
            self.assertEqual(row['window_end'], fold['window_end'])
            for metric in ['mae_thb', 'rmse_thb']:
                train, validation = float(row['train_' + metric]), float(row['validation_' + metric])
                self.assertTrue(math.isfinite(train))
                self.assertGreaterEqual(train, 0)
                self.assertAlmostEqual(validation, float(old[metric]), places=6)
                self.assertAlmostEqual(float(row[metric + '_gap']), validation - train)
                for number in [train, validation, validation - train]:
                    self.assertIn(f'{number:,.2f}', content)
        count = sum(int(row['validation_rows']) for row in errors)
        pooled_mae = sum(int(row['validation_rows']) * float(row['validation_mae_thb']) for row in errors) / count
        self.assertAlmostEqual(pooled_mae, summary['validation']['mae_thb'])

    def test_current_scope_counts_are_consistent_in_report_and_folds(self):
        report = ROOT / 'docs/assets/modeling'
        summary = read_metadata(report, 'summary')
        config = read_metadata(report, 'config')
        folds = read_metadata(report, 'folds')
        content = (ROOT / 'docs/modeling.md').read_text()
        split_section = content.split('## 3.', 1)[1].split('## 4.', 1)[0]
        validation_rows = sum(fold['validation_rows'] for fold in folds)
        self.assertEqual(len(folds), 5)
        self.assertEqual({fold['window_days'] for fold in folds}, {75})
        from datetime import date, timedelta
        for left, right in zip(folds, folds[1:]):
            self.assertEqual(date.fromisoformat(left['window_end']) + timedelta(days=1),
                             date.fromisoformat(right['window_start']))
        for fold in folds:
            self.assertLess(fold['train_max'], fold['window_start'])
            self.assertLessEqual(fold['window_start'], fold['validation_min'])
            self.assertLessEqual(fold['validation_max'], fold['window_end'])
        self.assertLess(folds[-1]['window_end'], config['retrospective_test_start'])
        self.assertIn('75 วันเท่ากัน', split_section)
        self.assertIn(f'**{validation_rows:,} แถว**', split_section)
        self.assertIn(f"**{summary['evaluation_fit_rows']:,} แถวก่อน", split_section)
        self.assertIn(f"**{summary['retrospective_rows']:,} แถววันที่", split_section)
        self.assertEqual(summary['deployment_fit_rows'], config['expected_training_rows'])
        self.assertEqual(summary['training_conditions'], ['used'])

    def test_html_report_links_have_targets_and_website_links_use_github(self):
        from script.report_links import REPOSITORY, website_report_links
        parser = ReportParser()
        parser.feed((ROOT / 'docs/assets/modeling/report.html').read_text())
        self.assertTrue(any(url.startswith('#7-') for url in parser.links))
        for url in parser.links:
            if url.startswith('#'):
                self.assertIn(unquote(url[1:]), parser.ids)
            elif url.startswith(REPOSITORY + '/blob/main/'):
                path = unquote(urlsplit(url).path.split('/blob/main/', 1)[1])
                self.assertTrue((ROOT / path).exists(), path)
        markdown = website_report_links((ROOT / 'docs/modeling.md').read_text())
        self.assertIn(REPOSITORY + '/blob/main/docs/modeling.md#7-', markdown)
        self.assertIn(REPOSITORY + '/blob/main/docs/project.md', markdown)

    def test_platform_groups_account_for_all_evaluation_rows_and_errors(self):
        summary = read_metadata(ROOT / 'docs/assets/modeling', 'summary')
        groups = summary['platform_evaluation']['groups']
        total = sum(group['rows'] for group in groups.values())
        self.assertEqual(total, summary['retrospective_rows'])
        pooled_mae = sum(group['rows'] * group['mae_thb'] for group in groups.values()) / total
        self.assertAlmostEqual(pooled_mae, summary['retrospective']['mae_thb'])
        content = (ROOT / 'docs/modeling.md').read_text()
        for name in ['Android', 'iOS']:
            self.assertIn(name, content)
            self.assertIn(f"{groups[name]['mae_thb']:,.2f}", content)
        self.assertIn('ยังไม่ยืนยัน OS', content)
        self.assertIn('## 7. ผลการประเมินแยก Android และ iOS', content)

    def test_canonical_report_has_metrics_and_portable_graphs(self):
        report = ROOT / 'docs/assets/modeling'
        summary = read_metadata(report, 'summary')
        content = (ROOT / 'docs/modeling.md').read_text()
        for key in ['mae_thb', 'rmse_thb']:
            self.assertIn(f"{summary['retrospective'][key]:,.2f}", content)
        self.assertIn('ไม่มีการทดสอบนัยสำคัญทางสถิติ', content)
        self.assertIn('ไม่ใช่ holdout ใหม่', content)
        self.assertFalse(has_metadata(report, 'summary_text'))
        parser = ReportParser()
        parser.feed((report / 'report.html').read_text())
        self.assertEqual(len(parser.images), 6)
        self.assertTrue(all(src.startswith('data:image/png;base64,') for src in parser.images))
        self.assertGreaterEqual(parser.headings, 9)
        self.assertGreaterEqual(parser.tables, 5)
        # The main comparison keeps one column per model and metric.
        rows = [line for line in content.splitlines() if line.startswith('| MAE (บาท) |')]
        self.assertEqual(rows[0].count('|'), 4)


if __name__ == '__main__':
    unittest.main()
