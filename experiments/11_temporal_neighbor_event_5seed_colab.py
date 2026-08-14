
import json, random, time
import numpy as np
import torch
from torch import nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support

BASE="/content"
DATA=f"{BASE}/temf_final_graph_prepared.npz"
OUT=f"{BASE}/temporal_neighbor_event_5seed_results.json"

SEEDS=[13,21,42,77,101]
EPOCHS=3
BATCH=4096

z=np.load(DATA)
Xp=z["X_plain"].astype(np.float32)
times=z["times"]
y=z["y"].astype(np.float32)
prior=z["prior"]

# Layout of X_plain is:
#   0:50   current transformed wallet features + target observation gap
#   50:55  static graph-structural features
#   55:77  leakage-safe prior-neighbor event summaries
#
# External-strengthening baseline:
# current entity observation + strictly-prior neighbor event representation.
# No static graph structure and NO recurrent target-wallet hidden state.
X=np.concatenate([Xp[:,0:50], Xp[:,55:77]], axis=1).astype(np.float32)

tr=times<=34
va=(times>=35)&(times<=41)
te=times>=42
rec=prior>0

class EventMLP(nn.Module):
    def __init__(self,din):
        super().__init__()
        self.net=nn.Sequential(
            nn.Linear(din,48),
            nn.ReLU(),
            nn.LayerNorm(48),
            nn.Linear(48,32),
            nn.ReLU(),
            nn.LayerNorm(32),
            nn.Linear(32,1)
        )
    def forward(self,x):
        return self.net(x).squeeze(-1)

pos=float(y[tr].sum())
neg=float(tr.sum()-pos)
pos_weight=torch.tensor([neg/pos],dtype=torch.float32)
crit=nn.BCEWithLogitsLoss(pos_weight=pos_weight)

def best_threshold(p,mask):
    pv=p[mask]; yv=y[mask]
    qs=np.unique(np.quantile(pv,np.linspace(0,1,401)))
    best=(-1.0,0.5)
    for t in qs:
        f=precision_recall_fscore_support(
            yv.astype(np.int8),pv>=t,average="binary",zero_division=0
        )[2]
        if f>best[0]:
            best=(float(f),float(t))
    return best[1]

def run(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    model=EventMLP(X.shape[1])
    opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4)

    ds=TensorDataset(torch.from_numpy(X[tr]),torch.from_numpy(y[tr]))
    loader=DataLoader(ds,batch_size=BATCH,shuffle=True)
    losses=[]
    t0=time.time()

    for ep in range(EPOCHS):
        model.train(); total=n=0
        for xb,yb in loader:
            opt.zero_grad()
            logits=model(xb)
            loss=crit(logits,yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(),5.0)
            opt.step()
            total+=float(loss.detach())*len(xb); n+=len(xb)
        losses.append(total/n)

    pred=np.empty(len(y),dtype=np.float32)
    model.eval()
    with torch.no_grad():
        eval_loader=DataLoader(
            TensorDataset(torch.from_numpy(X)),
            batch_size=8192,shuffle=False
        )
        offset=0
        for (xb,) in eval_loader:
            pp=torch.sigmoid(model(xb)).cpu().numpy()
            pred[offset:offset+len(pp)]=pp
            offset+=len(pp)

    th=best_threshold(pred,va)
    pr,re,f,_=precision_recall_fscore_support(
        y[te].astype(np.int8),pred[te]>=th,average="binary",zero_division=0
    )
    rm=te & rec
    return {
        "seed":seed,
        "model":"temporal_neighbor_event_mlp",
        "epochs":EPOCHS,
        "loss":losses,
        "threshold":float(th),
        "seconds":float(time.time()-t0),
        "pr_auc":float(average_precision_score(y[te],pred[te])),
        "roc_auc":float(roc_auc_score(y[te],pred[te])),
        "precision":float(pr),
        "recall":float(re),
        "f1":float(f),
        "recurrent_pr_auc":float(average_precision_score(y[rm],pred[rm])),
        "recurrent_roc_auc":float(roc_auc_score(y[rm],pred[rm])),
    }

runs=[]
for seed in SEEDS:
    r=run(seed); runs.append(r)
    print(seed,{k:round(r[k],4) for k in
          ["pr_auc","roc_auc","precision","recall","f1",
           "recurrent_pr_auc","recurrent_roc_auc"]},flush=True)

keys=["pr_auc","roc_auc","precision","recall","f1",
      "recurrent_pr_auc","recurrent_roc_auc"]
summary={
    k:{
        "mean":float(np.mean([r[k] for r in runs])),
        "sd":float(np.std([r[k] for r in runs],ddof=1))
    } for k in keys
}

out={
 "protocol":"3-epoch five-seed temporal-neighbor event baseline; chronological split 1-34/35-41/42-49",
 "baseline_definition":{
   "input":"current wallet representation (50 dims) + strictly-prior directional neighbor-event summaries (22 dims)",
   "excluded":"static graph structural features and recurrent target-wallet hidden state",
   "classifier":"MLP 72->48->32->1 with ReLU/LayerNorm",
   "purpose":"test whether locked Graph-Memory gains persist beyond a non-recurrent event-driven temporal-neighborhood representation"
 },
 "seeds":SEEDS,
 "runs":runs,
 "summary":summary
}

with open(OUT,"w") as f:
    json.dump(out,f,indent=2)
print("SAVED",OUT)
