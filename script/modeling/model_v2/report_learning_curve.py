"""Render stored temporal learning-curve measurements without fitting estimators."""
import csv
from statistics import mean
from pathlib import Path

import matplotlib.pyplot as plt
from script.artifacts import metadata_sha, read_metadata
from script.modeling.common import table
from script.modeling.split_dataset import sha, write_csv


def summarize_curves(rows, fractions):
    """Give each temporal fold equal weight at the same requested training fraction."""
    summary = []
    for fraction in fractions:
        points = [row for row in rows if row['requested_fraction'] == fraction]
        scores = {key: mean(row[key] for row in points)
                  for key in ['train_rows', 'train_mae_thb', 'validation_mae_thb',
                              'train_rmse_thb', 'validation_rmse_thb']}
        summary.append({'requested_fraction': fraction, 'folds': len(points), **scores,
                        'mae_thb_gap': scores['validation_mae_thb'] - scores['train_mae_thb']})
    return summary


def render_learning_curve(report, config, folds, selected):
    report = Path(report)
    path = report / 'tables/learning_curve.csv'
    if not path.exists():
        return ''
    metadata = read_metadata(report, 'learning_curve')
    if (metadata['config_sha256'] != metadata_sha(report, 'config') or
            metadata['output_sha256'] != sha(path) or
            metadata['reference_sha256'] != sha(report / 'tables/train_validation_errors.csv') or
            metadata['candidate'] != selected['name']):
        raise ValueError('Learning curves are stale; rerun learning_curve.py')
    with path.open() as handle:
        rows = [{key: (value if key in ('candidate', 'train_min', 'train_max', 'window_start', 'window_end')
                       else float(value) if value else None) for key, value in row.items()}
                for row in csv.DictReader(handle)]
    if len(rows) != len(folds) * len(metadata['fractions']):
        raise ValueError('Incomplete learning curves')
    for fold in folds:
        points = [row for row in rows if row['fold'] == fold['fold']]
        if ([row['requested_fraction'] for row in points] != metadata['fractions'] or
                any(row['candidate'] != selected['name'] or row['validation_rows'] != fold['validation_rows'] or
                    row['full_train_rows'] != fold['train_rows'] or row['train_max'] >= fold['window_start'] or
                    row['window_start'] != fold['window_start'] or row['window_end'] != fold['window_end']
                    for row in points)):
            raise ValueError('Learning curve differs from recorded folds')
    summary = summarize_curves(rows, metadata['fractions'])
    write_csv(report / 'tables/learning_curve_summary.csv', summary)
    fig, axis = plt.subplots(figsize=(9, 5))
    training_sizes = [row['train_rows'] for row in summary]
    for partition, marker in [('train', 'o'), ('validation', 's')]:
        axis.plot(training_sizes, [row[partition + '_mae_thb'] for row in summary],
                  marker=marker, label=partition.capitalize())
    axis.set(xlabel='Mean number of training listings across 5 folds', ylabel='Mean MAE (THB)',
             xticks=training_sizes, ylim=(0, None), title='Learning curve: mean across 5 temporal folds')
    axis.set_xticklabels([f'{size:,.1f}' for size in training_sizes])
    axis.grid(alpha=.25)
    axis.legend()
    fig.tight_layout()
    for suffix in ['png', 'svg']:
        temporary = report / 'figures' / ('learning_curve_summary.tmp.' + suffix)
        fig.savefig(temporary, dpi=160, format=suffix)
        temporary.replace(report / 'figures' / ('learning_curve_summary.' + suffix))
    plt.close(fig)
    summary_table = table(['Training', 'จำนวนฝึกเฉลี่ย', 'Train MAE เฉลี่ย (บาท)',
                           'Validation MAE เฉลี่ย (บาท)', 'MAE gap (บาท)'],
        [[f"{row['requested_fraction']:.0%}", f"{row['train_rows']:,.1f}",
          *[f"{row[key]:,.2f}" for key in ['train_mae_thb', 'validation_mae_thb', 'mae_thb_gap']]]
         for row in summary])
    first, last = summary[0], summary[-1]
    return f'''### 5.2 Learning curve สรุป

สรุปผลที่ฝึกไว้ {len(rows)} ครั้งเป็น **กราฟเดียว** ใช้ขนาด training **10%, 25%, 50%, 75%, 100%** และนำ MAE ของทั้ง {len(folds)} fold ที่สัดส่วนเดียวกันมา **เฉลี่ยแบบให้แต่ละ fold มีน้ำหนักเท่ากัน** ทั้งเส้น training และ validation ค่านี้จึงต่างจาก validation MAE แบบรวมทุกแถวที่ใช้เลือกโมเดลในหัวข้อ 4

แกน X คือ **จำนวนข้อมูลฝึกเฉลี่ยของทั้ง 5 fold (แถว)** ในแต่ละขนาด ค่าเฉลี่ยอาจมีทศนิยมเพราะแต่ละ fold ใช้จำนวนแถวต่างกัน แกน Y คือ **MAE เฉลี่ยจากทั้ง 5 fold หน่วยบาท** คำนวณ error โดยไม่ถ่วงน้ำหนักในแต่ละ fold แต่ละจุดใช้พารามิเตอร์ ฟีเจอร์ และสัดส่วน HGB/CatBoost เดิม ฝึกจากข้อมูลเก่าไปใหม่และรวมวันตัดให้ครบวัน โดยตรึง validation เดิมของ fold นั้น การเตรียมข้อมูลและน้ำหนักความใหม่ใช้เฉพาะ training ณ จุดนั้น จุด 100% ตรวจตรงกับผลในหัวข้อ 5.1 ครบทุก fold

![Learning curve สรุปค่าเฉลี่ยทั้ง 5 fold](figures/learning_curve_summary.png)

{summary_table}

เมื่อเพิ่ม training จาก 10% เป็น 100% validation MAE เฉลี่ยลดจาก **{first['validation_mae_thb']:,.2f}** เป็น **{last['validation_mae_thb']:,.2f} บาท** และช่องว่าง train/validation ลดจาก **{first['mae_thb_gap']:,.2f}** เป็น **{last['mae_thb_gap']:,.2f} บาท** แต่ยังมีช่องว่างเหลืออยู่ ค่าเฉลี่ยอาจซ่อนความแตกต่างระหว่าง fold

กราฟเปลี่ยนทั้งจำนวนและช่วงเวลาของ training พร้อมกัน จึงยังแยกผลของจำนวนข้อมูลออกจากการเปลี่ยนแปลงราคาและรุ่นตามเวลาไม่ได้ ชุด training ระหว่าง fold ซ้อนกัน และ validation เคยใช้เลือกสัดส่วนโมเดลแล้ว กราฟนี้จึงใช้วิเคราะห์พฤติกรรมของโมเดลที่เลือก ยังไม่ยืนยันสาเหตุของ overfitting ไม่ใช้ชุดประเมินย้อนหลัง 682 แถวในการสร้างกราฟนี้

หลักฐาน: [ตารางค่าเฉลี่ย](assets/modeling/tables/learning_curve_summary.csv) · [ผลแต่ละ fold และขนาดฝึก รวม MAE/RMSE](assets/modeling/tables/learning_curve.csv)

'''
