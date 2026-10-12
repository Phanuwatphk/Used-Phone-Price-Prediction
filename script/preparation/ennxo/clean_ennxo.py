"""Clean saved ENNXO extraction using versioned rules and a correction ledger."""
import argparse
import csv
import hashlib
import json
import platform
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__:
    from .audit_ennxo_raw import ROOT, DEFAULT_RAW, dump, inventory, read_records
    from .cleaning_rules import clean_row, apply_correction, model_key
else:
    from audit_ennxo_raw import ROOT, DEFAULT_RAW, dump, inventory, read_records
    from cleaning_rules import clean_row, apply_correction, model_key

DEFAULT_INPUT = ROOT / 'data/intermediate/ennxo' / DEFAULT_RAW.name / 'extraction'
DEFAULT_RULES = ROOT / 'config/ennxo/cleaning_rules.json'
DEFAULT_CORRECTIONS = ROOT / 'config/ennxo/corrections.json'

REVIEW_AREAS = [
    ('รุ่น', {'multiple_title_models', 'model_conflict', 'model_missing_or_ambiguous', 'selected_model_not_confirmed_in_title',
               'model_description_conflict', 'model_outside_observed_catalog', 'model_requires_review_after_brand_correction'},
     'เทียบชื่อ การ์ด ช่องรุ่น และรายละเอียด; รุ่นนอก catalog ตรวจชื่อกับแหล่งผู้ผลิตก่อนเพิ่มกฎ alias; ค่าขัดกันต้องบันทึกหลักฐานรายแถว'),
    ('ความจุ', {'storage_missing', 'storage_conflict', 'possible_ram_in_selected_storage', 'reviewed_storage_unconfirmed'},
     'ตรวจ ROM/RAM/SD จากข้อความเต็มหรือ HTML รายสินค้าเดิม; ไม่ใช้สเปคความจุที่รุ่นรองรับแทนความจุเครื่องที่ขาย'),
    ('ยี่ห้อ', {'brand_missing_or_ambiguous', 'brand_conflict'},
     'ตรวจชื่อและรายละเอียด พร้อมช่อง maker; ถ้ายืนยันการสะกดได้ให้เพิ่ม alias หรือคำแก้ที่มีหลักฐาน'),
    ('ราคา', {'invalid_price', 'possible_placeholder_price', 'price_source_conflict', 'card_price_conflict', 'description_price_conflict', 'possible_partial_payment_price', 'reviewed_price_unconfirmed'},
     'เทียบราคาช่องสินค้า การ์ด และข้อความราคา; แยกราคาทั้งเครื่องจากเงินดาวน์และค่างวด ถ้าไม่ทราบราคาทั้งเครื่องให้พัก'),
    ('อาการเสีย/ล็อก', {'reported_damage_or_lock'},
     'ตรวจว่าเป็นอาการปัจจุบัน คำปฏิเสธ ประวัติซ่อม หรือประกัน; เก็บสถานะความเสียหาย ไม่รวมเข้ากลุ่มเครื่องปกติโดยไม่มีหลักฐาน'),
    ('ขายเป็นชุด', {'possible_bundle'},
     'ตรวจว่าราคาเป็นของโทรศัพท์เครื่องเดียวหรือทั้งชุด; ไม่แบ่งราคาด้วยการคาดเดา'),
    ('ฟิลด์อื่น', {'condition_missing_or_unknown', 'missing_or_invalid_publication_date', 'invalid_or_future_publication_date', 'missing_title_or_description', 'description_non_phone_device', 'reviewed_identity_conflict'},
     'ย้อนดูข้อมูลต้นทางและตำแหน่ง HTML; ถ้าเว็บไม่ระบุจริงให้เก็บเป็น missing')
]


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


from script.artifacts import read_metadata, write_metadata, write_metadata_bytes

def clean(extraction, raw, output, rules_path=DEFAULT_RULES, corrections_path=DEFAULT_CORRECTIONS):
    extraction, raw, output = extraction.resolve(), raw.resolve(), output.resolve()
    for protected in (raw, extraction, rules_path.resolve().parent):
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Output must be separate from inputs')
    input_path = extraction / 'ennxo_extracted.jsonl'
    before = inventory(raw)
    if before != json.loads((extraction / 'raw_checksums.json').read_text()):
        raise ValueError('Raw snapshot changed since extraction')
    input_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    rows = read_records(input_path)
    raw_rows = read_records(raw / 'listings.jsonl')
    if Counter(r['url'] for r in rows) != Counter(r['url'] for r in raw_rows) or len({r['url'] for r in rows}) != len(rows):
        raise ValueError('Input/raw URL accounting differs')
    raw_by_url = {r['url']: r for r in raw_rows}
    if any(r['raw_listing'] != raw_by_url[r['url']] for r in rows):
        raise ValueError('Original values differ from raw')
    extraction_summary = read_metadata(extraction, 'summary')
    if not extraction_summary.get('accounting_passed') or extraction_summary.get('records') != len(rows):
        raise ValueError('Extraction accounting not passed')
    rules_bytes, corrections_bytes = rules_path.read_bytes(), corrections_path.read_bytes()
    rules, ledger = json.loads(rules_bytes), json.loads(corrections_bytes)
    if rules.get('version') not in (1, 2, 3, 4, 5, 6) or ledger.get('schema_version') != 1 or not isinstance(ledger.get('corrections'), list):
        raise ValueError('Unsupported rules/correction schema')
    if rules.get('field_source_priority') not in (None, 'description_first'):
        raise ValueError('Unsupported field source priority')
    if rules.get('accepted_conditions', ['used']) not in (['used'], ['used', 'new']) or rules.get('condition_text_conflict_action', 'hold') not in ('hold', 'note'):
        raise ValueError('Unsupported condition policy')
    corrections = {}
    for entry in ledger['corrections']:
        if not isinstance(entry, dict) or entry.get('url') in corrections or entry.get('url') not in {r['url'] for r in rows}:
            raise ValueError('Correction URL is missing, repeated or unknown')
        corrections[entry['url']] = entry
    catalog = {}
    for row in rows:
        sub = row['embedded_product'].get('subfields') or {}
        maker, model = sub.get('maker') or {}, sub.get('model') or {}
        if maker.get('slug') != 'others' and model.get('slug') != 'others' and model.get('name'):
            key = (maker.get('name'), model_key(model['name'], maker.get('name')))
            if key in catalog and catalog[key] != model['name']:
                raise ValueError('Model normalization collision: ' + str(key))
            catalog[key] = model['name']
    references = {}
    for reference in rules.get('verified_model_references', []):
        if reference.get('brand') not in rules['brands'] or not reference.get('models') or not reference.get('source_url', '').startswith('https://') or not reference.get('checked_on'):
            raise ValueError('Invalid model reference')
        for name in reference['models']:
            key = (reference['brand'], model_key(name, reference['brand']))
            catalog.setdefault(key, name)
            references.setdefault(key, []).append(reference['source_url'])
    results = []
    for row in rows:
        result = clean_row(row, rules, catalog)
        if row['url'] in corrections:
            apply_correction(result, corrections[row['url']], rules)
        key = (result['clean']['brand'], model_key(result['clean']['model'], result['clean']['brand']))
        result['evidence']['model']['catalog_reference_urls'] = references.get(key, [])
        # Exact same image is only a candidate grouping signal, never grounds to delete a row.
        image = row['card'].get('image_url')
        result['candidate_image_group'] = hashlib.sha256(image.encode()).hexdigest()[:20] if image else None
        results.append(result)
    if inventory(raw) != before or hashlib.sha256(input_path.read_bytes()).hexdigest() != input_hash:
        raise ValueError('Inputs changed during cleaning')
    if rules_path.read_bytes() != rules_bytes or corrections_path.read_bytes() != corrections_bytes:
        raise ValueError('Configuration changed during cleaning')
    status = Counter(r['status'] for r in results)
    if sum(status.values()) != len(raw_rows) or any(r['status'] == 'accepted' and (r['hold_reasons'] or r['exclusion_reasons'] or any(v is None for v in r['clean'].values())) for r in results):
        raise ValueError('Clean output invariant failed')
    counts = Counter(reason for r in results for reason in r['hold_reasons'] + r['exclusion_reasons'])
    image_groups = Counter(r['candidate_image_group'] for r in results if r['candidate_image_group'])
    summary = {'cleaning_version': rules['version'], 'snapshot': raw.name, 'input_records': len(rows),
               'status_counts': {s: status[s] for s in ('accepted', 'needs_review', 'excluded')},
               'reason_counts': dict(sorted(counts.items())), 'corrections_applied': len(corrections),
               'missing_legacy_brands_recovered_from_html': sum('legacy_brand_missing_but_embedded_maker_available' in r['original']['observations'] for r in results),
               'models_recovered_from_title': sum('model_from_explicit_title' in r['notes'] for r in results),
               'description_field_counts': {field: sum(field + '_from_description' in r['notes'] for r in results) for field in ('brand', 'model', 'storage_gb')},
               'verified_model_keys': len(references),
               'repeated_image_candidate_groups': sum(n > 1 for n in image_groups.values()),
               'accounting_passed': True, 'raw_unchanged': True,
               'limitations': ['accepted means passed current rules, not independently verified ground truth',
                               'prices are asking prices, not completed-sale prices',
                               'no train/test split, duplicate adjudication or model training yet']}
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'ennxo_cleaned.jsonl').open('w', encoding='utf-8') as file:
        for row in results:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
    fields = ['url', 'product_id', 'source', 'status', 'brand', 'model', 'storage_gb', 'condition', 'price_thb', 'published_at',
              'title', 'description', 'hold_reasons', 'exclusion_reasons', 'notes', 'input_sha256', 'page_file', 'candidate_image_group']
    for state in ('accepted', 'needs_review', 'excluded'):
        with (output / (state + '.csv')).open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in results:
                if row['status'] != state:
                    continue
                original = row['original']
                writer.writerow({**{k: row[k] for k in ('url', 'product_id', 'source', 'status', 'input_sha256', 'candidate_image_group')},
                                 **row['clean'], 'title': original['embedded_product'].get('name'),
                                 'description': original['embedded_product'].get('detail'),
                                 'page_file': original['provenance']['page_file'],
                                 **{k: '|'.join(row[k]) for k in ('hold_reasons', 'exclusion_reasons', 'notes')}})
    write_metadata(output, 'summary', summary)
    tasks = [{'area': area, 'records': sum(r['status'] == 'needs_review' and bool(set(r['hold_reasons']) & reasons) for r in results),
              'reason_codes': sorted(reasons), 'next_action': action} for area, reasons, action in REVIEW_AREAS]
    dump(output / 'review_plan.json', {'areas': tasks, 'note': 'Counts overlap: a listing can require more than one type of review'})
    write_metadata(output, 'validation', {'raw_input_urls_match': True, 'original_values_match_raw': True,
         'output_urls_match_input': Counter(r['url'] for r in results) == Counter(r['url'] for r in rows),
         'status_accounting_passed': sum(status.values()) == len(rows),
         'accepted_has_required_values_and_no_unresolved_reasons': True, 'raw_unchanged': True})
    dump(output / 'model_catalog.json', [{'brand': brand, 'normalized_key': key, 'selected_label': label}
                                        for (brand, key), label in sorted(catalog.items())])
    dump(output / 'raw_checksums.json', before)
    write_metadata_bytes(output, 'rules', rules_bytes)
    (output / 'corrections.json').write_bytes(corrections_bytes)
    scripts = [Path(__file__).resolve(), Path(__file__).with_name('cleaning_rules.py'), Path(__file__).with_name('description_sections.py'), Path(__file__).with_name('audit_ennxo_raw.py')]
    write_metadata(output, 'provenance', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
         'python': platform.python_version(), 'input_sha256': input_hash,
         'rules_sha256': hashlib.sha256(rules_bytes).hexdigest(), 'corrections_sha256': hashlib.sha256(corrections_bytes).hexdigest(),
         'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts}})
    lines = ['# ENNXO — ผลตรวจและ clean', '',
             f'อ่าน extraction และหลักฐาน HTML ที่เก็บไว้ ตรวจด้วยกฎเวอร์ชัน {rules["version"]} ไม่ส่ง request ไปเว็บ และเก็บต้นฉบับทุกแถว', '',
             '| สถานะ | จำนวน |', '|---|---:|', f'| ผ่านกฎปัจจุบัน (accepted) | {status["accepted"]:,} |',
             f'| ต้องตรวจเพิ่มเติม (needs_review) | {status["needs_review"]:,} |', f'| นอกขอบเขต (excluded) | {status["excluded"]:,} |',
             f'| รวม | {len(rows):,} |', '',
             'accepted ยังไม่ใช่ชุดฝึกสำเร็จรูป ต้องตรวจกลุ่มประกาศซ้ำ กำหนด split และตรวจตัวอย่างก่อนฝึก รายการ excluded ยังอยู่ใน JSONL และ CSV ไม่ได้ลบ', '',
             '## เหตุผลที่พบ', '', '| รหัส | จำนวนประกาศ |', '|---|---:|']
    lines += [f'| {reason} | {count} |' for reason, count in sorted(counts.items())]
    lines += ['', '## วิธีตรวจคิวต่อ', '', '| กลุ่ม | ประกาศที่พัก | วิธีตรวจ |', '|---|---:|---|']
    lines += [f'| {task["area"]} | {task["records"]} | {task["next_action"]} |' for task in tasks if task['records']]
    lines += ['', 'หนึ่งประกาศมีหลายเหตุผลได้ ดู `needs_review.csv` สำหรับคิวตรวจ และ `ennxo_cleaned.jsonl` สำหรับค่าต้นฉบับ หลักฐาน และเหตุผลครบทุกแถว', '',
              'กฎและคำตอบที่ใช้รอบนี้อยู่ใน `metadata.json#rules` และ `corrections.json`; hash ของ input/โค้ดอยู่ใน `metadata.json#provenance`', '']
    write_metadata(output, 'report_text', '\n'.join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--rules', type=Path, default=DEFAULT_RULES)
    parser.add_argument('--corrections', type=Path, default=DEFAULT_CORRECTIONS)
    args = parser.parse_args()
    clean(args.input, args.raw, args.output or ROOT / 'data/intermediate/ennxo' / args.raw.name / 'clean', args.rules, args.corrections)
