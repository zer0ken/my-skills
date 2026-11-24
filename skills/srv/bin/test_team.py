"""Tests of team.py: judge from observations, routing, clustering, and the verify rule, with a fake model server."""

import argparse
import http.server
import importlib.util
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


team = load("srv_team", "team.py")
fixtures = load("test_team_fixtures", "test_sweep.py")
FakeEndpoint = fixtures.FakeEndpoint


def perspective(pid: str, breadth: list[str], depth: str = "low") -> dict:
    return {"id": pid, "value": f"value {pid}", "broken_if": f"broken {pid}", "depth": depth, "breadth": breadth,
            "checks": [{"question": "c", "means": "read"}], "sources": ["catalog: db"]}


def finding(fid: str, path: str, line: int, status: str = "exact") -> dict:
    return {"id": fid, "severity": "MAJOR", "file": path, "line": line, "anchor": "x", "anchor_status": status,
            "condition": "c", "evidence": "e", "fix": "f"}


class PureTest(unittest.TestCase):
    def test_findings_close_in_one_file_form_one_cluster(self) -> None:
        groups = team.cluster([finding("a", "f.py", 10), finding("b", "g.py", 11), finding("c", "f.py", 13),
                               finding("d", "f.py", 30)])
        self.assertEqual([[f["id"] for f in g] for g in groups], [["a", "c"], ["d"], ["b"]])

    def test_a_question_goes_to_the_perspectives_whose_breadth_holds_its_target(self) -> None:
        perspectives = [perspective("K-1", ["U-1/E-1"]), perspective("K-2", ["U-1/E-2"]), perspective("K-3", ["U-1/E-2"])]
        results = {"K-1": [{"questions": [{"about": "U-1/E-2", "question": "q"}]}]}
        judgments = {"K-1": {"verdict": "holds"}, "K-2": {"verdict": "holds"}, "K-3": {"verdict": "undecided"}}
        questions = team.route_questions(perspectives, results, judgments)
        self.assertEqual([(q["perspective"], q["question"].startswith("(K-1 의 질문")) for q in questions],
                         [("K-2", True), ("K-3", False), ("K-3", True)],
                         "an undecided perspective gets its own broken_if first, then the routed question")

    def test_a_cluster_is_confirmed_only_when_every_call_confirms_an_anchored_claim(self) -> None:
        yes = {"verdict": "CONFIRMED", "severity": "MAJOR", "reason": "r"}
        no = {"verdict": "REJECTED", "severity": "MINOR", "reason": "r"}
        group = [finding("a", "f.py", 1)]
        self.assertEqual(team.decide_cluster(group, [yes, yes, yes]), ("CONFIRMED", "MAJOR"))
        self.assertEqual(team.decide_cluster(group, [yes, yes, no])[0], "PLAUSIBLE")
        self.assertEqual(team.decide_cluster([finding("a", "f.py", 1, "missing")], [yes, yes, yes])[0], "PLAUSIBLE",
                         "a claim whose line is not at the head is not confirmed by agreement")
        self.assertEqual(team.decide_cluster(group, [no, no, no]), ("REJECTED", "MINOR"))
        self.assertEqual(team.decide_cluster(group, [yes, yes])[0], "PLAUSIBLE", "a failed call leaves it unsettled")

    def test_metrics_are_summed_over_replicas_for_the_model_only(self) -> None:
        values: dict[str, float] = {}
        team.add_metrics(values, 'vllm:prompt_tokens_total{model_name="m",engine="0"} 5\n'
                                 'vllm:prompt_tokens_total{model_name="other",engine="0"} 7\n', "m")
        team.add_metrics(values, 'vllm:prompt_tokens_total{model_name="m",engine="0"} 3\n', "m")
        self.assertEqual(values, {"vllm:prompt_tokens_total": 8.0})

    def test_majority_needs_more_than_half(self) -> None:
        self.assertEqual(team.majority(["broken", "broken", "holds"]), "broken")
        self.assertEqual(team.majority(["broken", "holds", "undecided"]), "undecided")

    def test_a_counter_that_went_down_has_no_delta(self) -> None:
        before = {"vllm:prompt_tokens_total": 10.0, "vllm:generation_tokens_total": 9.0}
        after = {"vllm:prompt_tokens_total": 15.0, "vllm:generation_tokens_total": 3.0}
        self.assertEqual(team.metric_delta(before, after), {"prompt_tokens_total": 5.0})


class ModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeEndpoint)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        FakeEndpoint.requests = []
        self.options = argparse.Namespace(base_url=f"http://127.0.0.1:{self.server.server_port}/v1", model="fake",
                                          max_tokens=1000, reasoning_effort=None, api_key_env=None, timeout=30)
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "q.py").write_text("a = 1\nfilter_one()\nfilter_two()\n", encoding="utf-8")
        for command in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "h"]):
            subprocess.run(["git", "-C", str(self.repo), *command], check=True)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_the_judge_sees_observations_not_the_inspector_conclusion_and_a_broken_value_becomes_a_finding(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: json.dumps({"verdict": "broken", "decisive": [2], "reason": "r"}))
        p = perspective("K-1", ["U-1/E-1"], depth="high")
        results = {"K-1": [{"checked": [{"item": "1", "location": "q.py:1", "result": "one definition"},
                                        {"item": "1", "location": "q.py:2", "result": "the test is written twice"}]}]}
        judgments = team.judge_perspectives([p], results, self.options)
        self.assertEqual(judgments["K-1"]["verdict"], "broken")
        self.assertEqual(len(FakeEndpoint.requests), team.JUDGE_SAMPLES)
        user = FakeEndpoint.requests[0]["messages"][1]["content"]
        self.assertIn("Broken if: broken K-1", user)
        self.assertIn("2. q.py:2: the test is written twice", user)
        found = team.judged_findings({"K-1": p}, judgments, self.repo)
        self.assertEqual((found[0]["id"], found[0]["file"], found[0]["line"], found[0]["anchor"]),
                         ("J-K-1", "q.py", 2, "filter_one()"))

    def test_verify_confirms_only_by_unanimous_calls(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: json.dumps({"verdict": "CONFIRMED", "severity": "BLOCKER", "reason": "r"}))
        clusters = team.verify([finding("a", "q.py", 2)], self.repo, "# pack", {}, self.options)
        self.assertEqual([(c["id"], c["verdict"], c["severity"]) for c in clusters], [("R-001", "CONFIRMED", "BLOCKER")])
        self.assertIn("    2| filter_one()", FakeEndpoint.requests[0]["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
