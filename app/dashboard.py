"""Read-only dataset explorer and aggregate model results for the browser UI."""
import json
import logging
import os
import math
import unicodedata
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LABELS = {'ennxo': 'ENNXO', 'mac2hand': 'Mac2Hand'}


if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from script.artifacts import read_metadata
from script.report_links import website_report_links

def normalize_model_search(value):
    """Match casing, compatibility characters, spacing and punctuation uniformly."""
    return ''.join(character for character in unicodedata.normalize('NFKC', value).casefold()
                   if character.isalnum())


def clear_model_selection():
    st.session_state['filter_model'] = None


def explorer_charts(frame):
    """Fix count/price origins at zero while allowing maxima to follow the filters."""
    counts = frame['brand'].value_counts().head(10).rename_axis('brand').reset_index(name='count')
    trend = frame.groupby('year', as_index=False)['price_thb'].median()
    count_max = max(1, math.ceil(counts['count'].max() * 1.12))
    price_max = max(1, math.ceil(trend['price_thb'].max() * 1.12))
    bars = alt.Chart(counts).mark_bar(color='#1e3a5f', cornerRadiusEnd=3).encode(
        x=alt.X('count:Q', title='จำนวนประกาศ',
                scale=alt.Scale(domain=[0, count_max], nice=False, clamp=True),
                axis=alt.Axis(format=',d', tickMinStep=1)),
        y=alt.Y('brand:N', title=None, sort='-x'),
        tooltip=[alt.Tooltip('brand:N', title='ยี่ห้อ'),
                 alt.Tooltip('count:Q', title='จำนวนประกาศ', format=',d')],
    )
    line = alt.Chart(trend).mark_line(color='#1e3a5f', point=True, strokeWidth=2).encode(
        x=alt.X('year:Q', title='ปีประกาศ', scale=alt.Scale(zero=False),
                axis=alt.Axis(format='d', tickMinStep=1, tickCount=6, labelAngle=0)),
        y=alt.Y('price_thb:Q', title='ราคา (บาท)',
                scale=alt.Scale(domain=[0, price_max], nice=False, clamp=True),
                axis=alt.Axis(format=',.0f')),
        tooltip=[alt.Tooltip('year:Q', title='ปีประกาศ', format='d'),
                 alt.Tooltip('price_thb:Q', title='ราคามัธยฐาน (บาท)', format=',.0f')],
    )
    return tuple(chart.properties(height=280).configure_view(stroke=None).configure_axis(
        labelColor='#475569', titleColor='#334155', gridColor='#dbe3ed', labelFontSize=12,
        domain=False, tickSize=0, labelPadding=8, titlePadding=12,
    ) for chart in (bars, line))


@st.cache_data
def read_dataset(path, stamp):
    frame = pd.read_csv(path, encoding='utf-8-sig')
    required = ['source', 'brand', 'model', 'storage_gb', 'condition', 'price_thb', 'published_at']
    if not set(required).issubset(frame.columns):
        raise ValueError('Dataset schema differs')
    frame['published_at'] = pd.to_datetime(frame['published_at'], errors='raise')
    frame['year'] = frame['published_at'].dt.year
    frame['price_thb'] = pd.to_numeric(frame['price_thb'], errors='raise')
    return frame


def render_explorer():
    st.title('สำรวจข้อมูลมือถือ')
    st.write('ค้นหาและกรองชุดข้อมูลที่คัดสำหรับโมเดลแล้ว สถิติด้านล่างเปลี่ยนตามตัวกรอง')
    path = Path(os.environ.get('PHONE_PRICE_DATASET_PATH', str(ROOT / 'data/final/dataset.csv')))
    if not path.is_absolute():
        path = ROOT / path
    try:
        frame = read_dataset(str(path), path.stat().st_mtime_ns)
    except Exception:
        logging.getLogger(__name__).exception('Unable to read public dataset')
        st.error('ยังเปิดชุดข้อมูลไม่ได้ กรุณาให้ผู้ดูแลตรวจไฟล์ข้อมูล')
        return
    st.caption(f"ชุดเต็ม {len(frame):,} ประกาศ · {frame['published_at'].min():%Y-%m-%d} ถึง {frame['published_at'].max():%Y-%m-%d} · ไม่ใช่ประกาศสดจากเว็บ")
    st.caption('หน้านี้สำรวจชุดเผยแพร่ที่เก็บทั้งใหม่และมือสอง ส่วนโมเดลประเมินราคาฝึกเฉพาะมือสอง')
    with st.container(border=True):
        st.subheader('ค้นหาประกาศ')
        left, middle, right = st.columns(3)
        with left:
            sources = st.multiselect('เว็บต้นทาง', sorted(frame['source'].unique()),
                                     default=sorted(frame['source'].unique()), key='filter_sources',
                                     format_func=lambda value: SOURCE_LABELS.get(value, value))
        with middle:
            brands = st.multiselect('ยี่ห้อ (เว้นว่าง = ทั้งหมด)', sorted(frame['brand'].unique()), key='filter_brands')
        with right:
            condition = st.selectbox('สภาพ', ['all', 'used', 'new'], key='filter_condition',
                                    format_func=lambda value: {'all': 'ทั้งหมด', 'used': 'มือสอง', 'new': 'ของใหม่ตามผู้ขาย'}[value])
        query = st.text_input('ค้นหาชื่อรุ่น', placeholder='เช่น iphone13 หรือ Galaxy', key='filter_query',
                              on_change=clear_model_selection)
        search = normalize_model_search(query)
        candidates = frame[frame['source'].isin(sources)]
        if brands:
            candidates = candidates[candidates['brand'].isin(brands)]
        if condition != 'all':
            candidates = candidates[candidates['condition'].eq(condition)]
        if search:
            candidates = candidates[candidates['model'].map(normalize_model_search).str.contains(search, regex=False)]
        matches = sorted(set(zip(candidates['brand'], candidates['model'])))
        if st.session_state.get('filter_model') not in matches:
            st.session_state['filter_model'] = None
        selected_model = st.selectbox('เลือกรุ่นจากผลค้นหา', [None, *matches], key='filter_model',
            disabled=not matches,
            format_func=lambda value: (f'{value[0]} {value[1]}' if value else
                                      'ทุกรุ่นที่ตรงกับคำค้น' if matches else 'ไม่พบรุ่นที่ตรงกับคำค้น'))
        year_min, year_max = int(frame['year'].min()), int(frame['year'].max())
        years = (year_min, year_max)
        if year_min < year_max:
            years = st.slider('ปีที่ตั้งประกาศ', year_min, year_max, (year_min, year_max), key='filter_years')
    filtered = frame[frame['source'].isin(sources) & frame['year'].between(*years)]
    if brands:
        filtered = filtered[filtered['brand'].isin(brands)]
    if condition != 'all':
        filtered = filtered[filtered['condition'].eq(condition)]
    if search:
        filtered = filtered[filtered['model'].map(normalize_model_search).str.contains(search, regex=False)]
    if selected_model is not None:
        filtered = filtered[filtered['brand'].eq(selected_model[0]) & filtered['model'].eq(selected_model[1])]
    if filtered.empty:
        st.info('ไม่พบประกาศตามตัวกรอง ลองเปลี่ยนยี่ห้อ รุ่น หรือช่วงปี')
        return
    first, second, third = st.columns(3)
    first.metric('ประกาศที่พบ', f'{len(filtered):,}')
    second.metric('ราคามัธยฐาน', f"{filtered['price_thb'].median():,.0f} บาท")
    third.metric('จำนวนยี่ห้อ', f"{filtered['brand'].nunique():,}")
    bars, line = explorer_charts(filtered)
    left, right = st.columns(2)
    with left:
        st.subheader('ยี่ห้อที่มีประกาศมากที่สุด')
        st.altair_chart(bars, width='stretch')
    with right:
        st.subheader('ราคามัธยฐานตามปีประกาศ')
        st.altair_chart(line, width='stretch')
    st.caption('ราคาต่างปีอาจมาจากรุ่นและสภาพคนละกลุ่ม จึงไม่ใช่การลดราคาของเครื่องรุ่นเดียวกัน')
    st.subheader('รายการประกาศ')
    columns = ['source', 'brand', 'model', 'storage_gb', 'condition', 'price_thb', 'published_at']
    display = filtered.sort_values('published_at', ascending=False)[columns].copy()
    display['source'] = display['source'].map(SOURCE_LABELS).fillna(display['source'])
    display['condition'] = display['condition'].map({'used': 'มือสอง', 'new': 'ของใหม่ตามผู้ขาย'})
    display['published_at'] = display['published_at'].dt.strftime('%Y-%m-%d')
    display = display.rename(columns={'source': 'เว็บ', 'brand': 'ยี่ห้อ', 'model': 'รุ่น',
                                     'storage_gb': 'ความจุ (GB)', 'condition': 'สภาพ',
                                     'price_thb': 'ราคา (บาท)', 'published_at': 'วันที่ประกาศ'})
    st.dataframe(display.head(500), hide_index=True, width='stretch')
    st.caption('ตารางแสดงไม่เกิน 500 ประกาศล่าสุดตามตัวกรอง ดาวน์โหลดเพื่อดูทั้งหมดได้')
    st.download_button('ดาวน์โหลดรายการที่กรอง (CSV)', display.to_csv(index=False).encode('utf-8-sig'),
                       file_name='phone_listings_filtered.csv', mime='text/csv')


def render_model_results():
    st.title('ผลโมเดลและขอบเขตการใช้งาน')
    report = ROOT / 'docs/assets/modeling'
    try:
        summary = read_metadata(report, 'summary')
    except (OSError, ValueError):
        st.info('ยังไม่มีรายงานผลโมเดลสำหรับแสดง')
        return
    st.write(f"เลือกสัดส่วนโมเดลจาก validation ตามเวลา 2 ช่วง ภายใต้ขอบเขตและฟีเจอร์ที่กำหนดไว้ ผลด้านล่างเป็นการเปรียบเทียบย้อนหลังบนมือสอง {summary['retrospective_rows']:,} ประกาศเดิม")
    first, second, third = st.columns(3)
    first.metric('คลาดเคลื่อนเฉลี่ย (MAE)', f"{summary['retrospective']['mae_thb']:,.0f} บาท")
    second.metric('RMSE', f"{summary['retrospective']['rmse_thb']:,.0f} บาท")
    third.metric('R²', f"{summary['retrospective']['r2']:.3f}")
    st.info('ชุดประเมินเดิมเคยใช้พัฒนาแล้ว คะแนนนี้เป็นผลย้อนหลัง โมเดลใช้งานที่ฝึกครบทุกแถวยังไม่มีคะแนนทดสอบอิสระ')
    groups = [row for row in summary['groups'] if row['group'] == 'source']
    st.subheader('ผลประเมินแยกเว็บไซต์')
    st.dataframe(pd.DataFrame([{'เว็บ': SOURCE_LABELS.get(row['value'], row['value']),
                               'จำนวนประกาศที่ประเมิน': row['rows'],
                               'MAE (บาท)': round(row['mae_thb'])} for row in groups]), hide_index=True)
    st.caption('รายละเอียดต่อไปนี้อ่านจากรายงานโมเดลหลักไฟล์เดียวกับที่ดาวน์โหลด')
    import re
    content = (ROOT / 'docs/modeling.md').read_text(encoding='utf-8')
    sections = re.split(r'^## ', content, flags=re.MULTILINE)[1:]
    for section in sections:
        heading, _, body = section.partition('\n')
        with st.expander(heading, expanded=heading.startswith('สรุป') or 'Android และ iOS' in heading):
            pieces = re.split(r'(!\[[^\]]*\]\(assets/[^)]+\.png\))', body)
            for piece in pieces:
                match = re.fullmatch(r'!\[([^\]]*)\]\((assets/[^)]+\.png)\)', piece)
                if match:
                    st.image(str(ROOT / 'docs' / match.group(2)), caption=match.group(1))
                elif piece.strip():
                    st.markdown(website_report_links(piece))
    st.subheader('ดาวน์โหลดรายงาน')
    left, right = st.columns(2)
    with left:
        st.download_button('ดาวน์โหลดรายงานพร้อมกราฟ (HTML ไฟล์เดียว)',
                           (report / 'report.html').read_bytes(), file_name='model_report.html', mime='text/html', width='stretch')
    with right:
        st.download_button('ดาวน์โหลดรายงานโมเดล (Markdown)', content.encode('utf-8'),
                           file_name='model_report.md', mime='text/markdown', width='stretch')
    with st.expander('ตารางตัวเลขประกอบรายงาน (CSV)'):
        for path in sorted((report / 'tables').glob('*.csv')):
            st.download_button(path.name, path.read_bytes(), file_name=path.name, mime='text/csv',
                               key='download-model-' + path.stem)
