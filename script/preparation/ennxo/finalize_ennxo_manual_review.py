"""Validate recorded individual evidence reviews and publish the complete ENNXO round."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

if __package__:
    from .audit_ennxo_raw import ROOT, DEFAULT_RAW, dump, read_records
else:
    from audit_ennxo_raw import ROOT, DEFAULT_RAW, dump, read_records

DEFAULT_INPUT = ROOT / 'data/intermediate/ennxo' / DEFAULT_RAW.name / 'clean'
DEFAULT_LEDGER = ROOT / 'config/ennxo/manual_review.json'
DEFAULT_OUTPUT = ROOT / 'data/intermediate/ennxo' / DEFAULT_RAW.name / 'manual_review'


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


from script.artifacts import write_metadata

def finalize(current, ledger_path, output):
    current, ledger_path, output = current.resolve(), ledger_path.resolve(), output.resolve()
    ledger = json.loads(ledger_path.read_text())
    if ledger.get('schema_version') != 1 or not isinstance(ledger.get('reviews'), list):
        raise ValueError('Unsupported manual review ledger')
    baseline = (ROOT / ledger['baseline']).resolve()
    for protected in (baseline, current, ROOT / 'data/raw', ROOT / 'config'):
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Review output must be separate from inputs')
    paths = [baseline / 'ennxo_cleaned.jsonl', current / 'ennxo_cleaned.jsonl', ledger_path]
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    before, after = [read_records(p) for p in paths[:2]]
    old, new = [{r['url']: r for r in rows} for rows in (before, after)]
    if len(old) != len(before) or len(new) != len(after) or old.keys() != new.keys():
        raise ValueError('Baseline/current URL accounting differs')
    if any(old[url]['input_sha256'] != new[url]['input_sha256'] for url in old):
        raise ValueError('Source evidence changed')
    queue = {url: r for url, r in old.items() if r['status'] == 'needs_review'}
    reviews = ledger['reviews']
    if Counter(r['url'] for r in reviews) != Counter({url: 1 for url in queue}):
        raise ValueError('Manual reviews must cover each baseline queue row exactly once')
    records = []
    for review in reviews:
        row = new[review['url']]
        if review.get('input_sha256') != row['input_sha256'] or review.get('product_id') != row['product_id']:
            raise ValueError('Manual review evidence changed: ' + row['url'])
        if any(not isinstance(review.get(k), str) or not review[k].strip()
               for k in ('reviewer', 'reviewed_on', 'reason')):
            raise ValueError('Review requires reviewer, date and reason')
        original, evidence = row['original'], review['evidence']
        product = original['embedded_product']
        lines = [{'line': n, 'text': line} for n, line in enumerate((product.get('detail') or '').splitlines(), 1)]
        expected = {'title': product.get('name'), 'selected_subfields': product.get('subfields'),
                    'selected_price': product.get('price'), 'description_lines': lines,
                    'page_file': original['provenance']['page_file'],
                    'page_sha256': original['provenance']['page_sha256']}
        if any(evidence.get(k) != v for k, v in expected.items()):
            raise ValueError('Quoted evidence differs from original: ' + row['url'])
        if row['status'] == 'accepted':
            disposition = 'accepted'
        elif row['status'] == 'excluded':
            disposition = 'excluded'
        elif set(row['hold_reasons']) == {'reported_damage_or_lock'}:
            disposition = 'confirmed_damage_or_lock'
        else:
            disposition = 'awaiting_evidence'
        records.append({**review, 'disposition': disposition, 'current_status': row['status'],
                        'remaining_reasons': row['hold_reasons'], 'exclusion_reasons': row['exclusion_reasons'],
                        'clean': row['clean'], 'correction': row.get('review_correction')})
    if hashes != [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]:
        raise ValueError('Inputs changed during report generation')
    counts = Counter(r['disposition'] for r in records)
    changes_outside = [url for url in old if url not in queue and old[url]['status'] != new[url]['status']]
    summary = {'round': ledger['round'], 'baseline_queue': len(queue), 'reviewed_records': len(records),
               'unreviewed_records': 0, 'disposition_counts': dict(sorted(counts.items())),
               'dataset_status_counts': dict(sorted(Counter(r['status'] for r in after).items())),
               'status_changes_outside_baseline_queue': changes_outside,
               'complete_evidence_coverage': True, 'inputs_unchanged': True,
               'model_scope_decision': ledger.get('model_scope_decision'),
               'scope': 'Individual source evidence reviews assisted by Codex; no independent human or physical verification. Reviewed does not mean every record is usable for training.'}
    output.mkdir(parents=True, exist_ok=True)
    write_metadata(output, 'summary', summary)
    dump(output / 'review_evidence.json', records)
    dump(output / 'manual_reviews.json', ledger)
    write_metadata(output, 'provenance', {'input_sha256': dict(zip(('baseline', 'current', 'manual_ledger'), hashes)),
                                      'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    fields = ['product_id', 'url', 'disposition', 'current_status', 'reason', 'remaining_reasons',
              'reviewer', 'reviewed_on', 'input_sha256']
    for name, group in [('reviewed', records), ('accepted_from_queue', [r for r in records if r['disposition'] == 'accepted']),
                        ('confirmed_damage_or_lock', [r for r in records if r['disposition'] == 'confirmed_damage_or_lock']),
                        ('awaiting_evidence', [r for r in records if r['disposition'] == 'awaiting_evidence']),
                        ('excluded_from_queue', [r for r in records if r['disposition'] == 'excluded'])]:
        with (output / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for record in group:
                writer.writerow({k: '|'.join(record[k]) if isinstance(record[k], list) else record[k] for k in fields})
    labels = {'accepted': 'ผ่านหลังตรวจ', 'excluded': 'แยกออกจากเป้าหมาย',
              'confirmed_damage_or_lock': 'ตรวจแล้ว: เครื่องเสีย/ล็อก เก็บแยก',
              'awaiting_evidence': 'ตรวจแล้ว: หลักฐานยังไม่พอ/ขัดกัน'}
    lines = ['# ENNXO — ผลตรวจรายรายการ', '',
             f'ตรวจคิวเดิมครบ {len(records)} รายการ ไม่มีรายการที่ยังไม่ได้อ่านหลักฐานในรอบนี้', '',
             '| ผลตรวจ | จำนวน |', '|---|---:|']
    lines += [f'| {label} | {counts[key]} |' for key, label in labels.items()]
    lines += ['', 'เครื่องเสีย/ล็อกยังเป็น needs_review ใน cleaner ตามนโยบายแยกจากเครื่องปกติ การตรวจครบไม่ใช่การรับเข้าชุดฝึกทั้งหมด', '',
              'อ่าน reviewed.csv สำหรับผลรายแถว และ review_evidence.json สำหรับข้อความครบ เลขบรรทัด หลักฐาน HTML และคำแก้', '',
              '## รายการที่ต้องมีหลักฐานเพิ่ม', '', '| รหัส | สิ่งที่ยังติด |', '|---|---|']
    lines += [f'| [{r["product_id"]}]({r["url"]}) | {r["reason"].replace(chr(10), " ").replace("|", "/")} |'
              for r in records if r['disposition'] == 'awaiting_evidence']
    lines += ['', 'ไม่เติมรุ่น ความจุ หรือราคาที่ต้นทางไม่ยืนยัน และเก็บ raw ทุกแถว', '']
    write_metadata(output, 'report_text', '\n'.join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--ledger', type=Path, default=DEFAULT_LEDGER)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    finalize(args.input, args.ledger, args.output)
