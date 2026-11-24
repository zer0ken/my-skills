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


def change(cid: str, kind: str = "returned_value", structure: dict = NO_STRUCTURE) -> dict:
    return {"id": cid, "kind": kind, "subject": "s", "before": "b", "after": "a", "hunks": ["H1"], "structure": structure}


def perspective(pid: str, breadth: list[str], depth: str = "low", means: str = "read") -> dict:
    return {"id": pid, "value": "v", "sources": ["db"], "breadth": breadth, "depth": depth,
            "checks": [{"question": "c", "means": means}]}


def valid(hunk: str = "H1", catalog=("db", "trace")) -> dict:
    return {
        "changes": [{**change("E-1"), "hunks": [hunk]}],
        "behaviour_free": [],
        "perspectives": [perspective("K-1", ["E-1"], means="execute")],
        "sources": [{"source": "db", "use": "used", "reason": ""}]
        + [{"source": s, "use": "dismissed", "reason": "r"} for s in catalog if s != "db"],
    }


class CheckDesignTest(unittest.TestCase):
    def test_a_covering_design_passes(self) -> None:
        self.assertEqual(design.check_design(valid(), ["H1"], ["db", "trace"]), [])

    def test_a_hunk_in_no_change_fails(self) -> None:
        problems = design.check_design(valid(), ["H1", "H2"], ["db", "trace"])
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("hunks ['H2'] are in no change"), problems)

    def test_a_behaviour_free_hunk_needs_a_reason(self) -> None:
        answer = valid()
        answer["behaviour_free"] = [{"hunk": "H2", "reason": " "}]
        self.assertTrue(design.check_design(answer, ["H1", "H2"], ["db", "trace"]))
        answer["behaviour_free"] = [{"hunk": "H2", "reason": "comment only"}]
        self.assertEqual(design.check_design(answer, ["H1", "H2"], ["db", "trace"]), [])

    def test_a_change_in_no_breadth_fails(self) -> None:
        answer = valid()
        answer["changes"].append(change("E-2", "failure_result"))
        self.assertEqual(
            design.check_design(answer, ["H1"], ["db", "trace"]),
            ["changes ['E-2'] are in no `low`-depth perspective's breadth; every change needs a yardstick that judges "
             "its behaviour inside the functions it touches"],
        )

    def test_a_change_judged_only_at_high_depth_fails(self) -> None:
        # Low depth is where a change's behaviour is judged line by line; a high yardstick alone leaves it unjudged.
        answer = valid()
        answer["perspectives"][0]["depth"] = "high"
        self.assertTrue(design.check_design(answer, ["H1"], ["db", "trace"])[0].startswith("changes ['E-1'] are in no `low`"))

    def test_a_structural_change_needs_a_high_depth_perspective(self) -> None:
        # PR 1726 R-004: record identity held as a metadata_pairs string prefix; low-depth yardsticks caught only the
        # symptom at graph_search.cypher:339, never the representation itself.
        answer = valid()
        answer["changes"].append(change("E-2", "stored_data", {"alters": True, "what": "레코드 동일성을 문자열 접두사로 나타낸다"}))
        answer["perspectives"][0]["breadth"].append("E-2")
        self.assertEqual(
            design.check_design(answer, ["H1"], ["db", "trace"]),
            ["changes ['E-2'] alter a structure but are in no `high`-depth perspective's breadth; a structural defect "
             "judged only at low level shows as its symptoms, so give them a yardstick on the structure itself"],
        )
        answer["perspectives"].append(perspective("K-2", ["E-2"], depth="high"))
        self.assertEqual(design.check_design(answer, ["H1"], ["db", "trace"]), [])

    def test_every_change_states_its_structure(self) -> None:
        answer = valid()
        answer["changes"][0]["structure"] = {"alters": False, "what": " "}
        self.assertTrue(design.check_design(answer, ["H1"], ["db", "trace"])[0].startswith("E-1 has no `structure`"))

    def test_a_check_states_its_means(self) -> None:
        answer = valid()
        answer["perspectives"][0]["checks"] = ["c"]
        self.assertTrue(design.check_design(answer, ["H1"], ["db", "trace"]))
        answer["perspectives"][0]["checks"] = [{"question": "c", "means": "guess"}]
        self.assertTrue(design.check_design(answer, ["H1"], ["db", "trace"]))

    def test_an_external_contract_needs_an_execute_check(self) -> None:
        answer = valid()
        answer["changes"].append(change("E-2", "external_contract"))
        answer["perspectives"].append(perspective("K-2", ["E-1", "E-2"], means="read"))
        self.assertEqual(
            design.check_design(answer, ["H1"], ["db", "trace"]),
            ["external contracts ['E-2'] are in no breadth of a perspective with an `execute` check; what an external "
             "program, service, or library does is decided by running the code against a fake built from its "
             "documentation, not by reading the code that assumes it"],
        )
        answer["perspectives"][0]["breadth"].append("E-2")
        self.assertEqual(design.check_design(answer, ["H1"], ["db", "trace"]), [])

    def test_every_catalog_entry_is_used_or_dismissed_with_a_reason(self) -> None:
        answer = valid()
        answer["sources"] = [{"source": "db", "use": "used", "reason": ""}, {"source": "trace", "use": "dismissed", "reason": ""}]
        self.assertEqual(
            design.check_design(answer, ["H1"], ["db", "trace", "tests"]),
            ["catalog entry 'trace' is dismissed but is a perspective's source or has no reason",
             "catalog entry 'tests' has no row in `sources`; use it in a perspective or dismiss it with a reason"],
        )

    def test_used_entry_must_be_a_perspective_source(self) -> None:
        answer = valid()
        answer["sources"][1] = {"source": "trace", "use": "used", "reason": ""}
        self.assertEqual(design.check_design(answer, ["H1"], ["db", "trace"]),
                         ["catalog entry 'trace' is marked used but no perspective names it as a source"])

    def test_a_source_outside_catalog_and_records_fails(self) -> None:
        answer = valid()
        answer["perspectives"][0]["sources"] = ["db", "taste"]
        self.assertEqual(len(design.check_design(answer, ["H1"], ["db", "trace"])), 1)
        answer["perspectives"][0]["sources"] = ["db", "requirement: rows load", "rule: AGENTS.md:3"]
        self.assertEqual(design.check_design(answer, ["H1"], ["db", "trace"]), [])


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
        FakeEndpoint.respond = staticmethod(lambda body: json.dumps(valid()))

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

    def test_one_call_per_unit_and_files_carry_the_design(self) -> None:
        self.assertEqual(self.run_design(), 0)
        self.assertEqual(len(FakeEndpoint.requests), 2)
        body = FakeEndpoint.requests[0]
        self.assertEqual(body["response_format"]["json_schema"]["schema"], design.DESIGN_SCHEMA)
        user = body["messages"][1]["content"]
        self.assertIn("## db\n\n1. Check queries.", user)
        self.assertRegex(user, r"@@ [^\n]*@@[^\n]*  \[H1\]")
        unit = json.loads((self.out / "U-2.json").read_text(encoding="utf-8"))
        self.assertEqual((unit["ok"], unit["hunks"], unit["perspectives"][0]["depth"]), (True, ["H1"], "low"))
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual((summary["depths"], summary["structural_changes"]), ({"high": 0, "low": 2}, 0))

    def test_uncovered_answer_is_sent_back_with_its_problems(self) -> None:
        calls = []

        def respond(body: dict) -> str:
            calls.append(body)
            return json.dumps(valid() if len(body["messages"]) == 4 else valid(hunk="H9"))

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_design(), 0)
        retry = next(b for b in calls if len(b["messages"]) == 4)
        self.assertEqual(retry["messages"][2]["role"], "assistant")
        self.assertIn("hunks ['H1'] are in no change", retry["messages"][3]["content"])

    def test_unit_whose_design_never_covers_fails_the_run(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: json.dumps(valid(hunk="H9")))
        self.assertEqual(self.run_design(), 1)
        self.assertEqual(json.loads((self.out / "summary.json").read_text())["failed"], ["U-1", "U-2"])
        self.assertIn("rerun them with --only U-1 U-2", self.stderr)

    def test_diff_that_is_not_the_plan_source_is_rejected(self) -> None:
        self.diff.write_text(DIFF + "diff --git a/x b/x\n", encoding="utf-8")
        self.assertEqual(self.run_design(), 2)
        self.assertEqual(FakeEndpoint.requests, [])


if __name__ == "__main__":
    unittest.main()
