# เอกสารโครงการ

| อ่านภาพรวม | เนื้อหา |
|---|---|
| [ใช้งานฟอร์มประเมินราคา](summary/app.md) | คำสั่งเปิดแอป วิธีกรอกข้อมูล และตำแหน่งคู่มือไฟล์ |
| [ผลโมเดล](summary/modeling.md) | ผล test แยกเว็บ ข้อจำกัด และไฟล์โมเดล |
| [ชุดโมเดลรอบแรก](summary/model_input.md) | 9,210แถวหลังปิดคิวและคัดออก |
| [สรุป EDA](summary/eda.md) | ผลสำรวจชุดรวมและลิงก์รายงาน/กราฟ |
| [สรุปการ scrape](summary/scraping.md) | สถานะทั้งสองเว็บ |
| [ENNXO](summary/ennxo.md) | Raw ผล clean และคิวตรวจปัจจุบัน |
| [Mac2Hand](summary/mac2hand.md) | สถานะการเก็บและผล clean ทุกวันที่ |

| อ่านรายละเอียด | เนื้อหา |
|---|---|
| [วิธีทำ ENNXO](details/ennxo/methodology.md) | ลำดับงาน หลักเกณฑ์ และคำสั่ง audit ที่ทำซ้ำได้ |
| [ถอดข้อมูล ENNXO](details/ennxo/extraction.md) | หลักฐานรายประกาศและผลขั้นที่ 2 |
| [Clean ENNXO](details/ennxo/cleaning.md) | กฎ ผลลัพธ์ คิวตรวจ และวิธีบันทึกคำแก้ |
| [ตรวจคิว ENNXO](details/ennxo/review.md) | สิ่งที่แก้ได้ หลักฐาน ผลก่อน/หลัง และปัญหาที่ยังค้าง |
| [Raw ENNXO](details/ennxo/raw.md) | ไฟล์ต้นฉบับและขอบเขตการเริ่มใหม่ |
| [เก็บ Mac2Hand](details/mac2hand/pipeline.md) | การเก็บ raw และ monitor |
| [Clean Mac2Hand](details/mac2hand/cleaning.md) | ตรวจ raw, extraction, กฎ clean และคิวตรวจ |
| [ชุดข้อมูล Mac2Hand ล่าสุด](details/mac2hand/finalization.md) | ผลครบคิว สคริปต์ เกณฑ์ หลักฐาน และความหมายของไฟล์ final |
| [ตรวจคิว Mac2Hand](details/mac2hand/review.md) | กลุ่มปัญหา ledger คำแก้ และผลหลัง review |
| [คัดชุดก่อนเทรน](details/shared/model_input.md) | นโยบาย สคริปต์ เหตุผลรายแถว และทุกไฟล์ |
| [วิธีเทรนและทุกไฟล์](details/shared/modeling.md) | แผนแบ่งตามเวลา เปรียบเทียบโมเดล ทำนายและทำซ้ำ |
| [วิธีทำ EDA](details/shared/eda.md) | สคริปต์ กฎ ผลตรวจ และทุกไฟล์รายงาน |
| [ชุดรวมและ schema กลาง](details/shared/combined_dataset.md) | ตรวจ clean แยกเว็บ ปรับชื่อ/ชนิดข้อมูล และรวมพร้อม lineage |
| [ไฟล์สำหรับ GitHub](details/shared/github.md) | ไฟล์ที่รวม/ไม่รวม CI และวิธีใช้หลัง clone |
| [โครงสร้างและผลตรวจ](details/shared/project_structure.md) | มาตรฐานชื่อ ตำแหน่งผลปัจจุบัน และสิ่งที่แก้ |
| [คู่มือไฟล์](details/shared/data_guide.md) | โครงสร้างโปรเจค ผลแต่ละขั้น และงานย้อนหลัง |
| [ข้อมูลดิบ](details/shared/data_schema.md) | ฟิลด์และไฟล์หลัก |

สรุปอยู่ใน `summary/` รายละเอียดแยกเป็น `details/ennxo/`, `details/mac2hand/`, `details/shared/` สำหรับคู่มือร่วม โค้ดเก็บเว็บอยู่ `script/scraper/`, งาน clean/review/รวมอยู่ `script/preparation/`, งาน EDA อยู่ `script/analysis/eda/`

มีชุดรวม 10,032 แถวแล้ว ทำ EDA ร่วมแล้ว คัดเหลือ 9,210 แถว แบ่งข้อมูลและฝึกโมเดลรอบแรกแล้ว

งานโมเดลอยู่ `script/modeling/` ผลล่าสุดอยู่ `reports/modeling/asking_price_v2/` ส่วน V1 เก็บเป็นประวัติ ฟอร์มผู้ใช้อยู่ `script/app/` ดู [คู่มือเปิดแอป](../script/app/README.md)
