"""Thai browser form; inference only, with no collection or training."""
from datetime import datetime
import csv
import json
import logging
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
# Streamlit prepends the entry-point directory, which also contains app.py.
# Keep the project root first so ``app.dashboard`` resolves to the package.
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

import streamlit as st
from script.modeling.predict import DEFAULT_MODEL, load_model, predict_rows


def apply_layout():
    """Small presentation overrides; native widgets retain focus and keyboard behavior."""
    st.markdown('''
    <style>
    div.stMainBlockContainer { max-width: 1160px; padding-top: 2.8rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { background: #eef2f6; border-right: 1px solid #cbd5e1; }
    [data-testid="stSidebarContent"] {
        height: 100%; overflow: clip; overscroll-behavior: none;
    }
    [data-testid="stSidebarUserContent"] { padding-bottom: 1rem; }
    [data-testid="stSidebar"] h1 { font-size: 1.35rem; text-align: center; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { text-align: center; }
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
        width: 100%; align-items: stretch;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"] {
        justify-content: center; width: 100%; padding: .75rem .8rem; border-radius: 8px;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) {
        background: #1e3a5f;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) p {
        color: #fff !important; font-weight: 600;
    }
    [data-testid="stSidebar"] [data-testid="stRadioOption"]:not(:has(input:checked)):hover {
        background: #dce5ef;
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
    [data-testid="stCaptionContainer"] { line-height: 1.75; opacity: 1 !important; }
    [data-testid="stCaptionContainer"] p, [data-testid="stCaptionContainer"] span {
        color: #475569 !important; font-size: .9rem;
    }
    [data-testid="stWidgetLabel"] p { color: #1e293b; font-weight: 500; }
    [data-testid="stMain"] a { color: #1e3a5f; text-decoration: underline; }
    [data-testid="stMain"] hr, [data-testid="stSidebar"] hr { border-color: #cbd5e1; }
    [data-testid="stMetric"] {
        background: #fff; border: 1px solid #cbd5e1; border-left: 4px solid #1e3a5f;
        border-radius: 12px; padding: 1.2rem 1.3rem;
        box-shadow: 0 3px 14px rgb(15 23 42 / 4%);
    }
    [data-testid="stMetricLabel"] p { color: #334155; font-weight: 600; }
    [data-testid="stMetricValue"] { color: #0f172a; font-size: 2rem; font-weight: 650; }
    [data-testid="stForm"] { background: #fff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 1.4rem; }
    [data-testid="stExpander"] { background: #fff; border-color: #cbd5e1; border-radius: 12px; }
    [data-testid="stExpander"] summary p { color: #334155; font-weight: 500; }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stNumberInput"] [data-baseweb="input"],
    [data-testid="stDateInput"] [data-baseweb="input"] { border-color: #bac7d6; }
    [data-testid="stAlert"] { border-radius: 10px; }
    [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {
        display: none;
    }
    [data-testid="stNumberInputField"] { appearance: textfield; -moz-appearance: textfield; }
    [data-testid="stMain"] input::placeholder { color: #475569 !important; opacity: 1; }
    [data-testid="stNumberInputField"]::-webkit-inner-spin-button,
    [data-testid="stNumberInputField"]::-webkit-outer-spin-button { -webkit-appearance: none; }
    .stButton button, .stFormSubmitButton button, .stDownloadButton button {
        min-height: 2.8rem; border-radius: 8px; font-weight: 500;
    }
    @media (max-height: 600px) {
        [data-testid="stSidebarHeader"] { height: 2.5rem; min-height: 2.5rem; }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .5rem; }
        [data-testid="stSidebar"] hr { margin: .6rem 0; }
        [data-testid="stSidebar"] [data-testid="stRadioOption"] { padding: .4rem .8rem; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { line-height: 1.5; }
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


@st.cache_data
def storage_catalog(path, stamp, reference_path, reference_stamp):
    """Official model capacities where known, otherwise observed clean capacities."""
    choices = {}
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            value = float(row['storage_gb'])
            if not value.is_integer() or value <= 0:
                raise ValueError('Invalid storage capacity in dataset')
            choices.setdefault(row['brand'] + ':' + row['model'], set()).add(int(value))
    result = {key: sorted(values) for key, values in choices.items()}
    reference = json.loads(Path(reference_path).read_text(encoding='utf-8'))['capacities']
    for key, values in reference.items():
        if not values or any(type(value) is not int or value <= 0 for value in values):
            raise ValueError('Invalid model storage reference')
        result[key] = sorted(set(values))
    return result


@st.cache_data
def listing_support(path, stamp):
    """Counts and latest dates describe observed used listings, not confidence levels."""
    result = {}
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            if row['condition'] != 'used':
                continue
            key = (row['brand'], row['model'], int(float(row['storage_gb'])))
            item = result.setdefault(key, {'count': 0, 'latest': row['published_at']})
            item['count'] += 1
            item['latest'] = max(item['latest'], row['published_at'])
    return result


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

    st.caption(f"Model Version {artifact.get('model_version', artifact.get('feature_version', 1))} · ข้อมูลฝึกถึง {artifact['fit_date_max']}")

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

    dataset = Path(os.environ.get('PHONE_PRICE_DATASET_PATH', str(ROOT / 'data/final/dataset.csv')))
    if not dataset.is_absolute():
        dataset = ROOT / dataset
    reference = Path(os.environ.get('PHONE_PRICE_STORAGE_REFERENCE_PATH', str(ROOT / 'config/app/storage_options.json')))
    if not reference.is_absolute():
        reference = ROOT / reference
    try:
        capacities = storage_catalog(str(dataset), dataset.stat().st_mtime_ns,
                                     str(reference), reference.stat().st_mtime_ns)[brand + ':' + model]
    except (OSError, ValueError, KeyError):
        logging.getLogger(__name__).exception('Unable to read model storage options')
        st.error('ยังโหลดตัวเลือกความจุของรุ่นนี้ไม่ได้ กรุณาให้ผู้ดูแลตรวจชุดข้อมูล')
        st.stop()
    if st.session_state.get('storage') not in capacities:
        st.session_state['storage'] = 128 if 128 in capacities else capacities[0]

    uses_warranty = 'warranty_days' in artifact['feature_names']
    warranty = None
    with st.form('estimate'):
        storage = st.selectbox('ความจุ (GB)', capacities, key='storage',
                               format_func=lambda value: f'{value:,} GB',
                               help='เลือกความจุของเครื่อง รุ่นที่มีข้อมูลสเปกใช้ตัวเลือกจากผู้ผลิต ส่วนรุ่นอื่นใช้ค่าที่พบในชุดข้อมูล')
        device_status = st.selectbox('สภาพการใช้งาน', ['normal', 'unsupported'], key='device_status',
                                    format_func=lambda value: {'normal': 'ใช้งานปกติ ไม่เสียหรือถูกล็อก',
                                                              'unsupported': 'จอแตก มีอาการเสีย หรือถูกล็อก'}[value])
        st.caption('ยังไม่แยกราคาตามรอยขีดข่วนหรือประวัติซ่อม ช่องสภาพใช้ตรวจขอบเขตการประเมิน')
        with st.expander('ข้อมูลเพิ่มเติม (ไม่ทราบให้เว้นว่าง)', expanded=True):
            left, right = st.columns(2)
            with left:
                battery = st.number_input('สุขภาพแบตเตอรี่ (%)', min_value=0, max_value=100,
                                          value=None, step=1, key='battery', placeholder='ไม่ทราบ')
                box = st.selectbox('มีกล่องหรือไม่', [None, 1, 0], key='box',
                                  format_func=lambda v: {None: 'ไม่ทราบ', 1: 'มีกล่อง', 0: 'ไม่มีกล่อง'}[v])
            with right:
                if uses_warranty:
                    warranty = st.number_input('ประกันเหลือ (วัน)', min_value=0, max_value=999, value=None,
                                               step=1, key='warranty', placeholder='ไม่ทราบ',
                                               help='กรอก 0 เมื่อทราบว่าไม่มีประกัน')
                day = st.date_input('วันที่ตั้งประกาศ', key='day',
                                    value=datetime.now(ZoneInfo('Asia/Bangkok')).date())
        submitted = st.form_submit_button('ประเมินราคา', type='primary', width='stretch')

    if submitted and device_status != 'normal':
        st.warning('โมเดลนี้ยังไม่รองรับเครื่องจอแตก เสีย หรือถูกล็อก จึงไม่แสดงราคาประเมินสำหรับสภาพนี้')
        submitted = False
    if submitted:
        row = {'brand': brand, 'model': model, 'storage_gb': storage,
               'condition': 'used', 'published_at': day.isoformat(),
               'battery_health_pct': battery, 'box_mentioned': box}
        if uses_warranty:
            row['warranty_days'] = warranty
        # Keep older checked artifacts usable; the current source-free model needs no source.
        if not artifact.get('source_free'):
            row['source'] = 'mac2hand'
        try:
            result = predict_rows(artifact, [row])[0]
        except Exception:
            logging.getLogger(__name__).exception('Price prediction failed')
            st.error('ประเมินราคาไม่สำเร็จ กรุณาตรวจข้อมูลที่กรอก หากยังไม่ได้ให้แจ้งผู้ดูแล')
        else:
            st.metric('ราคาตั้งขายโดยประมาณ', f"{result['predicted_price_thb']:,.0f} บาท")
            st.caption(f"{brand} {model} · {storage:,} GB · {day.isoformat()}")
            if brand != 'Apple':
                st.warning('ข้อมูลฝึกส่วนใหญ่เป็น iPhone ผลย้อนหลังของยี่ห้ออื่นคลาดเคลื่อนมากกว่า ควรดูผลแยกกลุ่มในเมนูผลโมเดลและเทียบประกาศปัจจุบันเพิ่มเติม')
            support = listing_support(str(dataset), dataset.stat().st_mtime_ns).get((brand, model, storage))
            if support:
                st.caption(f"ข้อมูลมือสองรุ่นและความจุนี้ {support['count']:,} ประกาศ · ประกาศล่าสุด {support['latest']}")
                if support['count'] < 10:
                    st.warning('รุ่นและความจุนี้มีข้อมูลมือสองน้อยกว่า 10 ประกาศ ควรเทียบประกาศปัจจุบันเพิ่มเติมก่อนตั้งราคา')
            else:
                st.warning('ไม่มีประกาศมือสองรุ่นและความจุนี้ตรงกันในชุดข้อมูล ผลนี้เป็นการประมาณจากข้อมูลอื่นที่โมเดลเรียนรู้')
            if 'date_outside_training_range' in result['coverage_flags']:
                st.info(f"วันที่เลือกอยู่นอกช่วงข้อมูลที่ใช้ฝึก (ถึง {artifact['fit_date_max']}) ราคาตลาดปัจจุบันอาจต่างจากผลนี้")
            if any(flag.endswith('_unknown') for flag in result['coverage_flags']):
                optional_label = 'แบตเตอรี่ ประกัน หรือกล่อง' if uses_warranty else 'แบตเตอรี่หรือกล่อง'
                st.caption(f'ข้อมูล{optional_label}ที่เว้นว่างจะถือว่าไม่ทราบ ไม่ได้ถือว่าเป็นศูนย์')

    st.divider()
    st.caption('ผลเป็นการประมาณราคาประกาศ ไม่ใช่ราคาปิดการขาย ควรเทียบประกาศรุ่นและสภาพใกล้เคียงก่อนตั้งราคา')
    with st.expander('ข้อมูลที่โมเดลใช้และข้อจำกัด'):
        optional_label = 'สุขภาพแบตเตอรี่ ประกันเหลือ และการมีกล่อง' if uses_warranty else 'สุขภาพแบตเตอรี่และการมีกล่อง'
        st.write(f'ข้อมูลที่กรอก: ยี่ห้อ รุ่น ความจุ วันที่ประกาศ {optional_label} โมเดลคำนวณอายุรุ่น กลุ่มรุ่น และค่าที่บอกว่าไม่ทราบจากข้อมูลเหล่านี้')
        if artifact.get('source_free'):
            st.write('โมเดลรวมข้อมูลทั้งสองเว็บไซต์โดยไม่ใช้เว็บไซต์ต้นทางเป็นฟีเจอร์ ประเมินโดยกำหนดประเภทเครื่องเป็นมือสอง')
        st.write('โมเดลรอบนี้ใช้เครื่องปกติ ไม่รองรับเครื่องเสีย จอแตก ล็อก หรือขายเป็นอะไหล่ และไม่ได้เรียนรู้ผลของรอยตำหนิ/ประวัติซ่อม จึงไม่หักราคาแทนความเสียหายโดยอัตโนมัติ')
        st.write(f"ข้อมูลฝึกถึง {artifact['fit_date_max']} ผลสำหรับรุ่นหรือสภาพที่มีข้อมูลน้อยอาจคลาดเคลื่อนมาก")
        if artifact.get('dataset_sha256') == 'a630520c2f7efc8ed793591aaa01e780d1198fa630410da3c335c27c6bd0e5c6' and artifact.get('role') == 'deployment_full_data':
            st.write('โมเดลปัจจุบันฝึกจากข้อมูลมือถือมือสอง 9,100 ประกาศ ส่วนใหญ่เป็น iPhone อ่านผลประเมินย้อนหลังและข้อจำกัดในเมนูผลโมเดล โมเดลใช้งานที่ฝึกครบยังไม่มีผลทดสอบอิสระ')


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
        from app.dashboard import render_explorer, render_model_results
        if page == 'สำรวจข้อมูล':
            render_explorer()
        else:
            render_model_results()


if __name__ == '__main__':
    main()
