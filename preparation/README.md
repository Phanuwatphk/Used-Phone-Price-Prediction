# เตรียมข้อมูลก่อนวิเคราะห์

อ่านข้อมูลในเครื่อง ไม่ส่ง request ไปเว็บ ลำดับงานคือ raw → audit/extraction → clean/review → final → รวม schema กลาง แยก ENNXO, Mac2Hand และงานที่ใช้ทั้งคู่ชัดเจน

| สคริปต์ | ใช้กับ | อ่านอะไร / ทำอะไร | เขียนไว้ที่ไหน |
|---|---|---|---|
| `ennxo/audit_ennxo_raw.py` | ENNXO | raw → ตรวจจำนวน URL ฟิลด์ ค่าขาด และ HTML | `data/intermediate/ennxo/<รอบ>/raw_audit/` |
| `ennxo/extract_ennxo_raw.py` | ENNXO | raw → ถอดค่าจาก HTML เก็บต้นฉบับและที่มา | `.../extraction/` |
| `ennxo/clean_ennxo.py` | ENNXO | extraction + กฎ + corrections → normalize และแยกสถานะ | `.../clean/` |
| `ennxo/review_ennxo_queue.py` | ENNXO | clean + baseline → เทียบคิวก่อน/หลัง | `.../review/` |
| `ennxo/finalize_ennxo_manual_review.py` | ENNXO | clean + ledger + baseline → ตรวจคำตัดสินครบคิวและแยกผล | `.../manual_review/` |
| `ennxo/export_ennxo_dataset.py` | ENNXO | clean → ตรวจ accepted.csv เทียบ JSONL แล้วคัดลอก CSV ทุก byte | `data/final/ennxo/<รอบ>/` |
| `mac2hand/prepare_mac2hand.py` | Mac2Hand | raw → ตรวจ manifest/hash และ parse HTML | `data/intermediate/mac2hand/<รอบ>/{raw_audit,extraction}/` |
| `mac2hand/clean_mac2hand.py` | Mac2Hand | extraction + กฎ → ตรวจและแยกสถานะ | `.../clean/` |
| `mac2hand/review_mac2hand_queue.py` | Mac2Hand | clean + ledger → ตรวจคำแก้และจัดคิว | `.../manual_review/` |
| `mac2hand/finalize_mac2hand.py` | Mac2Hand | ผล review + กฎ → ส่งมอบกลุ่มผ่านและแยกปัญหาทุกแถว | `data/final/mac2hand/<รอบ>/` และ `data/intermediate/mac2hand/<รอบ>/finalization/` |
| `shared/select_model_input.py` | ทั้งสองเว็บ | ชุดรวม + คิวEDA + นโยบาย → ตัดunion822รหัส | `data/final/` และ `data/intermediate/model_input/<รอบ>/` |
| `shared/prepare_combined_dataset.py` | ทั้งสองเว็บ | อ่าน CSV ผ่านจาก registry → ตรวจรายเว็บ ปรับ schema รวม พร้อม source | `data/intermediate/combined/<รอบ>/before_selection/` และ `data/intermediate/combined/<รอบ>/audit/` |

โมดูลประกอบ: ENNXO `cleaning_rules.py` เก็บกฎตรวจฟิลด์, `description_sections.py` แยกส่วนรายละเอียด; Mac2Hand `resolution_rules.py` เก็บกฎตรวจหลักฐานขั้นส่งมอบ โมดูลเหล่านี้ไม่รันแยก

คำสั่งช่วงส่งมอบและรวมจากรากโปรเจค:

```bash
.venv/bin/python -B preparation/ennxo/export_ennxo_dataset.py
.venv/bin/python -B preparation/mac2hand/finalize_mac2hand.py
.venv/bin/python -B preparation/shared/prepare_combined_dataset.py
```

การทำซ้ำ snapshot เดิมต้องมีข้อมูลและ ledger ตรงรอบ คำสั่งสร้างผลใหม่ในปลายทางที่กำหนด ไม่จำเป็นต้องรันขั้นก่อนหน้าซ้ำเพื่ออ่าน dataset ที่เสร็จแล้ว `--output` เลือกปลายทาง final; Mac2Hand ใช้ `--review-output` แยกหลักฐาน, ตัวรวมใช้ `--audit-output` แยก lineage/audit เมื่อลองรันให้กำหนดปลายทางทั้งสองเพื่อไม่ทับผลปัจจุบัน API เดิมที่ไม่ส่งปลายทางเสริมยังสร้าง bundle ใน output เดียวได้

รองรับรันไฟล์ผ่าน absolute path จาก directory อื่น และ `python -m preparation.<เว็บหรือshared>.<โมดูล>` จากรากโปรเจค ดู [ENNXO](../docs/details/ennxo/methodology.md), [Mac2Hand](../docs/details/mac2hand/cleaning.md), [ชุดรวม](../docs/details/shared/combined_dataset.md) และ [คู่มือไฟล์](../docs/details/shared/data_guide.md)

เมื่อใช้ปลายทางทดลองแบบเดิมและไม่ส่ง option ปลายทางเสริม CLI ยังรองรับ bundle ใน output/input เดียว ค่าเริ่มต้นของ snapshot ปัจจุบันแยกขั้นตาม registry

ขั้นคัดชุดโมเดล: `.venv/bin/python -B preparation/shared/select_model_input.py` อ่าน [วิธีทำและทุกไฟล์](../docs/details/shared/model_input.md) ผล9,210แถว ยังไม่แบ่งหรือเทรน
