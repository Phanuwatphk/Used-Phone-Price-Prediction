"""Export reproducible aggregate EDA figures without seller text or contact data."""
from collections import Counter
from datetime import date
import os
from pathlib import Path
import tempfile

COLORS = {'ennxo': '#007f86', 'mac2hand': '#3858a6'}


def render(rows, tables, output, rules):
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'used_phone_matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    matplotlib.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.spines.top': False, 'axes.spines.right': False, 'svg.hashsalt': 'used-phone-eda-v1'})
    output.mkdir(parents=True, exist_ok=True)
    figures = []
    sources = sorted(COLORS)

    def save(fig, name, caption):
        fig.tight_layout()
        fig.savefig(output / (name + '.png'), dpi=180)
        fig.savefig(output / (name + '.svg'), metadata={'Date': None})
        plt.close(fig)
        figures.append({'name': name, 'caption': caption})

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    counts = Counter(r['source'] for r in rows)
    axes[0].bar(sources, [counts[s] for s in sources], color=[COLORS[s] for s in sources])
    for index, source in enumerate(sources):
        axes[0].text(index, counts[source], f"{counts[source]:,} ({counts[source]/len(rows):.1%})", ha='center', va='bottom')
    axes[0].set(title='Source composition', ylabel='Listings'); axes[0].margins(y=.15)
    brands = sorted(tables['brand_counts'], key=lambda r: r['total'])
    left = np.zeros(len(brands))
    for source in sources:
        values = [r.get(source, 0) for r in brands]
        axes[1].barh([r['brand'] for r in brands], values, left=left, label=source, color=COLORS[source])
        left += values
    axes[1].set(title='Brand composition by source', xlabel='Listings'); axes[1].legend()
    save(fig, '01_source_and_brand', 'สัดส่วนเว็บและยี่ห้อ: จำนวนใน snapshot ไม่ใช่ส่วนแบ่งตลาด')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    prices = [r['price_thb'] for r in rows]
    lower, upper = min(prices), max(prices)
    if lower == upper:
        lower, upper = lower * .9, upper * 1.1
    bins = np.geomspace(lower, upper, rules['price_histogram_bins'] + 1)
    boxes = []
    for source in sources:
        selected = [r['price_thb'] for r in rows if r['source'] == source]; boxes.append(selected)
        # Equal weight per source highlights shape without the larger source dominating.
        axes[0].hist(selected, bins=bins, weights=np.ones(len(selected)) / len(selected),
                     histtype='step', linewidth=2, color=COLORS[source], label=f'{source} (n={len(selected):,})')
    axes[0].set(xscale='log', title='Asking-price distribution (all rows)', xlabel='THB (log scale)', ylabel='Fraction of each source')
    axes[0].legend()
    axes[1].boxplot(boxes, tick_labels=sources, showfliers=True,
                    flierprops={'markersize': 2, 'alpha': .35})
    axes[1].set(yscale='log', ylabel='THB (log scale)', title='Median, quartiles, and full-range fliers')
    save(fig, '02_price_distribution', 'ราคาทุกแถว แกน log เพื่อเห็นทั้งราคาต่ำและสูง จุดนอกกล่องเป็น IQR ภาพรวมต่อเว็บ ต่างจากคิวตรวจที่คุมรุ่น/ปี และยังคงอยู่ใน dataset')

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    years = sorted({r['publication_year'] for r in rows})
    for offset, source in enumerate(sources):
        selected = [r for r in rows if r['source'] == source]
        counts = Counter(r['publication_year'] for r in selected)
        axes[0].bar(np.array(years) + (offset - .5) * .35, [counts[y] for y in years],
                    width=.35, label=source, color=COLORS[source])
        by_year = {}
        for year in years:
            values = [r['price_thb'] for r in selected if r['publication_year'] == year]
            if values:
                by_year[year] = float(np.median(values))
        axes[1].plot(list(by_year), list(by_year.values()), marker='o', color=COLORS[source], label=source)
    axes[0].set(title='Coverage by publication year', ylabel='Listings'); axes[0].legend()
    axes[1].set(xlabel='Publication year', ylabel='Median asking price (THB)', title='Yearly medians: changing product mix')
    axes[1].set_xticks(years); axes[1].tick_params(axis='x', rotation=45)
    save(fig, '03_publication_year', 'ช่วงปีต่างกันมาก เส้น median เปลี่ยนตามรุ่นที่ปะปน ไม่ใช่ราคาของเครื่องรุ่นเดิมลดลงตามเวลา')

    fig, ax = plt.subplots(figsize=(12, 5))
    for source in sources:
        selected = [r for r in rows if r['source'] == source]
        ax.scatter([date.fromisoformat(r['published_at']) for r in selected], [r['price_thb'] for r in selected],
                   s=7, alpha=.22, color=COLORS[source], label=f'{source} (all {len(selected):,} rows)', rasterized=True)
    ax.set(yscale='log', title='Asking price and publication date', xlabel='Publication date', ylabel='THB (log scale)')
    ax.legend(); fig.autofmt_xdate()
    save(fig, '04_price_over_time', 'แสดงทุกประกาศตามวันที่ ไม่มีการจำกัด 12 เดือน และยังไม่ปรับเงินเฟ้อหรือเลือกช่วงฝึก')

    counts = Counter((r['brand'], r['model']) for r in rows)
    top = counts.most_common(rules['top_models_in_chart'])[::-1]
    fig, ax = plt.subplots(figsize=(12, 7))
    labels = [f'{brand} / {model}' for (brand, model), _ in top]; left = np.zeros(len(top))
    for source in sources:
        values = [sum(r['source'] == source and (r['brand'], r['model']) == key for r in rows) for key, _ in top]
        ax.barh(labels, values, left=left, color=COLORS[source], label=source); left += values
    ax.set(title=f"Top {len(top)} brand-model pairs", xlabel='Listings'); ax.legend()
    save(fig, '05_top_models', 'รุ่นที่พบมากที่สุด; ตารางแนบท้ายเก็บจำนวนทุกรุ่น รวมรุ่นที่มีตัวอย่างน้อย')

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    storages = sorted({r['storage_gb'] for r in rows}); positions = np.arange(len(storages))
    for offset, source in enumerate(sources):
        counts = Counter(r['storage_gb'] for r in rows if r['source'] == source)
        axes[0].bar(positions + (offset - .5) * .35, [counts[n] for n in storages], width=.35,
                    label=source, color=COLORS[source])
    axes[0].set_xticks(positions, [str(n) for n in storages]); axes[0].set(title='Storage coverage', xlabel='Storage (GB)', ylabel='Listings'); axes[0].legend()
    boxes = [[r['price_thb'] for r in rows if r['storage_gb'] == storage] for storage in storages]
    axes[1].boxplot(boxes, tick_labels=[f'{n}\nn={len(v)}' for n, v in zip(storages, boxes)],
                    flierprops={'markersize': 2, 'alpha': .3})
    axes[1].set(yscale='log', title='Prices by storage (mixed models and years)', xlabel='Storage (GB)', ylabel='THB (log scale)')
    save(fig, '06_storage_and_price', 'ความจุปะปนกับรุ่นและปี กลุ่มที่มีตัวอย่างน้อยตีความอย่างระมัดระวัง ไม่ใช่ผลของความจุต่อราคาโดยตรง')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for offset, source in enumerate(sources):
        selected = [r for r in rows if r['source'] == source]; counts = Counter(r['condition'] for r in selected)
        axes[0].bar(np.arange(2) + (offset - .5) * .35, [counts[k]/len(selected)*100 for k in ('used', 'new')],
                    width=.35, label=source, color=COLORS[source])
    axes[0].set_xticks([0, 1], ['used', 'new']); axes[0].set(title='Seller-selected condition', ylabel='Percent within source'); axes[0].legend()
    correlations = tables['correlations']; pos = np.arange(len(correlations))
    for offset, (key, label, color) in enumerate([('price_vs_storage_spearman', 'Price vs storage', '#007f86'),
                                                ('price_vs_publication_year_spearman', 'Price vs publication year', '#b76727')]):
        values = [r[key] if r[key] is not None else 0 for r in correlations]
        axes[1].bar(pos + (offset-.5)*.35, values, width=.35, color=color, label=label)
        for index, item in enumerate(correlations):
            if item[key] is None:
                axes[1].text(index + (offset-.5)*.35, .02, 'NA', ha='center', fontsize=8)
    axes[1].set_xticks(pos, [r['source'] for r in correlations]); axes[1].axhline(0, color='#999', linewidth=.8)
    axes[1].set(ylim=(-1, 1), title='Descriptive rank associations', ylabel='Spearman correlation'); axes[1].legend(fontsize=8)
    save(fig, '07_condition_and_associations', 'new/used เป็นช่องผู้ขาย; correlation รวมไม่ควบคุมรุ่น/สภาพ/อายุ ไม่ใช่เหตุและผล')

    fig, ax = plt.subplots(figsize=(12, 6))
    comparisons = sorted(tables['source_comparisons'], key=lambda r: min(r['ennxo_n'], r['mac2hand_n']), reverse=True)[:10]
    if comparisons:
        labels = [f"{r['brand']} {r['model']} {r['storage_gb']}GB / {r['publication_year']} ({r['ennxo_n']},{r['mac2hand_n']})" for r in comparisons]
        ax.barh(labels[::-1], [r['ennxo_minus_mac2hand_percent'] for r in comparisons][::-1], color='#007f86')
        ax.axvline(0, color='#555', linewidth=1)
        ax.set(xlabel='ENNXO median relative to Mac2Hand (%)', title='Most-supported matched model/storage/condition/year groups')
    else:
        ax.text(.5, .5, 'No groups meeting the minimum sample size in both sources', ha='center', transform=ax.transAxes)
        ax.set_axis_off()
    save(fig, '08_matched_source_comparison', 'เทียบรุ่น/ความจุ/สภาพ/ปีเดียวกัน ขั้นต่ำ 3 แถวต่อเว็บ ตัวเลขวงเล็บคือ n ของ ENNXO, Mac2Hand; ยังไม่ควบคุมเดือนหรือสภาพเครื่องจริง')
    return figures
