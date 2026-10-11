# วิธีทำ EDA ชุดรวม

วิเคราะห์ 10,032 แถวจากชุดรวมหลัง clean ทุกวันที่ของ snapshot ไม่มีการเปลี่ยน dataset อ่าน [สรุป EDA](../../summary/eda.md) หรือ [รายงานละเอียด](../../../reports/eda/ennxo_20261005_mac2hand_20261006/report.md)

## สคริปต์ที่รัน

```bash
.venv/bin/python -u -B script/analysis/eda/run_eda.py
```

ใช้ทั้ง ENNXO และ Mac2Hand อ่าน `dataset.csv`, `dataset.jsonl`, `lineage.jsonl`, `schema.json`, `summary.json`, `run_metadata.json` ของชุดรวม และอ่าน `mac2hand_final.jsonl` เพิ่มสำหรับข้อความที่ไม่มีใน CSV dataset/schema/summary/metadata อยู่ใน `data/intermediate/combined/<รอบ>/before_selection/`; lineage/audit อยู่ใน `data/intermediate/combined/<รอบ>/audit/` และ JSONL ทุกแถว Mac2Hand อยู่ `data/intermediate/mac2hand/<รอบ>/finalization/` ใช้ `--evidence` เลือก lineage directory ตรวจ hash, ชนิดข้อมูล, จำนวน, key และความตรงกันก่อนวิเคราะห์ ตรวจ hash ซ้ำหลังทำงาน

`script/analysis/eda/run_eda.py` เรียก `eda_statistics.py` คำนวณสถิติ และ `eda_plots.py` สร้างกราฟ ค่าเริ่มต้นอิงตำแหน่งไฟล์ รันจาก `/tmp` ด้วย absolute path หรือรันโมดูลจากรากโปรเจคได้

## หลักเกณฑ์

- ตรวจฟิลด์ ค่าขาด source รหัสและ lineage; สำรวจยี่ห้อ รุ่น ความจุ สภาพ ราคาตั้งขายและวันประกาศ
- IQR ใช้ percentile แบบ linear interpolation เทียบภายใน source/brand/model/storage/condition/year กลุ่มอย่างน้อย 10 แถว fence = Q1−1.5IQR และ Q3+1.5IQR กลุ่มเล็ก/IQR=0 ข้ามและบอกจำนวน ไม่ยืนยันว่าแถวที่ไม่ flag ถูกต้องทุกแถว
- เทียบเว็บเฉพาะ brand/model/storage/condition/year ที่มีอย่างน้อย 3 แถวต่อเว็บ ยังมีความต่างเรื่องเดือน สภาพเครื่องจริง และผู้ขาย จึงไม่สรุปเป็นผลของเว็บต่อราคา
- candidate ซ้ำใช้กลุ่มเดิม และข้อความ normalize Unicode/case/ช่องว่างที่ตรงกันยาวอย่างน้อย 80 ตัวอักษร พร้อมยี่ห้อ รุ่น ความจุ สภาพ ราคาเดียวกัน รวมกลุ่มข้อความที่ซ้อนกันเป็น components ภาพซ้ำเป็นสัญญาณแยก ไม่ถือข้อความร้านหรือภาพเดียวเป็นเครื่องเดียวทันที
- Spearman ใช้ average rank สำหรับ ties ไม่ทดสอบนัยสำคัญ ไม่ตีความเชิงเหตุและผล
- sensitivity เป็นสมมติฐานเปรียบเทียบสถิติ ไม่เขียน dataset ที่ลบ outlier/duplicate การเลือก 1 แถวต่อ candidate ไม่ใช่คำตัดสินเครื่องซ้ำ

กฎและ threshold อยู่ใน `config/shared/eda_rules.json` ผล IQR ของ EDA ทั้งชุดไม่ใช้แทน threshold ที่ต้องเรียนรู้จาก train เมื่อเริ่มโมเดล

## ผลที่พบ

ราคา median รวม 18,990 บาท; ENNXO 8,980 และ Mac2Hand 19,900 บาท ความต่างของช่วงปีและรุ่นทำให้ median รวมเทียบเป็นผลเว็บไม่ได้ Apple 9,225 แถว (91.96%) และ 251 จาก 308 คู่ยี่ห้อ–รุ่นมีน้อยกว่า 10 แถว

IQR ประเมินได้ 7,543 แถว ระบุ 205 แถวสำหรับตรวจต่อ ข้ามกลุ่มเล็ก 2,467 และ IQR=0 อีก 22 แถว รวมครบ 10,032 กลุ่มข้อความ candidate หลังรวมการซ้อนกัน 280 components / 617 แถว ยังไม่ยืนยันว่าเครื่องเดียวกัน พบข้อความตรงข้ามเว็บ 0 กลุ่มจากวิธีนี้ ไม่ได้ยืนยันว่าไม่มีประกาศซ้ำข้ามเว็บจริง

ตรวจข้อความครบ 10,032 แถว 9,504 แถวยาวถึง threshold มี 27 กลุ่ม / 403 แถวที่เทียบเว็บตามเกณฑ์ได้ รายละเอียดทุกรุ่น/ปีและผลสมมติฐานอยู่ใน CSV แนบท้ายรายงาน

## โครงสร้างผลและแต่ละไฟล์

รายงานที่เก็บใน Git อยู่ใน `reports/eda/ennxo_20261005_mac2hand_20261006/`

| ไฟล์/โฟลเดอร์ | เก็บอะไร |
|---|---|
| `summary.md` | สรุปสั้น ภาพรวมและประเด็นหลัก |
| `report.md` | รายงานละเอียดพร้อมกราฟและข้อจำกัด |
| `report.html` | รายงานเปิดใน browser กราฟฝังในไฟล์เดียว |
| `figures/*.png`, `*.svg` | กราฟ 8 ชุด export สำหรับอ่าน/นำเสนอ |
| `summary.json` | สถิติหลัก จำนวน candidate และ sensitivity สำหรับใช้งานต่อ |
| `rules.json` | สำเนากฎและ thresholds ที่ใช้ |
| `run_metadata.json` | เวลา dependencies โค้ดและ hash ข้อมูลเข้า |
| `validation.json` | ผลตรวจ input/lineage/จำนวนและการไม่เปลี่ยนข้อมูล |
| `output_hashes.json` | hash ของไฟล์รายงาน กราฟ และตาราง เพื่อเทียบผล/สำรอง |

ตารางใน `tables/` เป็นข้อมูลรวม ไม่มีข้อความติดต่อหรือ URL รายประกาศ

| CSV | เก็บอะไร |
|---|---|
| `source_statistics.csv` | จำนวน สัดส่วน quartile/median/mean ราคาและช่วงวันแต่ละเว็บ |
| `brand_counts.csv`, `model_counts.csv` | จำนวนยี่ห้อ/รุ่น แยกเว็บ |
| `publication_year_counts.csv` | จำนวนตามปีประกาศ แยกเว็บ ไม่ใช่ปริมาณตลาดจริง |
| `storage_counts.csv`, `condition_counts.csv` | จำนวนความจุและช่องสภาพ แยกเว็บ |
| `model_price_statistics.csv` | สถิติราคาตามเว็บ/ยี่ห้อ/รุ่น |
| `model_storage_year_statistics.csv` | สถิติกลุ่มเว็บ/รุ่น/ความจุ/สภาพ/ปี พร้อม n |
| `source_comparisons.csv` | กลุ่มที่เทียบ median ของสองเว็บได้ พร้อม n และเปอร์เซ็นต์ต่าง |
| `correlations.csv` | Spearman รวมและแยกเว็บ |
| `sensitivity.csv` | สถิติกรณีสมมติพัก flags หรือเลือก 1 แถวต่อ candidate |
| `outlier_fences.csv` | ขนาดกลุ่มและ fence ที่ใช้ตรวจ IQR |

คิวตรวจรายแถวเก็บเฉพาะเครื่องใน `data/intermediate/eda/ennxo_20261005_mac2hand_20261006/`

| ไฟล์ | เก็บอะไร |
|---|---|
| `outlier_candidates.csv` | 205 แถว พร้อม URL ราคา peer_n median/fence และงานถัดไป |
| `price_extremes.csv` | 5 ราคาสูงสุดต่อเว็บจากขั้นรวม สำหรับตรวจร่วมกับ IQR |
| `duplicate_groups.json` | ทุกกลุ่ม candidate พร้อมวิธีและ listing_id ที่เกี่ยวข้อง กลุ่มซ้อนกันได้ |
| `duplicate_memberships.csv` | mapping แต่ละแถวเข้ากลุ่ม candidate; listing_id อาจซ้ำเมื่ออยู่หลายกลุ่ม |
| `text_candidate_components.json` | กลุ่มข้อความหลังรวมการซ้อนกัน 280 กลุ่ม / 617 แถว |
| `validation.json` | สำเนาผลตรวจความครบและไม่เปลี่ยน input |

## การตรวจงาน

ผ่าน 121 tests ครอบคลุม percentile/ties, การแยกปีและกลุ่ม, zero IQR, กลุ่มซ้ำซ้อนและภาพ, sensitivity ไม่เปลี่ยนข้อมูล, supplementary text ที่ตรง CSV, การป้องกัน output ทับ input, CSV/JSONL ตรงกัน และการสร้างรายงาน/กราฟแยกจากคิวส่วนตัว ตรวจกราฟด้วยภาพจริงและตรวจรันซ้ำจาก directory อื่น

ขั้นต่อไปคือตรวจ candidate/outlier ตามหลักฐาน แล้วกำหนด split และนโยบายข้อมูลฝึก การทำ EDA รอบนี้ไม่ได้รับรองสภาพเครื่องจริงหรือสร้างโมเดล

นโยบายล่าสุด2026-10-11: ผู้ใช้เลือกตัดสมาชิกคิวEDAทั้งหมด822แถวและหยุดreview ชุดโมเดล9,210แถวอยู่ขั้น [คัดชุดก่อนเทรน](model_input.md) รายงานEDAนี้เป็นผลก่อนคัด10,032แถว
