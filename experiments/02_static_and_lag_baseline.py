import pandas as pd, numpy as np, glob, re, json, os, time
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support, confusion_matrix

from pathlib import Path

repo = Path(__file__).resolve().parents[1]
processed_dir = repo / "data" / "processed"
results_dir = repo / "results" / "main"
results_dir.mkdir(parents=True, exist_ok=True)
parts=[]
for p in glob.glob(str(repo / "data" / "raw" / "wallets_features_part*.txt")):
    b=os.path.basename(p)
    # authoritative replacements only: part1(2), part2(2), and parts3-15(1)
    if b in ['wallets_features_part1(2).txt','wallets_features_part2(2).txt'] or re.match(r'wallets_features_part(?:[3-9]|1[0-5])\(1\)\.txt$',b):
        parts.append(p)
def pnum(p):
    return int(re.search(r'part(\d+)',os.path.basename(p)).group(1))
parts=sorted(parts,key=pnum)
assert [pnum(p) for p in parts]==list(range(1,16)), [os.path.basename(x) for x in parts]
with open(parts[0]) as f: header=f.readline().rstrip('\n').split(',')
exclude={'first_block_appeared_in','last_block_appeared_in','lifetime_in_blocks','first_sent_block','first_received_block','num_timesteps_appeared_in'}
behavior=[c for c in header if c not in {'address','Time step'} and c not in exclude]
use=['address','Time step']+behavior
frames=[]
for i,p in enumerate(parts):
    kw=dict(usecols=use)
    if i==0: df=pd.read_csv(p, **kw)
    else: df=pd.read_csv(p, names=header, header=None, **kw)
    frames.append(df)
    print('loaded',i+1,len(df), flush=True)
df=pd.concat(frames,ignore_index=True); del frames
raw_rows=len(df)
# drop fully identical selected-feature rows first
before=len(df); df=df.drop_duplicates(); exact_dups=before-len(df)
# one observation per address/time; mean only if multiple non-identical source records remain
# use numeric groupby mean
agg=df.groupby(['address','Time step'],as_index=False,sort=False)[behavior].mean()
del df
obs_rows=len(agg)
# labels
classes=pd.read_csv(repo / "data" / "raw" / "wallets_classes(2).txt")
agg=agg.merge(classes,on='address',how='left',validate='many_to_one')
# labeled only; class1 illicit=1, class2 licit=0, class3 unknown excluded
lab=agg[agg['class'].isin([1,2])].copy()
lab['y']=(lab['class']==1).astype('int8')
# chronological recurrence features calculated BEFORE filtering labels and using no labels
agg=agg.sort_values(['address','Time step']).reset_index(drop=True)
g=agg.groupby('address',sort=False)
agg['prior_obs_count']=g.cumcount().astype('float32')
agg['prev_time']=g['Time step'].shift(1)
agg['gap_since_prev']=agg['Time step']-agg['prev_time']
agg['gap_since_prev']=agg['gap_since_prev'].fillna(50).clip(0,50).astype('float32')
# key behavioral lags and deltas
key=['total_txs','btc_transacted_total','btc_sent_total','btc_received_total','fees_total','fees_as_share_mean','blocks_btwn_txs_mean','num_addr_transacted_multiple','transacted_w_address_total','transacted_w_address_mean']
mem=['prior_obs_count','gap_since_prev']
for c in key:
    prev=g[c].shift(1)
    pc='prev__'+c; dc='delta__'+c
    agg[pc]=prev.fillna(0)
    agg[dc]=(agg[c]-prev).fillna(0)
    mem += [pc,dc]
lab=agg[agg['class'].isin([1,2])].copy(); lab['y']=(lab['class']==1).astype('int8')
# fill inf/nan
for c in behavior+mem:
    lab[c]=pd.to_numeric(lab[c],errors='coerce').replace([np.inf,-np.inf],np.nan).fillna(0)
train=lab['Time step']<=34
val=(lab['Time step']>=35)&(lab['Time step']<=41)
test=lab['Time step']>=42

def fit_eval(features,name):
    Xtr=lab.loc[train,features].to_numpy(dtype=np.float32); ytr=lab.loc[train,'y'].to_numpy()
    Xv=lab.loc[val,features].to_numpy(dtype=np.float32); yv=lab.loc[val,'y'].to_numpy()
    Xte=lab.loc[test,features].to_numpy(dtype=np.float32); yte=lab.loc[test,'y'].to_numpy()
    sc=StandardScaler().fit(Xtr)
    Xtr=sc.transform(Xtr); Xv=sc.transform(Xv); Xte=sc.transform(Xte)
    clf=SGDClassifier(loss='log_loss',class_weight='balanced',alpha=1e-5,max_iter=1000,tol=1e-4,random_state=42,early_stopping=False)
    clf.fit(Xtr,ytr)
    pv=clf.predict_proba(Xv)[:,1]; pt=clf.predict_proba(Xte)[:,1]
    # choose threshold maximizing validation F1 among score quantiles + .5
    qs=np.unique(np.quantile(pv,np.linspace(0,1,501)))
    best=(0.5,-1)
    for t in qs:
        pred=(pv>=t)
        _,_,f,_=precision_recall_fscore_support(yv,pred,average='binary',zero_division=0)
        if f>best[1]: best=(float(t),float(f))
    thr=best[0]; pred=(pt>=thr)
    pr,re,f,_=precision_recall_fscore_support(yte,pred,average='binary',zero_division=0)
    tn,fp,fn,tp=confusion_matrix(yte,pred,labels=[0,1]).ravel()
    return {
      'name':name,'n_features':len(features),'threshold_from_val':thr,
      'val_pr_auc':float(average_precision_score(yv,pv)),'val_roc_auc':float(roc_auc_score(yv,pv)),'val_best_f1':best[1],
      'test_pr_auc':float(average_precision_score(yte,pt)),'test_roc_auc':float(roc_auc_score(yte,pt)),
      'test_precision':float(pr),'test_recall':float(re),'test_f1':float(f),
      'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)
    }

res_static=fit_eval(behavior,'static_behavioral')
res_temf=fit_eval(behavior+mem,'temporal_memory_lite')
summary={
 'authoritative_parts':[os.path.basename(p) for p in parts],
 'raw_rows':raw_rows,'exact_duplicate_rows_removed':exact_dups,'address_time_rows_after_aggregation':obs_rows,
 'unique_addresses':int(agg.address.nunique()),'time_min':int(agg['Time step'].min()),'time_max':int(agg['Time step'].max()),
 'labeled_obs':int(len(lab)),'positive_obs':int(lab.y.sum()),
 'splits':{'train_obs':int(train.sum()),'val_obs':int(val.sum()),'test_obs':int(test.sum()),'train_positive':int(lab.loc[train,'y'].sum()),'val_positive':int(lab.loc[val,'y'].sum()),'test_positive':int(lab.loc[test,'y'].sum())},
 'excluded_future_risk_fields':sorted(exclude),
 'memory_features':mem,
 'results':[res_static,res_temf]
}
out=results_dir / "elliptic_temf_baseline_results.json"
with open(out,'w') as f: json.dump(summary,f,indent=2)
print(json.dumps(summary,indent=2))
print('SAVED',out)
