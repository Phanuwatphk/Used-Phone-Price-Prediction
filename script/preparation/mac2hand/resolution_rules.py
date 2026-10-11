"""Evidence-based final Mac2Hand normalization and quarantine rules; no network."""
import copy
from datetime import date
import math
import re

if __package__:
    from .clean_mac2hand import normalized, models, storage_claims
else:
    from clean_mac2hand import normalized, models, storage_claims


def alias_text(text):
    text = normalized(text)
    text = re.sub(r'iphone\s*\(iphone\)\s*', 'iphone ', text)
    text = re.sub(r'(?<![a-z])(?:i\s*[- ]?phon(?:e)?|ipone|iphnoe|ipnone|ipohne)\s*(?=[0-9xs]|se\b|air\b)', 'iphone ', text)
    text = re.sub(r'(?<![a-z0-9])i(?=\d{1,2}(?:s|c|plus|pro|\s))', 'iphone ', text)
    text = re.sub(r'(?<![a-z0-9])(?:xs\s*max|xs|xr|se\s*(?:2020|2022|2016))(?=\s|\d|$)', lambda m: 'iphone '+m[0], text)
    text = re.sub(r'(?<=\d)\s*pius\b', ' plus', text)
    text = re.sub(r'ไอ\s*โฟน', 'iphone ', text)
    text = re.sub(r'(?<![a-z])ip\s*(?=\d)', 'iphone ', text)
    text = re.sub(r'iphone\s*(\d{1,2})\s+(\d{2,4})\s+(mini|pro\s*max|pro|plus)\b', r'iphone \1 \3 \2', text)
    return text


def phone_models(text, rules, catalog):
    text = alias_text(text)
    result = []
    for item in models(text):
        if item['value'] in catalog or item['value'] == 'iPhone SE':
            result.append({'brand': 'Apple', 'model': item['value'], 'text': item['text']})
    for brand, pattern in rules['non_apple_models'].items():
        for match in re.finditer(pattern, text, re.I):
            token = re.sub(r'\s+', ' ', match[1]).strip()
            token = re.sub(r'([a-z])\s+(\d)', r'\1\2', token)
            if brand == 'Samsung':
                token = re.sub(r'^z\s*(fold|flip)\s*(\d+)', lambda m: 'Z '+m[1].title()+m[2], token)
                token = token[:1].upper()+token[1:]
                token = re.sub(r'\b(ultra|plus|note|pro|prime|fe)\b', lambda m: m[1].upper() if m[1]=='fe' else m[1].title(), token)
                label = 'Galaxy '+token
            elif brand == 'Xiaomi':
                label = 'Xiaomi '+token.title()
            elif brand == 'Motorola':
                label = 'Moto '+token.upper()
            elif brand == 'Asus':
                label = 'ROG Phone '+token.upper().replace('PRO', 'Pro')
            else:
                label = re.sub(r'\b(pro|plus|ultra|flip|find|reno|pocket|mate|fold|legion|phone|duel)\b', lambda m: m[1].title(), token)
                label = re.sub(r'(?<![a-z])[afvxyng](?=\d)', lambda m: m[0].upper(), label)
            result.append({'brand': brand, 'model': label, 'text': match[0]})
    return result


def item_lines(description):
    """Remove contact/signature lines without losing item fields after shop introductions."""
    kept = []
    for line in str(description or '').splitlines():
        stripped = line.strip()
        if re.search(r'^(?:สินค้าอื่น|รายการสินค้าอื่น|ประกาศที่คล้ายกัน)', stripped):
            break
        if re.search(r'^(?:[#•✅🔻⭕ ]*)?(?:เบอร์ติดต่อ|หมายเลขโทรศัพท์|โทรศัพท์|ติดต่อ|โทร\s*[:.]|tel\s*:|line\s*:|id\s*line|line\s*id|facebook|fanpage|website|www\.|https?://|รบกวนช่วยกด|ช่วยกด\s*like|สามารถติดตาม|หรือค้นหาใน|รับซื้อ|#รับซื้อ)', stripped, re.I):
            continue
        kept.append(line)
    return '\n'.join(kept)


def price_claims(text):
    claims = []
    pattern = r'(?<![a-z])(?:ราคา\s*(?:\(price\))?\s*[:：]?|เพียง|ขอขาย(?:ที่)?|ขายที่)\s*฿?\s*([\d,]+)(?:\.\d{1,2})?'
    for match in re.finditer(pattern, text, re.I):
        prefix = text[max(0, match.start()-18):match.start()]
        if re.search(r'ส่ง|ค่าส่ง|ราคาเดิม|จาก|เปรียบเทียบ|ราคาศูนย์', prefix):
            continue
        suffix = text[match.end():match.end()+12]
        if re.match(r'\s*(?:%|งวด|เดือน|ต่อเดือน|-/เดือน|ครั้ง|รอบ|gb|g|tb)', suffix):
            continue
        value = int(match[1].replace(',', ''))
        if value >= 100:
            claims.append({'value': value, 'text': match[0]})
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if re.fullmatch(r'[💰•\s]*[\d,]+(?:\.\d{1,2})?\s*บาท.*', line) or (i==0 and re.search(r'iphone|ไอโฟน|samsung|oppo|vivo|xiaomi|realme|huawei|moto', line, re.I)):
            for match in re.finditer(r'(?<![\d,])(\d[\d,]*)\s*บาท', line):
                prefix=line[max(0,match.start()-25):match.start()]
                if re.search(r'ค่าส่ง|ส่ง|ems|ราคาเดิม|ราคาศูนย์|ราคาเต็ม',prefix,re.I):
                    continue
                value=int(match[1].replace(',', ''))
                if value>=100:claims.append({'value':value,'text':match[0], 'method':'explicit_baht_in_item_heading_or_price_line'})
    return claims


def card_price(text):
    if not text or '%' in text:
        return None
    numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{1,2})?', text)
    if len(numbers) != 1:
        return None
    return float(numbers[0].replace(',', ''))


def condition_hits(text, rules):
    hits, suppressed = [], []
    for line in text.splitlines():
        for match in re.finditer(rules['damage_pattern'], line, re.I):
            prefix = line[max(0, match.start()-60):match.start()]
            reason = None
            if re.search(rules['negation_prefix_pattern'], prefix):
                reason = 'negation_or_hypothetical'
            elif re.search(r'(?:รับประกัน|ประกัน(?:ใจ|ความพอใจ|อุบัติเหตุ)?)[^\n]{0,40}$', prefix):
                reason = 'warranty_context'
            elif re.search(r'กรณี|เผื่อ|ถ้าเกิด|เช่น\s*(?:หน้า)?$', prefix):
                reason = 'conditional_context'
            record = {'text': match[0], 'line': line}
            (suppressed if reason else hits).append({**record, **({'reason': reason} if reason else {})})
    return hits, suppressed


def capacity_candidates(text, allowed, model_claims):
    result = storage_claims(text, allowed)
    canonical = alias_text(text)
    for model in model_claims:
        needle = re.escape(normalized(model['text']))
        pattern = needle+r'\s*[/ :.-]*\s*(\d{1,4})(?!\d)\s*(?=สี|b\b|gb\b|g\b|tb\b|black\b|white\b|gold\b|silver\b|space\b|starlight\b|midnight\b|graphite\b|blue\b|green\b|pink\b|purple\b|red\b|natural\b|desert\b|สภาพ|เครื่อง|ศูนย์|ครบ|ราคา|$)'
        for match in re.finditer(pattern, canonical, re.I):
            value = int(match[1])
            if value in allowed:
                result.append({'value': value, 'text': match[0], 'method': 'abbreviated_storage_after_explicit_model'})
    return result


def resolve(row, rules, catalog):
    result = copy.deepcopy(row)
    detail, card = row['original']['detail'] or {}, row['original']['raw_listing']
    title = detail.get('title') or card.get('name', '')
    subtitle = card.get('subtitle') or ''
    body = item_lines(detail.get('description'))
    original_holds = list(row['hold_reasons'])
    reasons, exclusions, notes = [], list(row['exclusion_reasons']), []
    if re.search(rules['accessory_pattern'], normalized(title)):
        exclusions.append('accessory')
    if re.search(rules['other_device_pattern'], normalized(title)):
        exclusions.append('other_device')
    if re.search(rules['service_pattern'], title):
        exclusions.append('buy_request_or_service')
    if row['original']['extraction_errors'] or not detail:
        reasons.append('source_detail_unavailable')
    title_models = phone_models(title, rules, catalog)
    opening = '\n'.join(body.splitlines()[:4])
    opening_models = phone_models(opening, rules, catalog)
    # Explicit wishes/upgrade comparisons do not describe the sold device.
    if re.search(r'อยากเปลี่ยน|อยากได้|เปลี่ยนไปใช้|เหตุผล.*(?:แลก|เปลี่ยน)', opening):
        opening_models = [m for m in opening_models if any((m['brand'],m['model'])==(t['brand'],t['model']) for t in title_models)]
    subtitle_models = phone_models(subtitle, rules, catalog)
    selected = phone_models((detail.get('specs') or {}).get('รุ่น', ''), rules, catalog)
    model_values = {(m['brand'],m['model']) for m in title_models+selected}
    opening_values = {(m['brand'],m['model']) for m in opening_models}
    subtitle_values = {(m['brand'],m['model']) for m in subtitle_models}
    if len(opening_values)==1 and opening_values==subtitle_values:
        model_values = opening_values
        if {(m['brand'],m['model']) for m in title_models+selected} != model_values:
            notes.append('seller_description_and_subtitle_override_metadata_model')
    if len(model_values)==1:
        result['clean']['brand'], result['clean']['model'] = next(iter(model_values))
        if opening_values and not opening_values <= model_values:
            reasons.append('model_sources_conflict')
    elif not model_values:
        # An explicit, unique model in the item specification may recover an abbreviated title.
        labeled = [line for line in body.splitlines() if re.search(r'^(?:model|รุ่น|รายละเอียดสินค้า|specification)', line.strip(), re.I)]
        spec_models = phone_models('\n'.join(labeled), rules, catalog)
        if not spec_models:
            spec_models = phone_models(body, rules, catalog)
        values = {(m['brand'],m['model']) for m in spec_models}
        if len(values)==1:
            result['clean']['brand'],result['clean']['model']=next(iter(values))
            notes.append('model_from_explicit_description_specification')
        elif result['clean'].get('brand') and result['clean'].get('model') and row.get('manual_review',{}).get('disposition')=='corrected':
            notes.append('prior_evidenced_manual_model_retained')
        else:
            result['clean']['model'] = None
            reasons.append('model_missing_or_unrecognized')
    else:
        result['clean']['model'] = None
        reasons.append('multiple_models_or_model_conflict')
    if result['clean'].get('model') == 'iPhone SE':
        reasons.append('se_generation_unspecified')
    if re.search(r'\bse\s*2021\b.*se\s*3', alias_text(title)):
        reasons.append('se_year_and_generation_conflict')
    full_claims = phone_models(title, rules, catalog)
    capacities = capacity_candidates(title+'\n'+body+'\n'+'\n'.join(card.get('badges',[])), rules['storage_gb'], full_claims+opening_models)
    values = {c['value'] for c in capacities}
    seller_capacities = capacity_candidates(subtitle+'\n'+body, rules['storage_gb'], subtitle_models+opening_models)
    seller_values = {c['value'] for c in seller_capacities}
    subtitle_capacities = capacity_candidates(subtitle,rules['storage_gb'],subtitle_models)
    subtitle_storage = {c['value'] for c in subtitle_capacities}
    if len(seller_values)==1 and seller_values==subtitle_storage:
        if values != seller_values:
            notes.append('seller_description_and_subtitle_override_metadata_storage')
        values = seller_values
    if len(values)==1:
        result['clean']['storage_gb']=next(iter(values))
    elif len(values)>1:
        result['clean']['storage_gb']=None
        reasons.append('storage_multiple_or_conflicting')
    elif result['clean'].get('storage_gb') and row.get('manual_review',{}).get('disposition')=='corrected':
        notes.append('prior_evidenced_manual_storage_retained')
    else:
        result['clean']['storage_gb']=None
        reasons.append('storage_missing')
    parsed_card = card_price(card.get('price_raw'))
    detail_price = detail.get('price_thb')
    claims = price_claims(body)
    claim_values = {c['value'] for c in claims}
    price = detail_price
    if parsed_card is not None and parsed_card==detail_price:
        if claim_values and claim_values != {detail_price}:
            reasons.append('price_sources_conflict')
        elif card.get('price') != parsed_card:
            notes.append('card_price_format_recovered')
    elif parsed_card is None and '%' in str(card.get('price_raw')) and len(claim_values)==1:
        price=next(iter(claim_values));notes.append('seller_price_recovered_from_percentage_in_price_field')
    elif parsed_card is None and not card.get('price_raw') and len(claim_values)==1 and claim_values=={detail_price}:
        notes.append('price_from_agreeing_detail_and_explicit_seller_text')
    else:
        reasons.append('price_sources_conflict_or_ambiguous')
    if type(price) not in (int,float) or not math.isfinite(price) or price<100 or price in rules['price_placeholders']:
        reasons.append('price_missing_invalid_or_placeholder')
    result['clean']['price_thb']=price
    if detail.get('currency') != 'THB':
        reasons.append('currency_unverified')
    if result['clean'].get('condition') not in ('used','new'):
        reasons.append('condition_unverified')
    if not detail.get('description'):
        reasons.append('description_missing')
    try:
        published = date.fromisoformat(result['clean']['published_at'])
        if published > date.fromisoformat(card['scraped_at'][:10]):reasons.append('date_after_snapshot')
    except (TypeError,ValueError):reasons.append('published_date_missing_or_invalid')
    if result['clean']['published_at'] != card.get('published_date'):
        reasons.append('published_date_conflict')
    damage,suppressed = condition_hits(title+'\n'+subtitle+'\n'+body+'\n'+str(detail.get('condition_label_raw') or ''),rules)
    partial = [m[0] for m in re.finditer(rules['partial_price_pattern'],title+'\n'+body,re.I)]
    if damage:reasons.append('reported_damage_lock_or_contract')
    if partial:reasons.append('partial_payment_or_multiple_price_basis')
    if row.get('manual_review',{}).get('disposition')=='keep_separate':
        reasons.append('prior_manual_separate_decision')
    exclusions=sorted(set(exclusions));reasons=sorted(set(reasons))
    if exclusions: disposition='excluded'
    elif 'source_detail_unavailable' in reasons:disposition='missing_source'
    elif 'reported_damage_lock_or_contract' in reasons or 'prior_manual_separate_decision' in reasons:disposition='non_normal'
    elif any('conflict' in r or 'multiple' in r or 'partial_payment' in r for r in reasons):disposition='ambiguous'
    elif reasons:disposition='insufficient_data'
    else:disposition='accepted'
    result.update(status='accepted' if disposition=='accepted' else 'excluded' if disposition=='excluded' else 'needs_review',
                  disposition=disposition,hold_reasons=reasons,exclusion_reasons=exclusions)
    result['notes']=list(dict.fromkeys(row['notes']+notes))
    result['resolution']={'method':'deterministic_evidence_rules', 'baseline_status':row['status'],
        'baseline_hold_reasons':original_holds,'model_claims':title_models,'description_models':opening_models,
        'storage_claims':capacities,'seller_storage_claims':seller_capacities,
        'card_price_parsed':parsed_card,'detail_price':detail_price,'seller_price_claims':claims,
        'condition_hits':damage,'suppressed_condition_hits':suppressed,'item_text':body,
        'resolved_baseline_reasons':original_holds if disposition=='accepted' else []}
    return result
