import numpy as np
from sklearn.metrics import precision_recall_fscore_support

def best_f1_threshold(y, p, mask, quantiles=401):
    y=np.asarray(y); p=np.asarray(p); mask=np.asarray(mask, dtype=bool)
    pv=p[mask]; yv=y[mask]
    thresholds=np.unique(np.quantile(pv, np.linspace(0,1,quantiles)))
    best=(-1.0, 0.5)
    for t in thresholds:
        f=precision_recall_fscore_support(yv, pv>=t, average="binary", zero_division=0)[2]
        if f > best[0]: best=(float(f), float(t))
    return best[1]
