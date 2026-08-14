
import json, random, time
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence, pad_packed_sequence
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support

BASE="/content"
DATA=f"{BASE}/temf_final_graph_prepared.npz"
OUT=f"{BASE}/graph_memory_5seed_results.json"
SEEDS=[13,21,42,77,101]
EPOCHS=3
BATCH=1024

z=np.load(DATA)
Xplain=z["X_plain"].astype(np.float32)
Xhub=z["X_hub"].astype(np.float32)
times=z["times"]; y=z["y"]; prior=z["prior"]; starts=z["starts"]; ends=z["ends"]
tr=times<=34
va=(times>=35)&(times<=41)
te=times>=42
rec=prior>0

class DS(Dataset):
    def __init__(self,X,train):
        self.X=X; self.items=[]
        for s,e in zip(starts,ends):
            if train:
                k=np.searchsorted(times[s:e],34,side="right")
                if k:self.items.append((int(s),int(s+k)))
            else:self.items.append((int(s),int(e)))
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        s,e=self.items[i]
        return torch.from_numpy(self.X[s:e]),torch.from_numpy(y[s:e].astype(np.float32)),s

def coll(batch):
    xs,ys,ss=zip(*batch)
    lens=torch.tensor([len(x) for x in xs])
    return pad_sequence(xs,batch_first=True),pad_sequence(ys,batch_first=True),lens,ss

class Model(nn.Module):
    def __init__(self,din):
        super().__init__()
        self.p=nn.Sequential(nn.Linear(din,48),nn.ReLU(),nn.LayerNorm(48))
        self.r=nn.GRU(48,32,batch_first=True)
        self.h=nn.Sequential(nn.LayerNorm(32),nn.Linear(32,1))
    def forward(self,x,lens):
        p=pack_padded_sequence(self.p(x),lens.cpu(),batch_first=True,enforce_sorted=False)
        o,_=self.r(p)
        o,_=pad_packed_sequence(o,batch_first=True)
        return self.h(o).squeeze(-1)

pos=y[tr].sum(); neg=tr.sum()-pos
crit=nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg/pos]),reduction="none")

def best_threshold(p,mask):
    pv=p[mask]; yv=y[mask]
    qs=np.unique(np.quantile(pv,np.linspace(0,1,401)))
    best=(-1,0.5)
    for t in qs:
        f=precision_recall_fscore_support(yv,pv>=t,average="binary",zero_division=0)[2]
        if f>best[0]: best=(f,float(t))
    return best[1]

def run(X,seed,name):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    model=Model(X.shape[1])
    opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4)
    loader=DataLoader(DS(X,True),batch_size=BATCH,shuffle=True,collate_fn=coll)
    losses=[]; t0=time.time()
    for ep in range(EPOCHS):
        model.train(); total=n=0
        for xb,yb,lens,ss in loader:
            opt.zero_grad()
            lo=model(xb,lens)
            mask=torch.arange(lo.shape[1])[None,:] < lens[:,None]
            loss=(crit(lo,yb[:,:lo.shape[1]])*mask).sum()/mask.sum()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(),5)
            opt.step()
            total+=float(loss.detach())*int(mask.sum()); n+=int(mask.sum())
        losses.append(total/n)

    pred=np.empty(len(y),np.float32)
    model.eval()
    with torch.no_grad():
        for xb,yb,lens,ss in DataLoader(DS(X,False),batch_size=BATCH,collate_fn=coll):
            pp=torch.sigmoid(model(xb,lens)).cpu().numpy()
            for j,(s,l) in enumerate(zip(ss,lens.numpy())):
                pred[s:s+l]=pp[j,:l]

    th=best_threshold(pred,va)
    pr,re,f,_=precision_recall_fscore_support(y[te],pred[te]>=th,average="binary",zero_division=0)
    rm=te & rec
    return {
        "seed":seed,"model":name,"epochs":EPOCHS,"loss":losses,
        "threshold":th,"seconds":time.time()-t0,
        "pr_auc":float(average_precision_score(y[te],pred[te])),
        "roc_auc":float(roc_auc_score(y[te],pred[te])),
        "precision":float(pr),"recall":float(re),"f1":float(f),
        "recurrent_pr_auc":float(average_precision_score(y[rm],pred[rm])),
        "recurrent_roc_auc":float(roc_auc_score(y[rm],pred[rm])),
    }

runs=[]
for seed in SEEDS:
    for name,X in [("plain_graph_memory",Xplain),("hub_suppressed",Xhub)]:
        r=run(X,seed,name); runs.append(r)
        print(seed,name,{k:round(r[k],4) for k in ["pr_auc","roc_auc","f1"]},flush=True)

def summarize(model):
    rr=[r for r in runs if r["model"]==model]
    keys=["pr_auc","roc_auc","precision","recall","f1","recurrent_pr_auc","recurrent_roc_auc"]
    return {k:{"mean":float(np.mean([r[k] for r in rr])),
               "sd":float(np.std([r[k] for r in rr],ddof=1))}
            for k in keys}

out={"protocol":"3-epoch matched five-seed final robustness; chronological split 1-34/35-41/42-49",
     "seeds":SEEDS,"runs":runs,
     "plain_summary":summarize("plain_graph_memory"),
     "hub_summary":summarize("hub_suppressed")}
with open(OUT,"w") as f: json.dump(out,f,indent=2)
print("SAVED",OUT)
