# โครงสร้างโครงการตามขั้นตอน

จัดเมื่อ 2026-10-11 แยกโค้ดตามหน้าที่ และแยกเว็บภายในขั้นที่มีกฎเฉพาะเว็บ เลือกชุดข้อมูลปัจจุบันจาก [registry](../../../data/datasets.json)

```text
scraper/
  ennxo/                         ตัวเก็บ ENNXO และ parser HTML
  mac2hand/                      ตัวเก็บ Mac2Hand, parser และ monitor
preparation/
  ennxo/                         audit → extraction → clean → review → export
  mac2hand/                      audit/extraction → clean → review → finalization
  shared/                        ตรวจสองเว็บ ปรับ schema และรวม
analysis/
  eda/                           สถิติและสร้างกราฟ/รายงาน EDA
config/{ennxo,mac2hand,shared}/   กฎ schema catalogue และ ledger

data/
  raw/<เว็บ_เวลารอบ>/             ต้นฉบับและ checkpoint การเก็บ
  intermediate/
    ennxo/<รอบ>/                 audit, extraction, clean, review และ history
    mac2hand/<รอบ>/              audit, extraction, clean, review และ finalization
    combined/<รอบ>/              lineage, audit รายเว็บ และค่าที่ normalize
    eda/<รอบ>/                   คิว outlier/candidate รายแถว
  final/dataset.csv              ชุดโมเดล9,210แถว รวมในGit
  final/{ennxo,mac2hand}/<รอบ>/    ผลผ่านเฉพาะเว็บ สำรองในเครื่อง
  datasets.json                  บัญชีชุดปัจจุบัน

reports/eda/<รอบ>/
  summary.md                     สรุปอ่านสั้น
  report.md, report.html          รายงานรายละเอียดและกราฟ
  figures/                       กราฟ PNG/SVG
  tables/                        ตารางสถิติรวม CSV
  *.json                         สถิติ กฎ ผลตรวจ และ hash สำหรับทำซ้ำ

docs/summary/                    สรุปแยกเว็บ การเก็บ และ EDA
docs/details/{ennxo,mac2hand,shared}/
                                 วิธีทำ หลักฐาน คู่มือ และบัญชีย้ายไฟล์
script/tests/                    fixtures และการทดสอบ workflow
archive/                         งานเก่าที่ไม่ใช้ใน pipeline ปัจจุบัน
```

## มาตรฐานตำแหน่งและชื่อ

ชื่อเว็บใช้ `ennxo`, `mac2hand`; `shared` คือโค้ด/กฎที่ใช้ทั้งคู่, `combined` คือชุดข้อมูลที่รวมแล้ว ชื่อรอบต้นทางคงเวลาการเก็บเดิม ชุดรวมและรายงาน EDA ใช้รอบเดียวกันเพื่อจับคู่ได้ ชื่อไฟล์ Python ใช้ snake_case และโฟลเดอร์หลักใช้ตัวพิมพ์เล็ก

raw คือไฟล์ที่เก็บจากเว็บ; intermediate คือผลระหว่างทาง ข้อมูลทุกสถานะและหลักฐานตรวจ; final คือชุดผ่านที่ส่งต่อพร้อมข้อมูลกำกับ ไม่ใช้คำว่า final แทนข้อมูลที่ยืนยันสภาพเครื่องหรือผ่านการแบ่ง train/test แล้ว รายงานขั้น audit/clean อยู่กับขั้นนั้น ส่วนรายงาน EDA อยู่ reports เท่านั้น

อ่าน [สคริปต์เก็บ](../../../scraper/README.md), [สคริปต์เตรียม](../../../preparation/README.md), [สคริปต์วิเคราะห์](../../../analysis/README.md) และ [คู่มือไฟล์](data_guide.md)

## การย้ายและทำซ้ำ

[บัญชีรอบนี้](migrations/stage_reorganization_20261011.json) เก็บ old→new และ SHA-256 ของผลข้อมูล 168 ไฟล์ ตรวจตรงเดิมทั้งหมด ไม่แก้ metadata เก่าเพื่อให้ประวัติยังตรงกับเวลาที่สร้าง อัปเดต path ในโค้ด คู่มือ registry และ baseline pointer ของ ledger ENNXO ให้ชี้ตำแหน่งใหม่ โดยคงคำตัดสินเดิม

เพิ่ม ENNXO export เพื่อคัดลอกกลุ่มผ่านไป final อย่างทำซ้ำได้; Mac2Hand finalization และตัวรวมมีปลายทางเสริมสำหรับหลักฐานใน intermediate API ที่เรียกแบบเดิมยังรองรับ output bundle เดียว แต่ CLI ค่าเริ่มต้นแยกขั้นตามโครงสร้างนี้

รายละเอียดผลตรวจรอบจัดโครงสร้างอยู่ใน [validation](migrations/stage_reorganization_validation_20261011.json) ไม่เริ่ม scrape ใหม่หรือฝึกโมเดล ข้อมูลจริงและ ledger สำรองแยกจาก Git ดู [การจัดไฟล์ GitHub](github.md)

ย้ายโฟลเดอร์ tests ทั้งชุดไป `script/tests/` ตามคำขอผู้ใช้ แก้ import fixtures และ path config พร้อม CI ผ่าน125tests ทั้งจากรากโปรเจคและ `/tmp` ดู [บัญชีย้าย](migrations/tests_reorganization_20261011.json)

เพิ่ม preparation/shared/select_model_input.py สำหรับคัดตามนโยบายทั้งสองเว็บ ผลใช้ต่ออยู่ data/final/ และเหตุผลคัดอยู่ data/intermediate/model_input/<รอบ>/ ดู [คู่มือ](model_input.md)

ตำแหน่งสำหรับcommitล่าสุด: data/final/dataset.csv คือชุดหลัก9,210แถว เปิดเฉพาะ8ไฟล์ข้อมูลกำกับในGit ชุดก่อนตัด10,032แถวย้ายไป intermediate/combined/<รอบ>/before_selection ดู [บัญชีย้าย](migrations/publish_dataset_layout_20261011.json)
