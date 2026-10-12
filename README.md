# Used Phone Price

เว็บ Streamlit สำหรับประเมินราคาตั้งขายมือถือ สำรวจประกาศ และดูผลโมเดล ใช้ข้อมูล ENNXO และ Mac2Hand ที่ตรวจและคัดแล้ว **9,210 ประกาศ** ทุกแถวมีเว็บต้นทาง ผลราคาเป็นการประมาณราคาประกาศ หน่วยบาท

## เปิดใช้งาน

**[เปิดเว็บประเมินราคาที่ deploy แล้ว](https://secondhand-phone-price-prediction.streamlit.app/)**

มี 3 เมนู: **ประเมินราคา**, **สำรวจข้อมูล** และ **ผลโมเดล** เลือกความจุตามรุ่น กรองข้อมูล ดูกราฟ/ตาราง และดาวน์โหลด CSV ได้ โมเดลรอบนี้รองรับเครื่องใช้งานปกติ ไม่ประเมินเครื่องเสียหรือล็อก

โมเดลใช้งาน `models/asking_price_v2/model.joblib` และ `metadata.json` รวมใน Git แล้ว แอปไม่ scrape หรือเทรนระหว่างใช้งาน หากต้องการฝึกใหม่ ใช้ `python -u -B script/modeling/train_improved.py`

### รันบนเครื่องเพื่อพัฒนา

ใช้ Python 3.12 และรันจากรากโปรเจค:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app/app.py
```

คำสั่งนี้เปิด **http://localhost:8501** บนเครื่องที่รัน ส่วนผู้ใช้เว็บออนไลน์ให้ใช้ลิงก์ด้านบน

Deploy บน Streamlit Community Cloud: ตั้ง **Main file path เป็น `app/app.py`**, Python **3.12** และ branch ที่ commit โค้ดกับโมเดลทั้งสองแล้ว หลังย้ายจาก `script/app/app.py` ต้องแก้ path ใน Settings ของแอปที่ deploy อยู่ด้วย `requirements.txt` ใช้ `requirements-lock.txt` ให้ตรงกับ artifact อ่าน [วิธี deploy](docs/development.md#deploy)

## เอกสาร

เริ่มที่ README นี้ แล้วเลือกอ่านเพียงเรื่องที่ต้องการ มีคู่มือ/รายงานหลักอีก 4 ไฟล์:

| ต้องการอ่าน | เปิดไฟล์ |
|---|---|
| **วิธีเก็บข้อมูลและเตรียม dataset** | [คู่มือข้อมูล](docs/data.md) — ภาพรวม ENNXO/Mac2Hand, raw, clean, review, schema, รวมและคัด พร้อมหน้าที่ไฟล์ |
| **รันอะไร ใช้ config ไหน พัฒนาและ CI** | [คู่มือรันและพัฒนา](docs/development.md) — สคริปต์ทุกขั้น คำสั่ง input/output, config, tests และ GitHub |
| **EDA: วิธีสำรวจ สถิติและกราฟ** | [รายงาน EDA](docs/eda.md) |
| **โมเดล: features แบ่ง/เทรน กราฟและผล** | [รายงานโมเดล](docs/modeling.md) |

รายละเอียดเก็บครบในคู่มือเหล่านี้ ใช้สารบัญข้ามหัวข้อได้ กราฟ ตาราง CSV, HTML สำหรับดาวน์โหลด และ metadata ของรอบทดลองอยู่ใน `docs/assets/` เป็นไฟล์ประกอบที่ลิงก์จากรายงาน

## โครงสร้าง

```text
app/                   หน้าเว็บและตัวเปิด Streamlit
script/
  scraper/             เก็บข้อมูล แยก ennxo/mac2hand
  preparation/         ตรวจ clean review รวมและคัดข้อมูล
  analysis/eda/        วิเคราะห์ข้อมูลและสร้างรายงาน
  modeling/            features แบ่งข้อมูล เทรนและทำนาย
  tests/               โค้ดทดสอบ offline รวมฟอร์มเว็บ
config/                กฎและแผนทดลอง
data/{raw,intermediate,final}/  ต้นฉบับ ผลระหว่างทาง และชุดใช้ต่อ
models/                โมเดลใช้งาน+metadata รวม Git; โมเดลทดลองเก็บในเครื่อง
docs/                  เอกสารทั้งหมด อ่าน EDA ที่ eda.md และโมเดลที่ modeling.md
  assets/eda/          report.html, metadata.json, figures/, tables/
  assets/modeling/     ผลปัจจุบันแบบเดียวกัน + history.zip ของการทดลองเดิม
.github/workflows/ci.yml       ตรวจอัตโนมัติบน GitHub
.streamlit/config.toml        ธีมหน้าเว็บ
```

## ตรวจงาน

```bash
python -B -m unittest discover -s script/tests -t .
```

Workflow **CI** ตรวจ dependencies, syntax, การสร้าง input จากข้อมูลใน Git, ลิงก์เอกสาร/registry/checksum รายงาน และ tests เมื่อ push/PR เข้า `main` หรือกดรันเอง ไม่ scrape หรือเทรนโมเดลจริงใน CI

รอบปรับปรุงทดลอง 33 ตัวเลือกบนข้อมูลเดิม เลือก ensemble HGB + CatBoost จาก validation ตามเวลา; ผลย้อนหลังและข้อจำกัดอ่านใน [รายงานโมเดล](docs/modeling.md)

EDA เดิมสำรวจ 10,032 แถว ก่อนคัด 822 แถวออกเหลือ 9,210 แถว คะแนน V2 เป็นผลย้อนหลัง ไม่ใช่ผลทดสอบอิสระของโมเดลใช้งานที่ฝึกครบ อ่านขอบเขตคะแนนใน [รายงานโมเดล](docs/modeling.md)

ผลแต่ละขั้นใช้ `metadata.json` ไฟล์เดียวรวมสรุป กฎ ผลตรวจ และที่มา ชุดสุดท้ายมีเพียง `dataset.csv`, `condition_features.csv`, `metadata.json`; ข้อมูลรายแถวระหว่างทางอยู่ `data/intermediate/` ดูตำแหน่งปัจจุบันจาก `data/datasets.json`
