# โมเดลที่ฝึกแล้ว

ปัจจุบันใช้ `asking_price_v2/`:

- `model.joblib`: operational model ฝึกครบ 9,210 แถว / 300 รุ่น รวมข้อมูลล่าสุดถึง 2026-10-06 ไม่มี independent test score
- `evaluation.joblib`: โมเดล fit 8,517 แถวก่อน cutoff สำหรับเปรียบเทียบย้อนหลังบน test เดิม 693 แถว
- `metadata.json`: input/code/catalog/model hashes, versions และจำนวน/บทบาทของแต่ละ artifact

V1 เก็บใน `asking_price_v1/` เป็นประวัติ Binary ไม่ขึ้น Git สร้างใหม่ด้วย `script/modeling/train_improved.py` หลัง clone ได้จาก core + public condition sidecar โหลดผ่าน `script/modeling/predict.py` เพื่อเช็ค checksum และใช้ feature contract ของแต่ละเวอร์ชัน

อ่าน [ผลสรุป](../docs/summary/modeling.md) และ [รายละเอียด V2](../reports/modeling/asking_price_v2/report.md)
