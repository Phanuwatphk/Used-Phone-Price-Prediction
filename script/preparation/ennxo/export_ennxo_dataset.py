"""Export the accepted ENNXO snapshot unchanged into its final delivery directory."""
import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = 'ennxo_20261005T231833_239519_Asia-Bangkok'
DEFAULT_INPUT = ROOT / 'data/intermediate/ennxo' / SNAPSHOT / 'clean'
DEFAULT_OUTPUT = ROOT / 'data/intermediate/ennxo' / SNAPSHOT / 'accepted'


if not __package__:
    import sys
    sys.path.insert(0, str(ROOT))

from script.artifacts import read_metadata, write_metadata

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(input_dir, output):
    input_dir, output = input_dir.resolve(), output.resolve()
    for protected in (input_dir, ROOT / 'data/raw', ROOT / 'config'):
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Output overlaps a protected input')
    files = [input_dir / name for name in ('accepted.csv', 'metadata.json', 'ennxo_cleaned.jsonl')]
    before = {str(p): sha(p) for p in files}
    with files[0].open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    clean_summary = read_metadata(input_dir, 'summary')
    cleaned = [json.loads(line) for line in files[2].read_text().splitlines()]
    accepted = [r for r in cleaned if r['status'] == 'accepted']
    ids = [str(r['product_id']) for r in rows]
    if (not rows or len(ids) != len(set(ids)) or
            len(rows) != clean_summary['status_counts']['accepted'] or
            len(cleaned) != clean_summary['input_records'] or
            ids != [str(r['product_id']) for r in accepted] or
            any(r['source'] != 'ennxo' or r['status'] != 'accepted' for r in rows)):
        raise ValueError('Accepted dataset differs from clean snapshot accounting')
    for row, original in zip(rows, accepted):
        if (row['url'] != original['url'] or original['hold_reasons'] or original['exclusion_reasons'] or
                any(row.get(key) != str(value) for key, value in original['clean'].items())):
            raise ValueError('Accepted CSV values differ from cleaned evidence')
    if before != {str(p): sha(p) for p in files}:
        raise ValueError('Inputs changed during export')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'dataset.csv').write_bytes(files[0].read_bytes())
    if sha(output / 'dataset.csv') != before[str(files[0])]:
        raise ValueError('Export differs from accepted CSV')
    if before != {str(p): sha(p) for p in files}:
        raise ValueError('Inputs changed during export')
    summary = {'source': 'ennxo', 'snapshot': clean_summary['snapshot'],
               'records': len(rows), 'input_records': len(cleaned),
               'status_counts': clean_summary['status_counts'],
               'export_only': True, 'all_dates_retained': True}
    artifacts = {
        'summary.json': summary,
        'validation.json': {'input_files_unchanged': True, 'accepted_only': True,
                            'csv_bytes_unchanged': True, 'product_ids_unique': True},
        'run_metadata.json': {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
                              'input_hashes': {str(Path(p).relative_to(ROOT)) if Path(p).is_relative_to(ROOT) else p: h
                                               for p, h in before.items()},
                              'script_sha256': sha(Path(__file__)),
                              'dataset_sha256': sha(output / 'dataset.csv')}}
    for name, content in artifacts.items():
        write_metadata(output, {'summary.json':'summary','validation.json':'validation','run_metadata.json':'provenance'}[name], content)
    write_metadata(output, 'report_text', f'# ชุดข้อมูล ENNXO ส่งมอบ\n\n`dataset.csv` เก็บเฉพาะกลุ่มผ่าน {len(rows):,} แถว '
        'คัดลอก accepted.csv ทุก byte โดยไม่ clean ใหม่หรือเปลี่ยนคอลัมน์\n\n'
        'metadata.json#summary เก็บจำนวน, metadata.json#validation เก็บผลตรวจ, metadata.json#provenance เก็บที่มาและ hash '
        'ข้อมูลทุกสถานะและหลักฐานคิวเก็บใน data/intermediate/ennxo/<รอบ>/\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export(args.input, args.output)
