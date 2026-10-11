import copy
import json
from pathlib import Path
import unittest
from script.preparation.mac2hand.clean_mac2hand import clean_row, models, storage_claims

RULES = json.loads((Path(__file__).resolve().parents[2] / 'config/mac2hand/cleaning_rules.json').read_text())


def extracted():
    return {'source': 'mac2hand', 'product_id': '123', 'url': 'https://mac2hand.com/detail/123/',
            'extraction_errors': [], 'detail': {'title': 'iPhone 13 Pro Max 256GB', 'specs': {},
            'description': 'เครื่องใช้เอง ไม่ติดล็อค ไม่ติด iCloud\nราคา : 15000 บาท',
            'price_thb': 15000, 'currency': 'THB', 'condition_selected': 'https://schema.org/UsedCondition',
            'condition_label_raw': '98%', 'published_date': '2020-01-01'},
            'raw_listing': {'name': 'iPhone 13 Pro Max 256GB', 'subtitle': '', 'price': 15000,
            'badges': [], 'published_date': '2020-01-01', 'scraped_at': '2026-10-06T17:00:00+07:00'}}


class MacCleaningTests(unittest.TestCase):
    def test_valid_legacy_listing_and_negations(self):
        row = extracted(); before = copy.deepcopy(row)
        result = clean_row(row, RULES)
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['clean']['model'], 'iPhone 13 Pro Max')
        self.assertEqual(result['clean']['storage_gb'], 256)
        self.assertEqual(row, before)
        self.assertEqual(result['clean']['published_at'], '2020-01-01')

    def test_missing_detail_never_falls_back_to_card_as_verified(self):
        row = extracted(); row['detail'] = None; row['extraction_errors'] = ['missing']
        result = clean_row(row, RULES)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('detail_unavailable_or_unverified', result['hold_reasons'])
        self.assertIsNone(result['clean']['price_thb'])

    def test_conflicting_models_and_multiple_storage_options(self):
        row = extracted(); row['detail']['title'] += ' / iPhone 14 128GB'
        result = clean_row(row, RULES)
        self.assertIn('multiple_or_conflicting_models', result['hold_reasons'])
        self.assertIn('storage_conflict_or_multiple_options', result['hold_reasons'])
        self.assertIsNone(result['clean']['model'])
        self.assertIsNone(result['clean']['storage_gb'])

    def test_damaged_device_separate_from_normal(self):
        row = extracted(); row['detail']['description'] += '\nจอแตก'
        self.assertIn('possible_damage_or_lock', clean_row(row, RULES)['hold_reasons'])

    def test_buttons_and_biometric_failures_held_without_matching_voice(self):
        for text in ['สแกนนิ้วเสีย', 'ปุ่มโฮมเสีย', 'Face ID ใช้ไม่ได้']:
            row = extracted(); row['detail']['description'] += '\n' + text
            self.assertIn('possible_damage_or_lock', clean_row(row, RULES)['hold_reasons'])
        row = extracted(); row['detail']['description'] += '\nปุ่ม Home ดี เสียงดี'
        self.assertEqual(clean_row(row, RULES)['status'], 'accepted')

    def test_other_smartphones_kept_for_model_review(self):
        row = extracted(); row['detail']['title'] = row['raw_listing']['name'] = 'Samsung S24 Ultra 256GB'
        result = clean_row(row, RULES)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['exclusion_reasons'], [])

    def test_new_claim_with_used_selected_retained(self):
        row = extracted(); row['detail']['description'] += '\nของใหม่แกะกล่อง'
        result = clean_row(row, RULES)
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['clean']['condition'], 'used')
        self.assertIn('seller_new_claim_with_used_selected_retained', result['notes'])

    def test_exact_price_not_down_payment(self):
        row = extracted(); row['detail']['description'] += '\nเงินดาวน์ 15000'
        self.assertIn('possible_partial_payment_or_contract', clean_row(row, RULES)['hold_reasons'])
        row = extracted(); row['detail']['price_thb'] = 1
        self.assertIn('possible_placeholder_price', clean_row(row, RULES)['hold_reasons'])

    def test_price_source_and_description_conflicts(self):
        row = extracted(); row['detail']['description'] = 'ราคา : 12000 บาท'
        self.assertIn('description_price_conflict', clean_row(row, RULES)['hold_reasons'])
        row['detail']['price_thb'] = 13000
        self.assertIn('card_detail_price_conflict', clean_row(row, RULES)['hold_reasons'])

    def test_services_and_accessories_excluded_with_raw_retained(self):
        for title in ['รับซื้อ iPhone 13 256GB', 'เคส iPhone 13 256GB', 'iPad 256GB']:
            row = extracted(); row['detail']['title'] = title
            result = clean_row(row, RULES)
            self.assertEqual(result['status'], 'excluded')
            self.assertEqual(result['original'], row)

    def test_se_and_old_x_models(self):
        self.assertEqual(models('iPhone XS Max')[0]['value'], 'iPhone XS Max')
        self.assertEqual(models('iPhone SE (2020)')[0]['value'], 'iPhone SE 2')
        row = extracted(); row['detail']['title'] = row['raw_listing']['name'] = 'iPhone SE 256GB'
        self.assertIn('se_generation_unspecified', clean_row(row, RULES)['hold_reasons'])

    def test_old_models_and_plus_symbols_preserved(self):
        for text, expected in [('iPhone 6S Plus', 'iPhone 6s Plus'), ('ไอโฟน 7+', 'iPhone 7 Plus'), ('iPhone6s+', 'iPhone 6s Plus'), ('iPhone 6s Plus64gb', 'iPhone 6s Plus'), ('iPhone15PM 256GB', 'iPhone 15 Pro Max'), ('iphone 3gs', 'iPhone 3GS')]:
            self.assertEqual(models(text)[0]['value'], expected)
        row = extracted(); row['detail']['title'] = row['raw_listing']['name'] = 'iPhone 64 256GB'
        self.assertIn('model_number_requires_review', clean_row(row, RULES)['hold_reasons'])

    def test_screen_insurance_not_actual_damage(self):
        row = extracted(); row['detail']['description'] += '\nติดฟิล์ม รับประกันหน้าจอแตก\nรับประกันความพอใจเครื่องมีปัญหายินดีคืนเงิน'
        self.assertEqual(clean_row(row, RULES)['status'], 'accepted')

    def test_ram_not_storage_and_tb_conversion(self):
        self.assertEqual(storage_claims('RAM 8GB', RULES['storage_gb']), [])
        self.assertEqual(storage_claims('4G All SIM', RULES['storage_gb']), [])
        self.assertEqual(storage_claims('RAM 8GB ROM 128GB', RULES['storage_gb'])[0]['value'], 128)
        self.assertEqual(storage_claims('1TB', RULES['storage_gb'])[0]['value'], 1024)

    def test_desired_upgrade_not_current_model_conflict(self):
        row = extracted(); row['detail']['description'] += '\nอยากเปลี่ยนเป็น iPhone 14 เลยขาย'
        self.assertEqual(clean_row(row, RULES)['status'], 'accepted')

    def test_capacity_not_mistaken_for_model_number(self):
        self.assertEqual(models('iPhone 16gb'), [])

    def test_future_date_not_accepted(self):
        row = extracted(); row['detail']['published_date'] = '2027-01-01'
        self.assertIn('published_date_after_snapshot', clean_row(row, RULES)['hold_reasons'])

    def test_contact_and_shop_signature_not_device_damage(self):
        row = extracted(); row['detail']['description'] += '\nเบอร์ติดต่อ : 0812345678\nรับซื้อเครื่องเสีย จอแตก'
        self.assertEqual(clean_row(row, RULES)['status'], 'accepted')


if __name__ == '__main__':
    unittest.main()
