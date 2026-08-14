import os, json, numpy as np, torch
from torch import nn
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support, confusion_matrix

torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))
base='/mnt/data'; z=np.load(base+'/temf_prepared.npz')
X=z['X']; Xseq=z['Xseq']; times=z['times']; y=z['y']; prior_count=z['prior_count']; starts=z['starts']; ends=z['ends']
train_mask=times<=34; val_mask=(times>=35)&(times<=41); test_mask=times>=42; recurrent=prior_count>0

class TEMFDecay(nn.Module):
    def __init__(self,din,hidden=32):
        super().__init__(); self.inproj=nn.Sequential(nn.Linear(din,48),nn.ReLU(),nn.LayerNorm(48)); self.cell=nn.GRUCell(48,hidden)
        self.raw_decay=nn.Parameter(torch.full((hidden,),-3.0)); self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Linear(hidden,1))
    def forward(self,x,lens):
        B,L,_=x.shape; z=self.inproj(x); h=torch.zeros(B,self.cell.hidden_size,dtype=x.dtype,device=x.device); outs=[]
        rate=torch.nn.functional.softplus(self.raw_decay)
        for t in range(L):
            gap=torch.expm1(torch.clamp(x[:,t,-1],0,10)).unsqueeze(1)
            hdec=h if t==0 else h*torch.exp(-gap*rate.unsqueeze(0))
            h=self.cell(z[:,t],hdec); outs.append(self.head(h).squeeze(-1))
        return torch.stack(outs,1)
    def rates(self): return torch.nn.functional.softplus(self.raw_decay).detach().numpy()

model=TEMFDecay(Xseq.shape[1],32)
ck=torch.load(base+'/elliptic_temf_decay_v1_trainonly.pt',map_location='cpu')
model.load_state_dict(ck['model_state']); model.eval()
p=np.full(len(y),np.nan,np.float32)
lens=(ends-starts).astype(int)
for L in sorted(np.unique(lens)):
    idx=np.flatnonzero(lens==L)
    for q in range(0,len(idx),4096):
        ids=idx[q:q+4096]
        xb=np.stack([Xseq[starts[i]:ends[i]] for i in ids]).astype(np.float32)
        with torch.no_grad(): pr=torch.sigmoid(model(torch.from_numpy(xb),torch.full((len(ids),),L,dtype=torch.long))).numpy()
        for j,i in enumerate(ids): p[starts[i]:ends[i]]=pr[j]
    print('inferred length',L,'wallets',len(idx),flush=True)
assert np.isfinite(p).all()

clf=SGDClassifier(loss='log_loss',class_weight='balanced',alpha=1e-5,max_iter=1000,tol=1e-4,random_state=42)
clf.fit(X[train_mask],y[train_mask]); ps=clf.predict_proba(X)[:,1]

def best_thr(probs, mask):
    pv=probs[mask]; yv=y[mask]; qs=np.unique(np.quantile(pv,np.linspace(0,1,501))); best=(.5,-1.)
    for t in qs:
        _,_,f,_=precision_recall_fscore_support(yv,pv>=t,average='binary',zero_division=0)
        if f>best[1]: best=(float(t),float(f))
    return best

def metric(probs,name,subset=None,subset_thr=False):
    vm=val_mask.copy(); tm=test_mask.copy()
    if subset is not None:
        tm &= subset
        if subset_thr: vm &= subset
    th,vf=best_thr(probs,vm); yt=y[tm]; pt=probs[tm]; pred=pt>=th
    prec,rec,f,_=precision_recall_fscore_support(yt,pred,average='binary',zero_division=0); tn,fp,fn,tp=confusion_matrix(yt,pred,labels=[0,1]).ravel()
    return dict(name=name,n=int(tm.sum()),positives=int(yt.sum()),threshold=th,val_best_f1=vf,pr_auc=float(average_precision_score(yt,pt)),roc_auc=float(roc_auc_score(yt,pt)),precision=float(prec),recall=float(rec),f1=float(f),tn=int(tn),fp=int(fp),fn=int(fn),tp=int(tp))

rates=model.rates(); results=[metric(ps,'static_robust_all'),metric(p,'temf_decay_v1_all'),metric(ps,'static_robust_recurrent_subset_threshold',recurrent,True),metric(p,'temf_decay_v1_recurrent_subset_threshold',recurrent,True)]
# pull train history from stdout-known values; fixed run seed 42
history=[{'epoch':1,'train_loss':0.68889362266831},{'epoch':2,'train_loss':0.55464152403375},{'epoch':3,'train_loss':0.5325340977493168}]
out={'seed':42,'split':{'train':int(train_mask.sum()),'val':int(val_mask.sum()),'test':int(test_mask.sum())},'architecture':'same v0 features + log gap; projection -> GRUCell with per-hidden-channel learned exponential decay h_prior*exp(-lambda_j*gap) -> classifier','training':history,'learned_decay':{'min_lambda':float(rates.min()),'median_lambda':float(np.median(rates)),'mean_lambda':float(rates.mean()),'max_lambda':float(rates.max()),'median_half_life_timesteps':float(np.log(2)/np.median(rates))},'results':results}
json.dump(out,open(base+'/elliptic_temf_decay_v1_results.json','w'),indent=2)
torch.save({'model_state':model.state_dict(),'architecture':out['architecture'],'seed':42},base+'/elliptic_temf_decay_v1.pt')
np.savez_compressed(base+'/elliptic_temf_decay_v1_predictions.npz',p_decay=p,p_static=ps)
print(json.dumps(out,indent=2))
