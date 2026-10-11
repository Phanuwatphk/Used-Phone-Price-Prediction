"""Conservative description sections with original, one-based line evidence."""
import re


def description_sections(detail):
    sections = []
    section = 'item'
    for number, original in enumerate(detail.splitlines(), 1):
        text = re.sub(r'^[\W_]+', '', original).strip()
        if not text:
            continue
        if re.match(r'(?:รายละเอียดสินค้า|สเปค(?:เครื่อง)?|ข้อมูลเครื่อง|รุ่น\s*[:：]|ความจุ\s*[:：]|ราคาขาย\s*[:：])', text):
            section = 'item'
        elif re.match(r'(?:รับเทิร์น|รับซื้อ|รับฝาก|เงื่อนไข(?:การ)?ผ่อน|การผ่อน|ผ่อนได้|วางดาวน์|เงินดาวน์|ดาวน์\s*\d|ใช้บัตรประชาชน|บัตรประชาชน|SpayLater|เครดิต)', text, re.I):
            section = 'financing'
        elif re.match(r'(?:ติดต่อ|สอบถาม|สนใจ(?:ติดต่อ|ทัก)|โทร\s*[:：\d]|เบอร์|Line\s*[:：@]|https?://|ได้ที่ร้าน|ที่อยู่ร้าน|พิกัดร้าน|นัดรับ)', text, re.I):
            section = 'contact'
        sections.append({'line': number, 'section': section, 'text': original})
    return sections


def apply_description_priority(clean, holds, notes, evidence, detail, rules, catalog,
                               normalize, model_key, text_models, storage_claims, field_holds):
    sections = description_sections(detail)
    item_lines = [line for line in sections if line['section'] == 'item']
    evidence['description_sections'] = sections
    mentions = set()
    identity = []
    for line in item_lines:
        identity_text = re.split(r'แถม|รองรับ|ใช้กับ|เคส|สายชาร์จ|หูฟัง|เครื่องเก่า|เปลี่ยนจาก|เทียบกับ|แลก|เซ็นเซอร์|กล้องหลัก', line['text'], maxsplit=1)[0]
        brands = [brand for brand, aliases in rules['brands'].items()
                  if any(re.search(r'(?<![a-z])' + re.escape(alias) + r'(?![a-z])', normalize(identity_text)) for alias in aliases)]
        if 'Redmi' in brands and 'Xiaomi' in brands:
            brands.remove('Xiaomi')
        # Accessories, compatible models and previous purchases are not item identities.
        family_heading = re.match(r'^[\W_]*(?:galaxy|note\s*\d|[asmf]\s*\d|reno\s*\d)', normalize(identity_text))
        if brands or re.search(r'รุ่น\s*[:：]', identity_text) or family_heading:
            mentions.update(brands)
            identity.append({**line, 'identity_text': identity_text})

    def replace(field, value, claims):
        previous = clean[field]
        clean[field] = value
        holds[:] = [reason for reason in holds if reason not in field_holds[field]]
        notes.append(field + '_from_description')
        if previous != value:
            notes.append(field + '_description_overrides_other_sources')
        evidence[field]['basis'] = 'description_item_section'
        evidence[field]['description_claims'] = claims
        evidence[field]['previous_candidate'] = previous

    if len(mentions) == 1:
        replace('brand', next(iter(mentions)), identity)
    elif len(mentions) > 1:
        holds.append('brand_conflict')
        evidence['brand']['description_claims'] = identity

    brand = clean['brand']
    claims = [{**line, 'model': model} for line in identity for model in text_models(line['identity_text'], brand)] if len(mentions) <= 1 else []
    keys = {model_key(claim['model'], brand) for claim in claims}
    if len(keys) == 1:
        key = next(iter(keys))
        selected = evidence['model']['selected'].get('name')
        # Same selected label is usable only if its maker agrees with the description.
        selected_brand = evidence['brand']['selected'].get('name')
        label = catalog.get((brand, key))
        if label is None and selected_brand == brand and model_key(selected, brand) == key:
            label = selected
        replace('model', label or claims[0]['model'], claims)
        if label is None:
            holds.append('model_outside_observed_catalog')
    elif len(keys) > 1:
        holds.append('model_description_conflict')
        evidence['model']['description_claims'] = claims
    elif 'brand_description_overrides_other_sources' in notes and evidence['brand']['selected'].get('name') != brand:
        # Never leave a model attached to a different maker after a brand override.
        clean['model'] = None
        holds.append('model_requires_review_after_brand_correction')

    claims = [{**line, 'source_text': line['text'], **claim} for line in item_lines
              for claim in storage_claims(line['text'], rules['storage_gb'])]
    values = {claim['value'] for claim in claims}
    if len(values) == 1:
        replace('storage_gb', next(iter(values)), claims)
    elif len(values) > 1:
        holds.append('storage_conflict')
        evidence['storage_gb']['description_claims'] = claims

    # Explicit selling-price labels remain evidence even without a currency suffix.
    prices = []
    for line in item_lines:
        for match in re.finditer(r'ราคา(?:สด|ขาย)?\s*[:=：]?\s*([0-9][0-9,]*(?:\.[0-9]+)?)', line['text']):
            prefix = line['text'][max(0, match.start() - 35):match.start()]
            if re.search(r'(?:ซื้อมา|ซื้อใหม่|มือหนึ่ง|มือ1|ดาวน์|ผ่อน|ประกัน|ค่าซ่อม|ค่าส่ง)[^\n]{0,20}$', prefix):
                continue
            if re.match(r'\s*(?:กิ๊ก|กิกะไบต์|GB|TB)', line['text'][match.end():], re.I):
                continue
            prices.append({**line, 'value': float(match[1].replace(',', ''))})
    pickup_lines = [line for line in item_lines if re.search(r'ราคา.*มารับเอง\s*[0-9]', line['text'])]
    matching_pickup = [line for line in pickup_lines if any(float(m[1].replace(',', '')) == clean['price_thb']
                      for m in re.finditer(r'มารับเอง\s*([0-9][0-9,]*(?:\.[0-9]+)?)', line['text']))]
    # A stated collection discount is a conditional offer, not an unexplained conflict.
    conditional = bool(matching_pickup) and all(claim['line'] in {line['line'] for line in matching_pickup}
                                              or claim['value'] == clean['price_thb'] for claim in prices)
    conditional = conditional and all(claim['value'] == clean['price_thb'] or
                                       any(claim['text'] in line['text'] for line in matching_pickup)
                                       for claim in evidence['price_thb']['description_claims'])
    if conditional:
        holds[:] = [reason for reason in holds if reason != 'description_price_conflict']
        notes.append('price_matches_explicit_pickup_offer')
    elif any(claim['value'] != clean['price_thb'] for claim in prices):
        holds.append('description_price_conflict')
    evidence['price_thb']['item_section_claims'] = prices
    evidence['price_thb']['pickup_offer_lines'] = pickup_lines

    # A phone title cannot hide a description that identifies a different device type.
    first = re.sub(r'^[\W_]+', '', item_lines[0]['text']).strip() if item_lines else ''
    if re.match(r'(?:ขาย\s*)?(?:ipad|tablet|macbook|router|watch|แท็บเล็ต|เราเตอร์|นาฬิกา)\b', first, re.I):
        holds.append('description_non_phone_device')
