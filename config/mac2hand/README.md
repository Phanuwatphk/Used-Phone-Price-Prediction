# Mac2Hand config

`cleaning_rules.json` เป็นกฎสำหรับ `script/preparation/mac2hand/clean_mac2hand.py` เท่านั้น มีเวอร์ชัน ขอบเขต ค่าความจุที่อ่านได้ ราคา placeholder และ regex ตรวจอุปกรณ์/บริการ/เงินดาวน์/เครื่องเสีย/คำปฏิเสธ

ทุกครั้งที่ clean จะเก็บสำเนา config และ hash ในผลลัพธ์ ดู [วิธีทำและข้อจำกัด](../../docs/details/mac2hand/cleaning.md) ไม่ใช้กฎนี้แก้ raw และไม่ใช้กับ ENNXO

`manual_reviews.json` เก็บ hash ของ clean baseline และคำตัดสินรายแถว พร้อมค่าที่แก้ เหตุผล ข้อความต้นทาง ผู้ตรวจและวันที่ ใช้กับ `review_mac2hand_queue.py` ดู [วิธีตรวจคิว](../../docs/details/mac2hand/review.md)

`finalization_rules.json` เป็นกฎตรวจซ้ำทุกแถวสำหรับ `finalize_mac2hand.py`; `iphone_model_names.json` เก็บชื่อรุ่น iPhone ที่ตรวจจาก Apple พร้อม URL และวันที่ ใช้ตรวจชื่อ ไม่เติมสเปก ทั้งคู่มีสำเนา/hash ใน `final/` ดู [ขั้นส่งมอบ](../../docs/details/mac2hand/finalization.md)
