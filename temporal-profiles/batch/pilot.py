#!/usr/bin/env python3
"""Local, count-only IBM transaction pilot; Python 3.8+ standard library.

Actual dataset execution is initiated by the user on their computer. Source
transactions are read-only. The unchanged solver is run in a bounded worker.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import time
import uuid

from pilot_data import DataError, build_cache, extract_context, parse_minute
from profile_solver import select_profile, solve_profiles


HERE = Path(__file__).resolve().parent
SOLVER_SHA256 = "a9f8f2c9f276055ab570940d784244192d177c16299f7a295ad75c481de7f4ba"
DEFAULT_LIMITS = {
    "max_context_events": 5000,
    "max_vertices": 5000,
    "max_discovery_events": 200000,
    "max_solver_events": 32,
    "max_R": 8,
    "max_profile_coordinates": 100000,
    "timeout_seconds": 30,
}
CLAIM_SCOPE = (
    "Minimum-cost count-based pattern outcome in the declared complete, eligible "
    "induced window context. No trained-classifier or fraud-effectiveness claim."
)


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=True)
        stream.write("\n")
    temporary.replace(path)


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError("{} must be an integer >= {}".format(name, minimum))
    return value


def _fields(value, allowed, name):
    if not isinstance(value, dict):
        raise ValueError(name + " must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError("Unknown {} field(s): {}".format(name, ", ".join(sorted(unknown))))


def validate_config(config):
    _fields(config, {
        "version", "case_name", "description", "expected_source_sha256", "root",
        "cutoff", "window_minutes", "min_w2", "accept", "max_cost", "limits",
        "reference_expectation",
    }, "config")
    if config.get("version") != 1 or isinstance(config.get("version"), bool):
        raise ValueError("config.version must be 1")
    for key in ("case_name", "cutoff"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise ValueError("config.{} must be a nonempty string".format(key))
    if "description" in config and not isinstance(config["description"], str):
        raise ValueError("description must be a string")
    _fields(config.get("root"), {"bank", "account"}, "root")
    for key in ("bank", "account"):
        if not isinstance(config["root"].get(key), str) or not config["root"][key]:
            raise ValueError("root.{} must be a nonempty string".format(key))
    parse_minute(config["cutoff"])
    _integer(config.get("window_minutes"), "window_minutes", 1)
    _integer(config.get("min_w2"), "min_w2")
    _fields(config.get("accept"), {"kind", "value"}, "accept")
    if config["accept"].get("kind") not in ("w3_at_most", "w3_exact"):
        raise ValueError("accept.kind must be w3_at_most or w3_exact")
    _integer(config["accept"].get("value"), "accept.value")
    if config.get("max_cost") is not None:
        _integer(config["max_cost"], "max_cost")
    source_hash = config.get("expected_source_sha256")
    if source_hash is not None:
        if not isinstance(source_hash, str) or len(source_hash) != 64:
            raise ValueError("expected_source_sha256 must be a SHA-256 string or null")
        if any(c not in "0123456789abcdef" for c in source_hash):
            raise ValueError("expected_source_sha256 must be lowercase hexadecimal")
    _fields(config.get("limits", {}), DEFAULT_LIMITS, "limits")
    limits = dict(DEFAULT_LIMITS)
    limits.update(config.get("limits", {}))
    for key, value in limits.items():
        if key == "timeout_seconds":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("timeout_seconds must be finite and positive")
        else:
            _integer(value, key, 0 if key == "max_R" else 1)
    reference = config.get("reference_expectation", {})
    _fields(reference, {
        "row_count", "global_window_event_count", "context_event_count", "vertex_count",
        "w2", "w3", "event_ids", "minimum_cost", "example_deleted_ids",
    }, "reference_expectation")
    for key, value in reference.items():
        if key in ("event_ids", "example_deleted_ids"):
            if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value) or len(set(value)) != len(value):
                raise ValueError("reference {} must contain distinct string IDs".format(key))
        else:
            _integer(value, "reference." + key)
    return limits


def validate_tree(events, root):
    """Independently check the whole original graph, before forced deletions."""
    if not isinstance(root, str) or not root or not isinstance(events, list):
        raise ValueError("Invalid root or event list")
    successor = {}
    ids = set()
    vertices = {root}
    for e in events:
        if not isinstance(e, dict):
            raise ValueError("Each event must be an object")
        for key in ("id", "source", "target"):
            if not isinstance(e.get(key), str) or not e[key]:
                raise ValueError("Event {} must be a nonempty string".format(key))
        if e["id"] in ids:
            raise ValueError("Duplicate original event ID")
        ids.add(e["id"])
        if isinstance(e.get("time"), bool) or not isinstance(e.get("time"), int):
            raise ValueError("Event time must be an integer")
        _integer(e.get("cost", 1), "event cost")
        if e.get("status", "optional") not in ("optional", "keep", "delete"):
            raise ValueError("Invalid forced status")
        s, t = e["source"], e["target"]
        if s == t:
            raise ValueError("Self-loop in the complete induced context")
        if s == root:
            raise ValueError("The root has an outgoing event in the context")
        if s in successor and successor[s] != t:
            raise ValueError("An account has multiple distinct outgoing neighbors")
        successor[s] = t
        vertices.update((s, t))
    depth = {root: 0}
    for vertex in vertices:
        if vertex in depth:
            continue
        path, seen = [], set()
        current = vertex
        while current not in depth:
            if current in seen:
                raise ValueError("Directed cycle in the complete induced context")
            if current not in successor:
                raise ValueError("An account has no directed path to the root")
            seen.add(current)
            path.append(current)
            current = successor[current]
        level = depth[current]
        for node in reversed(path):
            level += 1
            if level > 3:
                raise ValueError("The complete induced context has depth greater than three")
            depth[node] = level
    return depth


def count_walks(events, root):
    """Literal endpoint-chained pair/triple enumeration, without solver helpers."""
    incoming = defaultdict(list)
    for event in events:
        incoming[event["target"]].append(event)
    w2, w3 = 0, 0
    for last in incoming.get(root, []):
        for middle in incoming.get(last["source"], []):
            if middle["time"] < last["time"]:
                w2 += 1
                for first in incoming.get(middle["source"], []):
                    if first["time"] < middle["time"]:
                        w3 += 1
    return w2, w3


def verify_selection(instance, selected):
    """Verify a returned original-event witness independently of solver logic."""
    issues = []
    if not isinstance(selected, dict):
        return {"verified": False, "issues": ["No selected profile object"], "w2": None, "w3": None}
    deleted = selected.get("deleted_ids")
    if not isinstance(deleted, list) or any(not isinstance(x, str) for x in deleted):
        return {"verified": False, "issues": ["Invalid deletion ID list"], "w2": None, "w3": None}
    if len(set(deleted)) != len(deleted):
        issues.append("Duplicate deletion IDs")
    by_id = {event["id"]: event for event in instance["events"]}
    removed = set(deleted)
    if removed - set(by_id):
        issues.append("Unknown original event IDs")
    forced = {event["id"] for event in instance["events"] if event.get("status", "optional") == "delete"}
    kept = {event["id"] for event in instance["events"] if event.get("status", "optional") == "keep"}
    if not forced <= removed:
        issues.append("A mandatory deletion is missing")
    if removed & kept:
        issues.append("A protected event was deleted")
    remaining = [event for event in instance["events"] if event["id"] not in removed]
    w2, w3 = count_walks(remaining, instance["root"])
    baseline = [event for event in instance["events"] if event["id"] not in forced]
    baseline_w2, _ = count_walks(baseline, instance["root"])
    total = sum(by_id[e].get("cost", 1) for e in removed if e in by_id)
    forced_cost = sum(by_id[e].get("cost", 1) for e in forced)
    expected = {"w2": w2, "w3": w3, "total_cost": total,
                "optional_cost": total - forced_cost, "loss": baseline_w2 - w2}
    for key, value in expected.items():
        if isinstance(selected.get(key), bool) or not isinstance(selected.get(key), int) or selected.get(key) != value:
            issues.append("Reported {} does not match the witness".format(key))
    if w2 < max(0, instance["min_w2"]):
        issues.append("Preservation quota violated")
    return {"verified": not issues, "issues": issues, "w2": w2, "w3": w3,
            "total_cost": total, "deleted_event_count": len(removed)}


def _acceptance(config):
    target = config["accept"]["value"]
    if config["accept"]["kind"] == "w3_exact":
        return lambda w2, w3: w3 == target
    return lambda w2, w3: w3 <= target


def _reference_checks(config, cache, context, before):
    expected = config.get("reference_expectation", {})
    observed = dict(context)
    observed.update(row_count=cache["row_count"], w2=before[0], w3=before[1],
                    event_ids=sorted(e["id"] for e in context["events"]))
    checks = {}
    for key, value in expected.items():
        if key in ("minimum_cost", "example_deleted_ids"):
            continue
        if key == "event_ids":
            checks[key] = observed[key] == sorted(value)
        else:
            checks[key] = observed.get(key) == value
    return checks


def _write_selected_csv(path, instance, selected):
    removed = set(selected["deleted_ids"])
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["original_event_id", "source_bank_account_json", "target_bank_account_json",
                         "source_minute", "cost", "status"])
        for event in instance["events"]:
            if event["id"] in removed:
                writer.writerow([event["id"], event["source"], event["target"],
                                 event["time"], event.get("cost", 1), event.get("status", "optional")])


def _human_report(details, summary):
    lines = ["LOCAL TEMPORAL-PROFILE PILOT", "", "Status: " + summary["status"],
             "Scope: " + CLAIM_SCOPE, "", "Run ID: " + summary["run_id"],
             "Started UTC: " + summary["started_at_utc"],
             "Python: " + summary["runtime"]["python"],
             "Platform: " + summary["runtime"]["platform"], ""]
    cfg = details.get("config", {})
    if not isinstance(cfg, dict):
        cfg = {}
    if cfg:
        lines += ["Case: " + str(cfg.get("case_name")),
                  "Source-time cutoff (exclusive): " + str(cfg.get("cutoff")),
                  "Window in minutes: " + str(cfg.get("window_minutes")),
                  "Root bank/account: " + json.dumps(cfg.get("root")),
                  "Required W2: " + str(cfg.get("min_w2")),
                  "Count acceptance: " + json.dumps(cfg.get("accept")),
                  "Total unit-cost cap: " + str(cfg.get("max_cost")), ""]
    if "source" in summary:
        lines += ["Source CSV SHA-256: " + summary["source"]["sha256"],
                  "Source data rows: " + str(summary["source"]["row_count"]),
                  "Cache reused: " + str(summary["source"]["cache_reused"])]
    if "history" in summary:
        lines += ["Complete global-window events: " + str(summary["history"]["global_window_event_count"]),
                  "Complete induced-context events: " + str(summary["history"]["context_event_count"]),
                  "Context accounts: " + str(summary["history"]["vertex_count"])]
    if "before" in summary:
        lines += ["Original W2/W3: " + str(summary["before"]),
                  "Additional preservation loss allowance R: " + str(summary.get("R"))]
    selected = details.get("selected")
    if selected:
        lines += ["", "SELECTED ORIGINAL EVENTS", json.dumps(selected["deleted_ids"]),
                  "Remaining W2/W3: {}, {}".format(selected["w2"], selected["w3"]),
                  "Total cost: " + str(selected["total_cost"]),
                  "Independent witness verification: " + str(summary.get("witness_verified"))]
    if details.get("message"):
        lines += ["", "Detail: " + details["message"]]
    lines += ["", "Reference checks: " + json.dumps(summary.get("reference_checks", {}), sort_keys=True),
              "Elapsed seconds: " + str(summary["elapsed_seconds"]), "",
              "Historical reference expectations are comparisons, not prefilled current results.",
              "The entire induced context is retained; no tree projection or core pruning is used.",
              "Source records and saved models are unchanged. All hypothetical removals are local outputs.",
              "PILOT_SUMMARY.json contains aggregate evidence and excludes account and transaction IDs.",
              "A resource limit or timeout is incomplete computation, not mathematical infeasibility."]
    return "\n".join(lines) + "\n"


def run_case(csv_path, config, output_dir, cache_dir, progress=None):
    """Run one complete case; returns an aggregate summary with a relative run_id."""
    progress = progress or (lambda message: None)
    started = time.monotonic()
    run_id = "run_{}_{}".format(dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    folder = Path(output_dir).expanduser().resolve() / run_id
    folder.mkdir(parents=True, exist_ok=False)
    summary = {
        "format_version": 1, "application": "temporal_profile_mac_pilot",
        "run_id": run_id, "started_at_utc": _utc_now(), "status": "input_error",
        "claim_scope": CLAIM_SCOPE, "exact_optimality_claim": False,
        "witness_verified": False, "reference_checks": {},
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "operating_system": platform.system(), "machine": platform.machine()},
        "code_sha256": {name: sha256_file(HERE / name) for name in ("pilot.py", "pilot_data.py", "profile_solver.py")},
    }
    details = {"config": config, "source_path": str(Path(csv_path).expanduser().resolve()),
               "selected": None, "verification": None}

    def finish(status, reason_code, message):
        summary.update(status=status, reason_code=reason_code, completed_at_utc=_utc_now(),
                       elapsed_seconds=round(time.monotonic() - started, 6))
        details.update(message=message, summary=summary)
        _write_json(folder / "run_details.json", details)
        _write_json(folder / "PILOT_SUMMARY.json", summary)
        (folder / "RUN_REPORT.txt").write_text(_human_report(details, summary), encoding="utf-8")
        progress("Status: {}. Summary: {}".format(status, folder / "PILOT_SUMMARY.json"))
        return summary

    try:
        limits = validate_config(config)
        _write_json(folder / "config.json", config)
        summary["config_sha256"] = sha256_file(folder / "config.json")
        summary["run_kind"] = "synthetic_demo" if config["case_name"] == "synthetic_demo" else "data_pilot"
        summary["goal"] = {"min_w2": config["min_w2"], "accept": config["accept"], "max_cost": config.get("max_cost")}
        if summary["code_sha256"]["profile_solver.py"] != SOLVER_SHA256:
            return finish("input_error", "solver_identity_mismatch", "The expected unchanged solver file has a different hash.")
        cache = build_cache(Path(csv_path).expanduser(), Path(cache_dir).expanduser(),
                            expected_sha256=config.get("expected_source_sha256"), progress=progress)
        details["cache"] = cache
        summary["source"] = {"sha256": cache["source_sha256"], "row_count": cache["row_count"],
                             "cache_reused": cache["cache_reused"]}
        progress("Extracting the complete induced incoming-three-hop context ...")
        context = extract_context(cache, config["root"]["bank"], config["root"]["account"],
                                  config["cutoff"], window_minutes=config["window_minutes"],
                                  max_context_events=limits["max_context_events"],
                                  max_vertices=limits["max_vertices"],
                                  max_discovery_events=limits["max_discovery_events"], progress=progress)
        details["context"] = context
        summary["history"] = {key: context[key] for key in (
            "window_minutes", "global_window_event_count", "context_event_count", "vertex_count")}
        instance = {"root": context["root"], "min_w2": config["min_w2"], "events": context["events"]}
        _write_json(folder / "instance.json", instance)
        if not instance["events"]:
            return finish("out_of_scope", "empty_context", "The specified window/root has no induced transaction context.")
        try:
            depths = validate_tree(instance["events"], instance["root"])
        except ValueError as exc:
            return finish("out_of_scope", "unsupported_original_graph", str(exc))
        summary["structure"] = {"eligible": True, "maximum_depth": max(depths.values())}
        if len(instance["events"]) > limits["max_solver_events"]:
            return finish("resource_limit", "solver_event_limit", "Complete context retained, but it exceeds the configured solver-event limit.")
        before = count_walks(instance["events"], instance["root"])
        baseline_events = [e for e in instance["events"] if e.get("status", "optional") != "delete"]
        baseline = count_walks(baseline_events, instance["root"])
        summary["before"] = {"w2": before[0], "w3": before[1]}
        summary["baseline"] = {"w2": baseline[0], "w3": baseline[1]}
        checks = _reference_checks(config, cache, context, before)
        summary["reference_checks"].update(checks)
        if not all(checks.values()):
            return finish("reference_mismatch", "extraction_or_baseline_mismatch", "The reconstructed case differs from its declared reference expectations; no optimum is claimed.")
        if config["min_w2"] > baseline[0]:
            return finish("quota_infeasible", "quota_above_baseline", "The required two-walk count exceeds the post-mandatory baseline.")
        cap = baseline[0] - config["min_w2"]
        summary["R"] = cap
        if cap > limits["max_R"]:
            return finish("resource_limit", "preservation_loss_limit", "The preservation-loss allowance exceeds the configured run limit.")
        coordinates = (cap + 1) * (baseline[1] + 1)
        summary["possible_profile_coordinates"] = coordinates
        if coordinates > limits["max_profile_coordinates"]:
            return finish("resource_limit", "profile_coordinate_limit", "The full profile coordinate bound exceeds the configured run limit.")
        worker_path = folder / "worker_result.json"
        command = [sys.executable, "-B", str(HERE / "pilot.py"), "_worker",
                   "--instance", str(folder / "instance.json"), "--output", str(worker_path)]
        progress("Running the unchanged exact solver (time limit: {} seconds) ...".format(limits["timeout_seconds"]))
        solver_started = time.monotonic()
        try:
            worker = subprocess.run(command, capture_output=True, text=True, timeout=limits["timeout_seconds"],
                                    cwd=str(HERE), check=False)
        except subprocess.TimeoutExpired:
            summary["solver_elapsed_seconds"] = round(time.monotonic() - solver_started, 6)
            return finish("resource_limit", "solver_timeout", "The worker time limit was reached. This is not a no-solution result.")
        summary["solver_elapsed_seconds"] = round(time.monotonic() - solver_started, 6)
        if worker.returncode != 0 or not worker_path.is_file():
            details["worker_error"] = (worker.stderr or "")[-8000:]
            return finish("execution_error", "solver_worker_failed", "The solver worker did not complete successfully; see local run_details.json.")
        result = json.loads(worker_path.read_text(encoding="utf-8"))
        worker_path.replace(folder / "profiles.json")
        if result.get("original") != summary["before"] or result.get("baseline") != summary["baseline"]:
            return finish("verification_failed", "solver_count_disagreement", "Solver counts differ from the independent endpoint-chain counter.")
        if result.get("status") != "ok":
            return finish("verification_failed", "unexpected_solver_status", "Solver returned an unexpected status after the independent quota check.")
        summary["profile_count"] = len(result["profiles"])
        summary["solver_stats"] = result["stats"]
        selected = select_profile(result, _acceptance(config), max_cost=config.get("max_cost"))
        details["selected"] = selected
        expected_cost = config.get("reference_expectation", {}).get("minimum_cost")
        if expected_cost is not None:
            summary["reference_checks"]["minimum_cost"] = selected is not None and selected["total_cost"] == expected_cost
            if not summary["reference_checks"]["minimum_cost"]:
                return finish("reference_mismatch", "minimum_cost_reference_mismatch", "The selected minimum differs from the prior reference expectation.")
        if selected is None:
            return finish("no_acceptable_profile", "completed_search_no_accepted_profile", "The complete computed profile has no accepted entry within the configured cap and scope.")
        verification = verify_selection(instance, selected)
        details["verification"] = verification
        if not _acceptance(config)(selected["w2"], selected["w3"]):
            verification["verified"] = False
            verification["issues"].append("Acceptance rule violated")
        if config.get("max_cost") is not None and selected["total_cost"] > config["max_cost"]:
            verification["verified"] = False
            verification["issues"].append("Total cost cap violated")
        summary["witness_verified"] = verification["verified"]
        if not verification["verified"]:
            return finish("verification_failed", "selected_witness_failed", "The selected witness failed independent replay checks.")
        if sha256_file(HERE / "profile_solver.py") != SOLVER_SHA256:
            return finish("verification_failed", "solver_changed_during_run", "The solver identity changed during execution.")
        _write_selected_csv(folder / "selected_events.csv", instance, selected)
        summary["selected"] = {"w2": selected["w2"], "w3": selected["w3"],
                               "total_cost": selected["total_cost"], "deleted_event_count": len(selected["deleted_ids"])}
        summary["exact_optimality_claim"] = True
        return finish("solution_found", "complete_verified_count_solution", "A minimum-cost accepted count profile was selected and its original-event witness was independently verified.")
    except DataError as exc:
        status = "resource_limit" if exc.code == "resource_limit" else "input_error"
        return finish(status, "data_" + exc.code, str(exc))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return finish("input_error", "invalid_input_or_local_io", str(exc))
    except KeyboardInterrupt:
        return finish("interrupted", "user_interrupted", "Execution was interrupted; no incomplete result is certified.")
    except Exception as exc:
        details["exception_type"] = type(exc).__name__
        return finish("execution_error", "unexpected_execution_error", str(exc))


def _load_config(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _console(message):
    print(message, flush=True)


def _print_completion(summary, output_dir):
    folder = Path(output_dir).expanduser().resolve() / summary["run_id"]
    print("\nCompleted status: " + summary["status"])
    if summary.get("selected"):
        chosen = summary["selected"]
        print("Remove {} event(s), total cost {}; remaining W2={}, W3={}.".format(
            chosen["deleted_event_count"], chosen["total_cost"], chosen["w2"], chosen["w3"]))
    print("Detailed local report: " + str(folder / "RUN_REPORT.txt"))
    if summary.get("run_kind") == "synthetic_demo":
        print("Synthetic demo summary (this stage has not run the IBM data): " + str(folder / "PILOT_SUMMARY.json"))
    else:
        print("Upload this data-pilot summary to the chat: " + str(folder / "PILOT_SUMMARY.json"))


def _path_from_drag(text):
    text = text.strip()
    if not text:
        return None
    direct = Path(text).expanduser()
    if direct.is_file():
        return direct
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ValueError("Could not read the dragged file path: " + str(exc))
    if len(parts) != 1:
        raise ValueError("Drag one CSV file, or paste one complete file path.")
    return Path(parts[0]).expanduser()


def _interactive():
    print("LOCAL MAC TEMPORAL-PROFILE PILOT")
    print("Python {} on {}".format(platform.python_version(), platform.system()))
    print("First: a small synthetic check of the complete CSV-to-result pipeline.\n")
    demo = run_case(HERE / "examples/demo_transactions.csv", _load_config(HERE / "examples/demo_config.json"),
                    HERE / "runs", HERE / "cache", progress=_console)
    _print_completion(demo, HERE / "runs")
    if demo["status"] != "solution_found":
        print("The synthetic demo did not pass. Bring its PILOT_SUMMARY.json back to the chat.")
        return 1
    print("\nNext: the IBM q0011 preset from the earlier application audit.")
    print("Drag the ORIGINAL HI-Small_Trans.csv file into this Terminal window.")
    print("The file hash is checked; records are read only. Press Enter without a path to stop here.")
    try:
        source = _path_from_drag(input("CSV file: "))
    except (EOFError, KeyboardInterrupt):
        print("\nOnly the synthetic demo ran. The IBM data pilot has not run.")
        return 0
    except ValueError as exc:
        print(str(exc))
        return 2
    if source is None:
        print("Only the synthetic demo ran. The IBM data pilot has not run.")
        return 0
    if not source.is_file():
        print("That is not an existing file. Run again and drag the CSV file itself.")
        return 2
    result = run_case(source, _load_config(HERE / "pilot_config.json"), HERE / "runs", HERE / "cache", progress=_console)
    _print_completion(result, HERE / "runs")
    return 0 if result["status"] in ("solution_found", "no_acceptable_profile", "quota_infeasible", "out_of_scope") else 1


def main(argv=None):
    if sys.version_info < (3, 8):
        print("Python 3.8 or newer is required.", file=sys.stderr)
        return 2
    # All integer costs/counts retain their encodings; do not introduce a
    # decimal-conversion cap on interpreters that provide this optional setting.
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("interactive", help="run the synthetic demo, then ask for the raw IBM CSV")
    demo = sub.add_parser("demo", help="synthetic end-to-end CSV demonstration")
    demo.add_argument("--output-dir", type=Path, default=HERE / "runs")
    demo.add_argument("--cache-dir", type=Path, default=HERE / "cache")
    run = sub.add_parser("run", help="run a configured case on a local raw IBM CSV")
    run.add_argument("--csv", type=Path, required=True)
    run.add_argument("--config", type=Path, default=HERE / "pilot_config.json")
    run.add_argument("--output-dir", type=Path, default=HERE / "runs")
    run.add_argument("--cache-dir", type=Path, default=HERE / "cache")
    worker = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("--instance", type=Path, required=True)
    worker.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "_worker":
        result = solve_profiles(_load_config(args.instance))
        _write_json(args.output, result)
        return 0
    if args.command == "interactive":
        return _interactive()
    try:
        config = _load_config(HERE / "examples/demo_config.json" if args.command == "demo" else args.config)
    except (OSError, ValueError) as exc:
        parser.error("Unable to read config: " + str(exc))
    source = HERE / "examples/demo_transactions.csv" if args.command == "demo" else args.csv
    result = run_case(source, config, args.output_dir, args.cache_dir, progress=_console)
    _print_completion(result, args.output_dir)
    return 0 if result["status"] in ("solution_found", "no_acceptable_profile", "quota_infeasible", "out_of_scope") else 1


if __name__ == "__main__":
    sys.exit(main())
