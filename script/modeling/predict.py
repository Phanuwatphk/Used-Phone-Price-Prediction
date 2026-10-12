"""Predict asking price for a listing; output coverage information alongside THB."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT))
import joblib
from script.modeling.features import FEATURES, REQUIRED, features, prices
from script.modeling.split_dataset import sha

DEFAULT_MODEL = ROOT / 'models/asking_price_v2/model.joblib'


def load_model(path=DEFAULT_MODEL):
    path = Path(path)
    metadata = json.loads(path.with_name('metadata.json').read_text())
    if sha(path) != metadata['model_hashes'][path.name]:
        raise ValueError('Model artifact checksum differs')
    # Historical artifacts reference this selector before the version-folder move.
    # Register its shared implementation without rewriting the trained artifact.
    from script.modeling import common
    sys.modules.setdefault('script.modeling.train_improved', common)
    artifact = joblib.load(path)
    version = artifact.get('feature_version', 1)
    if version not in (1, 2):
        raise ValueError('Unsupported model feature version')
    from script.modeling.model_v2.features_v2 import FEATURES as V2_FEATURES
    if artifact['feature_names'] != (V2_FEATURES if version == 2 else FEATURES):
        raise ValueError('Model feature contract differs from inference code')
    return artifact


def predict_rows(artifact, rows):
    if artifact.get('feature_version', 1) == 2:
        from script.modeling.model_v2.features_v2 import features as improved_features
        frame = improved_features(rows, artifact['reference_catalog'])
    else:
        frame = features(rows)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=4):
        predicted = prices(artifact['model'], frame)
    results = []
    for row, value in zip(rows, predicted):
        key = row['brand'] + ':' + row['model']
        flags = []
        if artifact.get('feature_version', 1) == 2:
            for field in ['battery_health_pct', 'warranty_days', 'box_mentioned']:
                if row.get(field) in (None, ''):
                    flags.append(field + '_unknown')
        if key not in artifact['fitted_models']:
            flags.append('model_unseen_in_training')
        if row['brand'] not in artifact['fitted_brands']:
            flags.append('brand_unseen_in_training')
        if not artifact['fit_date_min'] <= row['published_at'] <= artifact['fit_date_max']:
            flags.append('date_outside_training_range')
        results.append({'predicted_price_thb': round(float(value), 2), 'target': 'listing_asking_price',
                        'coverage_flags': flags, 'model': artifact['candidate_name']})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-file', type=Path, default=DEFAULT_MODEL)
    parser.add_argument('--input-csv', type=Path, help='CSV with the six required feature fields')
    parser.add_argument('--output', type=Path, help='Write predictions as JSON; otherwise print')
    for field in ['battery_health_pct', 'warranty_days', 'box_mentioned']:
        parser.add_argument('--' + field.replace('_', '-'), type=float)
    for field in REQUIRED:
        parser.add_argument('--' + field.replace('_', '-'))
    args = parser.parse_args()
    if args.input_csv:
        with args.input_csv.open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
    else:
        row = {field: getattr(args, field) for field in REQUIRED}
        if any(value is None for value in row.values()):
            parser.error('Provide --input-csv or all six listing fields')
        row.update({field: getattr(args, field) for field in ['battery_health_pct', 'warranty_days', 'box_mentioned']})
        rows = [row]
    result = predict_rows(load_model(args.model_file), rows)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        destination = args.output.resolve()
        protected = [args.model_file.resolve().parent, ROOT / 'data/raw', ROOT / 'data/final', ROOT / 'config', ROOT / 'script']
        if args.input_csv:
            protected.append(args.input_csv.resolve())
        if any(destination == p or destination.is_relative_to(p.resolve()) for p in protected):
            parser.error('Output overlaps a model or protected input')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(encoded, encoding='utf-8')
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
