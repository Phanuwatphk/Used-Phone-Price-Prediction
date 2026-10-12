"""Offline audited feature enrichment; core dataset and raw HTML remain unchanged."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT))
from bs4 import BeautifulSoup
from script.modeling.split_dataset import dump, read_dataset, sha, write_csv, protected_output

DEFAULT_LINEAGE = ROOT / 'data/intermediate/combined/ennxo_20261005_mac2hand_20261006/audit/lineage.jsonl'
DEFAULT_MAC_DETAILS = ROOT / 'data/intermediate/mac2hand/mac2hand_20261006T172805_252838_Asia-Bangkok/finalization/mac2hand_final.jsonl'
DEFAULT_CATALOG = ROOT / 'config/modeling/iphone_release_years.json'
OPTIONAL = ['battery_health_pct', 'warranty_days', 'box_mentioned']


def extract_description(text):
    battery = set(int(v) for v in re.findall(r'(?:แบต(?:เตอรี่)?|battery(?:\s*health)?|BH)[^\d%\n]{0,15}(\d{1,3})\s*%', text, re.I))
    warranty = set(int(v) for v in re.findall(r'(?:รับประกัน|ประกัน)\s*(\d{1,3})\s*วัน', text))
    # Ambiguous claims stay missing. Absence of a box claim does not mean no box.
    box = ''
    positive_text = re.sub(r'ไม่มีกล่อง|ไร้กล่อง', '', text)
    positive = bool(re.search(r'(?:มี|พร้อม|ครบ)[^\n]{0,8}กล่อง|มีกล่อง|เครื่อง\s*[+＋]\s*กล่อง', positive_text))
    negative = bool(re.search(r'(?:ไม่มี|ไม่มีกล่อง|ไร้กล่อง)[^\n]{0,8}กล่อง|ไม่มีกล่อง', text))
    if positive != negative:
        box = 1 if positive else 0
    return {'battery_health_pct': next(iter(battery)) if len(battery) == 1 and 0 <= next(iter(battery)) <= 100 else '',
            'warranty_days': next(iter(warranty)) if len(warranty) == 1 else '', 'box_mentioned': box}


def catalog_from_html(path):
    soup = BeautifulSoup(Path(path).read_text(), 'html.parser')
    catalog = {}
    for heading in soup.find_all(['h2', 'h3']):
        name = heading.get_text(' ', strip=True)
        if not name.startswith('iPhone'): continue
        for sibling in heading.next_siblings:
            if getattr(sibling, 'name', None) in ('h2','h3'): break
            if not hasattr(sibling, 'get_text'): continue
            match = re.search(r'Year introduced:\s*(\d{4})', sibling.get_text(' ', strip=True))
            if match:
                catalog[name] = int(match[1]); break
    aliases = {'iPhone SE (1st generation)': 'iPhone SE 1', 'iPhone SE (2nd generation)': 'iPhone SE 2', 'iPhone SE (3rd generation)': 'iPhone SE 3'}
    catalog = {aliases.get(k,k): v for k,v in catalog.items()}
    if len(catalog) < 40 or catalog.get('iPhone 13') != 2021 or catalog.get('iPhone 17') != 2025:
        raise ValueError('Apple reference page did not yield the expected release-year catalog')
    return catalog


def prepare(output=None, lineage=DEFAULT_LINEAGE, mac_details=DEFAULT_MAC_DETAILS):
    config = json.loads((ROOT/'config/modeling/experiments.json#baseline').read_text())
    dataset = ROOT/config['dataset']
    output = Path(output or ROOT/'data/intermediate/modeling/asking_price_v2/enrichment')
    protected_output(output,[dataset,lineage,mac_details,DEFAULT_CATALOG])
    rows = read_dataset(dataset,config['dataset_sha256'])
    evidence = {}
    with Path(lineage).open() as handle:
        for line in handle:
            record = json.loads(line); evidence[record['listing_id']] = record
    mac_records = {}
    with Path(mac_details).open() as handle:
        for line in handle:
            record = json.loads(line); mac_records[str(record['product_id'])] = record
    enriched, coverage = [], Counter()
    for row in rows:
        record = evidence[row['listing_id']]
        original = record['original_csv_row']
        if original['source'] != row['source'] or str(original['product_id']) != row['product_id'] or float(original['price_thb']) != float(row['price_thb']):
            raise ValueError('Description lineage does not match canonical listing identity/price')
        # No price/title/raw text goes into the estimator: only these explicit condition claims.
        description = original.get('description') or ''
        if row['source'] == 'mac2hand':
            detail_record = mac_records[row['product_id']]
            if detail_record['url'] != row['url'] or float(detail_record['clean']['price_thb']) != float(row['price_thb']):
                raise ValueError('Mac2Hand full-text evidence differs from canonical listing')
            description = detail_record['original']['detail'].get('description') or ''
        added = extract_description(description)
        enriched.append({**row, **added})
        for key,value in added.items():
            if value != '': coverage[(row['source'],key)] += 1
    write_csv(output/'dataset.csv',enriched)
    dump(output/'audit.json',{'rows':len(rows),'core_dataset_unchanged':sha(dataset)==config['dataset_sha256'],
        'input_hashes':{config['dataset']:sha(dataset),str(Path(lineage).relative_to(ROOT)):sha(lineage),str(Path(mac_details).relative_to(ROOT)):sha(mac_details)},
        'optional_feature_coverage':[{ 'source':source,'field':field,'observed_rows':n} for (source,field),n in sorted(coverage.items())],
        'policy':'Explicit unique numerical claims only; ambiguous/absent values missing; full text and listing price are not model inputs.'})
    print('ENRICHED',len(rows),'rows',dict((str(k),v) for k,v in coverage.items()),flush=True)
    return output/'dataset.csv'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--lineage',type=Path,default=DEFAULT_LINEAGE)
    parser.add_argument('--apple-html',type=Path,help='Create the factual reference JSON from a cached official Apple page')
    args=parser.parse_args()
    if args.apple_html:
        dump(DEFAULT_CATALOG,{'source_url':'https://support.apple.com/en-us/108044','checked_on':'2026-10-11','html_sha256':sha(args.apple_html),
             'precision':'Year only; age is approximate. Not the age of the physical device.','release_years':catalog_from_html(args.apple_html)})
    prepare(args.output,args.lineage)

if __name__=='__main__': main()
