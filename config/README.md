# Configuration

กฎเก็บ/clean แยกตามเว็บไซต์ ส่วน `shared/dataset_schema.json` ใช้ปรับ schema และรวมทั้งสองเว็บ ดู [คู่มือ shared](shared/README.md)

| ไฟล์ ENNXO | หน้าที่ |
|---|---|
| `ennxo/cleaning_rules.json` | กฎเวอร์ชัน 6, ยี่ห้อ ความจุ และ reference ชื่อรุ่น |
| `ennxo/corrections.json` | คำแก้/การแยกออกที่ cleaner นำไปใช้ ผูกกับ URL และ input hash |
| `ennxo/manual_review.json` | บันทึกตรวจคิว 126 รายการ และขอบเขตโมเดลที่ผู้ใช้เลือก |

แก้ข้อมูลผ่าน correction ledger แล้วรัน cleaner ไม่แก้ raw หรือ CSV ผลลัพธ์โดยตรง ดู [วิธีบันทึกคำแก้](../docs/details/ennxo/cleaning.md#บันทึกคำตอบและแก้ข้อมูล)

Mac2Hand มี `cleaning_rules.json` สำหรับ baseline, `manual_reviews.json` สำหรับคำแก้รายแถว, `finalization_rules.json` และ `iphone_model_names.json` สำหรับขั้นส่งมอบล่าสุด ดู [คู่มือ config Mac2Hand](mac2hand/README.md) และ [วิธี clean](../docs/details/mac2hand/cleaning.md)

## ไฟล์ที่เก็บใน Git

เก็บกฎ catalogue และ `*.example.json` เป็นแม่แบบ ไฟล์จริง `ennxo/corrections.json`, `ennxo/manual_review.json`, `mac2hand/manual_reviews.json` อยู่ในเครื่องและถูก ignore เพราะมีหลักฐานรายประกาศ ดู [วิธีใช้หลัง clone](../docs/details/shared/github.md) ห้ามใช้แม่แบบว่างแทน ledger ของ snapshot เดิม
