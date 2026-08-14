# Historical Counterfactual Fraud Networks

Reproducibility repository for **Historical Counterfactual Fraud Networks: Graph-Aware Temporal Memory with Hub-Robust Relationship Explanations**.

The project studies fraud detection as a temporal-relational problem. It builds wallet-level temporal memory, augments it with strictly prior graph-neighbor behavior, and explains predictions by removing a relationship from the target wallet's historical relational memory and replaying the fixed model.

## Repository structure

```text
counterfactual-fraud-networks/
├── src/temf/                 # reusable model/metric/split utilities
├── experiments/              # experiment runners and archived development scripts
├── results/
│   ├── main/                 # predictive and five-seed JSON results
│   └── counterfactual/       # relationship effects and concentration analyses
├── artifacts/
│   ├── models/               # trained checkpoints used during the study
│   └── predictions/          # saved prediction arrays
├── data/                     # dataset instructions + SHA-256 manifests (not raw data)
├── docs/                     # protocol, timeline, results, paper-artifact mapping
├── paper/
│   ├── submitted_manuscript.pdf
│   ├── submitted_manuscript.docx
│   ├── figures/
│   └── archive/
├── tests/                    # result-integrity tests
└── .github/workflows/        # lightweight CI
```

## Headline results

| Model | PR-AUC mean (SD) | ROC-AUC mean (SD) | F1 mean (SD) |
|---|---:|---:|---:|
| Temporal-neighbor event MLP | 0.2089 (0.0099) | 0.7942 (0.0136) | 0.2450 (0.0137) |
| Plain Graph Memory | **0.2757 (0.0022)** | **0.8113 (0.0130)** | 0.2629 (0.0179) |
| Hub-Suppressed Graph Memory | 0.2744 (0.0096) | 0.8040 (0.0123) | **0.2814 (0.0155)** |

Hub suppression reduces the single most influential neighbor's share of total absolute historical-counterfactual effect from **23.9% to 10.3%**.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

Then follow [`data/README.md`](data/README.md) to place and verify the Elliptic++ files.

## Reproducing the paper

1. Prepare the temporal wallet data with `experiments/01_prepare_temf_data.py`.
2. Run the temporal-memory development experiments (`02`–`06`).
3. Use the graph-memory runners and the locked protocol documented in `docs/REPRODUCIBILITY.md`.
4. Run `experiments/10_graph_memory_5seed_colab.py` for the final five-seed graph comparison.
5. Run `experiments/11_temporal_neighbor_event_5seed_colab.py` for the controlled event baseline.
6. Compare exact outputs with `results/main/` and `results/counterfactual/`.

Some graph/counterfactual stages were developed interactively during the original study. Their exact result files, trained checkpoints, predictions, protocol, and paper-to-artifact mapping are preserved here; the repository intentionally keeps the original scripts used during development rather than rewriting history after submission.

## Data policy

Raw Elliptic++ data is **not redistributed** in this repository. See `data/raw_manifest.json` and `data/raw_manifest.sha256` for the exact authoritative files used. Large prepared arrays are also excluded; their checksums are in `data/prepared_artifacts_manifest.json`.

## Counterfactual interpretation

The reported counterfactuals are **model interventions**, not claims that a relationship caused illicit behavior. A positive effect means that the relationship increased the trained model's fraud probability; a negative effect means it reduced it.

## Paper artifacts

The submitted manuscript and figures are under `paper/`. See `docs/ARTIFACT_MAP.md` to trace manuscript claims to machine-readable outputs.

## License

A public code license has not yet been selected. See `LICENSE_PENDING.md` before making the repository public.
