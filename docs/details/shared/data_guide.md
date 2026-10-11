# คู่มือไฟล์และผลลัพธ์

ภาพรวมสั้นอยู่ใน [data/README](../../../data/README.md) และ [โครงสร้างโครงการ](project_structure.md) Path และจำนวนชุดปัจจุบันอยู่ใน [datasets.json](../../../data/datasets.json) ตารางนี้อธิบายไฟล์ตามขั้น ไม่ใช้ผล baseline แทนชุดล่าสุด

## Raw: ต้นฉบับ

`data/raw/<เว็บ_เวลารอบ>/` เก็บ `listings.jsonl` หนึ่งประกาศต่อ record, `pages/` HTML หน้ารวม, `details/` รายละเอียดสินค้าที่เก็บได้ ENNXO มี `ennxo_public_payload.json` ข้อมูลสินค้าฝังในหน้า และ `ennxo_summary.json` สรุปรอบ ส่วน Mac2Hand มี manifest ระบุผลเก็บราย URL รวม checkpoint/log ของตัวเก็บ อ่าน [raw ENNXO](../ennxo/raw.md) และ [pipeline Mac2Hand](../mac2hand/pipeline.md) สำหรับชื่อไฟล์เฉพาะเว็บ

## Intermediate: ตรวจ ถอด clean และ review

ผลอยู่ใน `data/intermediate/<เว็บ>/<รอบ>/`:

| โฟลเดอร์ / ไฟล์หลัก | เก็บอะไร |
|---|---|
| `raw_audit/{summary,profile,issues}.json`, `field_profile.csv` หรือ `issues.csv` | จำนวน ความครบ ค่าขาด และปัญหาที่ตรวจได้ รูปแบบไฟล์ต่างตามเว็บ |
| `raw_audit/raw_checksums.json` | hash ไฟล์ raw ใช้ตรวจว่าต้นฉบับตรงรอบ |
| `extraction/{ennxo,mac2hand}_extracted.jsonl` | ทุกประกาศพร้อมค่าถอดใหม่ ต้นฉบับและ provenance |
| `extraction/observations.csv`, `page_accounting.json` ที่มี | ข้อสังเกตและบัญชีการจับคู่หน้า/ประกาศ ENNXO |
| `clean/{ennxo,mac2hand}_cleaned.jsonl` | ทุกแถวหลังใช้กฎ ค่า clean เหตุผล hold/excluded และหลักฐาน |
| `clean/{accepted,needs_review,excluded}.csv` | แยกสถานะเพื่อใช้งานและตรวจ แถวพักไม่ถูกทิ้ง |
| `clean/{rules,corrections,model_catalog}.json` ที่มี | สำเนากฎ ledger และรายการรุ่นอ้างอิงของรอบ |
| `review/` | บัญชีคิวก่อน–หลังและตัวอย่างตรวจ เช่น `review_rows.csv`, `spot_check.json` |
| `manual_review/` ENNXO | `reviewed.csv` ผลคิวครบ126; `review_evidence.json` หลักฐาน; `confirmed_damage_or_lock.csv` 49เครื่องเสีย/ล็อก; `awaiting_evidence.csv` 35รอหลักฐาน; `accepted_from_queue.csv`, `excluded_from_queue.csv` ผลกลุ่มอื่น |
| `manual_review/` Mac2Hand | `mac2hand_reviewed.jsonl` ผลหลังคำแก้; `queue_plan.csv`, `queue_evidence.json` แผน/หลักฐาน; `manual_reviews.json` สำเนา ledger |
| `history/rules_v1` ถึง `rules_v5` ENNXO | ผลเก่า กฎและ metadata สำหรับเทียบย้อนหลัง |
| `summary.json`, `report.md` ของแต่ละขั้น | จำนวนและสรุปให้คนอ่าน |
| `validation.json`, `run_metadata.json` ของแต่ละขั้น | ผลตรวจ ข้อมูลเข้า เวอร์ชันโค้ดและ hash สำหรับทำซ้ำ |

ดู [clean ENNXO](../ennxo/cleaning.md), [review ENNXO](../ennxo/review.md), [clean Mac2Hand](../mac2hand/cleaning.md) และ [review Mac2Hand](../mac2hand/review.md)

## Intermediate: ผลตัดสิน Mac2Hand ทั้งชุด

`data/intermediate/mac2hand/<รอบ>/finalization/`:

| ไฟล์ | เก็บอะไร |
|---|---|
| `mac2hand_final.jsonl` | ทั้ง10,220แถว ค่า clean ต้นฉบับ resolution สถานะและงานถัดไป |
| `queue_decisions.csv`, `queue_decisions.json` | คิวเดิม1,789แถวพร้อมผล เหตุผล งานถัดไปและหลักฐานละเอียด |
| `non_normal.csv` | 144เครื่องเสีย/ล็อก/เงื่อนไขที่ศึกษาแยก |
| `ambiguous.csv` | 513แถวที่ค่าขัดกัน หลายเครื่อง หรือราคาต่อเครื่องไม่ชัด |
| `insufficient_data.csv` | 605แถวที่ข้อมูลรุ่น/ความจุ/รายละเอียดไม่พอ |
| `missing_source.csv` | 81แถวที่ขาดหน้ารายละเอียด |
| `excluded.csv` | 124ประกาศสินค้า/บริการนอกขอบเขต |
| `candidate_duplicate_groups.json` | 185กลุ่ม394แถวที่อาจลงซ้ำ ยังไม่ยืนยันเครื่องเดียวกัน |

อ่าน [ขั้นส่งมอบ Mac2Hand](../mac2hand/finalization.md) สำหรับเกณฑ์และตัวอย่าง

## Intermediate: หลักฐานชุดรวมและคิว EDA

`data/intermediate/combined/<รอบ>/` เก็บ `lineage.jsonl` mapping ทุกแถวไป CSV ต้นทางพร้อมค่าเดิมทุกคอลัมน์, `{ennxo,mac2hand}_audit.json` ผลตรวจรายเว็บ, `normalization_changes.json` ค่าก่อน/หลังแปลง และ `price_review.csv` ราคาสูงสุด5รายการต่อเว็บพร้อม URL/งานถัดไป

`data/intermediate/eda/<รอบ>/` เก็บ `outlier_candidates.csv` 205แถวและ peer/fence, `price_extremes.csv` ราคาสูงสุดจากขั้นรวม, `duplicate_groups.json` กลุ่ม candidate, `duplicate_memberships.csv` สมาชิกแต่ละกลุ่ม, `text_candidate_components.json` กลุ่มข้อความหลังรวมการซ้อนกัน280กลุ่ม617แถว และ `validation.json` ผลตรวจ ไม่มีการลบแถวเหล่านี้จาก final

## Final: ชุดผ่านสำหรับส่งต่อ

| โฟลเดอร์ | เก็บอะไร |
|---|---|
| `data/final/ennxo/<รอบ>/` | `dataset.csv` 1,279แถว คัดลอก accepted.csv ทุก byte; `summary.json`, `report.md`, `validation.json`, `run_metadata.json` เก็บจำนวน ผลตรวจและ hash |
| `data/final/mac2hand/<รอบ>/` | `dataset.csv` 8,753แถว; summary/report/validation/metadata; `rules.json`, `iphone_model_names.json` สำเนากฎ/catalogue |
| `data/intermediate/combined/<รอบ>/before_selection/` | `dataset.csv`, `dataset.jsonl` 10,032แถว schemaกลาง13คอลัมน์ พร้อม source; `schema.json` สำเนา schema; summary/report/validation/metadata |

CSV เฉพาะเว็บมีฟิลด์ประกอบต่างกัน ชุด combined ปรับมาตรฐานแล้ว อ่าน [schema](data_schema.md) และ [วิธีรวม](combined_dataset.md) `final` ยังไม่ได้แบ่ง train/test และยังไม่ยืนยัน candidate ซ้ำ

## Reports และงานย้อนหลัง

`reports/eda/<รอบ>/` มี `summary.md` อ่านสั้น, `report.md` และ `report.html` รายละเอียดพร้อมกราฟ, `figures/` PNG/SVG8ชุด, `tables/` สถิติรวม12CSV และ JSON กฎ/ผลตรวจ/hash รายละเอียดใน [คู่มือ EDA](eda.md) รายงานรวมเก็บใน Git; ข้อมูลรายประกาศเก็บใน data ที่ถูก ignore

`archive/` คือการทดลองและงานเก่าที่ไม่ใช่ผลปัจจุบัน ไม่ย้ายกลับมาใช้แทน final metadata เก่าคง path เดิม ให้ตาม [บัญชีย้ายรอบล่าสุด](migrations/stage_reorganization_20261011.json) และบัญชีรอบก่อนในโฟลเดอร์เดียวกันเพื่อหาตำแหน่งปัจจุบัน สำรอง raw/intermediate/ผลผ่านเฉพาะเว็บและ ledger จริงแยกจาก Git ชุดหลัก data/final/dataset.csv และไฟล์กำกับรวมในGit

ชุดใช้ต่อสำหรับโมเดล9,210แถวอยู่ data/final/ หลักฐานคัดและexcluded_rows/selection_decisions/lineage อยู่ data/intermediate/model_input/<รอบ>/ อ่าน [หน้าที่ทุกไฟล์](model_input.md)
