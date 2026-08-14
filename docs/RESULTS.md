# Headline results

## Five-seed selected-model comparison

| Model | PR-AUC mean (SD) | ROC-AUC mean (SD) | F1 mean (SD) |
|---|---:|---:|---:|
| Temporal-neighbor event MLP | 0.2089 (0.0099) | 0.7942 (0.0136) | 0.2450 (0.0137) |
| Plain Graph Memory | 0.2757 (0.0022) | 0.8113 (0.0130) | 0.2629 (0.0179) |
| Hub-Suppressed Graph Memory | 0.2744 (0.0096) | 0.8040 (0.0123) | 0.2814 (0.0155) |

## Counterfactual robustness
- Plain mean top-1 / top-5 / top-10 absolute-effect concentration: 23.9% / 46.0% / 57.0%
- Hub-suppressed: 10.3% / 35.0% / 45.2%
- Hub-suppressed mean absolute relationship effect: illicit 0.0917; licit 0.0502
- Illicit bootstrap 95% CI: 0.0750–0.1096
- Licit bootstrap 95% CI: 0.0361–0.0660

See the JSON/CSV files under `results/` for exact values.
