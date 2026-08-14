# Data

Raw Elliptic++ data and large generated arrays are intentionally **not committed** to this repository.

The expected directory structure is:

```text
data/
├── raw/                         # downloaded Elliptic++ source files
├── processed/                   # generated experiment-ready arrays
├── raw_manifest.json
├── raw_manifest.sha256
└── prepared_artifacts_manifest.json
```

## Raw Elliptic++ Data

Place the authoritative Elliptic++ files inside:

```text
data/raw/
```

using the filenames recorded in:

```text
data/raw_manifest.json
```

Raw dataset files should **not** be committed to Git.

### Verify Raw Files

SHA-256 hashes for the source files used during the project are recorded in:

```text
data/raw_manifest.sha256
```

Use these hashes to verify that your downloaded files match the files used in the experiments.

## Prepared Data

Generated experiment-ready arrays are written to:

```text
data/processed/
```

The main prepared artifacts are:

```text
temf_prepared.npz
temf_graph_structural_prepared.npz
temf_final_graph_prepared.npz
```

These files are intentionally excluded from Git because of their size.

Their expected sizes and SHA-256 digests are recorded in:

```text
data/prepared_artifacts_manifest.json
```

## Preparing the Temporal Dataset

After placing the required raw Elliptic++ wallet files in `data/raw/`, run from the repository root:

```bash
python3 experiments/01_prepare_temf_data.py
```

This produces:

```text
data/processed/temf_prepared.npz
data/processed/temf_prepared_meta.json
```

## Final Graph Experiments

The final Graph Memory and Temporal-Neighbor Event experiments use:

```text
data/processed/temf_final_graph_prepared.npz
```

The scripts are:

```bash
python3 experiments/10_graph_memory_5seed_colab.py
python3 experiments/11_temporal_neighbor_event_5seed_colab.py
```

The corresponding results are written to:

```text
results/main/
```

## Dataset Usage in the Paper

The final experiments use the Elliptic++ wallet feature/class files and the five-part `AddrAddr` graph.

`AddrTx` and `TxAddr` files were integrity-checked during development but are not required by the final models reported in the paper.

## Labels

The supervised task uses **labeled Elliptic++ wallets only**.

Unknown labels are excluded from supervised evaluation and are **not converted into negative examples**.

## Chronological Split

The evaluation protocol uses:

| Split | Time steps |
|---|---:|
| Training | 1–34 |
| Validation | 35–41 |
| Test | 42–49 |

This chronological split is used to avoid future information leaking into earlier training observations.

## Git Policy

The following directories exist in the repository but their generated/data contents are ignored by Git:

```text
data/raw/
data/processed/
```

Only `.gitkeep` placeholder files are tracked.

This prevents large dataset and generated NumPy artifacts from being accidentally committed.