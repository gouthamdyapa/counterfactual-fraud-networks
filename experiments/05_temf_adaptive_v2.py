import os, json, random, time
import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support, confusion_matrix
from pathlib import Path

SEED=42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))


repo = Path(__file__).resolve().parents[1]
processed_dir = repo / "data" / "processed"
results_dir = repo / "results" / "main"
models_dir = repo / "artifacts" / "models"
predictions_dir = repo / "artifacts" / "predictions"

results_dir.mkdir(parents=True, exist_ok=True)
models_dir.mkdir(parents=True, exist_ok=True)
predictions_dir.mkdir(parents=True, exist_ok=True)

z = np.load(processed_dir / "temf_prepared.npz")
Xseq=z['Xseq']; times=z['times']; y=z['y']; prior_count=z['prior_count']; starts=z['starts']; ends=z['ends']
train_mask=times<=34; val_mask=(times>=35)&(times<=41); test_mask=times>=42
recurrent=prior_count>0
# Reuse the exact static baseline probabilities from v0 to keep comparison identical.
p0 = np.load(predictions_dir / "elliptic_temf_gru_v0_predictions.npz")
pstatic=p0['pstatic']

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
        return torch.from_numpy(Xseq[s:e]), torch.from_numpy(y[s:e].astype(np.float32)), s

def collate(batch):
    xs,ys,ss=zip(*batch)
    lens=torch.tensor([len(x) for x in xs],dtype=torch.long)
    return pad_sequence(xs,batch_first=True), pad_sequence(ys,batch_first=True), lens, ss

class TEMFAdaptive(nn.Module):
    def __init__(self,din,hidden=32):
        super().__init__()
        self.hidden=hidden
        self.inproj=nn.Sequential(nn.Linear(din,48),nn.ReLU(),nn.LayerNorm(48))
        self.cell=nn.GRUCell(48,hidden)
        # Explicit adaptive fraud-memory retention gate. The gate sees current behavior,
        # prior memory, and elapsed-time signal and chooses how much prior memory to retain.
        self.gate=nn.Sequential(
            nn.Linear(48+hidden+1,hidden), nn.ReLU(),
            nn.Linear(hidden,hidden)
        )
        # Initialize retention near 0.5, allowing training to learn both remembering/forgetting.
        nn.init.zeros_(self.gate[-1].weight); nn.init.zeros_(self.gate[-1].bias)
        self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Linear(hidden,1))
    def forward(self,x,lens,return_gates=False):
        B,L,_=x.shape
        z=self.inproj(x)
        h=torch.zeros(B,self.hidden,device=x.device,dtype=x.dtype)
        outs=[]; gates=[]
        for t in range(L):
            active=(t<lens).to(x.dtype).unsqueeze(1)
            gap=x[:,t,-1:].clamp(min=0.0,max=10.0)  # log1p gap, same input convention as v0/v1
            candidate=self.cell(z[:,t,:],h)
            alpha=torch.sigmoid(self.gate(torch.cat([z[:,t,:],h,gap],dim=1)))
            hnew=alpha*h+(1.0-alpha)*candidate
            h=active*hnew+(1.0-active)*h
            outs.append(self.head(h).squeeze(-1))
            if return_gates: gates.append(alpha)
        logits=torch.stack(outs,dim=1)
        if return_gates: return logits, torch.stack(gates,dim=1)
        return logits

train_ds=SeqDS(train=True); full_ds=SeqDS(train=False)
train_loader=DataLoader(train_ds,batch_size=2048,shuffle=True,collate_fn=collate,num_workers=0)
model=TEMFAdaptive(Xseq.shape[1],32)
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
def infer_and_gate_stats():
    # Length-sorted batching minimizes padding while preserving exact wallet sequences.
    items=full_ds.items
    order=np.argsort([e-s for s,e in items])
    out=np.full(len(y),np.nan,dtype=np.float32)
    gate_sum=0.; gate_sq=0.; gate_n=0; gate_gap_sum=0.; gap_sum=0.; gap_sq=0.
    model.eval()
    bs=2048
    for a in range(0,len(order),bs):
        batch=[full_ds[int(i)] for i in order[a:a+bs]]
        xb,yb,lens,ss=collate(batch)
        logits,g=model(xb,lens,return_gates=True)
        p=torch.sigmoid(logits).cpu().numpy(); ga=g.cpu().numpy(); xx=xb.cpu().numpy()
        for j,(s,l) in enumerate(zip(ss,lens.numpy())):
            out[s:s+l]=p[j,:l]
            gv=ga[j,:l].reshape(-1)
            gaps=xx[j,:l,-1]
            # Pair each hidden gate with its observation gap for a rough correlation summary.
            gg=np.repeat(gaps,model.hidden)
            gate_sum += float(gv.sum()); gate_sq += float((gv*gv).sum()); gate_n += gv.size
            gate_gap_sum += float((gv*gg).sum()); gap_sum += float(gg.sum()); gap_sq += float((gg*gg).sum())
    assert np.isfinite(out).all()
    gm=gate_sum/gate_n; gvar=max(gate_sq/gate_n-gm*gm,0.)
    xm=gap_sum/gate_n; xvar=max(gap_sq/gate_n-xm*xm,0.)
    cov=gate_gap_sum/gate_n-gm*xm
    corr=cov/((gvar*xvar)**0.5+1e-12)
    return out, {'mean_retention_gate':gm,'std_retention_gate':gvar**0.5,'corr_gate_with_log_gap':corr}

p,gate_stats=infer_and_gate_stats()

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

results=[
 metric(pstatic,'static_robust_all'), metric(p,'temf_adaptive_v2_all'),
 metric(pstatic,'static_robust_recurrent_subset_threshold',recurrent,'subset'),
 metric(p,'temf_adaptive_v2_recurrent_subset_threshold',recurrent,'subset')
]
out={
 'seed':SEED,
 'split':{'train':int(train_mask.sum()),'val':int(val_mask.sum()),'test':int(test_mask.sum())},
 'architecture':'same v0 signed-log features + log gap; 48-d projection -> GRUCell(32) candidate; explicit learned retention alpha=sigmoid(MLP[current projection, prior hidden state, log gap]); h=alpha*h_prev+(1-alpha)*candidate -> classifier',
 'training':history,
 'gate_stats':gate_stats,
 'results':results
}
with open(results_dir / "elliptic_temf_adaptive_v2_results.json", "w") as f: json.dump(out,f,indent=2)
torch.save(
    {
        "model_state": model.state_dict(),
        "seed": SEED,
        "architecture": out["architecture"],
    },
    models_dir / "elliptic_temf_adaptive_v2.pt",
)
np.savez_compressed(
    predictions_dir / "elliptic_temf_adaptive_v2_predictions.npz",
    p_adaptive=p,
    p_static=pstatic,
)
print(json.dumps(out,indent=2),flush=True)
