"""V2 transfer features: official release-year age plus audited optional condition claims."""
import json
from pathlib import Path
import re
import numpy as np
from script.modeling.features import features as base_features

ROOT = Path(__file__).resolve().parents[2]
CATEGORICAL = ['source','brand','model','brand_model','model_family','condition','device_tier']
NUMERIC = ['storage_gb','log_storage','model_number','publication_days','publication_year','publication_month',
           'release_year','model_age_years','release_known','battery_health_pct','battery_missing',
           'warranty_days','warranty_missing','box_mentioned','box_missing']
FEATURES = CATEGORICAL + NUMERIC
TRANSFER_DROP = ['model','brand_model','model_number']


def load_catalog():
    return json.loads((ROOT/'config/modeling/iphone_release_years.json').read_text())['release_years']


def features(rows,catalog=None):
    catalog = load_catalog() if catalog is None else catalog
    frame = base_features(rows)
    tiers=[]; years=[]; ages=[]
    for row in rows:
        model=row['model'].lower()
        tier=next((v for v in ['pro max','ultra','pro','plus','mini','fold','flip','se','air'] if re.search(r'\b'+re.escape(v)+r'\b',model)), 'base')
        tiers.append(tier)
        year = catalog.get(row['model']) if row['brand']=='Apple' else None
        years.append(float(year) if year else np.nan)
        ages.append(max(0.,float(row['published_at'][:4])+(int(row['published_at'][5:7])-1)/12-year) if year else np.nan)
    frame['device_tier']=tiers;frame['release_year']=years;frame['model_age_years']=ages;frame['release_known']=np.isfinite(years).astype(int)
    for field in ['battery_health_pct','warranty_days','box_mentioned']:
        values=[]
        for row in rows:
            raw=row.get(field)
            value=float(raw) if raw not in (None,'') else np.nan
            if np.isfinite(value) and ((field=='battery_health_pct' and not 0<=value<=100) or (field=='warranty_days' and not 0<=value<=999) or (field=='box_mentioned' and value not in (0,1))):
                raise ValueError('Invalid optional condition field: '+field)
            values.append(value)
        frame[field]=values
        frame[{'battery_health_pct':'battery_missing','warranty_days':'warranty_missing','box_mentioned':'box_missing'}[field]]=(~np.isfinite(values)).astype(int)
    return frame[FEATURES]
