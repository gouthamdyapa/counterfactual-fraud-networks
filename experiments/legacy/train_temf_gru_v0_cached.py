import os,json,time,random
import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence,pack_padded_sequence,pad_packed_sequence
from torch.utils.data import Dataset,DataLoader
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score,roc_auc_score,precision_recall_fscore_support,confusion_matrix
SEED=42; random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED); torch.set_num_threads(min(8,os.cpu_count() or 1))
base='/mnt/data'; z=np.load(base+'/temf_prepared.npz')
X=z['X']; Xseq=z['Xseq']; times=z['times']; y=z['y']; prior_count=z['prior_count']; starts=z['starts']; ends=z['ends']
meta=json.load(open(base+'/temf_prepared_meta.json'))
train_mask=times<=34; val_mask=(times>=35)&(times<=41); test_mask=times>=42
class SeqDS(Dataset):
 def __init__(self,mode):
  self.items=[]
  for s,e in zip(starts,ends):
   if mode=='train':
    k=np.searchsorted(times[s:e],34,side='right')
    if k>0:self.items.append((int(s),int(s+k)))
   else:self.items.append((int(s),int(e)))
 def __len__(self):return len(self.items)
 def __getitem__(self,i):
  s,e=self.items[i];return torch.from_numpy(Xseq[s:e]),torch.from_numpy(y[s:e].astype(np.float32)),s
def collate(b):
 xs,ys,ss=zip(*b);lens=torch.tensor([len(x) for x in xs],dtype=torch.long)
 return pad_sequence(xs,batch_first=True),pad_sequence(ys,batch_first=True),lens,ss
class M(nn.Module):
 def __init__(self):
  super().__init__();self.inp=nn.Sequential(nn.Linear(Xseq.shape[1],48),nn.ReLU(),nn.LayerNorm(48));self.gru=nn.GRU(48,32,batch_first=True);self.head=nn.Sequential(nn.LayerNorm(32),nn.Linear(32,1))
 def forward(self,x,l):
  p=pack_padded_sequence(self.inp(x),l.cpu(),batch_first=True,enforce_sorted=False);o,_=self.gru(p);o,_=pad_packed_sequence(o,batch_first=True);return self.head(o).squeeze(-1)
tr=SeqDS('train');full=SeqDS('full');loader=DataLoader(tr,batch_size=1024,shuffle=True,collate_fn=collate)
model=M();pos=int(y[train_mask].sum());neg=int(train_mask.sum()-pos);crit=nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg/pos]),reduction='none');opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4)
h=[]
for ep in range(1,4):
 model.train();tot=n=0;t0=time.time()
 for xb,yb,lens,ss in loader:
  opt.zero_grad(set_to_none=True);log=model(xb,lens);L=log.shape[1];mask=torch.arange(L)[None,:]<lens[:,None];loss=crit(log,yb[:,:L]);loss=(loss*mask).sum()/mask.sum();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();tot+=loss.detach().item()*int(mask.sum());n+=int(mask.sum())
 r={'epoch':ep,'train_loss':tot/n,'seconds':time.time()-t0};h.append(r);print(r,flush=True)
@torch.no_grad()
def infer():
 out=np.full(len(y),np.nan,np.float32);model.eval();ld=DataLoader(full,batch_size=1024,shuffle=False,collate_fn=collate)
 for xb,yb,lens,ss in ld:
  p=torch.sigmoid(model(xb,lens)).numpy()
  for j,(s,l) in enumerate(zip(ss,lens.numpy())):out[s:s+l]=p[j,:l]
 return out
pgru=infer();clf=SGDClassifier(loss='log_loss',class_weight='balanced',alpha=1e-5,max_iter=1000,tol=1e-4,random_state=42);clf.fit(X[train_mask],y[train_mask]);pstatic=clf.predict_proba(X)[:,1]
def thr(p):
 pv=p[val_mask];yv=y[val_mask];best=(.5,-1)
 for t in np.unique(np.quantile(pv,np.linspace(0,1,501))):
  _,_,f,_=precision_recall_fscore_support(yv,pv>=t,average='binary',zero_division=0)
  if f>best[1]:best=(float(t),float(f))
 return best
def met(p,name,subset=None):
 t,vf=thr(p);m=test_mask.copy();m=m if subset is None else (m&subset);yt=y[m];pt=p[m];pred=pt>=t;pr,re,f,_=precision_recall_fscore_support(yt,pred,average='binary',zero_division=0);tn,fp,fn,tp=confusion_matrix(yt,pred,labels=[0,1]).ravel();return {'name':name,'n':int(m.sum()),'positives':int(yt.sum()),'threshold':t,'val_best_f1':vf,'pr_auc':float(average_precision_score(yt,pt)),'roc_auc':float(roc_auc_score(yt,pt)),'precision':float(pr),'recall':float(re),'f1':float(f),'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}
rec=prior_count>0
res=[met(pstatic,'static_robust_all'),met(pgru,'temf_gru_v0_all'),met(pstatic,'static_robust_recurrent',rec),met(pgru,'temf_gru_v0_recurrent',rec)]
out={'split':{'train':int(train_mask.sum()),'val':int(val_mask.sum()),'test':int(test_mask.sum())},'recurrence':meta['recurrence'],'architecture':'signed-log behavioral features + log gap -> 48-d projection -> GRU(32) -> classifier','epochs':h,'results':res}
json.dump(out,open(base+'/elliptic_temf_gru_v0_results.json','w'),indent=2);torch.save(model.state_dict(),base+'/elliptic_temf_gru_v0.pt');print(json.dumps(out,indent=2),flush=True)
