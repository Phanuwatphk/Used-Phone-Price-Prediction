"""Refresh aggregate EDA for the published model input, without raw/private data."""
from collections import Counter
import csv
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if not __package__:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from script.artifacts import collect_output_hashes, write_metadata
from script.modeling.split_dataset import read_dataset, sha, write_csv
from script.modeling.common import table


START = '<!-- model-input-eda:start -->'
END = '<!-- model-input-eda:end -->'


def replace_section(text, block):
    if START in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        return before + block + after
    title, rest = text.split('\n', 1)
    return title + '\n\n' + block + '\n' + rest


def refresh():
    report = ROOT / 'docs/assets/eda'
    core = ROOT / 'data/final/dataset.csv'
    sidecar = ROOT / 'data/final/condition_features.csv'
    before = {str(path.relative_to(ROOT)): sha(path) for path in (core, sidecar)}
    rows = read_dataset(core)
    with sidecar.open(encoding='utf-8', newline='') as handle:
        extra = list(csv.DictReader(handle))
    index = {row['listing_id']: row for row in extra}
    if len(index) != len(extra) or set(index) != {row['listing_id'] for row in rows}:
        raise ValueError('Condition feature identities differ from the published dataset')
    counts = Counter((row['brand'], row['model']) for row in rows)
    used_rows = [row for row in rows if row['condition'] == 'used']
    used_counts = Counter((row['brand'], row['model']) for row in used_rows)
    used_apple = sum(row['brand'] == 'Apple' for row in used_rows)
    coverage = []
    fields = ['battery_health_pct', 'warranty_days', 'box_mentioned']
    for scope, scoped_rows in [('published_core', rows), ('used_training', used_rows)]:
        for source in ['combined', 'ennxo', 'mac2hand']:
            group = scoped_rows if source == 'combined' else [row for row in scoped_rows if row['source'] == source]
            for field in fields:
                values = [float(index[row['listing_id']][field]) for row in group if index[row['listing_id']][field] != '']
                coverage.append({'scope': scope, 'source': source, 'feature': field, 'total': len(group), 'known': len(values),
                                 'missing': len(group) - len(values), 'known_pct': 100 * len(values) / len(group),
                                 'minimum': min(values) if values else '',
                                 'median': float(np.median(values)) if values else '',
                                 'maximum': max(values) if values else ''})
    year_counts = Counter((row['published_at'][:4], row['source']) for row in rows)
    years = sorted({year for year, source in year_counts})
    yearly = [{'year': year, 'ennxo': year_counts[(year, 'ennxo')], 'mac2hand': year_counts[(year, 'mac2hand')]}
              for year in years]
    used_year_counts = Counter((row['published_at'][:4], row['source']) for row in used_rows)
    for row in yearly:
        row.update({f'used_{source}': used_year_counts[(row['year'], source)] for source in ['ennxo', 'mac2hand']})
    support = []
    for brand, model in sorted(counts):
        group = [row for row in rows if (row['brand'], row['model']) == (brand, model)]
        used = [row for row in group if row['condition'] == 'used']
        support.append({'brand': brand, 'model': model, 'rows': len(group), 'used_rows': len(used),
                        'latest': max(row['published_at'] for row in group),
                        'latest_used': max((row['published_at'] for row in used), default='')})
    tables = report / 'tables'
    tables.mkdir(exist_ok=True)
    write_csv(tables / 'model_input_optional_coverage.csv', coverage)
    write_csv(tables / 'model_input_year_source.csv', yearly)
    write_csv(tables / 'model_input_model_support.csv', support)
    combined = [row for row in coverage if row['source'] == 'combined' and row['scope'] == 'published_core']
    used_combined = [row for row in coverage if row['source'] == 'combined' and row['scope'] == 'used_training']
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    labels = ['Battery health', 'Warranty days', 'Box claim']
    axes[0].barh(labels, [row['known_pct'] for row in used_combined])
    axes[0].set_xlim(0, 100)
    axes[0].set_xlabel('Used-only training input with a known value (%)')
    for i, row in enumerate(used_combined):
        axes[0].text(row['known_pct'] + 1, i, f"{row['known']:,} / {len(used_rows):,}", va='center')
    x = np.arange(len(years))
    mac = [row['used_mac2hand'] for row in yearly]
    axes[1].bar(x, mac, label='Mac2Hand')
    axes[1].bar(x, [row['used_ennxo'] for row in yearly], bottom=mac, label='ENNXO')
    axes[1].set_xticks(x, years, rotation=60)
    axes[1].set_ylabel('Used-only training listings')
    axes[1].legend()
    fig.tight_layout()
    figure = report / 'figures/model_input_coverage.png'
    fig.savefig(figure, dpi=160)
    plt.close(fig)
    total = len(rows)
    apple = sum(row['brand'] == 'Apple' for row in rows)
    old = sum(row['published_at'] < '2024-01-01' for row in rows)
    conditions = Counter(row['condition'] for row in rows)
    optional_table = table(['ข้อมูล', 'มีค่าในชุดเผยแพร่', 'มีค่าในชุดมือสอง', 'ไม่ทราบในชุดมือสอง', 'มีค่าในชุดมือสอง (%)'],
                           [[label, f"{core_item['known']:,}", f"{item['known']:,}", f"{item['missing']:,}", f"{item['known_pct']:.2f}"]
                            for label, core_item, item in zip(['สุขภาพแบตเตอรี่', 'ประกันเหลือ', 'กล่อง'], combined, used_combined)])
    summary = {'records': total, 'training_records': len(used_rows), 'condition_counts': dict(conditions), 'apple_rows': apple,
               'training_apple_rows': used_apple, 'training_models': len(used_counts),
               'training_models_under_10_rows': sum(n < 10 for n in used_counts.values()),
               'pre_2024_rows': old, 'models': len(counts), 'models_under_10_rows': sum(n < 10 for n in counts.values()),
               'optional_coverage': coverage, 'input_hashes': before,
               'updated_on': date(2026, 10, 15).isoformat(), 'dataset_modified': False}
    block = f'''{START}
## ข้อมูลที่ใช้ฝึกโมเดลปัจจุบัน

ส่วนนี้คำนวณจากข้อมูลเผยแพร่ {total:,} แถว หลังคัดคิวเดิม 822 แถวออก และแยกชุดฝึกเฉพาะมือสอง {len(used_rows):,} แถว ส่วน EDA ด้านล่างเป็นประวัติการสำรวจชุดก่อนคัด 10,032 แถว จึงมีจำนวนต่างกัน รอบนี้ไม่ลบข้อมูลต้นฉบับหรือคัดเพิ่มตามราคา

ชุดเผยแพร่มี Apple {apple:,} แถว ({apple/total:.2%}) และรุ่น/ยี่ห้อ {len(counts):,} คู่ โดย {summary['models_under_10_rows']:,} คู่มีน้อยกว่า 10 ประกาศ ข้อมูลก่อนปี 2024 มี {old:,} แถว ({old/total:.2%}) ส่วนชุดฝึกมือสองมี Apple {used_apple:,}/{len(used_rows):,} แถว ({used_apple/len(used_rows):.2%}) และ {len(used_counts):,} รุ่น/ยี่ห้อ โดย {summary['training_models_under_10_rows']:,} คู่มีน้อยกว่า 10 ประกาศ คะแนนรวมจึงไม่รับรองทุกรุ่นหรือทุกยี่ห้อ และราคาข้อมูลเก่าไม่ใช่ราคาตลาดปัจจุบันโดยตรง

`condition` มีครบทุกแถว: used {conditions['used']:,} / new {conditions['new']:,} เป็นประเภทที่ผู้ขายเลือก ไม่ใช่เกรดรอยตำหนิ โมเดลรอบนี้ฝึกเฉพาะ used ให้ตรงโจทย์ ส่วน new ยังคงอยู่ในชุดเผยแพร่ condition จึงใช้กรองขอบเขตและตรวจสอบ ไม่ใช้เป็นฟีเจอร์เพราะค่าคงที่ในชุดฝึก เครื่องที่เสีย/ล็อกไม่อยู่ในขอบเขต

{optional_table}

ค่าขาดหายคงเป็นไม่ทราบ แยกจากแบตเตอรี่ 0% ประกัน 0 วัน และไม่มีกล่อง ไม่มีการเติมข้อมูลลง dataset ให้ดูเหมือนครบ การเติมค่าที่จำเป็นในโมเดลเรียนรู้จาก train ของแต่ละ fold เท่านั้น ตรวจความครอบคลุมแยกเว็บและช่วงค่าได้ใน [ตารางข้อมูลเพิ่มเติม](assets/eda/tables/model_input_optional_coverage.csv)

ข้อมูลประกันยังเก็บใน sidecar แต่ไม่ใช้ในโมเดล V2เนื่องจากมีคำกล่าวอ้างชัดเจนน้อยมาก ไม่สรุปว่าประกันไม่มีผลต่อราคาจริง ข้อมูลรอยตำหนิ ประวัติซ่อม และอายุเครื่องจริงยังไม่มีคอลัมน์ที่ผ่านการตรวจพร้อมฝึก

![ความครอบคลุมข้อมูลฝึกและช่วงปี](assets/eda/figures/model_input_coverage.png)

เว็บไซต์ต้นทางเก็บเพื่อที่มาและประเมินผลแยกกลุ่ม ไม่ใช่คุณสมบัติเครื่อง ความต่างของราคาสองเว็บอาจมาจากรุ่น ปี และผู้ขายที่ต่างกัน การถอด source ไม่ได้ทำให้ข้อมูลสมดุลหรือกำจัดอคติทั้งหมด โดยเฉพาะรูปแบบการขาดข้อมูลที่อาจต่างกันตามเว็บ

การคัด outlier เดิมเกิดก่อนแบ่งข้อมูลและเคยเปิดดูชุดประเมินแล้ว จึงยังมี selection bias ผลโมเดลต้องเรียกการประเมินย้อนหลัง ไม่อ้างว่าเป็นผลทดสอบอิสระ การสำรวจครั้งนี้เพิ่มคำอธิบายและตาราง ไม่ใช้ราคาชุดประเมินย้อนหลังเลือกฟีเจอร์เพิ่ม

รายละเอียดประกอบ: [จำนวนและวันที่แยกรุ่น](assets/eda/tables/model_input_model_support.csv), [จำนวนประกาศแยกปีและเว็บ](assets/eda/tables/model_input_year_source.csv), [ผลทดลองฟีเจอร์และคำอธิบายโมเดล](modeling.md)
{END}'''
    document = ROOT / 'docs/eda.md'
    document.write_text(replace_section(document.read_text(encoding='utf-8'), block), encoding='utf-8')
    # Keep the downloadable HTML consistent with the current-data section.
    from script.modeling.model_v2.report_improved import html_export
    html_block = block.replace('assets/eda/figures/', 'figures/')
    rendered = html_export(html_block, report)
    rendered = rendered.split('<body>', 1)[1].split('</body>', 1)[0]
    rendered = START + rendered.replace(START, '').replace(END, '') + END
    html_path = report / 'report.html'
    original = html_path.read_text(encoding='utf-8')
    if START in original:
        before_html, rest = original.split(START, 1)
        _, after_html = rest.split(END, 1)
        original = before_html + rendered + after_html
    else:
        original = original.replace('<h1>รายงาน EDA ชุดรวม</h1>', '<h1>รายงาน EDA ชุดรวม</h1>' + rendered, 1)
    html_path.write_text(original, encoding='utf-8')
    write_metadata(report, 'model_input', summary)
    after = {str(path.relative_to(ROOT)): sha(path) for path in (core, sidecar)}
    if before != after:
        raise ValueError('Published EDA inputs changed')
    hashes = collect_output_hashes(report)
    hashes['../../eda.md'] = sha(document)
    write_metadata(report, 'hashes', hashes)
    print(f'Refreshed current model-input EDA: {total:,} rows; inputs unchanged')
    return summary


if __name__ == '__main__':
    refresh()
