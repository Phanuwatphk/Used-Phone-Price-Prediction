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
    rows = [row for row in rows if row['condition'] == 'used']
    counts = Counter((row['brand'], row['model']) for row in rows)
    used_rows = rows
    used_counts = Counter((row['brand'], row['model']) for row in used_rows)
    used_apple = sum(row['brand'] == 'Apple' for row in used_rows)
    coverage = []
    fields = ['battery_health_pct', 'warranty_days', 'box_mentioned']
    for scope, scoped_rows in [('used_training', used_rows)]:
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
    used_combined = [row for row in coverage if row['source'] == 'combined' and row['scope'] == 'used_training']
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    labels = ['Battery health', 'Warranty days', 'Box claim']
    axes[0].barh(labels, [row['known_pct'] for row in used_combined])
    axes[0].set_xlim(0, 100)
    axes[0].set_xlabel('Selected training input with a known value (%)')
    for i, row in enumerate(used_combined):
        axes[0].text(row['known_pct'] + 1, i, f"{row['known']:,} / {len(used_rows):,}", va='center')
    x = np.arange(len(years))
    mac = [row['used_mac2hand'] for row in yearly]
    axes[1].bar(x, mac, label='Mac2Hand')
    axes[1].bar(x, [row['used_ennxo'] for row in yearly], bottom=mac, label='ENNXO')
    axes[1].set_xticks(x, years, rotation=60)
    axes[1].set_ylabel('Selected training listings')
    axes[1].legend()
    fig.tight_layout()
    figure = report / 'figures/model_input_coverage.png'
    fig.savefig(figure, dpi=160)
    plt.close(fig)
    total = len(rows)
    apple = sum(row['brand'] == 'Apple' for row in rows)
    old = sum(row['published_at'] < '2024-01-01' for row in rows)
    conditions = Counter(row['condition'] for row in rows)
    optional_table = table(['ข้อมูล', 'มีค่าในชุดฝึก', 'ไม่ทราบ', 'ความครอบคลุม (%)', 'ใช้ในโมเดล'],
        [[label, f"{item['known']:,}", f"{item['missing']:,}", f"{item['known_pct']:.2f}", use]
         for label, item, use in zip(['สุขภาพแบตเตอรี่', 'ประกันเหลือ', 'กล่อง'],
                                    used_combined, ['ใช้', 'ไม่ใช้', 'ใช้'])])
    source_table = table(['เว็บไซต์', 'จำนวนประกาศ', 'มัธยฐานราคา (บาท)', 'ช่วงวันประกาศ'],
        [[source, f"{len(group):,}",
          f"{np.median([float(row['price_thb']) for row in group]):,.0f}",
          min(row['published_at'] for row in group) + ' ถึง ' + max(row['published_at'] for row in group)]
         for source in ['ennxo', 'mac2hand']
         for group in [[row for row in rows if row['source'] == source]]])
    prices = [float(row['price_thb']) for row in rows]
    summary = {'records': total, 'training_records': len(used_rows), 'condition_counts': dict(conditions), 'apple_rows': apple,
               'condition_interpretation': 'Seller-declared condition, not independently inspected. This report describes the current training scope.',
               'training_apple_rows': used_apple, 'training_models': len(used_counts),
               'training_models_under_10_rows': sum(n < 10 for n in used_counts.values()),
               'pre_2024_rows': old, 'models': len(counts), 'models_under_10_rows': sum(n < 10 for n in counts.values()),
               'optional_coverage': coverage, 'input_hashes': before,
               'updated_on': date(2026, 10, 15).isoformat(), 'dataset_modified': False}
    document = ROOT / 'docs/eda.md'
    markdown = f'''# การวิเคราะห์ข้อมูลเชิงสำรวจ (EDA)

หนึ่งแถวแทนหนึ่งประกาศจาก ENNXO หรือ Mac2Hand ราคาเป็นราคาตั้งขาย หน่วยบาท

## 1. ขอบเขตข้อมูล

ใช้ข้อมูลมือถือมือสองที่ผ่านการทำความสะอาดและคัดเลือกสำหรับฝึก V2 จำนวน **{len(used_rows):,} ประกาศ**

สถิติชุดปัจจุบันคำนวณจากข้อมูลที่ใช้ฝึก V2 สภาพเป็นข้อมูลจากผู้ขาย ไม่ใช่ผลตรวจเครื่องจริง และไม่ใช้เป็นฟีเจอร์ในรอบนี้

## 2. การกระจายชุดข้อมูลปัจจุบัน

{source_table}

| ตัวชี้วัด | ชุดฝึก {len(used_rows):,} แถว |
|---|---:|
| Apple | {used_apple:,} ({used_apple/len(used_rows):.2%}) |
| คู่ยี่ห้อ–รุ่น | {len(used_counts):,} |
| คู่ยี่ห้อ–รุ่นที่มีน้อยกว่า 10 ประกาศ | {summary['training_models_under_10_rows']:,} |
| ประกาศก่อนปี 2024 | {old:,} ({old/total:.2%}) |

ราคาชุดฝึก: มัธยฐาน **{np.median(prices):,.0f} บาท**; Q1–Q3 **{np.percentile(prices,25):,.0f}–{np.percentile(prices,75):,.0f} บาท** ข้อมูลกระจุกตัวใน Apple และประกาศเก่า จึงไม่เป็นตัวแทนตลาดปัจจุบันทุกยี่ห้อ

## 3. ความครบถ้วนของข้อมูลประกอบ

{optional_table}

ค่าที่ไม่ทราบคงเป็นค่าขาดหาย แยกจากศูนย์ แบตเตอรี่และกล่องสกัดจากข้อความที่ระบุชัด ประกันไม่ใช้เนื่องจากความครอบคลุมต่ำ ไม่มีข้อมูลรอยตำหนิ ประวัติซ่อม และอายุเครื่องจริงที่ผ่านการตรวจพร้อมฝึก

![ความครอบคลุมข้อมูลประกอบและปีประกาศของชุดฝึก 9,100 แถว](assets/eda/figures/model_input_coverage.png)

## 4. ผลสำรวจชุดก่อนคัด 10,032 แถว

กราฟและสถิติในส่วนนี้ใช้ชุดก่อนคัด ไม่ใช่ชุดฝึกปัจจุบัน

| ประเด็น | ผลสำรวจ |
|---|---|
| ราคามัธยฐาน; Q1–Q3 | 18,990; 11,500–27,000 บาท |
| IQR ภายในเว็บ/รุ่น/ความจุ/สภาพ/ปี | ระบุ 205 แถว จาก 7,543 แถวที่ประเมินได้ |
| กลุ่มที่ไม่ประเมิน IQR | กลุ่มเล็ก 2,467 แถว; IQR เป็นศูนย์ 22 แถว |
| กลุ่มข้อความที่อาจซ้ำ | 280 กลุ่ม รวม 617 แถว หลังรวมกลุ่มซ้อนกัน |
| กลุ่มที่เทียบสองเว็บได้ | 27 กลุ่ม รวม 403 แถว; อย่างน้อย 3 แถวต่อเว็บ |
| Spearman ราคา–ความจุ | 0.49 |
| Spearman ราคา–ปีประกาศ | 0.11 |

ค่าผิดปกติและข้อความซ้ำเป็นสัญญาณตรวจสอบ ไม่ยืนยันว่าราคาผิดหรือเป็นเครื่องเดียวกัน การเปรียบเทียบเว็บไซต์และสหสัมพันธ์ไม่แสดงความสัมพันธ์เชิงเหตุและผล

![สัดส่วนเว็บไซต์และยี่ห้อในชุดก่อนคัด 10,032 แถว](assets/eda/figures/01_source_and_brand.png)

![การกระจายราคาในชุดก่อนคัด 10,032 แถว](assets/eda/figures/02_price_distribution.png)

<a id="stage-eda"></a>

## 5. วิธีวิเคราะห์และข้อจำกัด

ตรวจความตรงกันของข้อมูลและ lineage ก่อนสรุปจำนวน การกระจายราคา IQR ภายในกลุ่ม และข้อความที่อาจซ้ำ ใช้ `script/analysis/eda/run_eda.py`; สถิติชุดปัจจุบันสร้างด้วย `script/analysis/eda/refresh_model_input_eda.py`

- การคัด 822 แถวทำก่อนแบ่งข้อมูลตามเวลา จึงมีความเอนเอียงจากการคัดเลือก ผลโมเดลต้องอ่านเป็นการประเมินย้อนหลัง
- จำนวนรุ่นและช่วงเวลาของสองเว็บไซต์ต่างกัน ความต่างของราคามัธยฐานไม่ใช่ผลของเว็บไซต์เพียงอย่างเดียว เว็บไซต์จึงเก็บเพื่อที่มาและรายงานแยกกลุ่ม
- สภาพเป็นคำระบุของผู้ขาย ไม่มีการตรวจเครื่องจริงหรือราคาปิดการขาย

หลักฐาน: [ความครบถ้วนแยกเว็บไซต์](assets/eda/tables/model_input_optional_coverage.csv) · [จำนวนและวันที่แยกรุ่น](assets/eda/tables/model_input_model_support.csv) · [จำนวนแยกปี](assets/eda/tables/model_input_year_source.csv) · [ข้อมูลกำกับและสถิติเดิม](assets/eda/metadata.json)

อ่านต่อ: [การคัดข้อมูล](data.md#stage-model_input) · [โมเดลและผลประเมิน](modeling.md)
'''
    document.write_text(markdown, encoding='utf-8')
    from script.modeling.model_v2.report_improved import html_export
    html_markdown = markdown.replace('assets/eda/figures/', 'figures/')
    exported = html_export(html_markdown, report).replace('<title>Model V2 report</title>', '<title>EDA</title>')
    (report / 'report.html').write_text(exported, encoding='utf-8')
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
