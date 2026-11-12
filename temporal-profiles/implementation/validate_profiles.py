#!/usr/bin/env python3
"""Independent, frozen-corpus validation of exact attainable walk profiles.

The oracle does not import or inspect candidate helpers. It enumerates every
legal subset of original optional event IDs and actual strict chained tuples
ending at the specified root. The root endpoint is inherited from the original
theorem definition; the v1 contract had accidentally omitted this condition.
The v1 corpus, oracle, protocol, and first specification-mismatch run are kept.
Run --prepare once, --oracle-only before the candidate is ready, then --run.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import platform
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "validation_cases.json"
PROTOCOL = HERE / "validation_protocol.json"
RESULTS = HERE / "validation_results"
SEED = 20261104
HUGE = 2 ** 130


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def event(eid, source, target, timestamp, cost=1, status="optional"):
    return {"id": eid, "source": source, "target": target, "time": timestamp,
            "cost": cost, "status": status}


def tuple_inventory(events, root):
    """Enumerate actual tuples, requiring the final target to equal root.

    Passing root=None is used only by the explicit global-vs-root fixture.
    """
    pairs, triples = [], []
    for i, first in enumerate(events):
        for j, second in enumerate(events):
            if (first["target"] == second["source"] and first["time"] < second["time"]
                    and (root is None or second["target"] == root)):
                pairs.append((i, j))
    for i, first in enumerate(events):
        for j, second in enumerate(events):
            for k, third in enumerate(events):
                if (first["target"] == second["source"] and
                    second["target"] == third["source"] and
                    first["time"] < second["time"] < third["time"] and
                    (root is None or third["target"] == root)):
                    triples.append((i, j, k))
    return pairs, triples


def direct_counts(events, root):
    pairs, triples = tuple_inventory(events, root)
    return {"w2": len(pairs), "w3": len(triples)}


def independent_validity(instance):
    """Oracle-side contract audit, independent from candidate validation."""
    if type(instance) is not dict:
        raise ValueError("instance must be a dict")
    if type(instance.get("root")) is not str or not instance["root"]:
        raise ValueError("root must be a nonempty string")
    if type(instance.get("events")) is not list:
        raise ValueError("events must be a list")
    if type(instance.get("min_w2", 0)) is not int:
        raise ValueError("min_w2 must be an integer excluding bool")
    root, successors, vertices, ids = instance["root"], {}, {instance["root"]}, set()
    for e in instance["events"]:
        if type(e) is not dict:
            raise ValueError("each event must be a dict")
        for name in ("id", "source", "target"):
            if type(e.get(name)) is not str or not e[name]:
                raise ValueError(name + " must be a nonempty string")
        if e["id"] in ids:
            raise ValueError("duplicate event ID")
        ids.add(e["id"])
        if type(e.get("time")) is not int:
            raise ValueError("timestamp must be an integer excluding bool")
        cost = e.get("cost", 1)
        if type(cost) is not int or cost < 0:
            raise ValueError("cost must be a nonnegative integer excluding bool")
        if e.get("status", "optional") not in ("optional", "keep", "delete"):
            raise ValueError("unsupported status")
        source, target = e["source"], e["target"]
        if source == target or source == root:
            raise ValueError("self-loop or outgoing root arc")
        if source in successors and successors[source] != target:
            raise ValueError("multiple successors")
        successors[source] = target
        vertices.update((source, target))
    for vertex in vertices:
        seen, depth, current = set(), 0, vertex
        while current != root:
            if current in seen or current not in successors:
                raise ValueError("cycle or disconnected component")
            seen.add(current)
            depth += 1
            if depth > 3:
                raise ValueError("depth exceeds three")
            current = successors[current]


def oracle(instance):
    independent_validity(instance)
    events = instance["events"]
    pairs, triples = tuple_inventory(events, instance["root"])
    # Masks here encode actual original tuples, not grouped event candidates.
    pair_masks = [sum(1 << index for index in pair) for pair in pairs]
    triple_masks = [sum(1 << index for index in triple) for triple in triples]
    forced = [i for i, e in enumerate(events) if e.get("status", "optional") == "delete"]
    optional = [i for i, e in enumerate(events) if e.get("status", "optional") == "optional"]
    forced_mask = sum(1 << index for index in forced)
    forced_cost = sum(events[index].get("cost", 1) for index in forced)
    baseline = {
        "w2": sum(not (mask & forced_mask) for mask in pair_masks),
        "w3": sum(not (mask & forced_mask) for mask in triple_masks),
    }
    table = {}
    for choice in range(1 << len(optional)):
        deleted_mask, optional_cost = forced_mask, 0
        for bit, index in enumerate(optional):
            if choice & (1 << bit):
                deleted_mask |= 1 << index
                optional_cost += events[index].get("cost", 1)
        w2 = sum(not (mask & deleted_mask) for mask in pair_masks)
        w3 = sum(not (mask & deleted_mask) for mask in triple_masks)
        key = (baseline["w2"] - w2, w3)
        if key not in table or optional_cost < table[key]["optional_cost"]:
            table[key] = {
                "loss": key[0], "w2": w2, "w3": w3,
                "optional_cost": optional_cost,
                "total_cost": forced_cost + optional_cost,
                "deleted_ids": sorted(events[i]["id"] for i in range(len(events))
                                      if deleted_mask & (1 << i)),
            }
    return {
        "original": {"w2": len(pairs), "w3": len(triples)},
        "baseline": baseline, "forced_cost": forced_cost, "table": table,
        "legal_deletion_subsets": 1 << len(optional),
        "original_pair_tuples": len(pairs), "original_triple_tuples": len(triples),
    }


def thresholds(base, include_omitted=False):
    n2 = direct_counts([e for e in base["events"] if e.get("status", "optional") != "delete"], base["root"])["w2"]
    values = sorted(set((-3, 0, n2 // 2, max(0, n2 - 1), n2, n2 + 1)))
    return (["omitted"] if include_omitted else []) + values


def build_corpus():
    histories = []

    def add(name, events, note, family="named", values=None, omitted=False):
        instance = {"root": "z", "events": events}
        independent_validity(instance)
        histories.append({"case_id": name, "family": family, "note": note,
                          "instance": instance,
                          "min_w2_values": values if values is not None else thresholds(instance, omitted)})

    add("empty", [], "Empty input; negative and omitted thresholds normalize to zero.", omitted=True)
    add("degree_zero_single", [event("q", "u", "z", 0, 7)], "One optional event belongs to no pair or triple.")
    add("all_mandatory_keep", [event("a", "l", "u", 0, 3, "keep"), event("b", "u", "v", 1, 4, "keep"), event("c", "v", "z", 2, 5, "keep")], "All events must remain.")
    add("all_mandatory_delete", [event("a", "l", "u", 0, HUGE + 3, "delete"), event("b", "u", "v", 1, 0, "delete"), event("c", "v", "z", 2, 7, "delete")], "No optional events; mandatory cost exceeds 128 bits.")
    add("forced_B_original_roles", [event("a", "l", "u", 0, 3), event("b", "u", "v", 1, 9, "delete"), event("c", "v", "z", 2, 2)], "The middle arc disappears after F; original roles and original counts remain authoritative.")
    add("all_mandatory_mixed", [event("a", "l", "u", 0, 3, "keep"), event("b", "u", "v", 1, 4, "delete"), event("c", "v", "z", 2, 5, "keep")], "Forced deletion leaves disconnected surviving events, valid in the original tree.")
    add("A0_A2_retained_B1_B3_C4", [event("a0", "l", "u", 0), event("a2", "l", "u", 2), event("b1", "u", "v", 1, 1, "keep"), event("b3", "u", "v", 3, 1, "keep"), event("c4", "v", "z", 4, 1, "keep")], "At T=2, exact W3 values 0,1,2,3 all occur; W3=2 requires deleting later A2 only.", values=[-3, 0, 2, 4, 5, 6])
    add("weighted_later_A_is_cheaper", [event("a0", "l", "u", 0, 100), event("a2", "l", "u", 2, 1), event("b3", "u", "v", 3, 1, "keep"), event("c4", "v", "z", 4, 1, "keep")], "Exact W3=1 costs one by deleting A2, not one hundred by deleting A0.", values=[-3, 0, 1, 2, 3, 4])
    add("equal_degree_C_cheaper_nonfirst", [event("a", "l", "u", 0, 1, "keep"), event("b", "u", "v", 1, 1, "keep"), event("c0_expensive", "v", "z", 3, 100), event("c1_cheap", "v", "z", 4, 1)], "Equal-degree C events require preserving costs and original identities.")
    add("zero_cost_parallel_multiplicity", [event("a0", "l", "u", 0, 0), event("a1", "l", "u", 0, 0), event("b", "u", "v", 1, 0), event("c0", "v", "z", 2, 0), event("c1", "v", "z", 2, 0)], "Parallel events with identical timestamps are distinct; all deletion costs are zero.")
    add("strict_tie_boundaries", [event("a0", "l", "u", 0, 2), event("a1", "l", "u", 1, 4, "keep"), event("b1", "u", "v", 1, 7), event("b2", "u", "v", 2, 1), event("c2", "v", "z", 2, 3), event("c3", "v", "z", 3, 0, "keep")], "Equality at either transition must exclude the tuple.")
    add("negative_timestamps", [event("a", "l", "u", -8, 2), event("b0", "u", "v", -8, 1), event("b1", "u", "v", -3, 5), event("c0", "v", "z", -3, 0), event("c1", "v", "z", -1, 6)], "Negative times and strict ties.")
    add("multiple_branches_children", [event("a11", "l11", "u11", 0, 2), event("a12", "l12", "u11", 1, 1), event("a2", "l2", "u12", 0, 9), event("a3", "l3", "u21", 1, 0), event("b11", "u11", "v1", 2, 4), event("b12", "u12", "v1", 1, 7, "keep"), event("b21", "u21", "v2", 2, 6), event("c10", "v1", "z", 3, 8), event("c11", "v1", "z", 4, 3, "delete"), event("c20", "v2", "z", 3, 2), event("q", "u0", "z", -1, 0)], "Several root branches, B children and A children; one zero-degree root edge.")
    add("C_degree_greater_than_R", [event("a", "l", "u", 0, 1), event("b1", "u", "v", 1, 1, "keep"), event("b2", "u", "v", 2, 1, "keep"), event("b3", "u", "v", 3, 1, "keep"), event("c", "v", "z", 4, 1)], "At T=5, C's degree three exceeds R=1.", values=[0, 3, 5, 6, 7])
    add("root_parallel_only", [event("q0", "u", "z", 0, 0), event("q1", "u", "z", 1, 9), event("q2", "u", "z", 2, 1, "delete"), event("q3", "u", "z", 3, 7, "keep")], "No pairs or triples; mandatory cost still applies.")
    add("huge_cost_precision", [event("a0", "l", "u", 0, HUGE + 3), event("a1", "l", "u", 1, HUGE + 1), event("b", "u", "v", 2, 1, "keep"), event("c", "v", "z", 3, 1, "keep")], "Distinct costs above 128 bits must not round to a tie.")
    add("extreme_integer_timestamps", [event("a", "l", "u", -(2 ** 150), 3), event("b", "u", "v", 0, 2), event("c", "v", "z", 2 ** 151, 1)], "Timestamps have arbitrary magnitude.")
    add("original_vs_postF_baseline", [event("a0", "l", "u", 0, 5, "delete"), event("a2", "l", "u", 2, 1), event("b1", "u", "v", 1, 2, "keep"), event("b3", "u", "v", 3, 4), event("c4", "v", "z", 4, 7, "keep"), event("c5", "v", "z", 5, 11, "delete")], "Original and post-F counts differ in both coordinates; selection tests both factual anchors.")
    add("depth_two_no_triples", [event("b0", "u0", "v", 0, 3), event("b1", "u1", "v", 1, 0), event("b2", "u1", "v", 2, 8, "delete"), event("c0", "v", "z", 1, 5), event("c1", "v", "z", 3, 1)], "Nontrivial W2 profile with W3 identically zero.")
    add("defaults_omitted", [{"id": "a", "source": "l", "target": "u", "time": 0}, {"id": "b", "source": "u", "target": "v", "time": 1}, {"id": "c", "source": "v", "target": "z", "time": 2}], "Omitted costs/statuses/min_w2 use the declared defaults.", omitted=True)

    for index, stamps in enumerate(itertools.product(range(3), repeat=5)):
        edges = [("a0", "l", "u"), ("a1", "l", "u"), ("b0", "u", "v"), ("b1", "u", "v"), ("c", "v", "z")]
        costs = [0, 2, 1, 7, 3]
        add(f"exhaustive5_{index:03d}", [event(*edge, stamp, cost) for edge, stamp, cost in zip(edges, stamps, costs)],
            "All 3^5 independent timestamp assignments on the fixed five-event path.", family="exhaustive_timestamp")

    rng = random.Random(SEED)
    for index in range(80):
        n_events = 12 if index % 10 == 0 else rng.randrange(1, 13)
        n_vertices = rng.randrange(1, min(7, n_events) + 1)
        depths, edges = {"z": 0}, []
        for node in range(n_vertices):
            source = f"v{node}"
            parent = rng.choice([v for v, depth in depths.items() if depth < 3])
            edges.append((source, parent))
            depths[source] = depths[parent] + 1
        event_edges = list(edges)
        event_edges.extend(rng.choice(edges) for _ in range(n_events - len(edges)))
        rng.shuffle(event_edges)
        events = []
        for j, (source, target) in enumerate(event_edges):
            status = "optional" if index % 10 == 0 else rng.choices(["optional", "keep", "delete"], [65, 20, 15])[0]
            cost = rng.choice([0, 0, 1, 2, 3, 7, 19, 2 ** 128 + j, 2 ** 200 + 17 * j + 1])
            events.append(event(f"r{index:02d}e{j:02d}", source, target, rng.randrange(-3, 5), cost, status))
        add(f"random_{index:02d}", events, "Seeded valid in-arborescence with at most twelve original events.", family="seeded_random")

    relations = []
    chosen = ["A0_A2_retained_B1_B3_C4", "weighted_later_A_is_cheaper", "equal_degree_C_cheaper_nonfirst",
              "multiple_branches_children", "original_vs_postF_baseline", "random_00", "random_10", "random_37"]
    by_id = {history["case_id"]: history for history in histories}
    for name in chosen:
        base = by_id[name]
        for transform in ("input_permutation", "injective_ID_renaming", "affine_timestamps", "positive_cost_scaling"):
            variant = copy.deepcopy(base)
            variant["case_id"] = name + "__" + transform
            variant["family"] = "metamorphic"
            variant["note"] = transform + " of " + name
            events = variant["instance"]["events"]
            relation = {"base_case_id": name, "variant_case_id": variant["case_id"], "transform": transform}
            if transform == "input_permutation":
                rng.shuffle(events)
            elif transform == "injective_ID_renaming":
                mapping = {e["id"]: f"renamed_{len(events)-j:03d}_λ" for j, e in enumerate(events)}
                for e in events:
                    e["id"] = mapping[e["id"]]
                relation["id_mapping"] = mapping
            elif transform == "affine_timestamps":
                for e in events:
                    e["time"] = 7 * e["time"] - 23
                relation["slope"], relation["intercept"] = 7, -23
            else:
                for e in events:
                    e["cost"] = 5 * e.get("cost", 1)
                relation["factor"] = 5
            histories.append(variant)
            relations.append(relation)

    valid = {"root": "z", "events": [event("e", "u", "z", 0)]}
    invalid = []

    def bad(name, instance, why):
        invalid.append({"case_id": name, "instance": instance, "reason": why})

    bad("instance_null", None, "Instance must be a dict.")
    bad("instance_list", [], "Instance must be a dict.")
    for field, values in {"root": [None, "", 1, True], "events": [None, {}, "events"], "min_w2": [None, True, 1.5, "1"]}.items():
        for j, value in enumerate(values):
            instance = copy.deepcopy(valid)
            instance[field] = value
            bad(f"invalid_{field}_{j}", instance, f"Invalid {field} type/value.")
    for field in ("root", "events"):
        instance = copy.deepcopy(valid)
        del instance[field]
        bad("missing_" + field, instance, "Required field is absent.")
    for j, value in enumerate([None, "bad", [], 3]):
        instance = copy.deepcopy(valid)
        instance["events"] = [value]
        bad(f"invalid_event_object_{j}", instance, "An event must be a dict.")
    for field in ("id", "source", "target"):
        for j, value in enumerate([None, "", 7, True]):
            instance = copy.deepcopy(valid)
            instance["events"][0][field] = value
            bad(f"invalid_event_{field}_{j}", instance, "Identifiers and endpoints must be nonempty strings.")
    for field in ("id", "source", "target", "time"):
        instance = copy.deepcopy(valid)
        del instance["events"][0][field]
        bad("missing_event_" + field, instance, "Required event field is absent.")
    for field, values in {"time": [None, True, 1.25, "1"], "cost": [None, True, -1, 1.25, "1"], "status": [None, True, "KEEP", "removed"]}.items():
        for j, value in enumerate(values):
            instance = copy.deepcopy(valid)
            instance["events"][0][field] = value
            bad(f"invalid_event_{field}_{j}", instance, f"Invalid event {field}.")
    bad("duplicate_ids", {"root": "z", "events": [event("e", "u", "z", 0), event("e", "u", "z", 1)]}, "Duplicate original IDs.")
    bad("self_loop", {"root": "z", "events": [event("e", "u", "u", 0)]}, "Self-loop.")
    bad("root_outgoing", {"root": "z", "events": [event("e", "z", "u", 0)]}, "Root cannot have an outgoing arc.")
    bad("cycle", {"root": "z", "events": [event("e0", "u", "v", 0), event("e1", "v", "u", 1)]}, "Directed cycle.")
    bad("multiple_successors", {"root": "z", "events": [event("e0", "u", "v", 0), event("e1", "u", "z", 1), event("e2", "v", "z", 2)]}, "A nonroot vertex has two distinct successors.")
    bad("depth_four", {"root": "z", "events": [event("e0", "l", "u", 0), event("e1", "u", "v", 1), event("e2", "v", "w", 2), event("e3", "w", "z", 3)]}, "Depth exceeds three.")
    bad("disconnected", {"root": "z", "events": [event("e0", "u", "v", 0), event("e1", "w", "z", 1)]}, "A mentioned vertex has no path to the specified root.")
    bad("forced_deleted_root_outgoing", {"root": "z", "events": [event("e", "z", "u", 0, 1, "delete")]}, "Graph validation precedes forced deletion.")
    bad("forced_deleted_depth_four", {"root": "z", "events": [event("e0", "l", "u", 0, 1, "delete"), event("e1", "u", "v", 1), event("e2", "v", "w", 2), event("e3", "w", "z", 3)]}, "Deleted original edges still determine depth.")
    return {"schema_version": 1, "seed": SEED, "histories": histories, "invalid_cases": invalid,
            "metamorphic_relations": relations}


def prepare():
    if CORPUS.exists() or PROTOCOL.exists():
        raise RuntimeError("Frozen corpus/protocol already exists; refusing to regenerate or retune.")
    corpus = build_corpus()
    write_json(CORPUS, corpus)
    families = {}
    for case in corpus["histories"]:
        families[case["family"]] = families.get(case["family"], 0) + 1
    protocol = {
        "schema_version": 1, "status": "frozen_before_first_candidate_call", "seed": SEED,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_filename": CORPUS.name, "corpus_sha256": digest_bytes(CORPUS.read_bytes()),
        "validator_sha256_at_freeze": digest_bytes(Path(__file__).read_bytes()),
        "solver_file_existed_at_freeze": (HERE / "profile_solver.py").exists(),
        "history_count": len(corpus["histories"]), "families": families,
        "threshold_query_count": sum(len(case["min_w2_values"]) for case in corpus["histories"]),
        "invalid_case_count": len(corpus["invalid_cases"]),
        "metamorphic_relation_count": len(corpus["metamorphic_relations"]),
        "oracle": "Enumerate original-ID legal deletion subsets; enumerate actual ordered pairs and triples by endpoint equality and strictly increasing times; no candidate helper imports or inspection.",
        "comparison": "Complete attained key set and minimum optional/total cost for every threshold; every returned original-ID witness checked directly for IDs, statuses, costs, W2 and W3.",
        "threshold_policy": "Before candidate calls: distinct values among -3,0,floor(N2/2),max(0,N2-1),N2,N2+1; named examples add required T; empty/default cases include omitted T.",
        "selection_predicates": ["always", "never", "parity", "residue_islands", "disconnected_count_regions", "exact_middle_W3", "original_count_equal", "baseline_count_equal", "exact_W3_two"],
        "selection_budgets": "None, zero, forced cost, largest attainable total cost plus one; when acceptance is possible also exact minimum accepted total cost and one below when nonnegative.",
        "metamorphic_policy": "Eight fixed histories, each transformed by permutation, injective ID renaming, time -> 7*time-23, and cost -> 5*cost; same frozen thresholds.",
        "runtime_policy": "Finite validation only; elapsed time is not a performance benchmark. No archived model/test execution. No corpus changes after candidate outcomes.",
    }
    write_json(PROTOCOL, protocol)
    print(json.dumps(protocol, sort_keys=True))


def load_frozen():
    corpus, protocol = json.loads(CORPUS.read_text()), json.loads(PROTOCOL.read_text())
    actual = digest_bytes(CORPUS.read_bytes())
    if actual != protocol["corpus_sha256"]:
        raise AssertionError("Frozen corpus digest does not match protocol")
    return corpus, protocol


def amend_root_endpoint():
    """Version the parent-authorized semantic correction without new histories."""
    corpus, prior_protocol = load_frozen()
    require(corpus["schema_version"] == 1, "Root endpoint amendment already applied")
    snapshot = RESULTS / "frozen_v1"
    prior_hashes = json.loads((snapshot / "hash_manifest.json").read_text())
    for filename, expected_hash in prior_hashes.items():
        require(digest_bytes((snapshot / filename).read_bytes()) == expected_hash,
                "Preserved v1 snapshot digest changed: " + filename)
    require(prior_hashes[CORPUS.name] == digest_bytes(CORPUS.read_bytes()), "Current corpus differs from v1 before amendment")
    require(prior_hashes[PROTOCOL.name] == digest_bytes(PROTOCOL.read_bytes()), "Current protocol differs from v1 before amendment")
    original_histories = [{"case_id": case["case_id"], "instance": case["instance"]} for case in corpus["histories"]]
    history_hash = digest_bytes(canonical(original_histories))
    changes = []
    for case in corpus["histories"]:
        prior = case["min_w2_values"]
        rederived = thresholds(case["instance"], "omitted" in prior)
        amended = (["omitted"] if "omitted" in prior else []) + sorted({t for t in prior + rederived if t != "omitted"})
        if amended != prior:
            changes.append({"case_id": case["case_id"], "prior_thresholds": prior,
                            "amended_thresholds": amended,
                            "added_thresholds": [t for t in amended if t not in prior]})
        case["min_w2_values"] = amended
    corpus["schema_version"] = 2
    corpus["semantic_definition"] = "W_h counts strictly time-increasing directed original-event h-tuples whose final target equals the specified root."
    corpus["specification_amendment"] = {
        "reason": "The root agent's initial validation contract omitted the inherited ending-at-root condition; the original theorem explicitly includes it.",
        "definition_source": "analysis/theorem_manuscript_v4/positive_section.tex, first W_h model definition",
        "original_history_data_sha256": history_hash,
        "history_or_event_data_changed": False,
        "threshold_policy": "Retain every prior query; add any missing root-baseline-derived threshold among -3,0,floor(N2/2),max(0,N2-1),N2,N2+1.",
        "threshold_changes": changes,
        "fixture_note_corrections": {
            "C_degree_greater_than_R": "Under root-ending semantics use T=2, N2=3, R=1. C deletion is forbidden by its degree, but A deletion may change W3 at zero W2 loss.",
            "weighted_later_A_is_cheaper": "Under root-ending semantics the nontrivial retained-B/C example is feasible at T=1.",
        },
    }
    after_histories = [{"case_id": case["case_id"], "instance": case["instance"]} for case in corpus["histories"]]
    require(digest_bytes(canonical(after_histories)) == history_hash, "Amendment changed a frozen event history")
    write_json(CORPUS, corpus)
    protocol = copy.deepcopy(prior_protocol)
    protocol.update({
        "schema_version": 2,
        "status": "frozen_after_specification_correction_before_root_ending_candidate_calls",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_sha256": digest_bytes(CORPUS.read_bytes()),
        "validator_sha256_at_freeze": digest_bytes(Path(__file__).read_bytes()),
        "previous_v1_hashes": prior_hashes,
        "previous_v1_frozen_at_utc": prior_protocol["frozen_at_utc"],
        "original_history_data_sha256": history_hash,
        "threshold_query_count": sum(len(case["min_w2_values"]) for case in corpus["histories"]),
        "prior_threshold_query_count": prior_protocol["threshold_query_count"],
        "threshold_query_policy": corpus["specification_amendment"]["threshold_policy"],
        "oracle": "Enumerate original-ID legal deletion subsets; enumerate actual ordered pairs and triples by endpoint equality, strictly increasing timestamps, and final target equal to root; no candidate helper imports or inspection.",
        "semantic_definition": corpus["semantic_definition"],
        "specification_correction": corpus["specification_amendment"],
        "prior_run_classification": "Specification/oracle mismatch caused by omitted root endpoint in the root agent's contract; not a confirmed candidate defect.",
        "semantic_fixture": "The all-mandatory three-event path has two global pairs but exactly one pair ending at the root; both interpretations have one triple.",
    })
    write_json(PROTOCOL, protocol)
    record = {
        "amendment_type": "root_agent_authorized_specification_correction",
        "prior_v1_hashes": prior_hashes,
        "amended_v2_hashes": {filename: digest_bytes((HERE / filename).read_bytes())
                              for filename in ("validate_profiles.py", "validation_cases.json", "validation_protocol.json")},
        "unchanged_history_data_sha256": history_hash,
        "histories_changed": 0,
        "prior_threshold_queries": prior_protocol["threshold_query_count"],
        "amended_threshold_queries": protocol["threshold_query_count"],
        "threshold_changes": changes,
        "prior_run_preserved": "validation_results/run_20261104T064405.550125Z_757c08ac48be",
        "prior_run_interpretation": protocol["prior_run_classification"],
        "definition_source": corpus["specification_amendment"]["definition_source"],
        "no_candidate_calls_during_amendment": True,
    }
    write_json(RESULTS / "specification_correction.json", record)
    snapshot_v2 = RESULTS / "frozen_v2"
    snapshot_v2.mkdir(exist_ok=False)
    for filename in ("validate_profiles.py", "validation_cases.json", "validation_protocol.json"):
        (snapshot_v2 / filename).write_bytes((HERE / filename).read_bytes())
    write_json(snapshot_v2 / "hash_manifest.json", record["amended_v2_hashes"])
    print(json.dumps({key: value for key, value in record.items() if key != "threshold_changes"}, sort_keys=True))


def make_instance(case, threshold):
    instance = copy.deepcopy(case["instance"])
    if threshold != "omitted":
        instance["min_w2"] = threshold
    return instance


def filtered_table(brute, threshold):
    threshold = max(0, 0 if threshold == "omitted" else threshold)
    n2 = brute["baseline"]["w2"]
    if threshold > n2:
        return None
    return {key: profile for key, profile in brute["table"].items() if key[0] <= n2 - threshold}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def root_endpoint_fixture(corpus):
    case = next(case for case in corpus["histories"] if case["case_id"] == "all_mandatory_keep")
    events, root = case["instance"]["events"], case["instance"]["root"]
    global_pairs, global_triples = tuple_inventory(events, None)
    root_pairs, root_triples = tuple_inventory(events, root)
    require(len(global_pairs) == 2 and len(root_pairs) == 1,
            "Explicit endpoint fixture must distinguish two global pairs from one root-ending pair")
    require(len(global_triples) == len(root_triples) == 1, "Explicit endpoint fixture triple count is malformed")
    return {
        "case_id": case["case_id"], "root": root,
        "global_counts": {"w2": len(global_pairs), "w3": len(global_triples)},
        "root_ending_counts": {"w2": len(root_pairs), "w3": len(root_triples)},
        "global_pair_ids": [[events[i]["id"] for i in pair] for pair in global_pairs],
        "root_ending_pair_ids": [[events[i]["id"] for i in pair] for pair in root_pairs],
    }


def special_oracle_assertions(oracles, corpus):
    root_endpoint_fixture(corpus)
    require(oracles["all_mandatory_keep"]["original"] == {"w2": 1, "w3": 1}, "Oracle does not count walks ending at root")
    table = filtered_table(oracles["A0_A2_retained_B1_B3_C4"], 2)
    require({key[1] for key in table} == {0, 1, 2, 3}, "Named A example must attain all four exact W3 values")
    profile = next(p for p in table.values() if p["w3"] == 2)
    require(profile["deleted_ids"] == ["a2"], "W3=2 counterexample must require later A2")
    table = filtered_table(oracles["weighted_later_A_is_cheaper"], 1)
    profile = min((p for p in table.values() if p["w3"] == 1), key=lambda p: p["total_cost"])
    require(profile["total_cost"] == 1 and profile["deleted_ids"] == ["a2"], "Weighted later-A example is malformed")
    table = filtered_table(oracles["equal_degree_C_cheaper_nonfirst"], 1)
    profile = min((p for p in table.values() if p["w3"] == 1), key=lambda p: p["total_cost"])
    require(profile["total_cost"] == 1 and profile["deleted_ids"] == ["c1_cheap"], "Equal-degree C example is malformed")
    brute = oracles["original_vs_postF_baseline"]
    require(brute["original"]["w2"] != brute["baseline"]["w2"] and brute["original"]["w3"] != brute["baseline"]["w3"], "Original-vs-baseline example lacks the declared contrast")
    require(filtered_table(oracles["C_degree_greater_than_R"], 2).keys() == {(0, 0), (0, 3)}, "C degree > R example is malformed")


def build_oracles(corpus):
    all_oracles = {case["case_id"]: oracle(case["instance"]) for case in corpus["histories"]}
    for case in corpus["invalid_cases"]:
        try:
            independent_validity(case["instance"])
        except ValueError:
            pass
        else:
            raise AssertionError("Declared invalid corpus case is valid: " + case["case_id"])
    special_oracle_assertions(all_oracles, corpus)
    for relation in corpus["metamorphic_relations"]:
        base, variant = all_oracles[relation["base_case_id"]], all_oracles[relation["variant_case_id"]]
        factor = relation.get("factor", 1)
        require(base["original"] == variant["original"] and base["baseline"] == variant["baseline"], "Metamorphic oracle count mismatch")
        require(set(base["table"]) == set(variant["table"]), "Metamorphic oracle key mismatch")
        for key in base["table"]:
            require(variant["table"][key]["total_cost"] == factor * base["table"][key]["total_cost"], "Metamorphic oracle cost mismatch")
    return all_oracles


def coverage_summary(corpus, oracles):
    cases = corpus["histories"]
    events = [e for case in cases for e in case["instance"]["events"]]
    return {
        "histories": len(cases), "threshold_queries": sum(len(case["min_w2_values"]) for case in cases),
        "invalid_schema_or_graph_cases": len(corpus["invalid_cases"]),
        "legal_deletion_subsets_enumerated": sum(o["legal_deletion_subsets"] for o in oracles.values()),
        "original_pair_tuples_enumerated": sum(o["original_pair_tuples"] for o in oracles.values()),
        "original_triple_tuples_enumerated": sum(o["original_triple_tuples"] for o in oracles.values()),
        "unrestricted_exact_profile_entries": sum(len(o["table"]) for o in oracles.values()),
        "threshold_filtered_expected_entries": sum(len(filtered_table(oracles[case["case_id"]], threshold) or {}) for case in cases for threshold in case["min_w2_values"]),
        "max_events": max(len(case["instance"]["events"]) for case in cases),
        "max_optional_events": max(sum(e.get("status", "optional") == "optional" for e in case["instance"]["events"]) for case in cases),
        "max_baseline_W2": max(o["baseline"]["w2"] for o in oracles.values()),
        "max_baseline_W3": max(o["baseline"]["w3"] for o in oracles.values()),
        "max_cost_bit_length": max((e.get("cost", 1).bit_length() for e in events), default=0),
        "histories_with_forced_deletions": sum(any(e.get("status", "optional") == "delete" for e in case["instance"]["events"]) for case in cases),
        "histories_with_forced_keeps": sum(any(e.get("status", "optional") == "keep" for e in case["instance"]["events"]) for case in cases),
        "histories_with_zero_cost": sum(any(e.get("cost", 1) == 0 for e in case["instance"]["events"]) for case in cases),
        "metamorphic_relations": len(corpus["metamorphic_relations"]),
    }


def oracle_only():
    start = time.perf_counter()
    corpus, protocol = load_frozen()
    oracles = build_oracles(corpus)
    summary = {"status": "oracle_preflight_passed", "corpus_sha256": protocol["corpus_sha256"],
               "coverage": coverage_summary(corpus, oracles), "elapsed_validation_seconds": time.perf_counter() - start,
               "candidate_calls": 0, "candidate_implementation_read": False,
               "semantic_endpoint_fixture": root_endpoint_fixture(corpus)}
    write_json(RESULTS / "oracle_preflight.json", summary)
    tables = {name: {"original": o["original"], "baseline": o["baseline"], "forced_cost": o["forced_cost"],
                     "profiles": [o["table"][key] for key in sorted(o["table"])]} for name, o in oracles.items()}
    write_json(RESULTS / "oracle_tables.json", tables)
    write_json(RESULTS / "root_endpoint_fixture.json", summary["semantic_endpoint_fixture"])
    print(json.dumps(summary, sort_keys=True))


def verify_profile(profile, instance, brute, threshold):
    require(type(profile) is dict, "profile is not a dictionary")
    for name in ("loss", "w2", "w3", "optional_cost", "total_cost"):
        require(type(profile.get(name)) is int and profile[name] >= 0, "invalid profile integer: " + name)
    deleted = profile.get("deleted_ids")
    require(type(deleted) is list and all(type(x) is str for x in deleted), "deleted_ids must be a list of strings")
    require(deleted == sorted(set(deleted)), "deleted_ids must be sorted and unique")
    events = instance["events"]
    by_id = {e["id"]: e for e in events}
    require(set(deleted) <= set(by_id), "witness contains an ID absent from the original instance")
    chosen = set(deleted)
    forced = {e["id"] for e in events if e.get("status", "optional") == "delete"}
    keep = {e["id"] for e in events if e.get("status", "optional") == "keep"}
    require(forced <= chosen, "witness omitted a forced deletion")
    require(not keep & chosen, "witness deleted a forced keep")
    total = sum(by_id[eid].get("cost", 1) for eid in chosen)
    optional = sum(by_id[eid].get("cost", 1) for eid in chosen - forced)
    require(profile["total_cost"] == total, "witness total cost differs")
    require(profile["optional_cost"] == optional, "witness optional cost differs")
    require(total == optional + brute["forced_cost"], "forced and optional costs do not add up")
    counts = direct_counts([e for e in events if e["id"] not in chosen], instance["root"])
    require(profile["w2"] == counts["w2"] and profile["w3"] == counts["w3"], "witness counts differ from strict original-event tuple count")
    require(profile["loss"] == brute["baseline"]["w2"] - counts["w2"], "loss must be relative to post-F baseline")
    require(counts["w2"] >= threshold, "witness violates normalized minimum W2")


def verify_result(result, instance, brute):
    require(type(result) is dict, "result is not a dictionary")
    threshold = max(0, instance.get("min_w2", 0))
    expected = filtered_table(brute, threshold)
    require(result.get("original") == brute["original"], "original counts differ")
    require(result.get("baseline") == brute["baseline"], "post-F baseline counts differ")
    require(type(result.get("min_w2")) is int and result["min_w2"] == threshold, "threshold normalization differs")
    require(type(result.get("forced_cost")) is int and result["forced_cost"] == brute["forced_cost"], "forced cost differs")
    require(result.get("reason") is None or type(result.get("reason")) is str, "reason has invalid type")
    require(type(result.get("stats")) is dict, "stats must be a dictionary")
    require(type(result.get("profiles")) is list, "profiles must be a list")
    if expected is None:
        require(result.get("status") == "infeasible", "T>N2 must be infeasible")
        require(result.get("R") is None and result["profiles"] == [], "infeasible result must have R=null and no profiles")
        return 0
    require(result.get("status") == "ok", "feasible instance must be ok")
    require(type(result.get("R")) is int and result["R"] == brute["baseline"]["w2"] - threshold, "R differs")
    keys = [(p.get("loss"), p.get("w3")) for p in result["profiles"]]
    require(keys == sorted(set(keys)), "profiles must be sorted by unique (loss,w3)")
    require(set(keys) == set(expected), "complete profile key mismatch: missing=" + repr(sorted(set(expected)-set(keys))) + "; extra=" + repr(sorted(set(keys)-set(expected))))
    for profile in result["profiles"]:
        verify_profile(profile, instance, brute, threshold)
        reference = expected[(profile["loss"], profile["w3"])]
        for field in ("w2", "w3", "optional_cost", "total_cost"):
            require(profile[field] == reference[field], "minimum value mismatch for " + field)
    return len(keys)


def predicates(brute):
    original, baseline = brute["original"], brute["baseline"]
    middle = baseline["w3"] // 2
    return [
        ("always", lambda w2, w3: True),
        ("never", lambda w2, w3: False),
        ("parity", lambda w2, w3: (w2 + w3) % 2 == 0),
        ("residue_islands", lambda w2, w3: (3 * w2 + 5 * w3) % 7 in (0, 3)),
        ("disconnected_count_regions", lambda w2, w3: (w3 % 3 == 1 and w2 % 2 == 0) or (w3 == 0 and w2 % 3 == 2)),
        ("exact_middle_W3", lambda w2, w3: w3 == middle),
        ("original_count_equal", lambda w2, w3: w2 == original["w2"] and w3 == original["w3"]),
        ("baseline_count_equal", lambda w2, w3: w2 == baseline["w2"] and w3 == baseline["w3"]),
        ("exact_W3_two", lambda w2, w3: w3 == 2),
    ]


def verify_selections(module, result, instance, brute, audit, counters):
    threshold = max(0, instance.get("min_w2", 0))
    expected = filtered_table(brute, threshold) or {}
    calls, witnesses = 0, 0
    for name, accept in predicates(brute):
        accepted = [p for p in expected.values() if accept(p["w2"], p["w3"])]
        budgets = {0, brute["forced_cost"], max((p["total_cost"] for p in expected.values()), default=0) + 1}
        if accepted:
            minimum = min(p["total_cost"] for p in accepted)
            budgets.add(minimum)
            if minimum > 0:
                budgets.add(minimum - 1)
        for budget in [None] + sorted(budgets):
            possible = [p for p in accepted if budget is None or p["total_cost"] <= budget]
            counters["selection_query_calls"] += 1
            selected = module.select_profile(result, accept, max_cost=budget)
            calls += 1
            record = {"predicate": name, "max_cost": budget, "returned": selected}
            audit.append(record)
            if not possible:
                require(selected is None, "selection returned a profile when acceptance/budget permits none: " + name)
            else:
                require(selected is not None, "selection omitted an attainable accepted profile: " + name)
                verify_profile(selected, instance, brute, threshold)
                witnesses += 1
                counters["selection_witnesses_checked"] += 1
                require(accept(selected["w2"], selected["w3"]), "selection predicate failed: " + name)
                require(budget is None or selected["total_cost"] <= budget, "selection total monetary budget failed")
                require(selected["total_cost"] == min(p["total_cost"] for p in possible), "selection is not minimum total cost: " + name)
                key = (selected["loss"], selected["w3"])
                require(key in expected and selected["total_cost"] == expected[key]["total_cost"], "selection is absent from exact minimum table")
    return calls, witnesses


def run_candidate(candidate_path):
    started = time.perf_counter()
    corpus, protocol = load_frozen()
    require(digest_bytes(Path(__file__).read_bytes()) == protocol["validator_sha256_at_freeze"],
            "Validator changed after the amended protocol was frozen")
    solver_hash = digest_bytes(candidate_path.read_bytes())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output_dir = RESULTS / ("run_" + timestamp + "_" + solver_hash[:12])
    output_dir.mkdir(parents=True)
    counters = {"candidate_solve_calls": 0, "candidate_invalid_calls": 0, "selection_query_calls": 0,
                "profile_entries_compared": 0, "profile_witnesses_checked": 0, "selection_witnesses_checked": 0,
                "histories_completed": 0, "threshold_queries_completed": 0, "metamorphic_relations_checked": 0}
    summary = {"status": "running", "corpus_sha256": protocol["corpus_sha256"], "solver_sha256": solver_hash,
               "validator_sha256": digest_bytes(Path(__file__).read_bytes()), "candidate_path": str(candidate_path),
               "protocol_sha256": digest_bytes(PROTOCOL.read_bytes()),
               "semantic_definition": corpus.get("semantic_definition"),
               "semantic_endpoint_fixture": root_endpoint_fixture(corpus),
               "candidate_implementation_inspected_by_oracle_author": False,
               "environment": {"python": sys.version, "platform": platform.platform(), "implementation": platform.python_implementation()},
               "counters": counters, "started_at_utc": datetime.now(timezone.utc).isoformat()}
    outputs, selections, result_index = [], [], {}
    current = {"stage": "oracle"}
    try:
        oracles = build_oracles(corpus)
        summary["coverage"] = coverage_summary(corpus, oracles)
        spec = importlib.util.spec_from_file_location("attainable_profiles_candidate", candidate_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        require(callable(getattr(module, "solve_profiles", None)), "candidate lacks solve_profiles")
        require(callable(getattr(module, "select_profile", None)), "candidate lacks select_profile")
        for case in corpus["histories"]:
            brute = oracles[case["case_id"]]
            for threshold in case["min_w2_values"]:
                current = {"stage": "valid_profile", "case_id": case["case_id"], "threshold": threshold}
                instance = make_instance(case, threshold)
                original_input = copy.deepcopy(instance)
                counters["candidate_solve_calls"] += 1
                result = module.solve_profiles(instance)
                outputs.append({"case_id": case["case_id"], "threshold": threshold,
                                "input_sha256": digest_bytes(canonical(original_input)), "output_sha256": digest_bytes(canonical(result)),
                                "result": result})
                require(instance == original_input, "solve_profiles mutated its input")
                n = verify_result(result, original_input, brute)
                counters["profile_entries_compared"] += n
                counters["profile_witnesses_checked"] += n
                result_index[(case["case_id"], str(threshold))] = result
                current["stage"] = "selection"
                selection_audit = []
                verify_selections(module, result, original_input, brute, selection_audit, counters)
                selections.append({"case_id": case["case_id"], "threshold": threshold, "queries": selection_audit})
                counters["threshold_queries_completed"] += 1
            counters["histories_completed"] += 1
        for case in corpus["invalid_cases"]:
            current = {"stage": "invalid_input", "case_id": case["case_id"]}
            counters["candidate_invalid_calls"] += 1
            try:
                result = module.solve_profiles(copy.deepcopy(case["instance"]))
            except ValueError as exc:
                outputs.append({"case_id": case["case_id"], "expected_exception": "ValueError", "observed_exception": type(exc).__name__, "message": str(exc)})
            except Exception as exc:
                raise AssertionError("invalid schema/graph raised " + type(exc).__name__ + " instead of ValueError") from exc
            else:
                raise AssertionError("invalid schema/graph did not raise ValueError: " + repr(result))
        for relation in corpus["metamorphic_relations"]:
            current = {"stage": "metamorphic", **relation}
            base_case = next(case for case in corpus["histories"] if case["case_id"] == relation["base_case_id"])
            factor = relation.get("factor", 1)
            for threshold in base_case["min_w2_values"]:
                base = result_index[(relation["base_case_id"], str(threshold))]
                variant = result_index[(relation["variant_case_id"], str(threshold))]
                require(base["status"] == variant["status"] and base["original"] == variant["original"] and base["baseline"] == variant["baseline"], "candidate metamorphic header mismatch")
                left = {(p["loss"], p["w3"]): p for p in base["profiles"]}
                right = {(p["loss"], p["w3"]): p for p in variant["profiles"]}
                require(set(left) == set(right), "candidate metamorphic key mismatch")
                for key in left:
                    require(right[key]["total_cost"] == factor * left[key]["total_cost"] and right[key]["optional_cost"] == factor * left[key]["optional_cost"], "candidate metamorphic cost mismatch")
            counters["metamorphic_relations_checked"] += 1
        require(digest_bytes(candidate_path.read_bytes()) == solver_hash, "candidate source changed during validation")
        summary["status"] = "passed"
    except Exception as exc:
        summary["status"] = "failed"
        summary["failure"] = {"context": current, "exception": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        write_json(output_dir / "discrepancy.json", summary["failure"])
    finally:
        summary["elapsed_validation_seconds"] = time.perf_counter() - started
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output_dir / "candidate_outputs.json", outputs)
        write_json(output_dir / "selection_outputs.json", selections)
        summary["output_files"] = {
            "candidate_outputs.json": digest_bytes((output_dir / "candidate_outputs.json").read_bytes()),
            "selection_outputs.json": digest_bytes((output_dir / "selection_outputs.json").read_bytes()),
        }
        write_json(output_dir / "summary.json", summary)
        write_json(RESULTS / "latest_run.json", {"directory": str(output_dir), "summary": summary})
        print(json.dumps({"directory": str(output_dir), **summary}, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--amend-root-endpoint", action="store_true")
    mode.add_argument("--oracle-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--candidate", type=Path, default=HERE / "profile_solver.py")
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return 0
    if args.amend_root_endpoint:
        amend_root_endpoint()
        return 0
    if args.oracle_only:
        oracle_only()
        return 0
    return run_candidate(args.candidate.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
