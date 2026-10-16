"""bin/ose-eval-gate turns an eval policy into an ACCEPT/REVERT verdict.

The decision rules of a detector improvement loop used to live in prose and in
ad-hoc loop scripts, and three real defects came out of that (safeanalyze,
rounds 3 and 4):

  * Summed holdout. A loop script checked the holdout on the SUM of F1 over the
    holdout sets, so a candidate that lost 2 TP on browsesafe-holdout was
    accepted because llmail-holdout rose more. The rule is per set.
  * Undocumented threshold. The same script rejected iterations whose dev F1
    gain was below 0.01, a number written nowhere. Iteration 20 was reverted on
    it, then retested and accepted as iteration 21. A threshold only exists if
    the policy declares it.
  * Single-sample tolerance (precedent v0.3.24). deepset-holdout went TP 54 -> 53
    while FP went 2 -> 0: F1 fell by one sample, precision rose, and the PRIMARY
    holdout F1 sum rose. That was accepted and became the written tolerance.

Plus the round-4 lesson that a small set (spanish, 52 positives) can move dev
F1 by +0.43 while its holdout moves +0.14: the generalization ratio gate.

The fixtures under test/fixtures/eval-gate/ reproduce those cases with the real
counts. Everything else is built inline from the shared policy.
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "bin" / "ose-eval-gate"
FIX = ROOT / "test" / "fixtures" / "eval-gate"
SCHEMA = ROOT / "specs" / "SCHEMAS" / "eval-policy.schema.json"


def load(name):
    return json.loads((FIX / name).read_text())


def counts(P, N, tp, fp, p95=12.0):
    return {"tp": tp, "fp": fp, "tn": N - fp, "fn": P - tp, "p95_ms": p95}


def f1(c):
    d = 2 * c["tp"] + c["fp"] + c["fn"]
    return 0.0 if d == 0 else 2 * c["tp"] / d


class GateRun:
    def __init__(self, proc):
        self.proc = proc
        self.code = proc.returncode
        try:
            self.out = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError:
            self.out = {}

    @property
    def decision(self):
        return self.out.get("decision")

    @property
    def text(self):
        return "\n".join(self.out.get("reasons", [])) + "\n" + self.proc.stderr


def run_gate(policy, baseline, candidate, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, obj in (("p", policy), ("b", baseline), ("c", candidate)):
            path = Path(tmp) / f"{name}.json"
            path.write_text(json.dumps(obj))
            paths.append(str(path))
        proc = subprocess.run(
            [sys.executable, str(GATE), "--policy", paths[0], "--baseline", paths[1],
             "--candidate", paths[2], "--json", *extra],
            capture_output=True, text=True, timeout=120,
        )
    return GateRun(proc)


def run_fixture(name, policy=None):
    return run_gate(policy or load("policy.json"), load(f"{name}.baseline.json"),
                    load(f"{name}.candidate.json"))


class Base(unittest.TestCase):
    def setUp(self):
        self.policy = load("policy.json")
        self.base = load("undocumented-threshold.baseline.json")
        self.cand = copy.deepcopy(self.base)
        self.cand["version"] = "next"

    def assertAccept(self, r):
        self.assertEqual(r.code, 0, f"expected ACCEPT, got {r.decision}: {r.text}")
        self.assertEqual(r.decision, "ACCEPT")

    def assertRevert(self, r, needle):
        self.assertEqual(r.code, 1, f"expected REVERT, got {r.decision}: {r.text}")
        self.assertEqual(r.decision, "REVERT")
        self.assertIn(needle, r.text)

    def assertInputError(self, r, needle):
        self.assertEqual(r.code, 2, f"expected input error, got {r.decision}: {r.text}")
        self.assertIn(needle, r.proc.stderr)


class TestRealBugFixtures(Base):
    def test_summed_holdout_bug_is_reverted_per_set(self):
        b = load("summed-holdout.baseline.json")
        c = load("summed-holdout.candidate.json")
        hold = [n for n, s in self.policy["sets"].items()
                if s["split"] == "holdout" and s["role"] == "PRIMARY"]
        # Premise: the summed check would have passed this candidate.
        self.assertGreater(sum(f1(c["sets"][n]) for n in hold),
                           sum(f1(b["sets"][n]) for n in hold))
        r = run_fixture("summed-holdout")
        self.assertRevert(r, "browsesafe-holdout")

    def test_no_threshold_unless_the_policy_declares_one(self):
        r = run_fixture("undocumented-threshold")
        self.assertAccept(r)

    def test_declared_min_gain_is_enforced(self):
        self.policy["gates"]["min_dev_f1_gain"] = 0.01
        r = run_fixture("undocumented-threshold", self.policy)
        self.assertRevert(r, "min_dev_f1_gain")

    def test_absent_min_gain_defaults_to_zero(self):
        del self.policy["gates"]["min_dev_f1_gain"]
        r = run_fixture("undocumented-threshold", self.policy)
        self.assertAccept(r)

    def test_v0324_single_sample_tolerance_is_accepted(self):
        r = run_fixture("v0324-single-sample")
        self.assertAccept(r)
        self.assertIn("single-sample tolerance", r.text)

    def test_v0324_without_tolerance_is_reverted(self):
        self.policy["gates"]["single_sample_tolerance"]["enabled"] = False
        r = run_fixture("v0324-single-sample", self.policy)
        self.assertRevert(r, "deepset-holdout")

    def test_tolerance_needs_primary_holdout_sum_to_rise(self):
        c = load("v0324-single-sample.candidate.json")
        b = load("v0324-single-sample.baseline.json")
        c["sets"]["llmail-holdout"] = b["sets"]["llmail-holdout"]
        r = run_gate(self.policy, b, c)
        self.assertRevert(r, "deepset-holdout")

    def test_tolerance_never_covers_two_lost_tp(self):
        b = load("v0324-single-sample.baseline.json")
        c = load("v0324-single-sample.candidate.json")
        c["sets"]["deepset-holdout"] = counts(203, 343, 52, 0)
        r = run_gate(self.policy, b, c)
        self.assertRevert(r, "deepset-holdout")

    def test_small_set_overfit_fails_generalization_ratio(self):
        r = run_fixture("spanish-overfit")
        self.assertRevert(r, "generalization")
        self.assertIn("spanish", r.text)

    def test_generalization_gate_can_be_disabled(self):
        self.policy["gates"]["generalization"]["enabled"] = False
        r = run_fixture("spanish-overfit", self.policy)
        self.assertAccept(r)


class TestRoles(Base):
    def test_precision_drop_on_primary_dev_reverts(self):
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 3)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "llmail")

    def test_guard_only_gain_alone_is_not_an_improvement(self):
        self.cand["sets"]["nemotron"] = counts(300, 300, 80, 0)
        self.cand["sets"]["nemotron-holdout"] = counts(300, 300, 81, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "no measurable improvement")

    def test_guard_only_regression_reverts(self):
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        self.cand["sets"]["nemotron-holdout"] = counts(300, 300, 35, 1)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "nemotron-holdout")

    def test_recall_only_allows_no_tp_loss(self):
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        self.cand["sets"]["multilingual-holdout"] = counts(825, 0, 19, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "multilingual-holdout")

    def test_report_only_never_gates(self):
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        self.cand["sets"]["stress"] = counts(180, 196, 1, 190)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertAccept(r)

    def test_missing_set_is_an_input_error(self):
        del self.cand["sets"]["llmail-holdout"]
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "llmail-holdout")

    def test_unknown_role_is_an_input_error(self):
        self.policy["sets"]["llmail"]["role"] = "PRIMARYISH"
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "PRIMARYISH")

    def test_inconsistent_counts_are_an_input_error(self):
        self.cand["sets"]["llmail"]["tp"] = -1
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "llmail")


class TestSealedSet(Base):
    def test_sealed_set_in_an_iteration_is_refused(self):
        self.cand["sets"]["sealed-2026q4"] = counts(200, 200, 100, 5)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "sealed")

    def test_sealed_set_gates_at_round_boundary(self):
        for m in (self.base, self.cand):
            m["evaluation"] = "round"
            m["sealed_evaluations"] = 1
        self.base["sets"]["sealed-2026q4"] = counts(200, 200, 100, 5)
        self.cand["sets"]["sealed-2026q4"] = counts(200, 200, 98, 5)
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "sealed-2026q4")

    def test_sealed_cadence_is_enforced(self):
        self.cand["evaluation"] = "release"
        self.cand["sealed_evaluations"] = 2
        self.cand["sets"]["sealed-2026q4"] = counts(200, 200, 100, 5)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "max_evaluations_per_release")


class TestLatency(Base):
    def test_latency_only_improvement_is_accepted(self):
        self.cand["change_kind"] = "latency"
        self.cand["sets"]["browsesafe"]["p95_ms"] = 44.0
        self.cand["sets"]["browsesafe-holdout"]["p95_ms"] = 48.0
        r = run_gate(self.policy, self.base, self.cand)
        self.assertAccept(r)
        self.assertIn("latency", r.text)

    def test_latency_only_needs_identical_labeled_counts(self):
        self.cand["sets"]["browsesafe"]["p95_ms"] = 44.0
        self.cand["sets"]["nemotron"] = counts(300, 300, 35, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "no measurable improvement")

    def test_noise_is_not_an_improvement(self):
        self.cand["sets"]["browsesafe"]["p95_ms"] = 67.0  # -4 %, inside 10 % noise
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "no measurable improvement")

    def test_latency_increase_without_gain_reverts(self):
        self.cand["sets"]["browsesafe"]["p95_ms"] = 90.0
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "latency")

    def test_over_budget_reverts_even_with_gain(self):
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        self.cand["sets"]["browsesafe"]["p95_ms"] = 120.0
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "budget")


class TestHygiene(Base):
    def test_stale_version_label_is_refused(self):
        self.cand["version"] = self.base["version"]
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "version")

    def test_dirty_tree_is_refused(self):
        self.cand["git"]["dirty"] = True
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "dirty")

    def test_new_errors_revert(self):
        self.cand["errors"] = 1
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "errors")

    def test_corpus_drop_without_fp_reduction_reverts(self):
        self.cand["corpus_findings"] = 10900
        self.cand["sets"]["llmail"] = counts(300, 160, 250, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "corpus")

    def test_security_hardening_without_regression_is_accepted(self):
        self.cand["change_kind"] = "security-hardening"
        r = run_gate(self.policy, self.base, self.cand)
        self.assertAccept(r)


def predictions(n_pos, n_neg, tp, fp):
    rows = []
    for i in range(n_pos):
        rows.append({"id": f"p{i}", "label": 1, "pred": 1 if i < tp else 0})
    for i in range(n_neg):
        rows.append({"id": f"n{i}", "label": 0, "pred": 1 if i < fp else 0})
    return rows


class TestPairedBootstrap(Base):
    def setUp(self):
        super().setUp()
        self.policy["gates"]["bootstrap"]["enabled"] = True
        self.policy["gates"]["bootstrap"]["resamples"] = 500
        self.base["sets"]["llmail"]["predictions"] = predictions(300, 160, 240, 0)

    def with_cand(self, tp):
        self.cand["sets"]["llmail"] = counts(300, 160, tp, 0)
        self.cand["sets"]["llmail"]["predictions"] = predictions(300, 160, tp, 0)

    def test_one_sample_gain_is_inside_the_noise(self):
        self.with_cand(241)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertRevert(r, "bootstrap")

    def test_large_gain_clears_the_ci(self):
        self.with_cand(270)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertAccept(r)

    def test_bootstrap_is_deterministic(self):
        self.with_cand(245)
        a = run_gate(self.policy, self.base, self.cand)
        b = run_gate(self.policy, self.base, self.cand)
        self.assertEqual(a.out, b.out)

    def test_missing_predictions_fail_explicitly(self):
        self.cand["sets"]["llmail"] = counts(300, 160, 270, 0)
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "predictions")

    def test_predictions_must_match_counts(self):
        self.with_cand(270)
        self.cand["sets"]["llmail"]["tp"] = 269
        self.cand["sets"]["llmail"]["fn"] = 31
        r = run_gate(self.policy, self.base, self.cand)
        self.assertInputError(r, "predictions")


class TestSchemaStaysInSync(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text())

    def test_schema_is_2020_12(self):
        self.assertEqual(self.schema["$schema"],
                         "https://json-schema.org/draft/2020-12/schema")

    def test_role_enum_matches_evaluator(self):
        roles = self.schema["$defs"]["set"]["properties"]["role"]["enum"]
        self.assertEqual(sorted(roles), sorted(
            ["PRIMARY", "RECALL-ONLY", "GUARD-ONLY", "REPORT-ONLY", "SEALED"]))

    def test_fixture_policy_uses_only_schema_keys(self):
        policy = load("policy.json")
        self.assertLessEqual(set(policy), set(self.schema["properties"]))
        gate_props = self.schema["properties"]["gates"]["properties"]
        self.assertLessEqual(set(policy["gates"]), set(gate_props))
        for name, sub in policy["gates"].items():
            if isinstance(sub, dict):
                self.assertLessEqual(set(sub), set(gate_props[name]["properties"]), name)

    def test_schema_documents_min_gain_default_zero(self):
        prop = self.schema["properties"]["gates"]["properties"]["min_dev_f1_gain"]
        self.assertEqual(prop["default"], 0)


if __name__ == "__main__":
    unittest.main()
