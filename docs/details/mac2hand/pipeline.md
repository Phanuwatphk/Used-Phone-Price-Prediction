# เก็บข้อมูล Mac2Hand

คู่มือนี้อธิบายการเก็บ raw และรายละเอียดทุกวันที่จากหมวด [iPhone](https://mac2hand.com/17/iphone) หน้ารวมรอบ 2026-10-06 เก็บครบ 171 หน้า 10,220 ประกาศ รายละเอียดรอบทุกวันที่จบแล้ว ดู [ชุดข้อมูลล่าสุด](finalization.md)

## สคริปต์ที่ใช้

| สคริปต์ | หน้าที่ | ผลที่เขียน |
|---|---|---|
| `run_mac2hand_collection.py` | เริ่มตัวเก็บและอัปเดตความคืบหน้า | `collection_progress.json`, `collection.log` ใน raw |
| `collect_mac2hand.py` | เก็บหน้าเว็บ ใช้ cache และบันทึกข้อผิดพลาด | HTML และ `details/manifest.json` |
| `mac2hand.py` | parser ที่ตัวเก็บใช้ จับคู่สินค้าด้วยรหัส | คืนข้อมูลให้ตัวเก็บ ไม่เขียนไฟล์เอง |
| `monitor_mac2hand.py` | แสดงจำนวนที่เก็บ สำเร็จ/ล้มเหลว PID และ log | อ่านอย่างเดียว |

## รันต่อและ monitor

รันจากรากโปรเจคหลังติดตั้ง dependencies ตาม [README](../../../README.md) ใช้ตัวเก็บหนึ่งงานต่อรอบ:

```bash
.venv/bin/python -u -B scraper/mac2hand/run_mac2hand_collection.py
```

ตรวจความคืบหน้าในอีก Terminal:

```bash
.venv/bin/python scraper/mac2hand/monitor_mac2hand.py
```

Monitor อัปเดตหน้าจอทุก 5 วินาที กด Ctrl+C ปิดหน้าดูได้โดยตัวเก็บยังทำงานต่อ ใช้ `--once` เพื่อดูครั้งเดียว ตัวเลขประมวลผลรอบนี้รวมการอ่าน cache เดิม จึงอาจต่างจากจำนวนหน้าที่มีผลเก็บแล้ว

## หลักฐานที่เก็บ

Raw อยู่ใน `data/raw/mac2hand_20261006T172805_252838_Asia-Bangkok/`:

- `listings.jsonl`, `pages/`, `mac2hand_summary.json`: ข้อมูลการ์ดและ HTML หน้ารวม
- `details/product_<id>.html`: HTML รายสินค้า
- `details/manifest.json`: รหัสประกาศ ไฟล์ เวลา ผลสำเร็จ/ล้มเหลวและข้อผิดพลาด
- `collection_progress.json`, `collection.log`: ความคืบหน้าปัจจุบัน

ตัวเก็บเว้นอย่างน้อย 2 วินาทีระหว่างการดึงหน้าใหม่และใช้ cache เมื่อรันต่อ ข้อผิดพลาดรายหน้าถูกบันทึกแล้วทำรายการถัดไป สคริปต์ปัจจุบันไม่ได้ clean/review หรือสร้างโมเดล

Parser เลือก Product JSON-LD ที่ sku ตรงกับรหัสประกาศ อ่านข้อความผู้ขายเฉพาะสินค้าหลัก ไม่รัน JavaScript ของเว็บ เก็บเวลาใน Asia/Bangkok หมวด iPhone อาจมีสินค้าอื่นปะปน ต้องตรวจขอบเขตภายหลัง

## การเตรียมข้อมูล

ผลล่าสุดอยู่ที่ `data/final/mac2hand/<รอบ>/dataset.csv` ดู [ขั้นส่งมอบ](finalization.md) และ [วิธีตรวจ clean baseline](cleaning.md) ยังไม่มี train/test ราคาที่เก็บเป็นราคาประกาศและสภาพเป็นข้อมูลผู้ขาย ดู [คู่มือไฟล์](../shared/data_guide.md) และ [ข้อมูลดิบ](../shared/data_schema.md)
