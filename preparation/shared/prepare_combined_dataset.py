"""Audit accepted source CSVs, align their schema, and merge with row-level lineage."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import statistics
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / 'data/datasets.json'
DEFAULT_SCHEMA = ROOT / 'config/shared/dataset_schema.json'
DEFAULT_OUTPUT = ROOT / 'data/intermediate/combined/ennxo_20261005_mac2hand_20261006/before_selection'
CORE = ('product_id', 'url', 'brand', 'model', 'storage_gb', 'condition', 'price_thb', 'published_at')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def display(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def standard_model(brand, model, schema):
    model = ' '.join(model.split())
    aliases = schema['model_aliases'].get(brand, {})
    model = next((v for k, v in aliases.items() if k.casefold() == model.casefold()), model)
    if brand == 'Samsung' and schema['samsung_fold_flip_spacing']:
        model = re.sub(r'^Galaxy\s+Z\s+(Fold|Flip)\s*(\d+)\b',
                       lambda m: f'Galaxy Z {m[1].capitalize()} {m[2]}', model, flags=re.I)
    if brand in schema['remove_redundant_brand_prefix']:
        model = re.sub(r'^' + re.escape(brand) + r'\s+', '', model, flags=re.I)
    return model


def standard_date(value, timezone):
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return date.fromisoformat(value).isoformat(), 'day'
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Timestamp has no timezone')
    return timestamp.astimezone(ZoneInfo(timezone)).date().isoformat(), 'timestamp'


def normalize(row, source, snapshot, schema):
    missing = [key for key in CORE if not str(row.get(key) or '').strip()]
    if missing:
        raise ValueError('Missing required fields: ' + ', '.join(missing))
    domain = urlparse(row['url']).hostname
    expected = {'ennxo': ('ennxo.com', 'www.ennxo.com'), 'mac2hand': ('mac2hand.com', 'www.mac2hand.com')}
    if domain not in expected[source] or urlparse(row['url']).scheme != 'https':
        raise ValueError('Source URL/domain mismatch')
    identifier = str(row['product_id']).strip()
    pattern = r'/product/(\d+)(?:/|$)' if source == 'ennxo' else r'/detail/(\d+)(?:/|$)'
    match = re.match(pattern, urlparse(row['url']).path)
    if not match or match[1] != identifier:
        raise ValueError('Product ID/URL mismatch')
    if row.get('source', '').strip() not in ('', source):
        raise ValueError('Existing source contradicts registered source')
    if row.get('status', 'accepted') != 'accepted' or row.get('disposition', 'accepted') != 'accepted':
        raise ValueError('Input includes a non-accepted row')
    if row.get('hold_reasons') or row.get('exclusion_reasons'):
        raise ValueError('Accepted input still has unresolved reasons')
    try:
        storage = Decimal(row['storage_gb'])
        price = Decimal(row['price_thb'])
        if not storage.is_finite() or storage <= 0 or storage != storage.to_integral_value():
            raise ValueError('Storage must be a positive integer in GB')
        if not price.is_finite() or price <= 0 or price != price.quantize(Decimal('0.01')):
            raise ValueError('Price must be positive THB with at most two decimal places')
    except InvalidOperation as error:
        raise ValueError('Invalid numeric field') from error
    if row['condition'] not in schema['conditions']:
        raise ValueError('Invalid seller condition')
    published, precision = standard_date(row['published_at'], schema['publication_timezone'])
    snapshot_day = re.search(r'_(\d{8})T', snapshot)
    if snapshot_day and published > datetime.strptime(snapshot_day[1], '%Y%m%d').date().isoformat():
        raise ValueError('Publication is after snapshot date')
    brand = row['brand'].strip()
    result = {'listing_id': f'{source}:{identifier}', 'source': source, 'source_snapshot': snapshot,
              'product_id': identifier, 'url': row['url'], 'brand': brand,
              'model': standard_model(brand, row['model'], schema), 'storage_gb': int(storage),
              'condition': row['condition'], 'price_thb': float(price), 'published_at': published,
              'published_at_raw': row['published_at'], 'published_at_precision': precision}
    return result


def profile(source, original, rows):
    prices = sorted(r['price_thb'] for r in rows)
    quantiles = statistics.quantiles(prices, n=4, method='inclusive') if len(prices) > 1 else prices * 3
    counts = lambda key: dict(sorted(Counter(r[key] for r in rows).items()))
    return {'source': source, 'records': len(rows),
            'missing_before_normalization': {k: sum(not r.get(k) for r in original) for k in ('source',) + CORE},
            'source_filled_from_registry_and_verified_url': sum(not r.get('source') for r in original),
            'brand_counts': counts('brand'), 'model_counts': counts('model'),
            'condition_counts': counts('condition'), 'storage_gb_counts': counts('storage_gb'),
            'publication_year_counts': dict(sorted(Counter(r['published_at'][:4] for r in rows).items())),
            'date_min': min(r['published_at'] for r in rows), 'date_max': max(r['published_at'] for r in rows),
            'price_thb': {'min': prices[0], 'q1': quantiles[0], 'median': statistics.median(prices),
                          'q3': quantiles[2], 'max': prices[-1]},
            'largest_prices_for_later_review': [{'listing_id': r['listing_id'], 'model': r['model'],
                'storage_gb': r['storage_gb'], 'price_thb': r['price_thb'], 'url': r['url']}
                for r in sorted(rows, key=lambda r: r['price_thb'], reverse=True)[:5]],
            'model_normalized_records': sum(a['model'] != b['model'] for a, b in zip(original, rows)),
            'date_precision_counts': counts('published_at_precision')}


def prepare(registry_path, schema_path, output, audit_output=None):
    registry_path, schema_path, output = registry_path.resolve(), schema_path.resolve(), output.resolve()
    audit_output = audit_output.resolve() if audit_output is not None else output
    if audit_output != output and (audit_output in output.parents or output in audit_output.parents):
        raise ValueError('Final and audit outputs overlap')
    registry = json.loads(registry_path.read_text()); schema = json.loads(schema_path.read_text())
    if schema['version'] != 1 or set(registry['datasets']) != set(schema['sources']):
        raise ValueError('Unsupported schema or sources')
    inputs = {source: (ROOT / info['usable_csv']).resolve() for source, info in registry['datasets'].items()}
    for protected in [registry_path, schema_path, ROOT / 'data/raw', ROOT / 'config', *inputs.values()]:
        if any(destination == protected or protected in destination.parents or destination in protected.parents
               for destination in (output, audit_output)):
            raise ValueError('Output overlaps a protected input')
    initial = {str(p): sha(p) for p in [registry_path, schema_path, *inputs.values()]}
    results, lineage, audits, changes = [], [], {}, []
    for source in schema['sources']:
        with inputs[source].open(encoding='utf-8-sig', newline='') as file:
            originals = list(csv.DictReader(file))
        info = registry['datasets'][source]
        if not originals or len(originals) != info['usable_records']:
            raise ValueError(f'{source}: count differs from registered accepted count')
        rows = []
        for number, original in enumerate(originals, 1):
            try:
                row = normalize(original, source, info['snapshot'], schema)
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f'{source} input row {number}: {error}') from error
            modified = {key: {'before': original.get(key), 'after': row[key]} for key in ('source', 'brand', 'model', 'storage_gb', 'price_thb', 'published_at')
                        if str(original.get(key, '')) != str(row[key])}
            if modified:
                changes.append({'listing_id': row['listing_id'], 'changes': modified})
            lineage.append({'listing_id': row['listing_id'], 'input_csv': display(inputs[source]),
                'input_sha256': initial[str(inputs[source])], 'input_record_number': number,
                'original_csv_row': original, 'normalization_changes': modified})
            rows.append(row)
        if len({r['product_id'] for r in rows}) != len(rows) or len({r['url'] for r in rows}) != len(rows):
            raise ValueError(f'{source}: duplicate product identities in accepted input')
        audits[source] = profile(source, originals, rows)
        results.extend(rows)
    if initial != {str(p): sha(p) for p in [registry_path, schema_path, *inputs.values()]}:
        raise ValueError('Inputs changed during merge')
    if len({r['listing_id'] for r in results}) != len(results):
        raise ValueError('Combined listing identity collision')
    output.mkdir(parents=True, exist_ok=True)
    audit_output.mkdir(parents=True, exist_ok=True)
    with (output / 'dataset.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(schema['fields'])); writer.writeheader(); writer.writerows(results)
    for name, rows in [('dataset.jsonl', results), ('lineage.jsonl', lineage)]:
        destination = audit_output if name == 'lineage.jsonl' else output
        with (destination / name).open('w', encoding='utf-8') as file:
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    dump(audit_output / 'normalization_changes.json', changes)
    for source, audit in audits.items():
        dump(audit_output / f'{source}_audit.json', audit)
    price_review = [{**row, 'source': source,
                     'reason': 'หนึ่งใน 5 ราคาสูงสุดของเว็บ; ยังไม่ยืนยันว่าผิด',
                     'next_action': 'เทียบราคาขายเต็มกับรายละเอียด รุ่น ความจุ และวันประกาศ; ไม่เดาราคาทดแทน'}
                    for source, audit in audits.items() for row in audit['largest_prices_for_later_review']]
    with (audit_output / 'price_review.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['listing_id', 'source', 'model', 'storage_gb', 'price_thb', 'url', 'reason', 'next_action'])
        writer.writeheader(); writer.writerows(price_review)
    summary = {'records': len(results), 'source_counts': dict(Counter(r['source'] for r in results)),
        'source_percentages': {s: round(a['records'] / len(results) * 100, 2) for s, a in audits.items()},
        'brand_counts': dict(Counter(r['brand'] for r in results)),
        'condition_counts': dict(Counter(r['condition'] for r in results)),
        'model_name_changes': sum(a['model_normalized_records'] for a in audits.values()),
        'dates_converted_from_timestamp': sum(r['published_at_precision'] == 'timestamp' for r in results),
        'price_review_records': len(price_review),
        'all_dates_retained': True, 'deduplicated': False, 'outliers_removed': False,
        'missing_values_imputed': False, 'train_test_split': False,
        'stage': 'source_audit_schema_alignment_merge'}
    dump(output / 'summary.json', summary); dump(output / 'schema.json', schema)
    dump(output / 'validation.json', {'records_match_sum_of_inputs': len(results) == sum(a['records'] for a in audits.values()),
        'sources_present_and_verified': all(r['source'] in schema['sources'] for r in results),
        'listing_ids_unique': True, 'required_fields_present': all(all(r.get(k) is not None and r.get(k) != '' for k in schema['fields']) for r in results),
        'inputs_unchanged': True, 'lineage_for_every_record': len(lineage) == len(results)})
    dump(output / 'run_metadata.json', {'generated_at': datetime.now(ZoneInfo(schema['publication_timezone'])).isoformat(),
        'script_sha256': sha(Path(__file__)), 'schema_sha256': initial[str(schema_path)],
        'registry_at_run': registry, 'input_hashes': {display(p): initial[str(p)] for p in inputs.values()},
        'output_directories': {'final': display(output), 'audit': display(audit_output)},
        'dataset_sha256': sha(output / 'dataset.csv')})
    report = ['# ตรวจชุด clean และรวม dataset', '', f"รวมเฉพาะ accepted **{len(results):,} แถว** ทุกแถวมี source และ listing_id", '',
        '| เว็บ | แถว | สัดส่วน | วันที่ (Asia/Bangkok) | ราคาต่ำสุด–สูงสุด (บาท) |', '|---|---:|---:|---|---:|']
    for source, audit in audits.items():
        report.append(f"| {source} | {audit['records']:,} | {summary['source_percentages'][source]}% | {audit['date_min']} ถึง {audit['date_max']} | {audit['price_thb']['min']:,.0f}–{audit['price_thb']['max']:,.0f} |")
    report += ['', 'คอลัมน์หลักครบ ไม่มีค่าขาด ไม่พบ product_id/URL ซ้ำภายในแต่ละเว็บ source เดิมมีครบและตรวจเทียบ URL แล้ว',
        f"ปรับชื่อรุ่น {summary['model_name_changes']:,} แถว และแปลง timestamp {summary['dates_converted_from_timestamp']:,} แถวเป็นวันไทย เก็บวัน/เวลาเดิมและความละเอียดไว้",
        'ข้อมูลต่างเว็บมีสัดส่วนยี่ห้อและช่วงเวลาต่างกัน ต้องตรวจผลกระทบต่อโมเดลใน EDA ร่วม ราคาสูงสุดเป็นรายการสำหรับตรวจต่อ ไม่ลบเพียงเพราะสูง',
        'ยังไม่ตรวจซ้ำข้ามเว็บ ไม่ลบ candidate ที่เหมือนกัน ไม่ทำ EDA ร่วมเต็มรูปแบบหรือแบ่ง train/test', '',
        'dataset/schema/summary/validation/metadata อยู่ปลายทาง --output; lineage/audit/normalization_changes/price_review อยู่ปลายทาง --audit-output เมื่อแยกขั้น',
        '`dataset.csv` และ `dataset.jsonl` คือชุดรวม `lineage.jsonl` เก็บค่าก่อนแปลงทุกแถวและฟิลด์เฉพาะเว็บ',
        '`ennxo_audit.json`, `mac2hand_audit.json` เก็บค่าขาด รุ่น ราคา วันที่และสัดส่วนแยกเว็บ',
        '`price_review.csv` เก็บ 5 ราคาสูงสุดต่อเว็บสำหรับตรวจตามบริบท ไม่ใช่รายการที่ยืนยันว่าผิด',
        '`normalization_changes.json` เก็บค่าก่อน/หลังที่เปลี่ยน `schema.json` ระบุคอลัมน์และชนิดข้อมูล',
        '`summary.json`, `validation.json`, `run_metadata.json` เก็บจำนวน ผลตรวจ และ hash สำหรับทำซ้ำ']
    (output / 'report.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument('--schema', type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument('--audit-output', type=Path, help='Audit directory; default separates current snapshot, custom --output retains legacy bundle')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    audit_output = args.audit_output
    if audit_output is None and args.output.resolve() == DEFAULT_OUTPUT.resolve():
        audit_output = ROOT / 'data/intermediate/combined/ennxo_20261005_mac2hand_20261006/audit'
    prepare(args.registry, args.schema, args.output, audit_output)
