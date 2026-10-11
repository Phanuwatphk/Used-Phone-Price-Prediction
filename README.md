# Used Phone Asking Price Prediction

โครงงานทำนายราคาตั้งขายมือถือมือสอง หน่วยบาท เก็บข้อมูลจาก ENNXO และ Mac2Hand ตรวจชุด clean และรวม schema กลางแล้ว **10,032 แถว** ทุกแถวมีเว็บต้นทาง ทำ EDA แล้ว คัดชุดโมเดลรอบแรกเหลือ **9,210 แถว** ตามนโยบายตัดคิว822แถว แบ่งตามเวลาและปรับโมเดลรอบ 2 แล้ว

## เริ่มอ่าน

**ใช้งานผ่านฟอร์ม:** รัน `.venv/bin/python script/app/run_app.py` แล้วเข้า **http://localhost:8501** เลือกรุ่น กรอกข้อมูล และกดประเมินราคา ดู [วิธีเปิดแอปและรายการไฟล์](script/app/README.md) ต้องมีโมเดลในเครื่องก่อนเปิด

- **[สรุปผลโมเดล](docs/summary/modeling.md)** · [รายงานรายละเอียดและกราฟ](reports/modeling/asking_price_v2/report.md) · [วิธีเทรน/ทำนาย](script/modeling/README.md)

**ข้อมูลหลักสำหรับเทรน: [data/final/dataset.csv](data/final/dataset.csv) — 9,210 แถว** (ENNXO 1,202 / Mac2Hand 8,008) ชุดก่อนตัด 10,032 แถวเก็บใน intermediate เป็นประวัติ

- [ชุดใช้ต่อสำหรับโมเดล9,210แถว](docs/summary/model_input.md) · [นโยบายและวิธีคัด](docs/details/shared/model_input.md)

- [สรุป EDA](docs/summary/eda.md) · [รายงานพร้อมกราฟ](reports/eda/ennxo_20261005_mac2hand_20261006/report.md)
- [ชุดรวมและผลตรวจเบื้องต้น](docs/details/shared/combined_dataset.md)
- [สรุปทั้งโครงการ](docs/summary/scraping.md) · [สารบัญเอกสาร](docs/README.md)
- [ENNXO: ผลล่าสุด](docs/summary/ennxo.md) · [ผลตรวจรายรายการ](docs/details/ennxo/review.md)
- [Mac2Hand: สถานะและการเก็บ](docs/summary/mac2hand.md)
- [ไฟล์สำหรับ GitHub และวิธีใช้หลัง clone](docs/details/shared/github.md)
- [โครงสร้างและผลตรวจ](docs/details/shared/project_structure.md) · [บัญชี dataset](data/datasets.json)
- [คู่มือไฟล์และข้อมูล](docs/details/shared/data_guide.md) · [เก็บเว็บ](script/scraper/README.md) · [เตรียมข้อมูล](script/preparation/README.md) · [วิเคราะห์](script/analysis/README.md)

## สถานะ

| เว็บ | ประกาศใน snapshot | งานปัจจุบัน |
|---|---:|---|
| ENNXO | 1,381 | ผ่าน 1,279; พัก 84 = เครื่องเสีย/ล็อก 49 + ต้องมีหลักฐานเพิ่ม 35; แยกออก 18 |
| Mac2Hand | 10,220 | ส่งมอบ `final/dataset.csv` 8,753 แถว; คิวเดิม 1,789 มีผลครบ; อีก 1,467 แถวเก็บแยกตามเหตุผล |

คิว ENNXO เดิม 126 รายการตรวจครบแล้ว ผู้ใช้เลือกเก็บเครื่องเสีย/ล็อกศึกษาแยก โมเดลรอบแรกจะใช้กลุ่มที่ไม่มีอาการเสีย/ล็อกที่ตรวจพบ คิวถูกปิดตามผู้ใช้ ชุดสำหรับโมเดลตัดสมาชิกคิวEDAออกแล้ว แบ่งข้อมูลและเทียบ 15 ตัวเลือกแล้ว อ่านผลโมเดลด้านล่าง

## โครงสร้าง

```text
script/
  scraper/{ennxo,mac2hand}/         เก็บเว็บ parser และ monitor
  preparation/{ennxo,mac2hand,shared}/  ตรวจ clean รวมและคัดชุด
  analysis/eda/                    วิเคราะห์และรายงาน EDA
  modeling/                        แบ่งข้อมูล เทรน ประเมินและทำนาย (ทั้งสองเว็บ)
  app/                             ฟอร์มประเมินราคาสำหรับผู้ใช้ในเบราว์เซอร์
  tests/                           fixtures และ tests แบบ offline
config/{ennxo,mac2hand,shared,modeling}/  กฎ schema และแผนทดลอง
data/raw/                          ต้นฉบับและ checkpoint
data/intermediate/                 ผลระหว่างทาง หลักฐาน split และ prediction รายแถว
data/final/dataset.csv              ชุดใช้ต่อ 9,210 แถว
models/asking_price_v2/             โมเดล binary และ metadata (เก็บในเครื่อง)
reports/{eda,modeling}/<รอบ>/       รายงาน กราฟ ตารางรวมและผลตรวจ
docs/{summary,details}/             สรุปสั้นและคู่มือรายละเอียด
archive/                           งานเก่าที่ไม่ใช้ใน pipeline ปัจจุบัน
```

ชุดหลักอยู่ใน `data/final/dataset.csv` ผลผ่านเฉพาะเว็บอยู่ใน `data/final/<เว็บ>/<รอบ>/` หลักฐานและกลุ่มปัญหาอยู่ใน `data/intermediate/<เว็บ>/<รอบ>/` ผลเตรียมเดิมอยู่ใน `archive/mac2hand/<รอบ>/` ดู [คู่มือข้อมูล](data/README.md) ก่อนเลือกไฟล์มาใช้ รวมเฉพาะกลุ่มผ่านไว้ใน `data/intermediate/combined/ennxo_20261005_mac2hand_20261006/before_selection/` แล้ว; ตรวจเบื้องต้นแยกเว็บเสร็จ ทำ EDA ร่วมแล้ว คัดคิวEDAออกจากชุดโมเดลแล้ว ฝึกและประเมินบน test ที่กันไว้แล้ว

## ติดตั้งและทดสอบ

ใช้ Python 3.12 ขึ้นไป คำสั่งจากรากโปรเจค:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -B -m unittest discover -s script/tests -t .
```

ผลตรวจล่าสุด: **145 tests ผ่าน** รวม workflow ชุดรวม/EDA; รองรับรันไฟล์จาก directory อื่นและรันโมดูล, dependencies ไม่ขัดกัน และ checksum raw ทั้งสองเว็บตรงเดิม ดู [รายละเอียดการจัดโครงสร้าง](docs/details/shared/project_structure.md)

`requirements.txt` ระบุ dependencies หลัก ส่วน `requirements-lock.txt` ระบุเวอร์ชันที่ใช้ตรวจงานนี้ ไม่ต้องติดตั้งใหม่หากมี environment ที่พร้อมแล้ว

ดูวิธีรัน ENNXO ใน [คู่มือวิธีทำ](docs/details/ennxo/methodology.md) และตรวจความคืบหน้า Mac2Hand ใน [คู่มือ monitor](docs/details/mac2hand/pipeline.md) ใช้ตัวเก็บ Mac2Hand เพียงหนึ่งงานต่อรอบ

Repository รวมชุดโมเดล 9,210 แถวและไฟล์กำกับแล้ว หลัง clone อ่านชุดนี้และรัน tests ได้ ส่วนการทำซ้ำตั้งแต่ scraping/clean/EDA เดิมต้องคืน raw, intermediate และ ledger จากสำเนาส่วนตัว ดู [คู่มือ GitHub](docs/details/shared/github.md)

Raw, intermediate และผลผ่านเฉพาะเว็บสำรองแยก ไม่รวมใน Git ราคาที่เก็บเป็นราคาประกาศ และสภาพเป็นข้อมูลที่ผู้ขายระบุ

## เทรนและทำนาย

```bash
.venv/bin/python -u -B script/modeling/train_improved.py
.venv/bin/python -B script/modeling/predict.py --source mac2hand --brand Apple --model 'iPhone 13' --storage-gb 128 --condition used --published-at 2026-10-06
```

V2 เลือกจาก validation ตามเวลา 2 ช่วง ทดลอง 12 ตัวเลือก; ผลย้อนหลังบน 693 แถวเดิม MAE ลดจาก 8,108 เป็น 5,339 บาท (34.1%) โมเดลใช้งานแยกฟิตครบ 9,210 แถว / 300 รุ่น ไม่มีคะแนน test อิสระของตัวที่ฟิตครบ ชุดประเมินเดิมที่เคยดูแล้วใช้เปรียบเทียบย้อนหลังเท่านั้น โมเดล/ผลรายแถวไม่รวม Git; โค้ด config และรายงานผลรวมอยู่ใน repo อ่าน [วิธีทดลองและทุกไฟล์](docs/details/shared/modeling.md)
