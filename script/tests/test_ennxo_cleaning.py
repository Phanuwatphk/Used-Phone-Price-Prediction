import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from script.preparation.ennxo.audit_ennxo_raw import ROOT, inventory, dump
from script.preparation.ennxo.clean_ennxo import clean
from script.preparation.ennxo.cleaning_rules import clean_row, apply_correction, model_key, storage_claims, text_models

RULES = json.loads((ROOT / 'config/ennxo/cleaning_rules.json').read_text())
DESCRIPTION_RULES = copy.deepcopy(RULES)
RULES.pop('field_source_priority', None)  # Keep regression coverage for the previous source policy.



from script.artifacts import write_metadata

def row(title='iPhone 13 128GB', detail='iPhone 13 128GB ใช้เอง ไม่ติดไอคลาวด์'):
    return {'url': 'https://www.ennxo.com/product/123', 'product_id': '123', 'source': 'ennxo',
            'raw_listing': {'url': 'https://www.ennxo.com/product/123', 'price': 5000, 'brand': None, 'scraped_at': '2026-10-05T20:00:00+07:00'},
            'card': {'name': title, 'price_texts': ['฿ 5,000'], 'image_url': 'image'},
            'embedded_product': {'name': title, 'detail': detail, 'price': 5000, 'condition': 'used', 'create_date': '2026-10-04T00:00:00Z',
                                 'subfields': {'maker': {'name': 'Apple', 'slug': 'apple'}, 'model': {'name': 'iPhone 13', 'slug': 'iphone-13'}, 'capacity': 128}},
            'observations': ['legacy_brand_missing_but_embedded_maker_available'], 'provenance': {'page_file': 'pages/page_1.html'}}


class CleaningTests(unittest.TestCase):
    def test_compact_brand_se_and_camera_component(self):
        original = row(detail='iPhoneSE3 128GB')
        result = clean_row(original, DESCRIPTION_RULES, {('Apple','se3'):'iPhone SE 3'})
        self.assertEqual(result['clean']['model'],'iPhone SE 3')
        original = row('Xiaomi 14 Ultra 128GB','Xiaomi 14 Ultra กล้องหลักใช้เซ็นเซอร์ Sony LYT-900 ความจุ128GB')
        result = clean_row(original, DESCRIPTION_RULES, {('Xiaomi','14ultra'):'14 Ultra'})
        self.assertNotIn('brand_conflict',result['hold_reasons'])
        self.assertEqual(result['clean']['brand'],'Xiaomi')

    def test_additional_reported_faults_stay_in_review(self):
        for fault in ('เครื่องปลดห้ามรีห้ามอัพ','จอหน้ามีรอยขีดข่วนกับบางทีกระพริบ','กล้องเวลาถ่ายภาพ1x-4x ถ่ายภาพจะเบลอ','ปากกาเขียนไม่ได้','ขาซิมมีปัญหา'):
            result = clean_row(row(detail='iPhone 13 128GB '+fault), DESCRIPTION_RULES,{})
            self.assertIn('reported_damage_or_lock',result['hold_reasons'])
    def test_capacity_pair_not_two_storages_and_expansion_not_rom(self):
        for text in ('ความจุ 8/128GB', 'ROM 128GB (Up to 1TB)', 'ROM 128GB รองรับการขยายความจุได้สูงสุดถึง 1TB ด้วย MicroSD Card'):
            self.assertEqual({c['value'] for c in storage_claims(text, RULES['storage_gb'])}, {128})
        self.assertEqual({c['value'] for c in storage_claims('𝐑𝐀𝐌 6+4 𝐑𝐎𝐌 128𝐠𝐛', RULES['storage_gb'])}, {128})

    def test_missing_families_and_exact_variants(self):
        for text,brand,key in [('Realme C30s','Realme','c30s'),('Realme X2 Pro','Realme','x2pro'),('Huawei NOVA3i','Huawei','nova3i'),('Huawei Y9Prime 2019','Huawei','y9prime2019'),('SamsungNote20Ultra5G','Samsung','note20ultra'),('Vivo Y91c','Vivo','y91c')]:
            self.assertEqual([model_key(m,brand) for m in text_models(text,brand)], [key])
        self.assertEqual(text_models('iPhone 12 Product Red', 'Apple'), ['iphone 12'])

    def test_description_exchange_brand_and_galaxy_heading(self):
        original = row('Samsung Galaxy S23 Plus 128GB','Samsung galaxy s23 plus 8/128 ขาย /เทิร์น แลกไอโฟน รุ่นโปร')
        original['embedded_product']['subfields']['maker']={'name':'Samsung','slug':'samsung'}
        result=clean_row(original, DESCRIPTION_RULES, {('Samsung','s23plus'):'Galaxy S23 Plus'})
        self.assertNotIn('brand_conflict',result['hold_reasons'])
        original['embedded_product']['detail']='Galaxy S23 Ultra 128GB'
        result=clean_row(original, DESCRIPTION_RULES, {('Samsung','s23ultra'):'Galaxy S23 Ultra'})
        self.assertEqual(result['clean']['model'],'Galaxy S23 Ultra')
    def test_description_overrides_wrong_selected_brand_model_and_storage(self):
        original = row()
        original['embedded_product']['subfields'] = {'maker': {'name': 'Samsung', 'slug': 'samsung'},
             'model': {'name': 'Galaxy S23 Ultra', 'slug': 's23-ultra'}, 'capacity': 256}
        result = clean_row(original, DESCRIPTION_RULES, {('Apple', '13'): 'iPhone 13'})
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual([result['clean'][f] for f in ('brand', 'model', 'storage_gb')], ['Apple', 'iPhone 13', 128])
        self.assertEqual(result['original'], original)
        self.assertEqual(result['evidence']['model']['description_claims'][0]['line'], 1)

    def test_description_sections_ignore_financing_stock_and_contact(self):
        original = row(detail='รายละเอียดสินค้า\nสีดำ\nแบต 90%\nสภาพดี\niPhone 13 128GB\nผ่อนได้\niPhone 14 256GB ดาวน์ 999 บาท\nติดต่อร้าน\niPhone 15 512GB')
        result = clean_row(original, DESCRIPTION_RULES, {})
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['clean']['model'], 'iPhone 13')
        self.assertEqual(result['evidence']['model']['description_claims'][0]['line'], 5)
        self.assertEqual(result['clean']['storage_gb'], 128)

    def test_description_internal_conflicts_and_damage_still_held(self):
        original = row(detail='iPhone 13 128GB\niPhone 14 256GB\nฝาหลังแตก')
        result = clean_row(original, DESCRIPTION_RULES, {})
        for reason in ('model_description_conflict', 'storage_conflict', 'reported_damage_or_lock'):
            self.assertIn(reason, result['hold_reasons'])

    def test_description_variant_requires_catalog_and_price_still_checked(self):
        original = row(detail='iPhone 13 mini 128GB ราคา 4,000 บาท')
        result = clean_row(original, DESCRIPTION_RULES, {})
        self.assertIn('model_outside_observed_catalog', result['hold_reasons'])
        self.assertIn('description_price_conflict', result['hold_reasons'])
        result = clean_row(original, DESCRIPTION_RULES, {('Apple', '13mini'): 'iPhone 13 Mini'})
        self.assertEqual(result['clean']['model'], 'iPhone 13 Mini')
        self.assertNotIn('model_conflict', result['hold_reasons'])

    def test_description_missing_keeps_fallback_and_se_generation(self):
        result = clean_row(row(detail='สภาพดี ใช้เอง'), DESCRIPTION_RULES, {})
        self.assertEqual(result['status'], 'accepted')
        self.assertNotIn('model_from_description', result['notes'])
        self.assertEqual(model_key(text_models('iPhone SE 2/64GB', 'Apple')[0], 'Apple'), 'se2')

    def test_description_non_phone_price_without_unit_and_thai_storage(self):
        result = clean_row(row(detail='iPad Pro M4 256GB'), DESCRIPTION_RULES, {})
        self.assertIn('description_non_phone_device', result['hold_reasons'])
        result = clean_row(row(detail='ไอโฟน13 128กิ๊ก\nราคา: 17500 มารับเอง 16990 บาท'), DESCRIPTION_RULES, {})
        self.assertIn('description_price_conflict', result['hold_reasons'])
        self.assertEqual(result['clean']['storage_gb'], 128)
        self.assertEqual(model_key(text_models('ไอโฟน12โปรแม็ค', 'Apple')[0], 'Apple'), '12promax')

    def test_purchase_history_does_not_hide_explicit_item_identity(self):
        result = clean_row(row(detail='โทรศัพท์มือถือ OPPO a12 สภาพซื้อมาเก็บไม่ได้ใช้'), DESCRIPTION_RULES, {('Oppo', 'a12'): 'A12'})
        self.assertEqual(result['clean']['model'], 'A12')
        self.assertEqual(result['clean']['brand'], 'Oppo')

    def test_explicit_pickup_discount_and_unmatched_price(self):
        result = clean_row(row(detail='iPhone 13 128GB\nราคา: 5500 มารับเอง 5000 บาท'), DESCRIPTION_RULES, {})
        self.assertNotIn('description_price_conflict', result['hold_reasons'])
        self.assertIn('price_matches_explicit_pickup_offer', result['notes'])
        result = clean_row(row(detail='iPhone 13 128GB\nราคา: 5500 มารับเอง 4990 บาท'), DESCRIPTION_RULES, {})
        self.assertIn('description_price_conflict', result['hold_reasons'])

    def test_original_preserved_and_html_brand_recovered(self):
        original = row()
        before = copy.deepcopy(original)
        result = clean_row(original, RULES, {})
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['clean']['brand'], 'Apple')
        self.assertIsNone(result['original']['raw_listing']['brand'])
        self.assertEqual(original, before)

    def test_conflicting_selected_model_and_capacity_are_held(self):
        original = row()
        original['embedded_product']['subfields']['model']['name'] = 'iPhone 14'
        original['embedded_product']['subfields']['capacity'] = 256
        result = clean_row(original, RULES, {})
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('model_conflict', result['hold_reasons'])
        self.assertIn('storage_conflict', result['hold_reasons'])

    def test_exact_variant_and_two_title_sources(self):
        original = row('iPhone 13 Pro Max 128GB', 'iPhone 13 Pro Max 128GB')
        result = clean_row(original, RULES, {})
        self.assertIn('model_conflict', result['hold_reasons'])
        original['card']['name'] = 'iPhone 14 128GB'
        self.assertIn('multiple_title_models', clean_row(original, RULES, {})['hold_reasons'])

    def test_explicit_missing_model_recovery_and_unknown_remains_missing(self):
        original = row('SamsungA35 5G 8/128', 'Samsung A35 5G RAM 8GB ROM 128GB')
        original['embedded_product']['subfields']['maker'] = {'name': 'Samsung', 'slug': 'samsung'}
        original['embedded_product']['subfields']['model'] = {'name': 'อื่นๆ', 'slug': 'others'}
        result = clean_row(original, RULES, {('Samsung', 'a35'): 'Galaxy A35'})
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(model_key(result['clean']['model'], 'Samsung'), 'a35')
        original['card']['name'] = original['embedded_product']['name'] = 'มือถือ Samsung 128GB'
        self.assertIsNone(clean_row(original, RULES, {})['clean']['model'])

    def test_ram_sd_and_model_number_not_storage(self):
        claims = storage_claims('RAM 8GB ROM 128GB รองรับ SD 256GB 8/128', RULES['storage_gb'])
        self.assertEqual({c['value'] for c in claims}, {128})

    def test_parenthesized_rom_thai_units_and_expansion_limit(self):
        text = 'หน่วยความจำภายใน (ROM): 128 GBหน่วยความจำแรม (RAM): 8 GB\nหน่วยความจำภายนอก microSD เพิ่มได้สูงสุด 512 GB'
        self.assertEqual({c['value'] for c in storage_claims(text, RULES['storage_gb'])}, {128})
        self.assertEqual({c['value'] for c in storage_claims('รอม 64 แรม 4', RULES['storage_gb'])}, {64})

    def test_emoji_accessory_and_board_not_phone(self):
        for title in ('🔥เคส iPhone 13', 'ชุดบอร์ด Samsung a04'):
            self.assertIn('accessory_or_part', clean_row(row(title), RULES, {})['exclusion_reasons'])
        self.assertIn('other_device', clean_row(row('Home Wi-Fi ซิมรายปี'), RULES, {})['exclusion_reasons'])

    def test_verified_catalog_still_holds_conflicting_variant_and_storage(self):
        original = row('OPPO A98 128GB', 'OPPO A98 ROM 128GB')
        original['embedded_product']['subfields']['maker'] = {'name': 'Oppo', 'slug': 'oppo'}
        original['embedded_product']['subfields']['model'] = {'name': 'อื่นๆ', 'slug': 'others'}
        result = clean_row(original, RULES, {('Oppo', 'a98'): 'A98'})
        self.assertEqual(result['status'], 'accepted')
        original['embedded_product']['subfields']['capacity'] = 256
        self.assertIn('storage_conflict', clean_row(original, RULES, {('Oppo', 'a98'): 'A98'})['hold_reasons'])
        original['embedded_product']['detail'] = 'OPPO A98 Pro ROM 128GB'
        original['embedded_product']['subfields']['capacity'] = 128
        result = clean_row(original, RULES, {('Oppo', 'a98'): 'A98'})
        self.assertIn('model_description_conflict', result['hold_reasons'])
        self.assertEqual(storage_claims('iPhone 16 RAM 8GB', RULES['storage_gb']), [])
        self.assertEqual(storage_claims('ความจุ 1TB', RULES['storage_gb'])[0]['value'], 1024)
        claims = storage_claims('ROM 128GB (เพิ่ม microSD ได้ถึง 1TB)', RULES['storage_gb'])
        self.assertEqual({c['value'] for c in claims}, {128})

    def test_unknown_catalog_price_in_description_and_bundle(self):
        original = row('iPhone 18 Pro 128GB', 'iPhone 18 Pro 128GB ราคา 4,000 บาท ขายคู่สมาร์ทวอทช์')
        original['embedded_product']['subfields']['model'] = {'name': 'อื่นๆ', 'slug': 'others'}
        result = clean_row(original, RULES, {})
        for reason in ('model_outside_observed_catalog', 'description_price_conflict', 'possible_bundle'):
            self.assertIn(reason, result['hold_reasons'])

    def test_structured_storage_sufficient_and_warranty_not_damage(self):
        original = row('iPhone 13', 'เครื่องใช้เอง มีประกันจอแตก')
        result = clean_row(original, RULES, {})
        self.assertEqual(result['status'], 'accepted')
        self.assertIn('storage_from_selected_field_only', result['notes'])

    def test_negation_and_actual_damage(self):
        original = row(detail='iPhone 13 128GB ไม่ติดล็อค ไม่เคยจอแตก')
        self.assertNotIn('reported_damage_or_lock', clean_row(original, RULES, {})['hold_reasons'])
        original['embedded_product']['detail'] += ' แต่ฝาหลังแตก'
        self.assertIn('reported_damage_or_lock', clean_row(original, RULES, {})['hold_reasons'])

    def test_new_accessory_does_not_make_device_new(self):
        result = clean_row(row(detail='iPhone 13 128GB ใช้เอง แถมเคสใหม่ยังไม่แกะ'), RULES, {})
        self.assertEqual(result['status'], 'accepted')
        original = row(detail='iPhone 13 128GB เครื่องใหม่ไม่เคยใช้')
        self.assertIn('seller_condition_text_disagrees', clean_row(original, RULES, {})['notes'])
        for title in ('iPhone 13 มือ1', 'iPhone 13 เครื่องใหม่'):
            self.assertIn('seller_condition_text_disagrees', clean_row(row(title), RULES, {})['notes'])
        for title in ('iPhone 13 สภาพเครื่องใหม่กริ๊บ', 'iPhone 13 เทียบมือหนึ่ง', 'iPhone 13 เทียบเท่ามือ 1'):
            self.assertNotIn('condition_conflict', clean_row(row(title), RULES, {})['hold_reasons'])
        self.assertNotIn('condition_conflict', clean_row(row(detail='ใช้เองขายเพราะซื้อเครื่องใหม่'), RULES, {})['hold_reasons'])
        self.assertIn('reported_damage_or_lock', clean_row(row('iPhone 13 จอเส้นเขียว'), RULES, {})['hold_reasons'])

    def test_scope_retains_excluded_record(self):
        original = row('ฟิล์ม iPhone 13 128GB')
        result = clean_row(original, RULES, {})
        self.assertEqual(result['status'], 'excluded')
        self.assertIn('accessory_or_part', result['exclusion_reasons'])
        self.assertEqual(result['original'], original)

    def test_selected_new_included_and_original_condition_preserved(self):
        original = row('iPhone 13 มือสอง', 'เครื่องสวย')
        original['embedded_product']['condition'] = 'new'
        result = clean_row(original, RULES, {})
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['clean']['condition'], 'new')
        self.assertEqual(result['original']['embedded_product']['condition'], 'new')
        self.assertIn('seller_condition_text_disagrees', result['notes'])
        self.assertIn('selected_new_included_by_scope', result['notes'])
        self.assertEqual(result['hold_reasons'], [])

    def test_new_phone_in_scope_but_new_accessory_remains_excluded(self):
        original = row()
        original['embedded_product']['condition'] = 'new'
        result = clean_row(original, RULES, {})
        self.assertEqual(result['status'], 'accepted')
        entry = {'action': 'correct', 'input_sha256': result['input_sha256'], 'values': {'condition': 'new'},
                 'reason': 'retain seller label', 'reviewer': 'test reviewer', 'evidence': 'selected field'}
        apply_correction(result, entry, RULES)
        self.assertEqual(result['status'], 'accepted')
        original['embedded_product']['name'] = original['card']['name'] = 'ฟิล์ม iPhone 13'
        self.assertIn('accessory_or_part', clean_row(original, RULES, {})['exclusion_reasons'])

    def test_previous_policy_still_replays(self):
        previous = dict(RULES)
        previous.pop('accepted_conditions')
        previous.pop('condition_text_conflict_action')
        original = row(detail='iPhone 13 128GB เครื่องใหม่ไม่เคยใช้')
        original['embedded_product']['condition'] = 'new'
        self.assertIn('selected_new_outside_used_scope', clean_row(original, previous, {})['exclusion_reasons'])

    def test_price_and_date_checks(self):
        original = row()
        original['embedded_product']['price'] = 1
        original['embedded_product']['create_date'] = '2026-10-06T00:00:00Z'
        result = clean_row(original, RULES, {})
        for reason in ('possible_placeholder_price', 'price_source_conflict', 'card_price_conflict', 'invalid_or_future_publication_date'):
            self.assertIn(reason, result['hold_reasons'])

    def test_correction_is_bound_to_evidence_and_does_not_clear_unrelated_holds(self):
        original = row()
        original['embedded_product']['subfields']['capacity'] = 256
        original['embedded_product']['detail'] += ' ฝาหลังแตก'
        result = clean_row(original, RULES, {})
        entry = {'action': 'correct', 'input_sha256': result['input_sha256'], 'values': {'storage_gb': 128},
                 'reason': 'ต้นฉบับระบุ 128GB', 'reviewer': 'user', 'evidence': 'ชื่อและรายละเอียด'}
        apply_correction(result, entry, RULES)
        self.assertNotIn('storage_conflict', result['hold_reasons'])
        self.assertIn('reported_damage_or_lock', result['hold_reasons'])
        self.assertEqual(result['status'], 'needs_review')
        entry['input_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            apply_correction(result, entry, RULES)

    def test_replay_and_raw_integrity_and_stale_input_rejection(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            raw, extraction = root / 'raw', root / 'extraction'
            raw.mkdir()
            extraction.mkdir()
            original = row()
            (raw / 'listings.jsonl').write_text(json.dumps(original['raw_listing']) + '\n')
            before = inventory(raw)
            (extraction / 'ennxo_extracted.jsonl').write_text(json.dumps(original) + '\n')
            dump(extraction / 'raw_checksums.json', before)
            write_metadata(extraction, 'summary', {'accounting_passed': True, 'records': 1})
            ledger = root / 'test_config/corrections.json'
            ledger.parent.mkdir()
            dump(ledger, {'schema_version': 1, 'corrections': []})
            clean(extraction, raw, root / 'one', corrections_path=ledger)
            clean(extraction, raw, root / 'two', corrections_path=ledger)
            for path in (root / 'one').iterdir():
                if path.name == 'metadata.json':
                    a=json.loads(path.read_text());b=json.loads((root/'two'/path.name).read_text())
                    a.pop('provenance');b.pop('provenance');self.assertEqual(a,b)
                else:
                    self.assertEqual(path.read_bytes(), (root / 'two' / path.name).read_bytes())
            self.assertEqual(inventory(raw), before)
            (raw / 'extra.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed since extraction'):
                clean(extraction, raw, root / 'three', corrections_path=ledger)


if __name__ == '__main__':
    unittest.main()
