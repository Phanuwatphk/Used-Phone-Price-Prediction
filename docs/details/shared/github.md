# ไฟล์สำหรับ GitHub และก่อน commit

Repo รวมโค้ด เอกสาร รายงาน และ **ชุดสำหรับโมเดล 9,210 แถวที่ data/final/dataset.csv** ให้คน clone แล้วมีข้อมูลเริ่มขั้นแบ่งและฝึกได้ Raw และหลักฐานระหว่างทางสำรองแยกในเครื่อง

| เอาขึ้น GitHub | เก็บอะไร |
|---|---|
| `README.md`, `.gitignore`, `requirements*.txt` | คู่มือ กฎเลือกไฟล์ และ dependencies |
| `scraper/`, `preparation/`, `analysis/` | โค้ดเก็บ ตรวจ clean คัดชุด และ EDA |
| `script/` | คู่มือและ tests พร้อม fixtures |
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
| `.venv/`, cache, `.env*`, `.codex/`, `.aws/` | environment และไฟล์เฉพาะเครื่อง |

.gitignore เปิดเฉพาะไฟล์ 8 รายการที่ราก data/final ชุด 9,210 แถวไม่มี title/description/ข้อความติดต่อ เก็บ URL และรหัสสินค้าไว้เพื่อบอกที่มา ข้อมูลทุกเว็บยังมี source

## หลัง clone

ติดตั้งตาม README แล้วรัน:

```bash
python -B -m unittest discover -s script/tests -t .
```

อ่าน `data/final/dataset.csv` เป็นข้อมูลสำหรับขั้นแบ่งและเทรนได้เลย ยังไม่มีโมเดลหรือ split สำเร็จ การทำซ้ำตั้งแต่ raw,clean,EDA10,032 แถว หรือรัน select_model_input.py ใหม่ ต้องคืนข้อมูล input และ ledger จากสำเนาส่วนตัวตาม registry/policy hash การมีชุด 9,210 แถวใน repo ไม่ได้รวม HTML ต้นทางและคิวที่ตัด

รายงาน EDA เดิมสำรวจ 10,032 แถวก่อนเลือก อ่าน [สรุปชุดที่ใช้ต่อ](../../summary/model_input.md) และ [วิธีคัด](model_input.md) สำหรับผล 9,210 แถว

## ตรวจชุดที่จะ commit

```bash
git status --short
git diff --cached --stat
git diff --cached --check
```

ไฟล์เก่า descript.txt, script/descript.py และ script/download.py ย้ายเข้าประวัติก่อนหน้านี้แล้ว การลบยังอยู่ในชุด commit งานนี้เตรียมไฟล์และตรวจชุดส่งมอบ ไม่ได้ commit หรือ push แทนผู้ใช้
