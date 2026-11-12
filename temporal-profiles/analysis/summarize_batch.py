#!/usr/bin/env python3
"""Descriptive analysis of a completed IBM v1 five-file aggregate export.

Usage: python3 summarize_batch.py BATCH_RESULTS.zip [--output results.json]
Requires only the Python standard library; does not execute archive members.
No solver, transaction data, saved profiles or original witness IDs are needed.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import itertools
import json
from pathlib import Path
from zipfile import ZipFile


def check(condition, message):
    if not condition:
        raise ValueError(message)


def hist(values):
    """JSON-safe histogram with string keys (including numeric categories)."""
    return dict(Counter(str(x) for x in values))


def read_archive(path):
    names = {"BATCH_SUMMARY.json", "CASE_RESULTS.jsonl", "GOAL_RESULTS.jsonl",
             "PROTOCOL.json", "RESULTS.txt"}
    with ZipFile(path) as z:
        check(set(z.namelist()) == names and len(z.namelist()) == len(names),
              "Expected five distinct named aggregate members")
        check(z.testzip() is None, "Archive CRC failure")
        def rows(name):
            with z.open(name) as fp:
                return [json.loads(line) for line in fp if line.strip()]
        return (json.loads(z.read("BATCH_SUMMARY.json")), json.loads(z.read("PROTOCOL.json")),
                rows("CASE_RESULTS.jsonl"), rows("GOAL_RESULTS.jsonl"))


def summarize(path):
    summary, protocol, cases, flat = read_archive(path)
    check(summary["run_kind"] == "ibm_cohort_batch" and summary["full_cohort_processed"]
          and protocol["protocol_id"] == "MAC_COMPLETE_CONTEXT_PROFILES_V1",
          "This analysis expects a full IBM complete-context v1 cohort, including limits")
    pol = protocol["policies"]
    ps, comps, budgets = pol["preservation_percentages"], pol["comparators"], pol["budgets"]
    frac = pol["target_fraction"]
    check(set(comps) == {"at_most", "exact"} and 100 in ps, "Unexpected comparator/grid")
    grid = set(itertools.product(ps, comps, budgets))
    case_by_id = {c["query_id"]: c for c in cases}
    check(len(case_by_id) == len(cases) == summary["recorded_queries"] ==
          protocol["cohort"]["query_count"], "Case count or duplicate query ID")
    check(len({c["query_index"] for c in cases}) == len(cases), "Duplicate query index")
    indexed = defaultdict(dict)
    for g in flat:
        qid = g["query_id"]
        key = (g["preservation_percentage"], g["comparator"], g["budget"])
        check(qid in case_by_id and key not in indexed[qid], "Unexpected or duplicate policy row")
        indexed[qid][key] = g
    check(len(flat) == len(cases) * len(grid) == summary["recorded_goal_conditions"],
          "Flat row count mismatch")
    tables = []  # Each item is unique by (query_id, integer preservation threshold).
    threshold_by_policy = {}
    for cid, c in case_by_id.items():
        rows = indexed[cid]
        check(set(rows) == grid, "Incomplete policy grid: " + cid)
        w2, w3 = c["counts"]["w2"], c["counts"]["w3"]
        target = w3 * frac["numerator"] // frac["denominator"]
        qs = c["quota_results"]
        check(len(qs) == len({q["min_w2"] for q in qs}) == c["planned_unique_quotas"],
              "Duplicate or missing numeric threshold: " + cid)
        byp = {}
        threshold_by_policy[cid] = byp
        for q in qs:
            tables.append((c, q))
            gs = {(g["comparator"], g["budget"]): g for g in q["goals"]}
            check(len(gs) == len(q["goals"]) and set(gs) == set(itertools.product(comps, budgets)),
                  "Unexpected table goal grid: " + cid)
            for cmp in comps:
                check(len({gs[(cmp, b)]["minimum_cost"] for b in budgets}) == 1,
                      "Budget alters the unbudgeted minimum cost: " + cid)
            for p in q["preservation_percentages"]:
                check(p in ps and p not in byp and q["min_w2"] == (w2*p+99)//100
                      and q["R"] == w2-q["min_w2"], "Invalid threshold mapping: " + cid)
                byp[p] = q
                for (cmp,b), inner in gs.items():
                    g = rows[(p,cmp,b)]
                    check(all(inner[k] == g[k] for k in inner), "Nested/flat goal differs: " + cid)
                    check(g["min_w2"] == q["min_w2"] and g["actual_R"] == q["R"] and
                          g["oracle_status"] == q["oracle"]["status"] and g["target_w3"] == target,
                          "Inconsistent table-to-policy mapping: " + cid)
                    if q["status"] == "completed":
                        cost = g["minimum_cost"]
                        expected = ("unattainable" if cost is None else "already_satisfied"
                                    if cost == 0 else "over_budget" if cost > b else "solution_found")
                        outcome = g["minimum_cost_outcome"]
                        check(cost is None if outcome is None else
                              (outcome["cost"] == cost == outcome["deleted_event_count"] and
                               outcome["w2"] >= q["min_w2"] and
                               (outcome["w3"] == target if cmp == "exact" else outcome["w3"] <= target)),
                              "Invalid aggregate outcome: " + cid)
                    else:
                        expected = "not_evaluated"
                    check(g["status"] == expected, "Status disagrees with table/cost: " + cid)
        check(not qs or set(byp) == set(ps), "Missing percentage: " + cid)
        for g in rows.values():
            check(g["baseline_w2"] == w2 and g["baseline_w3"] == w3 and
                  g["query_index"] == c["query_index"], "Case/goal identities or counts differ: "+cid)
            if not qs:
                check(g["status"] == "not_evaluated" and g["min_w2"] is None and
                      g["target_w3"] is None and g["minimum_cost"] is None,
                      "Missing table reported as evaluated: "+cid)

    done = [(c,q) for c,q in tables if q["status"] == "completed"]
    positive = [c for c in cases if c["counts"]["w3"] > 0]
    evaluated = [c for c in cases if c["status"] == "evaluated"]
    informative = [c for c in positive if c["status"] == "evaluated"]
    eligible = [c for c in cases if c["structure"]["status"] == "eligible"]
    cross = {}
    for status in sorted({c["status"] for c in cases}):
        group = [c for c in cases if c["status"] == status]
        cross[status] = {"positive_baseline_w3": sum(c["counts"]["w3"] > 0 for c in group),
                         "zero_baseline_w3": sum(c["counts"]["w3"] == 0 for c in group),
                         "total": len(group)}
    for c in evaluated:
        check(bool(c["quota_results"]) and all(q["status"] == "completed" for q in c["quota_results"]),
              "Evaluated case missing completed table: "+c["query_id"])
    for c,q in done:
        w, o = q["witness"], q["oracle"]
        check(w["status"] == "passed" and w["issues_count"] == 0 and
              w["witnesses_checked"] == q["profile_count"], "Witness replay discrepancy")
        if o["status"] == "passed":
            check(o["pairs_compared"] == q["profile_count"] and
                  o["subsets_checked"] == 2**c["context_event_count"], "Oracle tally discrepancy")
    validation = {
        "planned_query_thresholds": len(tables), "completed_query_thresholds": len(done),
        "completed_thresholds_R_histogram": hist(q["R"] for _,q in done),
        "incomplete_thresholds_reasons": hist(q["reason_code"] for _,q in tables if q["status"]!="completed"),
        "profile_entries_with_witness_replay": sum(q["witness"]["witnesses_checked"] for _,q in done),
        "completed_table_oracle_statuses": hist(q["oracle"]["status"] for _,q in done),
        "oracle_profile_entries_compared": sum(q["oracle"].get("pairs_compared") or 0 for _,q in done),
        "oracle_subset_visits_across_tables": sum(q["oracle"].get("subsets_checked") or 0 for _,q in done),
    }
    out = {"input_sha256": sha256(path.read_bytes()).hexdigest(), "run_id": summary["batch_run_id"],
           "coverage": cross, "query_count": len(cases), "positive_baseline_queries": len(positive),
           "eligible_nonempty_queries": len(eligible), "solved_positive_queries": len(informative),
           "recorded_policy_rows": len(flat), "policy_row_status": hist(g["status"] for g in flat),
           "policy_row_status_positive_baseline": hist(g["status"] for g in flat if g["baseline_w3"] > 0),
           "table_and_validation_counts": validation,
           "rounding_distinct_integer_thresholds_per_query": {}, "solved_positive_by_preservation": {}}
    check(out["policy_row_status"] == summary["goal_status_counts"] and
          out["policy_row_status_positive_baseline"] == summary["nonzero_w3_goal_status_counts"]
          and hist(c["status"] for c in cases) == summary["case_status_counts"],
          "Recomputed counts disagree with BATCH_SUMMARY.json")
    for name,group in [("eligible",eligible),("evaluated",evaluated),("evaluated_positive",informative)]:
        out["rounding_distinct_integer_thresholds_per_query"][name] = hist(len(c["quota_results"]) for c in group)
    pd = [(c,q) for c,q in done if c["counts"]["w3"]>0]
    out["solved_positive_tables"] = {"count":len(pd), "R_histogram":hist(q["R"] for _,q in pd),
                                     "oracle_status":hist(q["oracle"]["status"] for _,q in pd)}
    for p in ps:
        result = {"query_count":len(informative),
                  "actual_R":hist(threshold_by_policy[c["query_id"]][p]["R"] for c in informative)}
        ub_e_gap = []
        for cmp in comps:
            # The minimum cost is unbudgeted and is constant over the repeated budget rows.
            one = [indexed[c["query_id"]][(p,cmp,budgets[0])] for c in informative]
            result[cmp] = {
                "minimum_cost":hist("unattainable" if g["minimum_cost"] is None else g["minimum_cost"] for g in one),
                "status_by_budget":{str(b):hist(indexed[c["query_id"]][(p,cmp,b)]["status"] for c in informative)
                                    for b in budgets}}
        for c in informative:
            r = indexed[c["query_id"]]
            if r[(p,"at_most",budgets[0])]["minimum_cost"] is not None and r[(p,"exact",budgets[0])]["minimum_cost"] is None:
                ub_e_gap.append(threshold_by_policy[c["query_id"]][p])
        result["at_most_attainable_exact_unattainable"] = len(ub_e_gap)
        result["oracle_status_for_those_gaps"] = hist(q["oracle"]["status"] for q in ub_e_gap)
        out["solved_positive_by_preservation"][str(p)] = result
    anchor = protocol["reference_anchor"]["query_id"]
    changed = [c["query_id"] for c in informative if
               len({tuple(indexed[c["query_id"]][(p,cmp,budgets[0])]["minimum_cost"]
                          for cmp in comps) for p in ps})>1]
    out["positive_queries_changing_minimum_cost_or_attainability_across_policies"] = changed
    out["reference_and_changed_queries"] = {}
    for cid in sorted(set([anchor]+changed)):
        c = case_by_id[cid]
        out["reference_and_changed_queries"][cid] = {
            "context_events": c["context_event_count"], "vertices":c["vertex_count"], "baseline":c["counts"],
            "thresholds":[{"min_w2":q["min_w2"], "R":q["R"], "percentages":q["preservation_percentages"],
                           "profile_count":q["profile_count"], "oracle":q["oracle"]["status"],
                           "target_w3":q["goals"][0]["target_w3"],
                           "minimum_cost_outcomes":{g["comparator"]:g["minimum_cost_outcome"]
                                                    for g in q["goals"] if g["budget"]==budgets[0]}}
                          for q in c["quota_results"]]}
    out["interpretation"] = ("Descriptive counts from the aggregate export only. The integrity and agreement "
                             "checks here reconcile exported records; original transaction contexts, "
                             "witness replay, and exhaustive enumeration were not rerun. "
                             "Policy rows and subset visits across separate thresholds can repeat queries/subsets.")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = json.dumps(summarize(args.archive), indent=2, sort_keys=True) + "\n"
    if args.output:
        check(args.output.resolve() != args.archive.resolve(), "Output must differ from the archive")
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
