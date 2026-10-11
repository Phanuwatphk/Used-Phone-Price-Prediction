# วิเคราะห์ข้อมูล

โค้ดวิเคราะห์แยกจากการเก็บและเตรียมข้อมูล ปัจจุบันมีขั้น EDA ใน `eda/` ขั้นฝึกโมเดลแยกไว้ใน [../modeling/](../modeling/README.md)

| ไฟล์ | ใช้กับ / หน้าที่ |
|---|---|
| `eda/run_eda.py` | ชุดรวมทั้งสองเว็บ ตรวจ CSV/JSONL/lineage แล้วสร้างรายงานและคิวตรวจ |
| `eda/eda_statistics.py` | สถิติ IQR รายกลุ่ม candidate ซ้ำ Spearman และ sensitivity; ไม่รันแยก |
| `eda/eda_plots.py` | สร้างกราฟ PNG/SVG แบบ offline; ไม่รันแยก |

```bash
.venv/bin/python -B script/analysis/eda/run_eda.py
```

อ่าน dataset จาก `data/intermediate/combined/<รอบ>/before_selection/`, lineage/audit จาก `data/intermediate/combined/<รอบ>/audit/` และข้อความเต็มจาก `data/intermediate/mac2hand/<รอบ>/finalization/mac2hand_final.jsonl` ตรวจข้อความให้ตรงค่าต้นทางก่อนใช้ กฎอยู่ที่ `config/shared/eda_rules.json`

ผลอ่านภาพรวมอยู่ใน `reports/eda/<รอบ>/`: summary/report, HTML, `figures/` และ `tables/` คิวรายแถวและ URL อยู่ใน `data/intermediate/eda/<รอบ>/` สคริปต์ไม่แก้ dataset

รองรับรันจาก directory อื่นด้วย absolute path และ `python -m script.analysis.eda.run_eda` จากรากโปรเจค ปรับ `--input`, `--evidence`, `--mac2hand-details`, `--report`, `--private-output` เพื่อเลือกข้อมูลเข้าและผลทดลอง `--without-mac2hand-details` ใช้ข้อความจาก CSV เท่านั้นและระบุความครอบคลุมที่ลดลง ใช้ Python 3.12+ ตาม lock อ่าน [หลักเกณฑ์และทุกไฟล์ EDA](../../docs/details/shared/eda.md)

เมื่อใช้ปลายทางทดลองแบบเดิมและไม่ส่ง option ปลายทางเสริม CLI ยังรองรับ bundle ใน output/input เดียว ค่าเริ่มต้นของ snapshot ปัจจุบันแยกขั้นตาม registry
