import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

class TemporalGRU(nn.Module):
    def __init__(self, input_dim, projection_dim=48, hidden_dim=32):
        super().__init__()
        self.proj=nn.Sequential(nn.Linear(input_dim, projection_dim), nn.ReLU(), nn.LayerNorm(projection_dim))
        self.gru=nn.GRU(projection_dim, hidden_dim, batch_first=True)
        self.head=nn.Sequential(nn.LayerNorm(hidden_dim), nn.Linear(hidden_dim,1))
    def forward(self, x, lengths):
        packed=pack_padded_sequence(self.proj(x), lengths.cpu(), batch_first=True, enforce_sorted=False)
        out,_=self.gru(packed)
        out,_=pad_packed_sequence(out,batch_first=True)
        return self.head(out).squeeze(-1)

class EventMLP(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.net=nn.Sequential(nn.Linear(input_dim,48),nn.ReLU(),nn.LayerNorm(48),nn.Linear(48,32),nn.ReLU(),nn.LayerNorm(32),nn.Linear(32,1))
    def forward(self,x): return self.net(x).squeeze(-1)
