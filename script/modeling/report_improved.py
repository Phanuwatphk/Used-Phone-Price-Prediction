"""One canonical model report with training protocol, metrics and diagnostic figures."""
import base64
import html
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from script.modeling.report import table


def html_export(markdown, report):
    """Render this report's headings, tables and graphs into one portable HTML file."""
    def inline(text):
        escaped = html.escape(text)
        escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
        escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                      lambda m: '<a href="' + m[2] + '">' + m[1] + '</a>'
                      if m[2].startswith('https://') else m[1], escaped)
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
            blocks.append('<h' + level + '>' + inline(match[2]) + '</h' + level + '>')
        elif line.strip():
            blocks.append('<p>' + inline(line) + '</p>')
    if in_table:
        blocks.append('</tbody></table>')
    return '<!doctype html><html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Model V2 report</title><style>body{max-width:1050px;margin:32px auto;padding:0 20px;font-family:sans-serif;line-height:1.7;color:#172033}h2{margin-top:2em}table{border-collapse:collapse;width:100%;font-size:.9em}td,th{border:1px solid #cbd5e1;padding:8px;text-align:left}th{background:#eef2ff}img{max-width:100%;height:auto}pre{overflow:auto;background:#f1f5f9;padding:16px}figure{margin:24px 0}</style></head><body>' + ''.join(blocks) + '</body></html>'


def render(report, s, comparisons, actual, predicted):
    report = Path(report)
    figures = report / 'figures'
    figures.mkdir(exist_ok=True)
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    residual = predicted - actual
    config = json.loads((report / 'config.json').read_text())
    folds = json.loads((report / 'folds.json').read_text())

    def save(name):
        plt.tight_layout()
        for suffix in ['png', 'svg']:
            temporary = figures / (name + '.tmp.' + suffix)
            plt.savefig(temporary, dpi=160, format=suffix)
            temporary.replace(figures / (name + '.' + suffix))
        plt.close()

    ordered = sorted(comparisons, key=lambda r: r['mae_thb'], reverse=True)
    plt.figure(figsize=(10, 6))
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

    e, b, v = s['retrospective'], s['v1_same_cutoff'], s['validation']
    source = [r for r in s['groups'] if r['group'] == 'source']
    source_table = table(['เว็บ', 'n', 'MAE (บาท)', 'RMSE (บาท)', 'R²', 'ภายใน ±20%'],
                         [[r['value'], r['rows'], f'{r["mae_thb"]:,.2f}', f'{r["rmse_thb"]:,.2f}',
                           f'{r["r2"]:.4f}', f'{r["within_20pct"]*100:.2f}%'] for r in source])
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
    from script.modeling.features_v2 import CATEGORICAL, NUMERIC
    detailed = f'''# รายงานโมเดลราคาตั้งขายมือถือ — V2

รายงานหลักเรื่องโมเดล: อ่านวิธีเลือกข้อมูล วิธีเทรน กราฟ ตัววัด ผลแยกกลุ่ม และคำสั่งทำซ้ำได้ในไฟล์นี้ เอกสาร HTML เป็นเนื้อหาเดียวกันสำหรับเปิดใน browser; JSON/CSV เป็นหลักฐานตัวเลข ไม่ใช่คู่มืออีกชุด

## สรุปผลก่อนอ่านรายละเอียด

เลือก **HistGradientBoosting + log(price) + recency half-life 2 ปี** (`{s['selected_model']}`) จาก {len(comparisons)} ตัวเลือกด้วย validation ตามเวลา 2 ช่วง MAE validation **{v['mae_thb']:,.2f} บาท**

เปรียบเทียบย้อนหลังบน **{s['retrospective_rows']} ประกาศเดิม**: MAE ลดจาก **{b['mae_thb']:,.2f}** เป็น **{e['mae_thb']:,.2f} บาท** หรือ **{s['retrospective_mae_improvement_pct']:.2f}%**; R² **{e['r2']:.4f}**; ทำนายใน ±20% ของราคาประกาศได้ **{e['within_20pct']*100:.2f}%**

**ผลนี้เป็นการประเมินย้อนหลังบนชุดเดิมที่เคยเปิดดูระหว่างพัฒนา ไม่ใช่ holdout ใหม่** โมเดลสำหรับใช้งานฝึกครบ {s['deployment_fit_rows']:,} แถวและยังไม่มีคะแนนทดสอบอิสระของตัวที่ฝึกครบ

## 1. เลือกข้อมูลอะไรและตัดอะไรออก

หนึ่งแถวคือหนึ่งประกาศ ราคาเป้าหมายคือ **ราคาตั้งขาย หน่วยบาท** ไม่ใช่ราคาปิดการขาย ใช้ทุกวันที่ใน snapshot ไม่มีการจำกัด 12 เดือน

| ขั้น | ENNXO | Mac2Hand | รวม |
|---|---:|---:|---:|
| ประกาศดิบใน snapshot | 1,381 | 10,220 | 11,601 |
| ผ่าน clean ก่อนคัด EDA | 1,279 | 8,753 | 10,032 |
| ชุดใช้สำหรับโมเดลหลังคัด | 1,202 | 8,008 | 9,210 |

Clean ตรวจรุ่น ความจุ ราคา วันที่และขอบเขตสินค้า อิงรายละเอียดที่มีหลักฐาน เก็บ source/product_id/url/lineage ค่าที่ไม่ระบุหรือขัดกันไม่เดา แยกเครื่องเสีย/ล็อกและแถวที่ไม่ผ่านก่อนรวม; ป้ายสภาพ `new` ไม่ทำให้ถูกตัดอย่างเดียวตามนโยบายโครงการ

EDA ระบุคิวจาก IQR, ข้อความ candidate ซ้ำ และรายการราคาสูงสุด ผู้ใช้เลือกตัดสมาชิกคิวทั้งหมด **822 รหัส** โดยนับ union ของเหตุผลที่ซ้อนกัน ไม่ใช่ยืนยันว่าทั้ง 822 แถวผิดทั้งหมด คัดด้วย `script/preparation/shared/select_model_input.py` ตาม `config/shared/model_input_policy.json` คง raw และเหตุผลไว้

`data/final/dataset.csv` มี 13 คอลัมน์ / 9,210 แถว ข้อมูลส่วนใหญ่เป็น Apple และ Mac2Hand; กลุ่มย่อยไม่สมดุล การคัดใช้ EDA ทั้ง snapshot ก่อน split จึงมี selection bias คะแนนอธิบายชุดหลังคัดนี้ ไม่ใช่ประกาศทุกประเภทบนเว็บ

## 2. ใช้ features และจัดการ missing อย่างไร

ใช้ **22 features**:

- หมวดหมู่ 7 ตัว: `{', '.join(CATEGORICAL)}`
- ตัวเลข/ตัวบ่งชี้ 15 ตัว: `{', '.join(NUMERIC)}`

Features หลักคือเว็บ ยี่ห้อ รุ่น ความจุ สภาพและวันประกาศ เพิ่ม family/tier ของรุ่น ปีเปิดตัว iPhone จาก Apple และอายุรุ่น ณ เดือนประกาศโดยประมาณ ไม่ใช่อายุเครื่องจริง Android ที่ไม่มี catalog คงปีเปิดตัว missing

Battery health %, ประกันวันและกล่องถอดจากข้อความด้วยกฎ เฉพาะคำระบุชัดและค่าเดียว ตรวจ listing_id/source/price ตรง lineage ค่าขัดกันหรือไม่ระบุคง missing; กล่องมี/ไม่มีใช้ 1/0 และไม่ทราบเป็น missing แยกจากศูนย์ ไม่ป้อน title/description ทั้งหมดหรือราคาในข้อความให้โมเดล

One-hot encoding ใช้ unknown category ได้ ตัวเลขเติม median จาก train พร้อมคงคอลัมน์ที่ missing ทั้งหมดตาม imputer แล้ว scale จาก train ของ fold เท่านั้น ไม่เขียนค่าที่เติมกลับลง dataset เก็บ optional values ใน `data/final/condition_features.csv` จับคู่ด้วย listing_id ส่วนราคาเป้าหมาย ID และ URL ไม่ใช้เป็น features

## 3. แบ่ง train / validation / evaluation ตามเวลา

เรียงตามวันประกาศและรหัส ไม่สุ่มประกาศเก่ากับใหม่ปนกัน วันเดียวกันอยู่ฝั่งเดียว ป้องกันเรียนรู้ข้อมูลอนาคตใน preprocessing และน้ำหนักข้อมูล

{fold_table}

Validation สองช่วงรวม **1,054 แถว** จำนวน train ที่ทับกันระหว่าง folds ไม่ใช่ข้อมูลเพิ่ม เกณฑ์เลือกคือ MAE ของ prediction validation ทั้งสองช่วงรวมตามจำนวนแถวจริง

หลังเลือกวิธีแล้ว ฝึก evaluation artifact **8,517 แถวก่อน 2025-01-09** ประเมินบน **693 แถววันที่ 2025-01-09 ถึง 2026-10-06** cutoff เดียวกับ V1 รอบนี้ไม่ใช้ชุด 693 แถวเลือกพารามิเตอร์ แต่เคยเห็นชุดนี้ในการพัฒนาเดิม จึงเรียกการเปรียบเทียบย้อนหลัง

สุดท้ายฝึก operational artifact แยกด้วย **9,210 แถว** เพื่อเรียนรู้ {s['deployment_models']} รุ่นจนถึง {s['deployment_date_max']} การฝึกครบทำให้คะแนนย้อนหลังของ evaluation artifact ไม่ใช่คะแนนอิสระของ operational artifact

## 4. เทรนอย่างไร และเลือกตัวไหน

ทดลอง reference V1, HGB target ราคา/log(price), recency half-life เท่ากัน/2/4 ปี, transfer candidates ที่ลดการพึ่งชื่อรุ่น และ CatBoost depth 6/8 ไม่ได้ทำ exhaustive search ทุกพารามิเตอร์

วิธีชนะ: HGB loss `squared_error` บน log(price), `max_iter=400`, `max_leaf_nodes=31`, `learning_rate=0.07`, `l2_regularization=8`, `early_stopping=False`; seed **{config['seed']}**, threads **{config['threads']}** แปลงกลับด้วย exp ก่อนวัด error เป็นบาท ราคาทำนาย floor ที่ 1 บาทตาม inference เดิม

Recency half-life 2 ปี: น้ำหนักก่อน normalize = max(0.01, 2^(−อายุข้อมูลปี/2)) อายุข้อมูลนับจากวันล่าสุดใน train ของ fold แล้ว normalize ให้เฉลี่ย 1 ไม่ลบข้อมูลเก่า ทดลอง CatBoost 800 iterations, learning rate 0.045, RMSE บน log target, fixed iterations และ `has_time=True`

{compare}

![เปรียบเทียบ validation MAE](figures/validation_comparison.png)

**อ่านกราฟ:** แท่งสั้นคือ MAE ต่ำกว่า ใช้กราฟนี้และตัวเลข validation เลือกวิธี ไม่เลือกด้วยคะแนนชุดย้อนหลัง ตาราง [fold_metrics.csv](tables/fold_metrics.csv) เก็บผลแต่ละ fold เพื่อดูความเปลี่ยนแปลงตามเวลา

## 5. ใช้ตัววัดสถิติอะไร ได้ค่าเท่าไร

กำหนด y = ราคาประกาศจริง, ŷ = ราคาที่ทำนาย ตัววัดทั้งหมดคำนวณหลังแปลงกลับเป็นบาท บน 693 แถวเดียวกันสำหรับ V1/V2

{metrics_table}

MAE คือจำนวนบาทที่คลาดเคลื่อนเฉลี่ย RMSE สูงกว่า MAE เพราะให้น้ำหนัก error ใหญ่ Median absolute error บอกผลทั่วไปที่ไม่ถูกบางแถวลากมาก Bias ติดลบหมายถึงมีแนวโน้มทำนายต่ำ R² ไม่ใช่เปอร์เซ็นต์ accuracy และ MAPE ไม่ใช่อัตราผ่าน ±20%

**มี hypothesis test หรือ p-value หรือไม่:** งานนี้ยังไม่ได้ทำ t-test, ANOVA, Wilcoxon หรือทดสอบนัยสำคัญของความต่างโมเดล จึงไม่มี test statistic/p-value และไม่สรุปว่าดีขึ้นอย่างมีนัยสำคัญทางสถิติ MAE/RMSE/R² เป็น evaluation metrics ไม่ใช่ hypothesis tests การมีเพียง 2 folds และการใช้ test เดิมซ้ำไม่เพียงพอให้ตีความ 34.15% ว่าเป็นหลักฐานอิสระของประสิทธิภาพในอนาคต

## 6. ผลแยกเว็บและยี่ห้อ

{source_table}

จำนวนและส่วนผสมรุ่นต่างกัน จึงไม่ถือว่าคะแนนเว็บหนึ่งดีกว่าเพราะชื่อเว็บอย่างเดียว กลุ่มเล็กไม่ใช้รับรองความแม่นยำ

![MAE ตามยี่ห้อ](figures/retrospective_brand_mae.png)

**อ่านกราฟ:** แสดงเฉพาะยี่ห้อที่มีอย่างน้อย 10 แถว พร้อม n; แท่งสั้นคือ error น้อย ดู [retrospective_by_group.csv](tables/retrospective_by_group.csv) สำหรับทุกยี่ห้อ ปี สภาพ และรุ่นเคยเห็น/ไม่เคยเห็น กลุ่มน้อยกว่า 10 ยังคงอยู่ในตาราง ไม่ถูกลบจากผลประเมิน

## 7. กราฟวิเคราะห์ error

![ราคาจริงและราคาทำนาย](figures/retrospective_actual_vs_predicted.png)

**อ่านกราฟ:** จุดใกล้เส้นประคือทำนายใกล้ราคาประกาศ จุดใต้เส้นคือทำนายต่ำ จุดเหนือเส้นคือสูง ไม่ได้เทียบกับราคาขายสำเร็จ

![Residual กับราคาประกาศ](figures/retrospective_residuals.png)

**อ่านกราฟ:** residual = ŷ−y เส้นศูนย์คือถูกพอดี จุดต่ำกว่าศูนย์คือทำนายต่ำ ใช้ดูว่าราคาสูงมี error ทางเดียวมากหรือไม่ ไม่ได้ทดสอบว่าข้อสมมติ residual ผ่านทางสถิติ

![การกระจาย absolute error](figures/retrospective_error_distribution.png)

**อ่านกราฟ:** แกนนอนคือ error เป็นบาท แกนตั้งคือจำนวนประกาศ หางด้านขวาคือกลุ่มที่คลาดเคลื่อนสูง ไม่ใช่ confidence interval ของราคาทำนาย

## 8. ข้อจำกัดและข้อสรุปที่ใช้ได้

V2 ให้ MAE ต่ำกว่า V1 ในการเปรียบเทียบย้อนหลังเดียวกัน แต่มีอคติจากการคัดข้อมูลก่อน split ข้อมูลเว็บ/รุ่น/สภาพไม่สมดุล รุ่นใหม่/Android มีข้อจำกัดและสภาพจากผู้ขายอาจไม่ครบ ไม่มีการยืนยันว่าเป็นเครื่องคนละเครื่องทางกายภาพ

Catalog Apple รวบรวมภายหลัง ใช้ปีเปิดตัวที่ทราบ ณ วันประกาศ ไม่อ้างว่าระบบรู้ข้อมูลรุ่นที่ยังไม่เปิดตัวได้ในอดีต อายุมีความละเอียดระดับปี วันนอกช่วงฝึกหรือค่าที่ไม่ทราบมี coverage flags ซึ่งไม่ใช่ค่าความเชื่อมั่นทางสถิติ

โมเดลพร้อมทดลองประเมิน **ราคาตั้งขายของเครื่องปกติ** ก่อนรับรองประสิทธิภาพจริงควรประเมินชุดใหม่หลัง 2026-10-06 ที่ไม่เคยใช้พัฒนา ไม่อ้างราคาปิดขายหรือความแม่นยำ 100%

## 9. รันอะไร อ่านอะไร และผลเก็บที่ไหน

| สคริปต์ใน script/modeling/ | หน้าที่ / input | output |
|---|---|---|
| `prepare_features_v2.py` | อ่าน core/lineage/full-text และตรวจหลักฐาน ถอด optional claims | enrichment dataset/audit ใน intermediate (ต้องมีหลักฐาน private) |
| `rebuild_features_v2.py` | core + public condition sidecar ตรวจ hashes | enriched CSV byte ตรงรอบจริง ไม่ต้องใช้ raw |
| `features_v2.py` | สร้าง 22 features จากข้อมูลและ frozen catalog | โมดูลประกอบ ไม่รันแยก |
| `train_improved.py` | 2 temporal folds เลือก → evaluation → fit ครบ | artifacts, reports และ predictions รายแถว |
| `report_improved.py` | อ่านผลจริง/ตัวเลขสร้างรายงานนี้และกราฟ | docs/modeling.md, HTML และ figures |
| `predict.py` | ตรวจ checksum โหลด artifact และทำนาย | JSON หน้าจอ หรือ --output |

| ไฟล์/โฟลเดอร์ | เก็บอะไร |
|---|---|
| `data/final/dataset.csv`, `condition_features.csv` | core 9,210 แถวและ optional values รวม Git |
| `config/modeling/improved.json`, `iphone_release_years.json` | candidates, folds, weights, seed, input hashes และ catalog 54 รุ่นจาก Apple |
| `models/asking_price_v2/evaluation.joblib` | fit ก่อน cutoff สำหรับคะแนนย้อนหลัง |
| `models/asking_price_v2/model.joblib`, `metadata.json` | fit ครบสำหรับใช้งาน พร้อม checksum/version/บทบาท |
| `data/intermediate/modeling/asking_price_v2/evaluation/` | actual/prediction/error รายแถวในเครื่อง |
| `docs/modeling.md` | รายงานโมเดลหลักไฟล์เดียว |
| `docs/assets/modeling/asking_price_v2/` | figures PNG/SVG, tables CSV, HTML, config/folds/selection, summary.json, validation และ hashes |

```bash
# หลัง clone: rebuild จาก public core + sidecar แล้วเทรน
.venv/bin/python -B script/modeling/rebuild_features_v2.py
.venv/bin/python -u -B script/modeling/train_improved.py
# ใช้ผลตัวเลือกที่ทำครบต่อเมื่อหยุด และ config/hash เดิม
.venv/bin/python -u -B script/modeling/train_improved.py --resume
# ทำนายด้วย operational artifact
.venv/bin/python -B script/modeling/predict.py --source mac2hand --brand Apple --model 'iPhone 16 Pro' --storage-gb 256 --condition used --published-at 2026-10-06 --battery-health-pct 90
```

Batch ใช้ --input-csv และ --output; รองรับ absolute path จาก directory อื่น V2 model.joblib กับ metadata.json รวมใน Git สำหรับ deploy; evaluation/V1 binary, raw, ข้อความต้นทาง และ predictions รายแถวเก็บในเครื่อง; code/config/core/sidecar/รายงานผลรวมขึ้น Git ได้ เวลา pipeline ที่บันทึกล่าสุด {s['duration_seconds']:.1f} วินาที (resume ไม่รวมเวลาก่อนหยุด) เวลา fit ตัวเลือกที่บันทึกรวม {sum(r['fit_seconds'] for r in comparisons):.1f} วินาที ไม่รวมเขียนโค้ด/เตรียม feature

แหล่งนิยาม: [scikit-learn regression metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#regression-metrics), [HGB](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), [Apple iPhone release years](https://support.apple.com/en-us/108044)
'''
    if report.resolve() == (ROOT / 'docs/assets/modeling/asking_price_v2').resolve():
        document = ROOT / 'docs/modeling.md'
        detailed_for_docs = detailed.replace('](figures/', '](assets/modeling/asking_price_v2/figures/').replace('](tables/', '](assets/modeling/asking_price_v2/tables/')
    else:
        document = report / 'report.md'
        detailed_for_docs = detailed
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
    from script.modeling.train_models import metrics
    from script.modeling.split_dataset import dump, sha
    report = ROOT / 'docs/assets/modeling/asking_price_v2'
    predictions = ROOT / 'data/intermediate/modeling/asking_price_v2/evaluation/retrospective_predictions.csv'
    summary = json.loads((report / 'summary.json').read_text())
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
    render(report, summary, comparisons, actual, predicted)
    dump(report / 'report_refresh.json', {
        'refreshed_at': datetime.now(timezone.utc).isoformat(), 'training_repeated': False,
        'renderer_sha256': sha(Path(__file__)), 'predictions_sha256': sha(predictions),
        'note': 'Presentation refresh only. Original training metadata and artifact hashes remain unchanged.'})
    dump(report / 'output_hashes.json', {str(p.relative_to(report)): sha(p) for p in report.rglob('*')
                                       if p.is_file() and p.name not in ('output_hashes.json', 'progress.json')})
    hashes = json.loads((report / 'output_hashes.json').read_text())
    hashes['../../../modeling.md'] = sha(ROOT / 'docs/modeling.md')
    dump(report / 'output_hashes.json', hashes)
    print('Refreshed docs/modeling.md, HTML export and five diagnostic figures; no retraining')


if __name__ == '__main__':
    main()
