import os, json, random, time
import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset, DataLoader
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support, confusion_matrix

SEED=42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))
base='/mnt/data'
z=np.load(base+'/temf_prepared.npz')
X=z['X']; Xseq=z['Xseq']; times=z['times']; y=z['y']; prior_count=z['prior_count']; starts=z['starts']; ends=z['ends']
train_mask=times<=34; val_mask=(times>=35)&(times<=41); test_mask=times>=42
recurrent=prior_count>0

class SeqDS(Dataset):
    def __init__(self, train=False):
        self.items=[]
        for s,e in zip(starts,ends):
            if train:
                k=np.searchsorted(times[s:e],34,side='right')
                if k>0: self.items.append((int(s),int(s+k)))
            else:
                self.items.append((int(s),int(e)))
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        s,e=self.items[i]
        # Xseq last col is log1p(gap); preserve exact v0 input and also expose raw-ish gap for decay.
        return (torch.from_numpy(Xseq[s:e]), torch.from_numpy(y[s:e].astype(np.float32)), s)

def collate(batch):
    xs,ys,ss=zip(*batch)
    lens=torch.tensor([len(x) for x in xs],dtype=torch.long)
    return pad_sequence(xs,batch_first=True), pad_sequence(ys,batch_first=True), lens, ss

class TEMFDecay(nn.Module):
    def __init__(self,din,hidden=32):
        super().__init__()
        self.inproj=nn.Sequential(nn.Linear(din,48),nn.ReLU(),nn.LayerNorm(48))
        self.cell=nn.GRUCell(48,hidden)
        # Vector decay: each hidden memory channel learns its own non-negative decay rate.
        # Initial softplus(-3) ~= 0.049, close to weak/no decay for short gaps.
        self.raw_decay=nn.Parameter(torch.full((hidden,),-3.0))
        self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Linear(hidden,1))
    def forward(self,x,lens):
        B,L,_=x.shape
        z=self.inproj(x)
        h=torch.zeros(B,self.cell.hidden_size,device=x.device,dtype=x.dtype)
        outs=[]
        decay_rate=torch.nn.functional.softplus(self.raw_decay)
        for t in range(L):
            active=(t<lens).to(x.dtype).unsqueeze(1)
            # gap feature is log1p(raw gap), so expm1 reconstructs gap in time-step units.
            gap=torch.expm1(torch.clamp(x[:,t,-1],min=0.0,max=10.0)).unsqueeze(1)
            if t>0:
                hdec=h*torch.exp(-gap*decay_rate.unsqueeze(0))
            else:
                hdec=h
            hnew=self.cell(z[:,t,:],hdec)
            h=active*hnew+(1.0-active)*h
            outs.append(self.head(h).squeeze(-1))
        return torch.stack(outs,dim=1)
    def decay_rates(self):
        return torch.nn.functional.softplus(self.raw_decay).detach().cpu().numpy()

train_ds=SeqDS(train=True); full_ds=SeqDS(train=False)
train_loader=DataLoader(train_ds,batch_size=2048,shuffle=True,collate_fn=collate,num_workers=0)
model=TEMFDecay(Xseq.shape[1],32)
pos=int(y[train_mask].sum()); neg=int(train_mask.sum()-pos)
pos_weight=torch.tensor([neg/max(pos,1)],dtype=torch.float32)
crit=nn.BCEWithLogitsLoss(pos_weight=pos_weight,reduction='none')
opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4)
history=[]
for epoch in range(1,4):
    model.train(); total=0.; n=0; t0=time.time()
    for xb,yb,lens,ss in train_loader:
        opt.zero_grad(set_to_none=True)
        logits=model(xb,lens)
        mask=(torch.arange(logits.shape[1])[None,:] < lens[:,None])
        loss=crit(logits,yb[:,:logits.shape[1]])
        loss=(loss*mask).sum()/mask.sum()
        loss.backward(); nn.utils.clip_grad_norm_(model.parameters(),5.0); opt.step()
        total += float(loss)*int(mask.sum()); n += int(mask.sum())
    rec={'epoch':epoch,'train_loss':total/n,'seconds':time.time()-t0}
    history.append(rec); print('epoch',rec,flush=True)

@torch.no_grad()
def infer():
    loader=DataLoader(full_ds,batch_size=2048,shuffle=False,collate_fn=collate,num_workers=0)
    out=np.full(len(y),np.nan,dtype=np.float32); model.eval()
    for xb,yb,lens,ss in loader:
        p=torch.sigmoid(model(xb,lens)).numpy()
        for j,(s,l) in enumerate(zip(ss,lens.numpy())): out[s:s+l]=p[j,:l]
    assert np.isfinite(out).all(); return out
p=infer()

# exact matched static baseline from prepared data
clf=SGDClassifier(loss='log_loss',class_weight='balanced',alpha=1e-5,max_iter=1000,tol=1e-4,random_state=42)
clf.fit(X[train_mask],y[train_mask]); pstatic=clf.predict_proba(X)[:,1]

def best_thr(p,vmask):
    pv=p[vmask]; yv=y[vmask]
    qs=np.unique(np.quantile(pv,np.linspace(0,1,501)))
    best=(0.5,-1.)
    for t in qs:
        _,_,f,_=precision_recall_fscore_support(yv,pv>=t,average='binary',zero_division=0)
        if f>best[1]: best=(float(t),float(f))
    return best

def metric(p,name,subset=None,threshold_scope='global'):
    v=val_mask.copy(); m=test_mask.copy()
    if subset is not None:
        m &= subset
        if threshold_scope=='subset': v &= subset
    thr,vf=best_thr(p,v)
    yt=y[m]; pt=p[m]; pred=pt>=thr
    pr,re,f,_=precision_recall_fscore_support(yt,pred,average='binary',zero_division=0)
    tn,fp,fn,tp=confusion_matrix(yt,pred,labels=[0,1]).ravel()
    return {'name':name,'n':int(m.sum()),'positives':int(yt.sum()),'threshold':thr,'val_best_f1':vf,
            'pr_auc':float(average_precision_score(yt,pt)),'roc_auc':float(roc_auc_score(yt,pt)),
            'precision':float(pr),'recall':float(re),'f1':float(f),'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}

rates=model.decay_rates()
results=[
 metric(pstatic,'static_robust_all'), metric(p,'temf_decay_v1_all'),
 metric(pstatic,'static_robust_recurrent_subset_threshold',recurrent,'subset'),
 metric(p,'temf_decay_v1_recurrent_subset_threshold',recurrent,'subset')
]
out={
 'seed':SEED,'split':{'train':int(train_mask.sum()),'val':int(val_mask.sum()),'test':int(test_mask.sum())},
 'architecture':'same v0 signed-log features + log gap input; 48-d projection -> GRUCell(32) with per-hidden-channel learned exponential memory decay exp(-lambda_j*gap) -> classifier',
 'training':history,
 'learned_decay':{'min_lambda':float(rates.min()),'median_lambda':float(np.median(rates)),'mean_lambda':float(rates.mean()),'max_lambda':float(rates.max()),
                    'median_half_life_timesteps':float(np.log(2)/np.median(rates))},
 'results':results
}
with open(base+'/elliptic_temf_decay_v1_results.json','w') as f: json.dump(out,f,indent=2)
torch.save({'model_state':model.state_dict(),'seed':SEED,'architecture':out['architecture']},base+'/elliptic_temf_decay_v1.pt')
np.savez_compressed(base+'/elliptic_temf_decay_v1_predictions.npz',p_decay=p,p_static=pstatic)
print(json.dumps(out,indent=2),flush=True)
