"""Collect all Mac2Hand iPhone category pages with resumable, paced requests."""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
if __package__:
    from .mac2hand import CATEGORY, parse_category, parse_detail, read_jsonl
else:
    from mac2hand import CATEGORY, parse_category, parse_detail, read_jsonl

TZ = ZoneInfo('Asia/Bangkok')


def save(path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def session():
    s = requests.Session()
    s.headers['User-Agent'] = 'Mozilla/5.0 (compatible; AcademicPhonePriceResearch/1.0)'
    s.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=2,
             status_forcelist=[429,500,502,503,504], allowed_methods=['GET'])))
    return s


def fetch(s, url, path):
    if urlparse(url).hostname not in ('mac2hand.com', 'www.mac2hand.com'):
        raise ValueError('Unexpected pagination host')
    response = s.get(url, timeout=30)
    response.raise_for_status()
    if 'text/html' not in response.headers.get('Content-Type',''):
        raise ValueError('Expected HTML response')
    path.write_text(response.text, encoding='utf-8')
    return response.text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--details', action='store_true')
    parser.add_argument('--since', help='Include details on/after this YYYY-MM-DD date')
    parser.add_argument('--all-dates', action='store_true', help='Collect details for every listing, without a lower date cutoff')
    parser.add_argument('--continue-on-error', action='store_true', help='Record individual detail failures and continue; failed records remain held')
    args = parser.parse_args()
    if args.since and args.all_dates:parser.error('--since and --all-dates are mutually exclusive')
    if args.details and (not args.resume or not (args.since or args.all_dates)):
        parser.error('--details requires --resume and either --since or --all-dates')
    raw = args.resume.resolve() if args.resume else Path(__file__).resolve().parents[3] / 'data/raw' / datetime.now(TZ).strftime('mac2hand_%Y%m%dT%H%M%S_%f_Asia-Bangkok')
    raw.mkdir(parents=True, exist_ok=True)
    (raw/'pages').mkdir(exist_ok=True)
    print('RUN', raw, flush=True)
    summary_path = raw/'mac2hand_summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {'source':'mac2hand', 'started_at':datetime.now(TZ).isoformat(), 'timezone':TZ.key}
    with session() as s:
        if args.details:
            (raw/'details').mkdir(exist_ok=True)
            rows=read_jsonl(raw/'listings.jsonl')
            # Undated listings are not silently discarded; collect them for date recovery.
            targets=[r for r in rows if args.all_dates or not r.get('published_date') or r['published_date'] >= args.since]
            manifest_file=raw/'details/manifest.json'
            manifest=json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
            for i,row in enumerate(targets,1):
                key=row['product_id'];path=raw/'details'/f'product_{key}.html'
                entry=manifest.get(key,{})
                try:
                    if not path.exists() or entry.get('status')=='failed':
                        time.sleep(2)
                        fetch(s,row['listing_url'],path)
                        entry['scraped_at']=datetime.now(TZ).isoformat()
                    detail=parse_detail(path.read_text(),key)
                    entry.update(status='ok',html_file=path.name,detail=detail)
                except requests.HTTPError as e:
                    entry.update(status='failed',error=str(e))
                    manifest[key]=entry;save(manifest_file,manifest)
                    if e.response.status_code not in (404,410) and not args.continue_on_error:raise
                except (ValueError,requests.RequestException) as e:
                    entry.update(status='failed',error=str(e));manifest[key]=entry;save(manifest_file,manifest)
                    if not args.continue_on_error:raise
                manifest[key]=entry;save(manifest_file,manifest)
                if i%25==0 or i==len(targets):print('Details',i,'/',len(targets),flush=True)
            save(raw/'details/mac2hand_detail_summary.json',{'selected':len(targets),'since':args.since,'ok':sum(manifest[r['product_id']]['status']=='ok' for r in targets),'generated_at':datetime.now(TZ).isoformat(),'timezone':TZ.key})
            return
        url=CATEGORY;page=1;rows=[];seen=set();pages=[]
        summary['complete']=False;save(summary_path,summary)
        while url:
            path=raw/'pages'/f'page_{page}.html'
            if path.exists():html=path.read_text()
            else:
                if page>1:time.sleep(2)
                html=fetch(s,url,path)
            parsed,meta=parse_category(html)
            if meta['page']!=page:raise ValueError('Pagination returned unexpected page')
            if not any(r['product_id'] not in seen for r in parsed):raise ValueError('Repeated page; stop to prevent infinite collection')
            stamp=datetime.fromtimestamp(path.stat().st_mtime,TZ).isoformat()
            for r in parsed:
                if r['product_id'] in seen:continue
                seen.add(r['product_id']);rows.append({**r,'source':'mac2hand','currency':'THB','scraped_at':stamp,'timezone':TZ.key,'page':page,'listing_page_url':url})
            pages.append(meta)
            (raw/'listings.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
            summary.update(pages=len(pages),records=len(rows),advertised_records=pages[0]['advertised_records'],advertised_pages=pages[0]['total_pages'],last_page=meta)
            save(summary_path,summary)
            if page%10==0 or not meta['next_url']:print('Pages',page,'/',meta['total_pages'],'records',len(rows),flush=True)
            url=meta['next_url'];page+=1
        summary.update(complete=True,finished_at=datetime.now(TZ).isoformat())
        save(summary_path,summary)
        print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
