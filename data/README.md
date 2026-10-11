# ข้อมูลสำหรับใช้งาน

**ใช้ [final/dataset.csv](final/dataset.csv) — 9,210 แถว** เป็นชุดหลักของโมเดลรอบแรก ENNXO 1,202 และ Mac2Hand 8,008 แถว ทุกแถวมี source และ schema กลาง 13 คอลัมน์ ชุดนี้รวมใน GitHub แล้ว แบ่งตามเวลาและเทรนแล้ว ชุดนี้เป็นต้นฉบับก่อน split จึงยังมีครบ 9,210 แถว

[datasets.json](datasets.json) ระบุ `default_dataset: model_input_dataset` พร้อม path และจำนวน ชุดก่อนตัดคิว 10,032 แถวอยู่ใน `intermediate/combined/ennxo_20261005_mac2hand_20261006/before_selection/` เก็บในเครื่องเป็นประวัติ

| ไฟล์ที่รวมใน GitHub | เก็บอะไร |
|---|---|
| `final/dataset.csv` | ชุดใช้ต่อ 9,210 แถว |
| `final/dataset.jsonl` | ชุดเดียวกัน พร้อมชนิดข้อมูล JSON |
| `final/schema.json` | คอลัมน์ หน่วย และชนิดข้อมูล |
| `final/policy.json` | นโยบายตัดคิวและ hash ต้นทาง |
| `final/summary.json`, `final/report.md` | จำนวนก่อน/หลังและสรุปชุดที่เลือก |
| `final/validation.json` | ผลตรวจจำนวน ค่า และ schema |
| `final/run_metadata.json` | เวลา code/input hashes และ hashdataset |

| ข้อมูลที่เก็บในเครื่อง | เก็บอะไร |
|---|---|
| `raw/<เว็บ_เวลารอบ>/` | HTML บัญชีประกาศ manifest checkpoint และ log ต้นฉบับ |
| `intermediate/<เว็บ>/<รอบ>/` | audit extraction clean review และหลักฐานทุกสถานะ |
| `intermediate/combined/<รอบ>/` | lineage ผลตรวจรายเว็บ และชุดรวมก่อนคัด |
| `intermediate/eda/<รอบ>/` | คิวราคา/ข้อความอาจซ้ำจาก EDA |
| `intermediate/model_input/<รอบ>/` | 822 แถวที่ตัดพร้อมเหตุผล ผลตัดสินทุกแถวและ lineage9,210 แถว |
| `final/{ennxo,mac2hand}/<รอบ>/` | ผลผ่านเฉพาะเว็บก่อนคัด EDA สำรองแยก |

raw และข้อมูลระหว่างทางเก็บเป็นประวัติ ไม่ใช่ชุดสำหรับเทรน metadata เก่าคง path ที่ใช้ตอนสร้างไว้ รายงาน EDA เดิมใน reports สำรวจ 10,032 แถวก่อนคัด อ่าน [สรุปชุดปัจจุบัน](../docs/summary/model_input.md), [หน้าที่ทุกไฟล์](../docs/details/shared/model_input.md) และ [ไฟล์สำหรับ GitHub](../docs/details/shared/github.md)

ขั้นโมเดล: `intermediate/modeling/asking_price_v1/split/` เก็บ train/validation/test CSV และ assignments พร้อม hashes; `*predictions.csv` เก็บผลรายแถว โมเดลอยู่ `models/asking_price_v1/` รายงานอยู่ [สรุปโมเดล](../docs/summary/modeling.md)

`final/condition_features.csv` เป็น sidecar 9,210 แถว มี listing_id และคำระบุเชิงตัวเลข battery_health_pct/warranty_days/box_mentioned ไม่มีข้อความหรือข้อมูลติดต่อ รวม Git สำหรับ rebuild V2; dataset หลักยังมี schema 13 คอลัมน์เดิม โมเดลล่าสุดอยู่ `models/asking_price_v2/` ฝึกครบชุด ส่วน evaluation artifact แยกไว้ อ่าน [วิธี V2](../docs/details/shared/modeling.md)
