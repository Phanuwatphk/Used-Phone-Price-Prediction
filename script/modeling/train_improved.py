"""V2 rolling temporal selection, retrospective comparison, and full-data deployment fit."""
import argparse,csv
from datetime import datetime,timezone
import importlib.metadata
import json
from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[2]
if not __package__: sys.path.insert(0,str(ROOT))
import joblib
import numpy as np
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer,TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from threadpoolctl import threadpool_limits
from script.modeling import features_v2
from script.modeling.features import features as original_features,prices
from script.modeling.split_dataset import read_dataset,sha,dump,write_csv,protected_output
from script.modeling.train_models import build_model as original_model,metrics,group_metrics

DEFAULT_CONFIG=ROOT/'config/modeling/improved.json'


def weights(rows,half_life):
    if not half_life:return np.ones(len(rows))
    dates=np.array([np.datetime64(r['published_at'],'D').astype(int) for r in rows])
    w=np.maximum(.01,2.**(-(dates.max()-dates)/365.25/half_life))
    return w/w.mean()


def build(spec,seed=42,threads=4):
    if spec['kind']=='v1':
        return original_model({'kind':'hist_boost','log_target':True,'parameters':{'max_iter':350,'max_leaf_nodes':31,'learning_rate':.06,'l2_regularization':10.,'early_stopping':False}},seed,threads)
    categorical=[c for c in features_v2.CATEGORICAL if not spec.get('transfer_only') or c not in features_v2.TRANSFER_DROP]
    numeric=[c for c in features_v2.NUMERIC if not spec.get('transfer_only') or c not in features_v2.TRANSFER_DROP]
    if spec['kind']=='catboost':
        # CatBoost cannot drop columns via cat_features, so use a trained column selector below.
        estimator=CatBoostRegressor(iterations=800,depth=spec.get('depth',6),learning_rate=.045,loss_function='RMSE',
                                  cat_features=tuple(categorical),random_seed=seed,thread_count=threads,has_time=True,verbose=False,allow_writing_files=False)
        from sklearn.preprocessing import FunctionTransformer
        from script.modeling.train_improved import select_columns
        model=Pipeline([('selection',FunctionTransformer(select_columns,kw_args={'columns':categorical+numeric})),('regressor',estimator)])
    else:
        transform=ColumnTransformer([('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=False),categorical),
                      ('numeric',Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler())]),numeric)],sparse_threshold=0)
        model=Pipeline([('features',transform),('regressor',HistGradientBoostingRegressor(loss=spec.get('loss','squared_error'),max_iter=400,
              max_leaf_nodes=31,learning_rate=.07,l2_regularization=8.,early_stopping=False,random_state=seed))])
    return TransformedTargetRegressor(regressor=model,func=np.log,inverse_func=np.exp) if spec.get('log_target') else model


def select_columns(frame,columns):
    return frame[columns]


def get_frame(spec,rows,catalog):
    return original_features(rows) if spec['kind']=='v1' else features_v2.features(rows,catalog)


def fit(spec,rows,catalog,config):
    model=build(spec,config['seed'],config['threads'])
    frame=get_frame(spec,rows,catalog)
    target=np.array([float(r['price_thb']) for r in rows])
    with threadpool_limits(limits=config['threads']):
        model.fit(frame,target,regressor__sample_weight=weights(rows,spec.get('half_life',0)))
    return model


def forecast(model,spec,rows,catalog,threads=4):
    with threadpool_limits(limits=threads):return prices(model,get_frame(spec,rows,catalog))


def artifact(model,spec,rows,catalog,dataset_hash):
    return {'model':model,'feature_version':1 if spec['kind']=='v1' else 2,
            'feature_names':list(get_frame(spec,rows[:1],catalog).columns),'reference_catalog':catalog,
            'fitted_models':sorted({r['brand']+':'+r['model'] for r in rows}),
            'fitted_brands':sorted({r['brand'] for r in rows}),'fit_date_min':min(r['published_at'] for r in rows),
            'fit_date_max':max(r['published_at'] for r in rows),'dataset_sha256':dataset_hash,'candidate_name':spec['name']}


def run(config_path=DEFAULT_CONFIG, resume=False):
    config_path=Path(config_path).resolve();config=json.loads(config_path.read_text())
    start=time.monotonic();run_name=config['run']
    report=ROOT/'reports/modeling'/run_name;private=ROOT/'data/intermediate/modeling'/run_name;modeldir=ROOT/'models'/run_name
    dataset=ROOT/config['dataset'];catalog_path=ROOT/config['catalog']
    for output in [report,private/'evaluation',modeldir]: protected_output(output,[config_path,dataset,catalog_path])
    for output in [report/'tables',private/'evaluation',modeldir]:output.mkdir(parents=True,exist_ok=True)
    if not dataset.exists():
        from script.modeling.rebuild_features_v2 import rebuild
        rebuild(config)
    rows=sorted(read_dataset(dataset,config['dataset_sha256']),key=lambda r:(r['published_at'],r['listing_id']))
    if len(rows)!=config['expected_rows']:raise ValueError('Enriched row count mismatch')
    catalog=json.loads(catalog_path.read_text())['release_years']
    if sha(catalog_path)!=config['catalog_sha256']:raise ValueError('Catalog checksum mismatch')
    core=ROOT/'data/final/dataset.csv';core_hash=sha(core)
    if core_hash!=config['core_dataset_sha256']:raise ValueError('Canonical data changed')
    folds=[]
    for interval in config['folds']:
        training=[r for r in rows if r['published_at']<interval['start']]
        validation=[r for r in rows if interval['start']<=r['published_at']<=interval['end']]
        if not training or not validation:raise ValueError('Empty fold')
        folds.append((training,validation))
    previous_config = json.loads((report/'config.json').read_text()) if resume and (report/'config.json').exists() else None
    if previous_config:
        for key in ['dataset_sha256','core_dataset_sha256','catalog_sha256','seed','threads','folds','candidates']:
            if previous_config[key] != config[key]:
                raise ValueError('Cannot resume after changing learning configuration: ' + key)
    dump(report/'config.json',config)
    dump(report/'folds.json',[{'fold':i+1,'train_rows':len(a),'validation_rows':len(b),'train_max':a[-1]['published_at'],
                             'validation_min':b[0]['published_at'],'validation_max':b[-1]['published_at']} for i,(a,b) in enumerate(folds)])
    comparisons=[];fold_results=[];best=None
    if previous_config:
        def cached(path, text_fields):
            with path.open() as handle:
                return [{k:(v if k in text_fields else None if v=='' else float(v)) for k,v in row.items()} for row in csv.DictReader(handle)]
        comparisons=cached(report/'tables/validation_comparison.csv', ['name'])
        fold_results=cached(report/'tables/fold_metrics.csv', ['candidate'])
        if len(fold_results) != len(comparisons)*len(folds):
            raise ValueError('Incomplete cached fold results')
        for index,score in enumerate(comparisons):
            spec=config['candidates'][index]
            if score['name']!=spec['name']: raise ValueError('Cached candidate order differs')
            if best is None or (score['mae_thb'],spec['name'])<(best[1]['mae_thb'],best[0]['name']):best=(spec,score)
        print('RESUME',len(comparisons),'completed candidates verified',flush=True)
    completed_candidates = len(comparisons)
    for i,spec in enumerate(config['candidates'],1):
        if i <= completed_candidates: continue
        print(f'FIT {i}/{len(config["candidates"])} {spec["name"]}',flush=True);clock=time.monotonic();actuals=[];predictions=[]
        for index,(training,validation) in enumerate(folds):
            model=fit(spec,training,catalog,config);pred=forecast(model,spec,validation,catalog,config['threads'])
            actual=np.array([float(r['price_thb']) for r in validation])
            actuals.extend(actual);predictions.extend(pred)
            fold_results.append({'candidate':spec['name'],'fold':index+1,**metrics(actual,pred)})
        score={'name':spec['name'],**metrics(actuals,predictions),'fit_seconds':round(time.monotonic()-clock,2)}
        comparisons.append(score);write_csv(report/'tables/validation_comparison.csv',comparisons);write_csv(report/'tables/fold_metrics.csv',fold_results)
        dump(report/'progress.json',{'phase':'temporal_validation','completed':i,'total':len(config['candidates']),'last':score})
        print(f'POOLED VALIDATION MAE {score["mae_thb"]:.2f} ({score["fit_seconds"]:.1f}s)',flush=True)
        if best is None or (score['mae_thb'],spec['name'])<(best[1]['mae_thb'],best[0]['name']):best=(spec,score)
    spec,validation=best
    # The former v1 test is already inspected. Freeze selection first and label reuse explicitly.
    dump(report/'selection.json',{'candidate':spec,'validation_metrics':validation,'old_test_used_for_selection':False,
             'evaluation_status':'retrospective reuse of previously inspected v1 test; not a fresh independent holdout'})
    training=[r for r in rows if r['published_at']<config['retrospective_test_start']]
    test=[r for r in rows if r['published_at']>=config['retrospective_test_start']]
    print('SELECTED',spec['name'],'RETROSPECTIVE rows',len(test),flush=True)
    evaluation_model=fit(spec,training,catalog,config);pred=forecast(evaluation_model,spec,test,catalog,config['threads'])
    actual=np.array([float(r['price_thb']) for r in test]);evaluation=metrics(actual,pred)
    # v1 reference estimator uses the same cutoff, same input subset and same six core fields.
    baseline_spec=next(x for x in config['candidates'] if x['kind']=='v1')
    baseline_model=fit(baseline_spec,training,catalog,config);reference=metrics(actual,forecast(baseline_model,baseline_spec,test,catalog,config['threads']))
    write_csv(report/'tables/retrospective_metrics.csv',[{'model':'v1_same_cutoff',**reference},{'model':spec['name'],**evaluation}])
    groups=group_metrics(test,actual,pred,{r['brand']+':'+r['model'] for r in training})
    write_csv(report/'tables/retrospective_by_group.csv',groups)
    write_csv(private/'evaluation/retrospective_predictions.csv',[{'listing_id':r['listing_id'],'source':r['source'],'brand':r['brand'],'model':r['model'],
                        'actual_thb':float(y),'predicted_thb':float(p),'absolute_error_thb':float(abs(y-p))} for r,y,p in zip(test,actual,pred)])
    evaluation_artifact=artifact(evaluation_model,spec,training,catalog,core_hash)
    joblib.dump(evaluation_artifact,modeldir/'evaluation.joblib',compress=3)
    print('DEPLOYMENT FIT all',len(rows),'rows with frozen candidate (no in-sample accuracy claim)',flush=True)
    # A separate operational artifact can now learn contemporary models present in the full data.
    deployment=fit(spec,rows,catalog,config)
    deployment_artifact=artifact(deployment,spec,rows,catalog,core_hash);deployment_artifact['role']='deployment_full_data'
    joblib.dump(deployment_artifact,modeldir/'model.joblib',compress=3)
    loaded=joblib.load(modeldir/'model.joblib')
    if not np.allclose(forecast(loaded['model'],spec,rows[:20],catalog),forecast(deployment,spec,rows[:20],catalog)):
        raise ValueError('Artifact roundtrip failed')
    if sha(core)!=core_hash:raise ValueError('Core dataset changed during training')
    summary={'run':run_name,'selected_model':spec['name'],'validation':validation,'retrospective':evaluation,'v1_same_cutoff':reference,
             'retrospective_mae_improvement_pct':100*(1-evaluation['mae_thb']/reference['mae_thb']),
             'evaluation_fit_rows':len(training),'retrospective_rows':len(test),'deployment_fit_rows':len(rows),
             'deployment_models':len(deployment_artifact['fitted_models']),'deployment_date_max':deployment_artifact['fit_date_max'],
             'fresh_independent_holdout':False,'deployment_independent_test_metrics':None,
             'groups':[r for r in groups if r['group']!='brand_model'],'duration_seconds':round(time.monotonic()-start,2),
             'policy':'Keep all 9,210 rows. Recency weights do not remove old data. No tuning from old test in this run; it was examined in v1 and informed general diagnosis.'}
    meta={'run':run_name,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'config_sha256':sha(config_path),'dataset_sha256':core_hash,
          'enriched_sha256':sha(dataset),'catalog_sha256':sha(catalog_path),'model_hashes':{p.name:sha(p) for p in modeldir.glob('*.joblib')},
          'code_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'script/modeling').glob('*.py'))},
          'versions':{x:importlib.metadata.version(x) for x in ['scikit-learn','catboost','pandas','numpy','joblib']},
          'fit_roles':{'evaluation.joblib':{'rows':len(training),'test_excluded':True},'model.joblib':{'rows':len(rows),'includes_old_test':True,'independent_test_score':None}},
          'selected_model':spec['name'],'feature_contract':deployment_artifact['feature_names']}
    dump(modeldir/'metadata.json',meta);dump(report/'summary.json',summary);dump(report/'run_metadata.json',meta)
    dump(report/'validation.json',{'core_unchanged':True,'strict_temporal_folds':True,'encoder_fit_on_fold_training_only':True,
             'unknown_optional_values_not_imputed_in_dataset':True,'winner_chosen_before_retrospective_scoring':True,
             'model_roundtrip':True,'fresh_independent_holdout':False,'deployment_has_independent_test_score':False})
    from script.modeling.report_improved import render
    render(report,summary,comparisons,actual,pred)
    dump(report/'output_hashes.json',{str(p.relative_to(report)):sha(p) for p in report.rglob('*') if p.is_file() and p.name not in ('output_hashes.json','progress.json')})
    dump(report/'progress.json',{'phase':'completed','selected_model':spec['name'],'retrospective_mae':evaluation['mae_thb'],'deployment_rows':len(rows)})
    print('COMPLETE',json.dumps(summary,ensure_ascii=False),flush=True)
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,default=DEFAULT_CONFIG);parser.add_argument('--resume',action='store_true');args=parser.parse_args();run(args.config,args.resume)
