"""Re-extract every saved ENNXO listing with evidence; no cleaning or exclusions."""
import argparse
import csv
import hashlib
import json
import platform
from collections import Counter
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if __package__:
    from .audit_ennxo_raw import DEFAULT_RAW, ROOT, dump, inventory, read_records, missing
    from script.scraper.ennxo.ennxo_html import page_evidence
else:
    from audit_ennxo_raw import DEFAULT_RAW, ROOT, dump, inventory, read_records, missing
    from script.scraper.ennxo.ennxo_html import page_evidence


def specific_label(field):
    return isinstance(field, dict) and isinstance(field.get('name'), str) and bool(field['name'].strip()) and field.get('slug') != 'others' and field['name'] != 'อื่นๆ'


def extract(raw, output):
    raw, output = raw.resolve(), output.resolve()
    if output == raw or raw in output.parents or output in raw.parents:
        raise ValueError('Output must be separate from raw')
    checksums = inventory(raw)
    rows = read_records(raw / 'listings.jsonl')
    summary = json.loads((raw / 'ennxo_summary.json').read_text())
    if not summary.get('complete') or len(rows) != summary.get('raw_records'):
        raise ValueError('Incomplete raw snapshot')
    if len({r['url'] for r in rows}) != len(rows):
        raise ValueError('Repeated raw URLs; audit before extraction')
    pages = {}
    for number in sorted({r['page'] for r in rows}):
        path = raw / 'pages' / f'page_{number}.html'
        cards, products = page_evidence(path.read_text())
        expected = {r['url'] for r in rows if r['page'] == number}
        if {card['url'] for card in cards.values()} != expected:
            raise ValueError(f'HTML/raw accounting differs on page {number}')
        pages[number] = (cards, products)
    if len(pages) != summary.get('completed_pages'):
        raise ValueError('Saved page count differs from collection summary')
    extracted = []
    for line, row in enumerate(rows, 1):
        key = row['url'].split('/')[-1]
        cards, products = pages[row['page']]
        if key not in cards or key not in products:
            raise ValueError('Missing card/product evidence: ' + row['url'])
        card, payload = cards[key], products[key]
        product = payload['data']
        subfields = product.get('subfields') or {}
        maker, model = subfields.get('maker'), subfields.get('model')
        observations = []
        if len(card['price_texts']) != 1:
            observations.append('card_price_text_missing_or_multiple')
        if missing(card['info_text']):
            observations.append('card_info_text_missing')
        if missing(row.get('brand')) and specific_label(maker):
            observations.append('legacy_brand_missing_but_embedded_maker_available')
        if not specific_label(maker):
            observations.append('embedded_maker_unspecified')
        if not specific_label(model):
            observations.append('embedded_model_unspecified')
        if isinstance(maker, dict) and isinstance(row.get('model'), str) and row['model'].casefold() == str(maker.get('name')).casefold():
            observations.append('legacy_model_contains_maker')
        if missing(product.get('detail')):
            observations.append('missing_description')
        if missing(product.get('condition')):
            observations.append('missing_selected_condition')
        if missing(subfields.get('capacity')):
            observations.append('missing_embedded_capacity')
        if row.get('price') != product.get('price'):
            observations.append('legacy_and_embedded_prices_differ')
        if row.get('name') != product.get('name'):
            observations.append('legacy_and_embedded_names_differ')
        page_file = f'pages/page_{row["page"]}.html'
        extracted.append({'url': row['url'], 'product_id': key, 'source': 'ennxo',
                          'raw_listing': row, 'card': card, 'embedded_product': product,
                          'observations': observations,
                          'provenance': {'raw_line': line, 'page_file': page_file,
                                         'page_sha256': checksums[page_file], 'card_index': card['card_index'],
                                         'product_json_offsets': payload['json_offsets'],
                                         'description_reference': payload['description_reference']}})
    if inventory(raw) != checksums:
        raise ValueError('Raw changed during extraction')
    counts = Counter(issue for row in extracted for issue in row['observations'])
    # The old exported payload is comparison evidence only, never an input for extraction.
    legacy = json.loads((raw / 'ennxo_public_payload.json').read_text()) if (raw / 'ennxo_public_payload.json').exists() else None
    mismatches = []
    if legacy is not None:
        for row in extracted:
            previous = legacy.get(row['product_id'])
            if previous is None or {k: v for k, v in previous.items() if k != 'evidence_html_file'} != row['embedded_product']:
                mismatches.append(row['url'])
    result = {'extraction_version': 1, 'snapshot': raw.name, 'records': len(extracted), 'pages': len(pages),
              'matched_cards': len(extracted), 'matched_embedded_products': len(extracted),
              'descriptions_present': sum(not missing(r['embedded_product'].get('detail')) for r in extracted),
              'selected_condition_counts': dict(Counter(r['embedded_product'].get('condition') for r in extracted)),
              'specific_maker_available': sum(specific_label((r['embedded_product'].get('subfields') or {}).get('maker')) for r in extracted),
              'specific_model_available': sum(specific_label((r['embedded_product'].get('subfields') or {}).get('model')) for r in extracted),
              'observations': dict(sorted(counts.items())), 'records_excluded': 0, 'raw_values_overwritten': 0,
              'old_payload_comparison': {'available': legacy is not None, 'different_urls': mismatches},
              'accounting_passed': Counter(r['url'] for r in extracted) == Counter(r['url'] for r in rows)}
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'ennxo_extracted.jsonl').open('w', encoding='utf-8') as file:
        for row in extracted:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
    dump(output / 'summary.json', result)
    dump(output / 'raw_checksums.json', checksums)
    with (output / 'observations.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['url', 'observations', 'legacy_brand', 'legacy_model', 'embedded_maker', 'embedded_model', 'page_file'])
        for row in extracted:
            if row['observations']:
                subfields = row['embedded_product'].get('subfields') or {}
                writer.writerow([row['url'], json.dumps(row['observations']), row['raw_listing'].get('brand'),
                                 row['raw_listing'].get('model'), json.dumps(subfields.get('maker'), ensure_ascii=False),
                                 json.dumps(subfields.get('model'), ensure_ascii=False), row['provenance']['page_file']])
    scripts = [Path(__file__).resolve(), ROOT / 'script/scraper/ennxo/ennxo_html.py', Path(__file__).resolve().with_name('audit_ennxo_raw.py')]
    dump(output / 'run_metadata.json', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
         'python': platform.python_version(), 'beautifulsoup4': version('beautifulsoup4'), 'soupsieve': version('soupsieve'),
         'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts},
         'raw_fingerprint': hashlib.sha256(json.dumps(checksums, sort_keys=True).encode()).hexdigest()})
    report = ['# ENNXO — ถอดข้อมูลจาก HTML ขั้นที่ 2', '',
              'อ่าน HTML หน้ารวมโดยตรง ไม่ใช้คำตัดสินเก่าหรือไฟล์ payload เดิมเป็นต้นทาง ไม่เรียกเว็บ ไม่แก้ raw และไม่คัดออก', '',
              '| สิ่งที่ตรวจ | จำนวน |', '|---|---:|', f'| ประกาศ / การ์ด / ข้อมูลฝังที่จับคู่ได้ | {len(extracted):,} / {len(extracted):,} / {len(extracted):,} |',
              f'| HTML หน้ารวม | {len(pages)} |', f'| มีข้อความรายละเอียด | {result["descriptions_present"]:,} |',
              f'| ยี่ห้อเฉพาะที่เว็บระบุ | {result["specific_maker_available"]:,} |',
              f'| รุ่นเฉพาะที่เว็บระบุ | {result["specific_model_available"]:,} |',
              f'| ยี่ห้อขาดใน JSON เดิมแต่พบในข้อมูลฝัง | {counts["legacy_brand_missing_but_embedded_maker_available"]} |', '',
              'คำว่า “อื่นๆ” หรือไม่เลือกช่องไม่ได้ใช้เป็นยี่ห้อ/รุ่นเฉพาะ แต่ค่าต้นฉบับยังอยู่ครบ การมีรุ่นเฉพาะไม่ได้รับรองว่าตรงกับชื่อ/รายละเอียด', '',
              '## ผลลัพธ์', '', '- `ennxo_extracted.jsonl`: ทุกประกาศ แยก raw เดิม การ์ด ข้อมูลฝัง และที่มา',
              '- `observations.csv`: ข้อสังเกตรายประกาศ ไม่ใช่คำตัดสินรับเข้า/ตัดออก',
              '- `summary.json`: จำนวน ความครบ และการเทียบกับ payload เดิม',
              '- `raw_checksums.json`, `run_metadata.json`: หลักฐานไฟล์และเวอร์ชันโค้ด', '',
              'ยังไม่แก้รุ่น ความจุ ราคา หรือสภาพ และไม่สร้างชุดฝึก ขั้นต่อไปคือกำหนดกฎ clean และตรวจความขัดแย้งจากหลักฐานที่ถอดได้', '']
    (output / 'report.md').write_text('\n'.join(report))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    extract(args.raw, args.output or ROOT / 'data/intermediate/ennxo' / args.raw.name / 'extraction')
