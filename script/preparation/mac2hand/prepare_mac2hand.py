"""Audit and extract the saved Mac2Hand snapshot, offline and without changing raw."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if __package__:
    from script.scraper.mac2hand.mac2hand import parse_detail, read_jsonl
else:
    from script.scraper.mac2hand.mac2hand import parse_detail, read_jsonl

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW = ROOT / 'data/raw/mac2hand_20261006T172805_252838_Asia-Bangkok'




from script.artifacts import write_metadata

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksums(raw):
    return {str(p.relative_to(raw)): sha(p) for p in sorted(raw.rglob('*')) if p.is_file()}


def protect(output, *inputs):
    for item in inputs:
        item = item.resolve()
        if output == item or item in output.parents or output in item.parents:
            raise ValueError(f'Output overlaps input: {item}')


def prepare(raw, output):
    raw, output = raw.resolve(), output.resolve()
    protect(output, raw, ROOT / 'config')
    before = checksums(raw)
    rows = read_jsonl(raw / 'listings.jsonl')
    manifest = json.loads((raw / 'details/manifest.json').read_text())
    summary = json.loads((raw / 'mac2hand_summary.json').read_text())
    progress = json.loads((raw / 'collection_progress.json').read_text())
    if progress['status'] not in ('collection_finished', 'collection_finished_with_failures'):
        raise ValueError('Collection has not finished; do not prepare a changing snapshot')
    ids = [r['product_id'] for r in rows]
    urls = [r['url'] for r in rows]
    pages = list((raw / 'pages').glob('page_*.html'))
    if (not summary.get('complete') or len(rows) != summary['records'] or
            len(pages) != summary['pages'] or len(set(ids)) != len(ids) or
            len(set(urls)) != len(urls) or set(ids) != set(manifest)):
        raise ValueError('Raw accounting failed: rows, pages, unique identities or manifest')
    results, issues = [], []
    for i, row in enumerate(rows, 1):
        key = row['product_id']
        entry = manifest[key]
        path = raw / 'details' / f'product_{key}.html'
        detail, errors = None, []
        if path.exists():
            try:
                detail = parse_detail(path.read_text(encoding='utf-8'), key)
            except ValueError as error:
                errors.append('detail_parse_failed: ' + str(error))
        else:
            errors.append('detail_html_missing')
        if detail is not None and entry.get('status') == 'ok' and detail != entry.get('detail'):
            errors.append('manifest_detail_mismatch')
        if entry.get('status') != 'ok':
            errors.append('collection_failed: ' + entry.get('error', 'unknown'))
        for error in errors:
            issues.append({'product_id': key, 'url': row['url'], 'reason': error})
        results.append({'source': 'mac2hand', 'product_id': key, 'url': row['url'],
                        'raw_listing': row, 'detail': detail, 'extraction_errors': errors,
                        'provenance': {'html_file': str(path.relative_to(raw)),
                                       'html_sha256': before.get(str(path.relative_to(raw))),
                                       'manifest_status': entry.get('status'),
                                       'detail_scraped_at': entry.get('scraped_at')}})
        if i % 500 == 0:
            print(f'Parsed {i}/{len(rows)}', flush=True)
    after = checksums(raw)
    if before != after:
        raise ValueError('Raw changed during extraction; output not published')
    audit = {'snapshot': raw.name, 'records': len(rows), 'pages': len(pages),
             'manifest_status': dict(Counter(e['status'] for e in manifest.values())),
             'parsed_details': sum(r['detail'] is not None for r in results),
             'rows_with_errors': sum(bool(r['extraction_errors']) for r in results),
             'accounting_passed': True, 'raw_unchanged': True,
             'missing_fields': {f: sum(not (r['detail'] or {}).get(f) for r in results)
                                for f in ('description', 'price_thb', 'published_date', 'condition_selected')},
             'structured_specs_rows': sum(bool((r['detail'] or {}).get('specs')) for r in results)}
    audit_dir, extract_dir = output / 'raw_audit', output / 'extraction'
    audit_dir.mkdir(parents=True, exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    write_metadata(audit_dir, 'summary', audit)
    dump(audit_dir / 'issues.json', issues)
    dump(audit_dir / 'raw_checksums.json', before)
    with (extract_dir / 'mac2hand_extracted.jsonl').open('w', encoding='utf-8') as file:
        for row in results:
            file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    write_metadata(extract_dir, 'summary', audit)
    write_metadata(extract_dir, 'provenance', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
         'raw': str(raw), 'script_sha256': sha(Path(__file__)),
         'parser_sha256': sha(ROOT / 'script/scraper/mac2hand/mac2hand.py'),
         'extracted_sha256': sha(extract_dir / 'mac2hand_extracted.jsonl')})
    write_metadata(audit_dir, 'report_text', '# ตรวจ raw Mac2Hand\n\n' +
        f"ประกาศ {len(rows):,} รายการ หน้ารวม {len(pages)} หน้า อ่านรายละเอียดได้ {audit['parsed_details']:,} " +
        f"มีข้อผิดพลาด {audit['rows_with_errors']} รายการ\n\n" +
        'ตรวจรหัสและ URL ไม่ซ้ำ บัญชี manifest ตรงกับประกาศ และ hash raw ก่อน/หลังตรงกัน ' +
        'ทุก HTML รายละเอียดถูก parse ใหม่โดยจับคู่ Product sku; ไม่ส่ง request เพิ่ม\n\n' +
        'ดู metadata.json#summary สำหรับค่าขาด issues.json สำหรับข้อผิดพลาด และ raw_checksums.json สำหรับต้นฉบับทั้งหมด\n')
    print(json.dumps(audit, ensure_ascii=False, indent=2), flush=True)
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    prepare(args.raw, args.output or ROOT / 'data/intermediate/mac2hand' / args.raw.name)
