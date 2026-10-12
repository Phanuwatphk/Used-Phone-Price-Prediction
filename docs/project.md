# ภาพรวมโครงการ

เอกสารนี้อธิบายโครงสร้างข้อมูล หน้าที่ไฟล์และเครื่องมือ กฎที่ใช้ และการตรวจคุณภาพ อ่านวิธีใช้งานเว็บไซต์ที่ [README](../README.md)

| เรื่อง | อ่านที่ไหน |
|---|---|
| ตำแหน่งข้อมูล | [ตำแหน่งจัดเก็บข้อมูล](#ตำแหน่งจัดเก็บข้อมูล) |
| เครื่องมือแต่ละขั้น | [สคริปต์ทุกขั้น](#scripts) |
| กฎและแผนโมเดล | [Config](#config) |
| โมเดลและหลักฐานย้อนหลัง | [ไฟล์โมเดล](#model-artifacts) · [งานย้อนหลัง](#archive) |

โค้ดโมเดลแยกใน `script/modeling/model_v1/` และ `model_v2/`; โมดูลร่วมอยู่ด้านนอก ตารางด้านล่างอธิบายหน้าที่แต่ละไฟล์

`.devcontainer/devcontainer.json` กำหนด Python 3.12 ติดตั้ง dependencies จาก requirements และเปิดหน้าเว็บด้วย app/app.py ใน container โดยไม่เริ่ม scraper หรือฝึกโมเดล

## เอกสารและผลรายงาน

| ไฟล์ / โฟลเดอร์ | หน้าที่ |
|---|---|
| [README.md](../README.md) | ลิงก์เว็บไซต์และวิธีใช้งาน |
| [data.md](data.md) | วิธีเก็บ ตรวจ clean review รวม และคัดข้อมูล |
| [project.md](project.md) | ภาพรวมโครงสร้าง ขั้นตอน และกฎของโครงการ |
| [eda.md](eda.md) | รายงานสำรวจข้อมูล สถิติและกราฟ |
| [modeling.md](modeling.md) | Features การแบ่งข้อมูล ฝึก ผลประเมิน และข้อจำกัด |
| `assets/eda/` | กราฟ/ตาราง EDA พร้อม report.html และ metadata.json |
| `assets/modeling/` | กราฟผลโมเดล ตารางคะแนน HTML และ metadata |
| `assets/modeling/history.zip` | ผลและรายงานการทดลองเดิม |
| `history/*.json` | บัญชีย้ายไฟล์ย้อนหลัง |

## ตำแหน่งจัดเก็บข้อมูล

| ตำแหน่ง | เก็บอะไร |
|---|---|
| `data/raw/` | HTML บัญชีประกาศ checkpoint/log ต้นฉบับ |
| `data/intermediate/` | extraction, clean, review, lineage, ชุดก่อนคัด, split และ predictions |
| `data/final/dataset.csv` | ชุดหลัก 13 คอลัมน์ 9,210 แถว รวมสองเว็บ |
| `data/final/condition_features.csv` | listing_id + แบตเตอรี่/ประกันวัน/กล่อง; ว่างคือไม่ทราบ |
| `config/` | schema กฎ alias นโยบาย catalog และแผนทดลอง |
| `models/asking_price_v2/` | operational/evaluation artifacts และ metadata/checksums |
| `docs/assets/{eda,modeling}/` | กราฟ ตาราง CSV HTML และ metadata; เอกสารอ่านอยู่ docs/eda.md และ docs/modeling.md |
| `docs/history/` | บัญชีย้ายไฟล์ในอดีต (JSON) |

Path/hash ใน metadata และ `docs/history/` บันทึกตำแหน่ง ณ รอบเดิม จึงคงไว้เป็นหลักฐานย้อนหลัง ตำแหน่งใช้งานปัจจุบันอ่านจาก `data/datasets.json` และคู่มือนี้ ใช้ [บัญชีย้ายไฟล์](history/) เมื่อต้องตามหลักฐานที่ย้ายแล้ว

## การตรวจคุณภาพโครงการ

CI ตรวจ dependencies, syntax, การสร้าง features จากข้อมูลที่เผยแพร่ และ tests แบบ offline รวมฟอร์มเว็บ ความตรงกันของ dataset/โมเดล ลิงก์เอกสาร และ checksum รายงาน การตรวจนี้ไม่เก็บข้อมูลจากเว็บหรือฝึกโมเดลจริง

ข้อมูลดิบ ผลระหว่างทาง และหลักฐานรายแถวเก็บแยกจากข้อมูลสุดท้าย ชุดเผยแพร่มี dataset 9,210 แถว ข้อมูลแบตเตอรี่/ประกัน/กล่อง และ metadata ส่วนโมเดลใช้งานมี binary กับ metadata ที่ตรวจ checksum คู่กัน

<a id="model-artifacts"></a>

## ไฟล์โมเดลในเครื่อง

| ไฟล์ใน models/asking_price_v2/ | เก็บอะไร |
|---|---|
| `model.joblib` | โมเดลใช้งาน ฝึกครบ 9,210 แถว / 300 รุ่น ถึง 2026-10-06 ไม่มีคะแนนทดสอบอิสระ |
| `evaluation.joblib` | fit 8,517 แถวก่อน cutoff สำหรับผลย้อนหลังบน test เดิม 693 แถว |
| `metadata.json` | input/code/catalog/model hashes, versions และบทบาทของแต่ละ artifact |

V1 และ evaluation.joblib เป็นหลักฐานย้อนหลังแยกจากโมเดลใช้งาน V2; metadata เก็บ checksum และ feature contract ของแต่ละโมเดล ผลและข้อจำกัดอ่าน [รายงานโมเดล](modeling.md)

รอบปรับปรุง 2026-10-12 ใช้ `model_v2/train_improved.py` ตัวเดียว:

| ไฟล์ | หน้าที่ |
|---|---|
| `config/modeling/current.json` | แผนโมเดลใช้งานปัจจุบัน; ผล docs/assets/modeling/ และ models/asking_price_v2/ |
| `config/modeling/experiments.json` | เก็บ baseline/revision/age_transfer/ensemble ครบในไฟล์เดียว |
| `script/modeling/trend.py` | estimator สำหรับ trend, age normalization และ ensemble; ไม่รันแยก |
| `docs/assets/modeling/history.zip` | รายงาน กราฟ ตาราง และ config ของ 4 รอบเดิม เปิดอ่านโดยแตก ZIP |

ผล 33 ตัวเลือกอยู่ `docs/assets/modeling/metadata.json#tuning_review` กับ `tables/tuning_validation.csv` อ่านคำอธิบายใน [รายงานโมเดล](modeling.md#11-รอบปรับปรุง-2026-10-12) สำรองก่อนปรับอยู่ `archive/modeling/before_tuning_20261012/` การฝึกหลักเลือกด้วย validation แล้ว refit evaluation/operational ไม่ใช้ราคา test เป็น feature

<a id="archive"></a>

## งานย้อนหลังใน archive/

| โฟลเดอร์ | เก็บอะไร |
|---|---|
| `experiments/ennxo/` | parser/รายละเอียด ENNXO ทดลองเดิม บางไฟล์อ้างโมดูลที่เลิกใช้ |
| `legacy_kaggle/` | dataset/สคริปต์ Kaggle เดิม ไม่ใช่สองเว็บปัจจุบัน |
| `planning/` | ร่าง schema และบัญชีย้ายเดิม ไม่ใช่ schema กลางที่ใช้อยู่ |
| `mac2hand/<รอบ>/` | legacy_preparation และ before_quality_review สำรองผลเดิมก่อนตรวจ |

เก็บในเครื่องเพื่ออ้างอิง ไม่ใช้เป็น entry point หรือแทน final ตำแหน่งย้ายพร้อม checksum อยู่ใน [บัญชีย้ายไฟล์](history/structure_reorganization_20261011.json) และ JSON รอบอื่นใน docs/history/ ข้อมูลย้อนหลังยังอยู่ครบ

<a id="scripts"></a>

## สคริปต์ทุกขั้น

ตารางต่อไปนี้อธิบายหน้าที่เครื่องมือ ข้อมูลเข้า และผลลัพธ์ของแต่ละขั้น เพื่อใช้อ่านประกอบวิธีดำเนินโครงการ

| งาน | ใช้กับ | อ่าน / เขียนที่ไหน |
|---|---|---|
| [เปิดเว็บ](#scripts-app) | ชุดรวม | อ่าน final + โมเดล + รายงาน; แสดงผล/ดาวน์โหลด CSV |
| [เก็บข้อมูล](#scripts-scraper) | แยก ENNXO / Mac2Hand | เว็บ → data/raw/ |
| [เตรียมข้อมูล](#scripts-preparation) | แยกเว็บและ shared | raw → intermediate → final |
| [EDA](#scripts-analysis) | ทั้งสองเว็บ | ชุดก่อนคัด → docs/eda.md และ assets; คิวใน intermediate |
| [โมเดล](#scripts-modeling) | ทั้งสองเว็บ | final → features/split/predictions, models และรายงาน |
| [Tests](#scripts-tests) | ทุกขั้น | ใช้ fixtures แบบ offline |

กฎอยู่ใน [Config](#config) ผล EDA/โมเดลอ่านจาก [เอกสารโครงการ](../README.md#เอกสารโครงการ)

<a id="scripts-app"></a>

<a id="scripts-เปิดเว็บ"></a>

### การใช้งานเว็บไซต์

เปิด **[Used Phone Price](https://secondhand-phone-price-prediction.streamlit.app/)** ผ่านเบราว์เซอร์ มีเมนูประเมินราคา สำรวจข้อมูล และผลโมเดล

| ไฟล์ใน app/ | หน้าที่ |
|---|---|
| `app.py` | เมนูและฟอร์มประเมินราคา |
| `dashboard.py` | ตัวกรอง กราฟ ตาราง ดาวน์โหลด CSV และรายงานโมเดล |

การค้นหารุ่นปรับข้อความด้วย Unicode NFKC ตัวพิมพ์เล็ก และการตัดช่องว่าง/เครื่องหมายสำหรับจับคู่ เช่น `iphone13`, `IPHONE-13` และ `iPhone 13` ค้นหารุ่นเดียวกันได้ โดยไม่แก้ชื่อใน dataset ใต้ช่องค้นหามี dropdown ของรุ่นที่ตรงกับคำค้นและตัวกรองเว็บ/ยี่ห้อ/สภาพ เลือกได้ทั้งรุ่นเฉพาะหรือทุกรุ่นที่ตรง เมื่อเปลี่ยนคำค้นจะล้างการเลือกรุ่นเดิม

ฟอร์มรับยี่ห้อ รุ่น ความจุ วันที่ประกาศ และข้อมูลเพิ่มเติมที่ทราบ ได้แก่แบตเตอรี่ ประกัน และกล่อง ความจุเปลี่ยนตามรุ่น iPhone ใช้สเปกจาก Apple ส่วนรุ่นอื่นใช้ค่าที่พบใน dataset โมเดลคำนวณกลุ่มรุ่นและอายุรุ่นให้เอง

ค่า source และ condition ภายในเป็น mac2hand และ used ตามขอบเขตเดิม โมเดลยังไม่มี feature ความเสียหาย รอยตำหนิ หรือประวัติซ่อม จึงใช้กับเครื่องที่ทำงานปกติ กราฟสำรวจราคา/จำนวนเริ่มที่ศูนย์ ส่วนกราฟความคลาดเคลื่อนแสดงค่าบวกและลบตามจริง

ลิงก์รายงานในหน้าเว็บชี้ไปยังไฟล์และหัวข้อที่ตรงกันใน GitHub ส่วน HTML ที่ดาวน์โหลดใช้ anchor ภายในสำหรับข้ามหัวข้อ และลิงก์ GitHub สำหรับไฟล์ประกอบ

เว็บไซต์อ่านชุดข้อมูล โมเดล และรายงานที่จัดเตรียมไว้ ไม่เริ่มเก็บข้อมูลหรือฝึกโมเดลระหว่างที่ผู้ใช้ใช้งาน

Sidebar อยู่กับที่และไม่มีการเลื่อนภายใน เมนูและข้อความแสดงครบโดยลดระยะห่างเมื่อหน้าจอมีความสูงน้อย ส่วนเนื้อหาหลักยังเลื่อนได้ตามปกติ

<a id="scripts-scraper"></a>

<a id="scripts-เก็บข้อมูลจากเว็บ"></a>

### เก็บข้อมูลจากเว็บ

สคริปต์ใน `script/scraper/` ใช้ส่ง request เก็บ HTML และอ่านข้อความจากเว็บ แยกตามต้นทาง งาน audit/clean/review/รวมข้อมูลอยู่ใน [preparation](#scripts-preparation) และงาน EDA อยู่ใน [analysis](#scripts-analysis)

| ไฟล์ใน script/scraper/ | ใช้กับ | หน้าที่และผลลัพธ์ |
|---|---|---|
| `ennxo/collect_ennxo.py` | ENNXO | เก็บหน้าหมวดทุกวันโดยไม่จำกัดช่วงเวลา เทียบ URL กับ snapshot เดิม และบันทึก checkpoint เพื่อ resume |
| `ennxo/ennxo_html.py` | ENNXO | parser การ์ดและข้อมูลฝังใน HTML ใช้ร่วมกับขั้น extraction; ไม่รันแยก |
| `mac2hand/collect_mac2hand.py` | Mac2Hand | เก็บหน้าหมวดและหน้ารายละเอียดสินค้า บันทึก HTML และ manifest |
| `mac2hand/run_mac2hand_collection.py` | Mac2Hand | เรียกตัวเก็บและอัปเดต progress/log ใช้เพียงหนึ่งงานต่อรอบ |
| `mac2hand/monitor_mac2hand.py` | Mac2Hand | อ่าน checkpoint และแสดงความคืบหน้า ไม่เริ่มเก็บข้อมูล |
| `mac2hand/mac2hand.py` | Mac2Hand | parser หน้าหมวดและรายละเอียด; ไม่รันแยก |

ผลอยู่ใน `data/raw/<เว็บ_เวลารอบ>/`: `pages/` เก็บ HTML หน้าหมวด, `details/` เก็บหน้ารายละเอียดที่มี, `listings.jsonl` เก็บบัญชีประกาศ ส่วน manifest/progress/summary/log เก็บสถานะการดาวน์โหลด ดู [ไฟล์ raw ENNXO](data.md#ennxo-stage-raw) และ [pipeline Mac2Hand](data.md#mac2hand-stage-pipeline)

<a id="scripts-preparation"></a>

<a id="scripts-เตรียมและรวมข้อมูล"></a>

### เตรียมและรวมข้อมูล

อ่านข้อมูลในเครื่อง ไม่ส่ง request ไปเว็บ ลำดับงานคือ raw → audit/extraction → clean/review → final → รวม schema กลาง แยก ENNXO, Mac2Hand และงานที่ใช้ทั้งคู่ชัดเจน

| สคริปต์ใน preparation/ | ใช้กับ | อ่านอะไร / ทำอะไร | เขียนไว้ที่ไหน |
|---|---|---|---|
| `ennxo/audit_ennxo_raw.py` | ENNXO | raw → ตรวจจำนวน URL ฟิลด์ ค่าขาด และ HTML | `data/intermediate/ennxo/<รอบ>/raw_audit/` |
| `ennxo/extract_ennxo_raw.py` | ENNXO | raw → ถอดค่าจาก HTML เก็บต้นฉบับและที่มา | `.../extraction/` |
| `ennxo/clean_ennxo.py` | ENNXO | extraction + กฎ + corrections → normalize และแยกสถานะ | `.../clean/` |
| `ennxo/review_ennxo_queue.py` | ENNXO | clean + baseline → เทียบคิวก่อน/หลัง | `.../review/` |
| `ennxo/finalize_ennxo_manual_review.py` | ENNXO | clean + ledger + baseline → ตรวจคำตัดสินครบคิวและแยกผล | `.../manual_review/` |
| `ennxo/export_ennxo_dataset.py` | ENNXO | clean → ตรวจ accepted.csv เทียบ JSONL แล้วคัดลอก CSV ทุก byte | `data/intermediate/ennxo/<รอบ>/accepted/` |
| `mac2hand/prepare_mac2hand.py` | Mac2Hand | raw → ตรวจ manifest/hash และ parse HTML | `data/intermediate/mac2hand/<รอบ>/{raw_audit,extraction}/` |
| `mac2hand/clean_mac2hand.py` | Mac2Hand | extraction + กฎ → ตรวจและแยกสถานะ | `.../clean/` |
| `mac2hand/review_mac2hand_queue.py` | Mac2Hand | clean + ledger → ตรวจคำแก้และจัดคิว | `.../manual_review/` |
| `mac2hand/finalize_mac2hand.py` | Mac2Hand | ผล review + กฎ → ส่งมอบกลุ่มผ่านและแยกปัญหาทุกแถว | `data/intermediate/mac2hand/<รอบ>/accepted/` และ `data/intermediate/mac2hand/<รอบ>/finalization/` |
| `shared/select_model_input.py` | ทั้งสองเว็บ | ชุดรวม + คิวEDA + นโยบาย → ตัดunion822รหัส | `data/final/` และ `data/intermediate/model_input/<รอบ>/` |
| `shared/prepare_combined_dataset.py` | ทั้งสองเว็บ | อ่าน CSV ผ่านจาก registry → ตรวจรายเว็บ ปรับ schema รวม พร้อม source | `data/intermediate/combined/<รอบ>/before_selection/` และ `data/intermediate/combined/<รอบ>/audit/` |

โมดูลประกอบ: ENNXO `cleaning_rules.py` เก็บกฎตรวจฟิลด์, `description_sections.py` แยกส่วนรายละเอียด; Mac2Hand `resolution_rules.py` เก็บกฎตรวจหลักฐานขั้นส่งมอบ โมดูลเหล่านี้ไม่รันแยก

ขั้นคัดชุดโมเดลใช้ `shared/select_model_input.py` อ่าน [วิธีทำและหน้าที่ไฟล์](data.md#stage-model_input) ได้ชุด 9,210 แถว ก่อน [ขั้นโมเดล](#scripts-modeling)

<a id="scripts-analysis"></a>

<a id="scripts-วิเคราะห์-eda"></a>

### วิเคราะห์ EDA

โค้ดวิเคราะห์แยกจากการเก็บและเตรียมข้อมูล ปัจจุบันมีขั้น EDA ใน `eda/` ขั้นฝึกโมเดลแยกไว้ใน [ขั้นโมเดล](#scripts-modeling)

| ไฟล์ใน analysis/ | ใช้กับ / หน้าที่ |
|---|---|
| `eda/run_eda.py` | ชุดรวมทั้งสองเว็บ ตรวจ CSV/JSONL/lineage แล้วสร้างรายงานและคิวตรวจ |
| `eda/eda_statistics.py` | สถิติ IQR รายกลุ่ม candidate ซ้ำ Spearman และ sensitivity; ไม่รันแยก |
| `eda/eda_plots.py` | สร้างกราฟ PNG/SVG แบบ offline; ไม่รันแยก |

อ่าน dataset จาก `data/intermediate/combined/<รอบ>/before_selection/`, lineage/audit จาก `data/intermediate/combined/<รอบ>/audit/` และข้อความเต็มจาก `data/intermediate/mac2hand/<รอบ>/finalization/mac2hand_final.jsonl` ตรวจข้อความให้ตรงค่าต้นทางก่อนใช้ กฎอยู่ที่ `config/shared/eda_rules.json`

รายงานหลักอยู่ใน `docs/eda.md`; ไฟล์ประกอบอยู่ใน `docs/assets/eda/<รอบ>/`: summary JSON, HTML, `figures/` และ `tables/` คิวรายแถวและ URL อยู่ใน `data/intermediate/eda/<รอบ>/` สคริปต์ไม่แก้ dataset

เมื่อใช้ปลายทางทดลองแบบเดิมและไม่ส่ง option ปลายทางเสริม CLI ยังรองรับ bundle ใน output/input เดียว ค่าเริ่มต้นของ snapshot ปัจจุบันแยกขั้นตาม registry

<a id="scripts-modeling"></a>

<a id="scripts-ฝึกและใช้โมเดล"></a>

### ฝึกและใช้โมเดล

| ไฟล์ / โฟลเดอร์ | หน้าที่ |
|---|---|
| `model_v1/train_models.py` | ทดลอง baseline ตาม config เลือกด้วย validation แล้วประเมิน test |
| `model_v1/report.py` | สร้างรายงาน กราฟ และตารางผล V1 |
| `model_v2/features_v2.py` | สร้าง 22 features รวมอายุรุ่น แบตเตอรี่ ประกัน และกล่อง |
| `model_v2/prepare_features_v2.py` | ถอดข้อมูลเพิ่มเติมจากรายละเอียด พร้อมบันทึกหลักฐาน |
| `model_v2/rebuild_features_v2.py` | สร้าง input ฝึกจาก dataset กับ condition_features.csv ตรวจ hashes |
| `model_v2/train_improved.py` | เลือกด้วย temporal validation 2 ช่วง ประเมินย้อนหลัง และฝึกโมเดลใช้งาน |
| `model_v2/report_improved.py` | สร้างรายงาน V2, HTML, กราฟ และตารางจากผลที่บันทึกไว้ |
| `features.py` | ตรวจ input และสร้าง features พื้นฐานที่ V1/V2 ใช้ร่วม |
| `split_dataset.py` | อ่าน/ตรวจ dataset แบ่งข้อมูลตามวัน และฟังก์ชันไฟล์/hash ที่ทั้งสองรุ่นใช้ |
| `common.py` | สร้าง baseline วัด metrics รายกลุ่ม จัดตาราง และเลือกคอลัมน์ |
| `predict.py` | ตรวจ checksum โหลด V1/V2 และทำนายให้หน้าเว็บ; รองรับ path ภายในโมเดลเดิม |
| `trend.py` | Estimator ของ trend, depreciation และ ensemble ใช้ในการทดลองและโหลดโมเดลที่ฝึกแล้ว |


วิธีคัดข้อมูล features แบ่ง/เทรน ตัววัด ผล กราฟ และหน้าที่ทุกไฟล์ อ่าน [รายงานโมเดล V2 ไฟล์เดียว](modeling.md)

`model_v2/report_improved.py` สร้างรายงาน/กราฟใหม่จากผลที่บันทึกไว้โดยไม่เทรน ใช้ prediction ใน intermediate ที่อยู่ในเครื่อง `model_v1/train_models.py` และ `model_v1/report.py` เก็บไว้ทำซ้ำ V1 สำหรับประวัติ; predict รองรับโมเดลทั้ง V1/V2

<a id="scripts-tests"></a>

<a id="scripts-ทดสอบ-workflow"></a>

### ทดสอบ workflow

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

`test_modeling.py` ตรวจ split ตามวัน ไม่ใช้ target/ID เป็น feature, encoder ไม่ฟิตกับ validation, input/hash และปลายทางที่ห้ามทับ, หน่วย metric, workflow fixture และ model roundtrip พร้อม test แยกจาก fit

`test_modeling_improved.py` ตรวจ explicit/ambiguous description claims, อายุจาก frozen catalog, missing/unknown model inference, train-only recency weights, การตั้ง loss/พารามิเตอร์, CatBoost clone, การทำนาย/serialization ของ trend และ ensemble

`test_app.py` ตรวจโมเดลที่ใช้งานผ่านเว็บไซต์ จาก checkout แยก การตรึง dependencies ให้ตรง artifact และฟอร์มภาษาไทย การเลือกรุ่นตามยี่ห้อ unknown/ศูนย์/วันที่ และค่าคงที่ source=mac2hand, condition=used dropdown ความจุตามรุ่นและค่าที่ส่งเข้า inference ตัวกรอง/empty state การไม่เปลี่ยน dataset การเปิดหน้าสำรวจ/ผลโมเดลโดยไม่มี binary และการโหลดหน้าเว็บใน process ใหม่ ใช้ fixture ชั่วคราว ไม่ต้องมี binary ส่วนตัว CI เรียก tests เหล่านี้ผ่าน `.github/workflows/ci.yml`

`test_project_integrity.py` ตรวจลิงก์เอกสารและ dataset registry, CSV/JSONL/sidecar, จำนวน/source/schema และความตรงกันของโมเดลกับรายงาน รวม checksum ของไฟล์ประกอบรายงานทุกชุด ตรวจเฉพาะ public files จึงรันหลัง clone และใน CI ได้

`test_model_report.py` ตรวจตัวเลขรายงานกับ metadata.json#summary, การแยก metrics จาก hypothesis test, ตารางสูตร และ HTML ที่ฝังกราฟ 5 ภาพในไฟล์เดียว

<a id="config"></a>

## Config ทุกไฟล์

กฎแยกตามเว็บ ส่วน `shared/` และ `modeling/` ใช้ข้อมูลทั้งสองเว็บ ตารางนี้ระบุว่าแต่ละไฟล์ใช้กับสคริปต์ไหน ไม่แก้ raw หรือ CSV ผลลัพธ์โดยตรง: บันทึกคำแก้ใน ledger แล้วรันขั้นที่เกี่ยวข้องใหม่

<a id="config-ennxo"></a>

<a id="config-ennxo"></a>

### ENNXO

| ไฟล์ใน ennxo/ | หน้าที่ / สคริปต์ที่ใช้ |
|---|---|
| `cleaning_rules.json` | กฎเวอร์ชัน 6: ยี่ห้อ ความจุ และ reference ชื่อรุ่น ใช้กับ `clean_ennxo.py` |
| `corrections.json` | คำแก้/แยกออกที่ cleaner ใช้ ผูกกับ URL และ input hash |
| `manual_review.json` | บันทึกตรวจคิว 126 รายการ และขอบเขตโมเดลที่ผู้ใช้เลือก |

อ่าน [วิธี clean และบันทึกคำแก้](data.md#ennxo-stage-cleaning)

<a id="config-mac2hand"></a>

<a id="config-mac2hand"></a>

### Mac2Hand

| ไฟล์ใน mac2hand/ | หน้าที่ / สคริปต์ที่ใช้ |
|---|---|
| `cleaning_rules.json` | baseline ของ `clean_mac2hand.py`: version, ขอบเขต, ความจุ, ราคา placeholder และ regex ตรวจอุปกรณ์/บริการ/เงินดาวน์/เครื่องเสีย/คำปฏิเสธ |
| `manual_reviews.json` | `review_mac2hand_queue.py`: hash baseline, คำตัดสิน/ค่าที่แก้ เหตุผล ข้อความหลักฐาน ผู้ตรวจและวันที่ |
| `finalization_rules.json` | กฎตรวจซ้ำทุกแถวของ `finalize_mac2hand.py` |
| `metadata.json` | model_catalog: ชื่อรุ่น iPhone ที่ตรวจจาก Apple พร้อม URL/วันที่ ใช้ตรวจชื่อ ไม่เติมสเปก |

แต่ละขั้นเก็บสำเนากฎ/catalog และ hash ในผลลัพธ์ กฎของ Mac2Hand ไม่ใช้กับ ENNXO อ่าน [clean](data.md#mac2hand-stage-cleaning), [review](data.md#mac2hand-stage-review) และ [ส่งมอบ](data.md#mac2hand-stage-finalization)

<a id="config-shared"></a>

<a id="config-ใช้ร่วมกันทั้งสองเว็บ"></a>

### ใช้ร่วมกันทั้งสองเว็บ

| ไฟล์ใน shared/ | หน้าที่ / สคริปต์ที่ใช้ |
|---|---|
| `dataset_schema.json` | คอลัมน์ ชนิด หน่วย timezone นโยบายรวม/alias รุ่น สำหรับ `prepare_combined_dataset.py` |
| `eda_rules.json` | กลุ่ม/จำนวนขั้นต่ำ IQR การเทียบเว็บ และ candidate ข้อความซ้ำ สำหรับ `run_eda.py` |
| `model_input_policy.json` | นโยบายผู้ใช้ตัดสมาชิกคิว EDA ทั้งหมด พร้อม expected counts/input hashes สำหรับ `select_model_input.py` |

Schema ไม่เปลี่ยนคำตัดสิน source cleaner รุ่นไม่มี alias คงไว้ ไม่เติมความจุ/ราคา ไม่ fuzzy match รุ่นย่อย กฎ EDA ใช้สำรวจ ไม่แก้ dataset อ่าน [รวมข้อมูล](data.md#stage-combined_dataset), [EDA](eda.md#stage-eda) และ [คัดชุดโมเดล](data.md#stage-model_input)

### หน้าเว็บ

| ไฟล์ใน app/ | หน้าที่ |
|---|---|
| `storage_options.json` | ความจุ iPhone จาก Apple Support 54 รุ่น หน่วย GB พร้อมที่มา/วันที่/hash; ใช้กับ dropdown โดยไม่แก้ชุดฝึก |

<a id="config-modeling"></a>

<a id="config-โมเดล"></a>

### โมเดล

| ไฟล์ใน modeling/ | หน้าที่ |
|---|---|
| `current.json` | รอบ V2: 2 forward folds, 9 ตัวเลือกใน config หลัก (33 ตัวเลือกไม่ซ้ำรวมรอบปรับปรุง), recency weights, catalog/condition sidecar hashes และการวัด test เดิมย้อนหลัง |
| `experiments.json` (revision/age_transfer/ensemble) | กลุ่มทดลองแยก loss/trend, age normalization และ ensemble; outputs แยก run |
| `iphone_release_years.json` | ปีเปิดตัวจาก Apple ไม่ใช้ target ใน dataset เป็นที่มา |
| `experiments.json` (baseline) | รอบ V1: SHA-256 ชุด 9,210 แถว, split ตามเวลา, seed, threads และพารามิเตอร์ 15 ตัวเลือก |

เลือกจาก validation MAE แล้ว refit ก่อนประเมิน รอบ V1 ไม่ปรับโมเดลตาม test; V2 ใช้ test เดิมที่ดูแล้ว จึงเป็นผลย้อนหลัง สำหรับทดลองใหม่เปลี่ยน run และปลายทาง เก็บผลแต่ละรอบแยกกัน อ่าน [วิธีและผลโมเดล](modeling.md)



รูปแบบผลปัจจุบัน: แต่ละโฟลเดอร์ใช้ `metadata.json` รวมข้อมูลกำกับ ส่วน `metadata.json#summary` หมายถึง key summary ใน JSON ไม่ใช่ไฟล์อีกไฟล์ ชื่อไฟล์กำกับเดิมในประวัติ/raw คงเดิมเพื่อรักษาหลักฐาน; registry `data/datasets.json` ระบุตำแหน่งปัจจุบัน รายงาน EDA อยู่ `docs/eda.md` และโมเดลอยู่ `docs/modeling.md` ผลประกอบใน `docs/assets/eda/` และ `docs/assets/modeling/` ไม่มีชั้นชื่อรอบปัจจุบันซ้ำ รายงานโมเดลเดิม 4 รอบอยู่ history.zip สำรองก่อนลดไฟล์ทั้งโครงการอยู่ `archive/structure_before_simplification_20261012.zip` (เฉพาะในเครื่อง)


## ไฟล์ประกอบอื่น

| ไฟล์ / โฟลเดอร์ | หน้าที่ |
|---|---|
| `script/report_links.py` | แปลงลิงก์รายงานบนเว็บไปยังไฟล์/หัวข้อบน GitHub และสร้าง anchor ของ HTML |
| `script/artifacts.py` | อ่าน/เขียน metadata รวม รักษาที่มาและ checksum ใช้ทั้งสองเว็บ |
| `script/preparation/ennxo/cleaning_rules.py` | กฎตรวจฟิลด์ ENNXO |
| `script/preparation/ennxo/description_sections.py` | แยกข้อความรายละเอียด ENNXO เป็นส่วน |
| `script/preparation/mac2hand/resolution_rules.py` | ตัดสินจากหลักฐานในขั้นส่งมอบ Mac2Hand |
| `script/tests/test_artifacts.py` | ตรวจการรวม metadata และการรักษา byte/checksum |
| `__init__.py` ในแพ็กเกจ Python | ระบุโฟลเดอร์ให้ import เป็นแพ็กเกจ |
| `data/final/metadata.json` | Schema นโยบายคัด สรุป ผลตรวจ และที่มาชุดสุดท้าย |
| `models/asking_price_v2/model.joblib` | โมเดลใช้งานที่ฝึกครบ |
| `models/asking_price_v2/metadata.json` | Checksum เวอร์ชัน และบทบาท artifact |
| `models/*/evaluation.joblib` | โมเดลสำหรับประเมินย้อนหลัง แยกจากโมเดลใช้งาน |
| `archive/` | ข้อมูลและงานเก่าที่เก็บเป็นหลักฐาน |
| `requirements.txt`, `requirements-lock.txt` | รายการ dependencies และเวอร์ชันที่ตรงกับโมเดล |
| `.streamlit/config.toml` | ธีมและการตั้งค่าหน้าเว็บ |
| `.gitignore` | กำหนดไฟล์ที่เก็บในเครื่องและไฟล์ที่เผยแพร่ |
| `.gitattributes` | รักษารูปแบบไฟล์ โดยเฉพาะ byte ของ CSV |
