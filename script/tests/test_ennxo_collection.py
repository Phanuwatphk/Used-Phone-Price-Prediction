import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import requests

from script.scraper.ennxo.collect_ennxo import START_URL, collect, compare, following_page, parse_page


def html(key, next_page=None):
    product = {'public_id': key, 'name': 'Samsung A35', 'condition': 'used', 'detail': 'ROM128 RAM8',
               'price': 5000, 'subfields': {'maker': {'name': 'Samsung', 'slug': 'samsung'}, 'capacity': 128}}
    page = f'<div class="product-card-top-div"><a href="/product/{key}"><h2>Samsung A35</h2></a><div><div>128GB | Samsung</div></div><div>฿ 5,000</div></div>'
    page += '<script>self.__next_f.push(' + json.dumps([1, '1:' + json.dumps(product)]) + ')</script>'
    if next_page:
        page += f'<a aria-label="หน้า {next_page}" href="?page={next_page}">next</a>'
    return page


class Session:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def get(self, url, timeout):
        self.requests.append(url)
        result = self.pages[url]
        if isinstance(result, Exception):
            raise result
        class Response:
            headers = {'Content-Type': 'text/html; charset=utf-8'}
            def raise_for_status(self):
                pass
        response = Response()
        response.url, response.content = url, result.encode()
        return response


class CollectionTests(unittest.TestCase):
    def test_card_brand_not_mislabelled_as_model(self):
        rows, products, next_url = parse_page(html(1, 2), START_URL, 1, '2026-10-11T00:00:00+07:00')
        self.assertEqual(rows[0]['brand'], 'Samsung')
        self.assertIsNone(rows[0]['model'])
        self.assertEqual(products['1']['detail'], 'ROM128 RAM8')
        self.assertEqual(next_url, START_URL + '?page=2')

    def test_pagination_stays_in_category_and_moves_one_page(self):
        for link in ('https://example.com/?page=2', '?page=5', '/mobile-device/tablet?page=2'):
            with self.assertRaisesRegex(ValueError, 'pagination'):
                following_page(f'<a href="{link}" aria-label="หน้า 2">next</a>', START_URL, 1)
        self.assertIsNone(following_page(html(1), START_URL, 1))

    def test_url_difference_ignores_scrape_time(self):
        old = [{'url': 'a', 'name': 'phone', 'scraped_at': 'old'}, {'url': 'b'}]
        current = [{'url': 'a', 'name': 'phone', 'scraped_at': 'new'}, {'url': 'c'}]
        result = compare(old, current)
        self.assertEqual(result['new_urls'], ['c'])
        self.assertEqual(result['not_seen_urls'], ['b'])
        self.assertEqual(result['changed_card_values'], 0)

    def test_partial_fetch_resumes_and_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            baseline = root / 'old'
            baseline.mkdir()
            content = json.dumps({'url': 'https://www.ennxo.com/product/1'}) + '\n'
            (baseline / 'listings.jsonl').write_text(content)
            url2 = START_URL + '?page=2'
            partial = collect(root / 'new', baseline, delay=0,
                              session=Session({START_URL: html(1, 2), url2: requests.ConnectionError('failed')}))
            self.assertFalse(partial['complete'])
            self.assertEqual(partial['completed_pages'], 1)
            retry = Session({url2: html(2)})
            complete = collect(root / 'new', baseline, resume=True, delay=0, session=retry)
            self.assertTrue(complete['complete'])
            self.assertEqual(complete['new_unique_urls'], 1)
            self.assertEqual(complete['raw_records'], 2)
            self.assertEqual(retry.requests, [url2])
            self.assertEqual((baseline / 'listings.jsonl').read_text(), content)
            self.assertEqual(len((root / 'new/listings.jsonl').read_text().splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
