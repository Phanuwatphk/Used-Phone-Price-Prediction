"""Clean extracted Mac2Hand data using explicit, versioned rules; no network or imputation."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if __package__:
    from scraper.mac2hand.mac2hand import read_jsonl
    from .prepare_mac2hand import ROOT, DEFAULT_RAW, dump, sha, protect, checksums
else:
    from scraper.mac2hand.mac2hand import read_jsonl
    from prepare_mac2hand import ROOT, DEFAULT_RAW, dump, sha, protect, checksums

DEFAULT_RULES = ROOT / 'config/mac2hand/cleaning_rules.json'


def normalized(text):
    text = unicodedata.normalize('NFKC', str(text or '')).casefold()
    for a, b in [('ไอโฟน', 'iphone'), ('i phone', 'iphone'), ('โปรแม็กซ์', 'pro max'),
                 ('โปรแมกซ์', 'pro max'), ('โปร', 'pro'), ('พลัส', 'plus'), ('มินิ', 'mini')]:
        text = text.replace(a, b)
    text = re.sub(r'(\d{1,2}s?)\s*\+', r'\1 plus', text)
    return re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)


def models(text):
    text = normalized(text)
    pattern = r'iphone\s*(air|se(?:\s*\(?(20(?:16|20|22)|[123])(?!\d)\)?)?|xs\s*max|xs|xr|x|\d{1,2}(?:\s*(?:s\s*plus|pro\s*max|pm|pro|plus|mini|gs|[gces]))?)(?=$|[^a-z0-9]|\d{1,4}\s*(?:gb|g|tb)(?![a-z]))'
    result = []
    for match in re.finditer(pattern, text):
        token = re.sub(r'\s+', '', match[1]).replace('(', '').replace(')', '')
        tail = text[match.end():]
        if token[-1].isdigit() and (tail[:1].isdigit() or re.match(r'\s*(?:gb|g|tb)(?![a-z])', tail)):
            continue  # A capacity after iPhone is not a model number.
        if token.startswith('se'):
            generation = {'se2016': '1', 'se2020': '2', 'se2022': '3'}.get(token, token[2:])
            label = 'iPhone SE' + (f' {generation}' if generation else '')
        elif token in ('air', 'x', 'xr', 'xs', 'xsmax'):
            label = {'air': 'iPhone Air', 'x': 'iPhone X', 'xr': 'iPhone XR',
                     'xs': 'iPhone XS', 'xsmax': 'iPhone XS Max'}[token]
        else:
            number = re.match(r'\d+', token)[0]
            suffix = token[len(number):]
            label = 'iPhone ' + number + {'promax': ' Pro Max', 'pm': ' Pro Max', 'pro': ' Pro', 'plus': ' Plus',
                    'mini': ' mini', 'splus': 's Plus', 'gs': 'GS', 'g': 'G', 's': 's', 'c': 'c', 'e': 'e', '': ''}[suffix]
        result.append({'value': label, 'text': match[0], 'offset_normalized': match.start()})
    return result


def storage_claims(text, allowed):
    text = normalized(text)
    result = []
    pattern = r'(?<!\d)(\d{1,4})\s*(gb|g|tb|กิ๊ก|กิกะไบต์)(?![a-z])|(?:storage|ความจุ|ความจำเครื่อง|rom)\s*[/ :=-]*\s*(\d{1,4})(?!\d)'
    for match in re.finditer(pattern, text):
        prefix = text[max(0, match.start()-30):match.start()].split('\n')[-1]
        labels = list(re.finditer(r'ram|แรม|micro\s*sd|memory\s*card|เพิ่มเมม|rom|storage|ความจุ|ความจำเครื่อง', prefix))
        if not match[3] and labels and labels[-1][0] in ('ram', 'แรม', 'micro sd', 'memory card', 'เพิ่มเมม'):
            continue
        if re.match(r'\s*(?:ram|แรม)(?![a-z])', text[match.end():match.end()+10]):
            continue
        if match[2] == 'g' and int(match[1]) < 8:
            continue  # 4G/5G connectivity is not an explicit storage claim.
        value = int(match[1] or match[3]) * (1024 if match[2] == 'tb' else 1)
        if value in allowed:
            result.append({'value': value, 'text': match[0]})
    return result


def item_description(text):
    """Keep the item section before explicit shop/contact/other-stock headings."""
    lines = str(text or '').splitlines()
    kept = []
    for line in lines:
        if re.search(r'^\s*(?:[•✅🔻⭕]*\s*)?(?:เบอร์ติดต่อ|ติดต่อ\s*[:/]|โทร\s*[:.]|id\s*line|line\s*id|facebook|fanpage|สินค้าอื่น|รับซื้อ\s*รับเทิร์น)', line, re.I):
            break
        kept.append(line)
    return '\n'.join(kept)


def positive_hits(text, pattern, rules):
    return [{'text': m[0], 'offset': m.start()} for m in re.finditer(pattern, text, re.I)
            if not re.search(rules['negation_prefix_pattern'], text[max(0, m.start()-18):m.start()])]


def clean_row(row, rules):
    card, detail = row['raw_listing'], row['detail'] or {}
    holds, excludes, notes = [], [], []
    clean = {'brand': None, 'model': None, 'storage_gb': None,
             'price_thb': detail.get('price_thb'), 'condition': None,
             'published_at': detail.get('published_date')}
    evidence = {}
    if row['extraction_errors']:
        holds.append('detail_unavailable_or_unverified')
    title = detail.get('title') or card['name']
    titles = '\n'.join(dict.fromkeys([title, card['name'], card.get('subtitle', '')]))
    specs = detail.get('specs') or {}
    body = item_description(detail.get('description'))
    if re.search(rules['accessory_pattern'], normalized(title)):
        excludes.append('accessory')
    if re.search(rules['other_device_pattern'], normalized(title)):
        excludes.append('other_device')
    if re.search(rules['service_pattern'], title):
        excludes.append('buy_request_or_service')
    model_claims = models(titles)
    selected_models = models(specs.get('รุ่น', ''))
    model_values = {x['value'] for x in model_claims + selected_models}
    if len(model_values) == 1:
        clean['brand'], clean['model'] = 'Apple', next(iter(model_values))
        number = re.match(r'iPhone (\d+)', clean['model'])
        if number and int(number[1]) not in rules['numbered_model_tokens'] and clean['model'] not in ('iPhone 3G', 'iPhone 3GS'):
            holds.append('model_number_requires_review')
            clean['model'] = None
        if clean['model'] == 'iPhone SE':
            holds.append('se_generation_unspecified')
    elif len(model_values) > 1:
        holds.append('multiple_or_conflicting_models')
    else:
        holds.append('model_missing_or_unrecognized')
    opening = '\n'.join(body.splitlines()[:4])
    opening_models = [m for m in models(opening) if not re.search(
        r'(?:อยากเปลี่ยนเป็น|อยากเปลี่ยนไป|อยากได้)\s*$',
        normalized(opening)[max(0, m['offset_normalized']-30):m['offset_normalized']])]
    if clean['model'] and any(m['value'] != clean['model'] for m in opening_models):
        holds.append('model_description_conflict')
    evidence['model'] = {'selected': specs.get('รุ่น'), 'title_claims': model_claims,
                         'description_opening_claims': opening_models}
    capacities = storage_claims('\n'.join([specs.get('ความจุ', ''), titles, body,
                                           '\n'.join(card.get('badges', []))]), rules['storage_gb'])
    capacity_values = {x['value'] for x in capacities}
    if len(capacity_values) == 1:
        clean['storage_gb'] = next(iter(capacity_values))
    elif len(capacity_values) > 1:
        holds.append('storage_conflict_or_multiple_options')
    else:
        holds.append('storage_missing')
    evidence['storage_gb'] = {'selected': specs.get('ความจุ'), 'explicit_claims': capacities}
    price = clean['price_thb']
    if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
        holds.append('invalid_price')
    elif price in rules['price_placeholders'] or price < 100:
        holds.append('possible_placeholder_price')
    if detail.get('currency') != 'THB':
        holds.append('currency_unverified')
    if price != card.get('price'):
        holds.append('card_detail_price_conflict')
    # Only explicit price statements, not phone numbers, battery or installment rates.
    price_claims = []
    for line in body.splitlines():
        match = re.match(r'^\s*[•⭕💰🔥✅\s]*ราคา\s*[:：]?\s*([\d,]+)(?:\s*(?:บาท|฿|[-.]|$))', line)
        if match:
            price_claims.append({'value': int(match[1].replace(',', '')), 'text': line})
    if price_claims and any(x['value'] != price for x in price_claims):
        holds.append('description_price_conflict')
    partial = positive_hits(titles + '\n' + body, rules['partial_price_pattern'], rules)
    if partial:
        holds.append('possible_partial_payment_or_contract')
    evidence['price_thb'] = {'card': card.get('price'), 'detail': price,
                             'description_claims': price_claims, 'partial_payment_hits': partial}
    condition_uri = detail.get('condition_selected') or ''
    clean['condition'] = {'UsedCondition': 'used', 'NewCondition': 'new'}.get(condition_uri.rsplit('/', 1)[-1])
    if clean['condition'] is None:
        holds.append('condition_missing_or_unrecognized')
    damage = positive_hits(titles + '\n' + body + '\n' + str(detail.get('condition_label_raw') or ''),
                           rules['damage_pattern'], rules)
    if damage:
        holds.append('possible_damage_or_lock')
    evidence['condition'] = {'selected': condition_uri, 'label': detail.get('condition_label_raw'),
                             'damage_hits': damage, 'description_item_section': body}
    if not detail.get('description'):
        holds.append('description_missing')
    if 'ของใหม่' in titles + '\n' + body and clean['condition'] == 'used':
        notes.append('seller_new_claim_with_used_selected_retained')
    try:
        parsed_date = date.fromisoformat(clean['published_at'])
        if parsed_date > date.fromisoformat(card['scraped_at'][:10]):
            holds.append('published_date_after_snapshot')
    except (TypeError, ValueError):
        holds.append('published_date_missing_or_invalid')
    if clean['published_at'] != card.get('published_date'):
        holds.append('card_detail_date_conflict')
    evidence['published_at'] = {'card': card.get('published_date'), 'detail': clean['published_at']}
    return {'source': 'mac2hand', 'product_id': row['product_id'], 'url': row['url'], 'clean': clean,
            'status': 'excluded' if excludes else 'needs_review' if holds else 'accepted',
            'hold_reasons': sorted(set(holds)), 'exclusion_reasons': excludes, 'notes': notes,
            'evidence': evidence, 'original': row,
            'input_sha256': hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}


def clean_dataset(raw, extraction, output, rules_path=DEFAULT_RULES):
    raw, extraction, output = raw.resolve(), extraction.resolve(), output.resolve()
    protect(output, raw, extraction, ROOT / 'config')
    expected = json.loads((extraction.parent / 'raw_audit/raw_checksums.json').read_text())
    if checksums(raw) != expected:
        raise ValueError('Raw does not match audited snapshot')
    metadata = json.loads((extraction / 'run_metadata.json').read_text())
    input_file = extraction / 'mac2hand_extracted.jsonl'
    if sha(input_file) != metadata['extracted_sha256']:
        raise ValueError('Extraction hash mismatch')
    rows = read_jsonl(input_file)
    rules = json.loads(rules_path.read_text())
    results = [clean_row(row, rules) for row in rows]
    groups = defaultdict(list)
    for row in results:
        original = row['original']; detail = original['detail'] or {}
        seller = detail.get('seller_key')
        # Repeated seller text is a candidate for later review, not proof of the same device.
        if seller and detail.get('description') and row['clean']['model'] and row['clean']['storage_gb']:
            key = hashlib.sha256(json.dumps([seller, {k: v for k, v in row['clean'].items() if k != 'published_at'}, normalized(detail.get('title')),
                    normalized(detail['description'])], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
            groups[key].append(row)
    duplicate_groups = []
    for key, group in groups.items():
        if len(group) > 1:
            duplicate_groups.append({'candidate_group': key, 'product_ids': [r['product_id'] for r in group]})
            for row in group:
                row['candidate_duplicate_group'] = key
                row['notes'].append('possible_repeated_listing_not_confirmed_duplicate')
    raw_rows = read_jsonl(raw / 'listings.jsonl')
    if Counter(r['url'] for r in raw_rows) != Counter(r['url'] for r in results):
        raise ValueError('Rows missing or added')
    if not all(r['original']['raw_listing'] == card for r, card in zip(results, raw_rows)):
        raise ValueError('Original card changed')
    if checksums(raw) != expected:
        raise ValueError('Raw changed during cleaning')
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'mac2hand_cleaned.jsonl').open('w', encoding='utf-8') as file:
        for row in results:
            file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    fields = ['source', 'product_id', 'url', 'brand', 'model', 'storage_gb', 'condition', 'price_thb',
              'published_at', 'status', 'hold_reasons', 'exclusion_reasons', 'candidate_duplicate_group']
    for state in ('accepted', 'needs_review', 'excluded'):
        with (output / (state + '.csv')).open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
            for row in results:
                if row['status'] == state:
                    writer.writerow({**{f: row.get(f, '') for f in fields}, **row['clean'],
                                     'hold_reasons': '|'.join(row['hold_reasons']),
                                     'exclusion_reasons': '|'.join(row['exclusion_reasons'])})
    summary = {'snapshot': raw.name, 'rules_version': rules['version'], 'input_records': len(rows),
               'status_counts': dict(Counter(r['status'] for r in results)),
               'hold_reasons': dict(Counter(reason for row in results if row['status'] == 'needs_review' for reason in row['hold_reasons'])),
               'exclusion_reasons': dict(Counter(reason for row in results for reason in row['exclusion_reasons'])),
               'candidate_duplicate_groups': len(duplicate_groups),
               'candidate_duplicate_rows': sum(len(g['product_ids']) for g in duplicate_groups),
               'all_dates_retained': True}
    dump(output / 'summary.json', summary)
    dump(output / 'validation.json', {'accounting_passed': True, 'raw_unchanged': True,
                                      'original_cards_unchanged': True, 'extraction_hash_matches': True})
    dump(output / 'candidate_duplicate_groups.json', duplicate_groups)
    dump(output / 'run_metadata.json', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
         'input_sha256': sha(input_file), 'rules_sha256': sha(rules_path), 'script_sha256': sha(Path(__file__)),
         'raw': str(raw), 'extraction': str(extraction), 'rules': str(rules_path)})
    (output / 'rules.json').write_bytes(rules_path.read_bytes())
    (output / 'report.md').write_text('# ผล clean Mac2Hand\n\n' +
        f"ทั้งหมด {len(rows):,} รายการ ผล: {summary['status_counts']}\n\n" +
        'accepted = ผ่านกฎเตรียมข้อมูล ไม่ใช่ยืนยันสภาพจริงหรือพร้อมฝึกทันที ' +
        'needs_review = ข้อมูลขาด/ขัดกัน/ราคาไม่ชัด/อาการเสียหรือมีล็อก excluded = อุปกรณ์หรือบริการนอกขอบเขต\n\n' +
        'เก็บทุกวันที่และต้นฉบับทุกแถว ไม่เติมข้อมูลเดา ไม่ลบราคาที่สูงหรือต่ำด้วยสถิติ ' +
        'condition เป็นช่องผู้ขาย; ข้อความของใหม่แต่เลือกมือสองเก็บไว้ตามนโยบาย ' +
        'กลุ่มประกาศซ้ำเป็นผู้ต้องสงสัย ยังไม่รวม/ลบทิ้ง\n\n' +
        '| เหตุผลรอตรวจ | จำนวน |\n|---|---:|\n' +
        '\n'.join(f'| {key} | {n} |' for key, n in summary['hold_reasons'].items()) +
        '\n\nจำนวนเหตุผลซ้อนกันได้ หลักฐานรายแถวอยู่ใน mac2hand_cleaned.jsonl และคิวอยู่ใน needs_review.csv\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--rules', type=Path, default=DEFAULT_RULES)
    args = parser.parse_args()
    base = ROOT / 'data/intermediate/mac2hand' / args.raw.name
    clean_dataset(args.raw, args.input or base / 'extraction', args.output or base / 'clean', args.rules)
