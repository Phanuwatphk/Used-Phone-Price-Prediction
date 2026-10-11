# งานย้อนหลัง

ไฟล์ในโฟลเดอร์นี้เก็บเพื่ออ้างอิง ไม่ใช่ entry point ของ pipeline ปัจจุบัน เริ่มใช้งานจาก [README โครงการ](../README.md)

| โฟลเดอร์ | เนื้อหา |
|---|---|
| `experiments/ennxo/` | สคริปต์ทดลอง parser/รายละเอียด ENNXO เดิม บางไฟล์อ้างโมดูลที่ไม่ได้เก็บเป็นโค้ดใช้งานแล้ว |
| `legacy_kaggle/` | dataset และสคริปต์ Kaggle เดิม ไม่ใช่ข้อมูลจากสองเว็บที่ใช้อยู่ |
| `planning/` | ร่าง schema เดิมและบัญชีย้ายไฟล์; ไม่ถือเป็น schema กลางที่นำมาใช้แล้ว |
| `mac2hand/<รอบ>/` | `legacy_preparation/` เก็บผลเตรียมเดิม และ `before_quality_review/` เก็บสำเนาก่อนตรวจคุณภาพ |

ไม่รันสคริปต์ทดลองเก่าเป็นขั้นตอนหลัก ข้อมูลย้อนหลังเก็บครบ ผล Mac2Hand เก่ารวมตามเว็บและรอบ อ่าน [บัญชีย้ายพร้อม checksum](../docs/details/shared/migrations/structure_reorganization_20261011.json)
