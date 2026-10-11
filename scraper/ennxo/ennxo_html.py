"""Read product evidence from saved ENNXO HTML without deciding correct values."""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PRODUCT_FIELDS = ('public_id', 'name', 'condition', 'detail', 'price', 'subfields',
                  'is_sold_out', 'is_expired', 'create_date')


def embedded_products(soup):
    decoder = json.JSONDecoder()
    chunks = []
    for script in soup.select('script'):
        text = script.get_text()
        match = re.search(r'self\.__next_f\.push\(', text)
        if not match:
            continue
        try:
            value, _ = decoder.raw_decode(text, match.end())
        except ValueError:
            continue
        if isinstance(value, list) and len(value) > 1 and value[0] == 1 and isinstance(value[1], str):
            chunks.append(value[1])
    flight = ''.join(chunks)
    encoded = flight.encode('utf-8')
    references = {}
    # ENNXO's saved Flight text frames declare UTF-8 byte lengths.
    for match in re.finditer(rb'(?<![0-9a-f])([0-9a-f]+):T([0-9a-f]+),', encoded):
        size = int(match[2], 16)
        value = encoded[match.end():match.end() + size]
        if len(value) != size:
            continue
        try:
            references[match[1].decode()] = value.decode('utf-8')
        except UnicodeDecodeError:
            continue
    products = {}
    for match in re.finditer(r'\{"', flight):
        try:
            obj, _ = decoder.raw_decode(flight, match.start())
        except ValueError:
            continue
        if not isinstance(obj, dict) or obj.get('public_id') is None or 'condition' not in obj or 'subfields' not in obj:
            continue
        key = str(obj['public_id'])
        # Preserve present fields and nulls; do not import seller account objects.
        product = {field: obj[field] for field in PRODUCT_FIELDS if field in obj}
        reference = product.get('detail')
        if isinstance(reference, str) and re.fullmatch(r'\$[a-f0-9]+', reference):
            if reference[1:] not in references:
                raise ValueError(f'Unresolved description for product {key}: {reference}')
            product['detail'] = references[reference[1:]]
        else:
            reference = None
        if key in products:
            if products[key]['data'] != product:
                raise ValueError('Conflicting embedded objects for product ' + key)
            products[key]['json_offsets'].append(match.start())
        else:
            products[key] = {'data': product, 'description_reference': reference, 'json_offsets': [match.start()]}
    return products


def page_evidence(html):
    soup = BeautifulSoup(html, 'html.parser')
    cards = {}
    for index, card in enumerate(soup.select('div.product-card-top-div'), 1):
        link = card.select_one("a[href^='/product/']")
        if not link or not re.fullmatch(r'/product/\d+', link.get('href', '')):
            raise ValueError(f'Missing or invalid product URL on card {index}')
        key = link['href'].split('/')[-1]
        if key in cards:
            raise ValueError('Repeated product card on page: ' + key)
        heading = card.select_one('h2')
        title_link = heading.find_parent('a') if heading else None
        info_container = title_link.find_next_sibling('div') if title_link else None
        info_tag = info_container.select_one(':scope > div') if info_container else None
        info = info_tag.get_text(' ', strip=True) if info_tag else None
        location_image = card.select_one("img[alt='จังหวัด']")
        location = location_image.find_next_sibling('div') if location_image else None
        image = link.select_one('img')
        price_elements = [node.get_text(' ', strip=True) for node in card.find_all(['div', 'span', 'p'])
                          if not node.find(['div', 'span', 'p']) and node.get_text(strip=True).startswith('฿')]
        cards[key] = {'url': urljoin('https://www.ennxo.com', link['href']), 'card_index': index,
                      'name': heading.get_text(' ', strip=True) if heading else None,
                      'info_text': info, 'info_parts': info.split('|') if info is not None else [],
                      'price_texts': price_elements,
                      'location': location.get_text(' ', strip=True) if location else None,
                      'image_url': image.get('src') if image else None}
    return cards, embedded_products(soup)
