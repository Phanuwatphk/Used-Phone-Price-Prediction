# ข้อมูลดิบและฟิลด์หลัก

เก็บค่าต้นฉบับผู้ขายไว้ก่อน ยังไม่ถือว่าเป็นข้อมูลที่ตรวจถูกต้องแล้ว JSONL อ่านทีละบรรทัดด้วย JSON decoder ข้อความภายในอาจมีอักขระแบ่งบรรทัด Unicode

## ENNXO — listings.jsonl

| ฟิลด์ | ความหมาย |
|---|---|
| `name` | ชื่อประกาศ |
| `brand`, `model`, `storage` | ค่าจากการ์ดสินค้า; ยังไม่แก้ข้อขัดแย้ง |
| `price`, `currency` | ราคาประกาศและสกุลเงิน |
| `location` | จังหวัด/สถานที่จากการ์ด |
| `url`, `image_url` | URL สินค้าและรูป |
| `source` | ennxo |
| `listing_page_url`, `page` | หน้ารวมที่พบ |
| `scraped_at`, `timezone` | เวลาเก็บและเขตเวลา |

รายละเอียดที่ฝังใน HTML หน้ารวมและหน้าสินค้าบางส่วนยังอยู่ใน raw ต้องตรวจการ parse ใหม่ ดู [คู่มือ raw](../ennxo/raw.md)

## ENNXO — ผลถอดข้อมูลขั้นที่ 2

`ennxo_extracted.jsonl` แยก `raw_listing`, `card`, `embedded_product`, `observations`, `provenance` พร้อม `url`, `product_id`, `source` ดู [ฟิลด์และหลักฐานทั้งหมด](../ennxo/extraction.md#เก็บอะไรในแต่ละแถว) ยังไม่มีค่า final หรือการรับเข้า/ตัดออก

## ENNXO — ผล clean ขั้นที่ 3

`ennxo_cleaned.jsonl` เก็บทุกสถานะโดยมี:

| กลุ่ม | เนื้อหา |
|---|---|
| `url`, `product_id`, `source` | ตัวระบุประกาศ |
| `clean` | brand, model, storage_gb, condition, price_thb, published_at |
| `status`, `hold_reasons`, `exclusion_reasons`, `notes` | ผลกฎ เหตุผลที่ค้าง เหตุผลนอกขอบเขต และวิธีอ่านค่า |
| `evidence`, `input_sha256` | ค่าช่องเลือก ข้อความที่กฎอ่านได้ และ hash ของ extraction แถวนั้น |
| `original` | extraction เดิมทั้งหมด รวม raw_listing, card, embedded_product และ provenance |
| `candidate_image_group` | key ของภาพ URL เดียวกัน; ยังไม่ยืนยันเครื่องซ้ำ |
| `review_correction` | มีเฉพาะแถวที่นำคำแก้จาก ledger มาใช้ |

ผลตรวจคิวเดิม126รายการเก็บแยกใน `data/intermediate/ennxo/<รอบ>/manual_review/` โดยมี `disposition` แยกผ่าน/แยกออก/เครื่องเสีย/รอหลักฐาน ไม่ใช่คอลัมน์ฟีเจอร์ของโมเดล ดู [ผลตรวจรายรายการ](../ennxo/review.md)

CSV แยกสามสถานะเพื่ออ่านคิวและเปรียบเทียบ ยังไม่ใช้ description เป็นฟีเจอร์ฝึกโดยตรง ดู [กฎและคำแก้](../ennxo/cleaning.md)

กฎเวอร์ชัน 2 รับทั้ง new/used และ `clean.condition` ยังคงเป็นช่องสภาพที่ผู้ขายระบุ ไม่ใช่สภาพจริงที่ผู้ตรวจรับรอง ข้อความขัดกันเก็บเป็น note พร้อมหลักฐาน

## Mac2Hand

`listings.jsonl` เก็บ `product_id`, `url`, `listing_url`, `name`, `subtitle`, `badges`, `price_raw`, `price`, `published_date`, `image_url`, `card_text`, `source`, `currency`, `scraped_at`, `timezone`, `page` และ `listing_page_url`

`details/manifest.json` จับคู่รหัสประกาศกับ HTML ผลการเก็บ เวลาเก็บ และข้อผิดพลาด แต่ละหน้าเก็บต้นฉบับที่ `details/product_<id>.html` สเปคและข้อความผู้ขายต้องอ่านจากหน้าที่ตรงรหัสประกาศ

`collection_progress.json` มี `cached`, `ok`, `failed`, `total`, `updated_at`, `status`, `collector_pid`, `wrapper_pid` และ `mode=raw_collection_only` cached รวมทั้งหน้าสำเร็จและล้มเหลว ไม่ใช่จำนวนตัวอย่างพร้อมฝึก


## Mac2Hand — ผล clean

`data/intermediate/mac2hand/<รอบ>/clean/mac2hand_cleaned.jsonl` เก็บทุกแถว มี `source`, `product_id`, `url`, `clean` (brand/model/storage_gb/condition/price_thb/published_at), `status`, `hold_reasons`, `exclusion_reasons`, `notes`, `evidence`, `original`, `input_sha256` และ `candidate_duplicate_group` เฉพาะกลุ่มที่สงสัยประกาศซ้ำ

`original` รวมการ์ดและรายละเอียดที่ parse จาก HTML ใหม่ พร้อม provenance ค่าสภาพยังเป็นคำผู้ขาย ดู [วิธี clean](../mac2hand/cleaning.md) โครงสร้างข้อมูลหลักสอดคล้องกับ ENNXO ขั้น clean แยกเว็บคงโครงสร้างเดิม ส่วนชุดรวมปัจจุบันใช้ schema กลางตามหัวข้อท้ายเอกสาร

## Mac2Hand — ชุดส่งมอบล่าสุด

`final/dataset.csv` ใช้คอลัมน์หลัก `source`, `product_id`, `url`, `brand`, `model`, `storage_gb`, `condition`, `price_thb`, `published_at` พร้อม `seller_key`, `candidate_duplicate_group`, `disposition`, `hold_reasons`, `exclusion_reasons`, `notes`, `next_action` ช่องเหตุผลและคำแนะนำเป็นข้อมูลตรวจสอบ ไม่ใช่ฟีเจอร์ฝึกโดยอัตโนมัติ

`data/intermediate/mac2hand/<รอบ>/finalization/mac2hand_final.jsonl` เก็บทุกแถว พร้อม `original`, `resolution` (หลักฐานจากแต่ละแหล่ง), `disposition` และ `next_action` ดู [ความหมายไฟล์ทั้งหมด](../mac2hand/finalization.md) ผล ENNXO และ Mac2Hand มีฟิลด์หลักคล้ายกัน แต่ฟิลด์ประกอบต่างกัน ชุดรวมเก็บฟิลด์เฉพาะเว็บทั้งหมดใน `data/intermediate/combined/<รอบ>/audit/lineage.jsonl` ตามหัวข้อท้ายเอกสาร

## Schema กลางและชุดรวม

ใช้ `config/shared/dataset_schema.json` ชุดรวมมี `listing_id`, `source`, `source_snapshot`, `product_id`, `url`, `brand`, `model`, `storage_gb`, `condition`, `price_thb`, `published_at`, `published_at_raw`, `published_at_precision` วันที่มาตรฐานเป็นวันไทย; ค่าเดิมทุกคอลัมน์อยู่ใน lineage ดู [ชนิดข้อมูลและวิธีรวม](combined_dataset.md)
