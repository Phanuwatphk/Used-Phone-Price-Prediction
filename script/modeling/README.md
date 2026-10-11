# โมเดลล่าสุด: รอบ 2

ใช้ `train_improved.py` สำหรับรอบปัจจุบัน อ่าน [วิธีและทุกไฟล์](../../docs/details/shared/modeling.md) และ [ผลล่าสุด](../../docs/summary/modeling.md)

```bash
.venv/bin/python -u -B script/modeling/train_improved.py
.venv/bin/python -u -B script/modeling/train_improved.py --resume
.venv/bin/python -B script/modeling/predict.py --source mac2hand --brand Apple --model 'iPhone 16 Pro' --storage-gb 256 --condition used --published-at 2026-10-06 --battery-health-pct 90
```

`prepare_features_v2.py` ถอด claims จาก evidence เดิม, `features_v2.py` สร้างอายุรุ่น/optional features, `rebuild_features_v2.py` สร้าง enriched CSV จาก public core+sidecar โดยไม่ต้องมี raw ส่วนตัว, `train_improved.py` เลือกด้วย 2 forward validation folds และส่งมอบ evaluation/operational artifact แยกกัน, `report_improved.py` สร้างรายงาน V2 ค่าเริ่มต้นของ predict ใช้ operational V2 และยังโหลด V1 ด้วย --model-file ได้

## รอบแรก (เก็บทำซ้ำ/เปรียบเทียบ)

# แบ่งข้อมูลและเทรนราคาประกาศ

ใช้กับ **ENNXO และ Mac2Hand รวมกัน** อ่านเฉพาะชุด 9,210 แถวที่ส่งมอบแล้ว ไม่มี request ไปเว็บ และไม่แก้ raw/final

| ไฟล์ | หน้าที่ | อ่าน / เขียน |
|---|---|---|
| `split_dataset.py` | ตรึง hash ตรวจ input แบ่งวันตามเวลา | `data/final/dataset.csv` → `data/intermediate/modeling/<รอบ>/split/` |
| `features.py` | สร้าง feature จาก source, brand, model, storage, condition, วันที่ | โมดูลประกอบ ไม่รันแยก |
| `train_models.py` | เทียบ 15 ตัวเลือกบน validation เลือก/refit train+validation แล้ววัด test | split, `models/<รอบ>/`, `reports/modeling/<รอบ>/` และผลทำนายรายแถวใน intermediate |
| `predict.py` | โหลดโมเดล ตรวจ hash ทำนายบาทพร้อมข้อมูล coverage | JSON หน้าจอ หรือ `--output` |
| `report.py` | สรุป/รายละเอียด HTML กราฟ และตารางรวม | `reports/modeling/<รอบ>/` |

จากรากโปรเจค:

```bash
# ดู split อย่างเดียว; train จะสร้าง split เดียวกันให้อยู่แล้ว
.venv/bin/python -B script/modeling/split_dataset.py
# เทรนทั้งหมดและสร้างรายงาน (เขียนผลรอบเดิมใหม่)
.venv/bin/python -u -B script/modeling/train_models.py
# ทำนายหนึ่งประกาศ
.venv/bin/python -B script/modeling/predict.py \
  --source mac2hand --brand Apple --model 'iPhone 13' \
  --storage-gb 128 --condition used --published-at 2026-10-06
```

Config อยู่ [config/modeling/training.json](../../config/modeling/training.json) บันทึก dataset hash, 85%/7.5%/7.5%, seed และตัวเลือกพารามิเตอร์ แบ่งเป็นวันทั้งวันเพื่อไม่ให้วันเดียวกันอยู่คนละชุด เลือกจาก validation MAE หน่วยบาท; test ไม่ใช้ฟิตโมเดล/encoding หรือเลือกพารามิเตอร์

ใช้ `--config` เลือกรอบใหม่ และ `--report-output`, `--model-output`, `--private-output` แยกปลายทางทดลอง รุ่น/ยี่ห้อที่ไม่เคยเห็นและวันที่นอกช่วงฝึกแสดงเป็น coverage flags ราคาทำนายเป็นราคาตั้งขาย ไม่ใช่ราคาปิดการขาย

รองรับ `python -m script.modeling.train_models` จากรากโปรเจค และรันไฟล์ผ่าน absolute path จาก directory อื่น โมเดล binary/split/prediction อยู่ในเครื่องตาม .gitignore; หลัง clone ใช้คำสั่ง train เพื่อสร้างใหม่ อ่าน [ผลสรุป](../../docs/summary/modeling.md) และ [คู่มือไฟล์/วิธีทดลอง](../../docs/details/shared/modeling.md)
