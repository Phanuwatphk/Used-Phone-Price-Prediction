# คัดชุดข้อมูลก่อนเทรน

ผู้ใช้เลือกตัดคิว EDA ทั้งหมดและหยุดตรวจต่อ เมื่อ 2026-10-11 สร้างชุด 9,210 แถวจากชุดรวม 10,032 แถว ไม่เปลี่ยน source dataset หรือผล EDA เดิม ราคาคือราคาตั้งขาย สภาพคือช่องที่ผู้ขายระบุ

## วิธีทำซ้ำ

```bash
.venv/bin/python -B script/preparation/shared/select_model_input.py
```

ใช้กับทั้ง ENNXO และ Mac2Hand ค่าเริ่มต้นอิงตำแหน่งไฟล์ รันจาก directory อื่นด้วย absolute path หรือ `python -m script.preparation.shared.select_model_input` จากรากโปรเจคได้ ทดลองโดยระบุ `--output` และ `--audit-output` ไปปลายทางใหม่ ใช้ `--policy` เลือกกฎที่ version และ hash ตรงข้อมูลนั้น

| ข้อมูลเข้า | หน้าที่ |
|---|---|
| `data/intermediate/combined/<รอบ>/before_selection/dataset.csv`, `dataset.jsonl`, `schema.json` | ชุดรวมและ schema ก่อนคัด ตรวจ CSV/JSONL ตรงกันและรหัสไม่ซ้ำ |
| `data/intermediate/combined/<รอบ>/audit/lineage.jsonl` | ที่มาทุกแถว ต้องมีครบตรง listing_id |
| `data/intermediate/eda/<รอบ>/outlier_candidates.csv` | รหัสที่ flag ราคา IQR205 แถว |
| `.../text_candidate_components.json` | สมาชิก 280 กลุ่มข้อความอาจซ้ำ รวม 617 แถว |
| `.../price_extremes.csv` | ราคาสูงสุด 5 รายการต่อเว็บ รวม 10 แถว |
| `config/shared/model_input_policy.json` | นโยบายที่ผู้ใช้เลือก expected counts และ hash ของข้อมูลเข้าทุกไฟล์ |

สร้าง set ของ listing_id จากทั้ง 3 คิว แล้วตัด union822 รหัส มี 10memberships ที่ซ้อนคิว จึงไม่บวก 205+617+10 เป็นจำนวนแถวที่ตัด ราคา extremes มี 6 แถวเพิ่มจาก union ของ IQR กับข้อความ ตัดสมาชิกทุกแถวของกลุ่มข้อความ ไม่เลือกตัวแทน ไม่ยืนยันว่าเครื่องเดียวกันหรือราคาผิดจริง คงลำดับและค่าของแถวที่เก็บทั้ง 9,210 แถว

## ผลลัพธ์และแต่ละไฟล์

ปลายทาง final: `data/final/`

| ไฟล์ | เก็บอะไร |
|---|---|
| `dataset.csv` | 9,210 แถวพร้อม source ENNXO1,202 / Mac2Hand8,008 |
| `dataset.jsonl` | ชุดเดียวกัน พร้อมชนิดข้อมูล JSON เดิม |
| `schema.json` | schema กลาง 13 คอลัมน์เดิม |
| `policy.json` | สำเนานโยบายและ hash ที่ใช้คัดรอบนี้ |
| `summary.json`, `report.md` | จำนวนก่อน/หลัง สัดส่วนเว็บ ปี ยี่ห้อ ช่วงวันและราคา |
| `validation.json` | ผลตรวจ input คงเดิม ไม่มีสมาชิกคิวหลุดเข้าชุดใหม่ และบัญชีแถวครบ |
| `run_metadata.json` | เวลา code/policy/input hashes และ hashdataset |

ปลายทาง intermediate: `data/intermediate/model_input/ennxo_20261005_mac2hand_20261006_eda_queue_excluded_v1/`

| ไฟล์ | เก็บอะไร |
|---|---|
| `excluded_rows.csv` | 822 แถวที่ตัด พร้อม selection_reasons; เก็บเป็นประวัติ ไม่ใช่คิวงานต่อ |
| `selection_decisions.csv` | ผล selected และเหตุผลของทุก 10,032 รหัส บอกหลายเหตุผลในแถวเดียวได้ |
| `lineage.jsonl` | ที่มาต้นฉบับของ 9,210 แถวที่ใช้ต่อ |

## การใช้และขอบเขต

raw, final เฉพาะเว็บ, ชุดรวม 10,032 แถวและรายงาน EDA เดิมคงไว้เป็นประวัติ นโยบายคิวใหม่ override คำแนะนำงานถัดไปในรายงานเก่าโดยไม่เขียนแก้หลักฐานเก่า registry แยก `merged_dataset` กับ `model_input_dataset` ชัดเจน งานเทรนให้ใช้ model_input_dataset

ชุดใหม่เป็นผลเลือกก่อน split ยังไม่มี train/validation/test หรือโมเดล การคัดราคาใช้ EDA ทั้ง snapshot ตามนโยบายผู้ใช้ ไม่ใช่ outlierthreshold ที่เรียนรู้จาก train คะแนนที่จะรายงานจึงประเมินประชากรหลังคัดตามนโยบายนี้ ไม่ใช่ประกาศทุกชนิด ฟิต preprocessing จาก train และเก็บ split/seed/feature list ให้ทำซ้ำได้ หลีกเลี่ยงใช้รหัสหรือ URL เป็น feature โดยตรง
