"""Pin srv round 1: one call per (unit, designed perspective), validation and one retry, anchors, coverage."""

import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import ClassVar
from unittest import mock

SPEC = importlib.util.spec_from_file_location("sweep", Path(__file__).with_name("sweep.py"))
assert SPEC and SPEC.loader
sweep = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sweep
SPEC.loader.exec_module(sweep)

SOURCE = "def load(rows):\n    query = 'SELECT 1'\n    return rows\n"
CALLER = "from pkg.store import load\n\nload([])\n"
DIFF = (
    "diff --git a/pkg/store.py b/pkg/store.py\n--- a/pkg/store.py\n+++ b/pkg/store.py\n"
    "@@ -1,2 +1,3 @@\n def load(rows):\n+    query = 'SELECT 1'\n     return rows\n"
    "diff --git a/docs/a.md b/docs/a.md\n--- a/docs/a.md\n+++ b/docs/a.md\n@@ -1 +1 @@\n-old\n+new\n"
)


def answer(findings=None, checked=None) -> str:
    return json.dumps(
        {
            "findings": findings or [],
            "checked": checked if checked is not None else [{"item": "1", "location": "pkg/store.py:1", "result": "ok"}],
        }
    )


class FakeEndpoint(http.server.BaseHTTPRequestHandler):
    """Answers chat completions with `respond(request_body) -> content`, and records requests."""

    respond = staticmethod(lambda body: answer())
    requests: ClassVar[list] = []

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeEndpoint.requests.append(body)
        reply = FakeEndpoint.respond(body)
        status, headers = 200, {}
        if isinstance(reply, dict):  # a raw response: {"status": ..., "payload": ..., "headers": {...}}
            status, payload, headers = reply["status"], json.dumps(reply["payload"]), reply.get("headers", {})
        else:
            content, finish_reason = reply if isinstance(reply, tuple) else (reply, "stop")
            choice = {"message": {"content": content}, "finish_reason": finish_reason}
            payload = json.dumps({"choices": [choice], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload.encode())

    def log_message(self, format, *args) -> None:
        pass


def task_of(body: dict) -> str:
    """`change__<perspective>`, the task name, from the user message of a request."""
    user = body["messages"][1]["content"]
    return "change__" + user.split("# Perspective: ", 1)[1].split("\n", 1)[0]


class FakeJail:
    """Stands in for `reviewer.Jail`: each session is one HTTP call to the fake endpoint, so the round's logic is tested
    without omp. `tools` records the tools each session was started with."""

    tools: ClassVar[list[tuple[str, ...]]] = []

    def __init__(self, options, log=None) -> None:
        self.options = options

    def __enter__(self) -> "FakeJail":
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def call(self, messages, options, schema, schema_name, tools=(), label=""):
        FakeJail.tools.append(tuple(tools))
        return sweep.call_model(messages, options, schema, schema_name)


class SweepTest(unittest.TestCase):
    def setUp(self) -> None:
        jail = mock.patch.object(sweep.reviewer, "Jail", FakeJail)
        jail.start()
        self.addCleanup(jail.stop)
        FakeJail.tools = []
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
        (self.values / "trace.md").write_text("1. Trace the requirement.\n", encoding="utf-8")
        (self.values / "db.md").write_text("1. Check queries.\n", encoding="utf-8")
        self.diff = root / "diff.patch"
        self.diff.write_text(DIFF, encoding="utf-8")
        plan = sweep.plan_units.plan_units(DIFF)
        self.units = root / "units.json"
        self.units.write_text(json.dumps(plan), encoding="utf-8")
        self.design = root / "design"
        self.design.mkdir()
        # U-1 is docs/a.md, U-2 is pkg/store.py; the perspective ids name the value each one judges, and `trace`
        # spans both units, since breadth is not bound to the review units.
        for unit in ("U-1", "U-2"):
            self.write_unit(unit)
        self.write_perspectives()
        self.requirement = root / "issue.md"
        self.requirement.write_text("Load rows.\n", encoding="utf-8")
        self.out = root / "round-1"
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeEndpoint)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        FakeEndpoint.requests = []
        FakeEndpoint.respond = staticmethod(lambda body: answer())

    def write_unit(self, unit: str, sha256: str | None = None) -> None:
        design = {
            "unit": unit, "ok": True, "source_sha256": sha256 or hashlib.sha256(DIFF.encode()).hexdigest(),
            "changes": [{"id": "E-1", "kind": "returned_value", "subject": "s", "before": "b", "after": "a", "hunks": ["H1"],
                         "structure": {"alters": False, "what": "w"}}],
            "behaviour_free": [], "rules": [],
        }
        (self.design / f"{unit}.json").write_text(json.dumps(design), encoding="utf-8")

    def write_perspectives(self, depth: str = "low") -> None:
        breadths = {"db": ["U-2/E-1"], "trace": ["U-1/E-1", "U-2/E-1"]}
        design = {
            "ok": True, "source_sha256": hashlib.sha256(DIFF.encode()).hexdigest(),
            "perspectives": [
                {"id": p, "value": f"value of {p}", "sources": [f"catalog: {p}"], "breadth": b, "depth": depth,
                 "checks": [{"question": "c", "means": "execute"}]}
                for p, b in breadths.items()
            ],
            "sources": [],
        }
        (self.design / "perspectives.json").write_text(json.dumps(design), encoding="utf-8")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def run_sweep(self, *extra: str) -> int:
        argv = [
            "--units", str(self.units), "--diff", str(self.diff), "--repo", str(self.repo),
            "--design", str(self.design), "--values", str(self.values), "--requirements", str(self.requirement),
            "--out", str(self.out), "--base-url", f"http://127.0.0.1:{self.server.server_port}/v1",
            "--model", "fake", "--max-concurrency", "4", "--samples", "1", *extra,
        ]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = sweep.main(argv)
        self.stderr = stderr.getvalue()
        return code

    def read(self, name: str) -> dict:
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def test_one_call_per_task_and_coverage_passes(self) -> None:
        self.assertEqual(self.run_sweep(), 0)
        tasks = sorted(task_of(body) for body in FakeEndpoint.requests)
        self.assertEqual(tasks, ["change__db", "change__trace"])
        summary = self.read("summary.json")
        self.assertEqual((summary["tasks"], summary["ok"], summary["failed"]), (2, 2, []))
        self.assertEqual(self.read("progress.json")["done"], 2)
        body = FakeEndpoint.requests[0]
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertEqual(body["response_format"]["json_schema"]["schema"], sweep.FINDINGS_SCHEMA)

    def test_every_review_session_can_read_and_run(self) -> None:
        # How a check is decided belongs to the check; a session of any depth may need to run its counterexample.
        self.write_perspectives(depth="high")
        self.assertEqual(self.run_sweep(), 0)
        self.assertEqual(set(FakeJail.tools), {sweep.reviewer.REVIEW_TOOLS})

    def test_the_request_carries_depth_check_means_and_the_change_files(self) -> None:
        self.write_perspectives(depth="high")
        self.assertEqual(self.run_sweep(), 0)
        user = next(b for b in FakeEndpoint.requests if task_of(b) == "change__trace")["messages"][1]["content"]
        self.assertIn("Depth: high (the value is judged on structure:", user)
        self.assertIn("1. [execute] c", user)
        self.assertIn("# Files of the whole change", user)
        self.assertIn("- pkg/store.py (modified)", user)

    def test_samples_are_independent_calls_pooled_per_task(self) -> None:
        def respond(body: dict) -> str:
            finding = {"id": "F-1", "severity": "NIT", "file": "pkg/store.py", "line": 2,
                       "anchor": "query = 'SELECT 1'", "condition": "c", "evidence": "e", "fix": "f"}
            return answer([finding]) if task_of(body) == "change__db" else answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep("--samples", "3"), 0)
        self.assertEqual(sorted(task_of(b) for b in FakeEndpoint.requests).count("change__db"), 3, "each sample is its own call")
        result = self.read("change__db.json")
        self.assertEqual(result["samples"], 3)
        self.assertEqual([f["sample"] for f in result["findings"]], [1, 2, 3],
                         "pooled findings keep their sample number, because ids from two samples collide")
        self.assertEqual([row["sample"] for row in result["checked"]], [1, 2, 3])
        self.assertEqual(self.read("summary.json")["samples"], 3)

    def test_task_with_a_failed_sample_is_not_valid(self) -> None:
        calls: dict[str, int] = {}
        lock = threading.Lock()

        def respond(body: dict) -> str:
            task = task_of(body)
            with lock:
                calls[task] = calls.get(task, 0) + 1
                # Of a task's four calls, the first three always hold both attempts of one sample.
                first = calls[task] <= 3
            return "{}" if task == "change__trace" and first else answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep("--samples", "2"), 1)
        result = self.read("change__trace.json")
        self.assertFalse(result["ok"], "one unreviewed sample leaves the task's pooled review incomplete")
        self.assertNotIn("findings", result)
        self.assertTrue(any(error.startswith("sample ") for error in result["errors"]))
        self.assertEqual(self.read("summary.json")["failed"], ["change__trace"])
        self.assertIn("and rerun them with --only change__trace;", self.stderr,
                      "the recovery command the operator follows must name the value this script's --only accepts")

    def test_request_carries_numbered_head_lines_and_callers(self) -> None:
        self.run_sweep()
        user = next(b for b in FakeEndpoint.requests if task_of(b) == "change__db")["messages"][1]["content"]
        self.assertIn("    2|     query = 'SELECT 1'", user)
        self.assertIn("pkg/api.py:3:load([])", user)
        self.assertIn("1. Check queries.", user)
        self.assertIn("Value: value of db", user)
        self.assertIn("- U-2/E-1 [returned_value] s: b -> a (hunks U-2/H1)", user)

    def test_a_breadth_spanning_units_carries_the_hunks_of_each(self) -> None:
        # Breadth is the span of changes a yardstick takes, not bound to the review units (user, 2026-11-24, "ㄱㄱ").
        self.run_sweep()
        user = next(b for b in FakeEndpoint.requests if task_of(b) == "change__trace")["messages"][1]["content"]
        self.assertIn("[U-1/H1]", user)
        self.assertIn("[U-2/H1]", user)
        self.assertIn("### docs/a.md", user)
        self.assertIn("### pkg/store.py", user)

    def test_finding_line_is_re_located_from_its_anchor(self) -> None:
        finding = {"id": "F-1", "severity": "MAJOR", "file": "pkg/store.py", "line": 9,
                   "anchor": "query = 'SELECT 1'", "condition": "c", "evidence": "e", "fix": "f"}
        FakeEndpoint.respond = staticmethod(lambda body: answer([finding]) if task_of(body) == "change__db" else answer())
        self.assertEqual(self.run_sweep(), 0)
        anchored = self.read("change__db.json")["findings"][0]
        self.assertEqual((anchored["line"], anchored["anchor_status"], anchored["reported_line"]), (2, "moved", 9))
        self.assertEqual(self.read("summary.json")["findings_by_severity"]["MAJOR"], 1)

    def test_invalid_answer_is_retried_once(self) -> None:
        calls: dict[str, int] = {}

        def respond(body: dict) -> str:
            task = task_of(body)
            calls[task] = calls.get(task, 0) + 1
            return "not json" if task == "change__trace" and calls[task] == 1 else answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep(), 0)
        result = self.read("change__trace.json")
        self.assertEqual(result["attempts"], 2)
        self.assertTrue(result["errors"][0].startswith("sample 1: attempt 1: content is not JSON"))

    def test_refused_call_is_sent_again_until_the_server_answers(self) -> None:
        calls: dict[str, int] = {}
        lock = threading.Lock()
        open_circuit = {"status": 503, "payload": {"error": "No available workers (all circuits open or unhealthy)"}}

        def respond(body: dict):
            task = task_of(body)
            with lock:
                calls[task] = calls.get(task, 0) + 1
                refused = task == "change__trace" and calls[task] <= 3
            return open_circuit if refused else answer()

        FakeEndpoint.respond = staticmethod(respond)
        with mock.patch.object(sweep, "BACKOFF_BASE_S", 0.01):
            self.assertEqual(self.run_sweep(), 0, "a server that refuses for a while must not leave the task unreviewed")
        result = self.read("change__trace.json")
        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 1, "a refused call is a wait, not a used attempt")
        self.assertEqual(calls["change__trace"], 4)
        self.assertEqual(sum(error.startswith("sample 1: refused: HTTP 503") for error in result["errors"]), 3,
                         "each wait is recorded so the procedure log can account for the server's refusals")

    def test_refusal_longer_than_the_window_fails_the_task(self) -> None:
        def respond(body: dict):
            if task_of(body) == "change__trace":
                return {"status": 503, "payload": {"error": "No available workers"}}
            return answer()

        FakeEndpoint.respond = staticmethod(respond)
        with mock.patch.object(sweep, "BACKOFF_BASE_S", 0.01), mock.patch.object(sweep, "REFUSAL_WINDOW_S", 0.2):
            self.assertEqual(self.run_sweep(), 1)
        result = self.read("change__trace.json")
        self.assertFalse(result["ok"])
        self.assertIn("the server refused every call for 0 s, last: HTTP 503", result["errors"][-1])
        self.assertEqual(self.read("summary.json")["failed"], ["change__trace"])

    def test_retry_after_sets_the_wait(self) -> None:
        calls: list[int] = []

        def respond(body: dict):
            if task_of(body) != "change__trace":
                return answer()
            calls.append(1)
            if len(calls) == 1:
                return {"status": 429, "payload": {"error": "queue full"}, "headers": {"Retry-After": "0"}}
            return answer()

        FakeEndpoint.respond = staticmethod(respond)
        with mock.patch.object(sweep, "BACKOFF_BASE_S", 1000.0):  # a jittered wait would take minutes
            self.assertEqual(self.run_sweep(), 0)
        self.assertIn("sent again after 0.0 s", self.read("change__trace.json")["errors"][0])

    def test_closed_port_is_a_refusal(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            closed = probe.getsockname()[1]
        with mock.patch.object(sweep, "BACKOFF_BASE_S", 0.01), mock.patch.object(sweep, "REFUSAL_WINDOW_S", 0.2):
            code = self.run_sweep("--base-url", f"http://127.0.0.1:{closed}/v1")
        self.assertEqual(code, 1)
        errors = self.read("change__trace.json")["errors"]
        self.assertTrue(errors[0].startswith("sample 1: refused: connection failed"), errors[0])
        self.assertIn("the server refused every call", errors[-1])

    def test_enclosing_names_walk_out_to_the_top_level(self) -> None:
        lines = ["class Store:", "    x = 1", "", "    def load(self):", "        if True:", "            return 1", "def other():", "    pass"]
        self.assertEqual(sweep.enclosing_names(lines, 6), ["load", "Store"])
        self.assertEqual(sweep.enclosing_names(lines, 4), ["load", "Store"])
        self.assertEqual(sweep.enclosing_names(lines, 8), ["other"])
        self.assertEqual(sweep.enclosing_names(lines, 99), [])

    def test_answer_cut_at_max_tokens_is_not_retried(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: ('{"findings": [', "length") if task_of(body) == "change__trace" else answer())
        self.assertEqual(self.run_sweep("--max-tokens", "100"), 1)
        result = self.read("change__trace.json")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(
            result["errors"],
            [
                (
                    "sample 1: attempt 1: the answer stopped at --max-tokens 100 (finish_reason length); "
                    "reasoning tokens count toward it, so rerun the task with a larger --max-tokens"
                )
            ],
        )

    def test_large_file_is_shown_around_its_changes(self) -> None:
        big = "".join(f"line {n} " + "x" * 200 + "\n" for n in range(1, 401))
        (self.repo / "pkg" / "store.py").write_text(big, encoding="utf-8")
        change = sweep.plan_units.parse_diff(
            "diff --git a/pkg/store.py b/pkg/store.py\n--- a/pkg/store.py\n+++ b/pkg/store.py\n@@ -199,0 +200,1 @@\n+line 200\n"
        )[0]
        unit = {"files": [{"path": "pkg/store.py", "status": "modified"}]}
        text = sweep.numbered_head_files(self.repo, {"pkg/store.py": change}, unit)
        self.assertIn("(only the lines around its changes; the file has 400 lines)", text)
        self.assertIn("  140| line 140 ", text)
        self.assertIn("  260| line 260 ", text)
        self.assertNotIn("  139| ", text)
        self.assertNotIn("  261| ", text)

    def test_unit_shows_whole_files_smallest_first_within_its_budget(self) -> None:
        small = "".join(f"s{n}\n" for n in range(1, 11))
        big = "".join(f"line {n} " + "x" * 200 + "\n" for n in range(1, 401))
        (self.repo / "pkg" / "small.py").write_text(small, encoding="utf-8")
        (self.repo / "pkg" / "store.py").write_text(big, encoding="utf-8")
        changes = {
            path: sweep.plan_units.parse_diff(f"diff --git a/{path} b/{path}\n--- a\n+++ b\n@@ -199,0 +200,1 @@\n+x\n")[0]
            for path in ("pkg/store.py", "pkg/small.py")
        }
        unit = {"files": [{"path": "pkg/store.py", "status": "modified"}, {"path": "pkg/small.py", "status": "modified"}]}
        with mock.patch.object(sweep, "HEAD_CHARS_PER_UNIT", 50_000):
            text = sweep.numbered_head_files(self.repo, changes, unit)
        self.assertIn("### pkg/small.py\n    1| s1", text, "a small file fits the unit budget and is shown whole")
        self.assertIn("### pkg/store.py (only the lines around its changes; the file has 400 lines)", text,
                      "a file that would push the unit past HEAD_CHARS_PER_UNIT is cut to its changed lines, so the prompt stays bounded")
        self.assertNotIn("  139| ", text)

    def test_broken_responses_fail_their_task_and_the_round_still_reports(self) -> None:
        def respond(body: dict):
            task = task_of(body)
            if task == "change__trace":
                return {"status": 200, "payload": {"choices": []}}
            if task == "change__db":
                return {"status": 400, "payload": {"error": {"message": "maximum context length is 1000 tokens"}}}
            return answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep(), 1)
        self.assertEqual(self.read("summary.json")["failed"], ["change__db", "change__trace"])
        self.assertIn("not a chat completion", self.read("change__trace.json")["errors"][0])
        self.assertIn("HTTP 400", self.read("change__db.json")["errors"][0])
        self.assertIn("maximum context length is 1000 tokens", self.read("change__db.json")["errors"][0],
                      "the server's body names the cause; without it the operator cannot fix the task")

    def test_output_from_another_diff_does_not_count(self) -> None:
        self.assertEqual(self.run_sweep(), 0)
        stale = self.read("change__db.json")
        stale["source_sha256"] = "0" * 64
        (self.out / "change__db.json").write_text(json.dumps(stale), encoding="utf-8")
        self.assertEqual(self.run_sweep("--only", "change__trace"), 1)
        self.assertEqual(self.read("summary.json")["failed"], ["change__db"],
                         "a task file left by a run on another diff is not this plan's review of that task")

    def test_unit_without_a_valid_design_is_rejected(self) -> None:
        self.write_unit("U-1", sha256="0" * 64)
        self.assertEqual(self.run_sweep(), 2)
        self.assertEqual(FakeEndpoint.requests, [], "a unit no perspective covers must stop the round before any call")
        self.assertIn("units ['U-1'] have no valid change set", self.stderr)

    def test_line_windows_merge_when_they_touch(self) -> None:
        self.assertEqual(sweep.line_windows([(100, 100), (150, 150), (400, 400)], 420), [(40, 210), (340, 420)])

    def test_empty_checked_list_is_invalid(self) -> None:
        self.assertEqual(sweep.validate_answer(json.loads(answer(checked=[]))),
                         ["`checked` is empty: every checklist item of the perspective needs a row"])

    def test_task_without_valid_output_fails_coverage_until_rerun(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: "{}" if task_of(body) == "change__db" else answer())
        self.assertEqual(self.run_sweep(), 1)
        self.assertEqual(self.read("summary.json")["failed"], ["change__db"])
        FakeEndpoint.requests = []
        FakeEndpoint.respond = staticmethod(lambda body: answer())
        self.assertEqual(self.run_sweep("--only", "change__db"), 0)
        self.assertEqual([task_of(b) for b in FakeEndpoint.requests], ["change__db"])
        summary = self.read("summary.json")
        self.assertEqual((summary["tasks"], summary["ok"], summary["failed"], summary["this_run_tasks"]), (2, 2, [], 1))

    def test_diff_that_is_not_the_plan_source_is_rejected(self) -> None:
        self.diff.write_text(DIFF + "diff --git a/x b/x\n", encoding="utf-8")
        self.assertEqual(self.run_sweep(), 2)
        self.assertEqual(FakeEndpoint.requests, [])


if __name__ == "__main__":
    unittest.main()
