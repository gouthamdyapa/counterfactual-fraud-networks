# Reproducibility

This document describes the experimental protocol and the recommended order for reproducing the main results.

Run all commands from the repository root.

## 1. Data Setup

Place the required Elliptic++ files in:

```text
data/raw/
```

The raw data are intentionally not committed to this repository.

See:

```text
data/README.md
data/raw_manifest.json
data/raw_manifest.sha256
```

for the expected files and integrity information.

---

## 2. Prepare Temporal Data

Run:

```bash
python3 experiments/01_prepare_temf_data.py
```

This generates:

```text
data/processed/temf_prepared.npz
data/processed/temf_prepared_meta.json
```

The prepared temporal dataset contains wallet observations, chronological sequences, labels, time steps, and recurrence information used by the temporal experiments.

---

## 3. Run Core Temporal Experiments

The principal temporal experiments are:

```bash
python3 experiments/02_static_and_lag_baseline.py
python3 experiments/03_temf_gru_v0.py
python3 experiments/04_temf_decay_v1.py
python3 experiments/05_temf_adaptive_v2.py
python3 experiments/06_temf_5seed_robustness.py
```

Experiment outputs are written under:

```text
results/main/
artifacts/models/
artifacts/predictions/
```

where applicable.

---

## 4. Prepare Final Graph Data

The final graph experiments require graph-aware temporal features.

Run:

```bash
python3 experiments/09_prepare_final_graph_data.py
```

This consumes the prepared temporal data and the Elliptic++ `AddrAddr` graph files and generates:

```text
data/processed/temf_final_graph_prepared.npz
```

The preparation stage constructs:

- graph structural features,
- leakage-safe prior-neighbor memory,
- separate incoming and outgoing neighbor histories,
- strict hub-suppressed neighbor memory.

At target time `t`, relational features use only neighbor observations from times strictly earlier than `t`.

---

## 5. Run Final Graph Experiments

Run:

```bash
python3 experiments/10_graph_memory_5seed_colab.py
python3 experiments/11_temporal_neighbor_event_5seed_colab.py
```

Despite the historical `_colab` suffix, these scripts now use repository-relative paths and can be executed outside Google Colab.

Results are written to:

```text
results/main/
```

---

## Locked Protocol

The main experimental protocol is:

- Seeds: `13, 21, 42, 77, 101`
- Train: time steps `1–34`
- Validation: `35–41`
- Test: `42–49`
- Projection: 48 dimensions
- GRU hidden state: 32
- Optimizer: AdamW
- Learning rate: `1e-3`
- Weight decay: `1e-4`
- Batch size: 1024 for recurrent experiments
- Gradient clipping: 5
- Loss: class-weighted binary cross entropy
- Epochs: 3 for final graph-memory robustness
- Threshold: selected using validation F1 only

The chronological split and validation-only threshold selection are held fixed across the reported comparisons.

---

## Leakage Control

At target time `t`, relational features use each neighbor's most recent observation from a time strictly earlier than `t`.

Current-time observations are committed to neighbor memory only **after all target rows at time `t` have been constructed**.

Therefore, observations at time `t` cannot provide relational information to other observations at the same time step.

Standardization statistics for graph and neighbor-memory features are computed from the training period only.

---

## Hub Suppression

The hub-suppressed graph-memory variant scales each historical neighbor contribution using:

```text
1 / sqrt(1 + degree(u))
```

where `degree(u)` is the labeled graph degree of neighbor `u`.

The weighted messages are then aggregated separately for incoming and outgoing historical neighbors.

---

## Counterfactual Definition

For target wallet `v` and historical neighbor `u`, remove `u` from every eligible incoming/outgoing prior-neighbor aggregation in `v`'s history through the target time.

The modified target sequence is then replayed through the **fixed trained model**, and the final prediction is compared with the original prediction.

The signed effect is interpreted as a **model-intervention sensitivity**.

It is **not a real-world causal effect**.

---

## Large Artifacts

Large raw and generated data files are intentionally excluded from Git.

Expected prepared artifact sizes and SHA-256 hashes are recorded in:

```text
data/prepared_artifacts_manifest.json
```

This allows locally regenerated artifacts to be compared with those used during the original experiments.

---

## Legacy Scripts

Historical development and evaluation scripts are retained under:

```text
experiments/legacy/
```

These files may contain the original Colab-specific paths and are preserved for provenance.

For reproduction, use the numbered main scripts in:

```text
experiments/
```