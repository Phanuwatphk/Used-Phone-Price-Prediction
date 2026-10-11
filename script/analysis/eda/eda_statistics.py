"""Deterministic descriptive statistics and review candidates; never alter rows."""
from collections import Counter, defaultdict
import hashlib
import json
import math
import statistics
import unicodedata


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    lower = int(position); upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def price_stats(rows):
    prices = [r['price_thb'] for r in rows]
    return {'n': len(prices), 'min': min(prices) if prices else None,
            'q1': percentile(prices, .25), 'median': percentile(prices, .5),
            'q3': percentile(prices, .75), 'p95': percentile(prices, .95),
            'p99': percentile(prices, .99), 'max': max(prices) if prices else None,
            'mean': statistics.mean(prices) if prices else None}


def group_rows(rows, fields):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    return groups


def grouped_stats(rows, fields):
    return [{**dict(zip(fields, key)), **price_stats(group)}
            for key, group in sorted(group_rows(rows, fields).items())]


def count_table(rows, dimension):
    sources = sorted({r['source'] for r in rows})
    grouped = group_rows(rows, [dimension])
    return [{dimension: key[0], 'total': len(group),
             **{source: sum(r['source'] == source for r in group) for source in sources}}
            for key, group in sorted(grouped.items())]


def outlier_candidates(rows, rules):
    fields = rules['outlier_group_fields']; flags = []; fences = []
    eligible = skipped_small = skipped_zero = 0
    for key, group in sorted(group_rows(rows, fields).items()):
        if len(group) < rules['outlier_min_group_size']:
            skipped_small += len(group); continue
        stats = price_stats(group); iqr = stats['q3'] - stats['q1']
        if iqr == 0:
            skipped_zero += len(group); continue
        eligible += len(group)
        lower = stats['q1'] - rules['outlier_iqr_multiplier'] * iqr
        upper = stats['q3'] + rules['outlier_iqr_multiplier'] * iqr
        fence = {**dict(zip(fields, key)), 'n': len(group), 'q1': stats['q1'], 'q3': stats['q3'],
                 'median': stats['median'], 'lower_fence': lower, 'upper_fence': upper}
        fences.append(fence)
        for row in group:
            if row['price_thb'] < lower or row['price_thb'] > upper:
                flags.append({**row, 'peer_n': len(group), 'peer_median': stats['median'],
                              'lower_fence': lower, 'upper_fence': upper,
                              'direction': 'low' if row['price_thb'] < lower else 'high',
                              'next_action': 'ตรวจราคาขายเต็ม สภาพ รายละเอียด และวันประกาศ; ไม่แก้หรือลบด้วย IQR อย่างเดียว'})
    return flags, fences, {'eligible_rows': eligible, 'flagged_rows': len(flags),
                          'skipped_small_group_rows': skipped_small, 'skipped_zero_iqr_rows': skipped_zero,
                          'fence_groups': len(fences)}


def source_comparisons(rows, rules):
    fields = rules['source_comparison_fields']; comparisons = []
    for key, group in sorted(group_rows(rows, fields).items()):
        sources = group_rows(group, ['source'])
        if any(len(sources.get((s,), [])) < rules['source_comparison_min_per_source'] for s in ('ennxo', 'mac2hand')):
            continue
        a, b = price_stats(sources[('ennxo',)]), price_stats(sources[('mac2hand',)])
        comparisons.append({**dict(zip(fields, key)), 'ennxo_n': a['n'], 'mac2hand_n': b['n'],
                            'ennxo_median': a['median'], 'mac2hand_median': b['median'],
                            'ennxo_minus_mac2hand_percent': (a['median'] / b['median'] - 1) * 100})
    return comparisons


def average_ranks(values):
    ordered = sorted(range(len(values)), key=lambda index: values[index]); ranks = [0.] * len(values)
    first = 0
    while first < len(ordered):
        last = first + 1
        while last < len(ordered) and values[ordered[last]] == values[ordered[first]]:
            last += 1
        rank = (first + 1 + last) / 2
        for index in ordered[first:last]:
            ranks[index] = rank
        first = last
    return ranks


def spearman(a, b):
    if len(a) < 2 or len(a) != len(b):
        return None
    a, b = average_ranks(a), average_ranks(b)
    ma, mb = statistics.mean(a), statistics.mean(b)
    numerator = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    denominator = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return numerator / denominator if denominator else None


def text_key(text):
    return ' '.join(unicodedata.normalize('NFKC', text or '').casefold().split())


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def duplicate_candidates(rows, lineage, descriptions, rules):
    buckets = defaultdict(list); records = {r['listing_id']: r for r in rows}
    for row in rows:
        original = lineage[row['listing_id']]['original_csv_row']
        if original.get('candidate_duplicate_group'):
            buckets[('source_text_candidate', row['source'], original['candidate_duplicate_group'])].append(row['listing_id'])
        if original.get('candidate_image_group'):
            buckets[('source_image_candidate', row['source'], original['candidate_image_group'])].append(row['listing_id'])
        text = text_key(descriptions.get(row['listing_id']))
        if len(text) >= rules['duplicate_min_description_length']:
            attributes = [row[k] for k in rules['duplicate_description_fields']]
            buckets[('exact_description', digest([attributes, text]))].append(row['listing_id'])
    groups = []
    for key, ids in sorted(buckets.items()):
        ids = sorted(set(ids))
        if len(ids) < 2:
            continue
        sources = sorted({records[i]['source'] for i in ids})
        groups.append({'group_id': digest(key), 'method': key[0], 'listing_ids': ids,
                       'n': len(ids), 'sources': sources, 'cross_source': len(sources) > 1,
                       'physical_identity_confirmed': False})
    # Image-only signals can be generic shop photos; keep them out of text components.
    parents = {r['listing_id']: r['listing_id'] for r in rows}

    def find(identifier):
        while parents[identifier] != identifier:
            parents[identifier] = parents[parents[identifier]]
            identifier = parents[identifier]
        return identifier

    for group in groups:
        if group['method'] == 'source_image_candidate':
            continue
        for identifier in group['listing_ids'][1:]:
            parents[find(identifier)] = find(group['listing_ids'][0])
    components = defaultdict(list)
    for identifier in parents:
        components[find(identifier)].append(identifier)
    components = [{'component_id': digest(sorted(ids)), 'listing_ids': sorted(ids), 'n': len(ids)}
                  for ids in components.values() if len(ids) > 1]
    components.sort(key=lambda c: c['component_id'])
    return groups, components


def analyze(rows, lineage, descriptions, rules):
    flags, fences, outlier_summary = outlier_candidates(rows, rules)
    groups, components = duplicate_candidates(rows, lineage, descriptions, rules)
    comparisons = source_comparisons(rows, rules)
    correlations = []
    for source in ['combined', *sorted({r['source'] for r in rows})]:
        group = rows if source == 'combined' else [r for r in rows if r['source'] == source]
        correlations.append({'source': source, 'n': len(group),
            'price_vs_storage_spearman': spearman([r['price_thb'] for r in group], [r['storage_gb'] for r in group]),
            'price_vs_publication_year_spearman': spearman([r['price_thb'] for r in group], [r['publication_year'] for r in group])})
    flagged = {r['listing_id'] for r in flags}
    candidate_nonfirst = {i for group in components for i in group['listing_ids'][1:]}
    sensitivity = []
    for name, excluded in [('all_rows', set()), ('without_iqr_flags_diagnostic_only', flagged),
                           ('one_per_text_candidate_component_assumption_only', candidate_nonfirst)]:
        selected = [r for r in rows if r['listing_id'] not in excluded]
        sensitivity.append({'scenario': name, **price_stats(selected), 'excluded_n': len(excluded)})
    source_stats = grouped_stats(rows, ['source'])
    for item in source_stats:
        item['percent'] = item['n'] / len(rows) * 100
        selected = [r for r in rows if r['source'] == item['source']]
        item['date_min'] = min(r['published_at'] for r in selected)
        item['date_max'] = max(r['published_at'] for r in selected)
    missing = {field: sum(r.get(field) is None or r.get(field) == '' for r in rows) for field in rows[0]}
    summary = {'records': len(rows), 'source_statistics': source_stats,
        'combined_price_statistics': price_stats(rows), 'missing_values': missing,
        'brand_counts': dict(Counter(r['brand'] for r in rows)),
        'condition_counts': dict(Counter(r['condition'] for r in rows)),
        'unique_brand_model_pairs': len({(r['brand'], r['model']) for r in rows}),
        'publication_year_counts': dict(sorted(Counter(r['publication_year'] for r in rows).items())),
        'outlier_screening': outlier_summary,
        'duplicate_screening': {'method_group_counts': dict(Counter(g['method'] for g in groups)),
            'all_candidate_unique_rows': len({i for g in groups for i in g['listing_ids']}),
            'cross_source_groups': sum(g['cross_source'] for g in groups),
            'text_components': len(components), 'text_component_rows': sum(c['n'] for c in components),
            'descriptions_available': sum(bool(descriptions.get(r['listing_id'])) for r in rows),
            'descriptions_meeting_length_threshold': sum(len(text_key(descriptions.get(r['listing_id']))) >= rules['duplicate_min_description_length'] for r in rows)},
        'matched_source_comparison_groups': len(comparisons),
        'matched_source_comparison_records': sum(r['ennxo_n'] + r['mac2hand_n'] for r in comparisons),
        'sensitivity': sensitivity, 'correlations': correlations,
        'dataset_modified': False, 'deduplicated': False, 'training_performed': False}
    tables = {'source_statistics': source_stats, 'brand_counts': count_table(rows, 'brand'),
        'model_counts': [{**dict(zip(['brand', 'model', 'source'], k)), 'n': len(v)} for k, v in sorted(group_rows(rows, ['brand', 'model', 'source']).items())],
        'publication_year_counts': count_table(rows, 'publication_year'),
        'storage_counts': count_table(rows, 'storage_gb'), 'condition_counts': count_table(rows, 'condition'),
        'model_price_statistics': grouped_stats(rows, ['source', 'brand', 'model']),
        'model_storage_year_statistics': grouped_stats(rows, ['source', 'brand', 'model', 'storage_gb', 'condition', 'publication_year']),
        'source_comparisons': comparisons, 'correlations': correlations, 'sensitivity': sensitivity,
        'outlier_fences': fences}
    return summary, tables, flags, groups, components
