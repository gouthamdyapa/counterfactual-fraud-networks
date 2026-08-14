# Reproducibility

## Locked protocol
- Seeds: 13, 21, 42, 77, 101
- Train / validation / test: 1–34 / 35–41 / 42–49
- Projection: 48 dimensions
- GRU hidden state: 32
- Optimizer: AdamW
- Learning rate: 1e-3
- Weight decay: 1e-4
- Batch size: 1024 for recurrent experiments
- Gradient clipping: 5
- Loss: class-weighted binary cross entropy
- Epochs: 3 for final graph-memory robustness
- Threshold: selected on validation F1 only

## Leakage control
At target time `t`, relational features use each neighbor's most recent observation from a time strictly earlier than `t`. Current-time observations are committed only after all rows for `t` have been constructed.

## Counterfactual definition
For target wallet `v` and historical neighbor `u`, remove `u` from every eligible incoming/outgoing prior-neighbor aggregation in `v`'s history through the target time, replay the target sequence through the fixed trained model, and compare final probabilities.

These values are model-intervention sensitivities, not real-world causal effects.
