import copy
import json
from pathlib import Path
import unittest
import tempfile
import csv
import contextlib
import io
from script.preparation.mac2hand.finalize_mac2hand import finalize, next_action
from script.preparation.mac2hand.prepare_mac2hand import checksums
from script.preparation.mac2hand.clean_mac2hand import clean_row
from script.preparation.mac2hand.resolution_rules import resolve, alias_text, card_price, price_claims
from script.tests.test_mac2hand_cleaning import extracted, RULES as CLEAN_RULES

ROOT=Path(__file__).resolve().parents[2]
RULES=json.loads((ROOT/'config/mac2hand/finalization_rules.json').read_text())
CATALOG=json.loads((ROOT/'config/mac2hand/iphone_model_names.json').read_text())['models']


def fixture():
    source=extracted();source['raw_listing']['price_raw']='฿15,000'
    return source


def run(source):
    return resolve(clean_row(source,CLEAN_RULES),RULES,CATALOG)


class MacFinalizationTests(unittest.TestCase):
    def test_valid_old_listing_raw_not_modified(self):
        source=fixture();before=copy.deepcopy(source);row=run(source)
        self.assertEqual(row['disposition'],'accepted')
        self.assertEqual(source,before)
        self.assertEqual(row['original'],source)

    def test_shorthand_capacity_recovers_without_price_imputation(self):
        source=fixture();source['detail']['title']=source['raw_listing']['name']='iPhone 13 Pro Max 256 สีดำ'
        self.assertEqual(run(source)['clean']['storage_gb'],256)
        self.assertEqual(run(source)['disposition'],'accepted')
        source['detail']['title']=source['raw_listing']['name']='iPhone 13 Pro Max'
        source['detail']['description']='ราคา 15000 บาท'
        self.assertEqual(run(source)['disposition'],'insufficient_data')
        self.assertIsNone(run(source)['clean']['storage_gb'])

    def test_wrong_metadata_overridden_only_by_agreeing_seller_text(self):
        source=fixture();source['detail']['title']=source['raw_listing']['name']='iPhone 14 Pro Max 128GB iPhone 13 Pro Max 256GB'
        source['raw_listing']['subtitle']='iPhone 13 Pro Max 256GB'
        source['detail']['description']='iPhone 13 Pro Max 256GB\nราคา 15000 บาท'
        row=run(source)
        self.assertEqual(row['disposition'],'accepted')
        self.assertEqual(row['clean']['model'],'iPhone 13 Pro Max')
        self.assertEqual(row['clean']['storage_gb'],256)

    def test_real_capacity_conflict_not_overridden(self):
        source=fixture();source['detail']['description'] += '\nStorage: 512GB\nStorage: 256GB'
        self.assertEqual(run(source)['disposition'],'ambiguous')
        self.assertIsNone(run(source)['clean']['storage_gb'])

    def test_percentage_price_recovered_from_explicit_seller_price(self):
        source=fixture();source['raw_listing'].update(price_raw='฿99%',price=None);source['detail']['price_thb']=99
        row=run(source)
        self.assertEqual(row['disposition'],'accepted')
        self.assertEqual(row['clean']['price_thb'],15000)
        self.assertIn('seller_price_recovered_from_percentage_in_price_field',row['notes'])

    def test_unresolved_price_conflict_never_majority_vote(self):
        source=fixture();source['detail']['description']='ราคา 14000 บาท'
        self.assertEqual(run(source)['disposition'],'ambiguous')
        self.assertEqual(run(source)['clean']['price_thb'],15000)

    def test_charge_cycles_and_shipping_not_price(self):
        self.assertEqual(price_claims('ชาร์จเพียง 120 ครั้ง\nราคา : 15000 บาท\nค่าส่งราคา 100 บาท'),[{'value':15000,'text':'ราคา : 15000'}])
        self.assertIsNone(card_price('฿99%'))
        self.assertIsNone(card_price('฿ 1000-2000'))
        self.assertEqual(card_price('฿12,500.-'),12500)

    def test_known_misspellings_and_literal_model_in_full_description(self):
        for title in ['Iphon 13 Pro Max 256GB', 'iPhone (ไอโฟน) 13 Pro Max 256GB']:
            source=fixture();source['detail']['title']=source['raw_listing']['name']=title
            self.assertEqual(run(source)['disposition'],'accepted')
        source=fixture();source['detail']['title']=source['raw_listing']['name']='7990'
        source['detail']['description']='เครื่องใช้เอง\nรายละเอียดสินค้า\niPhone 13 Pro Max 256GB\nราคา 15000 บาท'
        self.assertEqual(run(source)['clean']['model'],'iPhone 13 Pro Max')

    def test_other_phone_brand_recognized_and_accessory_not_phone(self):
        source=fixture();source['detail']['title']=source['raw_listing']['name']='Samsung S24 Ultra 256GB'
        source['detail']['description']='Samsung S24 Ultra 256GB\nราคา 15000 บาท'
        row=run(source);self.assertEqual(row['clean']['model'],'Galaxy S24 Ultra');self.assertEqual(row['disposition'],'accepted')
        source['detail']['title']='หูฟัง iPhone 13 Pro Max';self.assertEqual(run(source)['disposition'],'excluded')

    def test_defects_negative_warranty_and_hypothetical(self):
        for text in ['Face ID ใช้งานไม่ได้','ติดล็อคซิม AIS','สแกนนิ้วเสีย','จอมีเส้น']:
            source=fixture();source['detail']['description']+='\n'+text
            self.assertEqual(run(source)['disposition'],'non_normal')
        for text in ['ไม่ติดล็อก','รับประกันหน้าจอแตก','ถ้าเกิดเครื่องมีปัญหาเคลมได้','ไม่ต้องกังวล เช่น หน้าจอมีเส้น']:
            source=fixture();source['detail']['description']+='\n'+text
            self.assertEqual(run(source)['disposition'],'accepted',text)

    def test_se_not_guessed_from_date_capacity_color(self):
        source=fixture();source['detail']['title']=source['raw_listing']['name']='iPhone SE 256GB สี Rose Gold'
        self.assertEqual(run(source)['disposition'],'insufficient_data')
        self.assertEqual(run(source)['clean']['model'],'iPhone SE')

    def test_missing_detail_quarantined(self):
        source=fixture();source['detail']=None;source['extraction_errors']=['failed']
        self.assertEqual(run(source)['disposition'],'missing_source')

    def test_prior_manual_separate_not_silently_accepted(self):
        row=clean_row(fixture(),CLEAN_RULES);row['manual_review']={'disposition':'keep_separate'}
        self.assertEqual(resolve(row,RULES,CATALOG)['disposition'],'non_normal')

    def test_multi_device_or_partial_payment_not_accepted(self):
        source=fixture();source['detail']['description']+='\nเงินดาวน์ 15000'
        self.assertEqual(run(source)['disposition'],'ambiguous')
        source=fixture();source['detail']['title']+=' / iPhone 14 128GB'
        self.assertEqual(run(source)['disposition'],'ambiguous')

    def test_percent_price_and_baht_heading(self):
        source=fixture();source['detail']['title']='iPhone 13 Pro Max 256GB 15000 บาท'
        source['raw_listing'].update(price_raw='฿100%',price=None);source['detail']['price_thb']=100
        source['detail']['description']='iPhone 13 Pro Max 256GB 15000 บาท\nเครื่องใช้เอง'
        self.assertEqual(run(source)['disposition'],'accepted')
        self.assertEqual(run(source)['clean']['price_thb'],15000)

    def test_storage_b_typo_only_after_explicit_phone_model(self):
        source=fixture();source['detail']['title']=source['raw_listing']['name']='iPhone 13 Pro Max 256B สีดำ'
        self.assertEqual(run(source)['clean']['storage_gb'],256)

    def test_workflow_accounts_queue_preserves_inputs_and_repeats_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);raw=root/'raw';raw.mkdir()
            stage=root/'processed/manual_review';stage.mkdir(parents=True)
            audit=stage.parent/'raw_audit';audit.mkdir()
            source=fixture();source['detail']['description']='ราคา 14000 บาท'
            row=clean_row(source,CLEAN_RULES)
            raw_file=raw/'listings.jsonl';raw_file.write_text(json.dumps({'url':row['url']})+'\n')
            input_file=stage/'input.jsonl';input_file.write_text(json.dumps(row)+'\n')
            before=input_file.read_bytes();hashes=checksums(raw)
            (audit/'raw_checksums.json').write_text(json.dumps(hashes))
            for name in ('first','repeat'):
                with contextlib.redirect_stdout(io.StringIO()):
                    summary=finalize(raw,input_file,root/name)
                self.assertEqual(summary['original_queue_records'],1)
                self.assertEqual(summary['dispositions'],{'ambiguous':1})
            self.assertEqual(input_file.read_bytes(),before)
            self.assertEqual(checksums(raw),hashes)
            self.assertEqual((root/'first/queue_decisions.csv').read_bytes(),(root/'repeat/queue_decisions.csv').read_bytes())
            with (root/'first/queue_decisions.csv').open(encoding='utf-8-sig') as file:
                decisions=list(csv.DictReader(file))
            self.assertIn('ราคาขายเต็ม',decisions[0]['next_action'])
            with contextlib.redirect_stdout(io.StringIO()):
                split=finalize(raw,input_file,root/'final',review_output=root/'intermediate')
            self.assertEqual(split,summary)
            self.assertTrue((root/'final/dataset.csv').exists())
            self.assertFalse((root/'final/ambiguous.csv').exists())
            self.assertTrue((root/'intermediate/ambiguous.csv').exists())
            self.assertTrue((root/'intermediate/mac2hand_final.jsonl').exists())
            self.assertEqual((root/'final/dataset.csv').read_bytes(),(root/'first/dataset.csv').read_bytes())
            raw_file.write_text(raw_file.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'Raw changed'):
                finalize(raw,input_file,root/'invalid')

    def test_missing_information_actions_match_each_reason(self):
        source=fixture();source['detail']['title']=source['raw_listing']['name']='iPhone SE'
        source['detail']['description']='ราคา 15000 บาท'
        action=next_action(run(source))
        self.assertIn('ความจุ',action)
        self.assertIn('รุ่นย่อย SE',action)
        self.assertIn('ไม่เติมค่าเดา',action)


if __name__=='__main__':unittest.main()
