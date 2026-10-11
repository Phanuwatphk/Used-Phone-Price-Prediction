import json
import unittest
import tempfile
from pathlib import Path
from script.scraper.mac2hand.mac2hand import parse_category, parse_detail, price_value, read_jsonl


def detail_html(key='123'):
    product={'@type':'Product','sku':key,'itemCondition':'https://schema.org/UsedCondition',
             'offers':{'price':15000,'priceCurrency':'THB','availability':'https://schema.org/InStock'}}
    return '<h1>iPhone 13</h1><script type="application/ld+json">'+json.dumps([product])+'''</script>
    <section aria-label="สเปคเครื่อง"><dl><dt>รุ่น</dt><dd>iPhone 13 (2021)</dd>
    <dt>ความจุ</dt><dd>128GB</dd><dt>สภาพ</dt><dd>มือสอง</dd></dl></section>
    <div><h2>รายละเอียดจากผู้ขาย</h2><p>เครื่องใช้เอง</p></div>
    <div><h2>ประกาศที่คล้ายกัน</h2><p>มือหนึ่ง 256GB</p></div>'''




class Mac2HandTests(unittest.TestCase):
    def test_category_uses_card_identity_and_pagination(self):
        flight='1:'+json.dumps({'id':123,'alt':'iPhone 13','createdAt':'2026-09-01'})
        html='<script>self.__next_f.push('+json.dumps([1,flight])+')</script>'
        html+='<h1>iPhone</h1>1 ประกาศ <a href="/detail/123/title"><div data-slot="card-content"><p>iPhone 13</p><span data-slot="badge">128GB</span><p>เครื่องใช้เอง</p><p>฿15,000</p></div></a>หน้า 1 / 2 <a href="/17/iphone?page=2">ถัดไป</a>'
        rows,meta=parse_category(html)
        self.assertEqual(rows[0]['published_date'],'2026-09-01')
        self.assertEqual(rows[0]['price'],15000)
        self.assertEqual(rows[0]['url'],'https://mac2hand.com/detail/123/')
        self.assertEqual(meta['next_url'],'https://mac2hand.com/17/iphone?page=2')
        with self.assertRaises(ValueError):parse_category('<h1>Access denied</h1>')

    def test_jsonl_preserves_unicode_line_separators_in_description(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.jsonl'
            row={'description':'บรรทัดแรก\u2028บรรทัดถัดไป\u2029ข้อความ'}
            path.write_text(json.dumps(row,ensure_ascii=False)+'\n',encoding='utf-8')
            self.assertEqual(read_jsonl(path),[row])

    def test_primary_schema_identity_and_related_exclusion(self):
        d=parse_detail(detail_html(),'123')
        self.assertEqual(d['description'],'เครื่องใช้เอง')
        self.assertEqual(d['specs']['ความจุ'],'128GB')
        with self.assertRaises(ValueError):parse_detail(detail_html('999'),'123')

    def test_price_ranges_and_placeholders_not_mistaken_for_exact_prices(self):
        self.assertEqual(price_value('฿ 15,000 บาท'),15000)
        self.assertIsNone(price_value('15,000-18,000'))
        self.assertIsNone(price_value('xxxx'))
















if __name__=='__main__':unittest.main()
