# สคริปต์โครงการ

โค้ดทุกขั้นอยู่ที่นี่ แยกหน้าที่และเว็บ งาน shared/modeling ใช้ชุดสองเว็บรวมกัน

| โฟลเดอร์ | ทำอะไร | ข้อมูล/ผลหลัก |
|---|---|---|
| [scraper/](scraper/README.md) | เก็บเว็บ แยก ennxo/mac2hand พร้อม parser และ monitor | `data/raw/` |
| [preparation/](preparation/README.md) | audit, extraction, clean, review, รวมและคัดชุด | `data/intermediate/`, `data/final/` |
| [analysis/](analysis/README.md) | EDA และกราฟสถิติ | `reports/eda/` |
| [modeling/](modeling/README.md) | แบ่งข้อมูล เทรน เปรียบเทียบ ประเมินและทำนาย | `data/intermediate/modeling/`, `models/`, `reports/modeling/` |
| [app/](app/README.md) | ฟอร์มภาษาไทยสำหรับผู้ใช้ เปิดในเบราว์เซอร์ | อ่านโมเดลที่ฝึกแล้ว ผลราคาแสดงบนหน้าจอ |
| [tests/](tests/README.md) | ทดสอบ workflow ด้วย fixtures แบบ offline | ผลทดสอบ ไม่ส่ง request ไปเว็บ |

```bash
.venv/bin/python -B -m unittest discover -s script/tests -t .
```

คำสั่งใช้จากรากโปรเจค แต่ CLI ทุกขั้นรองรับการรันไฟล์ผ่าน absolute path จาก directory อื่นด้วย
