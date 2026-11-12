#!/usr/bin/env python3
"""Offline, resumable complete-context profile evaluation; Python 3.8+."""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time
import uuid
import zipfile

from pilot_data import DataError, build_cache, extract_context, node_key, parse_minute
from pilot import validate_tree
from profile_solver import solve_profiles
from batch_verify import count_walks, verify_table, compare_table
from batch_io import discover_prior_inputs, parse_drag_path, resolve_input


HERE = Path(__file__).resolve().parent
IMMUTABLE = {
    "profile_solver.py": "a9f8f2c9f276055ab570940d784244192d177c16299f7a295ad75c481de7f4ba",
    "pilot_data.py": "217e8b5d2b5c9f984cbebfb40529234716e7cbdd68cbf98445cd9bfa4fe7572a",
    "pilot.py": "2a3fd2c6280feb4a8add19c30e49a3b56d408a93fac1bde85dafcb206e93bfbe",
}
CODE_FILES = ("batch.py", "batch_verify.py", "batch_io.py", "pilot.py",
              "pilot_data.py", "profile_solver.py", "run_batch.command")
LIMIT_KEYS = {
    "max_context_events", "max_vertices", "max_discovery_events", "max_solver_events",
    "max_R", "max_profile_coordinates", "solver_timeout_seconds",
    "oracle_max_optional_events", "oracle_timeout_seconds", "invocation_time_limit_seconds",
}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
QUERY_ID = re.compile(r"q[0-9]{4}\Z")


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def _value_hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".pending")
    temporary.write_bytes(_canonical(value))
    temporary.replace(path)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _runtime():
    return {"python": platform.python_version(), "operating_system": platform.system(),
            "machine": platform.machine(), "platform": platform.platform()}


def _int(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError("{} must be an integer >= {}".format(name, minimum))
    return value


def _fields(value, allowed, name, required=None):
    if not isinstance(value, dict):
        raise ValueError(name + " must be an object")
    if set(value) - set(allowed):
        raise ValueError("Unknown fields in " + name)
    if required is not None and set(required) - set(value):
        raise ValueError("Missing fields in " + name)


def _digest(value, name):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ValueError(name + " must be a lowercase SHA-256 string")


def load_inputs(protocol_path, cohort_path):
    protocol, cohort = _read_json(protocol_path), _read_json(cohort_path)
    keys = {"version", "protocol_id", "study_label", "dataset", "cohort", "window_minutes",
            "policies", "limits", "reference_anchor", "interpretation"}
    _fields(protocol, keys, "protocol", keys)
    if _int(protocol["version"], "version", 1) != 1:
        raise ValueError("Unsupported protocol version")
    for key in ("protocol_id", "study_label"):
        if not isinstance(protocol[key], str) or not protocol[key]:
            raise ValueError(key + " must be a nonempty string")
    _fields(protocol["dataset"], {"expected_sha256", "expected_rows", "synthetic"}, "dataset",
            {"expected_sha256", "expected_rows", "synthetic"})
    _digest(protocol["dataset"]["expected_sha256"], "source hash")
    _int(protocol["dataset"]["expected_rows"], "source row count")
    if not isinstance(protocol["dataset"]["synthetic"], bool):
        raise ValueError("dataset.synthetic must be Boolean")
    cohort_keys = {"sha256", "query_count", "source_sampling_protocol_sha256"}
    _fields(protocol["cohort"], cohort_keys, "cohort identity", cohort_keys)
    _digest(protocol["cohort"]["sha256"], "cohort hash")
    _int(protocol["cohort"]["query_count"], "query count", 1)
    sampling_hash = protocol["cohort"]["source_sampling_protocol_sha256"]
    if sampling_hash is not None:
        _digest(sampling_hash, "source sampling protocol hash")
    if _file_hash(cohort_path) != protocol["cohort"]["sha256"]:
        raise ValueError("The query manifest differs from the frozen protocol hash")
    _int(protocol["window_minutes"], "window minutes", 1)
    policy_keys = {"preservation_percentages", "target_fraction", "comparators", "budgets"}
    _fields(protocol["policies"], policy_keys, "policies", policy_keys)
    policies = protocol["policies"]
    for name in ("preservation_percentages", "comparators", "budgets"):
        values = policies[name]
        if not isinstance(values, list) or not values:
            raise ValueError("Policy lists must be nonempty")
        if len({json.dumps(x, sort_keys=True) for x in values}) != len(values):
            raise ValueError("Policy lists must not contain duplicates")
    for value in policies["preservation_percentages"]:
        _int(value, "preservation percent", 1)
        if value > 100:
            raise ValueError("Preservation percent must not exceed 100")
    for value in policies["budgets"]:
        _int(value, "budget")
    if any(value not in ("at_most", "exact") for value in policies["comparators"]):
        raise ValueError("Unsupported count comparator")
    _fields(policies["target_fraction"], {"numerator", "denominator"}, "target fraction",
            {"numerator", "denominator"})
    fraction = policies["target_fraction"]
    _int(fraction["numerator"], "target numerator")
    _int(fraction["denominator"], "target denominator", 1)
    if fraction["numerator"] > fraction["denominator"]:
        raise ValueError("Target fraction cannot exceed one")
    _fields(protocol["limits"], LIMIT_KEYS, "limits", LIMIT_KEYS)
    for key, value in protocol["limits"].items():
        if key.endswith("seconds"):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(key + " must be finite and positive")
        else:
            _int(value, key, 0 if key in ("max_R", "oracle_max_optional_events") else 1)
    anchor = protocol["reference_anchor"]
    if anchor is not None:
        anchor_keys = {"query_id", "context_events", "vertices", "w2", "w3",
                       "minimum_cost_at_full_preservation", "exact_target_at_full_preservation"}
        _fields(anchor, anchor_keys, "reference anchor", anchor_keys)
        if not isinstance(anchor["query_id"], str) or not QUERY_ID.fullmatch(anchor["query_id"]):
            raise ValueError("Invalid anchor query ID")
        for key in ("context_events", "vertices", "w2", "w3", "minimum_cost_at_full_preservation"):
            _int(anchor[key], "anchor " + key)
        if anchor["exact_target_at_full_preservation"] not in ("unattainable", "attainable"):
            raise ValueError("Invalid exact-target anchor expectation")
    if not isinstance(protocol["interpretation"], dict) or any(not isinstance(v, str) for v in protocol["interpretation"].values()):
        raise ValueError("Interpretation must contain explanatory strings")
    _fields(cohort, {"metadata", "queries"}, "cohort file", {"metadata", "queries"})
    if not isinstance(cohort["metadata"], dict) or not isinstance(cohort["queries"], list):
        raise ValueError("Malformed cohort file")
    queries = cohort["queries"]
    if len(queries) != protocol["cohort"]["query_count"]:
        raise ValueError("Frozen cohort query count does not match")
    if sampling_hash is not None and cohort["metadata"].get("protocol_sha256") != sampling_hash:
        raise ValueError("Original sampling protocol identity differs")
    pairs = set()
    for i, query in enumerate(queries):
        _fields(query, {"query_id", "root", "cutoff", "hash", "packed_key", "root_bank",
                        "root_account", "cutoff_text"}, "query",
                {"query_id", "root_bank", "root_account", "cutoff_text"})
        if query["query_id"] != "q%04d" % i:
            raise ValueError("Queries must retain their contiguous frozen order")
        root = node_key(query["root_bank"], query["root_account"])
        cutoff = parse_minute(query["cutoff_text"])
        if "cutoff" in query and query["cutoff"] != cutoff:
            raise ValueError("Recorded cutoff text and integer disagree")
        if (root, cutoff) in pairs:
            raise ValueError("Repeated account/time query")
        pairs.add((root, cutoff))
    if anchor is not None and anchor["query_id"] not in {q["query_id"] for q in queries}:
        raise ValueError("Reference anchor is missing from the cohort")
    return protocol, cohort


def _policy_groups(before, policies):
    groups = {}
    for percent in policies["preservation_percentages"]:
        minimum = (percent * before["w2"] + 99) // 100
        groups.setdefault(minimum, []).append(percent)
    return [(minimum, aliases) for minimum, aliases in groups.items()]


def _goal_rows(protocol, target, result=None, reason="not_computed"):
    rows = []
    for comparator in protocol["policies"]["comparators"]:
        candidates = [] if result is None else [p for p in result["profiles"]
            if (p["w3"] <= target if comparator == "at_most" else p["w3"] == target)]
        best = min(candidates, key=lambda p: (p["total_cost"], p["w3"], p["loss"], tuple(p["deleted_ids"]))) if candidates else None
        for budget in protocol["policies"]["budgets"]:
            row = {"comparator": comparator, "target_w3": target, "budget": budget,
                   "status": "not_evaluated", "reason_code": reason,
                   "minimum_cost": None, "minimum_cost_outcome": None}
            if result is not None:
                if best is None:
                    row.update(status="unattainable", reason_code="no_attainable_accepted_coordinate")
                else:
                    cost = best["total_cost"]
                    outcome = {"w2": best["w2"], "w3": best["w3"], "cost": cost,
                               "deleted_event_count": len(best["deleted_ids"])}
                    status = "over_budget" if cost > budget else ("already_satisfied" if cost == 0 else "solution_found")
                    row.update(status=status, reason_code="complete_verified_profile_lookup",
                               minimum_cost=cost, minimum_cost_outcome=outcome)
            rows.append(row)
    return rows


def _run_process(command, output, timeout):
    start = time.monotonic()
    try:
        child = subprocess.run(command, cwd=str(HERE), capture_output=True, text=True,
                               timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "elapsed_seconds": time.monotonic() - start}, None, "Worker reached its configured timeout."
    elapsed = time.monotonic() - start
    if child.returncode != 0 or not Path(output).is_file():
        return {"status": "failed", "elapsed_seconds": elapsed}, None, (child.stderr or "Worker output missing")[-8000:]
    try:
        payload = _read_json(output)
    except (OSError, ValueError) as exc:
        return {"status": "failed", "elapsed_seconds": elapsed}, None, str(exc)
    return {"status": "completed", "elapsed_seconds": elapsed}, payload, None


def _evaluate_quota(instance, aliases, before, target, protocol, folder, local_details):
    limits = protocol["limits"]
    minimum = instance["min_w2"]
    allowance = before["w2"] - minimum
    row = {"min_w2": minimum, "preservation_percentages": aliases, "R": allowance,
           "status": "resource_limit", "reason_code": "not_started", "profile_count": None,
           "possible_profile_coordinates": (allowance + 1) * (before["w3"] + 1),
           "solver": {"status": "not_run", "elapsed_seconds": 0.0, "solve_seconds": None},
           "witness": {"status": "not_run", "issues_count": 0, "witnesses_checked": 0, "elapsed_seconds": 0.0},
           "oracle": {"status": "not_run", "elapsed_seconds": 0.0, "subsets_checked": None},
           "goals": []}

    def stop(status, reason):
        row.update(status=status, reason_code=reason)
        row["goals"] = _goal_rows(protocol, target, reason=reason)
        return row

    if len(instance["events"]) > limits["max_solver_events"]:
        return stop("resource_limit", "solver_event_limit")
    if allowance > limits["max_R"]:
        return stop("resource_limit", "preservation_loss_limit")
    if row["possible_profile_coordinates"] > limits["max_profile_coordinates"]:
        return stop("resource_limit", "profile_coordinate_limit")
    folder.mkdir(parents=True, exist_ok=True)
    instance_path = folder / "instance.json"
    output_path = folder / "solver_worker.json"
    _write_json(instance_path, instance)
    command = [sys.executable, "-B", str(HERE / "batch.py"), "_solve",
               "--instance", str(instance_path), "--output", str(output_path)]
    worker, payload, error = _run_process(command, output_path, limits["solver_timeout_seconds"])
    row["solver"].update(worker)
    if worker["status"] != "completed":
        local_details["solver_error"] = error
        return stop("resource_limit" if worker["status"] == "timeout" else "execution_error",
                    "solver_timeout" if worker["status"] == "timeout" else "solver_worker_failed")
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        local_details["solver_error"] = "Malformed worker payload"
        return stop("verification_failed", "malformed_solver_payload")
    inner_time = payload.get("solver_seconds")
    if isinstance(inner_time, bool) or not isinstance(inner_time, (float, int)) or not math.isfinite(inner_time) or inner_time < 0:
        return stop("verification_failed", "invalid_solver_timing")
    row["solver"]["solve_seconds"] = inner_time
    result = payload["result"]
    _write_json(folder / "profiles.json", result)
    verify_started = time.monotonic()
    replay = verify_table(instance, result)
    row["witness"] = {"status": replay["status"], "issues_count": len(replay.get("issues", [])),
                      "witnesses_checked": replay.get("witnesses_checked", 0),
                      "elapsed_seconds": time.monotonic() - verify_started}
    _write_json(folder / "witness_checks.json", replay)
    if replay["status"] != "passed":
        local_details["witness_issues"] = replay.get("issues", [])
        return stop("verification_failed", "profile_witness_mismatch")
    row["profile_count"] = len(result["profiles"])
    optional_count = sum(e.get("status", "optional") == "optional" for e in instance["events"])
    if optional_count > limits["oracle_max_optional_events"]:
        row["oracle"]["status"] = "skipped_size"
    else:
        oracle_path = folder / "exhaustive_oracle.json"
        command = [sys.executable, "-B", str(HERE / "batch_verify.py"), "--instance", str(instance_path),
                   "--output", str(oracle_path), "--max-events", str(limits["oracle_max_optional_events"])]
        worker, oracle, error = _run_process(command, oracle_path, limits["oracle_timeout_seconds"])
        row["oracle"]["elapsed_seconds"] = worker["elapsed_seconds"]
        if worker["status"] == "timeout":
            row["oracle"]["status"] = "timeout"
        elif worker["status"] != "completed":
            row["oracle"]["status"] = "failed"
            local_details["oracle_error"] = error
            return stop("execution_error", "oracle_worker_failed")
        else:
            comparison = compare_table(result, oracle)
            _write_json(folder / "oracle_comparison.json", comparison)
            row["oracle"]["status"] = comparison["status"]
            if isinstance(oracle, dict):
                row["oracle"]["subsets_checked"] = oracle.get("subsets_checked")
                row["oracle"]["enumeration_seconds"] = oracle.get("elapsed_seconds")
            row["oracle"]["pairs_compared"] = comparison.get("pairs_compared", 0)
            if comparison["status"] != "passed":
                local_details["oracle_issues"] = comparison.get("issues", [])
                return stop("verification_failed", "exhaustive_profile_mismatch")
    row.update(status="completed", reason_code="complete_solver_with_replayed_profiles")
    row["goals"] = _goal_rows(protocol, target, result=result)
    return row


def _anchor_check(record, protocol):
    anchor = protocol["reference_anchor"]
    if anchor is None or record["query_id"] != anchor["query_id"]:
        return None
    if record["extraction"]["status"] != "complete":
        return {"status": "not_checked", "checks": {}}
    checks = {"context_events": record.get("context_event_count") == anchor["context_events"],
              "vertices": record.get("vertex_count") == anchor["vertices"],
              "w2": record.get("counts", {}).get("w2") == anchor["w2"],
              "w3": record.get("counts", {}).get("w3") == anchor["w3"]}
    complete = False
    for quota in record["quota_results"]:
        if 100 not in quota["preservation_percentages"] or quota["status"] != "completed":
            continue
        at_most = next((g for g in quota["goals"] if g["comparator"] == "at_most"), None)
        exact = next((g for g in quota["goals"] if g["comparator"] == "exact"), None)
        if at_most is not None:
            checks["minimum_cost"] = at_most["minimum_cost"] == anchor["minimum_cost_at_full_preservation"]
        if exact is not None:
            observed = "unattainable" if exact["status"] == "unattainable" else "attainable"
            checks["exact_target"] = observed == anchor["exact_target_at_full_preservation"]
        complete = at_most is not None and exact is not None
    return {"status": "failed" if not all(checks.values()) else ("passed" if complete else "partial"),
            "checks": checks}


def _evaluate_case(query, index, cache, protocol, run_folder):
    attempt = run_folder / "cases" / query["query_id"] / ("attempt_" + uuid.uuid4().hex[:10])
    attempt.mkdir(parents=True, exist_ok=False)
    local = {"query": query, "quota_details": {}}
    _write_json(attempt / "query.json", query)
    record = {"query_id": query["query_id"], "query_index": index,
              "status": "input_error", "reason_code": "not_started",
              "extraction": {"status": "not_run", "elapsed_seconds": 0.0},
              "structure": {"status": "unknown", "maximum_depth": None},
              "counts": None, "count_seconds": 0.0,
              "context_event_count": None, "vertex_count": None, "global_window_event_count": None,
              "planned_unique_quotas": 0, "quota_results": []}
    started = time.monotonic()

    def finish(status, reason):
        record.update(status=status, reason_code=reason,
                      elapsed_seconds=time.monotonic() - started)
        anchor = _anchor_check(record, protocol)
        if anchor is not None:
            record["reference_anchor"] = anchor
            if anchor["status"] == "failed":
                record.update(status="verification_failed", reason_code="reference_anchor_mismatch")
        local["record"] = record
        _write_json(attempt / "local_details.json", local)
        return record

    extraction_start = time.monotonic()
    try:
        context = extract_context(cache, query["root_bank"], query["root_account"], query["cutoff_text"],
            window_minutes=protocol["window_minutes"],
            max_context_events=protocol["limits"]["max_context_events"],
            max_vertices=protocol["limits"]["max_vertices"],
            max_discovery_events=protocol["limits"]["max_discovery_events"])
    except DataError as exc:
        limited = exc.code == "resource_limit"
        record["extraction"] = {"status": "resource_limit" if limited else "input_error",
                                "elapsed_seconds": time.monotonic() - extraction_start}
        local["extraction_error"] = str(exc)
        return finish("extraction_resource_limit" if limited else "input_error",
                      "extraction_cap_reached" if limited else "extraction_failed")
    record["extraction"] = {"status": "complete", "elapsed_seconds": time.monotonic() - extraction_start}
    for key in ("context_event_count", "vertex_count", "global_window_event_count"):
        record[key] = context[key]
    _write_json(attempt / "context.json", context)
    count_start = time.monotonic()
    before = count_walks(context["events"], context["root"])
    record["counts"] = before
    record["count_seconds"] = time.monotonic() - count_start
    if not context["events"]:
        record["structure"]["status"] = "empty"
        return finish("empty_context", "no_induced_events")
    try:
        depths = validate_tree(context["events"], context["root"])
    except ValueError as exc:
        record["structure"]["status"] = "ineligible"
        local["structure_reason"] = str(exc)
        return finish("unsupported_structure", "original_context_not_supported")
    record["structure"] = {"status": "eligible", "maximum_depth": max(depths.values())}
    groups = _policy_groups(before, protocol["policies"])
    record["planned_unique_quotas"] = len(groups)
    fraction = protocol["policies"]["target_fraction"]
    target = fraction["numerator"] * before["w3"] // fraction["denominator"]
    for minimum, aliases in groups:
        instance = {"root": context["root"], "min_w2": minimum, "events": context["events"]}
        details = {}
        quota = _evaluate_quota(instance, aliases, before, target, protocol,
                                attempt / ("quota_" + str(minimum)), details)
        local["quota_details"][str(minimum)] = details
        record["quota_results"].append(quota)
        if quota["status"] in ("verification_failed", "execution_error"):
            return finish(quota["status"], quota["reason_code"])
    limited = any(q["status"] == "resource_limit" or q["oracle"]["status"] == "timeout"
                  for q in record["quota_results"])
    return finish("evaluated_with_limits" if limited else "evaluated",
                  "completed_with_declared_limits" if limited else "all_requested_profile_tables_completed")


def _flat_goals(records, protocol):
    for record in records:
        for percent in protocol["policies"]["preservation_percentages"]:
            quota = next((q for q in record["quota_results"] if percent in q["preservation_percentages"]), None)
            if quota is None:
                goals = _goal_rows(protocol, None, reason=record["reason_code"])
            else:
                goals = quota["goals"]
            for goal in goals:
                row = {"query_id": record["query_id"], "query_index": record["query_index"],
                       "preservation_percentage": percent,
                       "min_w2": None if quota is None else quota["min_w2"],
                       "actual_R": None if quota is None else quota["R"],
                       "baseline_w2": None if record["counts"] is None else record["counts"]["w2"],
                       "baseline_w3": None if record["counts"] is None else record["counts"]["w3"],
                       "oracle_status": "not_run" if quota is None else quota["oracle"]["status"]}
                row.update(goal)
                yield row


def _distribution(values):
    clean = sorted(float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    if not clean:
        return {"count": 0, "total_seconds": 0.0, "median_seconds": None, "p95_seconds": None, "max_seconds": None}
    return {"count": len(clean), "total_seconds": sum(clean), "median_seconds": statistics.median(clean),
            "p95_seconds": clean[max(0, math.ceil(.95 * len(clean)) - 1)], "max_seconds": clean[-1]}


def _summary(state, records, protocol, status, reason, unfinished_query=None):
    quotas = [q for r in records for q in r["quota_results"]]
    goals = list(_flat_goals(records, protocol))
    count = lambda predicate: sum(bool(predicate(r)) for r in records)
    coverage = {
        "extractions_completed": count(lambda r: r["extraction"]["status"] == "complete"),
        "extraction_resource_limits": count(lambda r: r["extraction"]["status"] == "resource_limit"),
        "extraction_errors": count(lambda r: r["extraction"]["status"] == "input_error"),
        "nonempty_eligible_contexts": count(lambda r: r["structure"]["status"] == "eligible"),
        "ineligible_contexts": count(lambda r: r["structure"]["status"] == "ineligible"),
        "empty_contexts": count(lambda r: r["structure"]["status"] == "empty"),
        "structural_status_unknown": count(lambda r: r["structure"]["status"] == "unknown"),
        "complete_contexts_with_w3": count(lambda r: r["counts"] is not None and r["counts"]["w3"] > 0),
        "eligible_contexts_with_w3": count(lambda r: r["structure"]["status"] == "eligible" and r["counts"]["w3"] > 0),
        "complete_contexts_without_w3": count(lambda r: r["counts"] is not None and r["counts"]["w3"] == 0),
        "planned_unique_quota_tables": sum(r["planned_unique_quotas"] for r in records),
        "completed_profile_tables": sum(q["solver"]["status"] == "completed" for q in quotas),
        "verified_profile_tables": sum(q["witness"]["status"] == "passed" and q["oracle"]["status"] != "mismatch" and q["status"] == "completed" for q in quotas),
        "oracle_checked_tables": sum(q["oracle"]["status"] in ("passed", "mismatch") for q in quotas),
        "oracle_agreement_tables": sum(q["oracle"]["status"] == "passed" for q in quotas),
        "oracle_mismatch_tables": sum(q["oracle"]["status"] == "mismatch" for q in quotas),
        "oracle_size_skipped_tables": sum(q["oracle"]["status"] == "skipped_size" for q in quotas),
        "oracle_timeout_tables": sum(q["oracle"]["status"] == "timeout" for q in quotas),
        "profile_resource_limited_tables": sum(q["status"] == "resource_limit" for q in quotas),
        "witness_mismatch_tables": sum(q["witness"]["status"] == "mismatch" for q in quotas),
    }
    full = len(records) == protocol["cohort"]["query_count"]
    has_limits = bool(coverage["extraction_resource_limits"] or coverage["profile_resource_limited_tables"] or coverage["oracle_timeout_tables"])
    if status == "completed" and has_limits:
        status = "completed_with_limits"
    planned_goals = protocol["cohort"]["query_count"] * len(protocol["policies"]["preservation_percentages"]) * len(protocol["policies"]["comparators"]) * len(protocol["policies"]["budgets"])
    anchor = next((r["reference_anchor"] for r in records if "reference_anchor" in r),
                  {"status": "not_yet_processed" if protocol["reference_anchor"] else "not_applicable", "checks": {}})
    per_policy = {}
    for row in goals:
        key = "preserve_{}pct__{}__budget_{}".format(row["preservation_percentage"], row["comparator"], row["budget"])
        counter = per_policy.setdefault(key, Counter())
        counter[row["status"]] += 1
    summary = {
        "format_version": 1, "application": "temporal_profile_mac_batch",
        "batch_run_id": state["batch_run_id"], "status": status, "reason_code": reason,
        "run_kind": "synthetic_demo" if protocol["protocol_id"].startswith("SYNTHETIC_") else "ibm_cohort_batch",
        "study_label": protocol["study_label"], "reported_at_utc": _now(),
        "full_cohort_processed": full, "planned_queries": protocol["cohort"]["query_count"],
        "recorded_queries": len(records), "pending_queries": protocol["cohort"]["query_count"] - len(records),
        "unfinished_query_id": unfinished_query,
        "source": state.get("source"), "identity_sha256": state["identity_sha256"],
        "protocol_sha256": state["identity"]["protocol_sha256"],
        "cohort_sha256": state["identity"]["cohort_sha256"],
        "code_sha256": state["identity"]["code_sha256"], "runtime": state["identity"]["runtime"],
        "window_minutes": protocol["window_minutes"], "policy_grid": protocol["policies"],
        "limits": protocol["limits"], "coverage": coverage,
        "planned_goal_conditions": planned_goals, "recorded_goal_conditions": len(goals),
        "pending_goal_conditions": planned_goals - len(goals),
        "goal_status_counts": dict(Counter(g["status"] for g in goals)),
        "nonzero_w3_goal_status_counts": dict(Counter(g["status"] for g in goals if g["baseline_w3"] is not None and g["baseline_w3"] > 0)),
        "per_policy_status_counts": {k: dict(v) for k, v in per_policy.items()},
        "case_status_counts": dict(Counter(r["status"] for r in records)),
        "reference_anchor": anchor,
        "timing": {
            "invocations": state["invocations"],
            "cache_setup": _distribution(i["cache_setup_seconds"] for i in state["invocations"]),
            "extraction": _distribution(r["extraction"]["elapsed_seconds"] for r in records),
            "factual_counting": _distribution(r["count_seconds"] for r in records),
            "solver_inner_completed": _distribution(q["solver"]["solve_seconds"] for q in quotas),
            "solver_worker_attempts": _distribution(q["solver"]["elapsed_seconds"] for q in quotas if q["solver"]["status"] != "not_run"),
            "witness_replay": _distribution(q["witness"]["elapsed_seconds"] for q in quotas if q["witness"]["status"] != "not_run"),
            "oracle_worker_attempts": _distribution(q["oracle"]["elapsed_seconds"] for q in quotas if q["oracle"]["status"] in ("passed", "mismatch", "timeout", "failed")),
            "notes": "Cache/setup once per invocation; extraction per query; solver_inner excludes worker startup and file I/O. Worker times include those overheads. No speedup or whole-dataset optimization claim."
        },
        "interpretation": protocol["interpretation"],
        "reporting_notes": [
            "Unsupported and incomplete queries remain in the planned/recorded denominators.",
            "Extraction limits mean structural status unknown; solver limits can occur on eligible complete contexts.",
            "Rounded preservation policies share one computed profile table; flat policy rows retain each predeclared condition.",
            "Oracle size skips/timeouts are not counted as agreement. A completed exact solver with replayed witnesses can have incomplete independent exhaustive checking.",
            "The upload bundle contains aggregate records only; raw contexts and transaction IDs stay in local case files."
        ]
    }
    return summary, goals


def _write_outputs(folder, summary, records, goals, protocol):
    _write_json(folder / "BATCH_SUMMARY.json", summary)
    _write_json(folder / "PROTOCOL.json", protocol)
    for name, rows in (("CASE_RESULTS.jsonl", records), ("GOAL_RESULTS.jsonl", goals)):
        temporary = folder / (name + ".pending")
        with temporary.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
        temporary.replace(folder / name)
    coverage = summary.get("coverage", {})
    lines = ["LOCAL MAC COMPLETE-CONTEXT PROFILE BATCH", "",
             "Status: " + summary["status"], "Run: " + summary["batch_run_id"],
             "Recorded queries: {} / {}".format(summary["recorded_queries"], summary["planned_queries"]),
             "Pending queries: " + str(summary["pending_queries"]),
             "Full cohort processed: " + str(summary["full_cohort_processed"]), "",
             "Runtime: " + json.dumps(summary.get("runtime", {}), sort_keys=True),
             "Coverage: " + json.dumps(coverage, sort_keys=True), "",
             "Goal statuses: " + json.dumps(summary.get("goal_status_counts", {}), sort_keys=True),
             "Historical anchor: " + json.dumps(summary.get("reference_anchor", {}), sort_keys=True), "",
             "Read BATCH_SUMMARY.json for stage timings and CASE_RESULTS.jsonl / GOAL_RESULTS.jsonl for aggregate detail.",
             "The source cohort was previously audited. This is not held-out validation.",
             "Every induced event is retained. Unsupported contexts and resource limits are reported, not trimmed away.",
             "An unattainable goal, an over-budget goal, and incomplete computation have different statuses.",
             "The exact optimizer solves each supported local context, not the entire source CSV as one graph.",
             "No trained fraud-model class change or fraud-effectiveness claim is made."]
    if summary.get("run_kind") == "synthetic_demo":
        lines.append("This report concerns invented demonstration data only.")
    (folder / "RESULTS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    archive = folder / "BATCH_RESULTS.zip"
    temporary = folder / "BATCH_RESULTS.zip.pending"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as out:
        for name in ("BATCH_SUMMARY.json", "CASE_RESULTS.jsonl", "GOAL_RESULTS.jsonl", "PROTOCOL.json", "RESULTS.txt"):
            out.write(folder / name, name)
    temporary.replace(archive)


def _code_hashes():
    hashes = {name: _file_hash(HERE / name) for name in CODE_FILES}
    for name, expected in IMMUTABLE.items():
        if hashes[name] != expected:
            raise ValueError("An immutable solver/pilot module differs from the released version")
    return hashes


def _new_folder(output_dir):
    parent = Path(output_dir).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    name = "batch_{}_{}".format(dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    folder = parent / name
    folder.mkdir(mode=0o700)
    (folder / "case_records").mkdir()
    return folder


def _matching_run(output_dir, identity):
    parent = Path(output_dir).expanduser().resolve()
    if not parent.is_dir():
        return None
    expected = _value_hash(identity)
    candidates = []
    for folder in parent.glob("batch_*"):
        state_path = folder / "STATE.json"
        if state_path.is_file():
            candidates.append((state_path.stat().st_mtime_ns, folder))
        else:
            checkpoint_files = list((folder / "case_records").glob("*.json"))
            if checkpoint_files:
                candidates.append((max(p.stat().st_mtime_ns for p in checkpoint_files), folder))
    candidates.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    for _modified, folder in candidates:
        state_path = folder / "STATE.json"
        if not state_path.is_file():
            raise ValueError("Completed query checkpoints exist but their run state is missing; inspect them or deliberately use --new-run")
        try:
            state = _read_json(state_path)
        except (OSError, ValueError) as exc:
            raise ValueError("An existing batch state is unreadable; inspect it or deliberately use --new-run") from exc
        if not isinstance(state, dict) or not isinstance(state.get("identity"), dict) or not isinstance(state.get("identity_sha256"), str):
            raise ValueError("An existing batch state is malformed; inspect it or deliberately use --new-run")
        if _value_hash(state["identity"]) != state["identity_sha256"]:
            raise ValueError("An existing batch identity checksum does not match")
        if state["identity_sha256"] != expected:
            continue
        if state.get("identity") != identity or _value_hash(state["identity"]) != expected:
            raise ValueError("A matching run has corrupted identity metadata; use --new-run after inspecting it")
        if state.get("batch_run_id") != folder.name or not isinstance(state.get("invocations"), list):
            raise ValueError("A matching run has corrupted state metadata")
        if state.get("status") in ("verification_failed", "input_error", "execution_error"):
            raise ValueError("The most recent matching batch ended with a failure. Review its result before deliberately using --new-run")
        return folder, state
    return None


def _acquire_lock(folder):
    path = folder / "RUNNING.lock"
    token = uuid.uuid4().hex
    try:
        handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        lock = _read_json(path)
        pid = lock.get("pid") if isinstance(lock, dict) else None
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or lock.get("host") != platform.node():
            raise ValueError("Cannot establish whether an existing run lock is stale; inspect the local run folder")
        alive = True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
        except PermissionError:
            pass
        if alive:
            raise ValueError("This batch is already running in another process. Keep that Terminal open")
        path.unlink()
        handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid(), "host": platform.node(), "token": token}, stream)
    return token


def _release_lock(folder, token):
    try:
        path = folder / "RUNNING.lock"
        if _read_json(path).get("token") == token:
            path.unlink()
    except (OSError, ValueError, AttributeError):
        pass


def _load_records(folder, identity_hash, queries):
    available = {p.stem: p for p in (folder / "case_records").glob("*.json")}
    wanted = {q["query_id"] for q in queries}
    if set(available) - wanted:
        raise ValueError("Checkpoint contains an unknown query ID")
    records = []
    gap = False
    for index, query in enumerate(queries):
        path = available.get(query["query_id"])
        if path is None:
            gap = True
            continue
        if gap:
            raise ValueError("Completed query checkpoints are not a contiguous frozen prefix")
        wrapper = _read_json(path)
        if not isinstance(wrapper, dict) or wrapper.get("identity_sha256") != identity_hash:
            raise ValueError("Checkpoint identity differs from this run")
        record = wrapper.get("record")
        if not isinstance(record, dict) or wrapper.get("record_sha256") != _value_hash(record):
            raise ValueError("Checkpoint record checksum does not match")
        if record.get("query_id") != query["query_id"] or record.get("query_index") != index:
            raise ValueError("Checkpoint query/order differs from the frozen cohort")
        required = {"status", "reason_code", "extraction", "structure", "counts", "quota_results", "planned_unique_quotas", "count_seconds"}
        if required - set(record):
            raise ValueError("Checkpoint record is incomplete")
        records.append(record)
    return records


def _checkpoint(folder, identity_hash, record):
    wrapper = {"format_version": 1, "identity_sha256": identity_hash,
               "record_sha256": _value_hash(record), "record": record}
    _write_json(folder / "case_records" / (record["query_id"] + ".json"), wrapper)


def _failure_report(output_dir, status, reason, message, protocol=None, cohort=None, code=None, progress=None):
    folder = _new_folder(output_dir)
    planned = len(cohort["queries"]) if isinstance(cohort, dict) and isinstance(cohort.get("queries"), list) else 0
    summary = {"format_version": 1, "application": "temporal_profile_mac_batch",
               "batch_run_id": folder.name, "status": status, "reason_code": reason,
               "full_cohort_processed": False, "planned_queries": planned,
               "recorded_queries": 0, "pending_queries": planned, "runtime": _runtime(),
               "run_kind": "synthetic_demo" if isinstance(protocol, dict) and str(protocol.get("protocol_id", "")).startswith("SYNTHETIC_") else "ibm_cohort_batch",
               "code_sha256": code or {}, "coverage": {}, "goal_status_counts": {},
               "reference_anchor": {"status": "not_checked"}, "reported_at_utc": _now()}
    _write_json(folder / "LOCAL_FAILURE.json", {"message": message})
    _write_outputs(folder, summary, [], [], protocol or {})
    if progress:
        progress("{}: {}".format(status, message))
        progress("Result bundle: " + str(folder / "BATCH_RESULTS.zip"))
    return summary


def run_batch(csv_path, protocol_path, cohort_path, output_dir, cache_dir,
              resume=True, max_new_queries=None, progress=None):
    """Evaluate a frozen cohort, returning an aggregate report and resumable ID."""
    emit = progress or (lambda message: None)
    start = time.monotonic()
    started_utc = _now()
    protocol = cohort = code = None
    folder = state = lock_token = None
    try:
        if not isinstance(resume, bool):
            raise ValueError("resume must be Boolean")
        if max_new_queries is not None:
            _int(max_new_queries, "chunk size", 1)
        protocol, cohort = load_inputs(protocol_path, cohort_path)
        code = _code_hashes()
        identity = {"source_sha256": protocol["dataset"]["expected_sha256"],
                    "protocol_sha256": _file_hash(protocol_path),
                    "cohort_sha256": _file_hash(cohort_path), "code_sha256": code, "runtime": _runtime()}
        setup_start = time.monotonic()
        emit("Verifying the original source and a completed local cache once for this invocation ...")
        cache = build_cache(csv_path, cache_dir, expected_sha256=protocol["dataset"]["expected_sha256"], progress=emit)
        cache_seconds = time.monotonic() - setup_start
        if cache["row_count"] != protocol["dataset"]["expected_rows"]:
            raise ValueError("Source row count differs from the frozen protocol")
        existing = _matching_run(output_dir, identity) if resume else None
        if existing is None:
            folder = _new_folder(output_dir)
            state = {"format_version": 1, "batch_run_id": folder.name, "started_at_utc": _now(),
                     "identity": identity, "identity_sha256": _value_hash(identity), "invocations": [],
                     "source": {"sha256": cache["source_sha256"], "row_count": cache["row_count"]}, "status": "running"}
            (folder / "FROZEN_COHORT.json").write_bytes(Path(cohort_path).read_bytes())
            (folder / "FROZEN_PROTOCOL_SOURCE.json").write_bytes(Path(protocol_path).read_bytes())
        else:
            folder, state = existing
        lock_token = _acquire_lock(folder)
        records = _load_records(folder, state["identity_sha256"], cohort["queries"])
        if _file_hash(folder / "FROZEN_COHORT.json") != identity["cohort_sha256"] or _file_hash(folder / "FROZEN_PROTOCOL_SOURCE.json") != identity["protocol_sha256"]:
            raise ValueError("Frozen run inputs differ from their original identity")
        if existing is not None and len(records) == len(cohort["queries"]):
            emit("This identical batch has already completed. Reusing its completed case records.")
            summary, goals = _summary(state, records, protocol, "completed", "all_frozen_queries_recorded")
            state["status"] = summary["status"]
            _write_json(folder / "STATE.json", state)
            _write_outputs(folder, summary, records, goals, protocol)
            _release_lock(folder, lock_token)
            return summary
        invocation = {"started_at_utc": started_utc, "cache_setup_seconds": cache_seconds,
                      "cache_reused": cache["cache_reused"], "starting_recorded_queries": len(records),
                      "elapsed_seconds": None, "new_recorded_queries": 0}
        state["invocations"].append(invocation)
        state["status"] = "running"
        _write_json(folder / "STATE.json", state)
        _write_json(folder / "LOCAL_INPUTS.json", {"source_path": str(Path(csv_path).expanduser().resolve()),
                    "cache_dir": str(Path(cache_dir).expanduser().resolve()), "cache": cache})
    except KeyboardInterrupt:
        if folder is not None and lock_token is not None:
            _release_lock(folder, lock_token)
        return _failure_report(output_dir, "interrupted", "interrupted_during_setup", "Setup was interrupted; no new query result was certified.", protocol, cohort, code, emit)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if folder is not None and lock_token is not None:
            _release_lock(folder, lock_token)
        return _failure_report(output_dir, "input_error", "input_or_checkpoint_error", str(exc), protocol, cohort, code, emit)
    except Exception as exc:
        if folder is not None and lock_token is not None:
            _release_lock(folder, lock_token)
        return _failure_report(output_dir, "execution_error", "unexpected_setup_error", str(exc), protocol, cohort, code, emit)
    if existing is not None:
        emit("Resuming {} at query {} of {}.".format(folder.name, len(records) + 1, len(cohort["queries"])))
    else:
        emit("Starting all {} queries in frozen order.".format(len(cohort["queries"])))
    status, reason, unfinished = "completed", "all_frozen_queries_recorded", None
    initial_count = len(records)
    deadline = start + protocol["limits"]["invocation_time_limit_seconds"]
    try:
        for index in range(len(records), len(cohort["queries"])):
            if time.monotonic() >= deadline:
                status, reason = "paused", "invocation_time_limit"
                break
            if max_new_queries is not None and len(records) - initial_count >= max_new_queries:
                status, reason = "paused", "requested_chunk_complete"
                break
            query = cohort["queries"][index]
            unfinished = query["query_id"]
            emit("[{}/{}] {}: extracting and evaluating complete context ...".format(index + 1, len(cohort["queries"]), query["query_id"]))
            record = _evaluate_case(query, index, cache, protocol, folder)
            _checkpoint(folder, state["identity_sha256"], record)
            records.append(record)
            unfinished = None
            emit("  {}: {} ({:.2f}s).".format(query["query_id"], record["status"], record["elapsed_seconds"]))
            if record["status"] in ("verification_failed", "input_error", "execution_error"):
                status, reason = record["status"], record["reason_code"]
                break
    except KeyboardInterrupt:
        status, reason = "interrupted", "user_interrupted"
        emit("Pausing and saving completed query records ...")
    except Exception as exc:
        status, reason = "execution_error", "unexpected_query_error"
        _write_json(folder / "LOCAL_FAILURE.json", {"exception_type": type(exc).__name__, "message": str(exc), "unfinished_query_id": unfinished})
    try:
        if _code_hashes() != code:
            status, reason = "verification_failed", "code_changed_during_run"
    except (OSError, ValueError):
        status, reason = "verification_failed", "code_changed_during_run"
    invocation["elapsed_seconds"] = time.monotonic() - start
    invocation["new_recorded_queries"] = len(records) - initial_count
    invocation["finished_at_utc"] = _now()
    try:
        summary, goals = _summary(state, records, protocol, status, reason, unfinished)
        state["status"] = summary["status"]
        state["unfinished_query_id"] = unfinished
        _write_json(folder / "STATE.json", state)
        _write_outputs(folder, summary, records, goals, protocol)
        return summary
    finally:
        _release_lock(folder, lock_token)


def _console(message):
    print(message, flush=True)


def _print_completion(summary, output_dir):
    folder = Path(output_dir).expanduser().resolve() / summary["batch_run_id"]
    print("\nBatch status: {}. Recorded {} / {} queries; {} pending.".format(
        summary["status"], summary["recorded_queries"], summary["planned_queries"], summary["pending_queries"]))
    if summary.get("run_kind") == "synthetic_demo":
        print("Synthetic demo report: " + str(folder / "BATCH_SUMMARY.json"))
    else:
        print("Upload this IBM batch result bundle to the chat: " + str(folder / "BATCH_RESULTS.zip"))
    if summary["status"] in ("paused", "interrupted"):
        print("Run the same launcher again to continue this batch's remaining queries.")


def _demo(output_dir=None, cache_dir=None, progress=None):
    output_dir = output_dir or HERE / "demo_runs"
    cache_dir = cache_dir or HERE / "demo_cache"
    summary = run_batch(HERE / "examples/demo_transactions.csv", HERE / "examples/demo_protocol.json",
                        HERE / "examples/demo_cohort.json", output_dir, cache_dir, progress=progress)
    expected = _read_json(HERE / "examples/demo_expected.json")
    okay = (summary.get("planned_queries") == expected["planned_queries"]
            and summary.get("recorded_queries") == expected["recorded_queries"]
            and summary.get("full_cohort_processed") is True
            and summary.get("status") == "completed_with_limits"
            and all(summary.get("coverage", {}).get(k) == v for k, v in expected["coverage"].items()))
    folder = Path(output_dir).resolve() / summary["batch_run_id"]
    if okay:
        rows = [json.loads(line) for line in (folder / "CASE_RESULTS.jsonl").read_text().splitlines()]
        okay = {r["query_id"]: r["status"] for r in rows} == expected["case_statuses"]
    _print_completion(summary, output_dir)
    print("Synthetic batch demonstration: " + ("PASS" if okay else "FAILED"))
    return summary, okay


def _interactive():
    print("LOCAL MAC COMPLETE-CONTEXT PROFILE BATCH")
    print("Python {} on {}. First, a five-query invented-data demonstration.\n".format(platform.python_version(), platform.system()))
    _, okay = _demo(progress=_console)
    if not okay:
        print("The demonstration did not pass. Bring its report or Terminal error back to the chat.")
        return 1
    candidates = discover_prior_inputs()
    selected = None
    if len(candidates) == 1:
        selected = candidates[0]
        print("\nFound a compatible earlier pilot: " + str(selected["pilot_dir"]))
        print("Using its saved source CSV and local cache.")
    elif candidates:
        print("\nMore than one compatible earlier pilot was found:")
        for number, candidate in enumerate(candidates, 1):
            print("  {}. {}".format(number, candidate["pilot_dir"]))
        answer = input("Choose its number, or press Return to enter a folder/file path: ").strip()
        if answer:
            if not answer.isdigit() or not 1 <= int(answer) <= len(candidates):
                print("Choose one of the displayed numbers on the next launch.")
                return 2
            selected = candidates[int(answer) - 1]
    if selected is None:
        print("\nDrag the earlier temporal_profile_mac_pilot folder OR the original HI-Small_Trans.csv file here.")
        value = parse_drag_path(input("Earlier pilot folder or CSV: "))
        if value is None:
            print("Only the demonstration ran. The IBM batch has not run.")
            return 0
        selected = resolve_input(value)
    cache_dir = selected.get("cache_dir") or HERE / "cache"
    summary = run_batch(selected["csv_path"], HERE / "batch_protocol.json", HERE / "cohort.json",
                        HERE / "runs", cache_dir, progress=_console)
    _print_completion(summary, HERE / "runs")
    return 0 if summary["status"] in ("completed", "completed_with_limits", "paused", "interrupted") else 1


def main(argv=None):
    if sys.version_info < (3, 8):
        print("Python 3.8 or newer is required.", file=sys.stderr)
        return 2
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("interactive", help="check demo, discover prior inputs, and run/resume cohort")
    demo = commands.add_parser("demo", help="run invented five-query demonstration")
    demo.add_argument("--output-dir", type=Path, default=HERE / "demo_runs")
    demo.add_argument("--cache-dir", type=Path, default=HERE / "demo_cache")
    run = commands.add_parser("run", help="evaluate or resume the frozen cohort")
    run.add_argument("--csv", type=Path, required=True)
    run.add_argument("--cache-dir", type=Path, default=HERE / "cache")
    run.add_argument("--output-dir", type=Path, default=HERE / "runs")
    run.add_argument("--protocol", type=Path, default=HERE / "batch_protocol.json")
    run.add_argument("--cohort", type=Path, default=HERE / "cohort.json")
    run.add_argument("--chunk-size", type=int)
    run.add_argument("--new-run", action="store_true")
    solve = commands.add_parser("_solve", help=argparse.SUPPRESS)
    solve.add_argument("--instance", type=Path, required=True)
    solve.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "_solve":
        instance = _read_json(args.instance)
        started = time.monotonic()
        result = solve_profiles(instance)
        elapsed = time.monotonic() - started
        _write_json(args.output, {"solver_seconds": elapsed, "result": result})
        return 0
    if args.command == "interactive":
        try:
            return _interactive()
        except (EOFError, KeyboardInterrupt):
            print("\nInput selection stopped. No IBM batch was started by this prompt.")
            return 0
        except (OSError, ValueError) as exc:
            print("Input selection error: " + str(exc), file=sys.stderr)
            return 2
    if args.command == "demo":
        _, okay = _demo(args.output_dir, args.cache_dir, _console)
        return 0 if okay else 1
    summary = run_batch(args.csv, args.protocol, args.cohort, args.output_dir, args.cache_dir,
                        resume=not args.new_run, max_new_queries=args.chunk_size, progress=_console)
    _print_completion(summary, args.output_dir)
    return 0 if summary["status"] in ("completed", "completed_with_limits", "paused", "interrupted") else 1


if __name__ == "__main__":
    sys.exit(main())
