"""Report queue dispositions from versioned cleaning and evidence corrections; no network."""
import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

if __package__:
    from .audit_ennxo_raw import ROOT, DEFAULT_RAW, dump, read_records
else:
    from audit_ennxo_raw import ROOT, DEFAULT_RAW, dump, read_records

DEFAULT_INPUT = ROOT / 'data/intermediate/ennxo' / DEFAULT_RAW.name / 'clean'
DEFAULT_BASELINE = ROOT / 'data/intermediate/ennxo' / DEFAULT_RAW.name / 'history' / 'rules_v4'


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


from script.artifacts import write_metadata

def next_actions(reasons):
    actions = []
    if 'reported_damage_or_lock' in reasons:
        actions.append('เก็บแยกกลุ่มอาการเสีย/ล็อก; ยังไม่รวมกับเครื่องปกติ')
    if any(r in reasons for r in ('possible_partial_payment_price', 'possible_placeholder_price', 'description_price_conflict', 'reviewed_price_unconfirmed')):
        actions.append('ยืนยันราคาทั้งเครื่องและภาระผ่อน; ไม่เลือกค่าที่ขัดกันเอง')
    if 'possible_bundle' in reasons:
        actions.append('ยืนยันราคามือถือเครื่องเดียว; ไม่แบ่งราคาชุดด้วยการเดา')
    if 'model_outside_observed_catalog' in reasons:
        actions.append('ตรวจชื่อ/รุ่นย่อยกับแหล่งผู้ผลิตเพิ่ม; ไม่พบ reference ไม่เท่ากับรุ่นไม่มีอยู่จริง')
    if any('missing' in r or 'not_confirmed' in r or 'possible_ram' in r or 'unconfirmed' in r for r in reasons):
        actions.append('หลักฐานข้อความยังไม่พอ; ตรวจ HTML รายสินค้าเดิม/ภาพที่เก็บไว้ ถ้าไม่ระบุให้คง missing')
    if any('conflict' in r for r in reasons):
        actions.append('ตรวจข้อขัดแย้งที่ยังเหลือกับต้นทาง; คงค่าทั้งสองไว้จนยืนยันได้')
    return actions or ['ตรวจเหตุผลและหลักฐานต้นทางก่อนรับเข้า']


def review(baseline, current, output):
    baseline, current, output = baseline.resolve(), current.resolve(), output.resolve()
    for protected in (baseline, current, ROOT / 'data/raw', ROOT / 'config'):
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Review output must be separate from inputs')
    paths = [base / 'ennxo_cleaned.jsonl' for base in (baseline, current)]
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    before, after = [read_records(p) for p in paths]
    old = {r['url']: r for r in before}
    if len(old) != len(before) or Counter(r['url'] for r in before) != Counter(r['url'] for r in after):
        raise ValueError('Baseline/current URL accounting differs')
    records = []
    transitions = Counter()
    for row in after:
        previous = old[row['url']]
        if previous['input_sha256'] != row['input_sha256']:
            raise ValueError('Evidence changed between review runs')
        if previous['status'] != 'needs_review' and row['status'] != 'needs_review':
            continue
        method = 'evidence_correction' if row.get('review_correction') else 'versioned_rules'
        actions = next_actions(row['hold_reasons']) if row['status'] == 'needs_review' else []
        records.append({'product_id': row['product_id'], 'url': row['url'], 'previous_status': previous['status'],
                        'current_status': row['status'], 'review_method': method,
                        'previous_reasons': previous['hold_reasons'], 'remaining_reasons': row['hold_reasons'],
                        'exclusion_reasons': row['exclusion_reasons'], 'next_actions': actions,
                        'clean': row['clean'], 'evidence': row['evidence'], 'input_sha256': row['input_sha256'],
                        'correction': row.get('review_correction'), 'page_file': row['original']['provenance']['page_file']})
        transitions[(previous['status'], row['status'])] += 1
    if hashes != [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]:
        raise ValueError('Inputs changed during report generation')
    output.mkdir(parents=True, exist_ok=True)
    dump(output / 'review_evidence.json', records)
    fields = ['product_id', 'url', 'previous_status', 'current_status', 'review_method', 'remaining_reasons',
              'next_actions', 'page_file', 'input_sha256']
    with (output / 'review_rows.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({key: '|'.join(row[key]) if isinstance(row[key], list) else row[key] for key in fields})
    summary = {'baseline_queue': sum(r['status'] == 'needs_review' for r in before),
               'current_queue': sum(r['status'] == 'needs_review' for r in after),
               'reported_rows': len(records), 'transitions': {a + ' -> ' + b: n for (a, b), n in sorted(transitions.items())},
               'current_evidence_corrections': sum(bool(r.get('review_correction')) for r in after),
               'inputs_unchanged': True,
               'review_scope': 'All baseline queue rows and newly held rows are accounted for; versioned rule checks are distinct from individual evidence corrections. No claim of independent human or physical-device verification.'}
    write_metadata(output, 'summary', summary)
    write_metadata(output, 'provenance', {'input_sha256': dict(zip(('baseline', 'current'), hashes)),
          'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    lines = ['# ENNXO — บัญชีคิวตรวจ', '',
             f'คิวเดิม {summary["baseline_queue"]} รายการ → คิวปัจจุบัน {summary["current_queue"]} รายการ', '',
             '| ก่อน → หลัง | จำนวน |', '|---|---:|']
    lines += [f'| {transition} | {n} |' for transition, n in summary['transitions'].items()]
    lines += ['', 'อ่าน `review_rows.csv` สำหรับบัญชีรายแถว และ `review_evidence.json` สำหรับหลักฐาน/คำแก้/เหตุผลเต็ม', '',
              f'คำตรวจรายแถวใน ledger ปัจจุบันมี {summary["current_evidence_corrections"]} รายการ เป็นการตรวจหลักฐานโดย Codex ช่วยงาน ส่วนแถวอื่นตรวจด้วยกฎเวอร์ชัน ไม่อ้างว่ามนุษย์ตรวจทุกแถวหรือยืนยันสเปคจริงแล้ว', '']
    write_metadata(output, 'report_text', '\n'.join(lines))
    print(summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=DEFAULT_BASELINE)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/intermediate/ennxo' / DEFAULT_RAW.name / 'review')
    args = parser.parse_args()
    review(args.baseline, args.input, args.output)
