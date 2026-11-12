#!/usr/bin/env python3
"""Exact minimum-cost attainable walk profiles on temporal in-arborescences.

Events are explicitly represented original-ID decisions.  The original static
in-arborescence has depth at most three, directed toward ``root``.  Walks end at
that root and have strictly increasing timestamps.  Mandatory deletions are
removed only after validating the whole original graph and fixing event roles.

``solve_profiles`` returns the minimum nonnegative deletion cost at every exact
pair (additional two-walk loss, surviving three-walk count) satisfying the
preservation quota.  Monetary costs are values, never state-space coordinates.
Only identical states are coalesced: there is no dominance pruning across loss
or surviving three-walk count.  This is a restricted combinatorial solver, not a
model or application-pipeline implementation.

Python 3.8 or newer; standard library only.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Callable, Dict, Iterator, List, Tuple


@dataclass(frozen=True)
class _Event:
    id: str
    source: str
    target: str
    time: int
    cost: int
    status: str
    bit: int


@dataclass
class _Child:
    a: list[_Event]
    b: list[_Event]


@dataclass
class _Branch:
    c: list[_Event]
    children: dict[str, _Child]


# All entry values are (optional monetary cost, original-ID deletion mask).
_Entry = Tuple[int, int]
_Profile = Dict[Tuple[int, int], _Entry]
_States = Dict[Tuple[int, int, int], _Entry]
# One positive-degree C group: (degree, prefix costs, prefix witness masks).
_CGroup = Tuple[int, List[int], List[int]]


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _validate(instance: dict) -> tuple[str, int, list[_Event], dict[str, int], dict[str, str]]:
    """Validate schema and original graph, returning original vertex depths."""
    if not isinstance(instance, dict):
        raise ValueError("instance must be a dict")
    if "root" not in instance:
        raise ValueError("missing root")
    root = _require_name(instance["root"], "root")
    quota = instance.get("min_w2", 0)
    if not _is_integer(quota):
        raise ValueError("min_w2 must be an integer, not a bool")
    if "events" not in instance or not isinstance(instance["events"], list):
        raise ValueError("events must be a list")

    events: list[_Event] = []
    identifiers: set[str] = set()
    successor: dict[str, str] = {}
    vertices = {root}
    for index, raw in enumerate(instance["events"]):
        prefix = f"events[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{prefix} must be a dict")
        for key in ("id", "source", "target", "time"):
            if key not in raw:
                raise ValueError(f"{prefix} is missing {key}")
        event_id = _require_name(raw["id"], f"{prefix}.id")
        source = _require_name(raw["source"], f"{prefix}.source")
        target = _require_name(raw["target"], f"{prefix}.target")
        if event_id in identifiers:
            raise ValueError(f"duplicate event id: {event_id!r}")
        identifiers.add(event_id)
        time = raw["time"]
        if not _is_integer(time):
            raise ValueError(f"{prefix}.time must be an integer, not a bool")
        cost = raw.get("cost", 1)
        if not _is_integer(cost) or cost < 0:
            raise ValueError(f"{prefix}.cost must be a nonnegative integer, not a bool")
        status = raw.get("status", "optional")
        # Tuple membership also handles otherwise unhashable invalid values.
        if not isinstance(status, str) or status not in ("optional", "keep", "delete"):
            raise ValueError(f"{prefix}.status must be optional, keep, or delete")
        if source == target:
            raise ValueError("self-loops are not allowed")
        if source == root:
            raise ValueError("root must have no outgoing arc")
        if source in successor and successor[source] != target:
            raise ValueError(f"vertex {source!r} has multiple distinct successors")
        successor[source] = target
        vertices.add(source)
        vertices.add(target)
        events.append(_Event(event_id, source, target, time, cost, status, 1 << index))

    # Iterative path tracing avoids a recursion-limit dependency even for an
    # invalid input containing a very long chain or cycle.
    depth = {root: 0}
    for vertex in sorted(vertices):
        if vertex in depth:
            continue
        path: list[str] = []
        on_path: set[str] = set()
        current = vertex
        while current not in depth:
            if current in on_path:
                raise ValueError("original graph contains a directed cycle")
            if current not in successor:
                raise ValueError(f"vertex {current!r} has no directed path to root")
            on_path.add(current)
            path.append(current)
            current = successor[current]
        distance = depth[current]
        for node in reversed(path):
            distance += 1
            if distance > 3:
                raise ValueError("original graph has depth greater than three")
            depth[node] = distance
    return root, max(0, quota), events, depth, successor


def _walk_counts(events: list[_Event], depth: dict[str, int]) -> tuple[int, int]:
    """Count root-ending strict event pairs/triples using their middle events."""
    a_times: dict[str, list[int]] = defaultdict(list)
    c_times: dict[str, list[int]] = defaultdict(list)
    b_events: list[_Event] = []
    for event in events:
        role = depth[event.source]
        if role == 1:
            c_times[event.source].append(event.time)
        elif role == 2:
            b_events.append(event)
        else:
            a_times[event.target].append(event.time)
    for times in a_times.values():
        times.sort()
    for times in c_times.values():
        times.sort()
    w2 = 0
    w3 = 0
    for event in b_events:
        later = c_times.get(event.target, [])
        suffix = len(later) - bisect_right(later, event.time)
        earlier = a_times.get(event.source, [])
        prefix = bisect_left(earlier, event.time)
        w2 += suffix
        w3 += prefix * suffix
    return w2, w3


def _make_branches(
    survivors: list[_Event], depth: dict[str, int], successor: dict[str, str]
) -> dict[str, _Branch]:
    # Original vertices stay represented even if forced deletions disconnect
    # every surviving event in a child or branch.
    branches = {
        vertex: _Branch([], {})
        for vertex in sorted(depth)
        if depth[vertex] == 1
    }
    for vertex in sorted(depth):
        if depth[vertex] == 2:
            branches[successor[vertex]].children[vertex] = _Child([], [])
    for event in survivors:
        role = depth[event.source]
        if role == 1:
            branches[event.source].c.append(event)
        elif role == 2:
            branches[event.target].children[event.source].b.append(event)
        else:
            branches[successor[event.target]].children[event.target].a.append(event)
    return branches


def _c_groups(branch: _Branch, cap: int, stats: dict[str, int]) -> list[_CGroup]:
    b_times = sorted(event.time for child in branch.children.values() for event in child.b)
    groups: dict[int, list[_Event]] = defaultdict(list)
    for event in branch.c:
        if event.status != "optional":
            continue
        degree = bisect_left(b_times, event.time)
        if degree == 0:
            # Such a C event belongs to no baseline pair or triple.  Keeping it
            # achieves every attainable profile at no greater cost.
            stats["optional_c_degree_zero"] += 1
        elif degree > cap:
            # Its deletion alone exceeds the available two-walk loss.
            stats["optional_c_over_loss_cap"] += 1
        else:
            groups[degree].append(event)

    result: list[_CGroup] = []
    for degree in sorted(groups):
        ordered = sorted(groups[degree], key=lambda event: (event.cost, event.bit))
        prefix_cost = [0]
        prefix_mask = [0]
        # Counts beyond this cap can never occur in an admissible configuration.
        for event in ordered[: min(len(ordered), cap // degree)]:
            prefix_cost.append(prefix_cost[-1] + event.cost)
            prefix_mask.append(prefix_mask[-1] | event.bit)
        result.append((degree, prefix_cost, prefix_mask))
    return result


def _c_configurations(groups: list[_CGroup], cap: int) -> Iterator[tuple[int, int, int]]:
    """Yield (C pair loss, cheapest C deletion cost, original-ID mask).

    Equal positive baseline degree means equal B neighborhoods within a branch.
    For each multiplicity, the cheapest optional identities therefore suffice.
    The iterative depth-first generator retains only one frame per group.
    """
    if not groups:
        yield 0, 0, 0
        return
    # Frame: next group, incoming loss/cost/mask, next multiplicity to try.
    stack = [(0, 0, 0, 0, 0)]
    while stack:
        index, loss, cost, mask, count = stack.pop()
        degree, prefix_cost, prefix_mask = groups[index]
        maximum = min(len(prefix_cost) - 1, (cap - loss) // degree)
        if count > maximum:
            continue
        stack.append((index, loss, cost, mask, count + 1))
        new_loss = loss + degree * count
        new_cost = cost + prefix_cost[count]
        new_mask = mask | prefix_mask[count]
        if index + 1 == len(groups):
            yield new_loss, new_cost, new_mask
        else:
            stack.append((index + 1, new_loss, new_cost, new_mask, 0))


def _keep_best(table: dict, key: tuple, cost: int, mask: int) -> bool:
    old = table.get(key)
    if old is None or cost < old[0]:
        table[key] = (cost, mask)
        return True
    return False


def _child_profile(
    child: _Child, c_times: list[int], cap: int, stats: dict[str, int]
) -> _Profile:
    # At a timestamp, all B events precede all A events, so q counts only A
    # events with STRICTLY earlier time.  Input order cannot change that rule.
    chronological = [(event.time, 1, event.bit, event) for event in child.a]
    chronological.extend((event.time, 0, event.bit, event) for event in child.b)
    chronological.sort(key=lambda item: item[:3])
    suffixes = {
        event.bit: len(c_times) - bisect_right(c_times, event.time)
        for event in child.b
    }
    states: _States = {(0, 0, 0): (0, 0)}
    stats["max_child_dp_states"] = max(stats["max_child_dp_states"], len(states))
    for _, role, _, event in chronological:
        fresh: _States = {}
        optional = event.status == "optional"
        for (q, loss, w3), (cost, mask) in states.items():
            stats["dp_states_processed"] += 1
            stats["dp_transition_attempts"] += 1
            if role == 1:
                if _keep_best(fresh, (q + 1, loss, w3), cost, mask):
                    stats["dp_relaxations"] += 1
                if optional:
                    stats["dp_transition_attempts"] += 1
                    if _keep_best(fresh, (q, loss, w3), cost + event.cost, mask | event.bit):
                        stats["dp_relaxations"] += 1
            else:
                suffix = suffixes[event.bit]
                if _keep_best(fresh, (q, loss, w3 + q * suffix), cost, mask):
                    stats["dp_relaxations"] += 1
                if optional:
                    stats["dp_transition_attempts"] += 1
                    if loss + suffix <= cap:
                        if _keep_best(
                            fresh, (q, loss + suffix, w3), cost + event.cost, mask | event.bit
                        ):
                            stats["dp_relaxations"] += 1
        states = fresh
        stats["child_dp_layers"] += 1
        stats["max_child_dp_states"] = max(stats["max_child_dp_states"], len(states))

    result: _Profile = {}
    for (_, loss, w3), (cost, mask) in states.items():
        stats["child_terminal_states"] += 1
        if _keep_best(result, (loss, w3), cost, mask):
            stats["profile_relaxations"] += 1
    stats["max_profile_states"] = max(stats["max_profile_states"], len(result))
    return result


def _convolve(left: _Profile, right: _Profile, cap: int, stats: dict[str, int]) -> _Profile:
    result: _Profile = {}
    for (left_loss, left_w3), (left_cost, left_mask) in left.items():
        for (right_loss, right_w3), (right_cost, right_mask) in right.items():
            stats["convolution_pairs"] += 1
            loss = left_loss + right_loss
            if loss > cap:
                continue
            if _keep_best(
                result,
                (loss, left_w3 + right_w3),
                left_cost + right_cost,
                left_mask | right_mask,
            ):
                stats["convolution_relaxations"] += 1
    stats["max_profile_states"] = max(stats["max_profile_states"], len(result))
    return result


def _branch_profile(branch: _Branch, cap: int, stats: dict[str, int]) -> _Profile:
    groups = _c_groups(branch, cap, stats)
    aggregate: _Profile = {}
    for c_loss, c_cost, c_mask in _c_configurations(groups, cap):
        stats["c_configurations"] += 1
        c_times = sorted(event.time for event in branch.c if not event.bit & c_mask)
        remaining = cap - c_loss
        joined: _Profile = {(0, 0): (0, 0)}
        for child in branch.children.values():
            profile = _child_profile(child, c_times, remaining, stats)
            joined = _convolve(joined, profile, remaining, stats)
        for (loss, w3), (cost, mask) in joined.items():
            if _keep_best(aggregate, (c_loss + loss, w3), c_cost + cost, c_mask | mask):
                stats["profile_relaxations"] += 1
        stats["max_profile_states"] = max(stats["max_profile_states"], len(aggregate))
    return aggregate


def solve_profiles(instance: dict) -> dict:
    """Compute every feasible exact pair's minimum total deletion cost.

    Required input fields are ``root`` and ``events``.  Every event requires
    ``id``, ``source``, ``target``, and integer ``time``; its nonnegative integer
    ``cost`` defaults to 1 and ``status`` defaults to ``optional``.  ``keep`` and
    ``delete`` mean mandatory retention and mandatory deletion respectively.
    The signed integer ``min_w2`` defaults to 0 and is normalized to at least 0.
    Invalid schemas or original static graphs raise ValueError.

    ``original`` counts precede mandatory deletions.  ``baseline`` counts follow
    them.  Loss is measured from the baseline, and forced cost is charged once.
    Witnesses use sorted original event IDs.  Unknown extra dictionary fields
    have no effect; they are not additional dynamic features or constraints.

    The counters in ``stats`` describe actual implementation work only.  A
    relaxation is an insertion or strict cost improvement; attempted pairs or
    transitions include those rejected by the loss cap.
    """
    _, quota, events, depth, successor = _validate(instance)
    survivors = [event for event in events if event.status != "delete"]
    forced = [event for event in events if event.status == "delete"]
    original_w2, original_w3 = _walk_counts(events, depth)
    baseline_w2, baseline_w3 = _walk_counts(survivors, depth)
    forced_cost = sum(event.cost for event in forced)
    stats = {
        "events": len(events),
        "baseline_events": len(survivors),
        "forced_deleted_events": len(forced),
        "branches": sum(value == 1 for value in depth.values()),
        "children": sum(value == 2 for value in depth.values()),
        "optional_c_degree_zero": 0,
        "optional_c_over_loss_cap": 0,
        "c_configurations": 0,
        "child_dp_layers": 0,
        "dp_states_processed": 0,
        "dp_transition_attempts": 0,
        "dp_relaxations": 0,
        "child_terminal_states": 0,
        "convolution_pairs": 0,
        "convolution_relaxations": 0,
        "profile_relaxations": 0,
        "max_child_dp_states": 0,
        "max_profile_states": 0,
    }
    result = {
        "status": "infeasible" if quota > baseline_w2 else "ok",
        "reason": "min_w2 exceeds the baseline two-walk count" if quota > baseline_w2 else None,
        "original": {"w2": original_w2, "w3": original_w3},
        "baseline": {"w2": baseline_w2, "w3": baseline_w3},
        "min_w2": quota,
        "R": None if quota > baseline_w2 else baseline_w2 - quota,
        "forced_cost": forced_cost,
        "profiles": [],
        "stats": stats,
    }
    if quota > baseline_w2:
        return result

    cap = baseline_w2 - quota
    combined: _Profile = {(0, 0): (0, 0)}
    stats["max_profile_states"] = 1
    branches = _make_branches(survivors, depth, successor)
    for branch in branches.values():
        local = _branch_profile(branch, cap, stats)
        combined = _convolve(combined, local, cap, stats)

    forced_mask = 0
    for event in forced:
        forced_mask |= event.bit
    for (loss, w3), (optional_cost, optional_mask) in sorted(combined.items()):
        mask = forced_mask | optional_mask
        result["profiles"].append(
            {
                "loss": loss,
                "w2": baseline_w2 - loss,
                "w3": w3,
                "optional_cost": optional_cost,
                "total_cost": forced_cost + optional_cost,
                "deleted_ids": sorted(event.id for event in events if event.bit & mask),
            }
        )
    return result


def select_profile(
    result: dict, accept: Callable[[int, int], bool], max_cost: int | None = None
) -> dict | None:
    """Choose a minimum-total-cost accepted complete profile, or return None.

    ``accept(w2, w3)`` must return a bool and depend only on these counts and any
    genuinely invariant auxiliary data.  ``max_cost`` limits TOTAL cost, including
    forced deletions.  When a factual class is needed, the caller must compute it
    from ``result['original']``, not from the post-deletion baseline counts.

    Cost ties retain the first accepted profile in the solver's sorted order.
    The returned dictionary is the corresponding item in ``result['profiles']``.
    """
    if not isinstance(result, dict) or result.get("status") not in ("ok", "infeasible"):
        raise ValueError("result must be a solve_profiles result")
    if not isinstance(result.get("profiles"), list):
        raise ValueError("result profiles must be a list")
    if not callable(accept):
        raise ValueError("accept must be callable")
    if max_cost is not None and (not _is_integer(max_cost) or max_cost < 0):
        raise ValueError("max_cost must be a nonnegative integer, not a bool")
    if result["status"] == "infeasible":
        return None
    best: dict | None = None
    for profile in result["profiles"]:
        if max_cost is not None and profile["total_cost"] > max_cost:
            continue
        accepted = accept(profile["w2"], profile["w3"])
        if not isinstance(accepted, bool):
            raise ValueError("accept must return a bool")
        if accepted and (best is None or profile["total_cost"] < best["total_cost"]):
            best = profile
    return best


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON input instance")
    parser.add_argument("--output", required=True, type=Path, help="JSON result file")
    args = parser.parse_args(argv)
    # Python 3.11 introduced a decimal conversion digit limit.  The CLI must
    # accept/output arbitrary-precision integers, so disable that process-local
    # limit for the load/dump and restore it before returning.  Library imports
    # and direct API calls never change the interpreter's conversion settings.
    get_limit = getattr(sys, "get_int_max_str_digits", None)
    set_limit = getattr(sys, "set_int_max_str_digits", None)
    previous_limit = get_limit() if get_limit is not None else None
    if set_limit is not None:
        set_limit(0)
    try:
        with args.input.open("r", encoding="utf-8") as stream:
            instance = json.load(stream)
        result = solve_profiles(instance)
        with args.output.open("w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    finally:
        if set_limit is not None and previous_limit is not None:
            set_limit(previous_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
