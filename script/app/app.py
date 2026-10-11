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


def apply_layout():
    """Small presentation overrides; native widgets retain focus and keyboard behavior."""
    st.markdown('''
    <style>
    div.stMainBlockContainer { max-width: 1160px; padding-top: 2.8rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { border-right: 1px solid #e2e8f0; }
    [data-testid="stSidebar"] h1 { font-size: 1.35rem; text-align: center; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { text-align: center; }
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
        width: 100%; align-items: stretch;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"] {
        justify-content: center; width: 100%; padding: .6rem .8rem; border-radius: 8px;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) {
        background: #e2e8f0;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"] > div {
        width: 100%; justify-content: center;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {
        display: none;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"]:focus-within {
        outline: 2px solid #64748b; outline-offset: 2px;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] p { text-align: center; }
    [data-testid="stMain"] h1 { font-size: 2rem; font-weight: 650; letter-spacing: -0.025em; }
    [data-testid="stMain"] h2 { font-size: 1.4rem; font-weight: 600; }
    [data-testid="stMain"] h3 { font-size: 1.1rem; font-weight: 600; }
    [data-testid="stCaptionContainer"] { color: #64748b; line-height: 1.7; }
    [data-testid="stCaptionContainer"] p { color: #64748b; }
    [data-testid="stMetric"] {
        background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 1rem 1.2rem;
    }
    [data-testid="stMetricValue"] { font-size: 1.85rem; font-weight: 600; }
    [data-testid="stForm"] { background: #fff; border-radius: 12px; padding: 1.4rem; }
    [data-testid="stExpander"] { background: #fff; border-radius: 12px; }
    [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {
        display: none;
    }
    [data-testid="stNumberInputField"] { appearance: textfield; -moz-appearance: textfield; }
    [data-testid="stNumberInputField"]::-webkit-inner-spin-button,
    [data-testid="stNumberInputField"]::-webkit-outer-spin-button { -webkit-appearance: none; }
    .stButton button, .stFormSubmitButton button, .stDownloadButton button {
        min-height: 2.8rem; border-radius: 8px; font-weight: 500;
    }
    @media (max-width: 640px) {
        div.stMainBlockContainer { padding: 1.5rem 1rem 2rem; }
        [data-testid="stMain"] h1 { font-size: 1.65rem; }
        [data-testid="stForm"] { padding: 1rem; }
        [data-testid="stMetricValue"] { font-size: 1.5rem; }
    }
    </style>
    ''', unsafe_allow_html=True)


@st.cache_resource
def cached_model(path, model_stamp, metadata_stamp):
    # Modification stamps invalidate the cache when either checked artifact changes.
    return load_model(Path(path))


def render_estimator():
    st.title('ประเมินราคามือถือ')
    st.write('เลือกรุ่นและข้อมูลเครื่อง แล้วกดประเมินเพื่อดูราคาตั้งขายโดยประมาณ')
    st.caption('สำหรับมือถือมือสองที่ใช้งานปกติ ไม่เสียหรือถูกล็อก')

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
    left, right = st.columns(2)
    with left:
        brand = st.selectbox('ยี่ห้อ', brands, key='brand')
    models = sorted(pair.split(':', 1)[1] for pair in artifact['fitted_models']
                    if pair.split(':', 1)[0] == brand)
    # Rebuild the dependent selector before creating its widget.
    if st.session_state.get('phone_model') not in models:
        st.session_state['phone_model'] = 'iPhone 13' if 'iPhone 13' in models else models[0]
    with right:
        model = st.selectbox('รุ่น (พิมพ์เพื่อค้นหา)', models, key='phone_model')

    with st.form('estimate'):
        storage = st.number_input('ความจุ (GB)', min_value=1, max_value=8192,
                                  value=128, step=1, key='storage',
                                  help='กรอกความจุจริงของเครื่อง เช่น 128, 256 หรือ 512')
        with st.expander('ข้อมูลเพิ่มเติม (ไม่ทราบให้เว้นว่าง)'):
            left, right = st.columns(2)
            with left:
                battery = st.number_input('สุขภาพแบตเตอรี่ (%)', min_value=0, max_value=100,
                                          value=None, step=1, key='battery', placeholder='ไม่ทราบ')
                box = st.selectbox('มีกล่องหรือไม่', [None, 1, 0], key='box',
                                  format_func=lambda v: {None: 'ไม่ทราบ', 1: 'มีกล่อง', 0: 'ไม่มีกล่อง'}[v])
            with right:
                warranty = st.number_input('ประกันเหลือ (วัน)', min_value=0, max_value=999, value=None,
                                           step=1, key='warranty', placeholder='ไม่ทราบ',
                                           help='กรอก 0 เมื่อทราบว่าไม่มีประกัน')
                day = st.date_input('วันที่ตั้งประกาศ', key='day',
                                    value=datetime.now(ZoneInfo('Asia/Bangkok')).date())
        submitted = st.form_submit_button('ประเมินราคา', type='primary', width='stretch')

    if submitted:
        # These training features remain required by the existing artifact.
        row = {'source': 'mac2hand', 'brand': brand, 'model': model, 'storage_gb': storage,
               'condition': 'used', 'published_at': day.isoformat(),
               'battery_health_pct': battery, 'warranty_days': warranty, 'box_mentioned': box}
        try:
            result = predict_rows(artifact, [row])[0]
        except Exception:
            logging.getLogger(__name__).exception('Price prediction failed')
            st.error('ประเมินราคาไม่สำเร็จ กรุณาตรวจข้อมูลที่กรอก หากยังไม่ได้ให้แจ้งผู้ดูแล')
        else:
            st.metric('ราคาตั้งขายโดยประมาณ', f"{result['predicted_price_thb']:,.0f} บาท")
            st.caption(f"{brand} {model} · {storage:,} GB · {day.isoformat()}")
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
    st.set_page_config(page_title='Used Phone Price', layout='wide')
    apply_layout()
    with st.sidebar:
        st.title('Used Phone Price')
        st.caption('ประเมินราคาและสำรวจข้อมูลมือถือ')
        st.divider()
        page = st.radio('เมนู', ['ประเมินราคา', 'สำรวจข้อมูล', 'ผลโมเดล'],
                        key='navigation', label_visibility='collapsed', width='stretch')
        st.divider()
        st.caption('ENNXO · Mac2Hand')
        st.caption('ราคาตั้งขาย · หน่วยบาท')
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
