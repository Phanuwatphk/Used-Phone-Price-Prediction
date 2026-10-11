"""Build a usable normal-device dataset and fully account for every quarantined Mac2Hand row."""
import argparse
from collections import Counter, defaultdict
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
    from .prepare_mac2hand import ROOT, DEFAULT_RAW, protect, dump, sha, checksums
    from .resolution_rules import resolve, normalized
else:
    from script.scraper.mac2hand.mac2hand import read_jsonl
    from prepare_mac2hand import ROOT, DEFAULT_RAW, protect, dump, sha, checksums
    from resolution_rules import resolve, normalized

BASE = ROOT / 'data/intermediate/mac2hand' / DEFAULT_RAW.name
DEFAULT_RULES = ROOT / 'config/mac2hand/finalization_rules.json'
DEFAULT_CATALOG = ROOT / 'config/mac2hand/iphone_model_names.json'
FIELDS = ['source', 'product_id', 'url', 'brand', 'model', 'storage_gb', 'condition', 'price_thb',
          'published_at', 'seller_key', 'candidate_duplicate_group', 'disposition', 'hold_reasons', 'exclusion_reasons', 'notes', 'next_action']


def next_action(row):
    disposition = row['disposition']
    if disposition == 'accepted':
        return 'ใช้ใน EDA; ตรวจกลุ่มประกาศซ้ำก่อนแบ่ง train/test'
    if disposition == 'excluded':
        return 'เก็บต้นฉบับแยก; ไม่ใช้กับโมเดลราคามือถือ'
    if disposition == 'missing_source':
        return 'ต้องได้หน้ารายละเอียดสินค้าที่ตรง URL ใหม่; ถ้าหน้าหายคงแยกไว้'
    if disposition == 'non_normal':
        return 'เก็บศึกษาเครื่องเสีย/ล็อก/เงื่อนไขพิเศษแยกจากโมเดลรอบแรก'
    actions = []
    for reason in row['hold_reasons']:
        if 'storage' in reason:
            action = 'ต้องมีความจุเครื่องที่ขายชัดเจนจากผู้ขาย; ค่าขัดกันต้องยืนยันเครื่องเดียว'
        elif 'se_' in reason:
            action = 'ต้องมีรุ่นย่อย SE ที่ยืนยันได้; ไม่อนุมานจากสีหรือวันที่'
        elif 'model' in reason:
            action = 'ต้องมีชื่อรุ่นเครื่องที่ขายชัดเจน; หลายรุ่นต้องแยกเครื่องพร้อมราคา'
        elif 'price' in reason or 'partial_payment' in reason:
            action = 'ต้องยืนยันราคาขายเต็มของเครื่องเดียว; ไม่เลือกราคาที่ขัดกันหรือเงินดาวน์'
        elif 'date' in reason:
            action = 'ต้องยืนยันวันที่ประกาศจากหน้าสินค้าที่ตรงกัน'
        elif 'description' in reason:
            action = 'ต้องมีรายละเอียดสินค้าเพิ่มเติมจากหน้าต้นทางหรือผู้ขาย'
        elif 'condition' in reason:
            action = 'ต้องยืนยันสภาพและสถานะการใช้งานจากรายละเอียดสินค้า'
        elif 'currency' in reason:
            action = 'ต้องยืนยันว่าราคาเป็นเงินบาท'
        else:
            action = 'ต้องมีหลักฐานต้นทางเพิ่มสำหรับ ' + reason
        if action not in actions:
            actions.append(action)
    return '; '.join(actions) + '; หากหาไม่ได้ให้คงแยกไว้ ไม่เติมค่าเดา'


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer=csv.DictWriter(file,fieldnames=FIELDS);writer.writeheader()
        for row in rows:
            writer.writerow({**{k:row.get(k,'') for k in FIELDS},**row['clean'],
                'seller_key':(row['original']['detail'] or {}).get('seller_key') or '',
                'hold_reasons':'|'.join(row['hold_reasons']),
                'exclusion_reasons':'|'.join(row['exclusion_reasons']), 'notes':'|'.join(row['notes'])})


def finalize(raw, input_file, output, rules_path=DEFAULT_RULES, catalog_path=DEFAULT_CATALOG, review_output=None):
    raw,input_file,output=raw.resolve(),input_file.resolve(),output.resolve()
    review_output = review_output.resolve() if review_output is not None else output
    for destination in (output, review_output):
        protect(destination,raw,input_file.parent,ROOT/'config')
    if output != review_output:
        protect(output, review_output)
    expected=json.loads((input_file.parent.parent/'raw_audit/raw_checksums.json').read_text())
    if checksums(raw)!=expected:raise ValueError('Raw changed since audit')
    before={str(p.resolve()):sha(p) for p in (input_file,rules_path,catalog_path)}
    rules=json.loads(rules_path.read_text());catalog=json.loads(catalog_path.read_text())['models']
    rows=read_jsonl(input_file);raw_rows=read_jsonl(raw/'listings.jsonl')
    if Counter(r['url'] for r in rows)!=Counter(r['url'] for r in raw_rows):raise ValueError('Snapshot accounting mismatch')
    results=[resolve(row,rules,catalog) for row in rows]
    for result in results:
        result['next_action'] = next_action(result)
    for result in results:result.pop('candidate_duplicate_group',None)
    candidates=defaultdict(list)
    for row in results:
        detail=row['original']['detail'] or {};seller=detail.get('seller_key')
        if row['disposition']=='accepted' and seller and detail.get('description'):
            key=hashlib.sha256(json.dumps([seller,{k:v for k,v in row['clean'].items() if k!='published_at'},
                normalized(detail.get('title')),normalized(detail['description'])],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
            candidates[key].append(row)
    groups=[]
    for key,group in candidates.items():
        if len(group)>1:
            groups.append({'group_id':key,'product_ids':[r['product_id'] for r in group],
                           'meaning':'Possible repeated listing, not confirmed same physical device'})
            for row in group:row['candidate_duplicate_group']=key
    passed=[r for r in results if r['disposition']=='accepted']
    if not all(all(r['clean'].get(k) is not None for k in ('brand','model','storage_gb','price_thb','condition','published_at'))
               and not r['hold_reasons'] and not r['exclusion_reasons'] for r in passed):
        raise ValueError('Accepted row violates required fields or unresolved holds')
    if not all(a['original']==b['original'] for a,b in zip(rows,results)):raise ValueError('Original source changed')
    if before!={str(p.resolve()):sha(p) for p in (input_file,rules_path,catalog_path)} or checksums(raw)!=expected:
        raise ValueError('Inputs changed during finalization')
    output.mkdir(parents=True,exist_ok=True)
    review_output.mkdir(parents=True,exist_ok=True)
    with (review_output/'mac2hand_final.jsonl').open('w',encoding='utf-8') as file:
        for row in results:file.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    write_csv(output/'dataset.csv',passed)
    for disposition in ('excluded','missing_source','non_normal','ambiguous','insufficient_data'):
        write_csv(review_output/(disposition+'.csv'),[r for r in results if r['disposition']==disposition])
    queue_ids={r['product_id'] for r in rows if r['status']=='needs_review' or r.get('manual_review')}
    queue_results=[r for r in results if r['product_id'] in queue_ids]
    write_csv(review_output/'queue_decisions.csv',queue_results)
    dump(review_output/'queue_decisions.json',[{'product_id':r['product_id'],'url':r['url'],'disposition':r['disposition'],
        'hold_reasons':r['hold_reasons'],'exclusion_reasons':r['exclusion_reasons'],
        'resolution':r['resolution'],'next_action':r['next_action'],'manual_review':r.get('manual_review')} for r in queue_results])
    summary={'snapshot':raw.name,'input_records':len(rows),'dispositions':dict(Counter(r['disposition'] for r in results)),
        'original_queue_records':len(queue_results),'queue_dispositions':dict(Counter(r['disposition'] for r in queue_results)),
        'reclassified_prior_accepted':sum(a['status']=='accepted' and b['disposition']!='accepted' for a,b in zip(rows,results)),
        'quarantine_reasons':dict(Counter(reason for r in results if r['disposition'] not in ('accepted','excluded') for reason in r['hold_reasons'])),
        'candidate_duplicate_groups':len(groups),'candidate_duplicate_rows':sum(len(g['product_ids']) for g in groups),
        'all_dates_retained':True,'eda_performed':False,'normal_devices_first':True}
    dump(output/'summary.json',summary);dump(review_output/'candidate_duplicate_groups.json',groups)
    dump(output/'validation.json',{'raw_unchanged':True,'input_files_unchanged':True,'originals_unchanged':True,
        'all_records_accounted_for':len(results)==len(raw_rows),'every_original_queue_row_has_disposition':len(queue_results)==len(queue_ids),
        'accepted_required_fields_present':True,'accepted_no_unresolved_reasons':True})
    dump(output/'run_metadata.json',{'generated_at':datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
        'input_hashes':before,'script_sha256':sha(Path(__file__)),
        'rules_module_sha256':sha(Path(__file__).with_name('resolution_rules.py')),
        'cleaning_helper_sha256':sha(Path(__file__).with_name('clean_mac2hand.py')),'raw':str(raw),
        'output_directories':{'final':str(output),'review':str(review_output)},
        'dataset_sha256':sha(output/'dataset.csv')})
    (output/'rules.json').write_bytes(rules_path.read_bytes());(output/'iphone_model_names.json').write_bytes(catalog_path.read_bytes())
    report=['# ชุดข้อมูล Mac2Hand ล่าสุด','','เริ่มใช้ `dataset.csv` สำหรับ EDA ของกลุ่มปกติ ทุกวันที่ที่เก็บมา ไม่ได้แบ่ง train/test หรือฝึกโมเดล','',
            '| กลุ่ม | จำนวน |','|---|---:|']
    report += [f'| {group} | {count:,} |' for group,count in summary['dispositions'].items()]
    report += ['',f"คิวเดิม {len(queue_results):,} รายการมีผลครบทุกแถว ใช้กฎตรวจหลักฐานทั้งชุดและคำตัดสิน manual ที่บันทึกไว้ ไม่อ้างว่า manual ตรวจทุกแถว",'',
        'dataset และข้อมูลกำกับอยู่ในปลายทาง --output; ข้อมูลทุกแถว คิว และกลุ่มปัญหาอยู่ในปลายทาง --review-output เมื่อแยกขั้น',
        '`mac2hand_final.jsonl` เก็บทุกแถวและต้นฉบับ `queue_decisions.json` เก็บหลักฐานและการตัดสินคิวเดิม',
        'แถวที่ยังขาด/ขัดกันเก็บใน insufficient_data.csv หรือ ambiguous.csv แถวที่ขาดหน้าสินค้าเก็บ missing_source.csv เครื่องเสีย/ล็อก/ต้องศึกษาแยกอยู่ใน non_normal.csv นอกขอบเขตอยู่ใน excluded.csv',
        'ข้อมูลไม่ถูกเดา SE จากวันที่/สี/ความจุ ไม่เลือกหนึ่งค่าให้ประกาศหลายเครื่อง ราคาที่ใช้เป็นราคาผู้ขาย ไม่ใช่ราคาปิดการขาย',
        'ประกาศซ้ำเป็น candidate ที่คำนวณใหม่ในชุดผ่าน เก็บ group ID เพื่อใช้ตรวจและแบ่งข้อมูลภายหลัง ยังไม่ลบเพียงเพราะข้อความคล้ายกัน',
        'สภาพ new/used เป็นช่องผู้ขาย หมายถึงผ่านเกณฑ์ข้อความที่มี ไม่ใช่การตรวจสภาพเครื่องจริง']
    (output/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,default=DEFAULT_RAW)
    parser.add_argument('--input',type=Path,default=BASE/'manual_review/mac2hand_reviewed.jsonl')
    parser.add_argument('--output',type=Path,default=ROOT/'data/final/mac2hand'/DEFAULT_RAW.name)
    parser.add_argument('--review-output',type=Path,help='Review evidence directory; default separates current snapshot, custom --output retains legacy bundle')
    parser.add_argument('--rules',type=Path,default=DEFAULT_RULES)
    parser.add_argument('--catalog',type=Path,default=DEFAULT_CATALOG)
    args=parser.parse_args()
    review_output=args.review_output
    if review_output is None and args.output.resolve()==(ROOT/'data/final/mac2hand'/DEFAULT_RAW.name).resolve():
        review_output=BASE/'finalization'
    finalize(args.raw,args.input,args.output,args.rules,args.catalog,review_output)
