import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from script.preparation.ennxo.audit_ennxo_raw import inventory
from script.scraper.ennxo.ennxo_html import embedded_products, page_evidence
from script.preparation.ennxo.extract_ennxo_raw import extract


def hydration(text):
    return ''.join('<script>self.__next_f.push(' + json.dumps([1, chunk]) + ')</script>'
                   for chunk in (text[:23], text[23:]))


def product(description='เครื่องใช้เอง'):
    return {'public_id': 123, 'name': 'มือถือ', 'condition': 'used', 'detail': description, 'price': 5000,
            'subfields': {'maker': {'name': 'Samsung', 'slug': 'samsung'}, 'model': {'name': 'อื่นๆ', 'slug': 'others'}, 'capacity': 128},
            'seller_account': {'phone': 'private'}}


class ExtractionTests(unittest.TestCase):
    def test_split_hydration_and_contact_account_not_exported(self):
        result = embedded_products(BeautifulSoup(hydration('1:' + json.dumps(product())), 'html.parser'))
        self.assertEqual(result['123']['data']['detail'], 'เครื่องใช้เอง')
        self.assertNotIn('seller_account', result['123']['data'])

    def test_thai_multibyte_reference_and_unicode_newline_preserved(self):
        text = 'มือถือมือสอง\nมีรอยใช้งาน\u2028ข้อความ'
        flight = 'ab:T' + format(len(text.encode()), 'x') + ',' + text + '2:' + json.dumps(product('$ab'))
        result = embedded_products(BeautifulSoup(hydration(flight), 'html.parser'))
        self.assertEqual(result['123']['data']['detail'], text)
        self.assertEqual(result['123']['description_reference'], '$ab')

    def test_unresolved_reference_and_conflicting_product_fail(self):
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            embedded_products(BeautifulSoup(hydration('1:' + json.dumps(product('$ab'))), 'html.parser'))
        text = '1:' + json.dumps(product()) + '\n2:' + json.dumps(product('อีกข้อความ'))
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            embedded_products(BeautifulSoup(hydration(text), 'html.parser'))
        self.assertEqual(embedded_products(BeautifulSoup('<script>self.__next_f.push(alert("bad"))</script>', 'html.parser')), {})

    def test_extraction_preserves_legacy_missing_and_uses_html_instead_of_old_payload(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            raw = Path(tmp) / 'raw'
            (raw / 'pages').mkdir(parents=True)
            row = {'url': 'https://www.ennxo.com/product/123', 'page': 1, 'brand': None, 'model': 'Samsung', 'name': 'มือถือ', 'price': 5000}
            (raw / 'listings.jsonl').write_text(json.dumps(row) + '\n')
            (raw / 'ennxo_summary.json').write_text(json.dumps({'complete': True, 'raw_records': 1, 'completed_pages': 1}))
            (raw / 'ennxo_public_payload.json').write_text(json.dumps({'123': {'name': 'wrong old value'}}))
            html = '<div class="product-card-top-div"><a href="/product/123"><h2>มือถือ</h2></a><div><div>128GB | Samsung</div></div><div>฿ 5,000</div></div>'
            html += hydration('1:' + json.dumps(product()))
            (raw / 'pages/page_1.html').write_text(html)
            before = inventory(raw)
            result = extract(raw, Path(tmp) / 'out')
            record = json.loads((Path(tmp) / 'out/ennxo_extracted.jsonl').read_text())
            self.assertEqual(record['raw_listing'], row)
            self.assertIsNone(record['raw_listing']['brand'])
            self.assertEqual(record['embedded_product']['subfields']['maker']['name'], 'Samsung')
            self.assertEqual(record['card']['info_text'], '128GB | Samsung')
            self.assertEqual(record['provenance']['page_sha256'], before['pages/page_1.html'])
            self.assertEqual(result['observations']['legacy_brand_missing_but_embedded_maker_available'], 1)
            self.assertEqual(result['old_payload_comparison']['different_urls'], [row['url']])
            self.assertEqual(result['records_excluded'], 0)
            self.assertEqual(inventory(raw), before)

    def test_missing_product_card_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'invalid product URL'):
            page_evidence('<div class="product-card-top-div"><h2>ไม่มี URL</h2></div>')


if __name__ == '__main__':
    unittest.main()
