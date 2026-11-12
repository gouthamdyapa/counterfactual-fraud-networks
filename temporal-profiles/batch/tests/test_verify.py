"""Synthetic checks for the independent batch verifier and bounded oracle.

No solver, adapter, real dataset, or uploaded native-run event file is used.
"""

from copy import deepcopy
from itertools import combinations, permutations
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from batch_verify import compare_table, count_walks, exhaustive_table, verify_table


def event(identifier, source, target, minute, cost=1, status="optional"):
    return {"id": identifier, "source": source, "target": target,
            "time": minute, "cost": cost, "status": status}


def chain(quota=1):
    return {"root": "r", "min_w2": quota, "events": [
        event("early", "a", "b", 1),
        event("middle", "b", "c", 2),
        event("last", "c", "r", 3),
    ]}


def chain_result(quota=1):
    profiles = [
        {"w2": 1, "w3": 0, "loss": 0, "optional_cost": 1,
         "total_cost": 1, "deleted_ids": ["early"]},
        {"w2": 1, "w3": 1, "loss": 0, "optional_cost": 0,
         "total_cost": 0, "deleted_ids": []},
    ]
    if quota == 0:
        profiles.append({"w2": 0, "w3": 0, "loss": 1, "optional_cost": 1,
                         "total_cost": 1, "deleted_ids": ["middle"]})
    infeasible = quota > 1
    return {"status": "infeasible" if infeasible else "ok",
            "original": {"w2": 1, "w3": 1}, "baseline": {"w2": 1, "w3": 1},
            "min_w2": quota, "R": None if infeasible else 1 - quota,
            "forced_cost": 0, "profiles": [] if infeasible else profiles}


def literal_counts(events, root):
    counts = {}
    for length, key in ((2, "w2"), (3, "w3")):
        counts[key] = sum(1 for selected in permutations(events, length)
                          if selected[-1]["target"] == root
                          and all(left["target"] == right["source"] and left["time"] < right["time"]
                                  for left, right in zip(selected, selected[1:])))
    return counts


def literal_minima(instance):
    """Separate combination/permutation reference, with no event bit masks."""
    events = instance["events"]
    optional = [e for e in events if e.get("status", "optional") == "optional"]
    forced = {e["id"] for e in events if e.get("status", "optional") == "delete"}
    quota = max(0, instance.get("min_w2", 0))
    table, checked, feasible = {}, 0, 0
    for number in range(len(optional) + 1):
        for chosen in combinations(optional, number):
            checked += 1
            removed = forced | {e["id"] for e in chosen}
            observed = literal_counts([e for e in events if e["id"] not in removed], instance["root"])
            if observed["w2"] >= quota:
                feasible += 1
                point = (observed["w2"], observed["w3"])
                cost = sum(e.get("cost", 1) for e in events if e["id"] in removed)
                table[point] = min(table.get(point, cost), cost)
    return table, checked, feasible


def from_oracle(oracle):
    """Format a reference table as the public solver-result schema."""
    baseline = oracle["baseline"]
    return {
        "status": "infeasible" if oracle["min_w2"] > baseline["w2"] else "ok",
        "original": deepcopy(oracle["original"]), "baseline": deepcopy(baseline),
        "min_w2": oracle["min_w2"], "R": oracle["R"],
        "forced_cost": oracle["forced_cost"],
        "profiles": [{"w2": p["w2"], "w3": p["w3"],
                      "loss": baseline["w2"] - p["w2"],
                      "optional_cost": p["minimum_cost"] - oracle["forced_cost"],
                      "total_cost": p["minimum_cost"], "deleted_ids": list(p["deleted_ids"])}
                     for p in oracle["profiles"]],
    }


class CountTests(unittest.TestCase):
    def test_parallel_records_ties_unsorted_order_and_root_scope(self):
        events = [
            event("end2", "b", "r", 2), event("tied", "u", "a", 1),
            event("mid1", "a", "b", 1), event("first", "u", "a", 0),
            event("end1", "b", "r", 2), event("mid2", "a", "b", 1),
            event("other1", "x", "y", 0), event("other2", "y", "z", 1),
            event("other3", "z", "another_root", 2),
        ]
        unchanged = deepcopy(events)
        self.assertEqual(count_walks(events, "r"), {"w2": 4, "w3": 4})
        self.assertEqual(count_walks(events, "r"), literal_counts(events, "r"))
        self.assertEqual(events, unchanged)

    def test_equal_times_never_extend_even_when_input_order_looks_like_chain(self):
        events = [event("a", "x", "y", 5), event("b", "y", "z", 5), event("c", "z", "r", 6)]
        for ordering in permutations(events):
            self.assertEqual(count_walks(list(ordering), "r"), {"w2": 1, "w3": 0})

    def test_counter_handles_temporal_walks_without_relying_on_tree_roles(self):
        events = [event("a", "x", "x", 1), event("b", "x", "x", 2), event("c", "x", "r", 3)]
        self.assertEqual(count_walks(events, "r"), {"w2": 2, "w3": 1})
        self.assertEqual(count_walks([], "r"), {"w2": 0, "w3": 0})

    def test_invalid_identity_or_numeric_fields_are_rejected(self):
        variants = []
        for key, value in (("time", True), ("time", 1.0), ("cost", -1), ("cost", False),
                           ("source", ""), ("status", [])):
            items = chain()["events"]
            items[0][key] = value
            variants.append(items)
        items = chain()["events"]
        items[1]["id"] = items[0]["id"]
        variants.append(items)
        for items in variants:
            with self.subTest(items=items):
                with self.assertRaises(ValueError):
                    count_walks(items, "r")


class WitnessTests(unittest.TestCase):
    def test_known_chain_witnesses_and_metadata_pass(self):
        check = verify_table(chain(), chain_result())
        self.assertEqual(check["status"], "passed", check)
        self.assertEqual(check["witnesses_checked"], 2)
        self.assertFalse(check["complete_profile_optimality_checked"])

    def test_wrong_original_event_is_rejected_despite_claimed_good_counts(self):
        result = chain_result()
        result["profiles"][0]["deleted_ids"] = ["middle"]
        check = verify_table(chain(), result)
        self.assertEqual(check["status"], "mismatch")
        self.assertTrue(any("quota" in issue for issue in check["issues"]))

    def test_duplicate_unknown_and_nonstring_deletion_ids_fail(self):
        for ids in (["early", "early"], ["absent"], [True], [["early"]], "early"):
            result = chain_result()
            result["profiles"][0]["deleted_ids"] = ids
            with self.subTest(ids=ids):
                self.assertEqual(verify_table(chain(), result)["status"], "mismatch")

    def test_bad_scalar_metadata_and_noninteger_profile_fields_fail(self):
        changes = [
            ("original", {"w2": True, "w3": 1}),
            ("baseline", {"w2": 1, "w3": 0}),
            ("min_w2", 1.0), ("R", False), ("forced_cost", 1),
            ("status", "infeasible"), ("profiles", None),
        ]
        for key, value in changes:
            result = chain_result()
            result[key] = value
            with self.subTest(key=key):
                self.assertEqual(verify_table(chain(), result)["status"], "mismatch")
        for key in ("w2", "w3", "loss", "optional_cost", "total_cost"):
            result = chain_result()
            result["profiles"][0][key] = float(result["profiles"][0][key])
            with self.subTest(profile_key=key):
                self.assertEqual(verify_table(chain(), result)["status"], "mismatch")

    def test_missing_baseline_duplicate_coordinates_and_invalid_instance_fail(self):
        result = chain_result()
        result["profiles"].pop()
        self.assertEqual(verify_table(chain(), result)["status"], "mismatch")
        result = chain_result()
        result["profiles"].append(deepcopy(result["profiles"][0]))
        self.assertEqual(verify_table(chain(), result)["status"], "mismatch")
        for instance in (None, [], {"root": "r", "events": [], "min_w2": True}):
            self.assertEqual(verify_table(instance, chain_result())["status"], "mismatch")

    def test_forced_cost_charged_once_and_protected_events_enforced(self):
        instance = chain(0)
        instance["events"][0]["cost"] = 5
        instance["events"][1]["cost"] = 2
        instance["events"][2].update(cost=7, status="keep")
        instance["events"].append(event("mandatory", "x", "r", 4, 3, "delete"))
        oracle = exhaustive_table(instance)
        self.assertEqual({(p["w2"], p["w3"]): p["minimum_cost"] for p in oracle["profiles"]},
                         {(1, 1): 3, (1, 0): 8, (0, 0): 5})
        result = from_oracle(oracle)
        self.assertEqual(verify_table(instance, result)["status"], "passed")
        missing = deepcopy(result)
        missing["profiles"][0]["deleted_ids"].remove("mandatory")
        self.assertEqual(verify_table(instance, missing)["status"], "mismatch")
        protected = deepcopy(result)
        protected["profiles"][0]["deleted_ids"] = ["mandatory", "last"]
        protected["profiles"][0].update(w2=0, w3=0, loss=1, optional_cost=0, total_cost=10)
        check = verify_table(instance, protected)
        self.assertEqual(check["status"], "mismatch")
        self.assertTrue(any("mandatory-keep" in issue for issue in check["issues"]))


class ExhaustiveTests(unittest.TestCase):
    def test_complete_chain_table_and_subset_counts(self):
        oracle = exhaustive_table(chain())
        self.assertEqual(oracle["status"], "ok")
        self.assertIs(oracle["complete"], True)
        self.assertEqual(oracle["subsets_expected"], 8)
        self.assertEqual(oracle["subsets_checked"], 8)
        self.assertEqual(oracle["feasible_subsets"], 2)
        self.assertEqual({(p["w2"], p["w3"]): p["minimum_cost"] for p in oracle["profiles"]},
                         {(1, 1): 0, (1, 0): 1})
        self.assertEqual(compare_table(chain_result(), oracle)["status"], "passed")

    def test_gray_costs_and_masks_match_independent_weighted_subset_reference(self):
        randomizer = random.Random(73919)
        links = [("a", "b"), ("b", "c"), ("c", "r"), ("x", "c")]
        for case in range(8):
            events = []
            for index in range(5 + case % 4):
                source, target = links[randomizer.randrange(len(links))]
                events.append(event("e{}".format(index), source, target,
                                    randomizer.randrange(-1, 5), randomizer.randrange(0, 10),
                                    randomizer.choice(["optional", "optional", "optional", "keep", "delete"])))
            randomizer.shuffle(events)
            instance = {"root": "r", "min_w2": randomizer.randrange(0, 4), "events": events}
            unchanged = deepcopy(instance)
            expected, checked, feasible = literal_minima(instance)
            oracle = exhaustive_table(instance)
            with self.subTest(case=case):
                self.assertEqual({(p["w2"], p["w3"]): p["minimum_cost"] for p in oracle["profiles"]}, expected)
                self.assertEqual(oracle["subsets_checked"], checked)
                self.assertEqual(oracle["feasible_subsets"], feasible)
                self.assertEqual(verify_table(instance, from_oracle(oracle))["status"], "passed")
                self.assertEqual(compare_table(from_oracle(oracle), oracle)["status"], "passed")
                self.assertEqual(instance, unchanged)

    def test_optional_event_limit_excludes_forced_roles_and_never_means_infeasible(self):
        instance = chain(0)
        instance["events"][0]["status"] = "keep"
        instance["events"][1].update(status="delete", cost=3)
        complete = exhaustive_table(instance, max_events=1)
        self.assertEqual(complete["status"], "ok")
        self.assertEqual(complete["subsets_checked"], 2)
        skipped = exhaustive_table(instance, max_events=0)
        self.assertEqual(skipped["status"], "skipped_size")
        self.assertIs(skipped["complete"], False)
        self.assertEqual(skipped["subsets_checked"], 0)
        self.assertEqual(compare_table(from_oracle(complete), skipped)["status"], "not_checked")
        for bound in (True, -1, 1.0):
            with self.assertRaises(ValueError):
                exhaustive_table(instance, max_events=bound)

    def test_infeasible_quota_and_negative_quota_normalization(self):
        instance = chain(2)
        result = chain_result(2)
        oracle = exhaustive_table(instance)
        self.assertEqual(oracle["subsets_checked"], 8)
        self.assertEqual(oracle["feasible_subsets"], 0)
        self.assertEqual(oracle["profiles"], [])
        self.assertEqual(verify_table(instance, result)["status"], "passed")
        self.assertEqual(compare_table(result, oracle)["status"], "passed")
        instance = chain(-12)
        oracle = exhaustive_table(instance)
        self.assertEqual(oracle["min_w2"], 0)
        self.assertEqual(verify_table(instance, chain_result(0))["status"], "passed")
        self.assertEqual(compare_table(chain_result(0), oracle)["status"], "passed")

    def test_zero_optional_events_empty_instance_and_large_integer_costs(self):
        instance = {"root": "r", "events": [], "min_w2": 0}
        empty = exhaustive_table(instance, max_events=0)
        self.assertEqual(empty["subsets_checked"], 1)
        self.assertEqual(empty["profiles"], [{"w2": 0, "w3": 0, "minimum_cost": 0, "deleted_ids": []}])
        self.assertEqual(verify_table(instance, from_oracle(empty))["status"], "passed")
        instance = {"root": "r", "min_w2": 0, "events": [
            event("first", "a", "b", 0, 10 ** 80),
            event("last", "b", "r", 1, 10 ** 80 + 7),
        ]}
        oracle = exhaustive_table(instance)
        zero = next(p for p in oracle["profiles"] if p["w2"] == 0)
        self.assertEqual(zero["minimum_cost"], 10 ** 80)
        self.assertEqual(zero["deleted_ids"], ["first"])


class ComparisonTests(unittest.TestCase):
    def test_different_zero_cost_tied_witness_is_accepted(self):
        instance = {"root": "r", "min_w2": 0, "events": [
            event("first", "a", "b", 0, 0), event("last", "b", "r", 1, 0),
            event("irrelevant", "x", "r", -1, 0),
        ]}
        oracle = exhaustive_table(instance)
        result = from_oracle(oracle)
        for profile in result["profiles"]:
            profile["deleted_ids"] = ["last"] if profile["w2"] == 0 else ["irrelevant"]
        self.assertEqual(verify_table(instance, result)["status"], "passed")
        self.assertEqual(compare_table(result, oracle)["status"], "passed")

    def test_missing_pair_nonminimum_cost_and_duplicate_coordinate_are_rejected(self):
        oracle = exhaustive_table(chain())
        variants = []
        missing = chain_result()
        missing["profiles"].pop(0)
        self.assertEqual(verify_table(chain(), missing)["status"], "passed")
        variants.append(missing)
        costly = chain_result()
        costly["profiles"][0].update(optional_cost=2, total_cost=2)
        variants.append(costly)
        duplicate = chain_result()
        duplicate["profiles"].append(deepcopy(duplicate["profiles"][0]))
        variants.append(duplicate)
        for result in variants:
            self.assertEqual(compare_table(result, oracle)["status"], "mismatch")

    def test_incomplete_and_malformed_oracle_cannot_pass(self):
        original = exhaustive_table(chain())
        mutations = [
            ("complete", False), ("subsets_checked", 7), ("subsets_expected", 9),
            ("optional_events", True), ("optional_events", 10 ** 40),
            ("format_version", 1.0), ("method", "unknown"), ("max_optional_events", True),
            ("feasible_subsets", 0), ("profiles", []),
            ("profiles", None), ("status", "timeout"), ("R", False),
            ("baseline", {"w2": 1.0, "w3": 1}), ("elapsed_seconds", float("nan")),
        ]
        for key, value in mutations:
            oracle = deepcopy(original)
            oracle[key] = value
            with self.subTest(key=key):
                self.assertEqual(compare_table(chain_result(), oracle)["status"], "mismatch")
        for oracle in (None, [], {}, {"status": "ok", "profiles": []}):
            self.assertEqual(compare_table(chain_result(), oracle)["status"], "mismatch")
        oracle = deepcopy(original)
        oracle["profiles"].append(deepcopy(oracle["profiles"][0]))
        self.assertEqual(compare_table(chain_result(), oracle)["status"], "mismatch")

    def test_malformed_solver_table_cannot_pass_complete_comparison(self):
        oracle = exhaustive_table(chain())
        for result in (None, [], {}, {"status": "ok", "profiles": []}):
            self.assertEqual(compare_table(result, oracle)["status"], "mismatch")
        result = chain_result()
        result["profiles"][0]["total_cost"] = True
        self.assertEqual(compare_table(result, oracle)["status"], "mismatch")


class CommandTests(unittest.TestCase):
    def test_cli_with_spaces_writes_complete_atomic_output(self):
        with tempfile.TemporaryDirectory(prefix="synthetic oracle ") as directory:
            source = Path(directory) / "input instance.json"
            output = Path(directory) / "oracle output.json"
            source.write_text(json.dumps(chain()), encoding="utf-8")
            original = source.read_bytes()
            command = [sys.executable, "-B", str(PACKAGE / "batch_verify.py"),
                       "--instance", str(source), "--output", str(output), "--max-events", "3"]
            execution = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(execution.returncode, 0, execution.stderr)
            oracle = json.loads(output.read_text())
            self.assertEqual(compare_table(chain_result(), oracle)["status"], "passed")
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(list(Path(directory).glob(".oracle-*.pending")), [])

    def test_cli_rejects_overwriting_its_input_and_malformed_input(self):
        with tempfile.TemporaryDirectory(prefix="synthetic oracle ") as directory:
            source = Path(directory) / "instance.json"
            output = Path(directory) / "result.json"
            source.write_text(json.dumps(chain()), encoding="utf-8")
            original = source.read_bytes()
            command = [sys.executable, "-B", str(PACKAGE / "batch_verify.py"),
                       "--instance", str(source), "--output", str(source)]
            execution = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(execution.returncode, 2)
            self.assertEqual(source.read_bytes(), original)
            source.write_text("{broken json", encoding="utf-8")
            command[-1] = str(output)
            execution = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(execution.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
