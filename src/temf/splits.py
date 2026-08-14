import numpy as np

def chronological_masks(times):
    """Return locked train/validation/test masks for Elliptic++ time steps."""
    times=np.asarray(times)
    return times <= 34, (times >= 35) & (times <= 41), times >= 42
