"""Audit saved ENNXO inputs without correcting, filtering, or calling the site."""
import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW = ROOT / 'data/raw/ennxo_20261005T231833_239519_Asia-Bangkok'
FIELDS = ('name', 'storage', 'model', 'brand', 'location', 'price', 'url', 'image_url',
          'source', 'currency', 'scraped_at', 'listing_page_url', 'page', 'timezone')


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


from script.artifacts import write_metadata

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def inventory(raw):
    return {str(p.relative_to(raw)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raw.rglob('*')) if p.is_file()}


def read_records(path):
    def reject_constant(value):
        raise ValueError('Nonstandard JSON number: ' + value)

    rows = []
    with path.open(encoding='utf-8') as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                raise ValueError(f'Blank record at line {line_number}')
            try:
                row = json.loads(line, parse_constant=reject_constant)
            except ValueError as error:
                raise ValueError(f'Invalid JSON at line {line_number}: {error}') from error
            if not isinstance(row, dict):
                raise ValueError(f'Expected an object at line {line_number}')
            rows.append(row)
    return rows


def missing(value):
    return value is None or isinstance(value, str) and not value.strip()


def profile_records(rows):
    fields = []
    issues = []
    brands = {r['brand'].strip().casefold() for r in rows if isinstance(r.get('brand'), str) and r['brand'].strip()}
    for field in sorted(set(FIELDS) | {key for row in rows for key in row}):
        present = [r[field] for r in rows if field in r]
        values = [json.dumps(v, ensure_ascii=False, sort_keys=True) for v in present if not missing(v)]
        fields.append({'field': field, 'absent': len(rows) - len(present),
                       'null': sum(v is None for v in present),
                       'blank': sum(isinstance(v, str) and not v.strip() for v in present),
                       'missing_total': len(rows) - len(present) + sum(missing(v) for v in present),
                       'distinct_nonmissing': len(set(values)), 'types': dict(sorted(Counter(type(v).__name__ for v in present).items()))})
    for number, row in enumerate(rows, 1):
        codes = ['missing_' + f for f in FIELDS if missing(row.get(f))]
        price = row.get('price')
        if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price <= 0:
            codes.append('invalid_nonpositive_price')
        model = row.get('model')
        if isinstance(model, str) and model.strip().casefold() in brands:
            codes.append('model_contains_only_brand')
        url = row.get('url')
        if not isinstance(url, str) or urlparse(url).hostname != 'www.ennxo.com' or not urlparse(url).path.removeprefix('/product/').isdigit() or not urlparse(url).path.startswith('/product/'):
            codes.append('invalid_product_url')
        if row.get('source') != 'ennxo':
            codes.append('unexpected_source')
        if row.get('currency') != 'THB':
            codes.append('unexpected_currency')
        if codes:
            issues.append({'line': number, 'url': url, 'issues': sorted(codes)})
    prices = sorted(r['price'] for r in rows if isinstance(r.get('price'), (int, float)) and not isinstance(r['price'], bool) and math.isfinite(r['price']))
    groups = defaultdict(list)
    titles = defaultdict(list)
    for number, row in enumerate(rows, 1):
        if isinstance(row.get('url'), str):
            groups[row['url']].append(number)
        if isinstance(row.get('name'), str):
            titles[row['name']].append(number)
    return {'records': len(rows), 'unique_urls': len(groups), 'fields': fields,
            'prices': {'count': len(prices), 'min': min(prices) if prices else None,
                       'median': statistics.median(prices) if prices else None, 'max': max(prices) if prices else None,
                       'lowest_values': prices[:5], 'highest_values': prices[-5:]},
            'issues': issues, 'issue_counts': dict(sorted(Counter(code for item in issues for code in item['issues']).items())),
            'duplicate_urls': [{'url': url, 'lines': lines} for url, lines in sorted(groups.items()) if len(lines) > 1],
            'repeated_titles': [{'name': title, 'lines': lines} for title, lines in sorted(titles.items()) if len(lines) > 1],
            'brands': dict(sorted(Counter(r.get('brand') or '(missing)' for r in rows).items()))}


def audit(raw, output):
    raw, output = raw.resolve(), output.resolve()
    if output == raw or raw in output.parents or output in raw.parents:
        raise ValueError('Output must be separate from the raw directory')
    hashes = inventory(raw)
    rows = read_records(raw / 'listings.jsonl')
    summary = json.loads((raw / 'ennxo_summary.json').read_text(encoding='utf-8'))
    profile = profile_records(rows)
    failures = []
    pages = []
    for path in sorted((raw / 'pages').glob('page_*.html'), key=lambda p: int(p.stem.split('_')[-1])):
        page = int(path.stem.split('_')[-1])
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        cards = soup.select('div.product-card-top-div')
        links = [card.select_one("a[href^='/product/']") for card in cards]
        html_urls = [urljoin('https://www.ennxo.com', link['href']) for link in links if link is not None]
        raw_urls = [r.get('url') for r in rows if r.get('page') == page]
        match = Counter(html_urls) == Counter(raw_urls) and all(link is not None for link in links)
        pages.append({'page': page, 'html': str(path.relative_to(raw)), 'html_cards': len(cards),
                      'json_records': len(raw_urls), 'urls_match': match})
        if not match:
            failures.append(f'HTML/listings URL mismatch on page {page}')
    if len(pages) != summary.get('completed_pages'):
        failures.append('HTML page count differs from collection summary')
    if len(rows) != summary.get('raw_records') or profile['unique_urls'] != summary.get('unique_product_urls'):
        failures.append('Record/URL count differs from collection summary')
    if sum(page['json_records'] for page in pages) != len(rows):
        failures.append('Some JSON records do not map to a saved page')
    if summary.get('complete') is not True:
        failures.append('Collection summary does not declare complete')
    if profile['duplicate_urls']:
        failures.append('Duplicate product URLs in listings.jsonl')
    if inventory(raw) != hashes:
        raise ValueError('Raw files changed during audit; rerun from a stable snapshot')
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    profile.update(audit_version=1, snapshot=raw.name, raw_fingerprint=fingerprint,
                   saved_page_count=len(pages), saved_product_html_count=len(list((raw / 'details').glob('*.html'))),
                   collection_summary=summary, accounting={'passed': not failures, 'failures': failures},
                   records_changed=0, records_excluded=0,
                   limitations=['Accounting validates saved-page coverage, not every listing on the live website.',
                                'Card JSON was parsed by an earlier collector; missing values may be parser artifacts.',
                                'No description, condition, variant, capacity, price correctness, or train/test review was performed.'])
    output.mkdir(parents=True, exist_ok=True)
    dump(output / 'raw_checksums.json', hashes)
    dump(output / 'profile.json', profile)
    dump(output / 'page_accounting.json', pages)
    with (output / 'field_profile.csv').open('w', encoding='utf-8-sig', newline='') as file:
        fields = ['field', 'absent', 'null', 'blank', 'missing_total', 'distinct_nonmissing', 'types']
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for item in profile['fields']:
            writer.writerow({**item, 'types': json.dumps(item['types'], sort_keys=True)})
    with (output / 'issues.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['line', 'url', 'issues'])
        writer.writeheader()
        for item in profile['issues']:
            writer.writerow({**item, 'issues': json.dumps(item['issues'])})
    script = Path(__file__).resolve()
    write_metadata(output, 'provenance', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
         'python': platform.python_version(), 'beautifulsoup4': version('beautifulsoup4'), 'soupsieve': version('soupsieve'),
         'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(), 'raw_fingerprint': fingerprint,
         'command': f'python -B script/preparation/ennxo/audit_ennxo_raw.py --raw data/raw/{raw.name} --output <output-directory>'})
    missing_by_field = {f['field']: f['missing_total'] for f in profile['fields']}
    price_range = f'{profile["prices"]["min"]:,.0f}–{profile["prices"]["max"]:,.0f}' if profile['prices']['count'] else 'ไม่มีราคาตัวเลข'
    lines = ['# ENNXO — ผลตรวจข้อมูลดิบ ขั้นที่ 1', '',
             f'รอบ `{raw.name}` ตรวจข้อมูลที่เก็บไว้ในเครื่องโดยไม่เรียกเว็บ ไม่แก้ค่า และไม่คัดประกาศออก', '',
             '| ตรวจอะไร | ผล |', '|---|---:|', f'| ประกาศ | {len(rows):,} |',
             f'| URL ไม่ซ้ำ | {profile["unique_urls"]:,} |', f'| หน้ารวม HTML | {len(pages)} |',
             f'| URL ใน HTML ตรงกับ JSON ทุกหน้า | {"ผ่าน" if not failures else "ไม่ผ่าน — ดู profile.json"} |',
             f'| ช่องยี่ห้อขาด | {missing_by_field["brand"]} |', f'| ช่องรุ่นขาด | {missing_by_field["model"]} |',
             f'| ช่องรุ่นมีเพียงชื่อยี่ห้อ | {profile["issue_counts"].get("model_contains_only_brand", 0)} |',
             f'| ราคาต่ำสุด–สูงสุด (บาท) | {price_range} |',
             f'| ชื่อประกาศตรงกันหลาย URL (กลุ่ม) | {len(profile["repeated_titles"])} |', '',
             'ข้อมูลที่ขาดเป็นค่าที่พบใน JSON ของ parser เดิม ยังไม่พิสูจน์ว่าเว็บไม่มีข้อมูล ต้องอ่าน HTML และตรวจ parser ก่อนเติมค่า ชื่อซ้ำไม่พิสูจน์ว่าเป็นเครื่องเดียวกัน และราคาปลายช่วงไม่ถูกตัดออกโดยอัตโนมัติ', '',
             'บัญชีประกาศที่ตรวจผ่านยืนยันเฉพาะความตรงกันของ URL/จำนวนใน snapshot ไม่ใช่การตรวจความถูกต้องของสเปคหรือข้อความผู้ขาย', '',
             '## ไฟล์ผลการตรวจสอบ', '',
             '- `profile.json`: ผลตรวจทั้งหมดพร้อมข้อจำกัดและ fingerprint',
             '- `field_profile.csv`: ค่าขาด ชนิดข้อมูล และจำนวนค่าที่ต่างกันทุกฟิลด์',
             '- `issues.csv`: แถวที่มีข้อสังเกต ไม่ใช่รายการตัดออก',
             '- `page_accounting.json`: เปรียบเทียบ HTML กับ JSON ทีละหน้า',
             '- `raw_checksums.json`: SHA-256 ของไฟล์ต้นทางทุกไฟล์',
             '- `metadata.json#provenance`: เวลา สภาพแวดล้อม และเวอร์ชันโค้ดที่ใช้', '',
             'ขั้นต่อไป: ถอดข้อความและช่องสินค้าใหม่จาก HTML พร้อมที่มาของค่า ก่อนกำหนดกฎ clean และตรวจความขัดแย้ง', '']
    write_metadata(output, 'report_text', '\n'.join(lines))
    print(json.dumps({'records': len(rows), 'accounting': profile['accounting'],
                      'issue_counts': profile['issue_counts'], 'output': str(output)}, ensure_ascii=False, indent=2))
    if failures:
        raise ValueError('Raw accounting failed; see profile.json')
    return profile


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / 'data/intermediate/ennxo' / args.raw.name / 'raw_audit'
    audit(args.raw, output)
