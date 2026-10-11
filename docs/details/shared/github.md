# ไฟล์สำหรับ GitHub และก่อน commit

Repo รวมโค้ด เอกสาร รายงาน และ **ชุดสำหรับโมเดล 9,210 แถวที่ data/final/dataset.csv** ให้คน clone แล้วมีข้อมูลเริ่มขั้นแบ่งและฝึกได้ Raw และหลักฐานระหว่างทางสำรองแยกในเครื่อง

| เอาขึ้น GitHub | เก็บอะไร |
|---|---|
| `README.md`, `.gitignore`, `requirements*.txt` | คู่มือ กฎเลือกไฟล์ และ dependencies |
| `script/scraper/`, `script/preparation/`, `script/analysis/` | โค้ดเก็บ ตรวจ clean คัดชุด และ EDA |
| `script/` | คู่มือและ tests พร้อม fixtures |
| `script/app/` | หน้าฟอร์มภาษาไทยและตัวเปิดแอป อ่านโมเดลในเครื่อง |
| `config/` ยกเว้น ledger จริง | กฎ schema นโยบายคัด และแม่แบบ ledger |
| `docs/`, `reports/` | สรุป คู่มือ รายงาน EDA กราฟและตารางรวม |
| `data/README.md`, `data/datasets.json` | คู่มือและบัญชีชุดปัจจุบัน |
| `data/final/dataset.csv`, `dataset.jsonl` | ชุด 9,210 แถวเดียวกัน ใน CSV และ JSON แบบระบุชนิด |
| `data/final/schema.json`, `policy.json` | schema และนโยบายที่ใช้เลือก |
| `data/final/summary.json`, `report.md`, `validation.json`, `run_metadata.json` | ผลเลือก จำนวน ผลตรวจ และ hash สำหรับทำซ้ำ |
| `archive/README.md`, `.github/workflows/tests.yml` | คำอธิบายงานเก่าและ CI |

| เก็บในเครื่อง ไม่ใส่ Git | เก็บอะไร |
|---|---|
| `data/raw/`, `data/intermediate/` | HTML บัญชีประกาศ log หลักฐาน และ 822 แถวที่ตัด |
| `data/final/ennxo/`, `data/final/mac2hand/` | ชุดผ่านเฉพาะเว็บก่อนคัด สำหรับสำรอง |
| `config/ennxo/{corrections,manual_review}.json`, `config/mac2hand/manual_reviews.json` | ledger จริงที่มีข้อความหลักฐานรายประกาศ |
| `archive/` ยกเว้น README | งานเก่าและการทดลอง |
| `models/<รอบ>/` | model.joblib/model.cbm และ metadata สร้างใหม่จากสคริปต์ |
| `.venv/`, cache, `.env*`, `.codex/`, `.aws/` | environment และไฟล์เฉพาะเครื่อง |

.gitignore เปิดไฟล์หลัก 8 รายการและ condition sidecarที่ราก data/final ชุด 9,210 แถวไม่มี title/description/ข้อความติดต่อ เก็บ URL และรหัสสินค้าไว้เพื่อบอกที่มา ข้อมูลทุกเว็บยังมี source

## หลัง clone

ติดตั้งตาม README แล้วรัน:

```bash
python -B -m unittest discover -s script/tests -t .
```

อ่าน `data/final/dataset.csv` เป็นข้อมูลสำหรับขั้นแบ่งและเทรนได้เลย เทรนแล้วและมีรายงานผลใน repo; หลัง clone รัน `python -u -B script/modeling/train_improved.py` เพื่อสร้าง split และโมเดลในเครื่องใหม่ การทำซ้ำตั้งแต่ raw,clean,EDA10,032 แถว หรือรัน select_model_input.py ใหม่ ต้องคืนข้อมูล input และ ledger จากสำเนาส่วนตัวตาม registry/policy hash การมีชุด 9,210 แถวใน repo ไม่ได้รวม HTML ต้นทางและคิวที่ตัด

รายงาน EDA เดิมสำรวจ 10,032 แถวก่อนเลือก อ่าน [สรุปชุดที่ใช้ต่อ](../../summary/model_input.md) และ [วิธีคัด](model_input.md) สำหรับผล 9,210 แถว

## ตรวจชุดที่จะ commit

```bash
git status --short
git diff --cached --stat
git diff --cached --check
```

ไฟล์เก่า descript.txt, script/descript.py และ script/download.py ย้ายเข้าประวัติก่อนหน้านี้แล้ว การลบยังอยู่ในชุด commit งานนี้เตรียมไฟล์และตรวจชุดส่งมอบ ไม่ได้ commit หรือ push แทนผู้ใช้

รายงานโมเดล/config/กราฟ/ตารางรวมใส่ Git; split และผลทำนายรายแถวอยู่ intermediate และไม่ใส่ Git โมเดล binary ถูก ignore เหลือ `models/README.md` ไว้อธิบาย ชุด data/final ยังคงมี 9,210 แถวครบ ไม่เปลี่ยนเป็น train อย่างเดียว

เพิ่ม `data/final/condition_features.csv` เป็นตารางตัวเลข/รหัสสำหรับสร้าง enriched input V2 หลัง clone โดยไม่ต้องคืน raw/private evidence ไม่รวมข้อความต้นทาง เงื่อนไข data/final อื่นยังถูก ignore โมเดลใช้งานฝึกครบและไม่มีคะแนน test อิสระ; รายงานย้อนหลังระบุบทบาทไว้ชัด

เมื่อคืนหรือเทรนโมเดลแล้ว เปิดฟอร์มด้วย `python script/app/run_app.py` ดู [คู่มือและรายการไฟล์](../../../script/app/README.md) `streamlit` รวมใน requirements และ lock แล้ว tests ฟอร์มใช้ fixture จึงรัน CI ได้โดยไม่ต้องนำ model binary ขึ้น Git
