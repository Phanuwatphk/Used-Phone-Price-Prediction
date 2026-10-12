"""Train-only log-price trend with optional boosting of residuals.

The linear component can extrapolate calendar/age effects; category interactions
share those trends across models. No target statistics enter feature generation.
"""
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.base import clone


class FixedBlendRegressor(RegressorMixin, BaseEstimator):
    """Fixed nonnegative averaging weights selected using forward validation."""
    def __init__(self, estimators, blend_weights):
        self.estimators = estimators
        self.blend_weights = blend_weights

    def fit(self, X, y, sample_weight=None):
        if len(self.estimators) != len(self.blend_weights) or any(w < 0 for w in self.blend_weights) or sum(self.blend_weights) <= 0:
            raise ValueError('Invalid ensemble weights')
        self.estimators_ = [clone(estimator).fit(X,y,regressor__sample_weight=sample_weight) for estimator in self.estimators]
        return self

    def predict(self, X):
        predictions = np.asarray([estimator.predict(X) for estimator in self.estimators_])
        return np.average(predictions,axis=0,weights=self.blend_weights)


def trend_frame(frame):
    result = frame.copy()
    year = frame['publication_year'] + (frame['publication_month'] - 1) / 12 - 2020
    generation = frame['model_number']
    for brand in ['Apple', 'Samsung']:
        member = (frame['brand'] == brand).astype(float)
        result[brand + '_calendar'] = year * member
    for tier in ['base', 'pro', 'pro max', 'plus', 'mini', 'se', 'ultra']:
        member = ((frame['brand'] == 'Apple') & (frame['device_tier'] == tier)).astype(float)
        result[tier + '_generation'] = generation * member
        result[tier + '_age'] = frame['model_age_years'].fillna(0) * member
    return result


class TrendResidualRegressor(RegressorMixin, BaseEstimator):
    def __init__(self, alpha=10., residual_strength=0., random_state=42):
        self.alpha = alpha
        self.residual_strength = residual_strength
        self.random_state = random_state

    def fit(self, X, y, sample_weight=None):
        frame = trend_frame(X)
        categorical = list(frame.select_dtypes(include=['object', 'str']).columns)
        numeric = [column for column in frame if column not in categorical]
        self.transform_ = ColumnTransformer([
            ('category', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical),
            ('numeric', Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)),
                                  ('scale', StandardScaler())]), numeric)], sparse_threshold=0)
        values = self.transform_.fit_transform(frame)
        target = np.log(np.asarray(y, dtype=float))
        self.linear_ = Ridge(alpha=self.alpha).fit(values, target, sample_weight=sample_weight)
        self.residual_ = None
        if self.residual_strength:
            self.residual_ = HistGradientBoostingRegressor(max_iter=250, max_leaf_nodes=15,
                learning_rate=.05, l2_regularization=15., early_stopping=False,
                random_state=self.random_state).fit(values, target-self.linear_.predict(values), sample_weight=sample_weight)
        return self

    def predict(self, X):
        values = self.transform_.transform(trend_frame(X))
        result = self.linear_.predict(values)
        if self.residual_ is not None:
            result += self.residual_strength * self.residual_.predict(values)
        return np.exp(np.clip(result, -10., 20.))


class DepreciationRegressor(RegressorMixin, BaseEstimator):
    """Normalize age in training targets and restore it at inference.

Rate is a validation-selected modeling assumption, not a claimed market rate.
Unknown release years receive no age adjustment. Model identity and calendar
are excluded so the estimator shares price patterns with newly released models.
"""
    def __init__(self, rate=.3, max_leaf_nodes=15, random_state=42):
        self.rate = rate
        self.max_leaf_nodes = max_leaf_nodes
        self.random_state = random_state

    def _frame(self, X):
        return X.drop(columns=['model','brand_model','model_number','release_year',
                              'publication_days','publication_year','publication_month'])

    def fit(self, X, y, sample_weight=None):
        frame = self._frame(X)
        categorical = list(frame.select_dtypes(include=['object','str']).columns)
        numeric = [column for column in frame if column not in categorical]
        self.transform_ = ColumnTransformer([
            ('category',OneHotEncoder(handle_unknown='ignore',sparse_output=False),categorical),
            ('numeric',SimpleImputer(strategy='median',keep_empty_features=True),numeric)],sparse_threshold=0)
        values = self.transform_.fit_transform(frame)
        target = np.log(np.asarray(y,dtype=float)) + self.rate*X['model_age_years'].fillna(0).to_numpy()
        self.estimator_ = HistGradientBoostingRegressor(max_iter=400,max_leaf_nodes=self.max_leaf_nodes,
            learning_rate=.06,l2_regularization=15.,early_stopping=False,random_state=self.random_state)
        self.estimator_.fit(values,target,sample_weight=sample_weight)
        return self

    def predict(self, X):
        result = self.estimator_.predict(self.transform_.transform(self._frame(X)))
        result -= self.rate*X['model_age_years'].fillna(0).to_numpy()
        return np.exp(np.clip(result,-10.,20.))
