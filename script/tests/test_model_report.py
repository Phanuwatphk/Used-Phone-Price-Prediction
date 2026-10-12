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
        for key in ['mae_thb', 'rmse_thb', 'median_absolute_error_thb', 'mape_pct', 'bias_thb']:
            self.assertIn(f"{summary['retrospective'][key]:,.2f}", content)
        self.assertIn('ไม่มี test statistic/p-value', content)
        self.assertIn('ไม่ใช่ holdout ใหม่', content)
        self.assertFalse(has_metadata(report, 'summary_text'))
        parser = ReportParser()
        parser.feed((report / 'report.html').read_text())
        self.assertEqual(len(parser.images), 5)
        self.assertTrue(all(src.startswith('data:image/png;base64,') for src in parser.images))
        self.assertGreaterEqual(parser.headings, 9)
        self.assertGreaterEqual(parser.tables, 5)
        # Formula cells must not accidentally introduce extra Markdown table columns.
        rows = [line for line in content.splitlines() if line.startswith('| MAE |')]
        self.assertEqual(rows[0].count('|'), 5)


if __name__ == '__main__':
    unittest.main()
