#!/usr/bin/env python3
"""Independent walk-count, witness, and small-instance profile checks.

Python 3.8+ standard library only. This module does not import the profile
solver, data adapter, or pilot runner. The runner separately checks the
complete original graph's structural eligibility.

``verify_table`` replays every supplied witness and checks solver metadata;
it does not certify all missing outcomes. ``exhaustive_table`` enumerates
every permitted optional-deletion subset within its explicit size bound.
``compare_table`` accepts full agreement only after that enumeration finishes.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from itertools import groupby
import json
import math
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict, List, NamedTuple, Tuple


class _Event(NamedTuple):
    identifier: str
    source: str
    target: str
    minute: int
    cost: int
    status: str


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nonnegative_integer(value: Any) -> bool:
    return _integer(value) and value >= 0


def _name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(field + " must be a nonempty string")
    return value


def _parse_events(events: Any) -> List[_Event]:
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    parsed = []  # type: List[_Event]
    identifiers = set()
    for index, event in enumerate(events):
        label = "events[{}]".format(index)
        if not isinstance(event, dict):
            raise ValueError(label + " must be an object")
        identifier = _name(event.get("id"), label + ".id")
        if identifier in identifiers:
            raise ValueError("Original event IDs must be unique")
        identifiers.add(identifier)
        source = _name(event.get("source"), label + ".source")
        target = _name(event.get("target"), label + ".target")
        minute = event.get("time")
        if not _integer(minute):
            raise ValueError(label + ".time must be an integer, not a Boolean")
        cost = event.get("cost", 1)
        if not _nonnegative_integer(cost):
            raise ValueError(label + ".cost must be a nonnegative integer")
        status = event.get("status", "optional")
        if not isinstance(status, str) or status not in ("optional", "keep", "delete"):
            raise ValueError(label + ".status must be optional, keep, or delete")
        parsed.append(_Event(identifier, source, target, minute, cost, status))
    return parsed


def _parse_instance(instance: Any) -> Tuple[str, int, List[_Event]]:
    if not isinstance(instance, dict):
        raise ValueError("instance must be an object")
    root = _name(instance.get("root"), "root")
    quota = instance.get("min_w2", 0)
    if not _integer(quota):
        raise ValueError("min_w2 must be an integer, not a Boolean")
    return root, max(0, quota), _parse_events(instance.get("events"))


def _prefix_counts(events: List[_Event], root: str) -> Dict[str, int]:
    """Count using only prefixes from strictly earlier timestamp groups."""
    one = defaultdict(int)
    two = defaultdict(int)
    root_three = 0
    for _minute, group in groupby(sorted(events, key=lambda event: event.minute),
                                 key=lambda event: event.minute):
        add_one = defaultdict(int)
        add_two = defaultdict(int)
        for event in group:
            add_one[event.target] += 1
            add_two[event.target] += one[event.source]
            if event.target == root:
                root_three += two[event.source]
        # Delay both updates until the whole minute is processed. Equal-time
        # events never extend one another, regardless of their input order.
        for node, count in add_one.items():
            one[node] += count
        for node, count in add_two.items():
            two[node] += count
    return {"w2": two[root], "w3": root_three}


def count_walks(events: Any, root: Any) -> Dict[str, int]:
    """Count strict root-ending pairs/triples in the supplied event list.

    Events are distinct by original ID. This function counts every supplied
    event, irrespective of its keep/delete status; callers choose the original
    or post-mandatory list. Runtime is O(m log m), with O(m) auxiliary storage.
    """
    return _prefix_counts(_parse_events(events), _name(root, "root"))


def _walk_masks(events: List[_Event], root: str) -> Tuple[List[int], List[int]]:
    """Enumerate literal endpoint-chained event tuples, independent of prefixes."""
    incoming = defaultdict(list)
    for index, event in enumerate(events):
        incoming[event.target].append((index, event))
    pairs = []  # type: List[int]
    triples = []  # type: List[int]
    for last_index, last in incoming.get(root, []):
        for middle_index, middle in incoming.get(last.source, []):
            if middle.minute >= last.minute:
                continue
            pair = (1 << middle_index) | (1 << last_index)
            pairs.append(pair)
            for first_index, first in incoming.get(middle.source, []):
                if first.minute < middle.minute:
                    triples.append(pair | (1 << first_index))
    return pairs, triples


def _counts_after(pairs: List[int], triples: List[int], deleted_mask: int) -> Dict[str, int]:
    return {
        "w2": sum(1 for mask in pairs if not (mask & deleted_mask)),
        "w3": sum(1 for mask in triples if not (mask & deleted_mask)),
    }


def _count_metadata(value: Any, expected: Dict[str, int], label: str,
                    issues: List[str]) -> None:
    if not isinstance(value, dict):
        issues.append(label + " must contain integer w2 and w3 counts")
        return
    for key in ("w2", "w3"):
        if not _nonnegative_integer(value.get(key)) or value[key] != expected[key]:
            issues.append(label + "." + key + " differs from the independent count")


def _integer_metadata(value: Any, expected: int, label: str, issues: List[str]) -> None:
    if not _nonnegative_integer(value) or value != expected:
        issues.append(label + " differs from the independently required integer")


def _check_profile_fields(profile: Any, index: int, issues: List[str]) -> bool:
    label = "Profile {}".format(index)
    if not isinstance(profile, dict):
        issues.append(label + " must be an object")
        return False
    valid = True
    for key in ("w2", "w3", "loss", "optional_cost", "total_cost"):
        if not _nonnegative_integer(profile.get(key)):
            issues.append(label + "." + key + " must be a nonnegative integer")
            valid = False
    ids = profile.get("deleted_ids")
    if not isinstance(ids, list) or any(not isinstance(item, str) or not item for item in ids):
        issues.append(label + ".deleted_ids must be a list of nonempty original IDs")
        valid = False
    elif len(set(ids)) != len(ids):
        issues.append(label + " repeats a deleted original ID")
        valid = False
    return valid


def verify_table(instance: Any, result: Any) -> Dict[str, Any]:
    """Replay every profile witness and check all count/cost/quota metadata.

    A passed result here is a witness/metadata check. It is not a substitute
    for the full attainable-pair/minimum-cost comparison to exhaustive_table.
    Invalid input is returned as a mismatch, never as a passed empty check.
    """
    issues = []  # type: List[str]
    report = {
        "status": "mismatch", "issues": issues, "witnesses_checked": 0,
        "scope": "all_supplied_witnesses_and_solver_metadata",
        "complete_profile_optimality_checked": False,
    }  # type: Dict[str, Any]
    try:
        root, quota, events = _parse_instance(instance)
    except (ValueError, TypeError) as exc:
        issues.append("Invalid instance: " + str(exc))
        return report
    if not isinstance(result, dict):
        issues.append("Solver result must be an object")
        return report

    pairs, triples = _walk_masks(events, root)
    by_id = {event.identifier: index for index, event in enumerate(events)}
    forced_mask = sum(1 << index for index, event in enumerate(events) if event.status == "delete")
    forced_ids = {event.identifier for event in events if event.status == "delete"}
    protected_ids = {event.identifier for event in events if event.status == "keep"}
    forced_cost = sum(event.cost for event in events if event.status == "delete")
    original = {"w2": len(pairs), "w3": len(triples)}
    baseline = _counts_after(pairs, triples, forced_mask)
    infeasible = quota > baseline["w2"]
    expected_r = None if infeasible else baseline["w2"] - quota
    report.update(independent_original=original, independent_baseline=baseline,
                  min_w2=quota, forced_cost=forced_cost, expected_R=expected_r)

    expected_status = "infeasible" if infeasible else "ok"
    if result.get("status") != expected_status:
        issues.append("Solver status disagrees with the independent preservation-quota check")
    _count_metadata(result.get("original"), original, "original", issues)
    _count_metadata(result.get("baseline"), baseline, "baseline", issues)
    _integer_metadata(result.get("min_w2"), quota, "min_w2", issues)
    _integer_metadata(result.get("forced_cost"), forced_cost, "forced_cost", issues)
    if expected_r is None:
        if result.get("R", "missing") is not None:
            issues.append("R must be null when the baseline cannot meet the quota")
    else:
        _integer_metadata(result.get("R"), expected_r, "R", issues)

    profiles = result.get("profiles")
    if not isinstance(profiles, list):
        issues.append("Solver profiles must be a list")
        return report
    report["profiles_seen"] = len(profiles)
    if infeasible and profiles:
        issues.append("An infeasible quota cannot have any feasible profiles")
    if not infeasible and not profiles:
        issues.append("A feasible quota must include at least the mandatory-deletion baseline")

    coordinates = set()
    baseline_cost = None
    for index, profile in enumerate(profiles):
        label = "Profile {}".format(index)
        if not _check_profile_fields(profile, index, issues):
            continue
        coordinate = (profile["w2"], profile["w3"])
        if coordinate in coordinates:
            issues.append(label + " duplicates an attainable coordinate")
        coordinates.add(coordinate)
        if coordinate == (baseline["w2"], baseline["w3"]):
            baseline_cost = profile["total_cost"]
        removed = set(profile["deleted_ids"])
        if removed - set(by_id):
            issues.append(label + " references unknown original event IDs")
            continue
        if not forced_ids <= removed:
            issues.append(label + " omits a mandatory deletion")
        if removed & protected_ids:
            issues.append(label + " deletes a mandatory-keep event")

        mask = sum(1 << by_id[event_id] for event_id in removed)
        observed = _counts_after(pairs, triples, mask)
        total_cost = sum(events[by_id[event_id]].cost for event_id in removed)
        optional_cost = sum(events[by_id[event_id]].cost for event_id in removed
                            if events[by_id[event_id]].status == "optional")
        expected = {
            "w2": observed["w2"], "w3": observed["w3"],
            "loss": baseline["w2"] - observed["w2"],
            "optional_cost": optional_cost, "total_cost": total_cost,
        }
        report["witnesses_checked"] += 1
        for key, value in expected.items():
            if profile[key] != value:
                issues.append(label + "." + key + " does not match its original-ID witness")
        if observed["w2"] < quota:
            issues.append(label + " violates the preservation quota")
        if observed["w2"] > baseline["w2"] or observed["w3"] > baseline["w3"]:
            issues.append(label + " exceeds its post-mandatory baseline counts")
        if profile["total_cost"] != forced_cost + profile["optional_cost"]:
            issues.append(label + " does not charge mandatory cost exactly once")

    # With nonnegative optional costs, retaining all optional events attains
    # the baseline coordinate at exactly the mandatory cost. This known
    # minimum is a consistency check, not a general completeness argument.
    if not infeasible:
        if (baseline["w2"], baseline["w3"]) not in coordinates:
            issues.append("The guaranteed baseline coordinate is absent")
        elif baseline_cost != forced_cost:
            issues.append("The baseline coordinate must have the mandatory-only minimum cost")
    report["status"] = "passed" if not issues else "mismatch"
    return report


def exhaustive_table(instance: Any, max_events: int = 16) -> Dict[str, Any]:
    """Enumerate all permitted optional-removal subsets within a fixed bound.

    Each original event is one decision. Forced deletions are always charged,
    protected events cannot be deleted, and costs can be arbitrary nonnegative
    integers. Keeping one tied minimum witness is sufficient for each pair.
    Size skipping returns complete=False and never represents an empty proof.
    """
    started = time.monotonic()
    if not _nonnegative_integer(max_events):
        raise ValueError("max_events must be a nonnegative integer, not a Boolean")
    root, quota, events = _parse_instance(instance)
    optional = [(index, event) for index, event in enumerate(events) if event.status == "optional"]
    forced_mask = sum(1 << index for index, event in enumerate(events) if event.status == "delete")
    forced_cost = sum(event.cost for event in events if event.status == "delete")
    original = _prefix_counts(events, root)
    baseline = _prefix_counts([event for event in events if event.status != "delete"], root)
    optional_count = len(optional)
    expected_subsets = 1 << optional_count
    report = {
        "format_version": 1,
        "method": "enumerate_all_optional_deletion_subsets",
        "status": "skipped_size", "complete": False,
        "original": original, "baseline": baseline, "min_w2": quota,
        "R": None if quota > baseline["w2"] else baseline["w2"] - quota,
        "forced_cost": forced_cost, "original_events": len(events),
        "optional_events": optional_count,
        "protected_events": sum(event.status == "keep" for event in events),
        "forced_deleted_events": sum(event.status == "delete" for event in events),
        "max_optional_events": max_events,
        "subsets_expected": expected_subsets, "subsets_checked": 0,
        "feasible_subsets": 0, "profiles": [],
    }  # type: Dict[str, Any]
    if optional_count > max_events:
        report.update(skip_reason="optional_event_limit",
                      elapsed_seconds=time.monotonic() - started)
        return report

    pairs, triples = _walk_masks(events, root)
    if original != {"w2": len(pairs), "w3": len(triples)} or baseline != _counts_after(pairs, triples, forced_mask):
        raise RuntimeError("Independent prefix and literal-tuple counters disagree")

    best = {}  # type: Dict[Tuple[int, int], Tuple[int, int]]
    deleted_mask = forced_mask
    optional_cost = 0
    previous_gray = 0
    feasible_count = 0
    for number in range(expected_subsets):
        # Gray order changes one optional decision at a time. Walks are still
        # recounted directly from their literal event masks for every subset.
        gray = number ^ (number >> 1)
        if number:
            changed = gray ^ previous_gray
            position = changed.bit_length() - 1
            original_index, event = optional[position]
            deleted_mask ^= 1 << original_index
            optional_cost += event.cost if gray & changed else -event.cost
        previous_gray = gray
        observed = _counts_after(pairs, triples, deleted_mask)
        if observed["w2"] >= quota:
            feasible_count += 1
            coordinate = (observed["w2"], observed["w3"])
            total_cost = forced_cost + optional_cost
            incumbent = best.get(coordinate)
            if incumbent is None or total_cost < incumbent[0]:
                best[coordinate] = (total_cost, deleted_mask)

    profiles = []
    for (w2, w3), (cost, mask) in sorted(best.items()):
        profiles.append({
            "w2": w2, "w3": w3, "minimum_cost": cost,
            "deleted_ids": sorted(event.identifier for index, event in enumerate(events)
                                  if mask & (1 << index)),
        })
    report.update(status="ok", complete=True, subsets_checked=expected_subsets,
                  feasible_subsets=feasible_count, profiles=profiles,
                  elapsed_seconds=time.monotonic() - started)
    return report


def _oracle_metadata(oracle: Dict[str, Any], issues: List[str]) -> bool:
    """Validate completion evidence before comparing an oracle table."""
    required_integers = (
        "optional_events", "subsets_expected", "subsets_checked", "feasible_subsets",
        "min_w2", "forced_cost", "original_events", "protected_events", "forced_deleted_events",
        "max_optional_events",
    )
    valid = True
    if not _integer(oracle.get("format_version")) or oracle["format_version"] != 1:
        issues.append("Oracle format_version is unsupported")
        valid = False
    if oracle.get("method") != "enumerate_all_optional_deletion_subsets":
        issues.append("Oracle method is not the complete optional-subset enumeration")
        valid = False
    for key in required_integers:
        if not _nonnegative_integer(oracle.get(key)):
            issues.append("Oracle " + key + " must be a nonnegative integer")
            valid = False
    for name in ("original", "baseline"):
        value = oracle.get(name)
        if not isinstance(value, dict) or any(not _nonnegative_integer(value.get(key)) for key in ("w2", "w3")):
            issues.append("Oracle " + name + " must contain nonnegative integer counts")
            valid = False
    if not valid:
        return False
    expected_subsets = oracle["subsets_expected"]
    # Validate the exponent without shifting by an untrusted, potentially
    # enormous integer read from an incomplete or malformed worker artifact.
    if (expected_subsets < 1 or expected_subsets & (expected_subsets - 1)
            or expected_subsets.bit_length() - 1 != oracle["optional_events"]):
        issues.append("Oracle expected subset count is not 2**optional_events")
    if oracle["optional_events"] + oracle["protected_events"] + oracle["forced_deleted_events"] != oracle["original_events"]:
        issues.append("Oracle event-role counts do not sum to the original event count")
    if any(oracle["baseline"][key] > oracle["original"][key] for key in ("w2", "w3")):
        issues.append("Oracle baseline exceeds original walk counts")
    r = oracle.get("R", "missing")
    if oracle["min_w2"] > oracle["baseline"]["w2"]:
        if r is not None:
            issues.append("Oracle R must be null for an infeasible quota")
    elif not _nonnegative_integer(r) or r != oracle["baseline"]["w2"] - oracle["min_w2"]:
        issues.append("Oracle R does not match baseline minus quota")
    if "elapsed_seconds" in oracle:
        elapsed = oracle["elapsed_seconds"]
        try:
            valid_elapsed = (isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool)
                             and math.isfinite(elapsed) and elapsed >= 0)
        except (ValueError, OverflowError):
            valid_elapsed = False
        if not valid_elapsed:
            issues.append("Oracle elapsed_seconds is invalid")
    return True


def compare_table(result: Any, oracle: Any) -> Dict[str, Any]:
    """Compare complete attained-pair sets and minimum costs, ignoring tied IDs.

    The caller first uses verify_table to replay the solver's witnesses against
    the actual instance. This function never treats an incomplete enumeration,
    missing table, duplicate coordinate, or malformed count as agreement.
    """
    issues = []  # type: List[str]
    report = {"status": "mismatch", "issues": issues, "pairs_compared": 0}  # type: Dict[str, Any]
    if not isinstance(oracle, dict):
        issues.append("Oracle result must be an object")
        return report
    if not _oracle_metadata(oracle, issues):
        return report
    if oracle.get("status") == "skipped_size":
        if (oracle.get("complete") is not False or oracle["subsets_checked"] != 0
                or oracle["feasible_subsets"] != 0 or oracle.get("profiles") != []):
            issues.append("A size-skipped oracle must not claim completed results")
        if oracle["optional_events"] <= oracle["max_optional_events"]:
            issues.append("Oracle claims a size skip within its declared size limit")
        if not issues:
            report["status"] = "not_checked"
        return report
    if oracle.get("status") != "ok" or oracle.get("complete") is not True:
        issues.append("Oracle enumeration did not complete successfully")
        return report
    if oracle["optional_events"] > oracle["max_optional_events"]:
        issues.append("Oracle claims completed enumeration beyond its declared size limit")
    if oracle["subsets_checked"] != oracle["subsets_expected"]:
        issues.append("Oracle did not check every optional-deletion subset")
    if oracle["feasible_subsets"] > oracle["subsets_checked"]:
        issues.append("Oracle feasible subset count exceeds checked subsets")
    if not isinstance(result, dict):
        issues.append("Solver result must be an object")
        return report

    baseline = oracle["baseline"]
    quota = oracle["min_w2"]
    infeasible = quota > baseline["w2"]
    expected_status = "infeasible" if infeasible else "ok"
    if result.get("status") != expected_status:
        issues.append("Solver status disagrees with the oracle quota status")
    _count_metadata(result.get("original"), oracle["original"], "original", issues)
    _count_metadata(result.get("baseline"), baseline, "baseline", issues)
    _integer_metadata(result.get("min_w2"), quota, "min_w2", issues)
    _integer_metadata(result.get("forced_cost"), oracle["forced_cost"], "forced_cost", issues)
    if infeasible:
        if result.get("R", "missing") is not None:
            issues.append("Solver R must be null for an infeasible quota")
    else:
        _integer_metadata(result.get("R"), baseline["w2"] - quota, "R", issues)

    oracle_profiles = oracle.get("profiles")
    supplied_profiles = result.get("profiles")
    if not isinstance(oracle_profiles, list) or not isinstance(supplied_profiles, list):
        issues.append("Both oracle and solver profiles must be lists")
        return report
    expected = {}  # type: Dict[Tuple[int, int], int]
    for index, profile in enumerate(oracle_profiles):
        label = "Oracle profile {}".format(index)
        if not isinstance(profile, dict) or any(not _nonnegative_integer(profile.get(key)) for key in ("w2", "w3", "minimum_cost")):
            issues.append(label + " has invalid count or minimum-cost fields")
            continue
        ids = profile.get("deleted_ids")
        if (not isinstance(ids, list) or any(not isinstance(item, str) or not item for item in ids)
                or len(set(ids)) != len(ids)):
            issues.append(label + " has invalid original-event witness IDs")
            continue
        coordinate = (profile["w2"], profile["w3"])
        if coordinate in expected:
            issues.append(label + " duplicates an attainable coordinate")
        expected[coordinate] = profile["minimum_cost"]
        if not quota <= profile["w2"] <= baseline["w2"] or profile["w3"] > baseline["w3"]:
            issues.append(label + " is outside the quota/baseline count bounds")
        if profile["minimum_cost"] < oracle["forced_cost"]:
            issues.append(label + " fails to charge the mandatory cost")
    if len(oracle_profiles) > oracle["feasible_subsets"]:
        issues.append("Oracle reports more attainable pairs than feasible subsets")
    if infeasible:
        if oracle["feasible_subsets"] != 0 or oracle_profiles:
            issues.append("Oracle must have no feasible subsets or profiles above baseline quota")
    elif oracle["feasible_subsets"] < 1 or expected.get((baseline["w2"], baseline["w3"])) != oracle["forced_cost"]:
        issues.append("Oracle omits the guaranteed mandatory-only baseline minimum")

    supplied = {}  # type: Dict[Tuple[int, int], int]
    for index, profile in enumerate(supplied_profiles):
        if not _check_profile_fields(profile, index, issues):
            continue
        coordinate = (profile["w2"], profile["w3"])
        if coordinate in supplied:
            issues.append("Solver table repeats an attainable coordinate")
        supplied[coordinate] = profile["total_cost"]
        if profile["loss"] != baseline["w2"] - profile["w2"]:
            issues.append("Solver profile loss does not equal baseline minus w2")
        if profile["total_cost"] != oracle["forced_cost"] + profile["optional_cost"]:
            issues.append("Solver profile does not charge mandatory cost exactly once")
    missing = set(expected) - set(supplied)
    extra = set(supplied) - set(expected)
    if missing:
        issues.append("Solver table omits {} attainable coordinate(s)".format(len(missing)))
    if extra:
        issues.append("Solver table contains {} unattainable coordinate(s)".format(len(extra)))
    for coordinate in set(expected) & set(supplied):
        report["pairs_compared"] += 1
        if supplied[coordinate] != expected[coordinate]:
            issues.append("Minimum cost differs at coordinate {}".format(coordinate))
    report["status"] = "passed" if not issues else "mismatch"
    report["oracle_subsets_checked"] = oracle["subsets_checked"]
    return report


def _write_json_atomic(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent),
                                         prefix=".oracle-", suffix=".pending", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=True)
            stream.write("\n")
        temporary.replace(path)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-events", type=int, default=16)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 8):
        parser.error("Python 3.8 or newer is required")
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    try:
        if args.instance.resolve() == args.output.resolve():
            raise ValueError("The oracle output cannot overwrite its input instance")
        instance = json.loads(args.instance.read_text(encoding="utf-8"))
        result = exhaustive_table(instance, max_events=args.max_events)
        _write_json_atomic(args.output, result)
    except (ValueError, OSError, RuntimeError) as exc:
        print("Oracle did not complete: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
