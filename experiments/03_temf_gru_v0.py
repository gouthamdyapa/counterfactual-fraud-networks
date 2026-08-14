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
from pathlib import Path

SEED=42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))

repo = Path(__file__).resolve().parents[1]
raw_dir = repo / "data" / "raw"
results_dir = repo / "results" / "main"
models_dir = repo / "artifacts" / "models"

results_dir.mkdir(parents=True, exist_ok=True)
models_dir.mkdir(parents=True, exist_ok=True)

# authoritative parts only
parts=[]
for p in glob.glob(str(raw_dir / "wallets_features_part*.txt")):
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
classes=pd.read_csv(raw_dir / "wallets_classes(2).txt")
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

class SeqDS(Dataset):
    def __init__(self, mode):
        self.items=[]
        for s,e in zip(starts,ends):
            if mode=='train':
                # only causal history through timestep 34
                k=np.searchsorted(times[s:e],34,side='right')
                if k>0: self.items.append((s,s+k))
            else:
                self.items.append((s,e))
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        s,e=self.items[i]
        return (torch.from_numpy(Xseq[s:e]), torch.from_numpy(y[s:e].astype(np.float32)),
                torch.from_numpy(times[s:e].astype(np.int64)), torch.from_numpy(prior_count[s:e].astype(np.int64)), s)

def collate(batch):
    xs,ys,ts,pcs,ss=zip(*batch)
    lens=torch.tensor([len(x) for x in xs],dtype=torch.long)
    return (pad_sequence(xs,batch_first=True), pad_sequence(ys,batch_first=True),
            pad_sequence(ts,batch_first=True), pad_sequence(pcs,batch_first=True), lens, ss)

class TEMFGRU(nn.Module):
    def __init__(self,din,hidden=32):
        super().__init__()
        self.inproj=nn.Sequential(nn.Linear(din,48),nn.ReLU(),nn.LayerNorm(48))
        self.gru=nn.GRU(48,hidden,batch_first=True)
        self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Linear(hidden,1))
    def forward(self,x,lens):
        z=self.inproj(x)
        p=pack_padded_sequence(z,lens.cpu(),batch_first=True,enforce_sorted=False)
        o,_=self.gru(p)
        o,_=pad_packed_sequence(o,batch_first=True)
        return self.head(o).squeeze(-1)

device='cpu'
train_ds=SeqDS('train'); full_ds=SeqDS('full')
train_loader=DataLoader(train_ds,batch_size=1024,shuffle=True,collate_fn=collate,num_workers=0)
model=TEMFGRU(Xseq.shape[1],hidden=32).to(device)
pos=int(y[train_mask].sum()); neg=int(train_mask.sum()-pos)
pos_weight=torch.tensor([neg/max(pos,1)],dtype=torch.float32)
crit=nn.BCEWithLogitsLoss(pos_weight=pos_weight,reduction='none')
opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4)

history=[]
for epoch in range(1,7):
    model.train(); totloss=0.; nobs=0
    t0=time.time()
    for xb,yb,tb,pcb,lens,ss in train_loader:
        opt.zero_grad(set_to_none=True)
        logits=model(xb,lens)
        maxL=logits.shape[1]
        mask=torch.arange(maxL)[None,:] < lens[:,None]
        loss=crit(logits,yb[:,:maxL])
        loss=(loss*mask).sum()/mask.sum()
        loss.backward(); nn.utils.clip_grad_norm_(model.parameters(),5.0); opt.step()
        totloss += float(loss)*int(mask.sum()); nobs += int(mask.sum())
    rec={'epoch':epoch,'train_loss':totloss/nobs,'seconds':time.time()-t0}
    history.append(rec); print('epoch',rec,flush=True)

@torch.no_grad()
def infer_all():
    loader=DataLoader(full_ds,batch_size=1024,shuffle=False,collate_fn=collate,num_workers=0)
    out=np.full(len(lab),np.nan,dtype=np.float32)
    model.eval()
    for xb,yb,tb,pcb,lens,ss in loader:
        pr=torch.sigmoid(model(xb,lens)).cpu().numpy()
        for j,(s,l) in enumerate(zip(ss,lens.numpy())):
            out[s:s+l]=pr[j,:l]
    return out
pgru=infer_all()
assert np.isfinite(pgru).all()

# static baseline retrained under same robust preprocessing for apples-to-apples
clf=SGDClassifier(loss='log_loss',class_weight='balanced',alpha=1e-5,max_iter=1000,tol=1e-4,random_state=42)
clf.fit(X[train_mask],y[train_mask])
pstatic=clf.predict_proba(X)[:,1]

def threshold_from_val(p):
    pv=p[val_mask]; yv=y[val_mask]
    qs=np.unique(np.quantile(pv,np.linspace(0,1,501)))
    best=(0.5,-1.)
    for t in qs:
        pred=pv>=t
        _,_,f,_=precision_recall_fscore_support(yv,pred,average='binary',zero_division=0)
        if f>best[1]: best=(float(t),float(f))
    return best

def metrics(p,name,subset=None):
    thr,vf=threshold_from_val(p)
    m=test_mask.copy()
    if subset is not None: m &= subset
    yt=y[m]; pt=p[m]; pred=pt>=thr
    pr,re,f,_=precision_recall_fscore_support(yt,pred,average='binary',zero_division=0)
    tn,fp,fn,tp=confusion_matrix(yt,pred,labels=[0,1]).ravel()
    return {'name':name,'n':int(m.sum()),'positives':int(yt.sum()),'threshold_from_val':thr,'val_best_f1':vf,
            'pr_auc':float(average_precision_score(yt,pt)),'roc_auc':float(roc_auc_score(yt,pt)),
            'precision':float(pr),'recall':float(re),'f1':float(f),'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}

recurrent=(prior_count>0)
results=[
    metrics(pstatic,'static_robust_all'), metrics(pgru,'temf_gru_v0_all'),
    metrics(pstatic,'static_robust_recurrent',recurrent), metrics(pgru,'temf_gru_v0_recurrent',recurrent)
]
summary={
 'raw_rows_all_parts':raw_rows,'labeled_exact_duplicate_rows_removed':labeled_exact_dups,'labeled_observations':int(len(lab)),
 'split':{'train_le_34':int(train_mask.sum()),'val_35_41':int(val_mask.sum()),'test_42_49':int(test_mask.sum())},
 'features':{'behavioral':behavior,'excluded_future_risk_fields':sorted(exclude),'transform':'signed_log1p + train StandardScaler + clip[-10,10]','temporal_input':'log1p gap since prior wallet observation'},
 'recurrence':recurrence,'architecture':'Linear(50->48)+ReLU+LayerNorm -> GRU(48,32) -> LayerNorm+Linear; recurrent state updated only from feature observations, never labels',
 'training':{'epochs':6,'batch_wallet_sequences':1024,'optimizer':'AdamW','lr':1e-3,'class_pos_weight':float(neg/max(pos,1)),'history':history},
 'results':results
}
with open(results_dir / "elliptic_temf_gru_v0_results.json", "w") as f: json.dump(summary,f,indent=2)
torch.save(
    {
        "model_state": model.state_dict(),
        "behavior": behavior,
        "scaler_mean": scaler.mean_,
        "scaler_scale": scaler.scale_,
    },
    models_dir / "elliptic_temf_gru_v0.pt",
)
print(json.dumps(summary,indent=2),flush=True)
