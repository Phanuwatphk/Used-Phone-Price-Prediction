"""One canonical model report with training protocol, metrics and diagnostic figures."""
import base64
import csv
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



from script.artifacts import collect_output_hashes, read_metadata, write_metadata

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
        elif match := re.fullmatch(r'<a id="([\w-]+)"></a>', line):
            blocks.append('<a id="' + html.escape(match[1], quote=True) + '"></a>')
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
            if suffix == 'svg':
                temporary.write_text('\n'.join(line.rstrip() for line in temporary.read_text().splitlines()) + '\n')
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
    e, b = s['retrospective'], s['v1_same_cutoff']
    from script.modeling.model_v2.features_v2 import CATEGORICAL, NUMERIC
    dropped = set(selected.get('drop_features', []))
    categorical = [field for field in CATEGORICAL if field not in dropped and
                   (field != 'source' or not selected.get('source_free'))]
    numeric = [field for field in NUMERIC if field not in dropped]
    fold_table = table(['ช่วง', 'Train', 'Train ถึง', 'Validation', 'เริ่ม', 'ถึง', 'วัน'],
        [[r['fold'], f"{r['train_rows']:,}", r['train_max'], f"{r['validation_rows']:,}",
          r['window_start'], r['window_end'], r['window_days']] for r in folds])
    eligibility = {item['name']: item.get('eligible_for_selection', True) for item in config['candidates']}
    compare = table(['สัดส่วน HGB : CatBoost', 'Validation MAE (บาท)', 'RMSE (บาท)'],
        [[f"{(1-candidate['blend_weights'][1])*100:.0f} : {candidate['blend_weights'][1]*100:.0f}",
          f"{row['mae_thb']:,.2f}", f"{row['rmse_thb']:,.2f}"]
         for row in sorted(comparisons, key=lambda row: row['mae_thb'])
         if eligibility[row['name']]
         for candidate in config['candidates'] if candidate['name'] == row['name']])
    metric_specs = [('MAE (บาท)', 'mae_thb'), ('RMSE (บาท)', 'rmse_thb'),
                    ('R²', 'r2'), ('ภายใน ±20%', 'within_20pct')]
    def value(row, key):
        return (f"{row[key]*100:.2f}%" if key == 'within_20pct' else
                f"{row[key]:.4f}" if key == 'r2' else f"{row[key]:,.2f}")
    metrics_table = table(['ตัวชี้วัด', 'V1 reference', 'V2'],
        [[label, value(b, key), value(e, key)] for label, key in metric_specs])
    source_table = table(['เว็บไซต์', 'จำนวน', 'MAE (บาท)', 'ภายใน ±20%'],
        [[r['value'], r['rows'], value(r, 'mae_thb'), value(r, 'within_20pct')]
         for r in s['groups'] if r['group'] == 'source'])
    coverage_table = table(['รุ่นในชุดประเมิน', 'จำนวน', 'MAE (บาท)', 'ภายใน ±20%'],
        [['เคยอยู่ในชุดฝึก' if r['value'] == 'seen' else 'ไม่เคยอยู่ในชุดฝึก', r['rows'],
          value(r, 'mae_thb'), value(r, 'within_20pct')]
         for r in s['groups'] if r['group'] == 'model_coverage'])
    platform = s['platform_evaluation']
    platform_table = table(['กลุ่ม', 'จำนวน', 'MAE (บาท)', 'RMSE (บาท)', 'R²', 'ภายใน ±20%'],
        [[label, platform['groups'][name]['rows'],
          *[value(platform['groups'][name], key) for _, key in metric_specs]]
         for name, label in [('iOS', 'iOS (iPhone)'), ('Android', 'Android (อนุมาน)'),
                             ('unconfirmed', 'ยังไม่ยืนยัน OS')]
         if name in platform['groups']])
    drift = s['data_drift']
    apple = drift['training_brands'].get('Apple', 0)
    from script.modeling.model_v2.report_learning_curve import render_learning_curve
    learning_curve_section = render_learning_curve(report, config, folds, selected)
    from script.modeling.model_v2.correlation_matrix import render_section as render_correlation
    correlation_section = render_correlation(report, selected)
    detailed = f'''# โมเดลประเมินราคาตั้งขายมือถือมือสอง — V2

ใช้กับเครื่องที่ทำงานปกติ เป้าหมายคือราคาประกาศขาย หน่วยบาท

**ผลประเมินย้อนหลัง {s['retrospective_rows']:,} ประกาศ:** MAE **{e['mae_thb']:,.2f} บาท** · R² **{e['r2']:.4f}** · คลาดเคลื่อนไม่เกิน ±20% **{e['within_20pct']*100:.2f}%**

ผลนี้ไม่ใช่ holdout ใหม่ ชุดประเมินเคยใช้ระหว่างพัฒนา โมเดลใช้งานที่ฝึกครบยังไม่มีคะแนนทดสอบอิสระ

## 1. ข้อมูลที่ใช้

ใช้ข้อมูลมือถือมือสอง **{s['deployment_fit_rows']:,} ประกาศ** จาก ENNXO และ Mac2Hand หลังทำความสะอาดและคัดเลือก

สภาพเป็นข้อมูลที่ผู้ขายระบุในตลาดมือสอง ไม่ใช่ผลตรวจเครื่องจริง รายละเอียดการเตรียมข้อมูลอยู่ใน [รายงานข้อมูล](data.md#stage-model_input)

## 2. ฟีเจอร์และการเตรียมข้อมูล

ใช้ **{len(categorical)+len(numeric)} ฟีเจอร์**

| กลุ่ม | ฟีเจอร์ |
|---|---|
| หมวดหมู่ | `{', '.join(categorical)}` |
| ความจุและวันประกาศ | `storage_gb, publication_days` |
| ปีเปิดตัวและอายุรุ่น | `release_year, model_age_years, release_known` |
| แบตเตอรี่และกล่อง | `battery_health_pct, battery_missing, box_mentioned, box_missing` |

อายุรุ่นคำนวณจากปีเปิดตัว ไม่ใช่อายุเครื่องจริง บัญชีปีเปิดตัวครอบคลุม iPhone; รุ่นที่ไม่มีข้อมูลคงค่าขาดหาย

แบตเตอรี่และกล่องใช้เฉพาะข้อความที่ระบุชัด ค่าที่ไม่ทราบแยกจากศูนย์ HGB ใช้ one-hot encoding และเติมค่าตัวเลขด้วยมัธยฐานจาก train แต่ละช่วง ส่วน CatBoost จัดการหมวดหมู่และค่าตัวเลขขาดหายภายในโมเดล

| ไม่ใช้ | เหตุผล |
|---|---|
| `source` | เว็บไซต์ไม่ใช่คุณสมบัติเครื่อง เก็บไว้ตรวจที่มาและรายงานแยกกลุ่ม |
| `condition` | คงที่ในชุดฝึกรอบนี้ |
| ประกัน | มีค่าเพียง 157 จาก 9,100 แถว |
| ตัวแปรซ้ำและเลขจากชื่อรุ่น | ซ้ำกับข้อมูลเดิมหรือเปรียบเทียบข้ามยี่ห้อไม่ได้ |
| ราคาเป้าหมาย รหัส URL และข้อความเต็ม | ไม่ใช้เป็นตัวแปรทำนาย |

{correlation_section}## 3. การแบ่งข้อมูลตามเวลา

ใช้ expanding-window validation **{len(folds)} ช่วง ช่วงละ {config['validation_scheme']['window_days']} วันเท่ากัน** กำหนดช่วงต่อเนื่องย้อนจากวันเริ่มประเมินย้อนหลัง {config['retrospective_test_start']} รวม {len(folds)*config['validation_scheme']['window_days']} วัน โดยไม่ใช้ราคาเลือกขอบเขต Train ใช้ข้อมูลก่อนแต่ละช่วงและขยายตามเวลา ประกาศวันเดียวกันอยู่ฝั่งเดียวกัน

{fold_table}

จำนวนประกาศแต่ละช่วงต่างกันตามข้อมูลที่เกิดขึ้นจริง แม้ระยะเวลาเท่ากัน Validation รวม **{sum(fold['validation_rows'] for fold in folds):,} แถว** เลือกน้ำหนักด้วย MAE ของผลทำนายรวมทุกแถว ไม่เฉลี่ยคะแนนแต่ละช่วงเท่ากัน

| ขั้นตอนหลังเลือกน้ำหนัก | ข้อมูล |
|---|---|
| ฝึกโมเดลประเมินย้อนหลัง | **{s['evaluation_fit_rows']:,} แถวก่อน {config['retrospective_test_start']}** รวม train และ validation |
| ประเมินย้อนหลัง | **{s['retrospective_rows']:,} แถววันที่ {config['retrospective_test_start']} ถึง {s['deployment_date_max']}** |
| ฝึกโมเดลใช้งาน | **{s['deployment_fit_rows']:,} แถว** ครอบคลุม {s['deployment_models']} รุ่น |

การฝึกใหม่ใช้ข้อมูลก่อนวันตัดครบหลังเลือกน้ำหนักแล้ว ส่วนโมเดลใช้งานรวมข้อมูลล่าสุดด้วย คะแนนย้อนหลังจึงเป็นของโมเดลประเมิน ไม่ใช่คะแนนทดสอบโมเดลที่ฝึกครบ

## 4. วิธีฝึกและเลือกน้ำหนัก

ใช้ gradient boosting สองแบบ: HGB แบ่งค่าตัวเลขเป็นช่วงเพื่อสร้างต้นไม้ และ CatBoost รองรับตัวแปรหมวดหมู่โดยตรง ทั้งสองเรียนรู้จาก log ราคา แล้วแปลงกลับเป็นบาทก่อนเฉลี่ย

| การตั้งค่า | HGB | CatBoost |
|---|---|---|
| จำนวนรอบ | 400 | 800 |
| Learning rate | 0.07 | 0.045 |
| ความซับซ้อนต้นไม้ | สูงสุด 31 ใบ | depth 6 |
| การตั้งค่าเพิ่มเติม | L2 = 8; ไม่ใช้ early stopping | `has_time=True` |

ให้น้ำหนักข้อมูลล่าสุดมากกว่า โดยน้ำหนักลดครึ่งหนึ่งทุก 2 ปี อ้างอิงวันล่าสุดใน train ของแต่ละช่วง; seed = {config['seed']}

กำหนดฟีเจอร์และพารามิเตอร์หลักก่อนประเมิน ใช้ validation เลือกเฉพาะสัดส่วนผสม 3 แบบ ไม่ได้ค้นหาพารามิเตอร์ทุกค่า ตัวเปรียบเทียบ V1, source และประกันอยู่ใน [ผลทดลองทั้งหมด](assets/modeling/tables/validation_comparison.csv)

{compare}

เลือก **HGB {selected['blend_weights'][0]*100:.0f}% + CatBoost {selected['blend_weights'][1]*100:.0f}%** จาก MAE รวมบน validation {len(folds)} ช่วง


![MAE ของตัวเลือกบน validation](figures/validation_comparison.png)

## 5. ผลประเมินย้อนหลัง

เปรียบเทียบ V1 reference ที่ฝึกใหม่กับ V2 บนข้อมูลและวันตัดเดียวกัน จำนวน {s['retrospective_rows']:,} ประกาศ

{metrics_table}

MAE ลดลง **{s['retrospective_mae_improvement_pct']:.2f}%**; R² ไม่ใช่ร้อยละความแม่นยำ ไม่มีการทดสอบนัยสำคัญทางสถิติ

![ราคาประกาศกับราคาทำนาย](figures/retrospective_actual_vs_predicted.png)

![ความคลาดเคลื่อน: ราคาทำนาย − ราคาประกาศ](figures/retrospective_residuals.png)

{learning_curve_section}## 6. ผลแยกเว็บไซต์และความครอบคลุมรุ่น

{source_table}

{coverage_table}

เว็บไซต์และรุ่นมีส่วนผสมข้อมูลต่างกัน จึงไม่ตีความความต่างของคะแนนเป็นผลจากเว็บไซต์โดยตรง ดู [ผลแยก Android และ iOS](#7-ผลการประเมินแยก-android-และ-ios)

![MAE แยกยี่ห้อที่มีอย่างน้อย 10 ประกาศ](figures/retrospective_brand_mae.png)

## 7. ผลการประเมินแยก Android และ iOS

{platform_table}

อนุมานกลุ่มจากยี่ห้อและรุ่น เนื่องจากไม่มีข้อมูล OS ที่ตรวจยืนยัน กลุ่มยังไม่ยืนยัน OS ได้แก่ {', '.join(platform['unconfirmed_brands'])}

ชุดฝึกโมเดลประเมินมี Apple {apple:,}/{s['evaluation_fit_rows']:,} แถว ({apple/s['evaluation_fit_rows']:.2%}) และข้อมูลปีเปิดตัวมีเฉพาะ iPhone ผล Android ต่ำกว่าจึงอาจเกี่ยวข้องกับข้อมูลที่น้อยและความครอบคลุมรุ่นที่ต่างกัน ยังไม่พิสูจน์สาเหตุ ควรเพิ่มข้อมูล Android โดยเฉพาะรุ่นใหม่และประเมินช่วงเวลาใหม่

## 8. ข้อจำกัด

- การคัด 822 แถวอาศัย EDA ก่อนแบ่งข้อมูล จึงมีความเอนเอียงจากการคัดเลือก และไม่ยืนยันว่าทุกแถวที่ตัดเป็นข้อมูลผิด
- ชุดประเมินย้อนหลังเคยใช้ระหว่างพัฒนา จึงยังสรุปว่าไม่มี overfitting หรือรับรองผลในอนาคตไม่ได้ ต้องประเมินข้อมูลใหม่ที่ไม่เคยใช้พัฒนา
- ข้อมูลเก่าและ Apple มีสัดส่วนสูง รุ่นที่ไม่เคยพบให้ความคลาดเคลื่อนมากกว่า ผลรวมไม่รับรองทุกรุ่น
- ไม่มีราคาปิดขาย สภาพที่ตรวจจริง ประวัติซ่อม หรืออายุเครื่องจริง โมเดลไม่รองรับเครื่องเสียหรือล็อก

## 9. สคริปต์และหลักฐาน

| รายการ | หน้าที่ |
|---|---|
| `script/modeling/model_v2/rebuild_features_v2.py` | สร้างข้อมูลฟีเจอร์จากข้อมูลต้นทางและ sidecar |
| `script/modeling/model_v2/train_improved.py` | แบ่งเวลา เลือกน้ำหนัก ฝึกโมเดลประเมินและโมเดลใช้งาน |
| `script/modeling/model_v2/learning_curve.py` | ฝึกใหม่ 5 ขนาดบนชุด train ของช่วงล่าสุด ใช้ validation ชุดเดิมทุกขนาด |
| `script/modeling/model_v2/correlation_matrix.py` | คำนวณ Pearson correlation ของฟีเจอร์ตัวเลขและราคาจากชุดฝึกก่อนประเมินย้อนหลัง |
| `config/modeling/current.json` | พารามิเตอร์ วันตัด และตัวเลือกที่ทดลอง |
| `models/asking_price_v2/evaluation.joblib` | โมเดลสำหรับผลประเมินย้อนหลัง |
| `models/asking_price_v2/model.joblib` | โมเดลใช้งานที่ฝึกครบ |

หลักฐาน: [ผลแต่ละช่วง](assets/modeling/tables/fold_metrics.csv) · [ผลแยกกลุ่ม](assets/modeling/tables/retrospective_by_group.csv) · [ข้อมูลกำกับ](assets/modeling/metadata.json) · [โครงสร้างโครงการ](project.md)

## 10. ประวัติการพัฒนาโมเดล

| เวอร์ชัน | บทบาท |
|---|---|
| V1 | โมเดลพื้นฐาน; หลักฐานใน `docs/assets/modeling/history.zip` |
| V2 | โมเดลใช้งานปัจจุบัน HGB + CatBoost จำนวน 13 ฟีเจอร์ |

การทดลองฟีเจอร์และน้ำหนักโมเดลเป็นการพัฒนาภายใน V2
'''
    detailed = detailed.rstrip() + '\n'
    if report.resolve() == (ROOT / 'docs/assets/modeling').resolve():
        document = ROOT / 'docs/modeling.md'
        detailed_for_docs = detailed.replace('](figures/', '](assets/modeling/figures/').replace('](tables/', '](assets/modeling/tables/')
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
