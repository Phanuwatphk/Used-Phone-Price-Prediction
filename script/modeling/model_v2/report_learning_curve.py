"""Render one stored learning curve with a fixed temporal validation set."""
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from script.artifacts import metadata_sha, read_metadata
from script.modeling.common import table
from script.modeling.split_dataset import sha


def render_learning_curve(report, config, folds, selected):
    report = Path(report)
    path = report / 'tables/learning_curve.csv'
    if not path.exists():
        return ''
    metadata = read_metadata(report, 'learning_curve')
    if (metadata['config_sha256'] != metadata_sha(report, 'config') or
            metadata['output_sha256'] != sha(path) or
            metadata['reference_sha256'] != sha(report / 'tables/train_validation_errors.csv') or
            metadata['candidate'] != selected['name'] or
            metadata.get('split_policy') != 'latest_existing_temporal_validation' or
            metadata.get('fold') != folds[-1]['fold']):
        raise ValueError('Learning curve is stale; rerun learning_curve.py')
    with path.open() as handle:
        rows = [{key: (value if key in ('candidate', 'train_min', 'train_max', 'window_start', 'window_end')
                       else float(value) if value else None) for key, value in row.items()}
                for row in csv.DictReader(handle)]
    fold = folds[-1]
    interval = config['folds'][-1]
    if (len(rows) != len(metadata['fractions']) or
            [row['requested_fraction'] for row in rows] != metadata['fractions'] or
            any(row['candidate'] != selected['name'] or row['fold'] != fold['fold'] or
                row['validation_rows'] != fold['validation_rows'] or
                row['full_train_rows'] != fold['train_rows'] or row['train_max'] >= interval['start'] or
                row['window_start'] != interval['start'] or row['window_end'] != interval['end']
                for row in rows)):
        raise ValueError('Learning curve differs from the fixed validation split')
    fig, axis = plt.subplots(figsize=(9, 5))
    training_sizes = [int(row['train_rows']) for row in rows]
    for partition, marker in [('train', 'o'), ('validation', 's')]:
        axis.plot(training_sizes, [row[partition + '_mae_thb'] for row in rows],
                  marker=marker, label=partition.capitalize())
    axis.set(xlabel='Number of training listings', ylabel='MAE (THB)',
             xticks=training_sizes, ylim=(0, None), title='Learning curve: fixed temporal validation set')
    axis.set_xticklabels([f'{size:,}' for size in training_sizes])
    axis.grid(alpha=.25)
    axis.legend()
    fig.tight_layout()
    for suffix in ['png', 'svg']:
        temporary = report / 'figures' / ('learning_curve.tmp.' + suffix)
        fig.savefig(temporary, dpi=160, format=suffix)
        if suffix == 'svg':
            temporary.write_text('\n'.join(line.rstrip() for line in temporary.read_text().splitlines()) + '\n')
        temporary.replace(report / 'figures' / ('learning_curve.' + suffix))
    plt.close(fig)
    scores_table = table(['Training', 'จำนวนฝึก (แถว)', 'Train MAE (บาท)',
                          'Validation MAE (บาท)', 'MAE gap (บาท)'],
        [[f"{row['requested_fraction']:.0%}", f"{int(row['train_rows']):,}",
          *[f"{row[key]:,.2f}" for key in ['train_mae_thb', 'validation_mae_thb', 'mae_thb_gap']]]
         for row in rows])
    first, last = rows[0], rows[-1]
    return f'''### 5.1 Learning curve

ใช้ชุด train และ validation ของช่วงเวลาล่าสุดที่มีอยู่เดิมเพียงช่วงเดียว: training **{fold['train_rows']:,} แถว** ก่อนวันที่ **{interval['start']}** และ validation **{fold['validation_rows']:,} แถว** ช่วง **{interval['start']} ถึง {interval['end']}** เลือกช่วงล่าสุดตามลำดับเวลา

ฝึกโมเดลใหม่ **{len(rows)} ครั้ง** ด้วยข้อมูล training ขนาด **10%, 25%, 50%, 75%, 100%** ใช้วิธี พารามิเตอร์ ฟีเจอร์ และสัดส่วน HGB/CatBoost เดิมทุกครั้ง แต่ละขนาดใช้ข้อมูลเรียงจากเก่าไปใหม่และรวมวันตัดให้ครบวัน จึงอาจมีจำนวนแถวเกินสัดส่วนที่ระบุเล็กน้อย การเตรียมข้อมูลและน้ำหนักความใหม่เรียนรู้จาก training ที่ใช้ในครั้งนั้นเท่านั้น

ประเมินแต่ละโมเดลบน training ที่ใช้ฝึกและ **validation ชุดเดิมทุกขนาด** แกน X คือ **จำนวนข้อมูลฝึกจริง (แถว)** แกน Y คือ **MAE หน่วยบาท** ยิ่งต่ำยิ่งดี คำนวณหลังแปลง log ราคากลับและผสมโมเดลแล้ว โดยไม่ถ่วงน้ำหนักตอนวัด error **gap = validation error − training error** จุด 100% ตรวจตรงกับผลเดิมของช่วงนี้

![Learning curve บน validation ชุดเดิม](figures/learning_curve.png)

{scores_table}

เมื่อเพิ่ม training จาก 10% เป็น 100% validation MAE เปลี่ยนจาก **{first['validation_mae_thb']:,.2f}** เป็น **{last['validation_mae_thb']:,.2f} บาท** และช่องว่าง train/validation เปลี่ยนจาก **{first['mae_thb_gap']:,.2f}** เป็น **{last['mae_thb_gap']:,.2f} บาท** ใช้ดูแนวโน้มเมื่อเพิ่มข้อมูลและความห่างของ error ทั้งสองชุด

Training error วัดบนข้อมูลที่โมเดลเคยเรียน กราฟเปลี่ยนทั้งจำนวนและช่วงเวลาของ training พร้อมกัน จึงยังแยกผลของจำนวนข้อมูลออกจากการเปลี่ยนแปลงราคาและรุ่นตามเวลาไม่ได้ Validation นี้เคยใช้เลือกสัดส่วนโมเดลแล้ว กราฟจึงใช้วิเคราะห์พฤติกรรมของโมเดลที่เลือก ไม่ใช่ผลทดสอบอิสระ และไม่ใช้ชุดประเมินย้อนหลังในการสร้างกราฟ

หลักฐาน: [ผลทั้ง 5 ขนาด รวม MAE/RMSE](assets/modeling/tables/learning_curve.csv)

'''
