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
ALL_KINDS = list(design.CHANGE_KINDS)


def entry(pid: str, depth: str, picks: list[str], execute: bool = False):
    return design.sweep.CatalogPerspective(pid, f"title {pid}", f"value of {pid}", "when", f"broken {pid}", depth,
                                           tuple(picks), execute, "rv")


# A catalog that covers by construction: L1 is the low execute perspective of every kind, H2 the high one of
# structure, and L6 one picked by a tag.
CATALOG = {"L1": entry("L1", "low", ALL_KINDS, execute=True), "H2": entry("H2", "high", ["structure"]),
           "L6": entry("L6", "low", ["query"])}


def change(cid: str, kind: str = "returned_value", structure: dict = NO_STRUCTURE, unit: str = "U-1",
           files: tuple[str, ...] = ("pkg/store.py",), tags: tuple[str, ...] = ()) -> dict:
    return {"id": cid, "kind": kind, "subject": "s", "before": "b", "after": "a", "hunks": ["H1"], "tags": list(tags),
            "structure": structure, "unit": unit, "files": list(files)}


def perspective(pid: str, breadth: list[str], catalog: str = "L1", means: str = "execute", rules: list[str] = ()) -> dict:
    picked = CATALOG[catalog]
    checks = [{"question": "c", "means": means, "source": catalog}] + [{"question": "r", "means": "read", "source": r} for r in rules]
    return {"id": pid, "catalog": catalog, "value": picked.value, "broken_if": "x", "breadth": breadth,
            "depth": picked.depth, "checks": checks, "rules": [{"rule": r, "text": "t"} for r in rules]}


def valid_changes(hunk: str = "H1") -> dict:
    return {"changes": [{**change("E-1"), "hunks": [hunk]}], "behaviour_free": [], "rules": []}


def valid_perspectives() -> dict:
    return {"perspectives": [perspective("K-1", ["U-1/E-1"])],
            "unpicked": [{"catalog": "H2", "reason": "r"}, {"catalog": "L6", "reason": "r"}], "rules": []}


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
    def check(self, answer: dict, *changes: dict, rules: list[str] = ()) -> list[str]:
        return design.check_perspectives(answer, {f"{c['unit']}/{c['id']}": c for c in (changes or (change("E-1"),))},
                                         CATALOG, list(rules))

    def test_a_covering_perspective_set_passes(self) -> None:
        self.assertEqual(self.check(valid_perspectives()), [])

    def test_a_breadth_may_span_units(self) -> None:
        # Breadth is the span of changes a yardstick takes, not bound to the review units (user, 2026-11-24, "ㄱㄱ").
        answer = valid_perspectives()
        answer["perspectives"][0]["breadth"] = ["U-1/E-1", "U-2/E-1"]
        self.assertEqual(self.check(answer, change("E-1"), change("E-1", unit="U-2")), [])

    def test_a_perspective_is_picked_from_the_catalog_with_its_value_and_depth(self) -> None:
        # The user (2026-11-24): "관점은 코드에서 찾는게 아니라 미리 정해진 검토 관점 중에서 코드 변경에 관련된 걸 고르는거다."
        answer = valid_perspectives()
        answer["perspectives"][0]["catalog"] = "made"
        self.assertTrue(self.check(answer)[0].startswith("K-1 names 'made', which is not a catalog perspective"))
        answer = valid_perspectives()
        answer["perspectives"][0]["value"] = "a value written for this change"
        self.assertIn("K-1 changes the value or depth of L1; the catalog fixes both", self.check(answer))

    def test_a_change_in_no_low_breadth_fails(self) -> None:
        self.assertEqual(
            self.check(valid_perspectives(), change("E-1"), change("E-2", "failure_result")),
            [("changes ['U-1/E-2'] are in no `low` perspective's breadth; every change needs a yardstick that judges its "
             "behaviour inside the functions it touches")])

    def test_a_structural_change_needs_a_high_perspective(self) -> None:
        # PR 1726 R-004: low-depth yardsticks caught only a symptom of a structural defect.
        structural = change("E-2", "stored_data", {"alters": True, "what": "동일성을 문자열 접두사로 나타낸다"})
        answer = valid_perspectives()
        answer["perspectives"][0]["breadth"].append("U-1/E-2")
        self.assertEqual(self.check(answer, change("E-1"), structural),
                         [("changes ['U-1/E-2'] alter a structure but are in no `high` perspective's breadth; a "
                          "structural defect judged only at low level shows as its symptoms")])
        answer["perspectives"].append(perspective("K-2", ["U-1/E-2"], catalog="H2", means="read"))
        answer["unpicked"] = [{"catalog": "L6", "reason": "r"}]
        self.assertEqual(self.check(answer, change("E-1"), structural), [])

    def test_a_perspective_states_what_breaks_its_value(self) -> None:
        answer = valid_perspectives()
        answer["perspectives"][0]["broken_if"] = " "
        self.assertIn("K-1 has no `broken_if` bound to this change", self.check(answer))

    def test_a_low_perspective_stays_narrow(self) -> None:
        ids = [f"E-{n}" for n in range(1, design.LOW_BREADTH_MAX + 2)]
        answer = valid_perspectives()
        answer["perspectives"][0]["breadth"] = [f"U-1/{i}" for i in ids]
        self.assertTrue(any(p.startswith(f"K-1 is `low` with {len(ids)} changes") for p in self.check(answer, *map(change, ids))))

    def test_an_external_contract_needs_an_execute_check(self) -> None:
        answer = valid_perspectives()
        answer["perspectives"][0]["checks"][0]["means"] = "read"
        self.assertEqual(self.check(answer, change("E-1", "external_contract")),
                         [("external contracts ['U-1/E-1'] are in no breadth of a perspective with an `execute` check; what "
                          "an external program does is decided by running against a fake built from its documentation")])

    def test_one_perspective_asks_its_value_and_its_attached_rules_only(self) -> None:
        rule = "rule: tests/integration/AGENTS.md:7"
        answer = valid_perspectives()
        answer["perspectives"][0] = perspective("K-1", ["U-1/E-1"], rules=[rule])
        answer["rules"] = [{"rule": rule, "perspectives": ["L1"], "reason": "r"}]
        self.assertEqual(self.check(answer, rules=[rule]), [])
        answer["perspectives"][0]["checks"].append({"question": "q", "means": "read", "source": "H2"})
        self.assertIn("K-1 has checks asking ['H2'], which are neither its catalog value L1 nor a rule attached to "
                      "it; one perspective judges one value", self.check(answer, rules=[rule]))

    def test_every_catalog_perspective_is_picked_or_left_with_a_reason(self) -> None:
        answer = valid_perspectives()
        answer["unpicked"] = [{"catalog": "H2", "reason": " "}]
        self.assertIn("catalog perspectives ['H2', 'L6'] are neither picked nor left with a reason", self.check(answer))

    def test_a_rule_whose_directory_holds_a_changed_file_is_attached(self) -> None:
        # Run 13i left out the one-backend docstring rule that rv R-007 rests on; a root rule may stay context (13l).
        rule, root = "rule: pkg/AGENTS.md:7", "rule: AGENTS.md:2"
        answer = valid_perspectives()
        answer["rules"] = [{"rule": rule, "perspectives": [], "reason": "r"}, {"rule": root, "perspectives": [], "reason": "r"}]
        self.assertEqual(self.check(answer, rules=[rule, root]),
                         [(f"{rule} is attached to no perspective, but its document governs files the change touches "
                          "under 'pkg/'; whether those changes keep it is what the review decides")])

    def test_one_rule_text_cited_under_two_ids_is_one_source(self) -> None:
        designs = {"U-1": {"rules": [{"source": "rule: emem/AGENTS.md:3", "text": "keep it simple"},
                                     {"source": "rule: AGENTS.md:3", "text": "keep it simple "},
                                     {"source": "rule: AGENTS.md:4", "text": "other"}]}}
        self.assertEqual(design.distinct_rules(designs),
                         ({"rule: AGENTS.md:3": "keep it simple", "rule: AGENTS.md:4": "other"},
                          {"rule: emem/AGENTS.md:3": "rule: AGENTS.md:3"}))


class PickTest(unittest.TestCase):
    def test_a_perspective_is_picked_by_kind_structure_or_tag_in_change_order(self) -> None:
        changes = {"U-1/E-1": change("E-1", "stored_data", tags=("query",)), "U-1/E-2": change("E-2"),
                   "U-2/E-1": change("E-1", "documented_promise", {"alters": True, "what": "w"}, unit="U-2")}
        self.assertEqual(design.stakes_by_pick(CATALOG, changes),
                         {"L1": ["U-1/E-1", "U-1/E-2", "U-2/E-1"], "H2": ["U-2/E-1"], "L6": ["U-1/E-1"]})

    def test_a_rule_names_only_picked_perspectives(self) -> None:
        rule = "rule: pkg/AGENTS.md:7"
        changes = {"U-1/E-1": change("E-1")}
        self.assertEqual(design.check_rules({"rules": [{"rule": rule, "perspectives": ["L1"], "reason": "r"}]},
                                            [rule], ["L1"], changes), [])
        self.assertEqual(design.check_rules({"rules": [{"rule": "pkg/AGENTS.md:7", "perspectives": ["db#9"], "reason": "r"}]},
                                            [rule], ["L1"], changes),
                         [f"{rule} names ['db#9'], which are not picked perspective ids"])
        self.assertTrue(design.check_rules({"rules": [{"rule": rule, "perspectives": [], "reason": "r"}]},
                                           [rule], ["L1"], changes)[0].startswith(f"{rule} is attached to nothing, but"))

    def test_a_binding_asks_the_value_every_attached_rule_and_runs_when_required(self) -> None:
        rule = "rule: pkg/AGENTS.md:7"
        good = {"broken_if": "b", "checks": [{"question": "q", "means": "execute", "source": "catalog: L1"},
                                             {"question": "r", "means": "read", "source": "pkg/AGENTS.md:7"}]}
        self.assertEqual(design.check_bind(good, CATALOG["L1"], [rule]), [])
        bad = {"broken_if": " ", "checks": [{"question": "q", "means": "read", "source": "L1"}]}
        self.assertEqual(design.check_bind(bad, CATALOG["L1"], [rule]), [
            "`broken_if` is empty",
            (f"attached rules ['{rule}'] are asked by no check; give each its own check, so its observations stay apart "
            "from the value's"),
            ("this perspective is decided by a run; give an `execute` check naming the input to run and the result that "
            "would show the value lowered")])


class CatalogTest(unittest.TestCase):
    def test_the_repository_catalog_loads_and_covers_by_construction(self) -> None:
        catalog = design.sweep.read_catalog()
        self.assertEqual(design.sweep.catalog_problems(catalog), [])
        self.assertTrue(all(p.sources for p in catalog.values()))

    def test_a_catalog_that_leaves_a_kind_unjudged_is_refused(self) -> None:
        partial = {"L1": entry("L1", "low", ["returned_value"], execute=True), "H2": entry("H2", "high", ["structure"])}
        problems = design.sweep.catalog_problems(partial)
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("change kinds ['stored_data', "), problems)
        self.assertTrue(problems[1].startswith("no `execute` perspective picks `external_contract`"))


def step(body: dict) -> str:
    return body["response_format"]["json_schema"]["name"]


BIND = {"broken_if": "b", "checks": [{"question": "q", "means": "execute", "source": "L1"}]}


def respond_validly(body: dict) -> str:
    return json.dumps({"srv-changes": valid_changes(), "srv-bind": BIND}[step(body)])


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
        self.catalog = fixtures.write_catalog(root / "perspectives")
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
            "--units", str(self.units), "--diff", str(self.diff), "--repo", str(self.repo), "--catalog", str(self.catalog),
            "--context", str(self.context), "--out", str(self.out),
            "--base-url", f"http://127.0.0.1:{self.server.server_port}/v1", "--model", "fake",
        ]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = design.main(argv)
        self.stderr = stderr.getvalue()
        return code

    def test_change_sets_then_pick_bind_and_cut_by_depth(self) -> None:
        self.assertEqual(self.run_design(), 0)
        self.assertEqual(sorted(step(b) for b in FakeEndpoint.requests), ["srv-bind", "srv-changes", "srv-changes"],
                         "no structural change picks H2, and no rule needs a call")
        unit_body = next(b for b in FakeEndpoint.requests if step(b) == "srv-changes")
        self.assertEqual(unit_body["response_format"]["json_schema"]["schema"], design.CHANGES_SCHEMA)
        self.assertRegex(unit_body["messages"][1]["content"], r"@@ [^\n]*@@[^\n]*  \[H1\]")
        for body in FakeEndpoint.requests:
            self.assertTrue(body["messages"][1]["content"].startswith("# Repository context of this review"),
                            "every request starts with the shared pack, so the server reuses its prefix")
        bind = next(b for b in FakeEndpoint.requests if step(b) == "srv-bind")["messages"][1]["content"]
        self.assertIn("- L1 title L1 (low): value of db. Picked when: when L1.", bind)
        self.assertIn("Decided by a run.", bind)
        self.assertIn("- U-2/E-1 [returned_value] s: b -> a (pkg/store.py)", bind)
        perspectives = json.loads((self.out / "perspectives.json").read_text(encoding="utf-8"))
        self.assertEqual([(p["id"], p["catalog"], p["depth"], p["breadth"], p["checks"][0]["source"], p["value"])
                          for p in perspectives["perspectives"]],
                         [("K-1", "L1", "low", ["U-1/E-1", "U-2/E-1"], "L1", "value of db")])
        self.assertEqual(perspectives["unpicked"], [{"catalog": "H2", "reason": "no change is picked by structure"}])
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual((summary["depths"], summary["perspectives_ok"]), ({"high": 0, "low": 1}, True))

    def test_a_tag_picks_a_perspective_and_a_scoped_rule_binds_only_the_tasks_under_it(self) -> None:
        fixtures.write_catalog(self.catalog, {"L6": ("low", "query", False, "value of L6")})
        rule = "rule: docs/AGENTS.md:1"

        def respond(body: dict) -> str:
            name, user = step(body), body["messages"][1]["content"]
            if name == "srv-changes":
                tagged = valid_changes()
                if "docs/a.md" in user.split("# Unit files at the head", 1)[1]:
                    tagged["changes"][0]["tags"] = ["query"]
                return json.dumps({**tagged, "rules": [{"source": rule, "text": "Docs state the contract."}]})
            if name == "srv-rules":
                return json.dumps({"rules": [{"rule": rule, "perspectives": ["L1", "L6"], "reason": "r"}]})
            source = "L6" if "- L6 title" in user else "L1"
            checks = [{"question": "q", "means": "execute", "source": source}]
            if "- rule: docs/AGENTS.md:1: Docs state the contract." in user:
                checks.append({"question": "r", "means": "read", "source": rule})
            return json.dumps({"broken_if": "b", "checks": checks})

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_design(), 0)
        self.assertEqual(sorted(step(b) for b in FakeEndpoint.requests),
                         ["srv-bind", "srv-bind", "srv-changes", "srv-changes", "srv-rules"])
        perspectives = {p["catalog"]: p for p in json.loads((self.out / "perspectives.json").read_text())["perspectives"]}
        self.assertEqual(perspectives["L6"]["breadth"], ["U-1/E-1"], "the tag picks the docs change only")
        self.assertEqual(perspectives["L6"]["rules"], [{"rule": rule, "text": "Docs state the contract."}])
        self.assertEqual(perspectives["L1"]["breadth"], ["U-1/E-1", "U-2/E-1"])
        self.assertEqual([c["source"] for c in perspectives["L1"]["checks"]], ["L1", rule])

    def test_each_low_task_is_bound_to_its_own_changes(self) -> None:
        # Run 14b bound one `broken_if` per perspective and copied it to every task, so tasks judged changes their
        # `broken_if` did not name.
        breadths = {}

        def respond(body: dict) -> str:
            name, user = step(body), body["messages"][1]["content"]
            if name == "srv-changes":
                many = {"changes": [{**change(f"E-{n}"), "hunks": ["H1"]} for n in range(1, 6)], "behaviour_free": [], "rules": []}
                return json.dumps(many)
            listed = [line.split(" ", 2)[1] for line in user.split("# Changes in its breadth", 1)[1].splitlines() if line.startswith("- U-")]
            breadths.setdefault(len(breadths), listed)
            return json.dumps({"broken_if": "b " + ",".join(listed), "checks": [{"question": "q", "means": "execute", "source": "L1"}]})

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_design(), 0)
        perspectives = json.loads((self.out / "perspectives.json").read_text())["perspectives"]
        self.assertEqual([len(p["breadth"]) for p in perspectives], [design.LOW_BREADTH_MAX, 10 - design.LOW_BREADTH_MAX])
        for p in perspectives:
            self.assertEqual(p["broken_if"], "b " + ",".join(p["breadth"]), "each task's binding saw its own changes only")

    def test_uncovered_answer_is_sent_back_with_its_problems(self) -> None:
        calls = []

        def respond(body: dict) -> str:
            calls.append(body)
            if step(body) != "srv-changes":
                return respond_validly(body)
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
        self.assertNotIn("srv-bind", [step(b) for b in FakeEndpoint.requests],
                         "perspectives over a partial change set would leave the missing unit's changes unjudged")

    def test_perspectives_that_leave_a_unit_unjudged_fail_and_keep_the_change_sets(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: json.dumps(valid_changes() if step(body) == "srv-changes" else {"checks": []}))
        self.assertEqual(self.run_design(), 1)
        self.assertIn("no valid perspective set", self.stderr)
        FakeEndpoint.requests = []
        FakeEndpoint.respond = staticmethod(respond_validly)
        self.assertEqual(self.run_design(), 0)
        self.assertEqual(sorted(step(b) for b in FakeEndpoint.requests), ["srv-bind"], "valid change sets are reused")

    def test_diff_that_is_not_the_plan_source_is_rejected(self) -> None:
        self.diff.write_text(DIFF + "diff --git a/x b/x\n", encoding="utf-8")
        self.assertEqual(self.run_design(), 2)
        self.assertEqual(FakeEndpoint.requests, [])


if __name__ == "__main__":
    unittest.main()
