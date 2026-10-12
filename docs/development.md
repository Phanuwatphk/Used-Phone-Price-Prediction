# คู่มือรันและพัฒนา

วิธีติดตั้งแบบสั้นอยู่ใน [README](../README.md) รายละเอียดการใช้งานและทำซ้ำทั้งหมดรวมอยู่ในไฟล์นี้

| หัวข้อ | อ่านอะไร |
|---|---|
| [เปิดเว็บและคำสั่งหลัก](#คำสั่งหลัก) | เปิด/หยุด เปลี่ยนพอร์ต เทรนและรันต่อ |
| [ตำแหน่งข้อมูล](#ข้อมูลอยู่ตรงไหน) | raw, intermediate, final, models และรายงาน |
| [Deploy Streamlit](#deploy) | ไฟล์ที่ต้อง commit, entry point และ Python |
| [CI และ tests](#ci-และ-tests) | ตรวจ locally/GitHub และสิ่งที่ workflow รัน |
| [ไฟล์ขึ้น GitHub](#ไฟล์ขึ้น-github) | ไฟล์ public และสิ่งที่เก็บในเครื่อง |
| [สคริปต์ทุกขั้น](#scripts) | แต่ละไฟล์ทำอะไร อ่าน/เขียนที่ไหน แยกเว็บ |
| [Config ทุกไฟล์](#config) | กฎ นโยบาย ledger และแผนทดลอง |
| [โมเดลในเครื่อง](#model-artifacts) · [งานย้อนหลัง](#archive) | บทบาท artifact และไฟล์เก่า |

ติดตั้งตาม [README](../README.md) ใช้ Python 3.12 กับ `requirements-lock.txt` คำสั่งต่อไปนี้รันจากรากโปรเจค

เว็บออนไลน์: **[Used Phone Price](https://secondhand-phone-price-prediction.streamlit.app/)** คำสั่ง localhost ด้านล่างใช้สำหรับพัฒนาบนเครื่องเท่านั้น

## คำสั่งหลัก

| คำสั่งหลัง .venv/bin/python | หน้าที่ / ผล |
|---|---|
| `app/run_app.py` | เปิดเว็บ localhost:8501 ผลทำนายแสดงบนหน้าจอ |
| `-B script/modeling/rebuild_features_v2.py` | core + sidecar → enriched CSV ใน intermediate ตรวจ hashes |
| `-u -B script/modeling/train_improved.py` | เลือก/ฝึก → models, ไฟล์ประกอบรายงานใน docs/assets/ และ predictions ใน intermediate |
| `-u -B script/modeling/train_improved.py --resume` | ใช้ผลตัวเลือกที่ทำครบแล้วต่อ เมื่อ config/hashes ตรง |
| `-B -m unittest discover -s script/tests -t .` | ตรวจ workflow offline ด้วย fixtures |

`app/app.py` เป็น entry point/ฟอร์ม; `dashboard.py` อ่าน dataset และรายงานเพื่อแสดงกราฟ/ตัวกรอง; `run_app.py` เปิดเซิร์ฟเวอร์ ตัวทำนายร่วมคือ `script/modeling/predict.py` ธีมอยู่ `.streamlit/config.toml`

หน้าเว็บใช้พื้นสว่างกับสีกรมท่า `#1E3A5F` ไม่มีอีโมจิ ข้อความรองใช้เทาเข้ม `#475569` แสดงเต็มความเข้ม (ยกเลิก opacity 60% ของ caption เดิม) และ placeholder เข้มขึ้นเพื่อให้อ่านง่าย Sidebar จัดชื่อ คำอธิบาย และเมนูไว้กลาง เมนูที่เลือกใช้พื้นกรมท่าตัวอักษรขาว ส่วนแสดงตัวเลขมีขอบเน้นสีกรมท่า เส้นแบ่งและขอบช่องกรอกเข้มขึ้น ยี่ห้อ/รุ่นและข้อมูลเพิ่มเติมเรียงสองช่องคู่กัน ความจุเป็น dropdown ที่เปลี่ยนตามยี่ห้อ/รุ่นและ reset เมื่อค่าที่เลือกไม่อยู่ในรุ่นใหม่ iPhone ใช้ความจุจาก Apple Support ใน `config/app/storage_options.json` ส่วนรุ่นอื่นใช้ค่าที่พบใน public clean dataset (`data/final/dataset.csv`) ช่องตัวเลขแบตเตอรี่/ประกันไม่มีปุ่มบวก/ลบและยังตรวจขอบเขต 0–100% / 0–999 วัน; optional ว่างคือไม่ทราบและ 0 คงเป็นศูนย์จริง แยกตัวกรองเป็นกรอบและตัวเลขสรุปเป็นการ์ด CSS ใน `apply_layout()` ของ app.py ปรับระยะห่าง/ขนาดสำหรับหน้าจอเล็ก โดยคง widgets และการใช้คีย์บอร์ด

ตัวเลือกความจุหน้าเว็บ: `config/app/storage_options.json` เก็บสเปก 54 รุ่น iPhone หน่วย GB พร้อม URL/วันที่ตรวจ/hash ของ [Apple Support](https://support.apple.com/en-us/108044) ส่วน `storage_catalog()` ใน `app/app.py` อ่าน public dataset แล้วให้ค่าผู้ผลิตแทนค่าประกาศที่อาจผิด ใช้ cache ตามเวลาแก้ไขไฟล์ ไม่ส่ง request ไปเว็บระหว่างใช้งาน

ฟอร์มกรอกยี่ห้อ รุ่น ความจุ วันที่ แบตเตอรี่ ประกัน และกล่องครบแล้ว ข้อมูลที่เหลือ เช่นอายุรุ่น กลุ่มรุ่นและ missing indicators คำนวณให้ ไม่มี feature ความเสียหาย/รอยตำหนิ/ประวัติซ่อมในโมเดลที่ฝึก จึงไม่รับประเมินเครื่องเสีย จอแตก ล็อก หรือขายเป็นอะไหล่

ฟอร์มประเมินไม่ให้เลือกเว็บต้นทางหรือสภาพ และไม่แสดงเว็บในข้อความผลลัพธ์ ใช้ `source=mac2hand` และ `condition=used` คงที่ตามค่าเริ่มต้นเดิม เพราะโมเดล V2 ที่ฝึกแล้วมีสอง features นี้อยู่ การซ่อนช่องไม่ใช่การนำ features ออกจากโมเดล หากต้องการให้โมเดลไม่ใช้สองค่านี้ ต้องฝึกและประเมินรอบใหม่ ส่วนหน้าสำรวจยังกรองเว็บ/สภาพของ dataset ได้ตามเดิม

กราฟสำรวจใน `dashboard.py` ใช้ Altair สีกรมท่าและข้อความแกนเทาเข้ม: แกนจำนวนประกาศและราคามัธยฐานเริ่มที่ 0 เสมอ ขอบบนปรับตามข้อมูลที่กรองพร้อมพื้นที่เหนือค่าสูงสุด 12% ไม่เปิดการลากเปลี่ยนสเกล เรียงยี่ห้อตามจำนวนจากมากไปน้อย ปีแสดงเป็นจำนวนเต็มและ tooltip ระบุหน่วยชัดเจน การตั้งแกนนี้ใช้กับกราฟสำรวจสองกราฟ; กราฟ error ในรายงานโมเดลคงค่าคลาดเคลื่อนบวก/ลบตามจริง

แอปอ่าน `data/final/dataset.csv`, `docs/assets/modeling/` และโมเดลใน `models/asking_price_v2/` ดาวน์โหลด CSV ตามตัวกรองได้ แต่ไม่เขียนทับ dataset ไม่ scrape/เทรนเอง

กด `Ctrl+C` เพื่อหยุด ใช้ `--port 8502` เมื่อพอร์ตไม่ว่าง หรือ `--headless` ไม่เปิด browser อัตโนมัติ CLI รองรับ absolute path จาก directory อื่น Path ภายในอิงตำแหน่งไฟล์

<a id="deploy"></a>

## Deploy บน Streamlit Community Cloud

ปัญหาเดิม: `.gitignore` กัน models ทั้งหมด ทำให้ server ไม่มี model.joblib/metadata.json แม้หน้าเว็บเปิดได้ และ requirements.txt เดิมไม่ตรึงเวอร์ชันของ scikit-learn ที่ใช้โหลด artifact

| ต้องส่งขึ้น Git | หน้าที่ |
|---|---|
| `models/asking_price_v2/model.joblib` | โมเดลใช้งานที่ฝึกครบ 9,210 แถว ขนาดประมาณ 1 MB |
| `models/asking_price_v2/metadata.json` | checksum, เวอร์ชันไลบรารี และสัญญา features ของโมเดล |
| `requirements.txt` + `requirements-lock.txt` | Cloud อ่าน requirements.txt ซึ่งอ้าง lock ให้ติดตั้งเวอร์ชันเดียวกับการฝึก |
| `app/`, `script/`, `config/`, `data/final/` และ `docs/` ตาม whitelist | โค้ด หน้าเว็บ ข้อมูลสำรวจ และรายงานที่ใช้งาน |

หาก deploy ไว้แล้วด้วย path เดิม `script/app/app.py` ให้เปลี่ยน Main file path ใน Settings เป็น `app/app.py` หลัง push การย้ายไฟล์ ไม่ต้องสร้างแอปใหม่

1. Commit/push การแก้ไขพร้อมไฟล์โมเดลสองไฟล์ (ไม่ต้องใช้ git add -f เพราะ whitelist แล้ว)
2. เลือก repository/branch ที่มี commit นี้ และ Main file path เป็น `app/app.py`
3. ตั้ง Python 3.12 ใน Advanced settings ให้ตรง environment ที่ฝึก ถ้าแอปเดิมใช้ Python รุ่นอื่น ให้ deploy ใหม่ด้วยรุ่นนี้
4. รอ build dependencies และเปิดประเมินราคา แอปอ่านโมเดลที่ฝึกแล้ว ไม่เทรนใหม่บน Cloud

หากแอปยังใช้ commit เก่า ให้ตรวจ branch/commit ใน Manage app และ reboot หลัง push ถ้าล้มเหลวให้ดู logs: FileNotFoundError ตรวจสองไฟล์โมเดล; checksum mismatch ต้องส่ง model กับ metadata จากรอบเดียวกัน; sklearn/import error ตรวจ Python และการติดตั้ง lock การแก้ในเครื่องยังไม่ใช่การอัปเดต server จนกว่า commit จะถูก push

ตรวจไฟล์ก่อน commit ด้วย `git status --short --untracked-files=all models` และ `git ls-files -co --exclude-standard models/asking_price_v2/` ต้องเห็น model.joblib กับ metadata.json; evaluation.joblib ยังถูก ignore การโหลดไฟล์ของโปรเจคยังตรวจ SHA-256 ตามเดิม

อ้างอิง [การจัด dependencies ของ Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) และ [การเลือก entry point/Python](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

`script/artifacts.py` อ่าน/เขียน metadata รวม ใช้ร่วมทั้งสองเว็บและงาน EDA/โมเดล รองรับอ่าน snapshot รูปแบบเดิม และตรวจ checksum ของแต่ละส่วนได้ `script/tests/test_artifacts.py` ตรวจการเก็บหลักฐาน byte เดิม การแทนที่ และการไม่ hash อ้างตัวเอง

## ข้อมูลอยู่ตรงไหน

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

## CI และ tests

ใช้ **workflow เดียว** `.github/workflows/ci.yml` ชื่อ **CI** ติดตั้งผ่าน requirements.txt/lock แบบเดียวกับ deploy แล้วตรวจ dependencies → compile Python → rebuild input จากข้อมูล public → unittest ทั้งหมด รวม Streamlit AppTest รวมการตรวจเอกสาร/registry/checksum รายงาน รันเมื่อ push/PR เข้า `main` หรือกด Actions → CI → Run workflow

`script/tests/` เป็นโค้ดทดสอบ ส่วน CI เรียกการตรวจอัตโนมัติ จึงไม่เปลี่ยนชื่อโฟลเดอร์ tests และไม่สร้าง workflow ซ้ำ ไม่ scrape หรือเทรนจริงใน CI Tests ใช้ fixtures และไฟล์ public ของโปรเจค รวมโมเดลใช้งานที่ส่งขึ้น Git ไม่ต้องมี raw, ledger หรือ binary ของโมเดลทดลอง

ตรวจ locally ด้วยคำสั่งเดียวกับ CI:

```bash
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q app script
.venv/bin/python -B script/modeling/rebuild_features_v2.py
.venv/bin/python -B -m unittest discover -s script/tests -t .
```

## ไฟล์ขึ้น GitHub

รวมโค้ด config/แม่แบบ ledger, เอกสาร รายงานผลรวม requirements/lock, workflow, ธีม ชุด final หลักพร้อม sidecar/ไฟล์กำกับ และโมเดลใช้งาน V2 กับ metadata ตาม `.gitignore`

`.gitattributes` ปิดการแปลง line endings ของ CSV (`-text`) เพื่อรักษา byte/checksum ของ dataset และรายงาน แม้เครื่องที่ commit ตั้ง core.autocrlf ไว้

เก็บ raw/intermediate, ledger จริง, evaluation/V1 binary, `.venv`, `.env` และ `.streamlit/secrets.toml` ในเครื่อง หลัง clone ใช้โมเดลที่รวมใน Git ได้ทันที หรือสร้าง V2 ใหม่จาก core + sidecar ได้โดยไม่ต้องมี raw ส่วนทำซ้ำ scraping/clean/EDA เดิมต้องคืนหลักฐาน private ก่อน ไม่มี deploy อัตโนมัติใน workflow นี้

คำสั่งและหน้าที่ไฟล์ทุกขั้นอ่าน [คู่มือสคริปต์](#scripts); กฎแยกเว็บอ่าน [คู่มือ config](#config) แนวทาง CI: [GitHub Actions](https://docs.github.com/en/actions/get-started/understand-github-actions) รูปแบบ dashboard อ้างอิง [Gaming Statistics Dashboard](https://github.com/Phanuwatphk/Gaming-Statistics-Dashboard)

ผลตรวจล่าสุด: 167 tests ผ่าน ทั้ง workspace และสำเนา public ที่มีเฉพาะโมเดลใช้งาน ไม่มี raw/intermediate หรือโมเดล evaluation; เปิดทั้ง 3 หน้าเว็บจาก directory อื่นได้ รวม process ใหม่ที่ยังไม่ import app มาก่อน; entry point จัดรากโปรเจคไว้ก่อน directory ของ app.py เพื่อไม่ให้ชื่อไฟล์บังแพ็กเกจ ตรวจลิงก์เอกสารและ checksum ข้อมูลหลักผ่าน คำสั่ง CLI 24 ตัวเปิด --help จาก /tmp ได้ ผล GitHub Actions ต้องดูหลัง push/PR จริง

<a id="model-artifacts"></a>

## ไฟล์โมเดลในเครื่อง

| ไฟล์ใน models/asking_price_v2/ | เก็บอะไร |
|---|---|
| `model.joblib` | โมเดลใช้งาน ฝึกครบ 9,210 แถว / 300 รุ่น ถึง 2026-10-06 ไม่มีคะแนนทดสอบอิสระ |
| `evaluation.joblib` | fit 8,517 แถวก่อน cutoff สำหรับผลย้อนหลังบน test เดิม 693 แถว |
| `metadata.json` | input/code/catalog/model hashes, versions และบทบาทของแต่ละ artifact |

V1 ใน `models/asking_price_v1/` และ evaluation.joblib เป็นประวัติในเครื่อง เฉพาะ V2 model.joblib กับ metadata.json รวมใน Git สำหรับ deploy; ฝึกใหม่ได้จาก core + public condition sidecar โหลดผ่าน `script/modeling/predict.py` เพื่อเช็ค checksum และ feature contract ของ V1/V2 ไม่เปิด joblib จากแหล่งที่ไม่เชื่อถือ ผล/ข้อจำกัดอ่าน [รายงานโมเดล](modeling.md)

รอบปรับปรุง 2026-10-12 ใช้ `train_improved.py` ตัวเดียว:

| ไฟล์ | หน้าที่ |
|---|---|
| `config/modeling/current.json` | แผนโมเดลใช้งานปัจจุบัน; ผล docs/assets/modeling/ และ models/asking_price_v2/ |
| `config/modeling/experiments.json` | เก็บ baseline/revision/age_transfer/ensemble ครบในไฟล์เดียว |
| `script/modeling/trend.py` | estimator สำหรับ trend, age normalization และ ensemble; ไม่รันแยก |
| `docs/assets/modeling/history.zip` | รายงาน กราฟ ตาราง และ config ของ 4 รอบเดิม เปิดอ่านโดยแตก ZIP |

ทำซ้ำ V2 กลุ่มทดลองด้วย `train_improved.py --experiment revision` (หรือ `age_transfer`, `ensemble`) และเพิ่ม `--resume` เมื่อ input/config เดิม ผลใหม่อยู่ `data/intermediate/modeling/<run>/report/` เพื่อเก็บประวัติเดิมใน ZIP; baseline ใช้ `train_models.py` ตามแผน baseline ใน experiments.json แต่ละผลมี metadata.json รวม summary/config/folds/selection/provenance/validation/hashes ส่วน CSV/กราฟยังแยกตามรูปแบบการใช้งาน

ผล 33 ตัวเลือกอยู่ `docs/assets/modeling/metadata.json#tuning_review` กับ `tables/tuning_validation.csv` อ่านคำอธิบายใน [รายงานโมเดล](modeling.md#10-รอบปรับปรุง-2026-10-12) สำรองก่อนปรับอยู่ `archive/modeling/before_tuning_20261012/` การฝึกหลักเลือกด้วย validation แล้ว refit evaluation/operational ไม่ใช้ราคา test เป็น feature

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

รวมคำสั่งและหน้าที่ไฟล์ทุกขั้นไว้ที่นี่ เลือกอ่านเฉพาะงานที่ต้องทำจากตารางด้านล่าง คำสั่งใช้ Python ใน `.venv` และรันจากรากโปรเจค; CLI รองรับ absolute path จาก directory อื่นด้วย

| งาน | ใช้กับ | อ่าน / เขียนที่ไหน |
|---|---|---|
| [เปิดเว็บ](#scripts-app) | ชุดรวม | อ่าน final + โมเดล + รายงาน; แสดงผล/ดาวน์โหลด CSV |
| [เก็บข้อมูล](#scripts-scraper) | แยก ENNXO / Mac2Hand | เว็บ → data/raw/ |
| [เตรียมข้อมูล](#scripts-preparation) | แยกเว็บและ shared | raw → intermediate → final |
| [EDA](#scripts-analysis) | ทั้งสองเว็บ | ชุดก่อนคัด → docs/eda.md และ assets; คิวใน intermediate |
| [โมเดล](#scripts-modeling) | ทั้งสองเว็บ | final → features/split/predictions, models และรายงาน |
| [Tests](#scripts-tests) | ทุกขั้น | ใช้ fixtures แบบ offline |

กฎอยู่ใน [คู่มือ config](#config) วิธีติดตั้งและ CI อยู่ใน [คู่มือพัฒนา](development.md) ผล EDA/โมเดลอ่านในรายงานหลักที่ [README โครงการ](../README.md#เอกสาร)

<a id="scripts-app"></a>

<a id="scripts-เปิดเว็บ"></a>

### เปิดเว็บ

รัน `.venv/bin/python -m streamlit run app/app.py` จากรากโปรเจค แล้วเข้า **http://localhost:8501** มีเมนูประเมินราคา สำรวจข้อมูล และผลโมเดล กด `Ctrl+C` เพื่อหยุด ตัวช่วยเปิดจาก directory อื่นคือ `run_app.py` รองรับ `--port 8502` และ `--headless`

| ไฟล์ใน app/ | หน้าที่ |
|---|---|
| `app.py` | entry point, เมนู และฟอร์มประเมินราคา |
| `dashboard.py` | ตัวกรอง กราฟ ตาราง/download CSV และผลโมเดล |
| `run_app.py` | เปิด local server รองรับ directory อื่น |

ธีม สี และการปิด usage statistics อยู่ใน `.streamlit/config.toml` ที่รากโปรเจค

หลัง clone เปิดสำรวจ รายงาน และประเมินจากโมเดลที่รวมใน Git ได้ทันที โหลดเฉพาะ model.joblib/metadata ของโปรเจคที่ตรวจ checksum แล้วใน `models/asking_price_v2/` ไม่เปิด joblib จากแหล่งที่ไม่เชื่อถือ

ทดสอบ `.venv/bin/python -m unittest script.tests.test_app` ใช้โมเดล/ข้อมูล fixture ตั้ง `PHONE_PRICE_MODEL_PATH` หรือ `PHONE_PRICE_DATASET_PATH` เพื่อเลือก input อื่นได้ Relative path อิงรากโปรเจค

อ่าน [วิธีดำเนินงาน](data.md#workflow) และ [ผล/ข้อจำกัด](../README.md#เอกสาร) แนวเมนู/ตัวกรองอ้างอิง [Gaming Statistics Dashboard](https://github.com/Phanuwatphk/Gaming-Statistics-Dashboard) ใช้ [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest) ตรวจฟอร์ม

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

คำสั่งอ่านสถานะ Mac2Hand จากรากโปรเจค:

```bash
.venv/bin/python -B script/scraper/mac2hand/monitor_mac2hand.py
```

คำสั่งเก็บใหม่/รันต่อส่ง request ไปเว็บ ให้เลือก snapshot ก่อนรัน ดู `--help` และคู่มือเว็บนั้น ปัจจุบัน snapshot ทั้งสองเว็บเก็บจบแล้ว การจัดโครงสร้างไม่ได้เริ่มการ scrape ใหม่ รองรับรันไฟล์ผ่าน absolute path จาก directory อื่น และ `python -m script.scraper.<เว็บ>.<โมดูล>` จากรากโปรเจค

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
| `ennxo/export_ennxo_dataset.py` | ENNXO | clean → ตรวจ accepted.csv เทียบ JSONL แล้วคัดลอก CSV ทุก byte | `data/intermediate/ennxo/<รอบ>/` |
| `mac2hand/prepare_mac2hand.py` | Mac2Hand | raw → ตรวจ manifest/hash และ parse HTML | `data/intermediate/mac2hand/<รอบ>/{raw_audit,extraction}/` |
| `mac2hand/clean_mac2hand.py` | Mac2Hand | extraction + กฎ → ตรวจและแยกสถานะ | `.../clean/` |
| `mac2hand/review_mac2hand_queue.py` | Mac2Hand | clean + ledger → ตรวจคำแก้และจัดคิว | `.../manual_review/` |
| `mac2hand/finalize_mac2hand.py` | Mac2Hand | ผล review + กฎ → ส่งมอบกลุ่มผ่านและแยกปัญหาทุกแถว | `data/intermediate/mac2hand/<รอบ>/` และ `data/intermediate/mac2hand/<รอบ>/finalization/` |
| `shared/select_model_input.py` | ทั้งสองเว็บ | ชุดรวม + คิวEDA + นโยบาย → ตัดunion822รหัส | `data/final/` และ `data/intermediate/model_input/<รอบ>/` |
| `shared/prepare_combined_dataset.py` | ทั้งสองเว็บ | อ่าน CSV ผ่านจาก registry → ตรวจรายเว็บ ปรับ schema รวม พร้อม source | `data/intermediate/combined/<รอบ>/before_selection/` และ `data/intermediate/combined/<รอบ>/audit/` |

โมดูลประกอบ: ENNXO `cleaning_rules.py` เก็บกฎตรวจฟิลด์, `description_sections.py` แยกส่วนรายละเอียด; Mac2Hand `resolution_rules.py` เก็บกฎตรวจหลักฐานขั้นส่งมอบ โมดูลเหล่านี้ไม่รันแยก

คำสั่งช่วงส่งมอบและรวมจากรากโปรเจค:

```bash
.venv/bin/python -B script/preparation/ennxo/export_ennxo_dataset.py
.venv/bin/python -B script/preparation/mac2hand/finalize_mac2hand.py
.venv/bin/python -B script/preparation/shared/prepare_combined_dataset.py
```

การทำซ้ำ snapshot เดิมต้องมีข้อมูลและ ledger ตรงรอบ คำสั่งสร้างผลใหม่ในปลายทางที่กำหนด ไม่จำเป็นต้องรันขั้นก่อนหน้าซ้ำเพื่ออ่าน dataset ที่เสร็จแล้ว `--output` เลือกปลายทาง final; Mac2Hand ใช้ `--review-output` แยกหลักฐาน, ตัวรวมใช้ `--audit-output` แยก lineage/audit เมื่อลองรันให้กำหนดปลายทางทั้งสองเพื่อไม่ทับผลปัจจุบัน API เดิมที่ไม่ส่งปลายทางเสริมยังสร้าง bundle ใน output เดียวได้

รองรับรันไฟล์ผ่าน absolute path จาก directory อื่น และ `python -m script.preparation.<เว็บหรือshared>.<โมดูล>` จากรากโปรเจค ดู [ENNXO](data.md#ennxo-stage-methodology), [Mac2Hand](data.md#mac2hand-stage-cleaning), [ชุดรวม](data.md#stage-combined_dataset) และ [คู่มือไฟล์](data.md#stage-data_guide)

ขั้นคัดชุดโมเดล: `.venv/bin/python -B script/preparation/shared/select_model_input.py` อ่าน [วิธีทำและทุกไฟล์](data.md#stage-model_input) ผล9,210แถวก่อน split; ขั้นแบ่งและเทรนอยู่ [ขั้นโมเดล](#scripts-modeling)

<a id="scripts-analysis"></a>

<a id="scripts-วิเคราะห์-eda"></a>

### วิเคราะห์ EDA

โค้ดวิเคราะห์แยกจากการเก็บและเตรียมข้อมูล ปัจจุบันมีขั้น EDA ใน `eda/` ขั้นฝึกโมเดลแยกไว้ใน [ขั้นโมเดล](#scripts-modeling)

| ไฟล์ใน analysis/ | ใช้กับ / หน้าที่ |
|---|---|
| `eda/run_eda.py` | ชุดรวมทั้งสองเว็บ ตรวจ CSV/JSONL/lineage แล้วสร้างรายงานและคิวตรวจ |
| `eda/eda_statistics.py` | สถิติ IQR รายกลุ่ม candidate ซ้ำ Spearman และ sensitivity; ไม่รันแยก |
| `eda/eda_plots.py` | สร้างกราฟ PNG/SVG แบบ offline; ไม่รันแยก |

```bash
.venv/bin/python -B script/analysis/eda/run_eda.py
```

อ่าน dataset จาก `data/intermediate/combined/<รอบ>/before_selection/`, lineage/audit จาก `data/intermediate/combined/<รอบ>/audit/` และข้อความเต็มจาก `data/intermediate/mac2hand/<รอบ>/finalization/mac2hand_final.jsonl` ตรวจข้อความให้ตรงค่าต้นทางก่อนใช้ กฎอยู่ที่ `config/shared/eda_rules.json`

รายงานหลักอยู่ใน `docs/eda.md`; ไฟล์ประกอบอยู่ใน `docs/assets/eda/<รอบ>/`: summary JSON, HTML, `figures/` และ `tables/` คิวรายแถวและ URL อยู่ใน `data/intermediate/eda/<รอบ>/` สคริปต์ไม่แก้ dataset

รองรับรันจาก directory อื่นด้วย absolute path และ `python -m script.analysis.eda.run_eda` จากรากโปรเจค ปรับ `--input`, `--evidence`, `--mac2hand-details`, `--report`, `--private-output` เพื่อเลือกข้อมูลเข้าและผลทดลอง `--without-mac2hand-details` ใช้ข้อความจาก CSV เท่านั้นและระบุความครอบคลุมที่ลดลง ใช้ Python 3.12+ ตาม lock การสร้างรายงานหลักซ้ำคงส่วนวิธีทำใต้ anchor `stage-eda` ไว้ อ่าน [หลักเกณฑ์และทุกไฟล์ EDA](eda.md#stage-eda)

เมื่อใช้ปลายทางทดลองแบบเดิมและไม่ส่ง option ปลายทางเสริม CLI ยังรองรับ bundle ใน output/input เดียว ค่าเริ่มต้นของ snapshot ปัจจุบันแยกขั้นตาม registry

<a id="scripts-modeling"></a>

<a id="scripts-ฝึกและใช้โมเดล"></a>

### ฝึกและใช้โมเดล

วิธีคัดข้อมูล features แบ่ง/เทรน ตัววัด ผล กราฟ และหน้าที่ทุกไฟล์ อ่าน [รายงานโมเดล V2 ไฟล์เดียว](modeling.md)

```bash
.venv/bin/python -u -B script/modeling/train_improved.py
.venv/bin/python -u -B script/modeling/train_improved.py --resume
.venv/bin/python -B script/modeling/predict.py --source mac2hand --brand Apple --model 'iPhone 13' --storage-gb 128 --condition used --published-at 2026-10-06
```

`report_improved.py` สร้างรายงาน/กราฟใหม่จากผลที่บันทึกไว้โดยไม่เทรน ใช้ prediction ใน intermediate ที่อยู่ในเครื่อง `train_models.py` และ `report.py` เก็บไว้ทำซ้ำ V1 สำหรับประวัติ; predict รองรับ --model-file ของทั้ง V1/V2

<a id="scripts-tests"></a>

<a id="scripts-ทดสอบ-workflow"></a>

### ทดสอบ workflow

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

`test_modeling.py` ตรวจ split ตามวัน ไม่ใช้ target/ID เป็น feature, encoder ไม่ฟิตกับ validation, input/hash และปลายทางที่ห้ามทับ, หน่วย metric, workflow fixture และ model roundtrip พร้อม test แยกจาก fit

`test_modeling_improved.py` ตรวจ explicit/ambiguous description claims, อายุจาก frozen catalog, missing/unknown model inference, train-only recency weights, การตั้ง loss/พารามิเตอร์, CatBoost clone, การทำนาย/serialization ของ trend และ ensemble

`test_app.py` ตรวจโมเดลที่ส่งไป deploy จาก checkout แยก การตรึง dependencies ให้ตรง artifact และฟอร์มภาษาไทย การเลือกรุ่นตามยี่ห้อ unknown/ศูนย์/วันที่ และค่าคงที่ source=mac2hand, condition=used dropdown ความจุตามรุ่นและค่าที่ส่งเข้า inference ตัวกรอง/empty state การไม่เปลี่ยน dataset การเปิดหน้าสำรวจ/ผลโมเดลโดยไม่มี binary และตัวเปิดจาก directory อื่น ใช้ fixture ชั่วคราว ไม่ต้องมี binary ส่วนตัว CI เรียก tests เหล่านี้ผ่าน `.github/workflows/ci.yml`

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

<a id="config-สิ่งที่ขึ้น-git-และสิ่งที่ต้องคืนหลัง-clone"></a>

### สิ่งที่ขึ้น Git และสิ่งที่ต้องคืนหลัง clone

เก็บกฎ catalog และ `*.example.json` เป็นแม่แบบใน Git ส่วน ledger จริง `ennxo/corrections.json`, `ennxo/manual_review.json`, `mac2hand/manual_reviews.json` ถูก ignore เพราะมีหลักฐานรายประกาศ การทำซ้ำ snapshot เดิมต้องคืน ledger และข้อมูลตรงรอบ ห้ามใช้แม่แบบว่างแทน ledger เดิม อ่าน [วิธีทำซ้ำและ GitHub](development.md)

รูปแบบผลปัจจุบัน: แต่ละโฟลเดอร์ใช้ `metadata.json` รวมข้อมูลกำกับ ส่วน `metadata.json#summary` หมายถึง key summary ใน JSON ไม่ใช่ไฟล์อีกไฟล์ ชื่อไฟล์กำกับเดิมในประวัติ/raw คงเดิมเพื่อรักษาหลักฐาน; registry `data/datasets.json` ระบุตำแหน่งปัจจุบัน รายงาน EDA อยู่ `docs/eda.md` และโมเดลอยู่ `docs/modeling.md` ผลประกอบใน `docs/assets/eda/` และ `docs/assets/modeling/` ไม่มีชั้นชื่อรอบปัจจุบันซ้ำ รายงานโมเดลเดิม 4 รอบอยู่ history.zip สำรองก่อนลดไฟล์ทั้งโครงการอยู่ `archive/structure_before_simplification_20261012.zip` (เฉพาะในเครื่อง)
