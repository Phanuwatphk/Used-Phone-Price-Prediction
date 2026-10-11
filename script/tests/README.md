# Tests

รันจากรากโปรเจคด้วย `.venv/bin/python -B -m unittest discover -s script/tests -t .` การทดสอบใช้ fixtures และ temporary directories ไม่ส่ง request ไปเว็บ ไม่เปลี่ยน raw หรือสั่งเริ่ม/หยุดตัวเก็บ Mac2Hand

| ชื่อไฟล์ | ตรวจอะไร |
|---|---|
| `test_ennxo_collection.py` | Pagination, resume และการเทียบประกาศ ด้วย session จำลอง |
| `test_ennxo_raw_audit.py` | บัญชี raw, URL และการรักษาค่าเดิม |
| `test_ennxo_extraction.py` | การถอด HTML และที่มาของข้อความ |
| `test_ennxo_cleaning.py` | กฎ clean, correction ledger และผลที่ทำซ้ำได้ |
| `test_ennxo_review.py` | บัญชีคิวก่อน–หลัง |
| `test_ennxo_manual_review.py` | คิวตรวจครบ ไม่ซ้ำ และข้อความหลักฐานตรงต้นทาง |
| `test_mac2hand.py` | Parser หน้ารวม/หน้าสินค้าจาก fixtures |
| `test_mac2hand_preparation.py` | Workflow offline บัญชี raw, hash, manifest และการปฏิเสธรอบที่ยังเก็บอยู่ |
| `test_mac2hand_cleaning.py` | รุ่น/ความจุ/ราคา/สภาพ คำปฏิเสธ ขอบเขตสินค้า และการรักษาต้นฉบับ |
| `test_mac2hand_review.py` | ตรวจ hash/หลักฐานจริง ไม่ล้าง hold อื่น ไม่เปลี่ยน baseline และบัญชีคิวหลัง review |
| `test_mac2hand_finalization.py` | กู้ค่าที่มีหลักฐาน ความขัดแย้ง สภาพ SE และ workflow ส่งมอบที่รักษา input/raw และทำซ้ำผล CSV |

`test_combined_dataset.py` ตรวจ source/URL/key ชนิดข้อมูล วันที่ UTC→วันไทย alias รุ่น accepted accounting lineage การป้องกันทับ input และการทำซ้ำ ใช้ fixtures ของทั้งสองเว็บ ไม่ต้องใช้ dataset จริง

`test_eda.py` ตรวจสถิติ ties/IQR กลุ่มย่อย การเทียบเว็บ candidate ซ้ำซ้อนและภาพ การไม่เปลี่ยนข้อมูล การตรงกันของข้อความเสริม และ workflow สร้างกราฟ/รายงานแยกจากคิวรายแถว

`test_ennxo_export.py` ตรวจการส่งออก final ให้ CSV ทุก byte ตรงกลุ่มผ่าน ตรวจค่ากับหลักฐาน และป้องกันเขียนทับ input ส่วน tests ของ finalization/merge/EDA ตรวจปลายทาง final กับ intermediate ที่แยกกันด้วย

`test_model_input_selection.py` ตรวจunionคิวที่ซ้อนกัน unknown ID/hash/count mismatch การไม่เปลี่ยนค่า/lineage การทำซ้ำ และป้องกันoutputทับinput
