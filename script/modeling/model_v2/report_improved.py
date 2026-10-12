"""One canonical model report with training protocol, metrics and diagnostic figures."""
import base64
import html
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if not __package__:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from script.modeling.common import table
from script.report_links import heading_anchor, report_url



from script.artifacts import collect_output_hashes, has_metadata, read_metadata, write_metadata

def html_export(markdown, report):
    """Render this report's headings, tables and graphs into one portable HTML file."""
    def inline(text):
        escaped = html.escape(text)
        escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
        escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
        def link(match):
            target = report_url(html.unescape(match[2]), local_anchors=True)
            return ('<a href="' + html.escape(target, quote=True) + '">' + match[1] + '</a>'
                    if target else match[1])
        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, escaped)
    blocks = []; in_code = False; in_table = False
    for line in markdown.splitlines():
        if in_table and not line.startswith('|'):
            blocks.append('</tbody></table>'); in_table = False
        if line.startswith('```'):
            blocks.append('</code></pre>' if in_code else '<pre><code>'); in_code = not in_code
        elif in_code:
            blocks.append(html.escape(line) + '\n')
        elif line.startswith('|'):
            if re.fullmatch(r'[|\- :]+', line):
                continue
            cells = line.strip('|').split('|')
            tag = 'td' if in_table else 'th'
            if not in_table:
                blocks.append('<table><tbody>'); in_table = True
            blocks.append('<tr>' + ''.join('<' + tag + '>' + inline(c.strip()) + '</' + tag + '>' for c in cells) + '</tr>')
        elif match := re.fullmatch(r'!\[([^\]]*)\]\((figures/[^)]+)\)', line):
            data = base64.b64encode((report / match[2]).read_bytes()).decode()
            blocks.append('<figure><img alt="' + html.escape(match[1]) + '" src="data:image/png;base64,' + data + '"><figcaption>' + inline(match[1]) + '</figcaption></figure>')
        elif match := re.match(r'^(#{1,6}) (.+)$', line):
            level = str(len(match[1]))
            blocks.append('<h' + level + ' id="' + html.escape(heading_anchor(match[2]), quote=True)
                          + '">' + inline(match[2]) + '</h' + level + '>')
        elif line.strip():
            blocks.append('<p>' + inline(line) + '</p>')
    if in_table:
        blocks.append('</tbody></table>')
    return '<!doctype html><html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Model V2 report</title><style>body{max-width:1050px;margin:32px auto;padding:0 20px;font-family:sans-serif;line-height:1.7;color:#172033}h2{margin-top:2em}table{border-collapse:collapse;width:100%;font-size:.9em}td,th{border:1px solid #cbd5e1;padding:8px;text-align:left}th{background:#eef2ff}img{max-width:100%;height:auto}pre{overflow:auto;background:#f1f5f9;padding:16px}figure{margin:24px 0}</style></head><body>' + ''.join(blocks) + '</body></html>'


def platform_evaluation(rows, actual, predicted):
    """Report inferred phone platforms; unknown systems remain a separate group."""
    from script.modeling.common import metrics
    android_brands = {'Samsung', 'Oppo', 'Vivo', 'Xiaomi', 'Redmi', 'Realme',
                      'Infinix', 'Honor', 'OnePlus', 'Asus', 'Motorola', 'Google', 'Sony'}
    groups = {'iOS': [], 'Android': [], 'unconfirmed': []}
    for index, row in enumerate(rows):
        if row['brand'] == 'Apple' and row['model'].lower().startswith('iphone'):
            group = 'iOS'
        elif row['brand'] in android_brands:
            group = 'Android'
        else:
            group = 'unconfirmed'
        groups[group].append(index)
    return {
        'classification': 'Inferred from brand/model, not observed OS. Apple iPhone=iOS; Android brand allowlist; all others unconfirmed.',
        'android_brands': sorted(android_brands),
        'groups': {name: metrics(np.asarray(actual)[indices], np.asarray(predicted)[indices])
                   for name, indices in groups.items() if indices},
        'unconfirmed_brands': sorted({rows[i]['brand'] for i in groups['unconfirmed']}),
    }


def render(report, s, comparisons, actual, predicted, evaluation_rows=None, refresh_figures=True):
    report = Path(report)
    figures = report / 'figures'
    figures.mkdir(exist_ok=True)
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    residual = predicted - actual
    config = read_metadata(report, 'config')
    folds = read_metadata(report, 'folds')
    selected = next(candidate for candidate in config['candidates'] if candidate['name'] == s['selected_model'])
    method = {'hist': 'HistGradientBoosting', 'catboost': 'CatBoost', 'trend': 'Ridge trend + residual boosting',
              'depreciation': 'Age-normalized HistGradientBoosting',
              'blend': 'HGB / CatBoost weighted ensemble',
              'v1': 'V1 reference'}[selected['kind']]
    method += ' + log(price)' if selected.get('log_target') or selected['kind'] in ('trend','depreciation') else ' + price (THB)'

    def save(name):
        if not refresh_figures and all((figures / (name + '.' + suffix)).exists() for suffix in ['png', 'svg']):
            plt.close()
            return
        plt.tight_layout()
        for suffix in ['png', 'svg']:
            temporary = figures / (name + '.tmp.' + suffix)
            plt.savefig(temporary, dpi=160, format=suffix)
            temporary.replace(figures / (name + '.' + suffix))
        plt.close()

    ordered = sorted(comparisons, key=lambda r: r['mae_thb'], reverse=True)
    plt.figure(figsize=(10, max(6, len(comparisons) * .32)))
    plt.barh([r['name'] for r in ordered], [r['mae_thb'] for r in ordered])
    plt.xlabel('Pooled forward validation MAE (THB)')
    save('validation_comparison')
    plt.figure(figsize=(6, 6))
    plt.scatter(actual, predicted, s=14, alpha=.4)
    upper = max(max(actual), max(predicted)) * 1.04
    plt.plot([0, upper], [0, upper], 'k--')
    plt.xlabel('Actual asking price (THB)')
    plt.ylabel('Retrospective predicted price (THB)')
    save('retrospective_actual_vs_predicted')
    plt.figure(figsize=(9, 5))
    plt.scatter(actual, residual, s=14, alpha=.4)
    plt.axhline(0, color='black', linestyle='--')
    plt.xlabel('Actual asking price (THB)')
    plt.ylabel('Prediction minus actual (THB)')
    save('retrospective_residuals')
    plt.figure(figsize=(9, 5))
    plt.hist(np.abs(residual), bins=30, edgecolor='white')
    plt.xlabel('Absolute error (THB)')
    plt.ylabel('Listings')
    save('retrospective_error_distribution')
    brand_groups = sorted([r for r in s['groups'] if r['group'] == 'brand' and r['rows'] >= 10],
                          key=lambda r: r['mae_thb'])
    plt.figure(figsize=(9, 5))
    plt.barh([r['value'] + ' (n=' + str(r['rows']) + ')' for r in brand_groups],
             [r['mae_thb'] for r in brand_groups])
    plt.xlabel('Retrospective MAE (THB); groups with at least 10 listings')
    save('retrospective_brand_mae')

    if evaluation_rows is not None:
        s['platform_evaluation'] = platform_evaluation(evaluation_rows, actual, predicted)
        write_metadata(report, 'summary', s)
    platform_text = ''
    if platform := s.get('platform_evaluation'):
        labels = {'iOS': 'iOS (iPhone)', 'Android': 'Android (อนุมาน)', 'unconfirmed': 'ยังไม่ยืนยัน OS'}
        keys = [name for name in labels if name in platform['groups']]
        specifications = [('จำนวนประกาศ', 'rows', 'count'), ('MAE (บาท)', 'mae_thb', 'number'),
            ('RMSE (บาท)', 'rmse_thb', 'number'), ('Median absolute error (บาท)', 'median_absolute_error_thb', 'number'),
            ('R²', 'r2', 'r2'), ('MAPE', 'mape_pct', 'percent'),
            ('ทำนายใน ±20%', 'within_20pct', 'fraction'), ('Bias (บาท)', 'bias_thb', 'number')]
        metric_rows = []
        for label, key, kind in specifications:
            values = []
            for name in keys:
                value = platform['groups'][name][key]
                values.append('ไม่คำนวณ' if value is None else
                    str(value) if kind == 'count' else
                    f'{value:.4f}' if kind == 'r2' else
                    f'{value * 100:.2f}%' if kind == 'fraction' else
                    f'{value:.2f}%' if kind == 'percent' else f'{value:,.2f}')
            metric_rows.append([label, *values])
        platform_text = '\n## 7. ผลการประเมินแยก Android และ iOS\n\n' + table(['ตัววัด', *[labels[name] for name in keys]], metric_rows)
        platform_text += f"\nใช้ราคาจริงและผลทำนายของ evaluation artifact บน {len(actual):,} ประกาศย้อนหลังชุดเดิม ไม่ฝึกโมเดลแยกหรือเปลี่ยนพารามิเตอร์เพื่อคำนวณตารางนี้ Dataset ไม่มีฟิลด์ OS จริง จึงจัด Apple ที่ระบุรุ่น iPhone เป็น iOS และยี่ห้อ Android ตาม allowlist ที่บันทึกไว้ กลุ่มที่ยืนยันไม่ได้แยกไว้ครบ\n"
        if unknown := platform['groups'].get('unconfirmed'):
            platform_text += f"\nกลุ่มยังไม่ยืนยัน OS มี {unknown['rows']:,} แถว ได้แก่ {', '.join(platform['unconfirmed_brands'])} จึงไม่รวมเป็น Android อัตโนมัติ ตารางนี้ไม่ยืนยัน OS ที่ติดตั้งจริงหรือการดัดแปลงเครื่อง\n"
        if all(name in platform['groups'] for name in ['iOS', 'Android']):
            ios, android = platform['groups']['iOS'], platform['groups']['Android']
            platform_text += f"\n**อ่านผล:** iOS มี MAE {ios['mae_thb']:,.2f} บาท และ R² {ios['r2']:.4f} ส่วน Android มี MAE {android['mae_thb']:,.2f} บาท และ R² {android['r2']:.4f}; ทำนายใน ±20% ได้ {ios['within_20pct']*100:.2f}% และ {android['within_20pct']*100:.2f}% ตามลำดับ ดูทั้งความคลาดเคลื่อนเป็นบาทและสัดส่วนราคา Bias ติดลบหมายถึงแนวโน้มทำนายต่ำ\n"
        if drift := s.get('data_drift'):
            apple = drift['training_brands'].get('Apple', 0)
            platform_text += f"\n**ข้อมูลฝึก:** evaluation artifact มี Apple {apple:,} จาก {s['evaluation_fit_rows']:,} แถว ({apple/s['evaluation_fit_rows']*100:.2f}%) ส่วน catalog อายุรุ่นมีเฉพาะ iPhone จึงมีทั้งความไม่สมดุลของข้อมูลและความต่างของข้อมูลประกอบ\n"
        platform_text += "\n**ข้อจำกัด:** รุ่น ช่วงราคา และช่วงเวลาของแต่ละกลุ่มต่างกัน R² เทียบกับค่าเฉลี่ยภายในกลุ่ม และไม่ใช่เปอร์เซ็นต์ accuracy ผลนี้ไม่พิสูจน์ว่า OS เป็นสาเหตุของความแม่นยำ ไม่ได้ทดสอบนัยสำคัญทางสถิติ และยังไม่ใช่คะแนน holdout ใหม่ ควรเพิ่มข้อมูล Android และประเมินช่วงเวลาใหม่ก่อนรับรองผลแยกแพลตฟอร์ม\n"

    e, b, v = s['retrospective'], s['v1_same_cutoff'], s['validation']
    previous_text = ''
    if previous := s.get('previous_round'):
        old = previous['retrospective']
        previous_text = '\n\nเทียบกับโมเดลที่ใช้งานก่อนรอบนี้ บนประกาศย้อนหลังชุดเดียวกัน:\n\n' + table(
            ['ตัววัด', 'ก่อนปรับ', 'รอบนี้'],
            [[label, f'{old[key]:,.4f}' if key == 'r2' else f'{old[key]:,.2f}',
              f'{e[key]:,.4f}' if key == 'r2' else f'{e[key]:,.2f}']
             for label, key in [('MAE (บาท)', 'mae_thb'), ('RMSE (บาท)', 'rmse_thb'), ('R²', 'r2')]])
    source = [r for r in s['groups'] if r['group'] == 'source']
    source_table = table(['เว็บ', 'n', 'MAE (บาท)', 'RMSE (บาท)', 'R²', 'ภายใน ±20%'],
                         [[r['value'], r['rows'], f'{r["mae_thb"]:,.2f}', f'{r["rmse_thb"]:,.2f}',
                           f'{r["r2"]:.4f}', f'{r["within_20pct"]*100:.2f}%'] for r in source])
    coverage_table = table(['รุ่นในชุดประเมิน', 'n', 'MAE (บาท)', 'ภายใน ±20%'],
        [['เคยอยู่ในชุดฝึก' if r['value'] == 'seen' else 'ไม่เคยอยู่ในชุดฝึก', r['rows'],
          f'{r["mae_thb"]:,.2f}', f'{r["within_20pct"]*100:.2f}%']
         for r in s['groups'] if r['group'] == 'model_coverage'])
    drift_text = ''
    if drift := s.get('data_drift'):
        drift_text = (f"Apple ในชุดฝึก {drift['training_brands'].get('Apple',0)/s['evaluation_fit_rows']*100:.2f}% "
                      f"เทียบกับ {drift['evaluation_brands'].get('Apple',0)/s['retrospective_rows']*100:.2f}% ในชุดประเมิน "
                      f"มี {drift['unseen_model_rows']} แถวที่เป็นรุ่นไม่เคยอยู่ในชุดฝึก แสดงว่าข้อมูลต่างช่วงมีส่วนผสมต่างกัน")
    tuning_text = ''
    if has_metadata(report, 'tuning_review'):
        review = read_metadata(report, 'tuning_review')
        trials = table(['กลุ่มทดลอง', 'ตัวเลือกที่ชนะ validation', 'Validation MAE (บาท)', 'สถานะ'],
            [[r['label'], r['selected'], f'{r["validation_mae_thb"]:,.2f}', r['status']] for r in review['experiments']])
        tradeoffs = table(['ยี่ห้อ (อย่างน้อย 10 แถว)', 'n', 'MAE ก่อน (บาท)', 'MAE รอบนี้ (บาท)'],
            [[r['value'], r['rows'], f'{r["previous_mae_thb"]:,.2f}', f'{r["current_mae_thb"]:,.2f}']
             for r in review.get('group_tradeoffs',[])])
        storage_text = ''
        if storage_audit := review.get('storage_reference_audit'):
            storage_text = (f"ตรวจความจุกับสเปก Apple เพิ่ม พบ {storage_audit['flagged_rows']} แถวที่ความจุประกาศไม่อยู่ในรายการของรุ่นที่ normalize ไว้ "
                            "ยังไม่เดาว่ารุ่นหรือความจุผิด และไม่แก้ชุดฝึกในการเปรียบเทียบนี้ ต้องตรวจรายละเอียดต้นทางก่อน "
                            "หน้าเว็บใช้ตัวเลือกจากสเปกผู้ผลิตสำหรับ iPhone เพื่อกันค่าที่ไม่รองรับ "
                            "ดู [ผลตรวจความจุ](tables/storage_reference_audit.csv) และ [Apple Support](https://support.apple.com/en-us/108044)")
        tuning_text = f'''\n\n## 11. รอบปรับปรุง 2026-10-12

ทดลอง **{review['unique_candidates']} ตัวเลือกไม่ซ้ำ** โดยคงข้อมูล 9,210 แถวและ folds/cutoff เดิม ไม่ตัดประกาศเพิ่มเพื่อให้คะแนนดีขึ้น ค่า MAE/R² ทุกตัววัดบนแถวเดิม

{trials}

{review['decision']}

ผลรวมดีขึ้น แต่ไม่ได้ดีขึ้นทุกยี่ห้อ ต้องดู trade-off ต่อไปนี้ โดยเฉพาะ Samsung ที่ยังเป็นข้อจำกัด:

{tradeoffs}

ดูทุกกลุ่มใน [ตารางก่อน/หลังแยกกลุ่ม](tables/tuning_group_comparison.csv) ไม่ตัดกลุ่มที่ผลแย่ลงออกจากการรายงาน

{storage_text}

ใช้ MAE validation เลือกพารามิเตอร์ แล้วตรวจผลย้อนหลังเพื่อรับหรือปฏิเสธการเปลี่ยนโมเดลใช้งาน ผลย้อนหลังจึงมีส่วนใน การเลือกโมเดลใช้งาน และยังเป็นข้อมูลที่เคยเห็น ห้ามตีความเป็นการทดสอบอิสระหรือรับประกันผลในอนาคต

อ่าน [ตัวเลข validation ทุกตัวเลือก](tables/tuning_validation.csv) และ [บัญชีการทดลอง/ที่มาผล](metadata.json#tuning_review) สำหรับ config, hashes, สถานะและค่าก่อนปรับ ข้อมูลรายแถวและ binary ของโมเดลทดลองอยู่ในเครื่อง

กลุ่มทดลองเก็บแผนใน `experiments.json` และผลย้อนหลังใน `history.zip`; แผนหลัก `current.json` ใช้สร้างโมเดลใช้งานปัจจุบัน
'''
    compare = table(['ตัวเลือก', 'Validation MAE (บาท)', 'RMSE (บาท)', 'fit (วินาที)'],
                    [[r['name'], f'{r["mae_thb"]:,.2f}', f'{r["rmse_thb"]:,.2f}', r['fit_seconds']]
                     for r in sorted(comparisons, key=lambda r: r['mae_thb'])])
    fold_table = table(['Fold', 'Train n', 'Train ถึง', 'Validation n', 'Validation เริ่ม', 'Validation ถึง'],
                       [[r['fold'], r['train_rows'], r['train_max'], r['validation_rows'],
                         r['validation_min'], r['validation_max']] for r in folds])
    metric_rows = [
        ('MAE', 'เฉลี่ย abs(ŷ−y); ยิ่งต่ำยิ่งดี', 'mae_thb', 'บาท'),
        ('RMSE', 'รากของเฉลี่ย (ŷ−y)²; ไวต่อ error ก้อนใหญ่', 'rmse_thb', 'บาท'),
        ('Median absolute error', 'มัธยฐานของ abs(ŷ−y); ครึ่งหนึ่งมี error ไม่เกินค่านี้', 'median_absolute_error_thb', 'บาท'),
        ('R²', '1−SSE/SST; เทียบกับการทำนายด้วยค่าเฉลี่ยของชุดประเมิน', 'r2', ''),
        ('MAPE', 'เฉลี่ย abs(ŷ−y)/y ×100; ราคาต่ำทำให้เปอร์เซ็นต์สูงง่าย', 'mape_pct', '%'),
        ('ภายใน ±20%', 'สัดส่วนแถวที่ abs(ŷ−y)/y ≤0.20; ยิ่งสูงยิ่งดี', 'within_20pct', '%'),
        ('Bias', 'เฉลี่ย (ŷ−y); ลบหมายถึงทำนายต่ำโดยเฉลี่ย', 'bias_thb', 'บาท'),
    ]
    def value(row, key, unit):
        number = row[key] * (100 if key == 'within_20pct' else 1)
        return f'{number:,.4f}' if key == 'r2' else f'{number:,.2f} {unit}'
    metrics_table = table(['ตัววัด', 'ความหมาย', 'V1', 'V2'],
                          [[name, meaning, value(b, key, unit), value(e, key, unit)]
                           for name, meaning, key, unit in metric_rows])
    from script.modeling.model_v2.features_v2 import CATEGORICAL, NUMERIC
    detailed = f'''# รายงานโมเดลราคาตั้งขายมือถือ — V2

รายงานหลักเรื่องโมเดล: อ่านวิธีเลือกข้อมูล วิธีเทรน กราฟ ตัววัด ผลแยกกลุ่ม และหลักฐานประกอบได้ในไฟล์นี้ เอกสาร HTML เป็นเนื้อหาเดียวกันสำหรับเปิดใน browser; JSON/CSV เป็นหลักฐานตัวเลข ไม่ใช่คู่มืออีกชุด

## สรุปผลการประเมิน

เลือก **{method}** (`{s['selected_model']}`) จาก {len(comparisons)} ตัวเลือกด้วย validation ตามเวลา 2 ช่วง MAE validation **{v['mae_thb']:,.2f} บาท**

เปรียบเทียบย้อนหลังบน **{s['retrospective_rows']} ประกาศเดิม**: MAE ลดจาก **{b['mae_thb']:,.2f}** เป็น **{e['mae_thb']:,.2f} บาท** หรือ **{s['retrospective_mae_improvement_pct']:.2f}%**; R² **{e['r2']:.4f}**; ทำนายใน ±20% ของราคาประกาศได้ **{e['within_20pct']*100:.2f}%**{previous_text}

**ผลนี้เป็นการประเมินย้อนหลังบนชุดเดิมที่เคยเปิดดูระหว่างพัฒนา ไม่ใช่ holdout ใหม่** โมเดลสำหรับใช้งานฝึกครบ {s['deployment_fit_rows']:,} แถวและยังไม่มีคะแนนทดสอบอิสระของตัวที่ฝึกครบ

อ่าน [ผลประเมินแยก Android และ iOS](#7-ผลการประเมินแยก-android-และ-ios) จาก **test เดิม 693 ประกาศ** ในหัวข้อ 7

## 1. ข้อมูลที่เลือกใช้และข้อมูลที่ตัดออก

หนึ่งแถวคือหนึ่งประกาศ ราคาเป้าหมายคือ **ราคาตั้งขาย หน่วยบาท** ไม่ใช่ราคาปิดการขาย ใช้ทุกวันที่ใน snapshot ไม่มีการจำกัด 12 เดือน

| ขั้น | ENNXO | Mac2Hand | รวม |
|---|---:|---:|---:|
| ประกาศดิบใน snapshot | 1,381 | 10,220 | 11,601 |
| ผ่าน clean ก่อนคัด EDA | 1,279 | 8,753 | 10,032 |
| ชุดใช้สำหรับโมเดลหลังคัด | 1,202 | 8,008 | 9,210 |

Clean ตรวจรุ่น ความจุ ราคา วันที่และขอบเขตสินค้า อิงรายละเอียดที่มีหลักฐาน เก็บ source/product_id/url/lineage ค่าที่ไม่ระบุหรือขัดกันไม่เดา แยกเครื่องเสีย/ล็อกและแถวที่ไม่ผ่านก่อนรวม; ป้ายสภาพ `new` ไม่ทำให้ถูกตัดอย่างเดียวตามนโยบายโครงการ

EDA ระบุคิวจาก IQR, ข้อความ candidate ซ้ำ และรายการราคาสูงสุด ผู้ใช้เลือกตัดสมาชิกคิวทั้งหมด **822 รหัส** โดยนับ union ของเหตุผลที่ซ้อนกัน ไม่ใช่ยืนยันว่าทั้ง 822 แถวผิดทั้งหมด คัดด้วย `script/preparation/shared/select_model_input.py` ตาม `config/shared/model_input_policy.json` คง raw และเหตุผลไว้

`data/final/dataset.csv` มี 13 คอลัมน์ / 9,210 แถว ข้อมูลส่วนใหญ่เป็น Apple และ Mac2Hand; กลุ่มย่อยไม่สมดุล การคัดใช้ EDA ทั้ง snapshot ก่อน split จึงมี selection bias คะแนนอธิบายชุดหลังคัดนี้ ไม่ใช่ประกาศทุกประเภทบนเว็บ

## 2. ตัวแปรที่ใช้และการจัดการค่าขาดหาย

ใช้ **22 features**:

- หมวดหมู่ 7 ตัว: `{', '.join(CATEGORICAL)}`
- ตัวเลข/ตัวบ่งชี้ 15 ตัว: `{', '.join(NUMERIC)}`

Features หลักคือเว็บ ยี่ห้อ รุ่น ความจุ สภาพและวันประกาศ เพิ่ม family/tier ของรุ่น ปีเปิดตัว iPhone จาก Apple และอายุรุ่น ณ เดือนประกาศโดยประมาณ ไม่ใช่อายุเครื่องจริง Android ที่ไม่มี catalog คงปีเปิดตัว missing

Battery health %, ประกันวันและกล่องถอดจากข้อความด้วยกฎ เฉพาะคำระบุชัดและค่าเดียว ตรวจ listing_id/source/price ตรง lineage ค่าขัดกันหรือไม่ระบุคง missing; กล่องมี/ไม่มีใช้ 1/0 และไม่ทราบเป็น missing แยกจากศูนย์ ไม่ป้อน title/description ทั้งหมดหรือราคาในข้อความให้โมเดล

ฝั่ง HGB ใช้ one-hot encoding ที่รับ unknown category ได้ ตัวเลขเติม median และ scale จาก train ของ fold เท่านั้น ส่วน CatBoost ใช้ categorical features และ numeric missing ตาม native behavior ไม่ใช้ target encoding จาก validation ไม่เขียนค่าที่เติมกลับลง dataset เก็บ optional values ใน `data/final/condition_features.csv` จับคู่ด้วย listing_id ส่วนราคาเป้าหมาย ID และ URL ไม่ใช้เป็น features

## 3. การแบ่งข้อมูลตามเวลา

เรียงตามวันประกาศและรหัส ไม่สุ่มประกาศเก่ากับใหม่ปนกัน วันเดียวกันอยู่ฝั่งเดียว ป้องกันเรียนรู้ข้อมูลอนาคตใน preprocessing และน้ำหนักข้อมูล

{fold_table}

Validation สองช่วงรวม **1,054 แถว** จำนวน train ที่ทับกันระหว่าง folds ไม่ใช่ข้อมูลเพิ่ม เกณฑ์เลือกคือ MAE ของ prediction validation ทั้งสองช่วงรวมตามจำนวนแถวจริง

หลังเลือกวิธีแล้ว ฝึก evaluation artifact **8,517 แถวก่อน 2025-01-09** ประเมินบน **693 แถววันที่ 2025-01-09 ถึง 2026-10-06** cutoff เดียวกับ V1 รอบนี้ไม่ใช้ชุด 693 แถวเลือกพารามิเตอร์ แต่เคยเห็นชุดนี้ในการพัฒนาเดิม จึงเรียกการเปรียบเทียบย้อนหลัง

สุดท้ายฝึก operational artifact แยกด้วย **9,210 แถว** เพื่อเรียนรู้ {s['deployment_models']} รุ่นจนถึง {s['deployment_date_max']} การฝึกครบทำให้คะแนนย้อนหลังของ evaluation artifact ไม่ใช่คะแนนอิสระของ operational artifact

## 4. กระบวนการฝึกและการเลือกโมเดล

ทดลอง {len(comparisons)} ตัวเลือกตาม frozen config มี reference V1 และโมเดลที่ใช้ก่อนปรับ รวมถึงการปรับ loss, ความซับซ้อน และแนวโน้มราคา ไม่ได้ทำ exhaustive search ทุกพารามิเตอร์ ทุกตัวใช้ folds และแถวเดียวกัน

วิธีชนะ: **{method}**; seed **{config['seed']}**, threads **{config['threads']}** พารามิเตอร์ตัวเลือกที่ชนะ:

```json
{json.dumps(selected, ensure_ascii=False, indent=2)}
```

ตัวเลือก log target แปลงกลับด้วย exp ก่อนวัด error เป็นบาท ราคาทำนาย floor ที่ 1 บาทตาม inference เดิม HGB ไม่ใช้ early stopping ส่วน CatBoost ใช้ fixed iterations และ `has_time=True`

Recency half-life ของวิธีชนะ **{selected.get("half_life", 0)} ปี**: ถ้าเป็นศูนย์ให้น้ำหนักเท่ากัน ถ้ามากกว่าศูนย์ใช้ max(0.01, 2^(−อายุข้อมูลปี/half-life)) อายุข้อมูลนับจากวันล่าสุดใน train ของ fold แล้ว normalize ให้เฉลี่ย 1 ไม่ลบข้อมูลเก่า

Ensemble ฝึกสมาชิกแยกกันบน log ราคา แล้วเฉลี่ยราคาที่แปลงกลับเป็นบาทด้วยสัดส่วนที่กำหนดไว้ก่อน scoring; HGB default: 400 iterations, 31 leaves, learning rate 0.07, l2=8; CatBoost default: 800 iterations, depth 6, learning rate 0.045, RMSE บน log target สมาชิกได้รับ sample weights ชุดเดียวกัน ไม่มี stacking ที่เรียนจาก test

ตัวเลือก trend ใช้ Ridge บน log ราคา เพิ่ม interaction รุ่น/ระดับเครื่องกับอายุ และยี่ห้อกับปีประกาศ เติม missing/encode/scale จาก train เท่านั้น แล้วทดลอง HGB เรียนรู้ residual โดยไม่อ่านราคา validation เป็น feature

{compare}

![เปรียบเทียบ validation MAE](figures/validation_comparison.png)

**อ่านกราฟ:** แท่งสั้นคือ MAE ต่ำกว่า ใช้กราฟนี้และตัวเลข validation เลือกวิธี ไม่เลือกด้วยคะแนนชุดย้อนหลัง ตาราง [fold_metrics.csv](tables/fold_metrics.csv) เก็บผลแต่ละ fold เพื่อดูความเปลี่ยนแปลงตามเวลา

## 5. ตัวชี้วัดและผลการประเมิน

กำหนด y = ราคาประกาศจริง, ŷ = ราคาที่ทำนาย ตัววัดทั้งหมดคำนวณหลังแปลงกลับเป็นบาท บน 693 แถวเดียวกันสำหรับ V1/V2

{metrics_table}

MAE คือจำนวนบาทที่คลาดเคลื่อนเฉลี่ย RMSE สูงกว่า MAE เพราะให้น้ำหนัก error ใหญ่ Median absolute error บอกผลทั่วไปที่ไม่ถูกบางแถวลากมาก Bias ติดลบหมายถึงมีแนวโน้มทำนายต่ำ R² ไม่ใช่เปอร์เซ็นต์ accuracy และ MAPE ไม่ใช่อัตราผ่าน ±20%

**มี hypothesis test หรือ p-value หรือไม่:** งานนี้ยังไม่ได้ทำ t-test, ANOVA, Wilcoxon หรือทดสอบนัยสำคัญของความต่างโมเดล จึงไม่มี test statistic/p-value และไม่สรุปว่าดีขึ้นอย่างมีนัยสำคัญทางสถิติ MAE/RMSE/R² เป็น evaluation metrics ไม่ใช่ hypothesis tests การมีเพียง 2 folds และการใช้ test เดิมซ้ำไม่เพียงพอให้ตีความเปอร์เซ็นต์การปรับปรุงว่าเป็นหลักฐานอิสระของประสิทธิภาพในอนาคต

## 6. ผลการประเมินแยกเว็บไซต์และยี่ห้อ

{source_table}

{coverage_table}

{drift_text}

จำนวนและส่วนผสมรุ่นต่างกัน จึงไม่ถือว่าคะแนนเว็บหนึ่งดีกว่าเพราะชื่อเว็บอย่างเดียว กลุ่มเล็กไม่ใช้รับรองความแม่นยำ

![MAE ตามยี่ห้อ](figures/retrospective_brand_mae.png)

**อ่านกราฟ:** แสดงเฉพาะยี่ห้อที่มีอย่างน้อย 10 แถว พร้อม n; แท่งสั้นคือ error น้อย ดู [retrospective_by_group.csv](tables/retrospective_by_group.csv) สำหรับทุกยี่ห้อ ปี สภาพ และรุ่นเคยเห็น/ไม่เคยเห็น กลุ่มน้อยกว่า 10 ยังคงอยู่ในตาราง ไม่ถูกลบจากผลประเมิน

{platform_text}
## 8. กราฟวิเคราะห์ความคลาดเคลื่อน

![ราคาจริงและราคาทำนาย](figures/retrospective_actual_vs_predicted.png)

**อ่านกราฟ:** จุดใกล้เส้นประคือทำนายใกล้ราคาประกาศ จุดใต้เส้นคือทำนายต่ำ จุดเหนือเส้นคือสูง ไม่ได้เทียบกับราคาขายสำเร็จ

![Residual กับราคาประกาศ](figures/retrospective_residuals.png)

**อ่านกราฟ:** residual = ŷ−y เส้นศูนย์คือถูกพอดี จุดต่ำกว่าศูนย์คือทำนายต่ำ ใช้ดูว่าราคาสูงมี error ทางเดียวมากหรือไม่ ไม่ได้ทดสอบว่าข้อสมมติ residual ผ่านทางสถิติ

![การกระจาย absolute error](figures/retrospective_error_distribution.png)

**อ่านกราฟ:** แกนนอนคือ error เป็นบาท แกนตั้งคือจำนวนประกาศ หางด้านขวาคือกลุ่มที่คลาดเคลื่อนสูง ไม่ใช่ confidence interval ของราคาทำนาย

## 9. ข้อจำกัดและขอบเขตการสรุปผล

V2 ให้ MAE ต่ำกว่า V1 ในการเปรียบเทียบย้อนหลังเดียวกัน แต่มีอคติจากการคัดข้อมูลก่อน split ข้อมูลเว็บ/รุ่น/สภาพไม่สมดุล รุ่นใหม่/Android มีข้อจำกัดและสภาพจากผู้ขายอาจไม่ครบ ไม่มีการยืนยันว่าเป็นเครื่องคนละเครื่องทางกายภาพ

Catalog Apple รวบรวมภายหลัง ใช้ปีเปิดตัวที่ทราบ ณ วันประกาศ ไม่อ้างว่าระบบรู้ข้อมูลรุ่นที่ยังไม่เปิดตัวได้ในอดีต อายุมีความละเอียดระดับปี วันนอกช่วงฝึกหรือค่าที่ไม่ทราบมี coverage flags ซึ่งไม่ใช่ค่าความเชื่อมั่นทางสถิติ

โมเดลพร้อมทดลองประเมิน **ราคาตั้งขายของเครื่องปกติ** ก่อนรับรองประสิทธิภาพจริงควรประเมินชุดใหม่หลัง 2026-10-06 ที่ไม่เคยใช้พัฒนา ไม่อ้างราคาปิดขายหรือความแม่นยำ 100%

## 10. เครื่องมือ ข้อมูลเข้า และผลลัพธ์

| สคริปต์ใน script/modeling/ | หน้าที่ / input | output |
|---|---|---|
| `model_v2/prepare_features_v2.py` | อ่าน core/lineage/full-text และตรวจหลักฐาน ถอด optional claims | enrichment dataset/audit ใน intermediate (ต้องมีหลักฐาน private) |
| `model_v2/rebuild_features_v2.py` | core + public condition sidecar ตรวจ hashes | enriched CSV byte ตรงรอบจริง ไม่ต้องใช้ raw |
| `model_v2/features_v2.py` | สร้าง 22 features จากข้อมูลและ frozen catalog | โมดูลประกอบ ไม่รันแยก |
| `trend.py` | Ridge/residual, age normalization และ fixed-weight ensemble | โมดูล estimator สำหรับทดลอง ไม่รันแยก |
| `model_v2/train_improved.py` | 2 temporal folds เลือก → evaluation → fit ครบ | artifacts, reports และ predictions รายแถว |
| `model_v2/report_improved.py` | อ่านผลจริง/ตัวเลขสร้างรายงานนี้และกราฟ | docs/modeling.md, HTML และ figures |
| `predict.py` | ตรวจ checksum โหลด artifact และทำนาย | ราคาทำนายที่ส่งให้หน้าเว็บ |

| ไฟล์/โฟลเดอร์ | เก็บอะไร |
|---|---|
| `data/final/dataset.csv`, `condition_features.csv` | core 9,210 แถวและ optional values รวม Git |
| `config/modeling/current.json`, `iphone_release_years.json` | candidates, folds, weights, seed, input hashes และ catalog 54 รุ่นจาก Apple |
| `models/asking_price_v2/evaluation.joblib` | fit ก่อน cutoff สำหรับคะแนนย้อนหลัง |
| `models/asking_price_v2/model.joblib`, `metadata.json` | fit ครบสำหรับใช้งาน พร้อม checksum/version/บทบาท |
| `data/intermediate/modeling/asking_price_v2/evaluation/` | actual/prediction/error รายแถวในเครื่อง |
| `docs/modeling.md` | รายงานโมเดลหลักไฟล์เดียว |
| `docs/assets/modeling/` | metadata.json รวม summary/config/folds/selection/provenance/validation/hashes; figures, tables, HTML; history.zip เก็บผลทดลองเดิม |


เวลา pipeline ที่บันทึกล่าสุด {s['duration_seconds']:.1f} วินาที (resume ไม่รวมเวลาก่อนหยุด) เวลา fit ตัวเลือกที่บันทึกรวม {sum(r['fit_seconds'] for r in comparisons):.1f} วินาที ไม่รวมเขียนโค้ด/เตรียม feature

แหล่งนิยาม: [scikit-learn regression metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#regression-metrics), [HGB](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), [Apple iPhone release years](https://support.apple.com/en-us/108044)
{tuning_text}
หน้าที่ไฟล์ทั้งหมดดู [ตารางไฟล์ในโครงการ](project.md)
'''
    detailed = detailed.rstrip() + '\n'
    if report.resolve() == (ROOT / 'docs/assets/modeling').resolve():
        document = ROOT / 'docs/modeling.md'
        detailed_for_docs = detailed.replace('](figures/', '](assets/modeling/figures/').replace('](tables/', '](assets/modeling/tables/').replace('](metadata.json#tuning_review)', '](assets/modeling/metadata.json#tuning_review)')
    else:
        document = None
    if document:
        temporary_document = document.with_suffix('.tmp.md')
        temporary_document.write_text(detailed_for_docs, encoding='utf-8')
        temporary_document.replace(document)
    # Keep a single Markdown document; HTML is an export of the same text.
    temporary_html = report / 'report.tmp.html'
    temporary_html.write_text(html_export(detailed, report), encoding='utf-8')
    temporary_html.replace(report / 'report.html')


def main():
    """Refresh presentation from verified stored predictions; never fit estimators."""
    import csv
    from datetime import datetime, timezone
    from script.modeling.common import metrics
    from script.modeling.split_dataset import dump, sha
    report = ROOT / 'docs/assets/modeling'
    predictions = ROOT / 'data/intermediate/modeling/asking_price_v2/evaluation/retrospective_predictions.csv'
    summary = read_metadata(report, 'summary')
    with (report / 'tables/validation_comparison.csv').open() as handle:
        comparisons = [{k: (v if k == 'name' else float(v)) for k, v in row.items()}
                       for row in csv.DictReader(handle)]
    with predictions.open() as handle:
        rows = list(csv.DictReader(handle))
    if len({row['listing_id'] for row in rows}) != len(rows):
        raise ValueError('Stored prediction IDs repeat')
    actual = [float(row['actual_thb']) for row in rows]
    predicted = [float(row['predicted_thb']) for row in rows]
    for key, value in metrics(actual, predicted).items():
        if abs(value - summary['retrospective'][key]) > 1e-6:
            raise ValueError('Stored predictions differ from recorded metric: ' + key)
    render(report, summary, comparisons, actual, predicted, evaluation_rows=rows, refresh_figures=False)
    write_metadata(report, 'report_refresh', {
        'refreshed_at': datetime.now(timezone.utc).isoformat(), 'training_repeated': False,
        'renderer_sha256': sha(Path(__file__)), 'predictions_sha256': sha(predictions),
        'note': 'Presentation refresh only. Original training metadata and artifact hashes remain unchanged.'})
    write_metadata(report, 'hashes', collect_output_hashes(report))
    hashes = read_metadata(report, 'hashes')
    hashes['../../modeling.md'] = sha(ROOT / 'docs/modeling.md')
    write_metadata(report, 'hashes', hashes)
    print('Refreshed docs/modeling.md and HTML from stored predictions; no retraining')


if __name__ == '__main__':
    main()
