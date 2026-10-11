# ตรวจชุด clean และรวม dataset

> เอกสารนี้อธิบายขั้นรวมก่อน EDA; ผลวิเคราะห์ปัจจุบันอ่าน [วิธีทำ EDA](eda.md)

ชุดรวมล่าสุด **10,032 แถว** อยู่ใน `data/intermediate/combined/ennxo_20261005_mac2hand_20261006/before_selection/dataset.csv` ทุกแถวมี `source`, `product_id`, `url` และ `listing_id` ที่ไม่ชนข้ามเว็บ ใช้เฉพาะ accepted เดิม ไม่จำกัดช่วงวันที่

## ผลตรวจแยกเว็บ

| เว็บ | แถว | สัดส่วนชุดรวม | วันที่ประกาศหลังปรับเป็นวันไทย | ราคา (บาท) |
|---|---:|---:|---|---:|
| ENNXO | 1,279 | 12.75% | 2024-05-11 ถึง 2026-10-05 | 299–119,000 |
| Mac2Hand | 8,753 | 87.25% | 2010-04-02 ถึง 2026-10-06 | 350–320,000 |

คอลัมน์หลักครบ ไม่มีค่าขาด ไม่มี product_id/URL ซ้ำภายในแต่ละชุด ตรวจ status/เหตุผลค้างแล้วรับเฉพาะกลุ่มผ่าน `source` เดิมมีครบและตรงเว็บใน URL ทุกแถว หากรอบอื่นขาด source สคริปต์เติมจากบัญชี input หลังตรวจ domain และรหัส URL; ถ้าค่าเดิมขัดกันจะหยุด ไม่ทับค่าเงียบๆ

มี Apple 9,225 แถว (ประมาณ 92%) สภาพช่องผู้ขาย used 9,921 และ new 111 แถว ช่วงเวลาและสัดส่วนยี่ห้อต่างกันมาก ต้องพิจารณาใน EDA ร่วมและการประเมินโมเดล

## Schema ที่ใช้ร่วมกัน

กฎอยู่ใน `config/shared/dataset_schema.json` ใช้ทั้งสองเว็บ

| คอลัมน์ | ชนิด/ความหมาย |
|---|---|
| `listing_id` | string เช่น `ennxo:1206650`; key ของประกาศในชุดรวม |
| `source`, `source_snapshot` | เว็บและรอบข้อมูลต้นทาง |
| `product_id`, `url` | string เก็บรหัส/URL เดิม ไม่ใช้รหัสเป็นตัวเลขฟีเจอร์ |
| `brand`, `model` | string ชื่อยี่ห้อและรุ่นหลังปรับรูปแบบ |
| `storage_gb` | integer ความจุ GB ที่ source cleaner อ่านได้ |
| `condition` | used/new ตามช่องผู้ขาย ไม่ใช่ผลตรวจเครื่องจริง |
| `price_thb` | number ราคาตั้งขายเต็มเป็นบาท ไม่ใช่ราคาปิดการขาย |
| `published_at` | วัน `YYYY-MM-DD` มาตรฐาน Asia/Bangkok |
| `published_at_raw` | วันที่/เวลาเดิมก่อนแปลง |
| `published_at_precision` | day สำหรับวันที่อย่างเดียว หรือ timestamp สำหรับวันที่พร้อมเวลา |

CSV ต้องกำหนด dtype เมื่อโหลด โดยเฉพาะ product_id; `dataset.jsonl` เก็บชนิด JSON ชัดเจนเป็น string/integer/number มี source เฉพาะชื่อเว็บ ไม่มีค่า unknown

ปรับชื่อรุ่น 48 แถว เช่น `iPhone SE 2020` → `iPhone SE 2`, `Galaxy Z Flip4` → `Galaxy Z Flip 4`, `Xiaomi 13` → `13` เมื่อ brand เป็น Xiaomi ไม่รวมรุ่นย่อยต่างกันด้วย fuzzy matching และไม่รวมแบรนด์ Redmi เข้า Xiaomi

แปลง timestamp ENNXO 1,279 แถวเป็นวันไทย มี 94 แถวเปลี่ยนวันจาก UTC เพราะ timezone ส่วน Mac2Hand คงวันเดิม ไม่สร้างเวลาที่เว็บไม่ได้ระบุ เก็บค่าก่อนแปลงไว้ทุกแถว

## ประเด็นที่พบและงานถัดไป

ตรวจราคาสูงสุดย้อนข้อความที่เก็บไว้แล้ว: ENNXO `1156249` iPhone 13 128GB ราคา 119,000 มีข้อมูลดาวน์/ผ่อนในรายละเอียด แต่ยังไม่มีราคาขายเต็มทางเลือกที่ยืนยันได้; Mac2Hand `69078` iPhone 7 Plus 128GB ราคา 320,000 ไม่มีราคาทางเลือกชัดในรายละเอียด จึงยังไม่แก้เป็น 11,900 หรือ 32,000 ด้วยการคาดเดา

`price_review.csv` เก็บ 5 ราคาสูงสุดต่อเว็บเพื่อทบทวน รวม 10 แถว **ไม่ใช่ 10 แถวที่ยืนยันว่าผิด** และยังคงอยู่ใน dataset ต้องตรวจตามรุ่น/ความจุ/วันที่และหลักฐานราคาใน EDA ต่อ ก่อนเลือกนโยบาย outlier สำหรับฝึก

ยังไม่ตรวจประกาศซ้ำข้ามเว็บ ไม่ลบ candidate ที่ดูเหมือนกัน ไม่ทำ EDA ร่วมเต็มรูปแบบ ไม่แบ่ง train/test และไม่ฝึกโมเดล กลุ่มเครื่องเสีย/ล็อก/รอหลักฐานไม่ได้รวมมา

## สคริปต์ที่รัน

```bash
.venv/bin/python -u -B preparation/shared/prepare_combined_dataset.py
```

อ่าน CSV ที่ `data/datasets.json` ระบุ: ENNXO และ Mac2Hand ใช้ `data/final/<เว็บ>/<รอบ>/dataset.csv` ตรวจ hash จำนวน ฟิลด์ ชนิดข้อมูลและ URL ก่อน normalize แล้วรวม รองรับรันจาก directory อื่นผ่าน absolute path และ `python -m preparation.shared.prepare_combined_dataset` จากรากโปรเจค ไม่ส่ง request ไม่แก้ raw/CSV/ledger ต้นทาง

## ไฟล์ผลเก็บอะไร

dataset CSV/JSONL, schema, summary/report/validation/metadata อยู่ใน `data/intermediate/combined/ennxo_20261005_mac2hand_20261006/before_selection/` ส่วน lineage, audit รายเว็บ, normalization_changes และ price_review อยู่ใน `data/intermediate/combined/ennxo_20261005_mac2hand_20261006/audit/` ใช้ `--output` และ `--audit-output` เพื่อเลือกปลายทางสองขั้น

| ไฟล์ | เก็บอะไร |
|---|---|
| `dataset.csv` | ชุดรวม 10,032 แถว schema กลาง |
| `dataset.jsonl` | ชุดเดียวกัน พร้อมชนิดข้อมูล JSON ชัดเจน |
| `lineage.jsonl` | mapping ทุกแถวกลับ CSV ต้นทาง หมายเลข record hash และค่าเดิมทุกคอลัมน์ รวมฟิลด์เฉพาะเว็บ |
| `ennxo_audit.json`, `mac2hand_audit.json` | ค่าขาด จำนวนรุ่น ยี่ห้อ ความจุ สภาพ ช่วงราคา quartile และวันที่แยกเว็บ |
| `price_review.csv` | ราคาสูงสุดที่ควรทบทวน พร้อม URL และงานถัดไป |
| `normalization_changes.json` | ค่าที่เปลี่ยนก่อน/หลัง เช่นรูปแบบชื่อรุ่น ราคา และวัน |
| `schema.json` | สำเนา schema/alias ที่ใช้กับรอบนี้ |
| `summary.json`, `report.md` | จำนวนรวม สัดส่วนและสรุปข้อจำกัด |
| `validation.json` | ผลตรวจจำนวน source key ฟิลด์ และข้อมูลเข้าไม่เปลี่ยน |
| `run_metadata.json` | เวลา โค้ด/schema/input hashes บัญชี input และ hash dataset |

ผ่าน 110 tests รวม source ที่ขาด/ขัดกัน URLไม่ตรง ตัวเลข/วันไม่ถูกต้อง namespace รหัส การไม่เปลี่ยน input การเก็บ lineage และทำซ้ำผล CSV รัน workflow จริงจาก `/tmp` ได้
