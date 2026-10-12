"""Rebuild the private training CSV from public core data + condition feature sidecar."""
import argparse,csv,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
if not __package__:sys.path.insert(0,str(ROOT))
from script.modeling.split_dataset import read_dataset,sha,write_csv,protected_output


from script.artifacts import reference_json

def rebuild(config):
    dataset=ROOT/config['dataset'];core=ROOT/'data/final/dataset.csv';sidecar=ROOT/config['condition_features']
    if sha(core)!=config['core_dataset_sha256'] or sha(sidecar)!=config['condition_features_sha256']:
        raise ValueError('Core data or condition sidecar checksum differs')
    rows=read_dataset(core,config['core_dataset_sha256'])
    with sidecar.open(encoding='utf-8',newline='') as handle:extra=list(csv.DictReader(handle))
    index={r['listing_id']:r for r in extra}
    if len(index)!=len(extra) or set(index)!={r['listing_id'] for r in rows}:
        raise ValueError('Condition feature sidecar identity coverage differs')
    protected_output(dataset,[core,sidecar])
    write_csv(dataset,[{**row,**{k:v for k,v in index[row['listing_id']].items() if k!='listing_id'}} for row in rows])
    if sha(dataset)!=config['dataset_sha256']:raise ValueError('Rebuilt training input differs from frozen enriched hash')
    return dataset

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,default=ROOT/'config/modeling/current.json')
    args=parser.parse_args();print(rebuild(reference_json(args.config)))
