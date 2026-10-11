# สคริปต์สนับสนุนโครงการ

`tests/` เก็บการทดสอบและ fixtures ของ scraper, preparation และ EDA แยกจากโค้ดที่ใช้งานจริง อ่าน [แต่ละไฟล์ตรวจอะไร](tests/README.md)

รันจากรากโปรเจค:

```bash
.venv/bin/python -B -m unittest discover -s script/tests -t .
```

`-s` เลือกโฟลเดอร์ tests และ `-t .` ระบุรากโปรเจคให้ import โมดูลได้ตรงกัน Tests ใช้ข้อมูลจำลองและ temporary directories ไม่ส่ง request ไปเว็บ
