"""Pin the srv design stage: hunk ids, the coverage checks, the retry with problems, and the unit files."""

import contextlib
import http.server
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path


def load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


design = load("design", "design.py")
fixtures = load("test_sweep_fixtures", "test_sweep.py")
FakeEndpoint, DIFF, SOURCE, CALLER = fixtures.FakeEndpoint, fixtures.DIFF, fixtures.SOURCE, fixtures.CALLER


NO_STRUCTURE = {"alters": False, "what": "함수 안의 분기만 바뀐다"}
CATALOG = ["db", "trace"]


def change(cid: str, kind: str = "returned_value", structure: dict = NO_STRUCTURE, unit: str = "U-1") -> dict:
    return {"id": cid, "kind": kind, "subject": "s", "before": "b", "after": "a", "hunks": ["H1"],
            "structure": structure, "unit": unit}


def perspective(pid: str, breadth: list[str], depth: str = "low", means: str = "read") -> dict:
    return {"id": pid, "value": "v", "sources": ["catalog: db"], "breadth": breadth, "depth": depth,
            "checks": [{"question": "c", "means": means}]}


def valid_changes(hunk: str = "H1") -> dict:
    return {"changes": [{**change("E-1"), "hunks": [hunk]}], "behaviour_free": [], "rules": []}


def valid_perspectives() -> dict:
    return {
        "perspectives": [perspective("K-1", ["U-1/E-1"], means="execute")],
        "sources": [{"source": "catalog: db", "use": "used", "reason": ""}, {"source": "catalog: trace", "use": "dismissed", "reason": "r"}],
    }


class CheckChangesTest(unittest.TestCase):
    def test_a_covering_change_set_passes(self) -> None:
        self.assertEqual(design.check_changes(valid_changes(), ["H1"]), [])

    def test_a_hunk_in_no_change_fails(self) -> None:
        problems = design.check_changes(valid_changes(), ["H1", "H2"])
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("hunks ['H2'] are in no change"), problems)

    def test_a_behaviour_free_hunk_needs_a_reason(self) -> None:
        answer = valid_changes()
        answer["behaviour_free"] = [{"hunk": "H2", "reason": " "}]
        self.assertTrue(design.check_changes(answer, ["H1", "H2"]))
        answer["behaviour_free"] = [{"hunk": "H2", "reason": "comment only"}]
        self.assertEqual(design.check_changes(answer, ["H1", "H2"]), [])

    def test_every_change_states_its_structure(self) -> None:
        answer = valid_changes()
        answer["changes"][0]["structure"] = {"alters": False, "what": " "}
        self.assertTrue(design.check_changes(answer, ["H1"])[0].startswith("E-1 has no `structure`"))

    def test_a_rule_names_the_line_it_read(self) -> None:
        answer = valid_changes()
        answer["rules"] = [{"source": "AGENTS.md", "text": "x"}]
        self.assertTrue(design.check_changes(answer, ["H1"]))
        answer["rules"] = [{"source": "rule: AGENTS.md:3", "text": "x"}]
        self.assertEqual(design.check_changes(answer, ["H1"]), [])


class CheckPerspectivesTest(unittest.TestCase):
    def check(self, answer: dict, *changes: dict) -> list[str]:
        return design.check_perspectives(answer, {f"{c['unit']}/{c['id']}": c for c in (changes or (change("E-1"),))}, CATALOG)

    def test_a_covering_perspective_set_passes(self) -> None:
        self.assertEqual(self.check(valid_perspectives()), [])

    def test_a_breadth_may_span_units(self) -> None:
        # Breadth is the span of changes a yardstick takes, not bound to the review units (user, 2026-11-24, "ㄱㄱ").
        answer = valid_perspectives()
        answer["perspectives"][0]["breadth"] = ["U-1/E-1", "U-2/E-1"]
        self.assertEqual(self.check(answer, change("E-1"), change("E-1", unit="U-2")), [])

    def test_a_change_in_no_breadth_fails(self) -> None:
        self.assertEqual(
            self.check(valid_perspectives(), change("E-1"), change("E-2", "failure_result")),
            ["changes ['U-1/E-2'] are in no `low`-depth perspective's breadth; every change needs a yardstick that judges "
             "its behaviour inside the functions it touches"],
        )

    def test_a_change_judged_only_at_high_depth_fails(self) -> None:
        # Low depth is where a change's behaviour is judged line by line; a high yardstick alone leaves it unjudged.
        answer = valid_perspectives()
        answer["perspectives"][0]["depth"] = "high"
        self.assertTrue(self.check(answer)[0].startswith("changes ['U-1/E-1'] are in no `low`"))

    def test_a_structural_change_needs_a_high_depth_perspective(self) -> None:
        # PR 1726 R-004: record identity held as a metadata_pairs string prefix; low-depth yardsticks caught only the
        # symptom at graph_search.cypher:339, never the representation itself.
        answer = valid_perspectives()
        structural = change("E-2", "stored_data", {"alters": True, "what": "레코드 동일성을 문자열 접두사로 나타낸다"})
        answer["perspectives"][0]["breadth"].append("U-1/E-2")
        self.assertEqual(
            self.check(answer, change("E-1"), structural),
            ["changes ['U-1/E-2'] alter a structure but are in no `high`-depth perspective's breadth; a structural defect "
             "judged only at low level shows as its symptoms, so give them a yardstick on the structure itself"],
        )
        answer["perspectives"].append(perspective("K-2", ["U-1/E-2"], depth="high"))
        self.assertEqual(self.check(answer, change("E-1"), structural), [])

    def test_a_check_states_its_means(self) -> None:
        answer = valid_perspectives()
        answer["perspectives"][0]["checks"] = ["c"]
        self.assertTrue(self.check(answer))
        answer["perspectives"][0]["checks"] = [{"question": "c", "means": "guess"}]
        self.assertTrue(self.check(answer))

    def test_an_external_contract_needs_an_execute_check(self) -> None:
        answer = valid_perspectives()
        contract = change("E-2", "external_contract")
        answer["perspectives"].append(perspective("K-2", ["U-1/E-1", "U-1/E-2"], means="read"))
        self.assertEqual(
            self.check(answer, change("E-1"), contract),
            ["external contracts ['U-1/E-2'] are in no breadth of a perspective with an `execute` check; what an external "
             "program, service, or library does is decided by running the code against a fake built from its "
             "documentation, not by reading the code that assumes it"],
        )
        answer["perspectives"][0]["breadth"].append("U-1/E-2")
        self.assertEqual(self.check(answer, change("E-1"), contract), [])

    def test_every_catalog_entry_is_used_or_dismissed_with_a_reason(self) -> None:
        answer = valid_perspectives()
        answer["sources"] = [{"source": "catalog: db", "use": "used", "reason": ""}, {"source": "trace", "use": "dismissed", "reason": ""}]
        self.assertEqual(
            design.check_perspectives(answer, {"U-1/E-1": change("E-1")}, ["db", "trace", "tests"]),
            ["catalog entry 'trace' is dismissed but is a perspective's source or has no reason",
             "catalog entry 'tests' has no row in `sources`; use it in a perspective or dismiss it with a reason"],
        )

    def test_a_source_outside_catalog_and_records_fails(self) -> None:
        answer = valid_perspectives()
        answer["perspectives"][0]["sources"] = ["catalog: db", "taste"]
        self.assertEqual(len(self.check(answer)), 1)
        answer["perspectives"][0]["sources"] = ["db", "requirement: rows load", "rule: AGENTS.md:3"]
        self.assertEqual(self.check(answer), [], "a bare catalog id is the same entry as `catalog: <id>`")


def step(body: dict) -> str:
    return body["response_format"]["json_schema"]["name"]


def both_units_perspectives() -> dict:
    answer = valid_perspectives()
    answer["perspectives"][0]["breadth"] = ["U-1/E-1", "U-2/E-1"]
    return answer


def respond_validly(body: dict) -> str:
    return json.dumps(valid_changes() if step(body) == "srv-changes" else both_units_perspectives())


class DesignRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        (self.repo / "pkg").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        (self.repo / "pkg" / "store.py").write_text(SOURCE, encoding="utf-8")
        (self.repo / "pkg" / "api.py").write_text(CALLER, encoding="utf-8")
        (self.repo / "docs" / "a.md").write_text("new\n", encoding="utf-8")
        for command in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "head"]):
            subprocess.run(["git", "-C", str(self.repo), *command], check=True)
        self.values = root / "values"
        self.values.mkdir()
        (self.values / "db.md").write_text("1. Check queries.\n", encoding="utf-8")
        (self.values / "trace.md").write_text("1. Trace the requirement.\n", encoding="utf-8")
        self.diff = root / "diff.patch"
        self.diff.write_text(DIFF, encoding="utf-8")
        self.units = root / "units.json"
        self.units.write_text(json.dumps(design.sweep.plan_units.plan_units(DIFF)), encoding="utf-8")
        self.requirement = root / "issue.md"
        self.requirement.write_text("Load rows.\n", encoding="utf-8")
        self.out = root / "design"
        jail = mock.patch.object(design.sweep.reviewer, "Jail", fixtures.FakeJail)  # one HTTP call per session, no omp
        jail.start()
        self.addCleanup(jail.stop)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeEndpoint)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        FakeEndpoint.requests = []
        FakeEndpoint.respond = staticmethod(respond_validly)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def run_design(self) -> int:
        argv = [
            "--units", str(self.units), "--diff", str(self.diff), "--repo", str(self.repo), "--values", str(self.values),
            "--requirements", str(self.requirement), "--out", str(self.out),
            "--base-url", f"http://127.0.0.1:{self.server.server_port}/v1", "--model", "fake",
        ]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = design.main(argv)
        self.stderr = stderr.getvalue()
        return code

    def test_one_change_set_per_unit_then_one_perspective_set(self) -> None:
        self.assertEqual(self.run_design(), 0)
        self.assertEqual(sorted(step(b) for b in FakeEndpoint.requests), ["srv-changes", "srv-changes", "srv-perspectives"])
        unit_body = next(b for b in FakeEndpoint.requests if step(b) == "srv-changes")
        self.assertEqual(unit_body["response_format"]["json_schema"]["schema"], design.CHANGES_SCHEMA)
        self.assertRegex(unit_body["messages"][1]["content"], r"@@ [^\n]*@@[^\n]*  \[H1\]")
        whole = next(b for b in FakeEndpoint.requests if step(b) == "srv-perspectives")["messages"][1]["content"]
        self.assertIn("## db\n\n1. Check queries.", whole)
        self.assertIn("- U-1/E-1 [returned_value]", whole)
        self.assertIn("- U-2/E-1 [returned_value]", whole)
        unit = json.loads((self.out / "U-2.json").read_text(encoding="utf-8"))
        self.assertEqual((unit["ok"], unit["hunks"]), (True, ["H1"]))
        perspectives = json.loads((self.out / "perspectives.json").read_text(encoding="utf-8"))
        self.assertEqual(perspectives["perspectives"][0]["breadth"], ["U-1/E-1", "U-2/E-1"])
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual((summary["depths"], summary["structural_changes"], summary["perspectives_ok"]), ({"high": 0, "low": 1}, 0, True))

    def test_uncovered_answer_is_sent_back_with_its_problems(self) -> None:
        calls = []

        def respond(body: dict) -> str:
            calls.append(body)
            if step(body) == "srv-perspectives":
                return json.dumps(both_units_perspectives())
            return json.dumps(valid_changes() if len(body["messages"]) == 4 else valid_changes(hunk="H9"))

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_design(), 0)
        retry = next(b for b in calls if len(b["messages"]) == 4)
        self.assertEqual(retry["messages"][2]["role"], "assistant")
        self.assertIn("hunks ['H1'] are in no change", retry["messages"][3]["content"])

    def test_unit_whose_change_set_never_covers_fails_the_run(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: json.dumps(valid_changes(hunk="H9")))
        self.assertEqual(self.run_design(), 1)
        self.assertEqual(json.loads((self.out / "summary.json").read_text())["failed"], ["U-1", "U-2"])
        self.assertIn("rerun with --only U-1 U-2", self.stderr)
        self.assertNotIn("srv-perspectives", [step(b) for b in FakeEndpoint.requests],
                         "perspectives over a partial change set would leave the missing unit's changes unjudged")

    def test_perspectives_that_leave_a_unit_unjudged_fail_and_keep_the_change_sets(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: json.dumps(valid_changes() if step(body) == "srv-changes" else valid_perspectives()))
        self.assertEqual(self.run_design(), 1)
        self.assertIn("no valid perspective set", self.stderr)
        FakeEndpoint.requests = []
        FakeEndpoint.respond = staticmethod(respond_validly)
        self.assertEqual(self.run_design(), 0)
        self.assertEqual([step(b) for b in FakeEndpoint.requests], ["srv-perspectives"], "valid change sets are reused")

    def test_diff_that_is_not_the_plan_source_is_rejected(self) -> None:
        self.diff.write_text(DIFF + "diff --git a/x b/x\n", encoding="utf-8")
        self.assertEqual(self.run_design(), 2)
        self.assertEqual(FakeEndpoint.requests, [])


if __name__ == "__main__":
    unittest.main()
