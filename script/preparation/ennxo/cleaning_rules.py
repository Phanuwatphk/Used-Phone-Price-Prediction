"""Deterministic ENNXO checks. No network, statistical imputation or AI decisions."""
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime

if __package__:
    from .description_sections import apply_description_priority
else:
    from description_sections import apply_description_priority


def fingerprint(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def normalized(text):
    text = unicodedata.normalize('NFKC', str(text or '')).casefold()
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', ' ', text)
    for before, after in [('i phone', 'iphone'), ('ไอโฟน', 'iphone'), ('โปรแม็กซ์', 'promax'), ('โปรแมกซ์', 'promax'), ('โปรแม็ค', 'promax'), ('แม็กซ์', 'max'), ('มินิ', 'mini'), ('โปร', 'pro'), ('พลัส', 'plus'), ('+', 'plus')]:
        text = text.replace(before, after)
    text = re.sub(r'(samsung|oppo|vivo|huawei|realme|xiaomi|redmi)(?=[a-z])', r'\1 ', text)
    text = re.sub(r'iphone(?=se|xs|xr|x\b)', 'iphone ', text)
    return text


def model_key(text, brand):
    text = normalized(text)
    text = re.sub(r'\b5\s*g\b', '', text)
    text = re.sub(r'(?:samsung|galaxy|iphone|apple|oppo|vivo|xiaomi|redmi|realme|huawei|nokia|one\s*plus|google|honor)', '', text)
    text = re.sub(r'[^a-z0-9]', '', text)
    if brand == 'Samsung' and text.startswith(('zfold', 'zflip')):
        text = text[1:]
    return text


def text_models(text, brand):
    """Read explicit model tokens; does not certify real-world model existence."""
    text = normalized(text)
    text = re.sub(r'5\s*g\b', ' ', text)
    if brand != 'Apple':
        text = re.sub(r'(samsung|oppo|vivo|realme|huawei|honor)', r'\1 ', text)
    patterns = {
        'Apple': r'(?:iphone|ไอโฟน)\s*(?:se(?:\s*\(?(?:20(?:16|20|22)|[123])\)?)?|\d{1,2}(?:\s*(?:pro\s*max|pro|plus|mini|air|[ces])(?![a-z]))?)',
        'Samsung': r'(?<![a-z0-9])(?:galaxy\s*)?(?:z\s*)?(?:fold\s*\d{1,2}|flip\s*\d{1,2}|note\s*\d{1,2}(?:\s*(?:ultra|plus|lite))?|[jasmf]\s*\d{1,3}(?:s)?(?:\s*(?:ultra|plus|lite|fe|core|prime|pro))?)(?![a-z0-9])',
        'Oppo': r'(?<![a-z0-9])(?:reno\s*\d{1,2}(?:\s*(?:pro\s*plus|pro|z|f))?|find\s*[nx]\s*\d{1,2}(?:\s*(?:ultra|pro|flip))?|[af]\s*\d{1,2}(?:s|k|x)?(?:\s*(?:pro|plus|lite))?)(?![a-z0-9])',
        'Vivo': r'(?<![a-z0-9])(?:x\s*fold\s*\d{1,2}|[vxy]\s*\d{1,3}(?:e|i|s|t|c)?(?:\s*(?:pro\s*plus|pro|plus|lite))?)(?![a-z0-9])',
        'Redmi': r'(?:redmi\s*)?note\s*\d{1,2}(?:\s*(?:pro\s*plus|pro|s))?(?![a-z0-9])|redmi\s*\d{1,2}[ac]?(?![a-z0-9])',
        'Xiaomi': r'(?<![a-z0-9])(?:(?:xiaomi|mi)\s*\d{1,2}(?:t)?(?:\s*(?:ultra|pro|lite))?|(?:xiaomi\s*)?civi\s*\d{1,2}|poco\s*[fmxc]\s*\d{1,2}(?:\s*pro)?)(?![a-z0-9])',
        'Realme': r'(?<![a-z0-9])(?:realme\s*(?:gt(?:\s*(?:neo\s*\d{1,2}t?|master\s*edition|\d{1,2}(?:\s*pro)?))?|note\s*\d{1,2}|[cnx]\s*\d{1,2}(?:s|i)?(?:\s*pro)?|\d{1,2}(?:t|i)?(?:\s*(?:pro\s*plus|pro))?))(?![a-z0-9])',
        'Huawei': r'(?<![a-z0-9])(?:nova\s*\d{1,2}(?:i|t)?|mate\s*x?\s*\d{1,2}|[py]\s*\d{1,2}(?:\s*prime\s*20\d{2})?)(?:\s*(?:pro|lite))?(?![a-z0-9])',
        'OnePlus': r'one\s*plus\s*(?:\d{1,2}t?(?:\s*pro)?|open|nord\s*\w+)',
        'Google': r'pixel\s*\d{1,2}a?(?:\s*(?:pro\s*xl|pro|xl))?',
        'Honor': r'honor\s*(?:x\s*)?\d{1,3}(?:\s*(?:pro|lite))?',
        'Infinix': r'(?:hot|smart|note|zero)\s*\.?\s*\d{1,2}\s*(?:i|pro|plus|play)?',
        'Sony': r'xperia\s*\d{1,2}\s*(?:vii|vi|iv|iii|ii|v|i)(?![a-z])',
        'YESPHONE': r'yesphone\s*s\s*\d{1,2}\s*(?:cool)?',
        'Nokia': r'(?:nokia|โนเกีย)\s*(?:[ng]\s*\d{1,3}i?|\d{3,4})(?:\s*(?:plus|classic))?'
    }
    if brand not in patterns:
        return []
    return sorted({m.group().strip() for m in re.finditer(patterns[brand], text, re.I)})


def positive_hits(text, pattern, rules):
    return [m.group() for m in re.finditer(pattern, text, re.I)
            if not re.search(rules['negation_suffix_pattern'], text[max(0, m.start() - 18):m.start()])]


def storage_claims(text, allowed):
    """Only explicit ROM/storage/GB/TB and RAM/ROM pairs; ignore RAM and SD."""
    text = unicodedata.normalize('NFKC', text)
    claims = []
    spans = []
    for m in re.finditer(r'(?<!\d)(\d{1,2})\s*/\s*(\d{2,4})(?!\d)', text):
        value = int(m[2])
        if value in allowed:
            claims.append({'value': value, 'text': m.group()})
            spans.append(m.span())
    pattern = r'(?<!\d)(\d{1,4})\s*(gb|g|tb|กิ๊ก|กิกะไบต์)(?![a-z])|(?:rom|รอม|ความจุ|ความจำเครื่อง|storage)\s*[):=]*\s*(\d{1,4})(?!\d)\s*(gb|g|tb)?'
    for m in re.finditer(pattern, text, re.I):
        if any(m.start() < b and m.end() > a for a, b in spans):
            continue
        prefix = text[max(0, m.start() - 120):m.start()].split('\n')[-1]
        suffix = text[m.end():m.end() + 12]
        labels = list(re.finditer(r'rom|รอม|storage|ความจุ|หน่วยความจำภายใน|ram|แรม|micro\s*sd|\bsd\b|memory\s*card|เมมโมรี่|หน่วยความจำภายนอก', prefix, re.I))
        explicit_rom = bool(m[3])
        last_label = labels[-1].group().casefold() if labels else ''
        nonstorage_label = bool(last_label and not re.fullmatch(r'rom|รอม|storage|ความจุ|หน่วยความจำภายใน', last_label, re.I))
        expansion = re.search(r'up\s*to|ขยาย(?:ความจุ|หน่วยความจำ)?|เพิ่ม(?:เมม|หน่วยความจำ)|รองรับการเพิ่ม', prefix, re.I)
        if not explicit_rom and (nonstorage_label or expansion or re.match(r'\s*(?:ram|แรม)(?![a-z])', suffix, re.I)):
            continue
        value = int(m[1] or m[3]) * (1024 if (m[2] or m[4] or '').lower() == 'tb' else 1)
        if value in allowed:
            claims.append({'value': value, 'text': m.group()})
    return claims


def clean_row(row, rules, catalog):
    product, card, raw = row['embedded_product'], row['card'], row['raw_listing']
    sub = product.get('subfields') or {}
    title = str(product.get('name') or '')
    card_title = str(card.get('name') or '')
    detail = str(product.get('detail') or '')
    # Descriptions can contain shop signatures and other stock; title is the model anchor.
    titles = '\n'.join(dict.fromkeys([title, card_title]))
    opening = '\n'.join(detail.splitlines()[:4])[:500]
    item_text = titles + '\n' + opening
    holds, excludes, notes, evidence = [], [], [], {}
    clean = {'brand': None, 'model': None, 'storage_gb': None, 'condition': product.get('condition'),
             'price_thb': product.get('price'), 'published_at': product.get('create_date')}
    maker = sub.get('maker') or {}
    selected_brand = maker.get('name') if maker.get('slug') != 'others' and maker.get('name') in rules['brands'] else None
    mentions = []
    for brand, aliases in rules['brands'].items():
        if any(re.search(r'(?<![a-z])' + re.escape(alias) + r'(?![a-z])', normalized(titles), re.I) for alias in aliases):
            mentions.append(brand)
    # Redmi is a product brand; mentioning its parent company is compatible.
    if 'Redmi' in mentions and 'Xiaomi' in mentions:
        mentions.remove('Xiaomi')
    if selected_brand == 'Xiaomi' and mentions == ['Redmi']:
        notes.append('xiaomi_redmi_brand_taxonomy')
        mentions = ['Xiaomi']
    clean['brand'] = selected_brand or (mentions[0] if len(mentions) == 1 else None)
    evidence['brand'] = {'selected': maker, 'title_mentions': mentions, 'basis': 'embedded_maker' if selected_brand else 'explicit_title'}
    if not clean['brand']:
        holds.append('brand_missing_or_ambiguous')
    elif any(b != clean['brand'] for b in mentions):
        holds.append('brand_conflict')
    model = sub.get('model') or {}
    selected_model = model.get('name') if model.get('slug') != 'others' and model.get('name') not in (None, '', 'อื่นๆ') else None
    brand = clean['brand']
    title_models = text_models(titles, brand)
    keys = {model_key(m, brand) for m in title_models}
    selected_key = model_key(selected_model, brand) if selected_model else None
    clean['model'] = selected_model
    if len(keys) > 1:
        holds.append('multiple_title_models')
    elif selected_model and keys and selected_key not in keys:
        holds.append('model_conflict')
    elif not selected_model and len(keys) == 1:
        key = next(iter(keys))
        clean['model'] = catalog.get((brand, key), title_models[0])
        notes.append('model_from_explicit_title')
        if (brand, key) not in catalog:
            holds.append('model_outside_observed_catalog')
    elif not selected_model:
        holds.append('model_missing_or_ambiguous')
    elif not keys:
        # Unsupported model families: literal selected label must appear in title.
        compact_title = re.sub(r'[^a-z0-9]', '', normalized(titles))
        if not selected_key or selected_key not in compact_title:
            holds.append('selected_model_not_confirmed_in_title')
    detail_models = text_models(opening, brand)
    detail_keys = {model_key(m, brand) for m in detail_models}
    effective_key = model_key(clean['model'], brand) if clean['model'] else None
    if detail_keys and effective_key and any(k != effective_key for k in detail_keys):
        holds.append('model_description_conflict')
    evidence['model'] = {'selected': model, 'title_claims': title_models, 'description_opening_claims': detail_models}
    capacity = sub.get('capacity')
    clean['storage_gb'] = capacity if type(capacity) is int and capacity in rules['storage_gb'] else None
    claims = storage_claims(titles + '\n' + detail, rules['storage_gb'])
    values = {c['value'] for c in claims}
    if len(values) > 1 or values and clean['storage_gb'] is not None and values != {clean['storage_gb']}:
        holds.append('storage_conflict')
    elif clean['storage_gb'] is None and len(values) == 1:
        clean['storage_gb'] = next(iter(values))
        notes.append('storage_from_explicit_text')
    elif clean['storage_gb'] is None:
        holds.append('storage_missing')
    elif not claims:
        notes.append('storage_from_selected_field_only')
        if clean['storage_gb'] == 8 and brand != 'Nokia':
            holds.append('possible_ram_in_selected_storage')
    evidence['storage_gb'] = {'selected': capacity, 'explicit_claims': claims}
    price = clean['price_thb']
    if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
        holds.append('invalid_price')
    elif price in rules['price_placeholders']:
        holds.append('possible_placeholder_price')
    if price != raw.get('price'):
        holds.append('price_source_conflict')
    card_prices = card.get('price_texts') or []
    if len(card_prices) != 1 or re.sub(r'[^0-9.]', '', card_prices[0]) != str(price).removesuffix('.0'):
        holds.append('card_price_conflict')
    if re.search(rules['partial_price_pattern'], item_text, re.I):
        holds.append('possible_partial_payment_price')
    price_claims = []
    for m in re.finditer(r'(?:ราคา|ขาย|ปล่อย|เหลือ)\s*[:=]?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*[.\-]*\s*(?:บาท|บ\.|฿)', detail):
        prefix = detail[max(0, m.start() - 35):m.start()]
        if re.search(r'(?:ซื้อมา|ซื้อใหม่|มือหนึ่ง|มือ1|ดาวน์|ผ่อน|ประกัน|ค่าซ่อม|ค่าส่ง)[^\n]{0,20}$', prefix):
            continue
        value = float(m[1].replace(',', ''))
        price_claims.append({'value': value, 'text': m.group()})
    if any(c['value'] != price for c in price_claims):
        holds.append('description_price_conflict')
    evidence['price_thb'] = {'selected': price, 'card': card_prices, 'description_claims': price_claims}
    if re.search(r'ขายคู่|ขายเป็นคู่|ขายเป็นชุด|เหมารวม|ยกชุด|ราคาต่อชุด|ราคาทั้งชุด', titles + '\n' + detail):
        holds.append('possible_bundle')
    scope_title = re.sub(r'^[^\w]+', '', title).strip()
    if re.search(rules['accessory_title_pattern'], scope_title, re.I):
        excludes.append('accessory_or_part')
    if re.search(rules['other_device_title_pattern'], scope_title, re.I):
        excludes.append('other_device')
    if re.search(rules['service_title_pattern'], scope_title, re.I):
        excludes.append('service_advertisement')
    damage = positive_hits(detail + '\n' + titles, rules['damage_pattern'], rules)
    if damage:
        holds.append('reported_damage_or_lock')
    new_claims = [m.group() for m in re.finditer(rules['new_claim_pattern'], item_text)
                  if not re.search(rules['negation_suffix_pattern'], item_text[max(0, m.start() - 18):m.start()])
                  and not re.search(rules['new_claim_context_ignore_pattern'], item_text[max(0, m.start() - 25):m.start()])
                  and not re.search(rules['new_claim_suffix_ignore_pattern'], item_text[m.end():m.end() + 15])]
    used_claims = positive_hits(item_text, rules['used_claim_pattern'], rules)
    accepted_conditions = rules.get('accepted_conditions', ['used'])
    conflict_action = rules.get('condition_text_conflict_action', 'hold')
    if clean['condition'] == 'new' and 'new' not in accepted_conditions:
        if used_claims:
            holds.append('condition_conflict')
        else:
            excludes.append('selected_new_outside_used_scope')
    elif clean['condition'] not in accepted_conditions:
        holds.append('condition_missing_or_unknown')
    else:
        if clean['condition'] == 'new':
            notes.append('selected_new_included_by_scope')
        if (clean['condition'] == 'used' and new_claims) or (clean['condition'] == 'new' and used_claims):
            if conflict_action == 'note':
                notes.append('seller_condition_text_disagrees')
            else:
                holds.append('condition_conflict')
    evidence['condition'] = {'selected': clean['condition'], 'new_claims': new_claims, 'used_claims': used_claims, 'damage_claims': damage}
    if rules.get('field_source_priority') == 'description_first':
        apply_description_priority(clean, holds, notes, evidence, detail, rules, catalog,
                                   normalized, model_key, text_models, storage_claims, FIELD_HOLDS)
    try:
        date = datetime.fromisoformat(clean['published_at'].replace('Z', '+00:00'))
        scraped = datetime.fromisoformat(raw['scraped_at'])
        if date.tzinfo is None or date > scraped:
            holds.append('invalid_or_future_publication_date')
    except (ValueError, TypeError, KeyError, AttributeError):
        holds.append('missing_or_invalid_publication_date')
    if not title.strip() or not detail.strip():
        holds.append('missing_title_or_description')
    return {'url': row['url'], 'product_id': row['product_id'], 'source': row['source'], 'clean': clean,
            'status': 'excluded' if excludes else 'needs_review' if holds else 'accepted',
            'hold_reasons': sorted(set(holds)), 'exclusion_reasons': sorted(set(excludes)),
            'notes': sorted(set(notes)), 'evidence': evidence, 'input_sha256': fingerprint(row), 'original': row}


FIELD_HOLDS = {
    'brand': {'brand_missing_or_ambiguous', 'brand_conflict'},
    'model': {'multiple_title_models', 'model_conflict', 'model_missing_or_ambiguous', 'selected_model_not_confirmed_in_title', 'model_description_conflict', 'model_outside_observed_catalog', 'model_requires_review_after_brand_correction', 'reviewed_identity_conflict'},
    'storage_gb': {'storage_missing', 'storage_conflict', 'possible_ram_in_selected_storage', 'reviewed_storage_unconfirmed'},
    'condition': {'condition_conflict', 'condition_missing_or_unknown'},
    'price_thb': {'invalid_price', 'possible_placeholder_price', 'price_source_conflict', 'card_price_conflict', 'description_price_conflict', 'reviewed_price_unconfirmed'},
    'published_at': {'invalid_or_future_publication_date', 'missing_or_invalid_publication_date'}
}


def apply_correction(result, entry, rules):
    """A reviewed field clears only that field's reasons; unrelated holds survive."""
    if entry.get('input_sha256') != result['input_sha256']:
        raise ValueError('Correction evidence changed: ' + result['url'])
    for key in ('reason', 'reviewer', 'evidence'):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise ValueError('Correction requires ' + key)
    action = entry.get('action')
    if action not in ('exclude', 'correct'):
        raise ValueError('Correction action must be exclude or correct')
    if action == 'exclude':
        result['exclusion_reasons'].append('reviewed_exclusion')
    else:
        values = entry.get('values')
        resolved = entry.get('resolved_reasons', [])
        additional = entry.get('additional_hold_reasons', [])
        allowed_additional = {'reviewed_storage_unconfirmed', 'reviewed_identity_conflict',
                              'reviewed_price_unconfirmed', 'reported_damage_or_lock', 'possible_bundle'}
        if not isinstance(additional, list) or any(r not in allowed_additional for r in additional):
            raise ValueError('Invalid additional reviewed holds')
        if not isinstance(resolved, list) or any(r not in result['hold_reasons'] for r in resolved):
            raise ValueError('Resolved reasons must name existing holds')
        if not isinstance(values, dict) or not (values or resolved or additional) or set(values) - set(FIELD_HOLDS):
            raise ValueError('Invalid correction fields')
        for field, value in values.items():
            if field == 'brand' and value not in rules['brands']:
                raise ValueError('Invalid corrected brand')
            if field == 'model' and (not isinstance(value, str) or not value.strip()):
                raise ValueError('Invalid corrected model')
            if field == 'storage_gb' and (type(value) is not int or value not in rules['storage_gb']):
                raise ValueError('Invalid corrected storage')
            if field == 'condition' and value not in ('used', 'new'):
                raise ValueError('Invalid corrected condition')
            if field == 'price_thb' and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                raise ValueError('Invalid corrected price')
            if field == 'published_at':
                try:
                    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    scraped = datetime.fromisoformat(result['original']['raw_listing']['scraped_at'])
                    if date.tzinfo is None or date > scraped:
                        raise ValueError('Invalid corrected publication date')
                except (AttributeError, TypeError):
                    raise ValueError('Invalid corrected publication date') from None
            result['clean'][field] = value
            result['hold_reasons'] = [r for r in result['hold_reasons'] if r not in FIELD_HOLDS[field]]
        if 'condition' in values:
            result['exclusion_reasons'] = [r for r in result['exclusion_reasons'] if r != 'selected_new_outside_used_scope']
            if values['condition'] == 'new' and 'new' not in rules.get('accepted_conditions', ['used']):
                result['exclusion_reasons'].append('selected_new_outside_used_scope')
        # Changing the brand without explicitly reviewing the model invalidates its interpretation.
        if 'brand' in values and 'model' not in values:
            result['hold_reasons'].append('model_requires_review_after_brand_correction')
        result['hold_reasons'] = [r for r in result['hold_reasons'] if r not in resolved]
        result['hold_reasons'] = sorted(set(result['hold_reasons']) | set(additional))
    result['review_correction'] = entry
    result['status'] = 'excluded' if result['exclusion_reasons'] else 'needs_review' if result['hold_reasons'] else 'accepted'
