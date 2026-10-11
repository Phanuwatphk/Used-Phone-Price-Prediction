"""Thai browser form; inference only, with no collection or training."""
from datetime import datetime
import logging
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from script.modeling.predict import DEFAULT_MODEL, load_model, predict_rows


@st.cache_resource
def cached_model(path, model_stamp, metadata_stamp):
    # Modification stamps invalidate the cache when either checked artifact changes.
    return load_model(Path(path))


def render_estimator():
    st.title('ประเมินราคามือถือ')
    st.write('เลือกรุ่นและข้อมูลเครื่อง แล้วกดประเมินเพื่อดูราคาตั้งขายโดยประมาณ')
    st.caption('อ้างอิงประกาศ ENNXO และ Mac2Hand • สำหรับเครื่องปกติที่ไม่เสียหรือถูกล็อก')

    path = Path(os.environ.get('PHONE_PRICE_MODEL_PATH', str(DEFAULT_MODEL)))
    if not path.is_absolute():
        path = ROOT / path
    try:
        artifact = cached_model(str(path), path.stat().st_mtime_ns,
                                path.with_name('metadata.json').stat().st_mtime_ns)
    except Exception:
        logging.getLogger(__name__).exception('Unable to load price model')
        st.error('ยังประเมินราคาไม่ได้ กรุณาให้ผู้ดูแลตรวจไฟล์โมเดล สามารถเปิดเมนูสำรวจข้อมูลและผลโมเดลได้ก่อน')
        st.stop()

    brands = sorted(artifact['fitted_brands'])
    brand = st.selectbox('ยี่ห้อ', brands, key='brand')
    models = sorted(pair.split(':', 1)[1] for pair in artifact['fitted_models']
                    if pair.split(':', 1)[0] == brand)
    # Rebuild the dependent selector before creating its widget.
    if st.session_state.get('phone_model') not in models:
        st.session_state['phone_model'] = 'iPhone 13' if 'iPhone 13' in models else models[0]
    model = st.selectbox('รุ่น (พิมพ์เพื่อค้นหา)', models, key='phone_model')

    with st.form('estimate'):
        left, right = st.columns(2)
        with left:
            storage = st.number_input('ความจุ (GB)', min_value=1, max_value=8192,
                                      value=128, step=1, key='storage',
                                      help='กรอกความจุจริงของเครื่อง เช่น 128, 256 หรือ 512')
        with right:
            condition = st.selectbox('สภาพตามผู้ขาย', ['used', 'new'], key='condition',
                                    format_func=lambda v: {'used': 'มือสอง', 'new': 'ของใหม่ตามผู้ขาย'}[v])
        with st.expander('ข้อมูลเพิ่มเติม (ไม่ทราบให้เว้นว่าง)'):
            battery = st.number_input('สุขภาพแบตเตอรี่ (%)', min_value=0, max_value=100,
                                      value=None, step=1, key='battery', placeholder='ไม่ทราบ')
            warranty = st.number_input('ประกันเหลือ (วัน)', min_value=0, max_value=999, value=None,
                                       step=1, key='warranty', placeholder='ไม่ทราบ',
                                       help='กรอก 0 เมื่อทราบว่าไม่มีประกัน')
            box = st.selectbox('มีกล่องหรือไม่', [None, 1, 0], key='box',
                              format_func=lambda v: {None: 'ไม่ทราบ', 1: 'มีกล่อง', 0: 'ไม่มีกล่อง'}[v])
            source = st.selectbox('อ้างอิงประกาศจาก', ['mac2hand', 'ennxo'], key='source',
                                 format_func=lambda v: {'mac2hand': 'Mac2Hand', 'ennxo': 'ENNXO'}[v],
                                 help='ราคาประกาศในแต่ละเว็บต่างกัน ผลจึงขึ้นกับเว็บอ้างอิง')
            day = st.date_input('วันที่ตั้งประกาศ', key='day',
                                value=datetime.now(ZoneInfo('Asia/Bangkok')).date())
        submitted = st.form_submit_button('ประเมินราคา', type='primary', width='stretch')

    if submitted:
        row = {'source': source, 'brand': brand, 'model': model, 'storage_gb': storage,
               'condition': condition, 'published_at': day.isoformat(),
               'battery_health_pct': battery, 'warranty_days': warranty, 'box_mentioned': box}
        try:
            result = predict_rows(artifact, [row])[0]
        except Exception:
            logging.getLogger(__name__).exception('Price prediction failed')
            st.error('ประเมินราคาไม่สำเร็จ กรุณาตรวจข้อมูลที่กรอก หากยังไม่ได้ให้แจ้งผู้ดูแล')
        else:
            st.metric('ราคาตั้งขายโดยประมาณ', f"{result['predicted_price_thb']:,.0f} บาท")
            st.caption(f"{brand} {model} · {storage:,} GB · {source.upper() if source == 'ennxo' else 'Mac2Hand'} · {day.isoformat()}")
            if 'date_outside_training_range' in result['coverage_flags']:
                st.info(f"วันที่เลือกอยู่นอกช่วงข้อมูลที่ใช้ฝึก (ถึง {artifact['fit_date_max']}) ราคาตลาดปัจจุบันอาจต่างจากผลนี้")
            if any(flag.endswith('_unknown') for flag in result['coverage_flags']):
                st.caption('ข้อมูลแบตเตอรี่ ประกัน หรือกล่องที่เว้นว่างจะถือว่าไม่ทราบ ไม่ได้ถือว่าเป็นศูนย์')

    st.divider()
    st.caption('ผลเป็นการประมาณราคาประกาศ ไม่ใช่ราคาปิดการขาย ควรเทียบประกาศรุ่นและสภาพใกล้เคียงก่อนตั้งราคา')
    with st.expander('ข้อมูลอ้างอิงและข้อจำกัด'):
        st.write(f"ข้อมูลฝึกถึง {artifact['fit_date_max']} ผลสำหรับรุ่นหรือสภาพที่มีข้อมูลน้อยอาจคลาดเคลื่อนมาก")
        if artifact.get('dataset_sha256') == 'a630520c2f7efc8ed793591aaa01e780d1198fa630410da3c335c27c6bd0e5c6' and artifact.get('role') == 'deployment_full_data':
            st.write('ข้อมูล 9,210 ประกาศ ส่วนใหญ่เป็น iPhone การเปรียบเทียบย้อนหลังพบความคลาดเคลื่อนเฉลี่ยประมาณ 5,339 บาท ตัวเลขนี้ไม่ใช่ช่วงราคาที่รับประกัน และโมเดลใช้งานที่ฝึกครบยังไม่มีผลทดสอบอิสระ')


def main():
    st.set_page_config(page_title='Used Phone Price', page_icon='📱', layout='wide')
    with st.sidebar:
        st.title('📱 Used Phone Price')
        st.caption('ประเมินราคาและสำรวจข้อมูลมือถือ')
        page = st.radio('เมนู', ['ประเมินราคา', 'สำรวจข้อมูล', 'ผลโมเดล'], key='navigation')
        st.divider()
        st.caption('ข้อมูลประกาศ ENNXO และ Mac2Hand\nราคาตั้งขาย หน่วยบาท')
    if page == 'ประเมินราคา':
        render_estimator()
    else:
        from script.app.dashboard import render_explorer, render_model_results
        if page == 'สำรวจข้อมูล':
            render_explorer()
        else:
            render_model_results()


if __name__ == '__main__':
    main()
