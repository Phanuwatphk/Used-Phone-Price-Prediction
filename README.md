# Used Phone Price

เว็บ Streamlit สำหรับประเมินราคาตั้งขายมือถือ สำรวจประกาศ และดูผลโมเดล ใช้ข้อมูล ENNXO และ Mac2Hand ที่ตรวจและคัดแล้ว **9,210 ประกาศ** ทุกแถวมีเว็บต้นทาง ผลราคาเป็นการประมาณราคาประกาศ หน่วยบาท

## เปิดใช้งาน

ใช้ Python 3.12 และรันจากรากโปรเจค:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m streamlit run script/app/app.py
```

เข้า **http://localhost:8501** มี 3 เมนู:

- **ประเมินราคา** — เลือกรุ่น กรอกความจุ และข้อมูลเพิ่มเติมที่ทราบ สำหรับมือถือมือสอง
- **สำรวจข้อมูล** — กรองเว็บ ยี่ห้อ รุ่น สภาพและปี ดูกราฟ/ตาราง และดาวน์โหลด CSV
- **ผลโมเดล** — ดูผลประเมินย้อนหลัง แยกเว็บ และข้อจำกัด

โมเดลใช้งาน `models/asking_price_v2/model.joblib` และ `metadata.json` รวมใน Git แล้ว จึงประเมินได้หลัง clone โดยไม่ต้องเทรนเอง แอปไม่ scrape หรือเทรนระหว่างใช้งาน หากต้องการฝึกใหม่ ใช้ `python -u -B script/modeling/train_improved.py`

Deploy บน Streamlit Community Cloud: เลือกไฟล์ **`script/app/app.py`**, Python **3.12** และ branch ที่ commit ไฟล์โมเดลทั้งสองแล้ว `requirements.txt` ใช้เวอร์ชันจาก `requirements-lock.txt` เพื่อให้ตรงกับ artifact อ่าน [วิธี deploy และแก้ปัญหา](docs/development.md#deploy)

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
script/
  app/                 หน้าเว็บและตัวเปิด Streamlit
  scraper/             เก็บข้อมูล แยก ennxo/mac2hand
  preparation/         ตรวจ clean review รวมและคัดข้อมูล
  analysis/eda/        วิเคราะห์ข้อมูลและสร้างรายงาน
  modeling/            features แบ่งข้อมูล เทรนและทำนาย
  tests/               โค้ดทดสอบ offline รวมฟอร์มเว็บ
config/                กฎและแผนทดลอง
data/{raw,intermediate,final}/  ต้นฉบับ ผลระหว่างทาง และชุดใช้ต่อ
models/                โมเดลใช้งาน+metadata รวม Git; โมเดลทดลองเก็บในเครื่อง
docs/                  เอกสารทั้งหมด อ่าน EDA ที่ eda.md และโมเดลที่ modeling.md
  assets/              กราฟ ตาราง และไฟล์ประกอบรายงาน
.github/workflows/ci.yml       ตรวจอัตโนมัติบน GitHub
.streamlit/config.toml        ธีมหน้าเว็บ
```

## ตรวจงาน

```bash
python -B -m unittest discover -s script/tests -t .
```

Workflow **CI** ตรวจ dependencies, syntax, การสร้าง input จากข้อมูลใน Git และ tests เมื่อ push/PR เข้า `main` หรือกดรันเอง ไม่ scrape หรือเทรนโมเดลจริงใน CI

EDA เดิมสำรวจ 10,032 แถว ก่อนคัด 822 แถวออกเหลือ 9,210 แถว คะแนน V2 เป็นผลย้อนหลัง ไม่ใช่ผลทดสอบอิสระของโมเดลใช้งานที่ฝึกครบ อ่านขอบเขตคะแนนใน [รายงานโมเดล](docs/modeling.md)
