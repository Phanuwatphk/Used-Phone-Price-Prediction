# Used Phone Asking Price Prediction

โครงงานทำนายราคาตั้งขายมือถือมือสอง หน่วยบาท เก็บข้อมูลจาก ENNXO และ Mac2Hand ตรวจชุด clean และรวม schema กลางแล้ว **10,032 แถว** ทุกแถวมีเว็บต้นทาง ทำ EDA แล้ว คัดชุดโมเดลรอบแรกเหลือ **9,210 แถว** ตามนโยบายตัดคิว822แถว ยังไม่แบ่ง train/test หรือฝึกโมเดล

## เริ่มอ่าน

**ข้อมูลหลักสำหรับเทรน: [data/final/dataset.csv](data/final/dataset.csv) — 9,210 แถว** (ENNXO 1,202 / Mac2Hand 8,008) ชุดก่อนตัด 10,032 แถวเก็บใน intermediate เป็นประวัติ

- [ชุดใช้ต่อสำหรับโมเดล9,210แถว](docs/summary/model_input.md) · [นโยบายและวิธีคัด](docs/details/shared/model_input.md)

- [สรุป EDA](docs/summary/eda.md) · [รายงานพร้อมกราฟ](reports/eda/ennxo_20261005_mac2hand_20261006/report.md)
- [ชุดรวมและผลตรวจเบื้องต้น](docs/details/shared/combined_dataset.md)
- [สรุปทั้งโครงการ](docs/summary/scraping.md) · [สารบัญเอกสาร](docs/README.md)
- [ENNXO: ผลล่าสุด](docs/summary/ennxo.md) · [ผลตรวจรายรายการ](docs/details/ennxo/review.md)
- [Mac2Hand: สถานะและการเก็บ](docs/summary/mac2hand.md)
- [ไฟล์สำหรับ GitHub และวิธีใช้หลัง clone](docs/details/shared/github.md)
- [โครงสร้างและผลตรวจ](docs/details/shared/project_structure.md) · [บัญชี dataset](data/datasets.json)
- [คู่มือไฟล์และข้อมูล](docs/details/shared/data_guide.md) · [เก็บเว็บ](scraper/README.md) · [เตรียมข้อมูล](preparation/README.md) · [วิเคราะห์](analysis/README.md)

## สถานะ

| เว็บ | ประกาศใน snapshot | งานปัจจุบัน |
|---|---:|---|
| ENNXO | 1,381 | ผ่าน 1,279; พัก 84 = เครื่องเสีย/ล็อก 49 + ต้องมีหลักฐานเพิ่ม 35; แยกออก 18 |
| Mac2Hand | 10,220 | ส่งมอบ `final/dataset.csv` 8,753 แถว; คิวเดิม 1,789 มีผลครบ; อีก 1,467 แถวเก็บแยกตามเหตุผล |

คิว ENNXO เดิม 126 รายการตรวจครบแล้ว ผู้ใช้เลือกเก็บเครื่องเสีย/ล็อกศึกษาแยก โมเดลรอบแรกจะใช้กลุ่มที่ไม่มีอาการเสีย/ล็อกที่ตรวจพบ คิวถูกปิดตามผู้ใช้ ชุดสำหรับโมเดลตัดสมาชิกคิวEDAออกแล้ว เหลือขั้นแบ่งข้อมูลและฝึกbaseline

## โครงสร้าง

```text
scraper/{ennxo,mac2hand}/          เก็บเว็บ อ่าน HTML และ monitor
preparation/{ennxo,mac2hand,shared}/  ตรวจ raw ถอด clean review ส่งมอบและรวม
analysis/eda/                    วิเคราะห์สถิติและสร้างรายงาน EDA
config/{ennxo,mac2hand,shared}/   กฎ schema catalogue และ ledger
data/raw/<เว็บ_เวลารอบ>/          ต้นฉบับ HTML และ checkpoint
data/intermediate/<เว็บ>/<รอบ>/   ผลระหว่างทาง ทุกสถานะและหลักฐานตรวจ
data/intermediate/{combined,eda}/<รอบ>/  lineage และคิววิเคราะห์
data/final/dataset.csv           ชุดใช้เทรน 9,210 แถว พร้อมข้อมูลกำกับ
data/final/{ennxo,mac2hand}/<รอบ>/  ผลผ่านเฉพาะเว็บ สำรองในเครื่อง
reports/eda/<รอบ>/               รายงาน กราฟ และตารางสถิติรวม
docs/{summary,details}/          สรุปอ่านสั้นและคู่มือรายละเอียด
script/tests/                   ทดสอบ workflow โดยใช้ fixtures
archive/                        งานเก่าที่ไม่ใช้ใน pipeline ปัจจุบัน
```

ชุดหลักอยู่ใน `data/final/dataset.csv` ผลผ่านเฉพาะเว็บอยู่ใน `data/final/<เว็บ>/<รอบ>/` หลักฐานและกลุ่มปัญหาอยู่ใน `data/intermediate/<เว็บ>/<รอบ>/` ผลเตรียมเดิมอยู่ใน `archive/mac2hand/<รอบ>/` ดู [คู่มือข้อมูล](data/README.md) ก่อนเลือกไฟล์มาใช้ รวมเฉพาะกลุ่มผ่านไว้ใน `data/intermediate/combined/ennxo_20261005_mac2hand_20261006/before_selection/` แล้ว; ตรวจเบื้องต้นแยกเว็บเสร็จ ทำ EDA ร่วมแล้ว คัดคิวEDAออกจากชุดโมเดลแล้ว อยู่ขั้นเตรียมแบ่งข้อมูล

## ติดตั้งและทดสอบ

ใช้ Python 3.12 ขึ้นไป คำสั่งจากรากโปรเจค:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -B -m unittest discover -s script/tests -t .
```

ผลตรวจล่าสุด: **129 tests ผ่าน** รวม workflow ชุดรวม/EDA; รองรับรันไฟล์จาก directory อื่นและรันโมดูล, dependencies ไม่ขัดกัน และ checksum raw ทั้งสองเว็บตรงเดิม ดู [รายละเอียดการจัดโครงสร้าง](docs/details/shared/project_structure.md)

`requirements.txt` ระบุ dependencies หลัก ส่วน `requirements-lock.txt` ระบุเวอร์ชันที่ใช้ตรวจงานนี้ ไม่ต้องติดตั้งใหม่หากมี environment ที่พร้อมแล้ว

ดูวิธีรัน ENNXO ใน [คู่มือวิธีทำ](docs/details/ennxo/methodology.md) และตรวจความคืบหน้า Mac2Hand ใน [คู่มือ monitor](docs/details/mac2hand/pipeline.md) ใช้ตัวเก็บ Mac2Hand เพียงหนึ่งงานต่อรอบ

Repository รวมชุดโมเดล 9,210 แถวและไฟล์กำกับแล้ว หลัง clone อ่านชุดนี้และรัน tests ได้ ส่วนการทำซ้ำตั้งแต่ scraping/clean/EDA เดิมต้องคืน raw, intermediate และ ledger จากสำเนาส่วนตัว ดู [คู่มือ GitHub](docs/details/shared/github.md)

Raw, intermediate และผลผ่านเฉพาะเว็บสำรองแยก ไม่รวมใน Git ราคาที่เก็บเป็นราคาประกาศ และสภาพเป็นข้อมูลที่ผู้ขายระบุ
