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
context_script = load("srv_context", "context.py")
FakeEndpoint, DIFF, SOURCE, CALLER = fixtures.FakeEndpoint, fixtures.DIFF, fixtures.SOURCE, fixtures.CALLER


NO_STRUCTURE = {"alters": False, "what": "함수 안의 분기만 바뀐다"}
def catalog(*ids: str, stakes: dict[str, tuple[str, ...]] | None = None) -> dict:
    return {i: design.sweep.CatalogItem("# Method", "text", (stakes or {}).get(i, ())) for i in ids}


CATALOG = catalog("db#1", "trace#1")


def change(cid: str, kind: str = "returned_value", structure: dict = NO_STRUCTURE, unit: str = "U-1") -> dict:
    return {"id": cid, "kind": kind, "subject": "s", "before": "b", "after": "a", "hunks": ["H1"],
            "structure": structure, "unit": unit, "files": ["pkg/store.py"]}


def perspective(pid: str, breadth: list[str], depth: str = "low", means: str = "read") -> dict:
    return {"id": pid, "value": "v", "broken_if": "x", "breadth": breadth, "depth": depth,
            "checks": [{"question": "c", "means": means, "source": "catalog: db#1"}]}


def valid_changes(hunk: str = "H1") -> dict:
    return {"changes": [{**change("E-1"), "hunks": [hunk]}], "behaviour_free": [], "rules": []}


def valid_perspectives() -> dict:
    return {
        "perspectives": [perspective("K-1", ["U-1/E-1"], means="execute")],
        "dismissed": [{"item": "catalog: trace#1", "reason": "r"}], "rules": [],
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
        return design.check_perspectives(answer, {f"{c['unit']}/{c['id']}": c for c in (changes or (change("E-1"),))}, CATALOG, [])

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

    def test_a_perspective_states_what_breaks_its_value(self) -> None:
        answer = valid_perspectives()
        answer["perspectives"][0]["broken_if"] = " "
        problems = design.check_perspectives(answer, {"U-1/E-1": change("E-1")}, CATALOG, [])
        self.assertTrue(any("K-1 has no `broken_if`" in p for p in problems), problems)

    def test_a_low_perspective_stays_narrow(self) -> None:
        many = {f"U-1/E-{n}": change(f"E-{n}") for n in range(1, design.LOW_BREADTH_MAX + 2)}
        answer = valid_perspectives()
        answer["perspectives"][0]["breadth"] = list(many)
        problems = design.check_perspectives(answer, many, CATALOG, [])
        self.assertTrue(any(f"K-1 is `low` with {design.LOW_BREADTH_MAX + 1} changes" in p for p in problems), problems)
        answer["perspectives"] = [perspective("K-1", list(many)[: design.LOW_BREADTH_MAX], means="execute"),
                                  perspective("K-2", list(many)[design.LOW_BREADTH_MAX:], means="execute"),
                                  perspective("K-3", list(many), depth="high")]
        self.assertEqual(design.check_perspectives(answer, many, CATALOG, []), [],
                         "a high perspective may be wide: it judges structure, not lines")

    def test_a_check_states_its_means(self) -> None:
        answer = valid_perspectives()
        answer["perspectives"][0]["checks"] = ["c"]
        self.assertTrue(self.check(answer))
        answer["perspectives"][0]["checks"] = [{"question": "c", "means": "guess", "source": "catalog: db#1"}]
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

    def test_every_catalog_item_is_asked_by_a_check_or_dismissed_with_a_reason(self) -> None:
        # Coordinator, 2026-11-25: "항목마다 어느 관점의 가치로 쓰였거나 이유와 함께 기각됐는지를 코드가 확인하게 하라".
        answer = valid_perspectives()
        answer["dismissed"] = [{"item": "trace#1", "reason": " "}, {"item": "db#1", "reason": "r"}]
        self.assertEqual(
            design.check_perspectives(answer, {"U-1/E-1": change("E-1")}, catalog("db#1", "trace#1", "db#2", "tests#1"), []),
            ["catalog item 'trace#1' is dismissed without a reason",
             "catalog item 'db#1' is dismissed but a check asks it; keep one of the two",
             ("catalog items ['trace#1', 'db#2', 'tests#1'] are asked by no check and not dismissed; an item left out "
              "is a defect class the review never looks for, so give each a check in the perspective whose value it "
              "serves (a new perspective when none fits, within the breadth caps), or dismiss it with the reason no "
              "change has it at stake")],
            "an item of a file another item of which is asked is still unasked",
        )

    def test_an_item_with_a_stake_is_asked_over_every_change_of_its_kinds(self) -> None:
        # Replay 13b (PR #1726): the reuse item was asked over one unit, and the units holding its defects were not.
        changes = {"U-1/E-1": change("E-1"), "U-2/E-1": change("E-1", unit="U-2"),
                   "U-3/E-1": change("E-1", kind="test_contract", unit="U-3")}
        items = catalog("db#1", "growth#2", "tests#2", stakes={"growth#2": ("returned_value",), "tests#2": ("stored_data",)})
        answer = valid_perspectives()
        answer["dismissed"] = []
        answer["perspectives"] = [
            perspective("K-1", ["U-1/E-1", "U-3/E-1"], means="execute"),
            {**perspective("K-2", ["U-2/E-1"]), "checks": [{"question": "q", "means": "read", "source": "growth#2"}]},
        ]
        self.assertEqual(
            design.check_perspectives(answer, changes, items, []),
            [("growth#2 is at stake in changes ['U-1/E-1'], which are in the breadth of no perspective with a check "
             "naming it; a source asked over some of its changes leaves the rest unreviewed, so add the check to the "
             "perspectives that already hold those changes, or to a `high` perspective over all of them")],
            "an item whose kinds no change has (tests#2 here) needs no check",
        )
        answer["perspectives"][1]["breadth"] = ["U-1/E-1", "U-2/E-1"]
        self.assertEqual(design.check_perspectives(answer, changes, items, []), [])
        answer["dismissed"] = [{"item": "growth#2", "reason": "r"}]
        self.assertIn("catalog item 'growth#2' is dismissed but a check asks it; keep one of the two",
                      design.check_perspectives(answer, changes, items, []))

    def test_a_high_perspective_asking_a_source_is_widened_to_its_stake(self) -> None:
        # Run 13f (PR #1726): the answer failed twice on changes a high reuse check had left out of its breadth.
        changes = {f"U-{n}/E-1": change("E-1", unit=f"U-{n}") for n in (1, 2, 3)}
        items = catalog("db#1", "growth#2", stakes={"growth#2": ("returned_value",)})
        answer = valid_perspectives()
        answer["dismissed"] = []
        answer["perspectives"] = [
            perspective("K-1", list(changes), means="execute"),
            {**perspective("K-2", ["U-1/E-1"], depth="high"),
             "checks": [{"question": "q", "means": "read", "source": "growth#2"}]},
        ]
        self.assertEqual(design.widen_to_stakes(answer, changes, items, []),
                         [{"perspective": "K-2", "source": "growth#2", "changes": ["U-2/E-1", "U-3/E-1"]}])
        self.assertEqual(design.check_perspectives(answer, changes, items, []), [])
        answer["perspectives"][1]["depth"] = "low"
        answer["perspectives"][1]["breadth"] = ["U-1/E-1"]
        self.assertEqual(design.widen_to_stakes(answer, changes, items, []), [],
                         "a low perspective is not widened: its breadth is capped and judged line by line")

    def test_a_rule_states_its_stake_and_is_asked_over_it(self) -> None:
        # Coordinator, 2026-11-25: "규칙마다 걸리는 변경 종류를 설계 답에 적게 하고 코드가 같은 방식으로 덮음을 확인하게 하라".
        changes = {"U-1/E-1": change("E-1", kind="test_contract"),
                   "U-2/E-1": {**change("E-1", kind="test_contract", unit="U-2"), "files": ["tests/integration/t.py"]}}
        rule = "rule: tests/integration/AGENTS.md:7"
        answer = valid_perspectives()
        answer["perspectives"][0]["breadth"] = ["U-1/E-1", "U-2/E-1"]
        self.assertEqual(
            design.check_perspectives(answer, changes, CATALOG, [rule]),
            [(f"rules ['{rule}'] have no row in `rules`; a repository rule is a value source like a catalog item, so "
             "give each the change kinds and the path prefix it is at stake in, or no kinds and the reason")],
        )
        answer["rules"] = [{"rule": rule, "kinds": ["test_contract"], "under": "tests/integration/", "reason": ""}]
        self.assertEqual(
            design.check_perspectives(answer, changes, CATALOG, [rule]),
            [(f"{rule} is at stake in changes ['U-2/E-1'], which are in the breadth of no perspective with a check "
             "naming it; a source asked over some of its changes leaves the rest unreviewed, so add the check to the "
             "perspectives that already hold those changes, or to a `high` perspective over all of them")],
            "the path prefix keeps U-1/E-1, outside tests/integration/, out of the rule's stake",
        )
        answer["perspectives"][0]["checks"].append({"question": "q", "means": "read", "source": rule})
        self.assertEqual(design.check_perspectives(answer, changes, CATALOG, [rule]), [])
        answer["rules"][0]["rule"] = "tests/integration/AGENTS.md:7"
        self.assertEqual(design.check_perspectives(answer, changes, CATALOG, [rule]), [],
                         "a bare `<path>:<line>` names the same rule, as a bare item id names a catalog item")
        answer["perspectives"][0]["checks"].pop()
        answer["rules"] = [{"rule": rule, "kinds": [], "under": "", "reason": " "}]
        self.assertEqual(design.check_perspectives(answer, changes, CATALOG, [rule]),
                         [f"{rule} has no kinds and no reason; give the change kinds it is at stake in, or why none"])

    def test_every_catalog_stake_in_the_repository_is_a_change_kind(self) -> None:
        catalog_items = design.read_checked_catalog(design.sweep.VALUES)
        self.assertTrue(any(item.stakes for item in catalog_items.values()))

    def test_a_check_source_is_a_catalog_item_or_a_record(self) -> None:
        answer = valid_perspectives()
        answer["perspectives"][0]["checks"].append({"question": "q", "means": "read", "source": "catalog: db"})
        self.assertEqual(len(self.check(answer)), 1, "a whole catalog file is not a source")
        answer["perspectives"][0]["checks"][1]["source"] = "taste"
        self.assertEqual(len(self.check(answer)), 1)
        answer["perspectives"][0]["checks"][1]["source"] = "rule: AGENTS.md:3"
        self.assertEqual(len(self.check(answer)), 1, "a rule outside the request's rule list is not a source")
        for source in ("db#1", "requirement: rows load"):
            answer["perspectives"][0]["checks"][1]["source"] = source
            self.assertEqual(self.check(answer), [], source)


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
        (self.values / "db.md").write_text("# Method: db\n1. Check queries.\n", encoding="utf-8")
        (self.values / "trace.md").write_text("# Method: trace\n1. Trace the requirement.\n", encoding="utf-8")
        self.diff = root / "diff.patch"
        self.diff.write_text(DIFF, encoding="utf-8")
        self.units = root / "units.json"
        self.units.write_text(json.dumps(design.sweep.plan_units.plan_units(DIFF)), encoding="utf-8")
        self.requirement = root / "issue.md"
        self.requirement.write_text("Load rows.\n", encoding="utf-8")
        self.out = root / "design"
        self.context = root / "context"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(context_script.main([
                "--units", str(self.units), "--diff", str(self.diff), "--repo", str(self.repo),
                "--requirements", str(self.requirement), "--out", str(self.context)]), 0)
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
            "--context", str(self.context), "--out", str(self.out),
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
        self.assertTrue(unit_body["messages"][1]["content"].startswith("# Repository context of this review"),
                        "every request starts with the shared pack, so the server reuses its prefix")
        self.assertIn("Load rows.", unit_body["messages"][1]["content"])
        whole = next(b for b in FakeEndpoint.requests if step(b) == "srv-perspectives")["messages"][1]["content"]
        self.assertIn("# Method: db\n- db#1: Check queries.", whole)
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
