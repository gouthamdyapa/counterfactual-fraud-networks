import os,json,numpy as np,torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from sklearn.metrics import average_precision_score,roc_auc_score,precision_recall_fscore_support,confusion_matrix
base='/mnt/data'; z=np.load(base+'/temf_prepared.npz');Xseq=z['Xseq'];times=z['times'];y=z['y'];prior=z['prior_count'];starts=z['starts'];ends=z['ends']
train=times<=34;val=(times>=35)&(times<=41);test=times>=42;recur=prior>0
pstatic=np.load(base+'/elliptic_temf_gru_v0_predictions.npz')['pstatic']
class M(nn.Module):
 def __init__(self,din,hidden=32):
  super().__init__();self.hidden=hidden;self.inproj=nn.Sequential(nn.Linear(din,48),nn.ReLU(),nn.LayerNorm(48));self.cell=nn.GRUCell(48,hidden);self.gate=nn.Sequential(nn.Linear(81,hidden),nn.ReLU(),nn.Linear(hidden,hidden));self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Linear(hidden,1))
 def forward(self,x,lens,gstats=False):
  B,L,_=x.shape;z=self.inproj(x);h=torch.zeros(B,self.hidden);outs=[];gs=[]
  for t in range(L):
   a=(t<lens).to(x.dtype).unsqueeze(1);cand=self.cell(z[:,t],h);alpha=torch.sigmoid(self.gate(torch.cat([z[:,t],h,x[:,t,-1:]],1)));hn=alpha*h+(1-alpha)*cand;h=a*hn+(1-a)*h;outs.append(self.head(h).squeeze(-1));gs.append(alpha)
  return torch.stack(outs,1),torch.stack(gs,1)
model=M(Xseq.shape[1]);d=torch.load(base+'/temf_v2_training.pt',map_location='cpu');model.load_state_dict(d['model']);model.eval();torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))
items=[(int(s),int(e)) for s,e in zip(starts,ends)];order=np.argsort([e-s for s,e in items]);p=np.full(len(y),np.nan,np.float32);s1=s2=n=sg=sx=sxx=0.
with torch.no_grad():
 for a in range(0,len(order),4096):
  inds=order[a:a+4096];xs=[torch.from_numpy(Xseq[items[i][0]:items[i][1]]) for i in inds];lens=torch.tensor([len(x) for x in xs]);xb=pad_sequence(xs,batch_first=True);log,g=model(xb,lens);pp=torch.sigmoid(log).numpy();gg=g.numpy();xx=xb.numpy()
  for j,i in enumerate(inds):
   s,e=items[i];l=e-s;p[s:e]=pp[j,:l];gv=gg[j,:l].reshape(-1);gp=np.repeat(xx[j,:l,-1],32);s1+=gv.sum();s2+=(gv*gv).sum();sg+=(gv*gp).sum();sx+=gp.sum();sxx+=(gp*gp).sum();n+=gv.size
assert np.isfinite(p).all();gm=s1/n;gv=max(s2/n-gm*gm,0);xm=sx/n;xv=max(sxx/n-xm*xm,0);corr=(sg/n-gm*xm)/((gv*xv)**.5+1e-12)
def bt(pp,vm):
 pv=pp[vm];yv=y[vm];qs=np.unique(np.quantile(pv,np.linspace(0,1,501)));best=(.5,-1)
 for t in qs:
  _,_,f,_=precision_recall_fscore_support(yv,pv>=t,average='binary',zero_division=0)
  if f>best[1]:best=(float(t),float(f))
 return best
def met(pp,name,sub=None):
 vm=val.copy();tm=test.copy()
 if sub is not None:vm&=sub;tm&=sub
 t,vf=bt(pp,vm);yt=y[tm];pt=pp[tm];pr=pt>=t;P,R,F,_=precision_recall_fscore_support(yt,pr,average='binary',zero_division=0);tn,fp,fn,tp=confusion_matrix(yt,pr,labels=[0,1]).ravel();return {'name':name,'n':int(tm.sum()),'positives':int(yt.sum()),'threshold':t,'val_best_f1':vf,'pr_auc':float(average_precision_score(yt,pt)),'roc_auc':float(roc_auc_score(yt,pt)),'precision':float(P),'recall':float(R),'f1':float(F),'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}
out={'seed':42,'split':{'train':int(train.sum()),'val':int(val.sum()),'test':int(test.sum())},'architecture':'48-d behavior projection -> GRUCell candidate + explicit adaptive retention gate alpha(current behavior, prior memory, log gap); h=alpha*h_prev+(1-alpha)*candidate -> classifier','training':d['hist'],'gate_stats':{'mean_retention_gate':float(gm),'std_retention_gate':float(gv**.5),'corr_gate_with_log_gap':float(corr)},'results':[met(pstatic,'static_robust_all'),met(p,'temf_adaptive_v2_all'),met(pstatic,'static_robust_recurrent_subset_threshold',recur),met(p,'temf_adaptive_v2_recurrent_subset_threshold',recur)]}
json.dump(out,open(base+'/elliptic_temf_adaptive_v2_results.json','w'),indent=2);torch.save({'model_state':model.state_dict(),'seed':42,'architecture':out['architecture']},base+'/elliptic_temf_adaptive_v2.pt');np.savez_compressed(base+'/elliptic_temf_adaptive_v2_predictions.npz',p_adaptive=p,p_static=pstatic);print(json.dumps(out,indent=2))
