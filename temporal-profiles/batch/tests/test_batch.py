"""Synthetic-only integration checks for the resumable Mac batch wrapper.

No IBM source data or earlier scientific suite is used. Tiny actual solver and
oracle workers are exercised where their orchestration is the behavior at risk.
"""

import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time as real_time
import unittest
from unittest import mock
import zipfile


PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import batch


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class BatchIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="profile batch QA ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.csv_path = self.root / "invented_transactions.csv"
        self.protocol_path = self.root / "protocol.json"
        self.cohort_path = self.root / "cohort.json"
        self.output_dir = self.root / "output"
        self.cache_dir = self.root / "cache"
        examples = PACKAGE / "examples"
        for src, dst in (("demo_transactions.csv", self.csv_path),
                         ("demo_protocol.json", self.protocol_path),
                         ("demo_cohort.json", self.cohort_path)):
            shutil.copy2(examples / src, dst)
        self.messages = []

    def _run(self, resume=True, chunk=None):
        return batch.run_batch(
            self.csv_path, self.protocol_path, self.cohort_path,
            self.output_dir, self.cache_dir, resume=resume,
            max_new_queries=chunk, progress=self.messages.append,
        )

    def _folder(self, summary):
        return self.output_dir / summary["batch_run_id"]

    def _rows(self, summary, filename):
        path = self._folder(summary) / filename
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _protocol_edit(self, edit):
        protocol = read_json(self.protocol_path)
        edit(protocol)
        write_json(self.protocol_path, protocol)

    def _single_gap_fixture(self):
        """Invented four-event tree: preserved W2=2 permits W3 only0 or2."""
        with self.csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["Timestamp", "From Bank", "Account", "To Bank", "Account",
                             "Amount Received", "Receiving Currency", "Amount Paid",
                             "Payment Currency", "Payment Format", "Is Laundering"])
            for stamp, source_bank, source, target_bank, target in (
                    ("2022/09/01 09:00", "101", "QA_UPSTREAM", "102", "QA_MIDDLE"),
                    ("2022/09/01 09:10", "102", "QA_MIDDLE", "103", "QA_RECEIVER"),
                    ("2022/09/01 09:20", "102", "QA_MIDDLE", "103", "QA_RECEIVER"),
                    ("2022/09/01 09:30", "103", "QA_RECEIVER", "104", "QA_TARGET")):
                writer.writerow([stamp, source_bank, source, target_bank, target,
                                 "1", "USD", "1", "USD", "ACH", "0"])
        cohort = {"metadata": {"selected": 1, "synthetic_demo": True},
                  "queries": [{"query_id": "q0000", "root_bank": "104",
                               "root_account": "QA_TARGET", "cutoff_text": "2022-09-01 10:00"}]}
        write_json(self.cohort_path, cohort)
        protocol = read_json(self.protocol_path)
        protocol["protocol_id"] = "SYNTHETIC_QA_GAP_V1"
        protocol["cohort"]["query_count"] = 1
        protocol["cohort"]["sha256"] = digest(self.cohort_path)
        protocol["dataset"]["expected_rows"] = 4
        protocol["dataset"]["expected_sha256"] = digest(self.csv_path)
        write_json(self.protocol_path, protocol)

    @staticmethod
    def _is_solver(command):
        return "_solve" in command

    @staticmethod
    def _is_oracle(command):
        return any(Path(str(part)).name == "batch_verify.py" for part in command)

    @staticmethod
    def _worker_output(command):
        return Path(command[command.index("--output") + 1])

    def _assert_no_sensitive_values(self, value):
        with self.csv_path.open(newline="", encoding="utf-8") as stream:
            records = list(csv.reader(stream))[1:]
        accounts = {record[i] for record in records for i in (2, 4)}
        forbidden_keys = {"source_path", "csv_path", "cache_dir", "pilot_dir",
                          "root_bank", "root_account", "deleted_ids"}

        def visit(item):
            if isinstance(item, dict):
                self.assertFalse(forbidden_keys & set(item), forbidden_keys & set(item))
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
            elif isinstance(item, str):
                self.assertNotIn(str(self.root), item)
                self.assertNotIn("/Users/", item)
                self.assertNotIn("/workspace/", item)
                self.assertNotRegex(item, r"row:[0-9]+")
                self.assertNotIn(item, accounts)
                self.assertFalse(item.startswith("[\""), item)

        visit(value)

    def test_full_demo_keeps_denominators_and_solves_each_distinct_quota_once(self):
        original_process = subprocess.run
        with mock.patch.object(batch, "build_cache", wraps=batch.build_cache) as cache_call, \
             mock.patch.object(batch.subprocess, "run", wraps=original_process) as process_call:
            summary = self._run()
        self.assertEqual(cache_call.call_count, 1)
        self.assertEqual(summary["status"], "completed_with_limits")
        self.assertTrue(summary["full_cohort_processed"])
        self.assertEqual((summary["planned_queries"], summary["recorded_queries"], summary["pending_queries"]), (5, 5, 0))
        expected = read_json(PACKAGE / "examples/demo_expected.json")
        for key, value in expected["coverage"].items():
            self.assertEqual(summary["coverage"][key], value, key)
        rows = self._rows(summary, "CASE_RESULTS.jsonl")
        self.assertEqual({r["query_id"]: r["status"] for r in rows}, expected["case_statuses"])
        self.assertEqual([r["query_index"] for r in rows], list(range(5)))
        self.assertEqual(len(self._rows(summary, "GOAL_RESULTS.jsonl")), 5 * 18)
        commands = [call.args[0] for call in process_call.call_args_list]
        self.assertEqual(sum(self._is_solver(cmd) for cmd in commands), 2)
        self.assertEqual(sum(self._is_oracle(cmd) for cmd in commands), 2)
        for query_id in ("q0000", "q0002", "q0003"):
            row = next(r for r in rows if r["query_id"] == query_id)
            self.assertEqual(len(row["quota_results"]), 1)
            self.assertEqual(row["quota_results"][0]["preservation_percentages"], [100, 95, 90])

    def test_exact_unattainability_differs_from_over_budget(self):
        self._single_gap_fixture()
        summary = self._run()
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["coverage"]["oracle_agreement_tables"], 1)
        rows = self._rows(summary, "GOAL_RESULTS.jsonl")
        self.assertEqual(len(rows), 18)
        for row in rows:
            self.assertEqual(row["min_w2"], 2)
            self.assertEqual(row["target_w3"], 1)
            self.assertEqual(row["actual_R"], 0)
            if row["comparator"] == "exact":
                self.assertEqual(row["status"], "unattainable")
                self.assertIsNone(row["minimum_cost"])
                self.assertIsNone(row["minimum_cost_outcome"])
            else:
                self.assertEqual(row["status"], "over_budget" if row["budget"] == 0 else "solution_found")
                self.assertEqual(row["minimum_cost"], 1)
                self.assertEqual(row["minimum_cost_outcome"], {"w2": 2, "w3": 0, "cost": 1, "deleted_event_count": 1})

    def test_upload_archive_contains_only_aggregate_reports(self):
        summary = self._run()
        expected_names = {"BATCH_SUMMARY.json", "CASE_RESULTS.jsonl", "GOAL_RESULTS.jsonl", "PROTOCOL.json", "RESULTS.txt"}
        archive = self._folder(summary) / "BATCH_RESULTS.zip"
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()), expected_names)
            self.assertEqual(json.loads(z.read("BATCH_SUMMARY.json")), summary)
            for name in expected_names:
                content = z.read(name).decode("utf-8")
                if name.endswith(".json"):
                    self._assert_no_sensitive_values(json.loads(content))
                elif name.endswith(".jsonl"):
                    for line in content.splitlines():
                        if line.strip():
                            self._assert_no_sensitive_values(json.loads(line))
                else:
                    self.assertNotIn(str(self.root), content)
                    self.assertNotIn("/Users/", content)
                    self.assertNotRegex(content, r"row:[0-9]+")

    def test_resume_follows_frozen_order_without_repeating_completed_cases(self):
        first = self._run(chunk=2)
        self.assertEqual(first["status"], "paused")
        self.assertFalse(first["full_cohort_processed"])
        self.assertEqual((first["recorded_queries"], first["pending_queries"]), (2, 3))
        with mock.patch.object(batch, "extract_context", wraps=batch.extract_context) as extraction:
            second = self._run(chunk=1)
        self.assertEqual(extraction.call_count, 1)
        self.assertEqual(second["batch_run_id"], first["batch_run_id"])
        self.assertEqual((second["recorded_queries"], second["pending_queries"]), (3, 2))
        final = self._run()
        self.assertEqual(final["batch_run_id"], first["batch_run_id"])
        self.assertEqual([r["query_id"] for r in self._rows(final, "CASE_RESULTS.jsonl")], ["q%04d" % i for i in range(5)])
        self.assertEqual((final["recorded_queries"], final["pending_queries"]), (5, 0))
        with mock.patch.object(batch, "extract_context", wraps=batch.extract_context) as extraction, \
             mock.patch.object(batch.subprocess, "run") as worker:
            reused = self._run()
        self.assertEqual(reused["batch_run_id"], final["batch_run_id"])
        self.assertEqual(extraction.call_count, 0)
        self.assertEqual(worker.call_count, 0)

    def test_explicit_new_run_preserves_prior_checkpoints(self):
        self._single_gap_fixture()
        first = self._run()
        path = self._folder(first) / "case_records/q0000.json"
        original_bytes = path.read_bytes()
        second = self._run(resume=False)
        self.assertNotEqual(first["batch_run_id"], second["batch_run_id"])
        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertTrue(second["full_cohort_processed"])

    def test_source_hash_mismatch_is_input_error_before_extraction(self):
        with self.csv_path.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        with mock.patch.object(batch, "extract_context") as extraction:
            summary = self._run()
        self.assertEqual(summary["status"], "input_error")
        self.assertEqual(extraction.call_count, 0)
        self.assertFalse(summary["full_cohort_processed"])

    def test_source_row_count_mismatch_is_input_error_before_extraction(self):
        self._protocol_edit(lambda p: p["dataset"].update(expected_rows=16))
        with mock.patch.object(batch, "extract_context") as extraction:
            summary = self._run()
        self.assertEqual(summary["status"], "input_error")
        self.assertEqual(extraction.call_count, 0)

    def test_changed_cohort_fails_its_frozen_hash(self):
        cohort = read_json(self.cohort_path)
        cohort["queries"][0]["root_account"] = "DIFFERENT_TARGET"
        write_json(self.cohort_path, cohort)
        with mock.patch.object(batch, "build_cache") as cache_call:
            summary = self._run()
        self.assertEqual(summary["status"], "input_error")
        self.assertEqual(cache_call.call_count, 0)

    def test_unknown_constraint_field_is_not_silently_ignored(self):
        self._protocol_edit(lambda p: p.update(allow_tree_projection=True))
        with mock.patch.object(batch, "build_cache") as cache_call:
            summary = self._run()
        self.assertEqual(summary["status"], "input_error")
        self.assertEqual(cache_call.call_count, 0)

    def test_corrupted_record_checksum_blocks_resume_without_redo(self):
        first = self._run(chunk=1)
        path = self._folder(first) / "case_records/q0000.json"
        checkpoint = read_json(path)
        checkpoint["record"]["counts"]["w2"] += 100
        write_json(path, checkpoint)
        corrupted_bytes = path.read_bytes()
        with mock.patch.object(batch, "extract_context") as extraction, \
             mock.patch.object(batch.subprocess, "run") as worker:
            resumed = self._run()
        self.assertIn(resumed["status"], ("input_error", "verification_failed", "execution_error"))
        self.assertEqual(extraction.call_count, 0)
        self.assertEqual(worker.call_count, 0)
        self.assertEqual(path.read_bytes(), corrupted_bytes)
        self.assertFalse(resumed["full_cohort_processed"])

    def test_checkpoint_identity_mismatch_blocks_resume(self):
        first = self._run(chunk=1)
        path = self._folder(first) / "case_records/q0000.json"
        checkpoint = read_json(path)
        checkpoint["identity_sha256"] = "0" * 64
        write_json(path, checkpoint)
        with mock.patch.object(batch, "extract_context") as extraction, \
             mock.patch.object(batch.subprocess, "run") as worker:
            resumed = self._run()
        self.assertIn(resumed["status"], ("input_error", "verification_failed", "execution_error"))
        self.assertEqual(extraction.call_count, 0)
        self.assertEqual(worker.call_count, 0)

    def test_corrupted_owned_state_is_not_silently_ignored(self):
        first = self._run(chunk=1)
        folder = self._folder(first)
        path = folder / "STATE.json"
        original = path.read_bytes()
        case_path = folder / "case_records/q0000.json"
        original_case = case_path.read_bytes()
        for corruption in ("malformed_json", "bad_identity_hash", "missing_state"):
            with self.subTest(corruption=corruption):
                if corruption == "malformed_json":
                    path.write_text("{incomplete", encoding="utf-8")
                elif corruption == "bad_identity_hash":
                    state = json.loads(original)
                    state["identity_sha256"] = "0" * 64
                    write_json(path, state)
                else:
                    path.unlink()
                try:
                    with mock.patch.object(batch, "extract_context") as extraction, \
                         mock.patch.object(batch.subprocess, "run") as worker:
                        resumed = self._run()
                    self.assertIn(resumed["status"], ("input_error", "verification_failed", "execution_error"))
                    self.assertEqual(extraction.call_count, 0)
                    self.assertEqual(worker.call_count, 0)
                    self.assertEqual(case_path.read_bytes(), original_case)
                finally:
                    path.write_bytes(original)

    def test_matching_verification_failure_requires_explicit_new_run(self):
        original_process = subprocess.run

        def process(command, **kwargs):
            if self._is_oracle(command):
                write_json(self._worker_output(command), {
                    "status": "ok", "optional_events": 3, "subsets_checked": 8,
                    "feasible_subsets": 0, "profiles": [], "elapsed_seconds": 0.0})
                return subprocess.CompletedProcess(command, 0, "", "")
            return original_process(command, **kwargs)

        with mock.patch.object(batch.subprocess, "run", side_effect=process):
            failed = self._run()
        self.assertEqual(failed["status"], "verification_failed")
        checkpoint = self._folder(failed) / "case_records/q0000.json"
        old_bytes = checkpoint.read_bytes()
        with mock.patch.object(batch, "extract_context") as extraction, \
             mock.patch.object(batch.subprocess, "run") as worker:
            blocked = self._run()
        self.assertIn(blocked["status"], ("input_error", "verification_failed", "execution_error"))
        self.assertEqual(extraction.call_count, 0)
        self.assertEqual(worker.call_count, 0)
        self.assertEqual(checkpoint.read_bytes(), old_bytes)
        explicit = self._run(resume=False)
        self.assertNotEqual(explicit["batch_run_id"], failed["batch_run_id"])
        self.assertTrue(explicit["full_cohort_processed"])

    def test_solver_timeout_is_resource_limit_not_unattainability(self):
        original_process = subprocess.run

        def process(command, **kwargs):
            if self._is_solver(command):
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return original_process(command, **kwargs)

        with mock.patch.object(batch.subprocess, "run", side_effect=process):
            summary = self._run()
        self.assertTrue(summary["full_cohort_processed"])
        self.assertEqual(summary["coverage"]["completed_profile_tables"], 0)
        self.assertEqual(summary["coverage"]["oracle_agreement_tables"], 0)
        cases = self._rows(summary, "CASE_RESULTS.jsonl")
        for query_id in ("q0000", "q0002"):
            quota = next(c for c in cases if c["query_id"] == query_id)["quota_results"][0]
            self.assertEqual(quota["status"], "resource_limit")
            self.assertEqual(quota["reason_code"], "solver_timeout")
        self.assertTrue(all(r["status"] == "not_evaluated" for r in self._rows(summary, "GOAL_RESULTS.jsonl")))

    def test_oracle_timeout_preserves_witness_results_without_claiming_agreement(self):
        original_process = subprocess.run

        def process(command, **kwargs):
            if self._is_oracle(command):
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return original_process(command, **kwargs)

        with mock.patch.object(batch.subprocess, "run", side_effect=process):
            summary = self._run()
        self.assertTrue(summary["full_cohort_processed"])
        self.assertEqual(summary["coverage"]["completed_profile_tables"], 2)
        self.assertEqual(summary["coverage"]["verified_profile_tables"], 2)
        self.assertEqual(summary["coverage"]["oracle_timeout_tables"], 2)
        self.assertEqual(summary["coverage"]["oracle_agreement_tables"], 0)
        for row in self._rows(summary, "CASE_RESULTS.jsonl"):
            for quota in row["quota_results"]:
                if quota["status"] == "completed":
                    self.assertEqual(quota["witness"]["status"], "passed")
                    self.assertEqual(quota["oracle"]["status"], "timeout")
        self.assertTrue(any(g["status"] == "solution_found" for g in self._rows(summary, "GOAL_RESULTS.jsonl")))

    def test_oracle_disagreement_stops_batch_and_does_not_publish_goal_claims(self):
        original_process = subprocess.run

        def process(command, **kwargs):
            if self._is_oracle(command):
                payload = {"status": "ok", "optional_events": 3, "subsets_checked": 8,
                           "feasible_subsets": 0, "profiles": [], "elapsed_seconds": 0.0}
                write_json(self._worker_output(command), payload)
                return subprocess.CompletedProcess(command, 0, "", "")
            return original_process(command, **kwargs)

        with mock.patch.object(batch.subprocess, "run", side_effect=process):
            summary = self._run()
        self.assertEqual(summary["status"], "verification_failed")
        self.assertFalse(summary["full_cohort_processed"])
        self.assertEqual((summary["recorded_queries"], summary["pending_queries"]), (1, 4))
        self.assertEqual(summary["coverage"]["oracle_mismatch_tables"], 1)
        self.assertEqual(summary["coverage"]["oracle_agreement_tables"], 0)
        self.assertTrue(all(g["status"] == "not_evaluated" for g in self._rows(summary, "GOAL_RESULTS.jsonl")))

    def test_false_worker_witness_is_rejected_before_oracle_or_goal_lookup(self):
        original_process = subprocess.run
        oracle_calls = []

        def process(command, **kwargs):
            if self._is_oracle(command):
                oracle_calls.append(command)
            child = original_process(command, **kwargs)
            if self._is_solver(command) and child.returncode == 0:
                output = self._worker_output(command)
                payload = read_json(output)
                profile = next(p for p in payload["result"]["profiles"] if p["deleted_ids"])
                profile["deleted_ids"] = ["row:2"]
                write_json(output, payload)
            return child

        with mock.patch.object(batch.subprocess, "run", side_effect=process):
            summary = self._run()
        self.assertEqual(summary["status"], "verification_failed")
        self.assertEqual(summary["recorded_queries"], 1)
        self.assertEqual(oracle_calls, [])
        quota = self._rows(summary, "CASE_RESULTS.jsonl")[0]["quota_results"][0]
        self.assertEqual(quota["reason_code"], "profile_witness_mismatch")
        self.assertEqual(quota["witness"]["status"], "mismatch")
        self.assertTrue(all(g["status"] == "not_evaluated" for g in self._rows(summary, "GOAL_RESULTS.jsonl")))

    def test_oracle_size_skip_does_not_count_as_agreement(self):
        self._protocol_edit(lambda p: p["limits"].update(oracle_max_optional_events=2))
        original_process = subprocess.run
        with mock.patch.object(batch.subprocess, "run", wraps=original_process) as process_call:
            summary = self._run()
        self.assertEqual(summary["coverage"]["completed_profile_tables"], 2)
        self.assertEqual(summary["coverage"]["verified_profile_tables"], 2)
        self.assertEqual(summary["coverage"]["oracle_size_skipped_tables"], 1)
        self.assertEqual(summary["coverage"]["oracle_agreement_tables"], 1)
        commands = [call.args[0] for call in process_call.call_args_list]
        self.assertEqual(sum(self._is_oracle(cmd) for cmd in commands), 1)

    def test_extraction_caps_leave_structural_eligibility_unknown(self):
        self._protocol_edit(lambda p: p["limits"].update(max_context_events=2))
        summary = self._run()
        self.assertTrue(summary["full_cohort_processed"])
        self.assertEqual((summary["planned_queries"], summary["recorded_queries"], summary["pending_queries"]), (5, 5, 0))
        coverage = summary["coverage"]
        self.assertEqual(coverage["structural_status_unknown"], 3)
        self.assertEqual(coverage["extractions_completed"], 2)
        self.assertEqual(coverage["nonempty_eligible_contexts"], 1)
        self.assertEqual(coverage["empty_contexts"], 1)
        self.assertEqual(coverage["ineligible_contexts"], 0)
        for row in self._rows(summary, "CASE_RESULTS.jsonl"):
            if row["query_id"] in ("q0000", "q0001", "q0003"):
                self.assertEqual(row["structure"]["status"], "unknown")
                self.assertEqual(row["quota_results"], [])

    def test_interrupt_retains_partial_identity_and_resumes(self):
        original_process = subprocess.run

        def process(command, **kwargs):
            if self._is_oracle(command):
                raise KeyboardInterrupt
            return original_process(command, **kwargs)

        with mock.patch.object(batch.subprocess, "run", side_effect=process):
            interrupted = self._run()
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertFalse(interrupted["full_cohort_processed"])
        self.assertEqual((interrupted["recorded_queries"], interrupted["pending_queries"]), (0, 5))
        old_profiles = list(self._folder(interrupted).glob("cases/q0000/attempt_*/quota_*/profiles.json"))
        self.assertEqual(len(old_profiles), 1)
        old_bytes = old_profiles[0].read_bytes()
        resumed = self._run()
        self.assertEqual(resumed["batch_run_id"], interrupted["batch_run_id"])
        self.assertTrue(resumed["full_cohort_processed"])
        self.assertEqual(resumed["recorded_queries"], 5)
        self.assertEqual(old_profiles[0].read_bytes(), old_bytes)
        self.assertEqual(len(list(self._folder(resumed).glob("cases/q0000/attempt_*"))), 2)

    def test_invocation_deadline_pauses_without_turning_pending_cases_into_failures(self):
        self._protocol_edit(lambda p: p["limits"].update(invocation_time_limit_seconds=1))
        original_cache = batch.build_cache

        class Clock:
            offset = 0.0

            def monotonic(self):
                return real_time.monotonic() + self.offset

            def __getattr__(self, name):
                return getattr(real_time, name)

        clock = Clock()

        def cache_call(*args, **kwargs):
            result = original_cache(*args, **kwargs)
            clock.offset = 60.0
            return result

        with mock.patch.object(batch, "time", clock), \
             mock.patch.object(batch, "build_cache", side_effect=cache_call), \
             mock.patch.object(batch, "extract_context") as extraction:
            summary = self._run()
        self.assertEqual(summary["status"], "paused")
        self.assertFalse(summary["full_cohort_processed"])
        self.assertEqual((summary["recorded_queries"], summary["pending_queries"]), (0, 5))
        self.assertEqual(extraction.call_count, 0)
        self.assertEqual(self._rows(summary, "CASE_RESULTS.jsonl"), [])
        self.assertEqual(self._rows(summary, "GOAL_RESULTS.jsonl"), [])

    def test_local_exception_detail_is_excluded_from_shareable_reports(self):
        secret = "QA_TARGET at /Users/private-person/secret-source.csv row:4321"
        with mock.patch.object(batch, "extract_context", side_effect=RuntimeError(secret)):
            summary = self._run()
        self.assertIn(summary["status"], ("input_error", "execution_error"))
        archive = self._folder(summary) / "BATCH_RESULTS.zip"
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                content = z.read(name).decode("utf-8")
                self.assertNotIn(secret, content)
                self.assertNotIn("private-person", content)
                self.assertNotIn("row:4321", content)
                self.assertNotIn(str(self.root), content)


if __name__ == "__main__":
    unittest.main()
