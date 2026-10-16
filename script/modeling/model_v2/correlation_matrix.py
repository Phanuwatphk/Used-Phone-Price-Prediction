"""Describe selected numeric V2 features and price on evaluation-model training rows."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if not __package__:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from script.artifacts import metadata_sha, read_metadata, write_metadata
from script.modeling.common import table
from script.modeling.split_dataset import read_dataset, sha


def correlations(frame):
    """Pairwise Pearson correlation without imputing missing or constant observations."""
    known = frame.notna().astype('int64')
    return frame.corr(method='pearson', min_periods=2), known.T @ known


def run():
    from script.modeling.model_v2.features_v2 import NUMERIC
    from script.modeling.model_v2.train_improved import get_frame
    report = ROOT / 'docs/assets/modeling'
    config = read_metadata(report, 'config')
    spec = read_metadata(report, 'selection')['candidate']
    if spec != next(item for item in config['candidates'] if item['name'] == spec['name']):
        raise ValueError('Selected candidate differs from recorded configuration')
    dataset, catalog_path = ROOT / config['dataset'], ROOT / config['catalog']
    rows = read_dataset(dataset, config['dataset_sha256'])
    if len(rows) != config['expected_rows'] or sha(catalog_path) != config['catalog_sha256']:
        raise ValueError('Input differs from frozen training configuration')
    rows = [row for row in rows if row['condition'] in config['training_conditions']]
    if len(rows) != config['expected_training_rows']:
        raise ValueError('Training scope row count mismatch')
    rows = [row for row in rows if row['published_at'] < config['retrospective_test_start']]
    if len(rows) != read_metadata(report, 'summary')['evaluation_fit_rows']:
        raise ValueError('Evaluation training row count mismatch')
    catalog = json.loads(catalog_path.read_text())['release_years']
    frame = get_frame(spec, rows, catalog)
    numeric = [name for name in NUMERIC if name in frame]
    frame = frame[numeric].copy()
    frame['price_thb'] = [float(row['price_thb']) for row in rows]
    matrix, counts = correlations(frame)
    matrix.to_csv(report / 'tables/correlation_matrix.csv', index_label='feature')
    counts.to_csv(report / 'tables/correlation_pair_counts.csv', index_label='feature')
    fig, axis = plt.subplots(figsize=(12, 10))
    cmap = plt.get_cmap('coolwarm').copy()
    cmap.set_bad('#e5e7eb')
    heatmap = axis.imshow(np.ma.masked_invalid(matrix.to_numpy()), cmap=cmap, vmin=-1, vmax=1)
    labels = list(frame.columns)
    axis.set_xticks(range(len(labels)), labels, rotation=45, ha='right', fontsize=9)
    axis.set_yticks(range(len(labels)), labels, fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            value = matrix.iloc[i, j]
            axis.text(j, i, f'{value:.2f}' if np.isfinite(value) else 'N/A',
                      ha='center', va='center', fontsize=9,
                      color='white' if np.isfinite(value) and abs(value) > .55 else '#172033')
    axis.set_title(f'Pearson correlation: selected numeric features + price\n'
                   f'Training only: {len(rows):,} listings before {config["retrospective_test_start"]}')
    fig.colorbar(heatmap, ax=axis, shrink=.8, label='Pearson r')
    fig.tight_layout()
    for suffix in ['png', 'svg']:
        target = report / 'figures' / ('correlation_matrix.' + suffix)
        temporary = target.with_name('correlation_matrix.tmp.' + suffix)
        fig.savefig(temporary, dpi=160, format=suffix)
        if suffix == 'svg':
            temporary.write_text('\n'.join(line.rstrip() for line in temporary.read_text().splitlines()) + '\n')
        temporary.replace(target)
    plt.close(fig)
    write_metadata(report, 'correlation_matrix', {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'method': 'pearson',
        'candidate': spec['name'], 'rows': len(rows), 'features': labels,
        'scope': 'evaluation_model_training_only', 'cutoff': config['retrospective_test_start'],
        'config_sha256': metadata_sha(report, 'config'), 'dataset_sha256': sha(dataset),
        'catalog_sha256': sha(catalog_path), 'script_sha256': sha(Path(__file__)),
        'output_hashes': {str(path.relative_to(report)): sha(path) for path in
                          [report / 'tables/correlation_matrix.csv', report / 'tables/correlation_pair_counts.csv',
                           report / 'figures/correlation_matrix.png', report / 'figures/correlation_matrix.svg']},
        'policy': 'Unweighted pairwise complete observations; no imputation, scaling, log target, '
                  'categorical encoding, selection, retraining or retrospective scoring. Undefined '
                  'correlations (constant within the available pair or fewer than two pairs) remain missing.'})


def render_section(report, selected):
    report = Path(report)
    path = report / 'tables/correlation_matrix.csv'
    if not path.exists():
        return ''
    metadata = read_metadata(report, 'correlation_matrix')
    if (metadata['config_sha256'] != metadata_sha(report, 'config') or
            metadata['candidate'] != selected['name'] or
            any(sha(report / name) != expected for name, expected in metadata['output_hashes'].items())):
        raise ValueError('Correlation matrix is stale; rerun correlation_matrix.py')
    matrix = pd.read_csv(path, index_col='feature')
    counts = pd.read_csv(report / 'tables/correlation_pair_counts.csv', index_col='feature')
    price_table = table(['ฟีเจอร์', 'Pearson r กับราคา', 'จำนวนคู่ข้อมูล'],
        [[name, f"{matrix.loc[name, 'price_thb']:.3f}" if pd.notna(matrix.loc[name, 'price_thb']) else 'N/A',
          f"{counts.loc[name, 'price_thb']:,}"] for name in metadata['features'] if name != 'price_thb'])
    return f'''### 2.1 Correlation matrix ของฟีเจอร์ตัวเลขและราคา

ใช้ **Pearson correlation** ของฟีเจอร์ตัวเลขที่โมเดลเลือกไว้ {len(metadata['features'])-1} ตัวร่วมกับ `price_thb` หน่วยบาท บนชุดฝึกโมเดลประเมิน **{metadata['rows']:,} แถวก่อน {metadata['cutoff']}** ซึ่งรวม validation เดิมหลังเลือกโมเดลแล้ว แต่ไม่รวมชุดประเมินย้อนหลัง 682 แถว ไม่แปลงราคาเป็น log และไม่ใส่รหัสแทนฟีเจอร์หมวดหมู่ เช่น brand/model

![Correlation matrix ของฟีเจอร์ตัวเลขที่ใช้และราคา](figures/correlation_matrix.png)

ค่า r อยู่ระหว่าง −1 ถึง +1: ค่าบวกหมายถึงมีแนวโน้มเพิ่มไปด้วยกัน ค่าลบหมายถึงมีแนวโน้มสวนทางกัน ส่วนค่าใกล้ศูนย์หมายถึงความสัมพันธ์เชิงเส้นน้อย คำนวณแต่ละคู่จากแถวที่มีค่าทั้งสองตัวโดย **ไม่เติมค่าขาดหาย** จึงใช้จำนวนข้อมูลไม่เท่ากัน `N/A` หมายถึงคำนวณไม่ได้เพราะข้อมูลคู่ไม่พอหรือมีตัวแปรคงที่ในคู่ที่ใช้ ไม่ใช่ค่า correlation เท่ากับศูนย์

{price_table}

ค่าในกราฟเป็นความสัมพันธ์รวม ไม่ได้ควบคุมรุ่น ยี่ห้อ หรือช่วงเวลา จึงไม่ใช่เหตุและผลหรือ feature importance ของโมเดล และค่า r ต่ำไม่ได้แปลว่าไม่มีประโยชน์ต่อโมเดลต้นไม้ ตัวแปรปีเปิดตัว อายุรุ่น และวันประกาศสัมพันธ์กันจากวิธีคำนวณ ขณะที่ตัวแปร missing บางคู่คงที่เมื่อเลือกเฉพาะแถวที่มีข้อมูล จึงเกิด N/A ได้

หลักฐาน: [ค่า correlation](assets/modeling/tables/correlation_matrix.csv) · [จำนวนข้อมูลของแต่ละคู่](assets/modeling/tables/correlation_pair_counts.csv)

'''


if __name__ == '__main__':
    run()
    from script.modeling.model_v2.report_improved import main
    main()
