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

torch.save(model.state_dict(),base+'/elliptic_temf_gru_v0.pt')
json.dump({'epochs':h},open(base+'/elliptic_temf_gru_v0_train_history.json','w'),indent=2)
print('SAVED MODEL',flush=True)
