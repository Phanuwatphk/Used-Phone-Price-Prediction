"""Deterministic features available when a listing is published; never read its price."""
import re
from datetime import date
import numpy as np
import pandas as pd

CATEGORICAL = ['source', 'brand', 'model', 'brand_model', 'model_family', 'condition']
NUMERIC = ['storage_gb', 'log_storage', 'model_number', 'publication_days', 'publication_year', 'publication_month']
FEATURES = CATEGORICAL + NUMERIC
REQUIRED = ['source', 'brand', 'model', 'storage_gb', 'condition', 'published_at']


def validate_listing(row, require_source=True):
    required = REQUIRED if require_source else [field for field in REQUIRED if field != 'source']
    if any(row.get(k) is None or str(row[k]).strip() == '' for k in required):
        raise ValueError('Required listing fields: ' + ', '.join(required))
    if (require_source and row['source'] not in ('ennxo', 'mac2hand')) or row['condition'] not in ('used', 'new'):
        raise ValueError('Invalid source or condition')
    storage = float(row['storage_gb'])
    if not np.isfinite(storage) or storage <= 0 or not storage.is_integer():
        raise ValueError('storage_gb must be a positive integer in GB')
    day = date.fromisoformat(str(row['published_at']))
    if day.isoformat() != str(row['published_at']):
        raise ValueError('published_at must use YYYY-MM-DD')
    return int(storage), day


def features(rows, include_source=True):
    records = []
    for row in rows:
        storage, day = validate_listing(row, require_source=include_source)
        number = re.search(r'\d+(?:\.\d+)?', row['model'])
        records.append({
            **({'source': row['source']} if include_source else {}), 'brand': row['brand'], 'model': row['model'],
            'brand_model': row['brand'] + ':' + row['model'],
            'model_family': re.sub(r'\s+', ' ', re.sub(r'\d+(?:\.\d+)?', '#', row['model'])).strip(),
            'condition': row['condition'], 'storage_gb': storage, 'log_storage': np.log2(storage),
            'model_number': float(number.group()) if number else 0.0,
            'publication_days': (day - date(2010, 1, 1)).days,
            'publication_year': day.year, 'publication_month': day.month,
        })
    columns = FEATURES if include_source else [field for field in FEATURES if field != 'source']
    return pd.DataFrame(records, columns=columns)


def prices(model, frame):
    prediction = np.asarray(model.predict(frame), dtype=float).reshape(-1)
    if not np.isfinite(prediction).all():
        raise ValueError('Non-finite prediction')
    return np.maximum(prediction, 1.0)
