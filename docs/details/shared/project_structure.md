# โครงสร้างโครงการตามขั้นตอน

จัดเมื่อ 2026-10-11 แยกโค้ดตามหน้าที่ และแยกเว็บภายในขั้นที่มีกฎเฉพาะเว็บ เลือกชุดข้อมูลปัจจุบันจาก [registry](../../../data/datasets.json)

```text
script/
  scraper/{ennxo,mac2hand}/       เก็บเว็บ parser และ monitor
  preparation/{ennxo,mac2hand,shared}/  audit/extraction/clean/review/รวม/คัด
  analysis/eda/                  สถิติและรายงาน EDA
  modeling/                      split → compare → select → refit → test → predict
  app/                           ฟอร์มภาษาไทยและตัวเปิดแอป ใช้โมเดลที่เทรนแล้ว
  tests/                         fixtures และ tests offline
config/{ennxo,mac2hand,shared,modeling}/
data/
  raw/                           ต้นฉบับเก็บเว็บ
  intermediate/                  ผลระหว่างทาง หลักฐาน และคิวประวัติ
    modeling/asking_price_v1/     split CSV/assignments/hashes และผลทำนายรายแถว
  final/dataset.csv              ชุด 9,210 แถวก่อน split รวมใน Git
  final/{ennxo,mac2hand}/         ผลผ่านเฉพาะเว็บสำรองในเครื่อง
  datasets.json                  บัญชีชุดข้อมูลและโมเดล
models/asking_price_v1/           artifact และ metadata ในเครื่อง
reports/{eda,modeling}/<รอบ>/     สรุป รายละเอียด HTML กราฟ ตาราง และผลตรวจ
docs/{summary,details}/          คู่มือสั้น/ละเอียด แยกเว็บและ shared
archive/                         งานเก่า ไม่ใช้ใน pipeline ปัจจุบัน
```

## มาตรฐานตำแหน่งและชื่อ

ชื่อเว็บใช้ `ennxo`, `mac2hand`; `shared` คือโค้ด/กฎที่ใช้ทั้งคู่, `combined` คือชุดข้อมูลที่รวมแล้ว ชื่อรอบต้นทางคงเวลาการเก็บเดิม ชุดรวมและรายงาน EDA ใช้รอบเดียวกันเพื่อจับคู่ได้ ชื่อไฟล์ Python ใช้ snake_case และโฟลเดอร์หลักใช้ตัวพิมพ์เล็ก

raw คือไฟล์ที่เก็บจากเว็บ; intermediate คือผลระหว่างทาง ข้อมูลทุกสถานะและหลักฐานตรวจ; final คือชุดผ่านที่ส่งต่อพร้อมข้อมูลกำกับ ไม่ใช้คำว่า final แทนข้อมูลที่ยืนยันสภาพเครื่องหรือผ่านการแบ่ง train/test แล้ว รายงานขั้น audit/clean อยู่กับขั้นนั้น ส่วนรายงาน EDA อยู่ reports เท่านั้น

อ่าน [สคริปต์เก็บ](../../../script/scraper/README.md), [สคริปต์เตรียม](../../../script/preparation/README.md), [สคริปต์วิเคราะห์](../../../script/analysis/README.md) และ [คู่มือไฟล์](data_guide.md)

## การย้ายและทำซ้ำ

[บัญชีรอบนี้](migrations/stage_reorganization_20261011.json) เก็บ old→new และ SHA-256 ของผลข้อมูล 168 ไฟล์ ตรวจตรงเดิมทั้งหมด ไม่แก้ metadata เก่าเพื่อให้ประวัติยังตรงกับเวลาที่สร้าง อัปเดต path ในโค้ด คู่มือ registry และ baseline pointer ของ ledger ENNXO ให้ชี้ตำแหน่งใหม่ โดยคงคำตัดสินเดิม

เพิ่ม ENNXO export เพื่อคัดลอกกลุ่มผ่านไป final อย่างทำซ้ำได้; Mac2Hand finalization และตัวรวมมีปลายทางเสริมสำหรับหลักฐานใน intermediate API ที่เรียกแบบเดิมยังรองรับ output bundle เดียว แต่ CLI ค่าเริ่มต้นแยกขั้นตามโครงสร้างนี้

รายละเอียดผลตรวจรอบจัดโครงสร้างอยู่ใน [validation](migrations/stage_reorganization_validation_20261011.json) ไม่เริ่ม scrape ใหม่หรือฝึกโมเดล ข้อมูลจริงและ ledger สำรองแยกจาก Git ดู [การจัดไฟล์ GitHub](github.md)

ย้ายโฟลเดอร์ tests ทั้งชุดไป `script/tests/` ตามคำขอผู้ใช้ แก้ import fixtures และ path config พร้อม CI ผ่าน125tests ทั้งจากรากโปรเจคและ `/tmp` ดู [บัญชีย้าย](migrations/tests_reorganization_20261011.json)

เพิ่ม script/preparation/shared/select_model_input.py สำหรับคัดตามนโยบายทั้งสองเว็บ ผลใช้ต่ออยู่ data/final/ และเหตุผลคัดอยู่ data/intermediate/model_input/<รอบ>/ ดู [คู่มือ](model_input.md)

ตำแหน่งสำหรับcommitล่าสุด: data/final/dataset.csv คือชุดหลัก9,210แถว เปิดเฉพาะ8ไฟล์ข้อมูลกำกับในGit ชุดก่อนตัด10,032แถวย้ายไป intermediate/combined/<รอบ>/before_selection ดู [บัญชีย้าย](migrations/publish_dataset_layout_20261011.json)

ย้ายโค้ด scraper/preparation/analysis ทั้งหมดเข้า script ตามคำขอผู้ใช้ แก้ imports และ ROOT ตามตำแหน่งไฟล์ ไม่ย้าย raw หรือแก้ metadata ประวัติ ดู [บัญชีย้ายสคริปต์](migrations/scripts_reorganization_20261011.json) และ [คู่มือโมเดล](modeling.md) Tests ปัจจุบัน 135 ข้อรวมการป้องกัน leakage และ artifact roundtrip

รอบล่าสุด V2 แยก operational model fit ครบจาก evaluation model, เพิ่ม public numerical sidecar ที่ data/final/condition_features.csv เพื่อ rebuild หลัง clone ดู [ทุกไฟล์](modeling.md) Tests ปัจจุบัน 140 ข้อ ข้อมูลหลักไม่เปลี่ยน

เพิ่มหน้าจอผู้ใช้ใน `script/app/` แล้ว คู่มือหน้าที่ไฟล์และวิธีเปิดอยู่ [ที่นี่](../../../script/app/README.md) ผลทำนายแสดงบนหน้าจอ ไม่มี dataset ใหม่ ผลตรวจล่าสุด 145 tests ผ่าน รวมฟอร์ม 5 ข้อ และเปิดเซิร์ฟเวอร์จาก directory อื่นได้
