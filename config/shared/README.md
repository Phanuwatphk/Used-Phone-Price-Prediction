# Shared dataset config

`dataset_schema.json` ใช้กับ **ENNXO และ Mac2Hand** ระบุคอลัมน์ ชนิด หน่วย timezone นโยบายรวม และ alias ชื่อรุ่นสำหรับ `preparation/shared/prepare_combined_dataset.py` ไม่เปลี่ยนค่า raw หรือคำตัดสินของ source cleaner

รุ่นที่ไม่มี alias คงไว้ ไม่เติมความจุ/ราคา และไม่ fuzzy match รุ่นย่อย ดู [วิธีตรวจและรวม](../../docs/details/shared/combined_dataset.md)

`eda_rules.json` ใช้กับ `analysis/eda/run_eda.py` ระบุกลุ่ม/จำนวนขั้นต่ำ IQR, การเทียบเว็บ และเงื่อนไข candidate ข้อความซ้ำ ใช้สำรวจเท่านั้น ไม่แก้ dataset ดู [คู่มือ EDA](../../docs/details/shared/eda.md)

`model_input_policy.json` บันทึกนโยบายผู้ใช้ให้ตัดคิวEDAทุกสมาชิก expected counts และinput hashes ใช้กับ preparation/shared/select_model_input.py ทั้งสองเว็บ ดู [วิธีคัด](../../docs/details/shared/model_input.md)
