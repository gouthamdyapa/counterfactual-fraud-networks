import os,json,random,time,numpy as np,torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset,DataLoader
from sklearn.metrics import average_precision_score,roc_auc_score,precision_recall_fscore_support
base='/mnt/data'; seeds=[13,21,42,77,101]
z=np.load(base+'/temf_prepared.npz'); X=z['Xseq']; times=z['times']; y=z['y']; prior=z['prior_count']; starts=z['starts']; ends=z['ends']
tr=times<=34; va=(times>=35)&(times<=41); te=times>=42; rec=prior>0
pstatic=np.load(base+'/elliptic_temf_gru_v0_predictions.npz')['pstatic']
class DS(Dataset):
 def __init__(self,train):
  self.items=[]
  for s,e in zip(starts,ends):
   if train:
    k=np.searchsorted(times[s:e],34,side='right')
    if k:self.items.append((int(s),int(s+k)))
   elif times[e-1]>=35:self.items.append((int(s),int(e)))
 def __len__(self):return len(self.items)
 def __getitem__(self,i):
  s,e=self.items[i];return torch.from_numpy(X[s:e]),torch.from_numpy(y[s:e].astype(np.float32)),s
def col(b):
 xs,ys,ss=zip(*b); lens=torch.tensor([len(q) for q in xs]);return pad_sequence(xs,batch_first=True),pad_sequence(ys,batch_first=True),lens,ss
class M(nn.Module):
 def __init__(self,adaptive):
  super().__init__();self.ad=adaptive;self.ip=nn.Sequential(nn.Linear(X.shape[1],48),nn.ReLU(),nn.LayerNorm(48));self.cell=nn.GRUCell(48,32);self.head=nn.Sequential(nn.LayerNorm(32),nn.Linear(32,1))
  if adaptive:
   self.gate=nn.Sequential(nn.Linear(81,32),nn.ReLU(),nn.Linear(32,32));nn.init.zeros_(self.gate[-1].weight);nn.init.zeros_(self.gate[-1].bias)
 def forward(self,x,l):
  z=self.ip(x);h=torch.zeros(x.shape[0],32);o=[]
  for t in range(x.shape[1]):
   a=(t<l).float().unsqueeze(1);c=self.cell(z[:,t],h)
   if self.ad:
    al=torch.sigmoid(self.gate(torch.cat([z[:,t],h,x[:,t,-1:]],1)));c=al*h+(1-al)*c
   h=a*c+(1-a)*h;o.append(self.head(h).squeeze(-1))
  return torch.stack(o,1)
train_ds=DS(1); eval_ds=DS(0)
def best(p,mask):
 pv=p[mask];yv=y[mask];qs=np.unique(np.quantile(pv,np.linspace(0,1,301)));bf=(-1,.5)
 for t in qs:
  f=precision_recall_fscore_support(yv,pv>=t,average='binary',zero_division=0)[2]
  if f>bf[0]:bf=(f,float(t))
 return bf[1]
def mets(p,subset=None):
 vm=va.copy();tm=te.copy()
 if subset is not None:vm&=subset;tm&=subset
 t=best(p,vm);yt=y[tm];pt=p[tm];pr,re,f,_=precision_recall_fscore_support(yt,pt>=t,average='binary',zero_division=0)
 return dict(pr_auc=float(average_precision_score(yt,pt)),roc_auc=float(roc_auc_score(yt,pt)),precision=float(pr),recall=float(re),f1=float(f))
def run(seed,adaptive):
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.set_num_threads(8)
 dl=DataLoader(train_ds,batch_size=8192,shuffle=True,collate_fn=col,num_workers=0);m=M(adaptive);pw=torch.tensor([(tr.sum()-y[tr].sum())/y[tr].sum()]);crit=nn.BCEWithLogitsLoss(pos_weight=pw,reduction='none');op=torch.optim.AdamW(m.parameters(),lr=1e-3,weight_decay=1e-4)
 hist=[]
 for ep in range(2):
  m.train();tot=n=0
  for xb,yb,l,ss in dl:
   op.zero_grad();q=m(xb,l);mask=torch.arange(q.shape[1])[None,:]<l[:,None];loss=(crit(q,yb[:,:q.shape[1]])*mask).sum()/mask.sum();loss.backward();nn.utils.clip_grad_norm_(m.parameters(),5);op.step();tot+=loss.item()*mask.sum().item();n+=mask.sum().item()
  hist.append(tot/n)
 out=np.full(len(y),np.nan,np.float32);m.eval(); order=np.argsort([e-s for s,e in eval_ds.items])
 with torch.no_grad():
  for a in range(0,len(order),8192):
   b=[eval_ds[int(i)] for i in order[a:a+8192]];xb,yb,l,ss=col(b);p=torch.sigmoid(m(xb,l)).numpy()
   lens=l.numpy(); st=np.asarray(ss,dtype=np.int64)
   if lens.min()==lens.max():
    L=int(lens[0]); idx=st[:,None]+np.arange(L)[None,:]; out[idx]=p[:,:L]
   else:
    for j,(s0,ll) in enumerate(zip(st,lens)): out[s0:s0+ll]=p[j,:ll]
 assert np.isfinite(out[va|te]).all();return {'seed':seed,'model':'adaptive' if adaptive else 'gru','loss':hist,'all':mets(out),'recurrent':mets(out,rec)}
R=[]
for s in seeds:
 for ad in [False,True]:
  t=time.time();r=run(s,ad);r['seconds']=time.time()-t;R.append(r);print(s,r['model'],r['all'],flush=True)
summary={'protocol':'matched 2-epoch resource-bounded robustness run; same prepared data/split; validation/test-only inference preserving prior sequences','seeds':seeds,'static_all':mets(pstatic),'static_recurrent':mets(pstatic,rec),'runs':R}
for model in ['gru','adaptive']:
 rr=[r for r in R if r['model']==model]
 summary[model+'_mean_sd']={}
 for scope in ['all','recurrent']:
  summary[model+'_mean_sd'][scope]={k:{'mean':float(np.mean([r[scope][k] for r in rr])),'sd':float(np.std([r[scope][k] for r in rr],ddof=1))} for k in ['pr_auc','roc_auc','f1']}
open(base+'/temf_5seed_robustness_results.json','w').write(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
