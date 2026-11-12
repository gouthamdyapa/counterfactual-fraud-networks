#!/usr/bin/env python3
"""Build the explorer's finite, exhaustively checked reference tables.

Uses the unchanged reference solver for five existing small fixtures.  A separate
enumerator checks every legal deletion subset with an explicit root-ending event
tuple counter; it does not call the solver's counting or optimization helpers.
No original fixture, manuscript, or recorded research result is overwritten.

Python 3.8+; standard library only.  Run verify_data.py for a read-only check.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple


HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
SOLVER_PATH = STUDY / "implementation" / "profile_solver.py"
DATA_PATH = HERE / "data.js"
JS_PREFIX = "window.TEMPORAL_EXPLORER_DATA = "

CASE_SPECS = (
    {
        "id": "nonmonotone",
        "path": "implementation/examples/nonmonotone.json",
        "title": "An exact target changes the choice",
        "description": "Two deletions have the same cost but leave different three-event counts.",
        "lesson": "Deleting a_late leaves W3 = 2; deleting a_early leaves W3 = 1. Both cost 1 and preserve W2 = 2. Only the first meets the exact target W3 = 2, while both satisfy W3 <= 2.",
        "default_quota": 2,
        "default_target": 2,
        "default_mode": "exact",
        "default_budget": None,
    },
    {
        "id": "weighted_a",
        "path": "implementation/examples/weighted_a.json",
        "title": "The cheaper deletion wins",
        "description": "Two early events have the same count effect but very different deletion costs.",
        "lesson": "Either optional A-event deletion leaves W3 = 1 and W2 = 1. The solver chooses a_late_cheap, which costs 1 instead of 100.",
        "default_quota": 1,
        "default_target": 1,
        "default_mode": "exact",
        "default_budget": None,
    },
    {
        "id": "weighted_c",
        "path": "implementation/examples/weighted_c.json",
        "title": "An exact count can be missing",
        "description": "Two parallel final events share a timestamp and contribute walks in blocks of two.",
        "lesson": "With W2 >= 2, only W3 = 2 and W3 = 4 are attainable. An exact target of 3 is impossible at any cost, but the upper bound W3 <= 3 is met by deleting c_second_cheap at cost 1. The parallel events keep distinct IDs.",
        "default_quota": 2,
        "default_target": 3,
        "default_mode": "exact",
        "default_budget": None,
    },
    {
        "id": "forced_baseline",
        "path": "implementation/examples/forced_baseline.json",
        "title": "Mandatory deletions change the baseline",
        "description": "A required middle-event deletion removes both original walks and costs 7.",
        "lesson": "The original counts are W2 = 1 and W3 = 1. Deleting b_forced is mandatory, so the baseline becomes (0, 0) and every allowed result costs at least 7. Requiring W2 >= 1 is infeasible even with an unlimited budget.",
        "default_quota": 0,
        "default_target": 0,
        "default_mode": "exact",
        "default_budget": None,
    },
    {
        "id": "illustration",
        "path": "illustration/instance.json",
        "title": "A larger worked example",
        "description": "Ten events combine four incoming paths and four final transactions toward one root.",
        "lesson": "The original counts are W2 = 10 and W3 = 4. With W2 >= 5, deleting A2 attains the exact target W3 = 1 at cost 1 while preserving W2 = 10. A lower quota permits extra loss; it does not require using that loss. Explore other quotas and targets to see the full minimum-cost table.",
        "default_quota": 5,
        "default_target": 1,
        "default_mode": "exact",
        "default_budget": None,
    },
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def walk_counts(events: List[Dict[str, Any]], root: str) -> Tuple[int, int]:
    """Count explicit strict event pairs/triples whose last event ends at root.

    This deliberately uses tuple enumeration, not the reference solver's roles,
    bisect counting, group construction, or dynamic programs.  Equal timestamps
    cannot extend a walk; distinct original events remain distinct choices.
    """
    w2 = 0
    w3 = 0
    for first in events:
        for second in events:
            if first["target"] != second["source"] or first["time"] >= second["time"]:
                continue
            if second["target"] == root:
                w2 += 1
            for third in events:
                if (second["target"] == third["source"]
                        and second["time"] < third["time"]
                        and third["target"] == root):
                    w3 += 1
    return w2, w3


def enumerate_legal_deletions(instance: Dict[str, Any]) -> Tuple[Dict[Tuple[int, int], int], int]:
    """Return exact minimum total costs by count pair over all legal subsets."""
    events = instance["events"]
    optional = [event for event in events if event["status"] == "optional"]
    forced_ids = {event["id"] for event in events if event["status"] == "delete"}
    table = {}
    for mask in range(1 << len(optional)):
        deleted = forced_ids | {
            event["id"] for index, event in enumerate(optional) if mask & (1 << index)
        }
        survivors = [event for event in events if event["id"] not in deleted]
        key = walk_counts(survivors, instance["root"])
        cost = sum(event["cost"] for event in events if event["id"] in deleted)
        if key not in table or cost < table[key]:
            table[key] = cost
    return table, 1 << len(optional)


def load_solver():
    name = "temporal_profile_explorer_reference_solver"
    spec = importlib.util.spec_from_file_location(name, str(SOLVER_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the packaged reference solver")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves class metadata through the containing module.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def normalized_instance(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "root": raw["root"],
        "min_w2": raw.get("min_w2", 0),
        "events": [
            {
                "id": event["id"], "source": event["source"],
                "target": event["target"], "time": event["time"],
                "cost": event.get("cost", 1), "status": event.get("status", "optional"),
            }
            for event in raw["events"]
        ],
    }


def check_result(instance: Dict[str, Any], result: Dict[str, Any],
                 expected: Dict[Tuple[int, int], int], quota: int) -> int:
    events = instance["events"]
    forced_ids = {event["id"] for event in events if event["status"] == "delete"}
    keep_ids = {event["id"] for event in events if event["status"] == "keep"}
    event_by_id = {event["id"]: event for event in events}
    original = walk_counts(events, instance["root"])
    baseline = walk_counts([event for event in events if event["id"] not in forced_ids], instance["root"])
    forced_cost = sum(event_by_id[event_id]["cost"] for event_id in forced_ids)
    if result["original"] != {"w2": original[0], "w3": original[1]}:
        raise AssertionError("Reference solver original counts disagree with tuple enumeration")
    if result["baseline"] != {"w2": baseline[0], "w3": baseline[1]}:
        raise AssertionError("Reference solver baseline counts disagree with tuple enumeration")
    if result["forced_cost"] != forced_cost or result["min_w2"] != quota:
        raise AssertionError("Reference solver forced cost or quota differs")
    expected_status = "infeasible" if quota > baseline[0] else "ok"
    expected_r = None if expected_status == "infeasible" else baseline[0] - quota
    if result["status"] != expected_status or result["R"] != expected_r:
        raise AssertionError("Reference solver feasibility status or preservation loss differs")

    actual = {}
    for profile in result["profiles"]:
        key = (profile["w2"], profile["w3"])
        if key in actual:
            raise AssertionError("Duplicate exact profile key")
        actual[key] = profile["total_cost"]
        ids = profile["deleted_ids"]
        deleted = set(ids)
        if len(ids) != len(deleted) or not deleted.issubset(event_by_id):
            raise AssertionError("Invalid original-ID witness")
        if not forced_ids.issubset(deleted) or keep_ids.intersection(deleted):
            raise AssertionError("Witness violates mandatory event choices")
        counts = walk_counts([event for event in events if event["id"] not in deleted], instance["root"])
        cost = sum(event_by_id[event_id]["cost"] for event_id in deleted)
        if counts != key or key[0] < quota or cost != profile["total_cost"]:
            raise AssertionError("Witness counts, quota, or total cost disagree")
        if profile["optional_cost"] != cost - forced_cost or profile["loss"] != baseline[0] - key[0]:
            raise AssertionError("Witness optional cost or baseline loss disagrees")
    wanted = {key: cost for key, cost in expected.items() if key[0] >= quota}
    if actual != wanted:
        raise AssertionError("Reference profiles disagree with the full exhaustive minimum-cost table")
    return len(actual)


def build_data() -> Dict[str, Any]:
    solver = load_solver()
    cases = []
    source_fixtures = []
    subset_count = 0
    table_count = 0
    feasible_table_count = 0
    witness_count = 0
    for spec in CASE_SPECS:
        fixture_path = STUDY / spec["path"]
        raw_bytes = fixture_path.read_bytes()
        instance = normalized_instance(json.loads(raw_bytes.decode("utf-8")))
        source_fixtures.append({"path": spec["path"], "sha256": sha256_bytes(raw_bytes)})
        original = walk_counts(instance["events"], instance["root"])
        exhaustive, subsets = enumerate_legal_deletions(instance)
        quotas = []
        case_witnesses = 0
        for quota in range(original[0] + 1):
            candidate = dict(instance)
            candidate["min_w2"] = quota
            result = solver.solve_profiles(candidate)
            case_witnesses += check_result(candidate, result, exhaustive, quota)
            quotas.append({key: result[key] for key in (
                "min_w2", "baseline", "R", "status", "forced_cost", "profiles"
            )})
            table_count += 1
            feasible_table_count += result["status"] == "ok"
        case = {key: spec[key] for key in (
            "id", "title", "description", "lesson", "default_quota",
            "default_target", "default_mode", "default_budget"
        )}
        case.update(
            root=instance["root"], events=instance["events"],
            original={"w2": original[0], "w3": original[1]}, quotas=quotas,
            source_path=spec["path"],
            verification={"legal_subsets": subsets, "quota_tables": len(quotas),
                          "profile_witnesses": case_witnesses},
        )
        cases.append(case)
        subset_count += subsets
        witness_count += case_witnesses
    return {
        "schema_version": 1,
        "source": {
            "solver_path": "implementation/profile_solver.py",
            "solver_sha256": sha256_bytes(SOLVER_PATH.read_bytes()),
            "fixtures": source_fixtures,
        },
        "verification": {
            "method": "Exhaustive legal original-ID deletion subsets and independent strict root-ending event-tuple counting",
            "case_count": len(cases),
            "legal_subsets": subset_count,
            "quota_tables": table_count,
            "feasible_quota_tables": feasible_table_count,
            "infeasible_quota_tables": table_count - feasible_table_count,
            "profile_witnesses": witness_count,
            "all_minimum_cost_tables_match": True,
            "all_witnesses_verified": True,
            "scope": "Five bundled mathematical examples; not the IBM batch and not an independent human proof review.",
        },
        "cases": cases,
    }


def encode_data(data: Dict[str, Any]) -> bytes:
    # Stable key order and no timestamp make regeneration byte-for-byte portable.
    # Escaping '<' keeps this payload safe when embedded in a standalone HTML file.
    payload = json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2).replace("<", "\\u003c")
    return (JS_PREFIX + payload + ";\n").encode("utf-8")


def main() -> int:
    data = build_data()
    encoded = encode_data(data)
    DATA_PATH.write_bytes(encoded)
    print("Wrote {} ({} bytes)".format(DATA_PATH.name, len(encoded)))
    print(json.dumps(data["verification"], indent=2, sort_keys=True))
    print("data.js SHA-256: {}".format(sha256_bytes(encoded)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
