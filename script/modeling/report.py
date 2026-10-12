"""Aggregate model evaluation reports; per-listing predictions remain in intermediate."""
import html
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from script.artifacts import write_metadata

def table(headers, rows):
    return '| ' + ' | '.join(headers) + ' |\n|' + '|'.join(['---'] * len(headers)) + '|\n' + '\n'.join('| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows) + '\n'


def render_report(report, summary, metadata, comparisons, actual, predicted):
    figures = report / 'figures'
    figures.mkdir(exist_ok=True)
    def save(name):
        plt.tight_layout()
        plt.savefig(figures / (name + '.png'), dpi=160)
        plt.savefig(figures / (name + '.svg'))
        plt.close()
    ordered = sorted(comparisons, key=lambda r: r['mae_thb'], reverse=True)
    plt.figure(figsize=(10, 7))
    plt.barh([r['name'] for r in ordered], [r['mae_thb'] for r in ordered])
    plt.xlabel('Validation MAE (THB; lower is better)')
    save('validation_comparison')
    plt.figure(figsize=(6, 6))
    plt.scatter(actual, predicted, s=14, alpha=.4)
    upper = max(max(actual), max(predicted)) * 1.04
    plt.plot([0, upper], [0, upper], color='black', linestyle='--')
    plt.xlabel('Actual asking price (THB)'); plt.ylabel('Predicted asking price (THB)')
    save('test_actual_vs_predicted')
    plt.figure(figsize=(8, 4))
    plt.scatter(actual, predicted - actual, s=12, alpha=.4)
    plt.axhline(0, color='black', linestyle='--')
    plt.xlabel('Actual asking price (THB)'); plt.ylabel('Prediction minus actual (THB)')
    save('test_residuals')
    plt.figure(figsize=(7, 4))
    groups = [g for g in summary['test_groups'] if g['group'] == 'source']
    plt.bar([f'{g["value"]} (n={g["rows"]})' for g in groups], [g['mae_thb'] for g in groups])
    plt.ylabel('Test MAE (THB)')
    save('test_by_source')
    evaluation = summary['test']
    split_table = table(['ชุด', 'จำนวน', 'ช่วงประกาศ', 'ENNXO / Mac2Hand'], [[k, v['rows'], v['date_min'] + ' ถึง ' + v['date_max'], str(v['source_counts'].get('ennxo', 0)) + ' / ' + str(v['source_counts'].get('mac2hand', 0))] for k, v in summary['split'].items() if k in ('train', 'validation', 'test')])
    source_table = table(['เว็บ', 'Test', 'MAE (บาท)', 'RMSE (บาท)', 'คลาดเคลื่อนไม่เกิน 20%'], [[g['value'], g['rows'], f'{g["mae_thb"]:,.0f}', f'{g["rmse_thb"]:,.0f}', f'{g["within_20pct"]*100:.1f}%'] for g in groups])
    coverage = [g for g in summary['test_groups'] if g['group'] == 'model_coverage']
    coverage_table = table(['รุ่น', 'Test', 'MAE (บาท)'], [[g['value'], g['rows'], f'{g["mae_thb"]:,.0f}'] for g in coverage])
    short = f'''# ผลโมเดลรอบแรก

เทรนแล้วจากชุด 9,210 แถว โมเดลที่ได้ validation MAE ต่ำสุดใน {len(comparisons)} ตัวเลือกคือ **{summary['selected_model']}** จากนั้นฟิตใหม่ด้วย train + validation 8,517 แถว และประเมิน test 693 แถวที่กันไว้

**Test MAE {evaluation['mae_thb']:,.0f} บาท · RMSE {evaluation['rmse_thb']:,.0f} บาท · R² {evaluation['r2']:.3f}**
ราคาทำนายอยู่ใน ±20% ของราคาประกาศ {evaluation['within_20pct']*100:.1f}% ของ test; MAE ดีขึ้นจาก median baseline {summary['mae_improvement_pct']:.1f}%

{split_table}
{source_table}
ใช้ทำนาย **ราคาตั้งขาย** ไม่ใช่ราคาซื้อขายสำเร็จ ข้อมูลเก่ามากและสัดส่วนเว็บ/ยี่ห้อเปลี่ยนตามเวลา รุ่นที่ไม่เคยอยู่ในชุดฝึก {summary['split']['test']['unseen_model_rows_vs_final_fit']} แถวใน test ต้องอ่านผลแยกกลุ่มก่อนใช้งาน คะแนนนี้ใช้กับชุดที่ตัดคิว EDA ออกแล้ว การคัดเกิดก่อนแบ่งข้อมูลจึงมี selection bias

อ่าน [รายงานรายละเอียด](report.md) และ [ตัวเลขทั้งหมด](summary.json) โมเดลอยู่ `{summary['model_file']}` ใช้ `script/modeling/predict.py` สำหรับทำนาย ยังเก็บ test แยกจากข้อมูลฝึกของโมเดลส่งมอบ
'''
    # Keep generated report usable with alternative output paths/datasets too.
    short = short.replace('8,517 แถว', f"{summary['split']['train']['rows'] + summary['split']['validation']['rows']:,} แถว").replace('test 693 แถว', f"test {evaluation['rows']:,} แถว")
    comparison_table = table(['ตัวเลือก', 'Validation MAE', 'RMSE', 'จำนวนต้นไม้ที่เลือก', 'เวลา fit (วินาที)'], [[r['name'], f'{r["mae_thb"]:,.2f}', f'{r["rmse_thb"]:,.2f}', r['iterations'] or '—', r['fit_seconds']] for r in sorted(comparisons, key=lambda r: r['mae_thb'])])
    detailed = short + f'''
## วิธีทดลองและป้องกันข้อมูลรั่ว

1. ตรึง CSV ด้วย SHA-256 `{metadata['dataset_sha256']}` และประกาศรายการโมเดล/พารามิเตอร์ใน `config/modeling/experiments.json#baseline` ก่อนวัด test
2. เรียงตามวันที่และรหัสประกาศ แบ่งประมาณ 85%/7.5%/7.5%; วันที่เดียวกันอยู่ชุดเดียว เหตุผลที่เลือกสัดส่วนนี้คือ train ต้องมีทั้งสองเว็บ ช่วง 70–80% แรกมีเพียง Mac2Hand
3. ฟิต encoding/scaling เฉพาะ train ไม่ส่งราคา รหัสสินค้า URL หรือ snapshot เข้าเป็น feature สร้างความจุ รุ่น/ตระกูลรุ่น และเวลาประกาศด้วยกฎที่ไม่ใช้ target
4. เปรียบเทียบ median, Ridge, Extra Trees, HistGradientBoosting และ CatBoost; Ridge/boosting บางตัวทดลอง log(price) โดยแปลงกลับเป็นบาทก่อนวัด MAE CatBoost ใช้ categorical features โดยตรง และ `has_time=True`; early stopping ใช้ validation MAE เท่านั้น จำกัดสูงสุด 1,200 iterations
5. เลือก validation MAE ต่ำสุด จำนวน iterations ที่เลือกถูกตรึงก่อน refit train + validation ไม่มี early stopping หรือ tuning จาก test ประเมินเฉพาะผู้ชนะและ median baseline ที่กำหนดไว้ล่วงหน้า
6. 保存โมเดลและตรวจโหลดกลับแล้วให้ผลตรงเดิม test ยังคงกันไว้นอก artifact ไม่ใช้ผล test เพื่อแก้พารามิเตอร์รอบนี้

จำนวนแถวต่อช่วงไม่เท่ากันเพราะกันวันที่ประกาศทั้งวัน ไม่มี seed ในการแบ่งเวลา seed=42 ใช้กับอัลกอริทึมที่มี randomness ไม่ทำ random split หรือ random cross-validation; validation ช่วงเดียวเหมาะกับการส่งมอบรอบแรก แต่ยังไม่ใช่การรับรองเสถียรภาพทุกช่วงตลาด

## ผลเลือกโมเดล

{comparison_table}
![Validation comparison](figures/validation_comparison.png)

## ผล test และขอบเขตที่เรียนรู้

MAE คือค่าเฉลี่ยความผิดพลาดเป็นบาท RMSE ให้น้ำหนักกับความผิดพลาดก้อนใหญ่ ส่วน R² เทียบความแปรปรวนกับค่าเฉลี่ย test; MAPE ให้น้ำหนักกับของราคาถูกมากกว่าจึงไม่ใช้เลือกโมเดล Median absolute error = {evaluation['median_absolute_error_thb']:,.0f} บาท, MAPE = {evaluation['mape_pct']:.1f}%, bias = {evaluation['bias_thb']:,.0f} บาท (บวกหมายถึงทำนายแพงกว่า)

{coverage_table}
![Actual versus predicted](figures/test_actual_vs_predicted.png)
![Residuals](figures/test_residuals.png)
![By source](figures/test_by_source.png)

ตาราง [test_by_group.csv](tables/test_by_group.csv) มี source, brand, ปี, condition, รุ่นเคยเห็น/ไม่เคยเห็น และ brand:model รวมจำนวน MAE/RMSE/median error/R²/MAPE/bias กลุ่มเล็กมีความไม่แน่นอนสูง ไม่ตีความค่า R² จากกลุ่มแถวเดียว

## ข้อจำกัดและสิ่งที่ยังไม่รับรอง

- การตัด 822 แถวทำจาก EDA ทั้งชุดก่อนแบ่ง โดยรวมแถวที่ราคาผิดปกติและข้อความอาจซ้ำ คะแนนอาจดีกว่าการรับประกาศใหม่ทุกประเภท; การคัดไม่ใช่หลักฐานว่าแถวที่ตัดผิดจริง
- ทั้งชุดเป็น Apple ประมาณ 92% และเก่าครอบคลุม 2010–2026; train มี ENNXO เพียง 202 แถวก่อน validation สัดส่วนกลุ่มเปลี่ยนชัดเมื่อเวลาเดินหน้า ผลรวมจึงแทนทุกยี่ห้อ/เว็บไม่ได้
- test มีรุ่นใหม่ที่ไม่เคยฝึกและประกาศหลังวันฝึกสูงสุด โมเดล tree ไม่รับรองการ extrapolate เทคโนโลยีหรือระดับราคาอนาคต; CLI แสดง coverage flags แทนการซ่อนข้อจำกัด
- ตรวจรหัส/URL ซ้ำและกันวันประกาศแล้ว แต่ไม่มี serial number/ผู้ขายที่เชื่อถือได้สำหรับยืนยันเครื่องเดียวกันข้ามเว็บ จึงไม่รับรองว่าไม่มีเครื่องซ้ำทางกายภาพ
- condition คือค่าผู้ขายเลือก อาจมี new ในหมวดมือสองตามนโยบายผู้ใช้ ไม่มี battery health, warranty, ประวัติซ่อม/ราคาปิดขายที่ครบและตรวจยืนยันได้
- ผล test ใช้ประเมินโมเดลรอบนี้แล้ว หากปรับโมเดลจากข้อค้นพบนี้ควรมี holdout ใหม่หรือ rolling temporal evaluation ไม่ใช้ test เดิมเพื่ออ้างผลใหม่ที่เป็นอิสระ

## สคริปต์และไฟล์ส่งมอบ

| ที่อยู่ | เก็บอะไร |
|---|---|
| `script/modeling/features.py` | ตรวจ input และสร้าง 12 features จากหกฟิลด์ที่ทราบตอนประกาศ |
| `script/modeling/split_dataset.py` | อ่าน CSV ตรึง hash แบ่งวันตามเวลา ตรวจ ID/URL และเขียน split |
| `script/modeling/train_models.py` | ทดลองตาม config เลือก/refit/test บันทึก artifact และผลตรวจ |
| `script/modeling/predict.py` | โหลด artifact ตรวจ checksum แล้วทำนายพร้อม coverage flags |
| `script/modeling/report.py` | เขียนรายงานสรุป/รายละเอียด HTML กราฟและตารางรวม |
| `data/intermediate/modeling/<รอบ>/split/` | train.csv, validation.csv, test.csv, assignments.csv, summary/validation/hashes JSON |
| `data/intermediate/modeling/<รอบ>/*predictions.csv` | ราคาจริง/ทำนาย/ความผิดพลาดรายแถว เก็บในเครื่อง |
| `models/<รอบ>/` | model.joblib (ตัวทำนาย + สัญญา feature), model.cbm เมื่อเป็น CatBoost, metadata.json |
| `docs/assets/modeling/<รอบ>/` | summary/report, HTML, config, selection, metrics, metadata, validation และ output hashes |
| `docs/assets/modeling/<รอบ>/figures/` | กราฟ PNG/SVG 4 ชนิด |
| `docs/assets/modeling/<รอบ>/tables/` | ผล validation ทุกตัว และ test รวม/แยกกลุ่ม |

เวลา training pipeline {metadata['duration_seconds']:.1f} วินาที ไม่รวมติดตั้ง dependencies และเขียนโค้ด เวอร์ชันที่ใช้: {', '.join(k + '=' + v for k, v in metadata['versions'].items())} config, seed และ code/input/output hashes บันทึกไว้สำหรับทำซ้ำ ไม่อ้างว่าบิตของไฟล์ binary เหมือนกันบนทุกระบบ

## แหล่งหลักการ

[scikit-learn: data leakage และ pipeline](https://scikit-learn.org/stable/common_pitfalls.html), [การแบ่งข้อมูลตามเวลา](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split), [CatBoost: tuning/early stopping/has_time](https://catboost.ai/docs/en/concepts/parameter-tuning), [CatBoost: regression objectives](https://catboost.ai/docs/en/concepts/loss-functions-regression)
'''
    detailed = detailed.replace('保存โมเดล', 'บันทึกโมเดล')
    write_metadata(report, 'summary_text', short)
    write_metadata(report, 'report_text', detailed)
    # A self-contained HTML report: escaped full text and embedded figures.
    import base64
    images = ''.join('<figure><img style="max-width:100%" alt="' + p.stem + '" src="data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode() + '"></figure>' for p in sorted(figures.glob('*.png')))
    (report / 'report.html').write_text('<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Model evaluation</title><body style="max-width:1100px;margin:32px auto;font-family:sans-serif;padding:16px"><pre style="white-space:pre-wrap;line-height:1.6">' + html.escape(detailed) + '</pre>' + images + '</body></html>', encoding='utf-8')
