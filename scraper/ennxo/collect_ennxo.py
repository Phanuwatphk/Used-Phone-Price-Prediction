"""Collect current public ENNXO mobile pages and compare URLs with a saved snapshot."""
import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if __package__:
    from preparation.ennxo.audit_ennxo_raw import ROOT, DEFAULT_RAW, read_records
    from .ennxo_html import page_evidence
else:
    from preparation.ennxo.audit_ennxo_raw import ROOT, DEFAULT_RAW, read_records
    from ennxo_html import page_evidence

START_URL = 'https://www.ennxo.com/mobile-device/mobile'
TZ = ZoneInfo('Asia/Bangkok')


def now():
    return datetime.now(TZ).isoformat()


def save(path, obj):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def write_rows(path, rows):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(path)


def following_page(html, url, page):
    soup = BeautifulSoup(html, 'html.parser')
    icon = soup.select_one('img[alt="หน้าถัดไป"]')
    link = icon.find_parent('a') if icon else None
    if link is None:
        link = soup.select_one(f'a[aria-label="หน้า {page + 1}"]')
    if link is None or not link.get('href'):
        return None
    candidate = urljoin(url, link['href'])
    parsed = urlparse(candidate)
    query = parse_qs(parsed.query)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.ennxo.com'
            or parsed.path != '/mobile-device/mobile'
            or query != {'page': [str(page + 1)]}):
        raise ValueError('Unexpected pagination: ' + candidate)
    return candidate


def parse_page(html, url, page, scraped_at):
    cards, products = page_evidence(html)
    if not cards:
        raise ValueError('No product cards; inspect saved HTML')
    records = []
    matched = {}
    for key, card in cards.items():
        if key not in products:
            raise ValueError('Missing embedded product: ' + key)
        product = products[key]['data']
        if str(product['public_id']) != key:
            raise ValueError('Product identity mismatch')
        parts = [part.strip() or None for part in card['info_parts']]
        storage = parts[0] if parts else None
        model = parts[1] if len(parts) > 1 else None
        brand = parts[2] if len(parts) > 2 else None
        maker = (product.get('subfields') or {}).get('maker') or {}
        if len(parts) == 2 and model and model.casefold() == str(maker.get('name')).casefold():
            brand, model = model, None
        prices = card['price_texts']
        price = None
        if len(prices) == 1:
            try:
                price = float(prices[0].removeprefix('฿').strip().replace(',', ''))
            except ValueError:
                pass
        records.append({'name': card['name'], 'storage': storage, 'model': model, 'brand': brand,
                        'location': card['location'], 'price': price, 'url': card['url'], 'image_url': card['image_url'],
                        'source': 'ennxo', 'currency': 'THB', 'scraped_at': scraped_at, 'listing_page_url': url,
                        'page': page, 'timezone': TZ.key})
        matched[key] = product
    return records, matched, following_page(html, url, page)


def compare(old_rows, rows):
    old = {r['url']: r for r in old_rows}
    current = {r['url']: r for r in rows}
    new_urls = sorted(set(current) - set(old))
    missing = sorted(set(old) - set(current))
    fields = ('name', 'storage', 'model', 'brand', 'location', 'price', 'image_url')
    changes = [{'url': url, 'changed_fields': [f for f in fields if current[url].get(f) != old[url].get(f)]}
               for url in sorted(set(current) & set(old))]
    changes = [row for row in changes if row['changed_fields']]
    return {'old_unique_urls': len(old), 'current_unique_urls': len(current), 'new_unique_urls': len(new_urls),
            'shared_unique_urls': len(set(old) & set(current)), 'not_seen_in_current_crawl': len(missing),
            'changed_card_values': len(changes), 'new_urls': new_urls, 'not_seen_urls': missing,
            'changes': changes, 'note': 'not seen is not proof of deletion; changed fields may include parser differences'}


def collect(output, baseline=DEFAULT_RAW, resume=False, delay=2, session=None):
    output, baseline = output.resolve(), baseline.resolve()
    if output == baseline or baseline in output.parents or output in baseline.parents:
        raise ValueError('Output must be separate from baseline')
    baseline_path = baseline / 'listings.jsonl'
    baseline_hash = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    old_rows = read_records(baseline_path)
    if resume:
        state = json.loads((output / 'collection_progress.json').read_text())
        if state['baseline_sha256'] != baseline_hash or state['baseline'] != str(baseline):
            raise ValueError('Resume baseline differs')
    else:
        output.mkdir(parents=True, exist_ok=False)
        (output / 'pages').mkdir()
        state = {'started_at': now(), 'completed_pages': 0, 'next_url': START_URL,
                 'baseline': str(baseline), 'baseline_sha256': baseline_hash, 'status': 'collecting'}
    rows, products = [], {}
    for page in range(1, state['completed_pages'] + 1):
        journal = json.loads((output / 'pages' / f'page_{page}.json').read_text())
        path = output / 'pages' / f'page_{page}.html'
        if hashlib.sha256(path.read_bytes()).hexdigest() != journal['html_sha256']:
            raise ValueError('Saved page changed before resume')
        rows.extend(journal['records'])
        products.update(journal['products'])
    owned = session is None
    if owned:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        session.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=2,
             status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'], respect_retry_after_header=True)))
    state['status'] = 'collecting' if state['next_url'] else 'complete'
    failure = None
    try:
        while state['next_url']:
            page, url = state['completed_pages'] + 1, state['next_url']
            state.update({'updated_at': now(), 'requesting_url': url})
            save(output / 'collection_progress.json', state)
            if page > 1:
                time.sleep(delay)
            response = session.get(url, timeout=30)
            response.raise_for_status()
            if response.url != url or 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Unexpected redirect or non-HTML response')
            html_path = output / 'pages' / f'page_{page}.html'
            html_path.write_bytes(response.content)
            scraped = now()
            page_rows, page_products, next_url = parse_page(html_path.read_text(encoding='utf-8'), url, page, scraped)
            seen = {r['url'] for r in rows}
            if seen and {r['url'] for r in page_rows} <= seen:
                raise ValueError('Page repeats previously seen URLs; stopped to inspect pagination')
            journal = {'requested_url': url, 'scraped_at': scraped,
                       'html_sha256': hashlib.sha256(response.content).hexdigest(),
                       'records': page_rows, 'products': page_products, 'next_url': next_url}
            save(output / 'pages' / f'page_{page}.json', journal)
            rows.extend(page_rows)
            products.update(page_products)
            state.update({'completed_pages': page, 'next_url': next_url, 'updated_at': now(),
                          'raw_records': len(rows), 'unique_product_urls': len({r['url'] for r in rows}),
                          'new_unique_urls': len({r['url'] for r in rows} - {r['url'] for r in old_rows})})
            write_rows(output / 'listings.jsonl', rows)
            save(output / 'ennxo_public_payload.json', products)
            save(output / 'collection_progress.json', state)
            message = f'Page {page}: {len(page_rows)} cards | unique {state["unique_product_urls"]} | new vs baseline {state["new_unique_urls"]}'
            print(message, flush=True)
            with (output / 'collection.log').open('a', encoding='utf-8') as log:
                log.write(now() + ' ' + message + '\n')
    except (requests.RequestException, ValueError, KeyboardInterrupt) as error:
        failure = str(error) or type(error).__name__
        state['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        print('Stopped; completed pages preserved: ' + failure, flush=True)
    finally:
        if owned:
            session.close()
        state.update({'updated_at': now(), 'status': state['status'] if failure else 'complete', 'error': failure})
        save(output / 'collection_progress.json', state)
        write_rows(output / 'listings.jsonl', rows)
        comparison = compare(old_rows, rows)
        save(output / 'comparison.json', comparison)
        write_rows(output / 'new_listings.jsonl', [r for r in rows if r['url'] in set(comparison['new_urls'])])
        summary = {'source': 'ennxo', 'started_at': state['started_at'], 'finished_at': now(), 'timezone': TZ.key,
                   'completed_pages': state['completed_pages'], 'raw_records': len(rows),
                   'unique_product_urls': comparison['current_unique_urls'], 'complete': failure is None and state['next_url'] is None,
                   'stop_reason': failure or 'no_next_page_link', 'new_unique_urls': comparison['new_unique_urls'],
                   'baseline_sha256': baseline_hash, 'duplicate_url_occurrences': len(rows) - comparison['current_unique_urls']}
        save(output / 'ennxo_summary.json', summary)
        save(output / 'run_metadata.json', {'python_script': str(Path(__file__).resolve()),
             'code_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (Path(__file__), Path(__file__).with_name('ennxo_html.py'),
                                          ROOT / 'preparation/ennxo/audit_ennxo_raw.py')},
             'baseline': str(baseline), 'baseline_sha256': baseline_hash, 'delay_seconds': delay})
        if hashlib.sha256(baseline_path.read_bytes()).hexdigest() != baseline_hash:
            raise ValueError('Baseline changed during collection')
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        print('Output: ' + str(output), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--baseline', type=Path, default=DEFAULT_RAW)
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    if args.output and args.resume:
        parser.error('Choose --output or --resume')
    output = args.resume or args.output or ROOT / 'data/raw' / datetime.now(TZ).strftime('ennxo_%Y%m%dT%H%M%S_%f_Asia-Bangkok')
    result = collect(output, args.baseline, resume=bool(args.resume))
    raise SystemExit(0 if result['complete'] else 1)
