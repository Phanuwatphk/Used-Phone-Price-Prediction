"""Audited condition claims, transfer features, recency weighting and V1 compatibility."""
from datetime import date
import unittest
import numpy as np
from script.tests.test_modeling import listing
from script.modeling.features_v2 import features
from script.modeling.prepare_features_v2 import extract_description
from script.modeling.train_improved import weights,build,get_frame
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

if __name__=='__main__':unittest.main()
