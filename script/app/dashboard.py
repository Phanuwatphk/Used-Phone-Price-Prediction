"""Read-only dataset explorer and aggregate model results for the browser UI."""
import json
import logging
import os
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
SOURCE_LABELS = {'ennxo': 'ENNXO', 'mac2hand': 'Mac2Hand'}


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
    query = st.text_input('ค้นหาชื่อรุ่น', placeholder='เช่น iPhone 13 หรือ Galaxy', key='filter_query')
    year_min, year_max = int(frame['year'].min()), int(frame['year'].max())
    years = (year_min, year_max)
    if year_min < year_max:
        years = st.slider('ปีที่ตั้งประกาศ', year_min, year_max, (year_min, year_max), key='filter_years')
    filtered = frame[frame['source'].isin(sources) & frame['year'].between(*years)]
    if brands:
        filtered = filtered[filtered['brand'].isin(brands)]
    if condition != 'all':
        filtered = filtered[filtered['condition'].eq(condition)]
    if query.strip():
        filtered = filtered[filtered['model'].str.contains(query.strip(), case=False, regex=False, na=False)]
    if filtered.empty:
        st.info('ไม่พบประกาศตามตัวกรอง ลองเปลี่ยนยี่ห้อ รุ่น หรือช่วงปี')
        return
    first, second, third = st.columns(3)
    first.metric('ประกาศที่พบ', f'{len(filtered):,}')
    second.metric('ราคามัธยฐาน', f"{filtered['price_thb'].median():,.0f} บาท")
    third.metric('จำนวนยี่ห้อ', f"{filtered['brand'].nunique():,}")
    left, right = st.columns(2)
    with left:
        st.subheader('ยี่ห้อที่มีประกาศมากที่สุด')
        st.bar_chart(filtered['brand'].value_counts().head(10).rename('จำนวนประกาศ'), horizontal=True)
    with right:
        st.subheader('ราคามัธยฐานตามปีประกาศ')
        trend = filtered.groupby('year')['price_thb'].median().rename('ราคา (บาท)')
        trend.index = trend.index.astype(str)
        st.line_chart(trend)
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
    report = ROOT / 'docs/assets/modeling/asking_price_v2'
    try:
        summary = json.loads((report / 'summary.json').read_text())
    except (OSError, ValueError):
        st.info('ยังไม่มีรายงานผลโมเดลสำหรับแสดง')
        return
    st.write('เลือกวิธีจาก validation ตามเวลา 2 ช่วง ผลด้านล่างเป็นการเปรียบเทียบย้อนหลังบนชุดเดิม 693 ประกาศ')
    first, second, third = st.columns(3)
    first.metric('คลาดเคลื่อนเฉลี่ย (MAE)', f"{summary['retrospective']['mae_thb']:,.0f} บาท")
    second.metric('RMSE', f"{summary['retrospective']['rmse_thb']:,.0f} บาท")
    third.metric('R²', f"{summary['retrospective']['r2']:.3f}")
    st.info('ชุดประเมินเดิมเคยใช้พัฒนาแล้ว คะแนนนี้เป็นผลย้อนหลัง โมเดลใช้งานที่ฝึกครบทุกแถวยังไม่มีคะแนนทดสอบอิสระ')
    groups = [row for row in summary['groups'] if row['group'] == 'source']
    st.dataframe(pd.DataFrame([{'เว็บ': SOURCE_LABELS.get(row['value'], row['value']),
                               'จำนวนประกาศที่ประเมิน': row['rows'],
                               'MAE (บาท)': round(row['mae_thb'])} for row in groups]), hide_index=True)
    st.caption('รายละเอียดต่อไปนี้อ่านจากรายงานโมเดลหลักไฟล์เดียวกับที่ดาวน์โหลด')
    import re
    content = (ROOT / 'docs/modeling.md').read_text(encoding='utf-8')
    sections = re.split(r'^## ', content, flags=re.MULTILINE)[1:]
    for section in sections:
        heading, _, body = section.partition('\n')
        with st.expander(heading, expanded=heading.startswith('สรุป')):
            pieces = re.split(r'(!\[[^\]]*\]\(assets/[^)]+\.png\))', body)
            for piece in pieces:
                match = re.fullmatch(r'!\[([^\]]*)\]\((assets/[^)]+\.png)\)', piece)
                if match:
                    st.image(str(ROOT / 'docs' / match.group(2)), caption=match.group(1))
                elif piece.strip():
                    # CSV links in Markdown are downloads in the browser section below.
                    piece = re.sub(r'\[([^\]]+)\]\(assets/[^)]+\.csv\)', r'\1', piece)
                    st.markdown(piece)
    st.download_button('ดาวน์โหลดรายงานพร้อมกราฟ (HTML ไฟล์เดียว)',
                       (report / 'report.html').read_bytes(), file_name='model_report.html', mime='text/html')
    st.download_button('ดาวน์โหลดรายงานโมเดล (Markdown)', content.encode('utf-8'),
                       file_name='model_report.md', mime='text/markdown')
    with st.expander('ตารางตัวเลขประกอบรายงาน (CSV)'):
        for path in sorted((report / 'tables').glob('*.csv')):
            st.download_button(path.name, path.read_bytes(), file_name=path.name, mime='text/csv',
                               key='download-model-' + path.stem)
