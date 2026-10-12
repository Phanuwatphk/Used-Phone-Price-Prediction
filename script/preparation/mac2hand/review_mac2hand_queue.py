"""Triage all held Mac2Hand records and apply hash-bound, evidence-backed review decisions offline."""
import argparse
from collections import Counter
import copy
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if __package__:
    from script.scraper.mac2hand.mac2hand import read_jsonl
    from .prepare_mac2hand import ROOT, DEFAULT_RAW, dump, sha, protect
else:
    from script.scraper.mac2hand.mac2hand import read_jsonl
    from prepare_mac2hand import ROOT, DEFAULT_RAW, dump, sha, protect

BASE = ROOT / 'data/intermediate/mac2hand' / DEFAULT_RAW.name
DEFAULT_LEDGER = ROOT / 'config/mac2hand/manual_reviews.json'




from script.artifacts import write_metadata

def fingerprint(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def next_action(row):
    reasons = set(row['hold_reasons'])
    if 'detail_unavailable_or_unverified' in reasons:
        return 'missing_source', 'หน้าสินค้าอ่านไม่ได้; ต้องมีแหล่งข้อมูลเพิ่ม ไม่ใช้การ์ดแทนค่าที่ยืนยันแล้ว'
    if 'possible_damage_or_lock' in reasons:
        return 'condition_review', 'อ่านข้อความอาการ/คำปฏิเสธ/ประกัน; ถ้าเสียจริงเก็บแยกจากเครื่องปกติ'
    if reasons & {'multiple_or_conflicting_models', 'model_description_conflict', 'storage_conflict_or_multiple_options',
                  'description_price_conflict', 'card_detail_price_conflict', 'possible_partial_payment_or_contract',
                  'possible_placeholder_price', 'model_number_requires_review'}:
        return 'conflict_review', 'อ่านชื่อและรายละเอียดหลักเทียบราคา/ตัวเลือก ไม่เลือกค่าโดยอัตโนมัติ'
    if 'se_generation_unspecified' in reasons:
        return 'missing_generation', 'ตรวจว่ามีปี/รุ่นย่อยระบุชัดหรือไม่; ไม่เดาจากวันลงประกาศหรือราคา'
    return 'missing_field_review', 'ตรวจข้อความเต็มและคำย่อ; ถ้าไม่มีข้อมูลจริงให้ค้างไว้'


def apply_decision(row, decision):
    if row['status'] != 'needs_review' or decision['input_sha256'] != fingerprint(row) or decision['url'] != row['url']:
        raise ValueError('Review target is not held or its identity/hash has changed')
    if decision['disposition'] not in ('corrected', 'awaiting_evidence', 'keep_separate'):
        raise ValueError('Unknown review disposition')
    if not decision.get('rationale') or not decision.get('evidence'):
        raise ValueError('Review requires rationale and literal evidence')
    for evidence in decision['evidence']:
        value = row['original']
        for key in evidence['path'].split('.'):
            value = value.get(key) if isinstance(value, dict) else None
        if not isinstance(value, str) or not evidence['quote'] or evidence['quote'] not in value:
            raise ValueError('Review evidence is absent from the original source')
    patch = decision.get('patch', {})
    removed = set(decision.get('resolved_reasons', []))
    if not set(patch) <= {'brand', 'model', 'storage_gb'}:
        raise ValueError('Only brand/model/storage patches are supported in this review round')
    if not removed <= set(row['hold_reasons']):
        raise ValueError('Cannot resolve a reason not present')
    if decision['disposition'] != 'corrected' and (patch or removed):
        raise ValueError('Unresolved/separate reviews cannot modify clean values or remove holds')
    if decision['disposition'] == 'corrected':
        if not removed or not removed <= {'storage_missing', 'model_missing_or_unrecognized'}:
            raise ValueError('Only evidenced missing storage/model may be resolved in this round')
        allowed_patch = ({'storage_gb'} if 'storage_missing' in removed else set()) | ({'brand', 'model'} if 'model_missing_or_unrecognized' in removed else set())
        if set(patch) != allowed_patch:
            raise ValueError('Patch fields must correspond exactly to resolved reasons')
        if 'storage_missing' in removed and (type(patch.get('storage_gb')) is not int or patch['storage_gb'] not in (4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048)):
            raise ValueError('Missing storage requires a valid storage patch')
        if 'model_missing_or_unrecognized' in removed and (not isinstance(patch.get('brand'), str) or not patch['brand'].strip() or not isinstance(patch.get('model'), str) or not patch['model'].strip()):
            raise ValueError('Missing model requires both brand and model')
    result = copy.deepcopy(row)
    result['clean'].update(patch)
    result['hold_reasons'] = [r for r in row['hold_reasons'] if r not in removed]
    result['status'] = 'needs_review' if result['hold_reasons'] else 'accepted'
    result['manual_review'] = decision
    return result


def review(input_file, ledger_path, output):
    input_file, ledger_path, output = input_file.resolve(), ledger_path.resolve(), output.resolve()
    protect(output, input_file.parent, ROOT / 'data/raw', ROOT / 'config')
    hashes = (sha(input_file), sha(ledger_path))
    ledger = json.loads(ledger_path.read_text())
    if ledger['baseline_sha256'] != hashes[0]:
        raise ValueError('Ledger baseline hash mismatch; review the new baseline explicitly')
    rows = read_jsonl(input_file)
    if len({r['product_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate input identities')
    queue = {r['product_id']: r for r in rows if r['status'] == 'needs_review'}
    decisions = {}
    for decision in ledger['reviews']:
        key = decision['product_id']
        if key in decisions or key not in queue:
            raise ValueError('Duplicate or non-queue review decision')
        decisions[key] = decision
    results = [apply_decision(r, decisions[r['product_id']]) if r['product_id'] in decisions else copy.deepcopy(r) for r in rows]
    if hashes != (sha(input_file), sha(ledger_path)):
        raise ValueError('Review inputs changed during execution')
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'mac2hand_reviewed.jsonl').open('w', encoding='utf-8') as file:
        for row in results:
            file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    fields = ['source', 'product_id', 'url', 'brand', 'model', 'storage_gb', 'condition', 'price_thb', 'published_at', 'status', 'hold_reasons', 'exclusion_reasons', 'candidate_duplicate_group']
    for state in ('accepted', 'needs_review', 'excluded'):
        with (output / (state + '.csv')).open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
            for row in results:
                if row['status'] == state:
                    writer.writerow({**{f: row.get(f, '') for f in fields}, **row['clean'], 'hold_reasons': '|'.join(row['hold_reasons']), 'exclusion_reasons': '|'.join(row['exclusion_reasons'])})
    result_by_id = {r["product_id"]: r for r in results}
    evidence_rows = []
    for key, row in queue.items():
        category, action = next_action(row)
        evidence_rows.append({'product_id': key, 'url': row['url'], 'input_sha256': fingerprint(row),
            'reason_group': category, 'next_action': action, 'hold_reasons': row['hold_reasons'],
            'evidence': row['evidence'], 'original': row['original'],
            'manual_review': decisions.get(key), 'result_status': result_by_id[key]['status']})
    dump(output / 'queue_evidence.json', evidence_rows)
    with (output / 'queue_plan.csv').open('w', encoding='utf-8-sig', newline='') as file:
        fields = ['product_id', 'url', 'reason_group', 'next_action', 'hold_reasons', 'result_status', 'reviewed']
        writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
        for row in evidence_rows:
            writer.writerow({**{f: row[f] for f in fields if f in row},
                             'hold_reasons': '|'.join(row['hold_reasons']), 'reviewed': row['manual_review'] is not None})
    summary = {'baseline_queue': len(queue), 'manually_reviewed': len(decisions), 'not_manually_reviewed': len(queue)-len(decisions),
        'newly_accepted': sum(r['status'] == 'accepted' and r['product_id'] in queue for r in results),
        'final_status_counts': dict(Counter(r['status'] for r in results)),
        'review_dispositions': dict(Counter(d['disposition'] for d in decisions.values())),
        'queue_reason_groups': dict(Counter(next_action(r)[0] for r in queue.values())),
        'baseline_hold_reasons': dict(Counter(reason for r in queue.values() for reason in r['hold_reasons']))}
    write_metadata(output, 'summary', summary)
    dump(output / 'manual_reviews.json', ledger)
    write_metadata(output, 'validation', {'input_hashes_unchanged': True, 'records_preserved': len(rows)==len(results),
         'originals_unchanged': all(a['original']==b['original'] for a,b in zip(rows,results)),
         'non_queue_rows_unchanged': all(a==b for a,b in zip(rows,results) if a['status']!='needs_review')})
    write_metadata(output, 'provenance', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
        'baseline': str(input_file), 'baseline_sha256': hashes[0], 'ledger': str(ledger_path),
        'ledger_sha256': hashes[1], 'script_sha256': sha(Path(__file__))})
    write_metadata(output, 'report_text', '# ตรวจคิว Mac2Hand\n\n' +
        f"คิวเดิม {len(queue):,} ตรวจด้วย manual review {len(decisions)} รับเพิ่ม {summary['newly_accepted']} รายการ\n\n" +
        f"ผลล่าสุด: {summary['final_status_counts']}\n\n" +
        'queue_plan.csv จัดกลุ่มปัญหาและงานถัดไปครบทุกแถว ไม่ใช่ยืนยันว่าตรวจ manual ครบแล้ว ' +
        'queue_evidence.json เก็บหลักฐานเต็ม คำตัดสินผูก hash และข้อความตรงกับต้นฉบับ ' +
        'ชุดล่าสุดอยู่ใน mac2hand_reviewed.jsonl และ CSV แยกสถานะ ไม่แก้ raw หรือ clean baseline\n\n' +
        'รายการที่ข้อมูลต้นทางขาด ขัดกัน หรืออาจเสีย/ล็อกยังพักไว้ ไม่มีการเดา SE จากวันที่หรือเติมความจุจากราคา\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=BASE / 'clean/mac2hand_cleaned.jsonl')
    parser.add_argument('--ledger', type=Path, default=DEFAULT_LEDGER)
    parser.add_argument('--output', type=Path, default=BASE / 'manual_review')
    args = parser.parse_args()
    review(args.input, args.ledger, args.output)
