# เก็บข้อมูลจากเว็บไซต์

โฟลเดอร์นี้ใช้ส่ง request เก็บ HTML และอ่านข้อความจากเว็บ แยกตามต้นทาง งาน audit/clean/review/รวมข้อมูลอยู่ใน [preparation](../preparation/README.md) และงาน EDA อยู่ใน [analysis](../analysis/README.md)

| ไฟล์ | ใช้กับ | หน้าที่และผลลัพธ์ |
|---|---|---|
| `ennxo/collect_ennxo.py` | ENNXO | เก็บหน้าหมวดทุกวันโดยไม่จำกัดช่วงเวลา เทียบ URL กับ snapshot เดิม และบันทึก checkpoint เพื่อ resume |
| `ennxo/ennxo_html.py` | ENNXO | parser การ์ดและข้อมูลฝังใน HTML ใช้ร่วมกับขั้น extraction; ไม่รันแยก |
| `mac2hand/collect_mac2hand.py` | Mac2Hand | เก็บหน้าหมวดและหน้ารายละเอียดสินค้า บันทึก HTML และ manifest |
| `mac2hand/run_mac2hand_collection.py` | Mac2Hand | เรียกตัวเก็บและอัปเดต progress/log ใช้เพียงหนึ่งงานต่อรอบ |
| `mac2hand/monitor_mac2hand.py` | Mac2Hand | อ่าน checkpoint และแสดงความคืบหน้า ไม่เริ่มเก็บข้อมูล |
| `mac2hand/mac2hand.py` | Mac2Hand | parser หน้าหมวดและรายละเอียด; ไม่รันแยก |

ผลอยู่ใน `data/raw/<เว็บ_เวลารอบ>/`: `pages/` เก็บ HTML หน้าหมวด, `details/` เก็บหน้ารายละเอียดที่มี, `listings.jsonl` เก็บบัญชีประกาศ ส่วน manifest/progress/summary/log เก็บสถานะการดาวน์โหลด ดู [ไฟล์ raw ENNXO](../docs/details/ennxo/raw.md) และ [pipeline Mac2Hand](../docs/details/mac2hand/pipeline.md)

คำสั่งอ่านสถานะ Mac2Hand จากรากโปรเจค:

```bash
.venv/bin/python -B scraper/mac2hand/monitor_mac2hand.py
```

คำสั่งเก็บใหม่/รันต่อส่ง request ไปเว็บ ให้เลือก snapshot ก่อนรัน ดู `--help` และคู่มือเว็บนั้น ปัจจุบัน snapshot ทั้งสองเว็บเก็บจบแล้ว การจัดโครงสร้างไม่ได้เริ่มการ scrape ใหม่ รองรับรันไฟล์ผ่าน absolute path จาก directory อื่น และ `python -m scraper.<เว็บ>.<โมดูล>` จากรากโปรเจค
