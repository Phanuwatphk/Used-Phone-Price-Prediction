"""Freeze a model input subset by excluding the union of user-approved EDA queues."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY = ROOT / 'config/shared/model_input_policy.json'
SNAPSHOT = 'ennxo_20261005_mac2hand_20261006_eda_queue_excluded_v1'
DEFAULT_OUTPUT = ROOT / 'data/final'
DEFAULT_AUDIT = ROOT / 'data/intermediate/model_input' / SNAPSHOT


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


from script.artifacts import reference_bytes, reference_json, reference_sha, write_metadata, write_metadata_bytes

def sha(path):
    return reference_sha(path)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        return reader.fieldnames, list(reader)


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def path_display(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def select(policy_path=DEFAULT_POLICY, output=DEFAULT_OUTPUT, audit=DEFAULT_AUDIT):
    policy_path, output, audit = policy_path.resolve(), output.resolve(), audit.resolve()
    policy_bytes = policy_path.read_bytes()
    policy_hash = hashlib.sha256(policy_bytes).hexdigest()
    policy = json.loads(policy_bytes)
    if policy['version'] != 1 or policy['action'] != 'exclude_all_queue_members':
        raise ValueError('Unsupported selection policy')
    files = {key: (ROOT / value).resolve() for key, value in policy['inputs'].items()}
    before = {key: sha(path) for key, path in files.items()}
    if before != policy['input_sha256']:
        raise ValueError('Inputs differ from the approved snapshot hashes')
    for destination in (output, audit):
        for protected in (policy_path, ROOT / 'data/raw', ROOT / 'config', *files.values()):
            if destination == protected or destination in protected.parents or protected in destination.parents:
                raise ValueError('Output overlaps a protected input')
    if output == audit or output in audit.parents or audit in output.parents:
        raise ValueError('Final and audit outputs overlap')
    fields, csv_rows = read_csv(files['dataset_csv'])
    rows = [json.loads(line) for line in files['dataset_jsonl'].read_text().splitlines()]
    schema = reference_json(files['schema'])
    ids = [r['listing_id'] for r in rows]
    if (not rows or len(ids) != len(set(ids)) or fields != list(schema['fields']) or
            any(set(row) != set(fields) for row in rows) or
            len(rows) != len(csv_rows) or
            any(any(str(row[key]) != csv_row[key] for key in fields) for row, csv_row in zip(rows, csv_rows))):
        raise ValueError('CSV/JSONL/schema or listing identities disagree')
    lineage = [json.loads(line) for line in files['lineage'].read_text().splitlines()]
    if len(lineage) != len(rows) or len({r['listing_id'] for r in lineage}) != len(rows) or {r['listing_id'] for r in lineage} != set(ids):
        raise ValueError('Lineage does not account for all input rows')
    queues = {}
    for key in ('outliers', 'price_extremes'):
        _, candidates = read_csv(files[key])
        queues[key] = {r['listing_id'] for r in candidates}
    components = json.loads(files['text_components'].read_text())
    queues['text_candidates'] = {identifier for group in components for identifier in group['listing_ids']}
    excluded_ids = set().union(*queues.values())
    if not excluded_ids <= set(ids):
        raise ValueError('EDA queue references an unknown listing ID')
    counts = {'input': len(rows), 'excluded': len(excluded_ids), 'retained': len(rows) - len(excluded_ids)}
    if counts != policy['expected_counts']:
        raise ValueError('Selection counts differ from the approved policy')
    retained = [r for r in rows if r['listing_id'] not in excluded_ids]
    decisions = [{'listing_id': identifier, 'selected': identifier not in excluded_ids,
                  'reasons': '|'.join(key for key, queue in queues.items() if identifier in queue)} for identifier in ids]
    excluded_csv = [{**r, 'selection_reasons': d['reasons']} for r, d in zip(csv_rows, decisions) if not d['selected']]
    if before != {key: sha(path) for key, path in files.items()} or sha(policy_path) != policy_hash:
        raise ValueError('Inputs changed during selection')
    output.mkdir(parents=True, exist_ok=True); audit.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'dataset.csv', fields, [r for r in csv_rows if r['listing_id'] not in excluded_ids])
    with (audit / 'dataset.jsonl').open('w', encoding='utf-8') as file:
        for row in retained: file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    with (audit / 'lineage.jsonl').open('w', encoding='utf-8') as file:
        for row in lineage:
            if row['listing_id'] not in excluded_ids: file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    write_csv(audit / 'excluded_rows.csv', fields + ['selection_reasons'], excluded_csv)
    write_csv(audit / 'selection_decisions.csv', ['listing_id', 'selected', 'reasons'], decisions)
    prices = sorted(r['price_thb'] for r in retained)
    summary = {**counts, 'source_counts': dict(Counter(r['source'] for r in retained)),
               'excluded_source_counts': dict(Counter(r['source'] for r in rows if r['listing_id'] in excluded_ids)),
               'queue_counts': {key: len(value) for key, value in queues.items()},
               'overlapping_queue_memberships': sum(map(len, queues.values())) - len(excluded_ids),
               'brand_counts': dict(Counter(r['brand'] for r in retained)),
               'publication_year_counts': dict(sorted(Counter(r['published_at'][:4] for r in retained).items())),
               'price_thb': {'min': min(prices), 'median': statistics.median(prices), 'max': max(prices)},
               'date_min': min(r['published_at'] for r in retained), 'date_max': max(r['published_at'] for r in retained),
               'stage': 'model_input_selection_before_split', 'queue_review_closed': True,
               'physical_duplicates_confirmed': False, 'train_test_split': False, 'model_trained': False,
               'selection_bias_note': 'User opted to exclude all flagged rows; results apply to this retained subset.'}
    _, written_csv = read_csv(output / 'dataset.csv')
    written_rows = [json.loads(line) for line in (audit / 'dataset.jsonl').read_text().splitlines()]
    written_lineage = [json.loads(line) for line in (audit / 'lineage.jsonl').read_text().splitlines()]
    validation = {'inputs_unchanged': before == {key: sha(path) for key, path in files.items()} and sha(policy_path) == policy_hash,
                  'all_rows_accounted_for': len(retained) + len(excluded_csv) == len(rows),
                  'no_queue_members_retained': not excluded_ids & {r['listing_id'] for r in retained},
                  'retained_values_unchanged': written_rows == retained,
                  'output_csv_jsonl_consistent': len(written_csv) == len(written_rows) and
                      all(all(str(row[key]) == csv_row[key] for key in fields) for row, csv_row in zip(written_rows, written_csv)),
                  'schema_unchanged': True,
                  'lineage_for_every_retained_row': len(written_lineage) == len(retained) and
                      {row['listing_id'] for row in written_lineage} == {row['listing_id'] for row in retained}}
    if not all(validation.values()): raise ValueError('Selection validation failed')
    write_metadata_bytes(output, 'schema', reference_bytes(files['schema']))
    write_metadata_bytes(output, 'policy', policy_bytes)
    write_metadata(output, 'summary', summary); write_metadata(output, 'validation', validation)
    write_metadata(output, 'provenance', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
          'input_hashes': {path_display(files[key]): value for key, value in before.items()},
          'policy_sha256': policy_hash, 'script_sha256': sha(Path(__file__)),
          'dataset_sha256': sha(output / 'dataset.csv'),
          'output_directories': {'final': path_display(output), 'audit': path_display(audit)}})
    write_metadata(output, 'report_text', f'# ชุดข้อมูลก่อนแบ่ง train/validation/test\n\n'
        f'เก็บ {len(retained):,} แถว จาก {len(rows):,} แถว ตัดคิว EDA รวม {len(excluded_ids):,} แถวตามผู้ใช้ '
        'โดยนับ listing_id ซ้ำข้ามคิวครั้งเดียว ไม่แก้ค่าของแถวที่เก็บ\n\n'
        'dataset.csv/JSONL เก็บชุดใช้งาน metadata.json#schema เก็บคอลัมน์ metadata.json#policy เก็บกฎและ hash '
        'metadata.json#summary เก็บจำนวน metadata.json#validation เก็บผลตรวจ metadata.json#provenance เก็บที่มา '
        'เหตุผลรายแถวและ lineage อยู่ในปลายทาง audit\n\n'
        'ยังไม่แบ่งข้อมูลหรือฝึกโมเดล การตัด flags เป็นนโยบายเลือกข้อมูล ไม่ยืนยันว่าแถวที่ตัดผิดจริงทั้งหมด\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, default=DEFAULT_POLICY)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--audit-output', type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    select(args.policy, args.output, args.audit_output)
