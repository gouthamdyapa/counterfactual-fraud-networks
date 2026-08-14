import os,sys,random,time,json
import numpy as np, torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset,DataLoader
SEED=42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))
base='/mnt/data'; z=np.load(base+'/temf_prepared.npz')
Xseq=z['Xseq']; times=z['times']; y=z['y']; starts=z['starts']; ends=z['ends']
class DS(Dataset):
 def __init__(self):
  self.items=[]
  for s,e in zip(starts,ends):
   k=np.searchsorted(times[s:e],34,side='right')
   if k>0:self.items.append((int(s),int(s+k)))
 def __len__(self):return len(self.items)
 def __getitem__(self,i):
  s,e=self.items[i];return torch.from_numpy(Xseq[s:e]),torch.from_numpy(y[s:e].astype(np.float32))
def col(b):
 xs,ys=zip(*b); l=torch.tensor([len(x) for x in xs]);return pad_sequence(xs,batch_first=True),pad_sequence(ys,batch_first=True),l
class M(nn.Module):
 def __init__(self,din,hidden=32):
  super().__init__();self.hidden=hidden
  self.inproj=nn.Sequential(nn.Linear(din,48),nn.ReLU(),nn.LayerNorm(48));self.cell=nn.GRUCell(48,hidden)
  self.gate=nn.Sequential(nn.Linear(81,hidden),nn.ReLU(),nn.Linear(hidden,hidden));nn.init.zeros_(self.gate[-1].weight);nn.init.zeros_(self.gate[-1].bias)
  self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Linear(hidden,1))
 def forward(self,x,lens):
  B,L,_=x.shape;z=self.inproj(x);h=torch.zeros(B,self.hidden);outs=[]
  for t in range(L):
   a=(t<lens).to(x.dtype).unsqueeze(1);cand=self.cell(z[:,t],h);alpha=torch.sigmoid(self.gate(torch.cat([z[:,t],h,x[:,t,-1:]],1)))
   hn=alpha*h+(1-alpha)*cand;h=a*hn+(1-a)*h;outs.append(self.head(h).squeeze(-1))
  return torch.stack(outs,1)
model=M(Xseq.shape[1]); opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4)
ck=base+'/temf_v2_training.pt'; hist=[]
if os.path.exists(ck):
 d=torch.load(ck,map_location='cpu');model.load_state_dict(d['model']);opt.load_state_dict(d['opt']);hist=d['hist']
epoch=len(hist)+1
loader=DataLoader(DS(),batch_size=4096,shuffle=True,collate_fn=col,num_workers=0)
train_mask=times<=34;pos=int(y[train_mask].sum());neg=int(train_mask.sum()-pos);crit=nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg/max(pos,1)]),reduction='none')
model.train();tot=n=0;t0=time.time()
for xb,yb,lens in loader:
 opt.zero_grad(set_to_none=True);log=model(xb,lens);mask=(torch.arange(log.shape[1])[None,:]<lens[:,None]);loss=crit(log,yb[:,:log.shape[1]]);loss=(loss*mask).sum()/mask.sum();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();tot+=loss.detach().item()*int(mask.sum());n+=int(mask.sum())
rec={'epoch':epoch,'train_loss':tot/n,'seconds':time.time()-t0};hist.append(rec);torch.save({'model':model.state_dict(),'opt':opt.state_dict(),'hist':hist},ck);print(json.dumps(rec))
