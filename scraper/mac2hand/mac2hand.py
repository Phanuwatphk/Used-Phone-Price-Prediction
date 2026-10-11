"""Parse Mac2Hand category cards and the primary product, preserving evidence."""
import hashlib
import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE = 'https://mac2hand.com'
CATEGORY = BASE + '/17/iphone'


def read_jsonl(path):
    # splitlines() also splits U+2028/U+2029 inside valid JSON strings.
    with open(path, encoding='utf-8') as file:
        return [json.loads(line) for line in file if line.strip()]


def flight_objects(soup):
    decoder = json.JSONDecoder()
    chunks = []
    for script in soup.select('script'):
        text = script.get_text()
        match = re.search(r'self\.__next_f\.push\(', text)
        if not match:
            continue
        try:
            item, _ = decoder.raw_decode(text, match.end())
        except ValueError:
            continue
        if isinstance(item, list) and len(item) > 1 and item[0] == 1 and isinstance(item[1], str):
            chunks.append(item[1])
    text = ''.join(chunks)
    for match in re.finditer(r'\{"', text):
        try:
            item, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(item, dict):
            yield item


def price_value(text):
    text = re.sub(r'[฿,\s]', '', text or '').replace('บาท', '')
    return float(text) if re.fullmatch(r'\d+(?:\.\d{1,2})?', text) else None


def parse_category(html):
    soup = BeautifulSoup(html, 'html.parser')
    dates = {str(o['id']): o['createdAt'] for o in flight_objects(soup)
             if 'id' in o and 'createdAt' in o and 'alt' in o}
    rows = []
    seen = set()
    for a in soup.select('a[href^="/detail/"]'):
        card = a.select_one('[data-slot="card-content"]')
        if not card:
            continue
        match = re.match(r'/detail/(\d+)(?:/|$)', a['href'])
        if not match or match[1] in seen:
            continue
        key = match[1]
        paragraphs = card.select('p')
        price_tag = next((p for p in paragraphs if p.get_text(strip=True).startswith('฿')), None)
        titles = [p.get_text(' ', strip=True) for p in paragraphs if p is not price_tag]
        if not titles:
            raise ValueError(f'Missing title for {key}')
        seen.add(key)
        image = a.select_one('img')
        rows.append({'product_id': key, 'url': BASE + '/detail/' + key + '/',
                     'listing_url': urljoin(BASE, a['href']), 'name': titles[0],
                     'subtitle': titles[1] if len(titles) > 1 else '',
                     'badges': [p.get_text(' ', strip=True) for p in card.select('[data-slot="badge"]')],
                     'price_raw': price_tag.get_text(' ', strip=True) if price_tag else None,
                     'price': price_value(price_tag.get_text()) if price_tag else None,
                     'published_date': dates.get(key),
                     'image_url': urljoin(BASE, image['src']) if image and image.get('src') else None,
                     'card_text': card.get_text(' ', strip=True)})
    text = soup.get_text(' ', strip=True)
    pagination = re.search(r'หน้า\s+(\d+)\s*/\s*([\d,]+)', text)
    count = re.search(r'iPhone\s+([\d,]+)\s+ประกาศ', text)
    if not pagination or not rows:
        raise ValueError('Category cards or pagination absent; inspect response')
    next_link = next((a['href'] for a in soup.select('a[href]') if a.get_text(strip=True) == 'ถัดไป'), None)
    return rows, {'page': int(pagination[1]), 'total_pages': int(pagination[2].replace(',', '')),
                  'advertised_records': int(count[1].replace(',', '')) if count else None,
                  'next_url': urljoin(BASE, next_link) if next_link else None}


def parse_detail(html, product_id):
    soup = BeautifulSoup(html, 'html.parser')
    product = None
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.get_text())
        except ValueError:
            continue
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict) and obj.get('@type') == 'Product' and str(obj.get('sku')) == str(product_id):
                product = obj
    heading = soup.select_one('h1')
    if not product or not heading:
        raise ValueError('Missing primary Product JSON-LD matching requested ID')
    specs = {}
    for section in soup.select('section[aria-label="สเปคเครื่อง"]'):
        for dt in section.select('dt'):
            dd = dt.find_next_sibling('dd')
            if dd:
                specs[dt.get_text(strip=True)] = dd.get_text(' ', strip=True)
    description = next((h.parent.select_one('p') for h in soup.select('h2')
                        if h.get_text(strip=True) == 'รายละเอียดจากผู้ขาย'), None)
    offers = product.get('offers') or {}
    text = heading.parent.get_text(' ', strip=True)
    condition_tag = heading.parent.select_one('svg.lucide-tag')
    condition_label = condition_tag.parent.get_text(' ', strip=True) if condition_tag else None
    date = re.search(r'ลงประกาศ\s*(\d{4}-\d{2}-\d{2})', text)
    member = re.search(r'สมาชิก\s*#\s*(\d+)', soup.get_text(' ', strip=True))
    return {'title': heading.get_text(' ', strip=True), 'specs': specs,
            'description': description.get_text('\n', strip=True) if description else None,
            'price_thb': price_value(str(offers.get('price', ''))), 'currency': offers.get('priceCurrency'),
            'condition_selected': product.get('itemCondition', offers.get('itemCondition')),
            'condition_label_raw': specs.get('สภาพ') or condition_label,
            'availability': offers.get('availability'), 'category': product.get('category'),
            'seller_key': hashlib.sha256(('mac2hand:' + member[1]).encode()).hexdigest()[:20] if member else None,
            'published_date': date[1] if date else None, 'evidence_source': 'primary Product JSON-LD sku + visible specs/description'}
