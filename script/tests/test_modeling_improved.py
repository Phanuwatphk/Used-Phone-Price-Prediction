"""Audited condition claims, transfer features, recency weighting and V1 compatibility."""
from datetime import date
import unittest
import tempfile
from pathlib import Path
import joblib
import numpy as np
from script.tests.test_modeling import listing
from script.modeling.model_v2.features_v2 import features
from script.modeling.model_v2.prepare_features_v2 import extract_description
from script.modeling.model_v2.train_improved import weights,build,get_frame
from script.modeling.predict import predict_rows


class ImprovedModelingTests(unittest.TestCase):
    def test_description_claims_are_explicit_and_ambiguities_stay_missing(self):
        a=extract_description('ราคา 25000 แบตเตอรี่ 87% รับประกัน 30 วัน เครื่อง+กล่อง')
        self.assertEqual(a,{'battery_health_pct':87,'warranty_days':30,'box_mentioned':1})
        self.assertEqual(extract_description('แบต 87% แบต 91%')['battery_health_pct'],'')
        self.assertEqual(extract_description('แบต 120%')['battery_health_pct'],'')
        self.assertEqual(extract_description('ขายดี 99% ราคา 20000')['battery_health_pct'],'')
        self.assertEqual(extract_description('ไม่มีกล่อง')['box_mentioned'],0)
        self.assertEqual(extract_description('สภาพดี')['box_mentioned'],'')

    def test_age_uses_frozen_reference_and_never_target(self):
        row={**listing(1),'published_at':'2024-01-01','model':'iPhone 13'}
        catalog={'iPhone 13':2021}
        x=features([row],catalog)
        self.assertEqual(x.iloc[0]['model_age_years'],3)
        self.assertTrue(x.equals(features([{**row,'price_thb':'999999'}],catalog)))
        unknown=features([{**row,'brand':'Samsung','model':'Galaxy S24'}],catalog)
        self.assertTrue(np.isnan(unknown.iloc[0]['release_year']))
        self.assertEqual(unknown.iloc[0]['release_known'],0)
        with self.assertRaises(ValueError):features([{**row,'battery_health_pct':120}],catalog)

    def test_weights_use_only_supplied_training_dates(self):
        rows=[listing(0,'2020-01-01'),listing(1,'2024-01-01')]
        w=weights(rows,2)
        self.assertAlmostEqual(w.mean(),1)
        self.assertLess(w[0],w[1])
        self.assertTrue(np.all(weights(rows,0)==1))

    def test_missing_optional_features_and_unseen_model_predict_finitely(self):
        from threadpoolctl import threadpool_limits
        rows=[listing(i) for i in range(40)]
        spec={'kind':'hist','log_target':True,'half_life':2,'transfer_only':True}
        catalog={'iPhone 12':2020,'iPhone 17':2025}
        model=build(spec,threads=1)
        with threadpool_limits(limits=1):model.fit(get_frame(spec,rows,catalog),np.array([float(r['price_thb']) for r in rows]),regressor__sample_weight=weights(rows,2))
        artifact={'model':model,'feature_version':2,'reference_catalog':catalog,'fitted_models':['Apple:iPhone 12'],'fitted_brands':['Apple'],
                  'fit_date_min':'2024-01-01','fit_date_max':'2024-01-20','candidate_name':'fixture'}
        result=predict_rows(artifact,[{**listing(41),'model':'iPhone 17','published_at':'2026-01-01'}])[0]
        self.assertGreater(result['predicted_price_thb'],0)
        self.assertIn('model_unseen_in_training',result['coverage_flags'])
        self.assertIn('battery_health_pct_unknown',result['coverage_flags'])

    def test_catboost_clone_accepts_categorical_feature_contract(self):
        from sklearn.base import clone
        spec={'kind':'catboost','log_target':True,'depth':4,'transfer_only':True}
        model=clone(build(spec,threads=1))
        self.assertIsInstance(model.regressor.named_steps['regressor'].get_params()['cat_features'],tuple)

    def test_price_objective_and_hist_parameters_reach_estimators(self):
        from sklearn.base import clone
        cat = clone(build({'kind':'catboost','loss':'MAE','iterations':300,'log_target':False},threads=1))
        self.assertEqual(cat.named_steps['regressor'].get_params()['loss_function'],'MAE')
        self.assertEqual(cat.named_steps['regressor'].get_params()['iterations'],300)
        hist = build({'kind':'hist','max_leaf_nodes':7,'min_samples_leaf':30,'max_iter':25})
        self.assertEqual(hist.named_steps['regressor'].max_leaf_nodes,7)
        self.assertEqual(hist.named_steps['regressor'].min_samples_leaf,30)

    def test_trend_learns_depreciation_and_survives_serialization(self):
        from sklearn.base import clone
        from threadpoolctl import threadpool_limits
        rows=[{**listing(i),'model':'iPhone 13','published_at':f'{2021+i//12}-{i%12+1:02d}-01'} for i in range(36)]
        frame=features(rows,{'iPhone 13':2021})
        target=20000*np.exp(-np.arange(36)*.015)
        spec={'kind':'trend','alpha':1.,'residual_strength':.5}
        model=clone(build(spec,threads=1))
        future=features([{**rows[-1],'published_at':'2024-07-01'}],{'iPhone 13':2021})
        with threadpool_limits(limits=1):
            model.fit(frame,target,regressor__sample_weight=np.ones(len(rows)))
            prediction=model.predict(future)
            self.assertTrue(np.isfinite(prediction).all())
            self.assertGreater(prediction[0],0)
            self.assertLess(prediction[0],model.predict(frame.iloc[[-1]])[0])
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'model.joblib'
                joblib.dump(model,path)
                np.testing.assert_allclose(joblib.load(path).predict(future),prediction)

    def test_age_normalization_handles_unknown_release_without_target_features(self):
        from sklearn.base import clone
        from threadpoolctl import threadpool_limits
        rows=[{**listing(i),'model':'iPhone 13','published_at':f'2023-{i%12+1:02d}-01'} for i in range(48)]
        frame=features(rows,{'iPhone 13':2021})
        spec={'kind':'depreciation','rate':.3,'max_leaf_nodes':7}
        model=clone(build(spec,threads=1))
        android=features([{**rows[0],'brand':'Samsung','model':'Galaxy S30','published_at':'2026-01-01'}],{})
        with threadpool_limits(limits=1):
            model.fit(frame,np.linspace(5000,15000,len(rows)),regressor__sample_weight=np.ones(len(rows)))
            prediction=model.predict(android)
        self.assertTrue(np.isfinite(prediction).all())
        self.assertGreater(prediction[0],0)
        changed=android.copy();changed['model']='different';changed['brand_model']='different';changed['publication_year']=2099
        self.assertTrue(model.named_steps['regressor']._frame(android).equals(model.named_steps['regressor']._frame(changed)))

    def test_ensemble_averages_component_prices_and_roundtrips(self):
        from sklearn.base import clone
        from threadpoolctl import threadpool_limits
        rows=[listing(i) for i in range(40)]
        frame=features(rows,{})
        spec={'kind':'blend','components':[{'kind':'hist','log_target':True,'max_iter':15},
              {'kind':'catboost','log_target':True,'iterations':20,'depth':3}], 'blend_weights':[.75,.25]}
        model=clone(build(spec,threads=1))
        with threadpool_limits(limits=1):
            model.fit(frame,np.array([float(r['price_thb']) for r in rows]),regressor__sample_weight=np.ones(len(rows)))
            blend=model.named_steps['regressor']
            expected=.75*blend.estimators_[0].predict(frame)+.25*blend.estimators_[1].predict(frame)
            np.testing.assert_allclose(model.predict(frame),expected)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'model.joblib';joblib.dump(model,path)
                np.testing.assert_allclose(joblib.load(path).predict(frame),expected)

if __name__=='__main__':unittest.main()
