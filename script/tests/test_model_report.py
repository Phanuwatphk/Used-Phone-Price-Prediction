"""The canonical report and portable export contain the actual recorded metrics."""
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.headings = 0
        self.tables = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.images.append(dict(attrs)['src'])
        elif tag == 'h2':
            self.headings += 1
        elif tag == 'table':
            self.tables += 1


class ModelReportTests(unittest.TestCase):
    def test_canonical_report_has_metrics_and_portable_graphs(self):
        report = ROOT / 'docs/assets/modeling/asking_price_v2'
        summary = json.loads((report / 'summary.json').read_text())
        content = (ROOT / 'docs/modeling.md').read_text()
        for key in ['mae_thb', 'rmse_thb', 'median_absolute_error_thb', 'mape_pct', 'bias_thb']:
            self.assertIn(f"{summary['retrospective'][key]:,.2f}", content)
        self.assertIn('ไม่มี test statistic/p-value', content)
        self.assertIn('ไม่ใช่ holdout ใหม่', content)
        self.assertFalse((report / 'summary.md').exists())
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
