# Historical Counterfactual Fraud Networks

**Graph-Aware Temporal Memory with Hub-Robust Relationship Explanations**

This repository contains the code, experiments, results, figures, and reproducibility materials for our research on temporal and graph-aware cryptocurrency fraud detection.

## Paper

**Historical Counterfactual Fraud Networks: Graph-Aware Temporal Memory with Hub-Robust Relationship Explanations**

**Author:** Goutam Dyapa  
**Status:** Submitted to IEEE BigData 2026

## Overview

Fraud in transaction networks is both temporal and relational. A wallet's predicted risk may depend not only on its own behavior, but also on its historical relationships with other wallets.

This project combines:

- Temporal wallet memory
- Graph-aware relational memory
- Strictly prior neighbor information
- Hub-robust aggregation
- Historical counterfactual relationship explanations

The main counterfactual question is:

> Would a wallet still receive the same fraud-risk prediction if a particular historical relationship had not contributed to its graph context?

The counterfactual effects reported by this project describe **model sensitivity**. They should not be interpreted as evidence that a relationship caused illicit behavior.

## Main Results

| Model | PR-AUC | ROC-AUC | F1 |
|---|---:|---:|---:|
| Temporal-Neighbor Event MLP | 0.2089 ± 0.0099 | 0.7942 ± 0.0136 | 0.2450 ± 0.0137 |
| Plain Graph Memory | **0.2757 ± 0.0022** | **0.8113 ± 0.0130** | 0.2629 ± 0.0179 |
| Hub-Suppressed Graph Memory | 0.2744 ± 0.0096 | 0.8040 ± 0.0123 | **0.2814 ± 0.0155** |

Evaluation uses five random seeds:

`13, 21, 42, 77, 101`

with the chronological split:

- Training: time steps 1–34
- Validation: time steps 35–41
- Test: time steps 42–49

## Historical Counterfactual Analysis

The counterfactual experiment contains:

- 328 target wallets
- 164 illicit targets
- 164 licit targets
- 578 historical relationship interventions

Hub suppression reduced the single most influential neighbor's share of total absolute counterfactual effect from **23.9% to 10.3%**.

## Repository Structure

```text
src/             Reusable model and evaluation utilities
experiments/     Experiment scripts
results/         Predictive and counterfactual results
artifacts/       Model checkpoints and prediction artifacts
data/            Dataset instructions and file manifests
docs/            Reproducibility documentation
paper/           Submitted manuscript and figures
tests/           Repository tests
```

## Dataset

This project uses the **Elliptic++** dataset.

The large raw dataset files are not redistributed in this repository.

Information about the exact dataset files used in the experiments is available in:

```text
data/README.md
data/raw_manifest.json
data/raw_manifest.sha256
```

## Installation

Clone the repository:

```bash
git clone git@github.com:gouthamdyapa/counterfactual-fraud-networks.git
cd counterfactual-fraud-networks
```

Create a Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the tests:

```bash
pytest -q
```

## Reproducibility

Detailed reproduction instructions are available in:

```text
docs/REPRODUCIBILITY.md
```

The machine-readable experimental results are stored in:

```text
results/main/
results/counterfactual/
```

## Citation

The accompanying paper is currently under review.

A machine-readable citation template is provided in `CITATION.cff`.

## Author

**Goutam Dyapa**

IEEE Member

## Research Status

The accompanying paper has been submitted to **IEEE BigData 2026**.

The submitted experimental results are frozen. Documentation and reproducibility improvements may continue while the paper is under review.

## License

This project is licensed under the **Apache License 2.0**.

See the [LICENSE](LICENSE) file for details.