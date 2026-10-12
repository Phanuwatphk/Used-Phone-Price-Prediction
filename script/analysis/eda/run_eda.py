"""Create aggregate EDA reports and private row-review files without changing datasets."""
import argparse
import base64
from collections import Counter
import csv
from datetime import date, datetime
import hashlib
import html
import importlib.metadata
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__:
    from .eda_statistics import analyze
    from .eda_plots import render
else:
    from eda_statistics import analyze
    from eda_plots import render

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = 'ennxo_20261005_mac2hand_20261006'
DEFAULT_INPUT = ROOT / 'data/intermediate/combined' / SNAPSHOT / 'before_selection'
DEFAULT_REPORT = ROOT / 'docs/assets/eda'
DEFAULT_PRIVATE = ROOT / 'data/intermediate/eda' / SNAPSHOT
DEFAULT_DETAILS = ROOT / 'data/intermediate/mac2hand/mac2hand_20261006T172805_252838_Asia-Bangkok/finalization/mac2hand_final.jsonl'
DEFAULT_RULES = ROOT / 'config/shared/eda_rules.json'


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from script.artifacts import collect_output_hashes, read_metadata, write_metadata

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def read_jsonl(path):
    with path.open(encoding='utf-8') as file:
        return [json.loads(line) for line in file if line.strip()]


def write_csv(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else ['no_records'])
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({key: '|'.join(map(str, value)) if isinstance(value, list) else value for key, value in row.items()})


def validate_inputs(rows, lineage, schema):
    if not rows:
        raise ValueError('Dataset is empty')
    if len({r['listing_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate listing identity')
    if {r['source'] for r in rows} != set(schema['sources']):
        raise ValueError('Source coverage differs from merged schema')
    if len(lineage) != len(rows) or len({r['listing_id'] for r in lineage}) != len(rows):
        raise ValueError('Lineage accounting differs')
    if {r['listing_id'] for r in lineage} != {r['listing_id'] for r in rows}:
        raise ValueError('Lineage identities differ')
    for row in rows:
        if any(row.get(field) is None or row.get(field) == '' for field in schema['fields']):
            raise ValueError('Required field missing')
        if row['listing_id'] != f"{row['source']}:{row['product_id']}":
            raise ValueError('Listing key differs from source/product_id')
        if type(row['storage_gb']) is not int or row['storage_gb'] <= 0:
            raise ValueError('Invalid storage')
        if type(row['price_thb']) not in (float, int) or not math.isfinite(row['price_thb']) or row['price_thb'] <= 0:
            raise ValueError('Invalid price')
        date.fromisoformat(row['published_at'])
        if row['condition'] not in schema['conditions']:
            raise ValueError('Invalid seller condition')


def attach_descriptions(rows, lineage, details):
    descriptions = {r['listing_id']: lineage[r['listing_id']]['original_csv_row'].get('description', '') for r in rows}
    if details is None:
        return descriptions
    wanted = {r['product_id']: r for r in rows if r['source'] == 'mac2hand'}
    found = set()
    with details.open(encoding='utf-8') as file:
        for line in file:
            source_row = json.loads(line)
            identifier = source_row['product_id']
            if identifier not in wanted:
                continue
            if identifier in found or source_row['disposition'] != 'accepted':
                raise ValueError('Mac2Hand detail accounting differs')
            merged = wanted[identifier]; original = lineage[merged['listing_id']]['original_csv_row']
            if any(str(source_row['clean'][key]) != original[key] for key in ('brand', 'model', 'condition', 'published_at')):
                raise ValueError('Mac2Hand details do not match source CSV')
            if any(float(source_row['clean'][key]) != float(original[key]) for key in ('storage_gb', 'price_thb')):
                raise ValueError('Mac2Hand detail price/storage differs')
            descriptions[merged['listing_id']] = (source_row['original']['detail'] or {}).get('description', '')
            found.add(identifier)
    if found != set(wanted):
        raise ValueError('Missing accepted Mac2Hand descriptions')
    return descriptions


def table_markdown(rows, fields, labels=None):
    labels = labels or fields
    lines = ['| ' + ' | '.join(labels) + ' |', '|' + '|'.join('---' for _ in fields) + '|']
    for row in rows:
        values = []
        for field in fields:
            value = row.get(field)
            values.append(f'{value:,.2f}' if isinstance(value, float) else str(value if value is not None else 'NA'))
        lines.append('| ' + ' | '.join(values) + ' |')
    return '\n'.join(lines)


def body_html(body):
    """Render the small Markdown subset generated by this report into real HTML tables."""
    result = []
    for block in body.split('\n\n'):
        lines = block.splitlines()
        if lines and all(line.startswith('|') for line in lines):
            cells = lambda line: [html.escape(value.strip()) for value in line.strip('|').split('|')]
            heading = '<tr>' + ''.join('<th>' + cell + '</th>' for cell in cells(lines[0])) + '</tr>'
            rows = ['<tr>' + ''.join('<td>' + cell + '</td>' for cell in cells(line)) + '</tr>' for line in lines[2:]]
            result.append('<div class="table-scroll"><table><thead>' + heading + '</thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
        elif lines and all(line.startswith('- ') for line in lines):
            result.append('<ul>' + ''.join('<li>' + html.escape(line[2:]) + '</li>' for line in lines) + '</ul>')
        else:
            result.append('<p>' + '<br>'.join(html.escape(line) for line in lines) + '</p>')
    return '\n'.join(result)


def make_reports(summary, figures, report):
    total = summary['records']; apple = summary['brand_counts'].get('Apple', 0)
    outlier = summary['outlier_screening']; duplicate = summary['duplicate_screening']
    source_table = table_markdown(summary['source_statistics'], ['source', 'n', 'percent', 'median', 'date_min', 'date_max'],
                                 ['เว็บ', 'แถว', 'สัดส่วน (%)', 'median ราคา (บาท)', 'วันแรก', 'วันสุดท้าย'])
    old = sum(n for year, n in summary['publication_year_counts'].items() if int(year) < 2024)
    rare = summary['rare_brand_model_pairs']
    combined = summary['combined_price_statistics']
    findings = [f"ชุดรวม {total:,} แถว คอลัมน์หลักครบและมี source ทุกแถว ราคา median {combined['median']:,.0f} บาท (Q1 {combined['q1']:,.0f}; Q3 {combined['q3']:,.0f}) สำรวจทุกวันที่ ไม่มีการตัดช่วง 12 เดือน",
        f"Apple {apple:,} แถว ({apple/total:.2%}) มีรุ่น/ยี่ห้อ {summary['unique_brand_model_pairs']:,} คู่ โดย {rare:,} คู่มีน้อยกว่า 10 แถว ไม่ควรสรุปประสิทธิภาพรุ่นที่มีตัวอย่างน้อยจากภาพรวม",
        f"ข้อมูลก่อนปี 2024 มี {old:,} แถว ({old/total:.2%}) ช่วงเวลาของสองเว็บต่างกัน จึงไม่เปรียบเทียบ median รวมเป็นผลของเว็บโดยตรง",
        f"สภาพ used {summary['condition_counts'].get('used',0):,} และ new {summary['condition_counts'].get('new',0):,} เป็นช่องผู้ขาย ไม่ใช่ผลตรวจเครื่องจริง",
        f"IQR ภายในเว็บ/รุ่น/ความจุ/สภาพ/ปี ระบุ {outlier['flagged_rows']:,} แถวจากกลุ่มที่ประเมินได้ {outlier['eligible_rows']:,} แถว เป็นสัญญาณตรวจ ไม่ใช่ข้อยืนยันว่าราคาผิด",
        f"candidate จากข้อความมี {duplicate['text_components']:,} components รวม {duplicate['text_component_rows']:,} แถว หลังรวมกลุ่มที่ซ้อนกัน; สัญญาณภาพซ้ำแยกไว้ เพราะอาจเป็นรูปตัวอย่างร้าน",
        f"ตรวจข้อความจาก {duplicate['descriptions_available']:,} แถว พบกลุ่มข้อความตรงกันข้ามเว็บ {duplicate['cross_source_groups']:,} กลุ่ม วิธีนี้ไม่ครอบคลุมข้อความที่แก้คำหรือรูปที่ใช้ URL ต่างกัน",
        f"กลุ่มรุ่น/ความจุ/สภาพ/ปีที่มีอย่างน้อย 3 แถวต่อเว็บสำหรับเทียบ median มี {summary['matched_source_comparison_groups']:,} กลุ่ม รวม {summary['matched_source_comparison_records']:,} แถว ไม่ใช่การทดลองควบคุมสภาพเครื่องหรือผู้ขาย"]
    next_steps = [
        'ตรวจ outlier และตัวอย่างราคาสูงจากข้อความต้นทาง ยืนยันราคาขายเต็มก่อนแก้; ใช้ไฟล์ price_extremes.csv ร่วมด้วย เพราะกลุ่มเล็กหรือ IQR=0 อาจไม่ถูก flag',
        'ทบทวน candidate ซ้ำก่อนกำหนดกลุ่ม split ไม่ถือว่ารูป/ข้อความเหมือนกันแปลว่าเครื่องเดียวกัน ถ้ายืนยันเป็นเครื่องเดียวให้ใช้ group เดียวทั้ง train/test',
        'กำหนดเป้าหมายราคาตามวันประกาศหรือราคาปัจจุบันให้ชัด เลือกแผนประเมินตามเวลา และรายงานผลแยกเว็บ/รุ่นที่มีตัวอย่างพอ',
        'หลังแบ่งข้อมูล ให้เรียนรู้กฎ preprocessing/threshold ที่ใช้ฝึกจาก train เท่านั้น ไม่ใช้ fence จาก EDA ทั้งชุดตัดข้อมูล test']
    brief = ['# สรุป EDA ชุดรวม', '', source_table, '', *['- ' + point for point in findings[:6]], '',
             'อ่าน [รายงานรายละเอียด](metadata.json#report_text) หรือเปิด `report.html` ใน browser กราฟอยู่ใน `figures/` ตารางสรุปอยู่ใน `tables/`', '',
             'dataset ไม่เปลี่ยน ยังไม่ลบ candidate/outlier ไม่แบ่งข้อมูลหรือฝึกโมเดล']
    sensitivity_labels = {'all_rows': 'ทุกแถว', 'without_iqr_flags_diagnostic_only': 'สมมติพักแถวที่ IQR flag',
                          'one_per_text_candidate_component_assumption_only': 'สมมติเก็บ 1 แถวต่อกลุ่มข้อความ'}
    sensitivity_display = [{**row, 'scenario': sensitivity_labels[row['scenario']]} for row in summary['sensitivity']]
    sections = [('ข้อมูลและคุณภาพ', '\n\n'.join(findings[:4]) + '\n\n' + source_table),
        ('ราคาและ outlier', '\n\n'.join([findings[4],
            f"ข้ามกลุ่มเล็ก {outlier['skipped_small_group_rows']:,} แถว และกลุ่ม IQR=0 {outlier['skipped_zero_iqr_rows']:,} แถว จึงไม่ควรตีความว่าแถวที่ไม่ถูก flag ทุกแถวได้รับการยืนยัน",
            'ราคาเป็นราคาตั้งขาย ไม่ใช่ราคาปิดการขาย ตรวจราคาที่มีข้อมูลดาวน์/ผ่อนและราคาอาจพิมพ์ผิดจากหลักฐานเดิม แต่ไม่เดาราคาทดแทนเอง'])),
        ('ความสัมพันธ์และความต่างระหว่างเว็บ', findings[7] + '\n\n' + table_markdown(summary['correlations'],
            ['source', 'n', 'price_vs_storage_spearman', 'price_vs_publication_year_spearman'],
            ['เว็บ', 'แถว', 'Spearman ราคา–ความจุ', 'Spearman ราคา–ปีประกาศ']) +
            '\n\nSpearman ใช้ average ranks เมื่อค่าซ้ำ ไม่มีการทดสอบนัยสำคัญ ค่าเหล่านี้ปะปนรุ่น/สภาพ/ปี ไม่ใช่ผลเชิงเหตุและผล โดยเฉพาะความจุสูงมักอยู่ในรุ่นใหม่กว่า'),
        ('ประกาศที่อาจซ้ำ', findings[5] + '\n\n' + findings[6] +
            '\n\nจำนวนกลุ่มแยกวิธี: ' + ', '.join(f'{method} {count:,}' for method, count in duplicate['method_group_counts'].items()) +
            ' กลุ่มระหว่างวิธีซ้อนกันได้ จึงบวกแทนจำนวนเครื่องไม่ได้' +
            '\n\nใช้ candidate เดิมของแต่ละเว็บ และข้อความที่ normalize Unicode/case/ช่องว่างตรงกันอย่างน้อย 80 ตัวอักษร พร้อมยี่ห้อ รุ่น ความจุ สภาพและราคาเดียวกัน ไม่ใช้การเหมือนฟีเจอร์อย่างเดียวเป็นหลักฐานเครื่องซ้ำ ไม่รวมภาพซ้ำเข้ากลุ่มข้อความ'),
        ('Sensitivity analysis', table_markdown(sensitivity_display, ['scenario', 'n', 'excluded_n', 'median', 'mean'],
            ['กรณีสมมติ', 'แถว', 'พักในสมมติฐาน', 'median ราคา', 'mean ราคา']) +
            '\n\nเป็นการคำนวณเชิงสมมติเพื่อดูการเปลี่ยนสถิติ ไม่สร้าง dataset ที่ลบแถว ไม่สรุปว่า candidate คือเครื่องซ้ำจริง การจำลองเลือก key แรกใน component ตาม listing_id'),
        ('ข้อจำกัดและงานถัดไป', '\n\n'.join('- ' + point for point in next_steps) +
            '\n\nไม่มี battery health อายุเครื่อง ประวัติซ่อมที่ผ่านการตรวจจริง หรือราคาปิดขายใน schema นี้ การขาดข้อมูลส่วนนี้ไม่ใช่ missing ในช่องที่มี แต่เป็นข้อจำกัดตัวแปรของโครงการ')]
    details = ['# รายงาน EDA ชุดรวม', '', 'สำรวจหลัง clean และรวม schema ก่อนแบ่ง train/test ใช้ทุกแถวใน snapshot ไม่เปลี่ยนข้อมูลต้นทาง', '']
    for title, body in sections:
        details += ['## ' + title, '', body, '']
    details += ['## กราฟ', '']
    for item in figures:
        details += [f"![{item['name']}](figures/{item['name']}.png)", '', item['caption'], '']
    details += ['## ไฟล์ประกอบรายงาน', '',
        '`metadata.json` รวม summary (สถิติ), rules (กฎ), provenance (เวอร์ชันโค้ด dependencies/input hashes) และ validation; `tables/*.csv` เก็บทุกรุ่น/ปี/ความจุและวิธีเทียบเว็บ', '',
        'รายการรายแถวอยู่ใน `data/intermediate/eda/ennxo_20261005_mac2hand_20261006/` ได้แก่ `outlier_candidates.csv`, `duplicate_groups.json`, `duplicate_memberships.csv` และ `metadata.json#validation` เก็บเฉพาะเครื่อง; รายงานนี้ไม่เผยแพร่ข้อความ/ข้อมูลติดต่อจากประกาศ']
    markdown = '\n'.join(details) + '\n'
    if report.resolve() == DEFAULT_REPORT.resolve():
        document_path = ROOT / 'docs/eda.md'
        markdown = markdown.replace('](figures/', '](assets/eda/figures/')
        registry_path = ROOT / 'data/datasets.json'
        if registry_path.exists():
            registry = json.loads(registry_path.read_text(encoding='utf-8'))
            current = registry.get('model_input_dataset')
            if current:
                status = (f"รายงานนี้สำรวจ {total:,} แถวก่อนคัด ชุดใช้งานปัจจุบันมี {current['records']:,} แถว "
                          "อ่าน [ขั้นตอนคัดข้อมูล](data.md#stage-model_input) และ [ผลโมเดล](modeling.md) "
                          "คิว EDA เดิมปิดแล้ว ข้อเสนอในรายงานเป็นบันทึก ณ รอบสำรวจ ไม่ใช่คิวที่ต้องทำต่อ")
                title, body = markdown.split('\n', 1)
                markdown = title + '\n\n' + status + '\n' + body
        # Preserve the authored methodology when refreshing the numerical report.
        marker = '<a id="stage-eda"></a>'
        if document_path.exists():
            existing = document_path.read_text(encoding='utf-8')
            if marker in existing:
                markdown = markdown.rstrip() + '\n\n' + marker + existing.split(marker, 1)[1]
        document_path.write_text(markdown, encoding='utf-8')
    else:
        write_metadata(report, 'report_text', markdown)
    document = ['<!doctype html><html lang="th"><meta charset="utf-8">', '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>EDA ชุดรวมมือถือ</title><style>body{font:16px/1.65 system-ui,sans-serif;max-width:1080px;margin:auto;padding:32px;color:#223}h1,h2{line-height:1.3}img{max-width:100%;height:auto}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;text-align:left;border-bottom:1px solid #ddd}th{background:#f5f7fa}figure{margin:28px 0}figcaption{color:#456}@media print{body{padding:0}figure{break-inside:avoid}}</style>',
        '<h1>รายงาน EDA ชุดรวม</h1><p>อ่านประกอบรายงาน Markdown และตาราง CSV; ทุกกราฟสร้างจาก snapshot เดียวกัน ไม่มีการลบแถว</p>']
    for title, body in sections:
        document.append(f'<h2>{html.escape(title)}</h2>' + body_html(body))
    for item in figures:
        encoded = base64.b64encode((report / 'figures' / (item['name'] + '.png')).read_bytes()).decode()
        document.append(f'<figure><img alt="{html.escape(item["caption"])}" src="data:image/png;base64,{encoded}"><figcaption>{html.escape(item["caption"])}</figcaption></figure>')
    document.append('</html>')
    (report / 'report.html').write_text('\n'.join(document), encoding='utf-8')


def run(input_dir, report, private, rules_path=DEFAULT_RULES, details=None, evidence_dir=None):
    input_dir, report, private, rules_path = [p.resolve() for p in (input_dir, report, private, rules_path)]
    evidence_dir = evidence_dir.resolve() if evidence_dir is not None else input_dir
    details = details.resolve() if details is not None else None
    if report == private or report in private.parents or private in report.parents:
        raise ValueError('Public report and private review outputs overlap')
    input_files = sorted(p for p in input_dir.iterdir() if p.is_file()) + [rules_path]
    input_files += [p for p in sorted(evidence_dir.iterdir()) if p.is_file() and p not in input_files]
    if details is not None:
        input_files.append(details)
    for output in (report, private):
        for protected in [*input_files, ROOT / 'data/raw', ROOT / 'config']:
            if output == protected or protected in output.parents or output in protected.parents:
                raise ValueError('Output overlaps a protected input')
    before = {str(p): sha(p) for p in input_files}
    schema = read_metadata(input_dir, 'schema'); rules = json.loads(rules_path.read_text())
    if rules['version'] != 1 or rules['outlier_min_group_size'] < 4 or rules['outlier_iqr_multiplier'] <= 0:
        raise ValueError('Unsupported EDA rules')
    if sha(input_dir / 'dataset.csv') != read_metadata(input_dir, 'provenance')['dataset_sha256']:
        raise ValueError('Merged CSV differs from recorded hash')
    rows = read_jsonl(input_dir / 'dataset.jsonl'); original_lineage = read_jsonl(evidence_dir / 'lineage.jsonl')
    validate_inputs(rows, original_lineage, schema)
    with (input_dir / 'dataset.csv').open(encoding='utf-8-sig', newline='') as file:
        csv_rows = list(csv.DictReader(file))
    if len(csv_rows) != len(rows) or any(any(str(r[k]) != c[k] for k in schema['fields']) for r, c in zip(rows, csv_rows)):
        raise ValueError('Typed JSONL differs from merged CSV')
    if len(rows) != read_metadata(input_dir, 'summary')['records']:
        raise ValueError('Merged count differs from summary')
    lineage = {r['listing_id']: r for r in original_lineage}
    descriptions = attach_descriptions(rows, lineage, details)
    enriched = [{**r, 'publication_year': date.fromisoformat(r['published_at']).year} for r in rows]
    summary, tables, flags, groups, components = analyze(enriched, lineage, descriptions, rules)
    model_counts = Counter((r['brand'], r['model']) for r in rows)
    summary['rare_brand_model_pairs'] = sum(n < 10 for n in model_counts.values())
    report.mkdir(parents=True, exist_ok=True); private.mkdir(parents=True, exist_ok=True)
    (report / 'tables').mkdir(exist_ok=True)
    for name, table in tables.items():
        write_csv(report / 'tables' / (name + '.csv'), table)
    outlier_fields = list(enriched[0]) + ['peer_n', 'peer_median', 'lower_fence', 'upper_fence', 'direction', 'next_action']
    write_csv(private / 'outlier_candidates.csv', flags, outlier_fields)
    dump(private / 'duplicate_groups.json', groups); dump(private / 'text_candidate_components.json', components)
    memberships = [{'listing_id': identifier, 'group_id': group['group_id'], 'method': group['method'],
                    'cross_source': group['cross_source'], 'physical_identity_confirmed': False}
                   for group in groups for identifier in group['listing_ids']]
    write_csv(private / 'duplicate_memberships.csv', memberships,
              ['listing_id', 'group_id', 'method', 'cross_source', 'physical_identity_confirmed'])
    if (evidence_dir / 'price_review.csv').exists():
        (private / 'price_extremes.csv').write_bytes((evidence_dir / 'price_review.csv').read_bytes())
    figures = render(enriched, tables, report / 'figures', rules)
    write_metadata(report, 'summary', summary); write_metadata(report, 'rules', rules)
    make_reports(summary, figures, report)
    after = {str(p): sha(p) for p in input_files}
    if after != before:
        raise ValueError('EDA inputs changed during analysis')
    validation = {'input_files_unchanged': True, 'csv_jsonl_consistent': True,
        'lineage_for_every_row': True, 'dataset_records': len(rows),
        'sources_verified': sorted({r['source'] for r in rows}),
        'outlier_rows_accounted_for': sum(summary['outlier_screening'][key] for key in
            ('eligible_rows', 'skipped_small_group_rows', 'skipped_zero_iqr_rows')) == len(rows),
        'row_data_not_in_public_tables': all(not any(key in row for key in ('listing_id', 'url', 'description', 'title')) for table in tables.values() for row in table)}
    if not validation['outlier_rows_accounted_for'] or not validation['row_data_not_in_public_tables']:
        raise ValueError('EDA output accounting failed')
    write_metadata(private, 'validation', validation)
    write_metadata(report, 'validation', validation)
    write_metadata(report, 'provenance', {'generated_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
        'input_hashes': {str(Path(p).relative_to(ROOT)) if Path(p).is_relative_to(ROOT) else p: h for p, h in before.items()},
        'code_hashes': {p.name: sha(p) for p in (Path(__file__), Path(__file__).with_name('eda_statistics.py'), Path(__file__).with_name('eda_plots.py'))},
        'dependencies': {name: importlib.metadata.version(name) for name in ('matplotlib', 'numpy')},
        'rows': len(rows), 'figures': figures, 'input_files_unchanged': True})
    write_metadata(report, 'hashes', collect_output_hashes(report))
    if report == DEFAULT_REPORT.resolve():
        hashes = read_metadata(report, 'hashes')
        hashes['../../eda.md'] = sha(ROOT / 'docs/eda.md')
        write_metadata(report, 'hashes', hashes)
    print(json.dumps({'records': len(rows), 'outlier_screening': summary['outlier_screening'],
        'duplicate_screening': summary['duplicate_screening'], 'matched_source_comparison_groups': len(tables['source_comparisons']),
        'report': str(report), 'private_review': str(private)}, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, help='Lineage/audit directory; custom --input defaults to its original bundle')
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--report', type=Path, default=DEFAULT_REPORT)
    parser.add_argument('--private-output', type=Path, default=DEFAULT_PRIVATE)
    parser.add_argument('--rules', type=Path, default=DEFAULT_RULES)
    parser.add_argument('--mac2hand-details', type=Path, default=DEFAULT_DETAILS)
    parser.add_argument('--without-mac2hand-details', action='store_true', help='Use CSV lineage only; report reduced text coverage explicitly')
    args = parser.parse_args()
    evidence = args.evidence
    if evidence is None and args.input.resolve() == DEFAULT_INPUT.resolve():
        evidence = ROOT / 'data/intermediate/combined' / SNAPSHOT / 'audit'
    run(args.input, args.report, args.private_output, args.rules,
        None if args.without_mac2hand_details else args.mac2hand_details, evidence)
