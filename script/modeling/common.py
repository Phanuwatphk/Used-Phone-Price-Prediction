"""Shared model construction, evaluation, report tables and column selection."""
from collections import defaultdict
import numpy as np
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from script.modeling.features import CATEGORICAL, NUMERIC

def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    error = np.abs(actual - predicted)
    return {'rows': len(actual), 'mae_thb': float(mean_absolute_error(actual, predicted)),
            'rmse_thb': float(mean_squared_error(actual, predicted) ** .5),
            'median_absolute_error_thb': float(median_absolute_error(actual, predicted)),
            'r2': float(r2_score(actual, predicted)) if len(actual) > 1 and np.var(actual) > 0 else None,
            'mape_pct': float(np.mean(error / actual) * 100),
            'within_20pct': float(np.mean(error / actual <= .2)),
            'bias_thb': float(np.mean(predicted - actual))}


def build_model(spec, seed=42, threads=4, iterations=None):
    parameters = dict(spec['parameters'])
    kind = spec['kind']
    if kind == 'catboost':
        if iterations is not None:
            parameters['iterations'] = iterations
        return CatBoostRegressor(**parameters, cat_features=CATEGORICAL, random_seed=seed,
                                 thread_count=threads, eval_metric='MAE', has_time=True,
                                 allow_writing_files=False, verbose=False)
    if kind == 'median':
        estimator = DummyRegressor(strategy='median')
    elif kind == 'ridge':
        estimator = Ridge(**parameters)
    elif kind == 'extra_trees':
        estimator = ExtraTreesRegressor(**parameters, random_state=seed, n_jobs=threads)
    elif kind == 'hist_boost':
        estimator = HistGradientBoostingRegressor(**parameters, random_state=seed)
    else:
        raise ValueError('Unknown candidate: ' + kind)
    preprocessing = ColumnTransformer([
        ('categorical', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL),
        ('numeric', StandardScaler(), NUMERIC),
    ], sparse_threshold=0)
    model = Pipeline([('features', preprocessing), ('regressor', estimator)])
    if spec.get('log_target'):
        model = TransformedTargetRegressor(regressor=model, func=np.log, inverse_func=np.exp)
    return model


def group_metrics(rows, actual, predicted, fitted_models):
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        attributes = {'source': row['source'], 'brand': row['brand'], 'year': row['published_at'][:4],
                      'condition': row['condition'], 'model_coverage': 'seen' if row['brand'] + ':' + row['model'] in fitted_models else 'unseen',
                      'brand_model': row['brand'] + ':' + row['model']}
        for field, value in attributes.items():
            groups[(field, value)].append(i)
    return [{'group': field, 'value': value, **metrics(actual[idx], predicted[idx])}
            for (field, value), idx in sorted(groups.items())]


def table(headers, rows):
    return '| ' + ' | '.join(headers) + ' |\n|' + '|'.join(['---'] * len(headers)) + '|\n' + '\n'.join('| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows) + '\n'


def select_columns(frame, columns):
    return frame[columns]
