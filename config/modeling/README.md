# กำหนดการทดลองโมเดล

`training.json` ใช้กับทั้งสองเว็บรวมกัน ตรึง SHA-256 ของชุด 9,210 แถว ระบุจำนวน train/validation โดยสัดส่วนเวลา seed จำนวน threads และรายการโมเดล/พารามิเตอร์ 15 ตัวเลือกก่อนวัด test

เลือกจาก validation MAE เท่านั้น ทดสอบผู้ชนะหลัง refit train+validation ไม่มีการปรับโมเดลตาม test สำหรับทดลองใหม่ให้เปลี่ยน run และเลือกปลายทางใหม่ เก็บรายงานแต่ละรอบแยกกัน ส่วน test เดิมที่ดูผลแล้วไม่ใช่ holdout ใหม่

รอบล่าสุดใช้ `improved.json`: 2 forward folds/12 ตัวเลือก/recency weights/catalog/condition sidecar hashes และ test เดิมแบบย้อนหลัง `iphone_release_years.json` เป็นข้อเท็จจริงปีเปิดตัวจาก Apple ไม่ใช้ dataset target เป็นที่มา
