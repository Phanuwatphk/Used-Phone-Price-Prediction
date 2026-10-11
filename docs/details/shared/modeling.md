# วิธีใช้โมเดลล่าสุดและอ่านผล

รอบปัจจุบันคือ **asking_price_v2** อ่าน [สรุปผล](../../summary/modeling.md) และ [รายงานรายละเอียดรอบ 2](../../../reports/modeling/asking_price_v2/report.md) สำหรับวิธีเลือก ผลทุกตัวเลือก/ทุกกลุ่ม และขอบเขตคะแนน

## ลำดับงานและสคริปต์

| สคริปต์ใน script/modeling/ | อ่าน / ทำอะไร | เขียนผล |
|---|---|---|
| `prepare_features_v2.py` | core CSV + lineage ENNXO + full-text Mac2Hand → ถอด battery health/ประกันวัน/กล่อง โดยยืนยัน identity/price ตรงกัน | `data/intermediate/modeling/asking_price_v2/enrichment/{dataset.csv,audit.json}` |
| `features_v2.py` | core + optional claims + ปีเปิดตัวจาก catalog → อายุรุ่น/tier/missing indicators | โมดูลประกอบ ไม่รันแยก ไม่ใช้ target |
| `rebuild_features_v2.py` | core CSV + public condition sidecar → enriched CSV byte ตรง hash โดยไม่ต้องมี raw | enriched CSV ในเครื่อง |
| `train_improved.py` | 2 temporal folds → เทียบ 12 ตัว เลือก MAE ต่ำสุด → เปรียบเทียบย้อนหลัง → fit ใช้งานครบชุด | reports/modeling/asking_price_v2/, models/asking_price_v2/ และผลรายแถวใน intermediate |
| `predict.py` | โหลด V1/V2 ตรวจ hash ทำนายพร้อม coverage | JSON หน้าจอ หรือ --output |
| `report_improved.py` | ผลรวม/แยกเว็บ ทุกตัวเลือกและกราฟ | summary/report/HTML/figures/tables |

## โมเดลสองบทบาท

- `evaluation.joblib`: ฟิต 8,517 แถวก่อน 2025-01-09 ใช้เปรียบเทียบย้อนหลังบน test เดิม 693 แถว คะแนนอธิบายตัวนี้
- `model.joblib`: ใช้งานล่าสุด ฟิตครบ 9,210 แถวหลังเลือกวิธี ครอบคลุม 300 รุ่นรวมรุ่นล่าสุด และมี metadata ระบุ **ไม่มี independent test score** ไม่ยกคะแนน evaluation มาอ้างเป็นคะแนนอิสระของตัวนี้

ข้อมูลทุกวันที่ยังคงอยู่ น้ำหนัก half-life 2 ปีคำนวณจากวันล่าสุดใน fold train เท่านั้น ไม่ทิ้งข้อมูลเก่า Encoding/imputation/scaling ฟิตจาก fold train เท่านั้น คำระบุไม่ชัดใน dataset เก็บ missing; imputation เป็นส่วนของ estimator ไม่เขียนค่าเดาลง dataset

Catalog ปีเปิดตัวเป็นข้อเท็จจริงจาก Apple ใช้เฉพาะรุ่นที่ระบุใน reference ไม่เดาปี Android และไม่ถือว่าเป็นอายุของเครื่องจริง ค่าแบต/ประกัน/กล่องคือคำกล่าวในประกาศที่ถอดด้วยกฎ ไม่ใช่ผลตรวจเครื่องโดยตรง

## รันหลัง clone

```bash
# ถ้ายังไม่มี enriched CSV จะสร้างจาก core + sidecar ให้อัตโนมัติ
.venv/bin/python -u -B script/modeling/train_improved.py
# เมื่อหยุดระหว่างเปรียบเทียบ ใช้ผลตัวเลือกที่ทำครบแล้วต่อได้ ถ้า config/hash ตรงเดิม
.venv/bin/python -u -B script/modeling/train_improved.py --resume
# DEFAULT ใช้ operational V2; optional features ให้มาเมื่อทราบ
.venv/bin/python -B script/modeling/predict.py \
  --source mac2hand --brand Apple --model 'iPhone 16 Pro' \
  --storage-gb 256 --condition used --published-at 2026-10-06 \
  --battery-health-pct 90
```

Batch ใช้ `--input-csv` (หกฟิลด์ core และ optional ได้), `--output` เขียน JSON; ลำดับผลตรง input รองรับ absolute path จาก directory อื่นและ `python -m script.modeling.train_improved` จากรากโปรเจค

การถอดคำระบุจากต้นทางใหม่ใช้ `prepare_features_v2.py` และต้องมี private lineage/full-text evidence ของรอบเดิม หลัง clone ไม่ต้องมี raw เพราะรวม `data/final/condition_features.csv` ซึ่งมีเพียง listing_id และตัวเลข/ค่าขาดของสาม feature; code/catalog/core/sidecar/config ครบสำหรับ rebuild/เทรนใหม่ Hash ตรึงทั้งหมดไว้ใน config

## ผลลัพธ์แต่ละไฟล์

| ตำแหน่ง | เก็บอะไร |
|---|---|
| `data/final/dataset.csv` | ชุดหลัก schema เดิม 13 คอลัมน์ 9,210 แถว ไม่เปลี่ยน |
| `data/final/condition_features.csv` | sidecar 9,210 รหัส: battery_health_pct, warranty_days, box_mentioned; ช่องว่างคือไม่ทราบ |
| `config/modeling/iphone_release_years.json` | ปีเปิดตัว 54 รุ่นจาก Apple พร้อม source URL/hash |
| `config/modeling/improved.json` | 12 ตัวเลือก 2 fold cutoff weights seed input/catalog/sidecar hashes |
| `data/intermediate/modeling/asking_price_v2/enrichment/` | enriched CSV/audit input provenance และ coverage |
| `.../evaluation/retrospective_predictions.csv` | ผลจริง/ทำนาย/error รายแถว เก็บในเครื่อง |
| `models/asking_price_v2/` | operational/evaluation artifacts และ metadata แยกบทบาท/hash/versions |
| `reports/modeling/asking_price_v2/summary.md` | ผลสั้นรวม/แยกเว็บ และความหมายของคะแนน |
| `.../report.md`, `report.html` | รายละเอียด วิธีทำ ข้อจำกัด กราฟและคำสั่ง |
| `.../tables/` | validation_comparison, fold_metrics, retrospective_metrics และ retrospective_by_group CSV |
| `.../figures/` | validation MAE และ actual/predicted ใน PNG/SVG |
| `.../config.json`, `folds.json`, `selection.json` | config ที่ใช้ ขนาด/วันที่ fold และหลักฐานเลือกก่อนวัดย้อนหลัง |
| `.../summary.json`, `validation.json`, `run_metadata.json`, `output_hashes.json` | ตัวเลข ผลตรวจ versions/input/code/model/output hashes |
| `.../progress.json` | สถานะในเครื่อง ไม่ขึ้น Git |

ข้อมูลหลักและ condition sidecar รวม Git; HTML/ข้อความต้นทาง ผลทำนายรายแถว และ binary เก็บในเครื่อง รายงาน/config/กราฟ/ตารางรวมขึ้น Git ได้

## ขอบเขตและการตรวจ

Tests ปัจจุบัน 140 ข้อรวมกฎถอดคำระบุ, missing/unknown features, อายุจาก catalog ไม่ใช้ target, น้ำหนักอิง train, ปัญหา CatBoost clone, split/encoder isolation และ artifact roundtrip คะแนน V2 ดีขึ้นใน validation และผลย้อนหลัง แต่ไม่มี holdout ใหม่ที่ไม่เคยใช้พัฒนา ควรประเมินประกาศหลัง 2026-10-06 ที่ยังไม่เคยใช้พัฒนาเพื่อรับรองความแม่นยำในงานจริง

วิธีรอบแรกและผลเดิมเก็บเป็นประวัติที่ [รายงาน V1](../../../reports/modeling/asking_price_v1/report.md); core snapshot metadata คงข้อเท็จจริงตอนคัดข้อมูล ไม่เขียนย้อนหลังทับประวัติ
