import os, re, glob, json, random, time
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence, pad_packed_sequence
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support, confusion_matrix

SEED=42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))
base='/mnt/data'

# authoritative parts only
parts=[]
for p in glob.glob(base+'/wallets_features_part*.txt'):
    b=os.path.basename(p)
    if b in ['wallets_features_part1(2).txt','wallets_features_part2(2).txt'] or re.match(r'wallets_features_part(?:[3-9]|1[0-5])\(1\)\.txt$',b):
        parts.append(p)
parts=sorted(parts,key=lambda p:int(re.search(r'part(\d+)',os.path.basename(p)).group(1)))
assert len(parts)==15
with open(parts[0]) as f: header=f.readline().rstrip('\n').split(',')
exclude={'first_block_appeared_in','last_block_appeared_in','lifetime_in_blocks','first_sent_block','first_received_block','num_timesteps_appeared_in'}
behavior=[c for c in header if c not in {'address','Time step'} and c not in exclude]
use=['address','Time step']+behavior

# Stream parts and retain only labeled wallets before concatenation to control memory.
classes=pd.read_csv(base+'/wallets_classes(2).txt')
classes=classes[classes['class'].isin([1,2])].copy()
label_map=dict(zip(classes['address'],classes['class']))
labeled_addr=set(label_map)
frames=[]; raw_rows=0
for i,p in enumerate(parts):
    kw=dict(usecols=use)
    d=pd.read_csv(p, **kw) if i==0 else pd.read_csv(p,names=header,header=None,**kw)
    raw_rows += len(d)
    d=d[d['address'].isin(labeled_addr)]
    d['class']=d['address'].map(label_map).astype('int8')
    frames.append(d)
    print('loaded',i+1,'raw cumulative',raw_rows,'labeled retained',len(d),flush=True)
lab=pd.concat(frames,ignore_index=True); del frames
before=len(lab); lab=lab.drop_duplicates(); labeled_exact_dups=before-len(lab)
# consolidate any non-identical duplicate address/time records by mean; class is wallet-level
lab=lab.groupby(['address','Time step','class'],as_index=False,sort=False)[behavior].mean()
lab['y']=(lab['class']==1).astype(np.int8)
lab=lab.sort_values(['address','Time step']).reset_index(drop=True)
# clean numeric and robust transform; fit scaler on training observations only
Xraw=lab[behavior].to_numpy(dtype=np.float64)
Xraw=np.nan_to_num(Xraw,nan=0.0,posinf=0.0,neginf=0.0)
Xlog=np.sign(Xraw)*np.log1p(np.abs(Xraw))
times=lab['Time step'].to_numpy(np.int16)
y=lab['y'].to_numpy(np.int8)
train_mask=times<=34; val_mask=(times>=35)&(times<=41); test_mask=times>=42
scaler=StandardScaler().fit(Xlog[train_mask])
X=scaler.transform(Xlog).astype(np.float32)
X=np.clip(X,-10,10)
# explicit temporal input: normalized gap since prior observation (0 for first)
addresses=lab['address'].to_numpy()
new=np.r_[True,addresses[1:]!=addresses[:-1]]
starts=np.flatnonzero(new)
ends=np.r_[starts[1:],len(lab)]
gaps=np.zeros(len(lab),dtype=np.float32)
prior_count=np.zeros(len(lab),dtype=np.int16)
for s,e in zip(starts,ends):
    tt=times[s:e]
    if e-s>1: gaps[s+1:e]=np.diff(tt)
    prior_count[s:e]=np.arange(e-s,dtype=np.int16)
gapfeat=np.log1p(gaps)[:,None].astype(np.float32)
Xseq=np.concatenate([X,gapfeat],axis=1)

# recurrence summary
recurrence={
 'labeled_wallets':int(len(starts)),
 'wallets_with_2plus_obs':int(np.sum((ends-starts)>=2)),
 'wallets_with_3plus_obs':int(np.sum((ends-starts)>=3)),
 'max_sequence_len':int((ends-starts).max()),
 'test_obs_with_prior_history':int(np.sum(test_mask & (prior_count>0))),
 'test_positive_with_prior_history':int(np.sum(test_mask & (prior_count>0) & (y==1)))
}
print('recurrence',recurrence,flush=True)


np.savez(base+'/temf_prepared.npz',X=X,Xseq=Xseq,times=times,y=y,prior_count=prior_count,starts=starts,ends=ends)
with open(base+'/temf_prepared_meta.json','w') as f: json.dump({'behavior':behavior,'exclude':sorted(exclude),'raw_rows':raw_rows,'labeled_exact_dups':labeled_exact_dups,'recurrence':recurrence},f,indent=2)
print('SAVED prepared', X.shape, flush=True)
