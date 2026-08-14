import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel): return json.loads((ROOT/rel).read_text())

def test_graph_five_seed_summary():
    d=load("results/main/graph_memory_5seed_results.json")
    assert d["seeds"] == [13,21,42,77,101]
    assert abs(d["plain_summary"]["pr_auc"]["mean"] - 0.27573937906212115) < 1e-12
    assert abs(d["hub_summary"]["f1"]["mean"] - 0.28137472032347305) < 1e-12

def test_temporal_neighbor_baseline():
    d=load("results/main/temporal_neighbor_event_5seed_results.json")
    assert d["seeds"] == [13,21,42,77,101]
    assert abs(d["summary"]["pr_auc"]["mean"] - 0.20892991992101395) < 1e-12

def test_counterfactual_artifacts_exist():
    required=[
        "results/counterfactual/elliptic_historical_counterfactual_v0_results.json",
        "results/counterfactual/elliptic_hub_robust_counterfactual_results.json",
        "paper/figures/predictive_progression.png",
        "paper/figures/counterfactual_concentration.png",
    ]
    for f in required: assert (ROOT/f).exists(), f
