"""Pin srv round 1: one call per (unit, perspective), validation and one retry, anchors, coverage."""

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
        status = 200
        if isinstance(reply, dict):  # a raw response: {"status": ..., "payload": ...}
            status, payload = reply["status"], json.dumps(reply["payload"])
        else:
            content, finish_reason = reply if isinstance(reply, tuple) else (reply, "stop")
            choice = {"message": {"content": content}, "finish_reason": finish_reason}
            payload = json.dumps({"choices": [choice], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload.encode())

    def log_message(self, format, *args) -> None:
        pass


def task_of(body: dict) -> str:
    """`<unit>__<perspective>` from the user message of a request."""
    user = body["messages"][1]["content"]
    perspective = user.split("# Perspective: ", 1)[1].split("\n", 1)[0]
    unit = user.split("# Unit ", 1)[1].split(" ", 1)[0]
    return f"{unit}__{perspective}"


class SweepTest(unittest.TestCase):
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
        self.perspectives = root / "perspectives"
        self.perspectives.mkdir()
        (self.perspectives / "trace.md").write_text("---\nmatch: always\n---\n1. Trace the requirement.\n", encoding="utf-8")
        (self.perspectives / "db.md").write_text("---\nmatch-line: \\bSELECT\\b\n---\n1. Check queries.\n", encoding="utf-8")
        self.diff = root / "diff.patch"
        self.diff.write_text(DIFF, encoding="utf-8")
        plan = sweep.plan_units.plan_units(DIFF, perspectives=sweep.plan_units.read_perspectives(self.perspectives))
        self.units = root / "units.json"
        self.units.write_text(json.dumps(plan), encoding="utf-8")
        self.requirement = root / "issue.md"
        self.requirement.write_text("Load rows.\n", encoding="utf-8")
        self.out = root / "round-1"
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeEndpoint)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        FakeEndpoint.requests = []
        FakeEndpoint.respond = staticmethod(lambda body: answer())

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def run_sweep(self, *extra: str) -> int:
        argv = [
            "--units", str(self.units), "--diff", str(self.diff), "--repo", str(self.repo),
            "--perspectives", str(self.perspectives), "--requirements", str(self.requirement),
            "--out", str(self.out), "--base-url", f"http://127.0.0.1:{self.server.server_port}/v1",
            "--model", "fake", "--max-concurrency", "4", "--samples", "1", *extra,
        ]
        with contextlib.redirect_stderr(io.StringIO()):
            return sweep.main(argv)

    def read(self, name: str) -> dict:
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def test_one_call_per_task_and_coverage_passes(self) -> None:
        self.assertEqual(self.run_sweep(), 0)
        tasks = sorted(task_of(body) for body in FakeEndpoint.requests)
        self.assertEqual(tasks, ["U-1__trace", "U-2__db", "U-2__trace"])
        summary = self.read("summary.json")
        self.assertEqual((summary["tasks"], summary["ok"], summary["failed"]), (3, 3, []))
        self.assertEqual(self.read("progress.json")["done"], 3)
        body = FakeEndpoint.requests[0]
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertEqual(body["response_format"]["json_schema"]["schema"], sweep.FINDINGS_SCHEMA)

    def test_samples_are_independent_calls_pooled_per_task(self) -> None:
        def respond(body: dict) -> str:
            finding = {"id": "F-1", "severity": "NIT", "file": "pkg/store.py", "line": 2,
                       "anchor": "query = 'SELECT 1'", "condition": "c", "evidence": "e", "fix": "f"}
            return answer([finding]) if task_of(body) == "U-2__db" else answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep("--samples", "3"), 0)
        self.assertEqual(sorted(task_of(b) for b in FakeEndpoint.requests).count("U-2__db"), 3, "each sample is its own call")
        result = self.read("U-2__db.json")
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
            return "{}" if task == "U-1__trace" and first else answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep("--samples", "2"), 1)
        result = self.read("U-1__trace.json")
        self.assertFalse(result["ok"], "one unreviewed sample leaves the task's pooled review incomplete")
        self.assertNotIn("findings", result)
        self.assertTrue(any(error.startswith("sample ") for error in result["errors"]))
        self.assertEqual(self.read("summary.json")["failed"], ["U-1__trace"])

    def test_request_carries_numbered_head_lines_and_callers(self) -> None:
        self.run_sweep()
        user = next(b for b in FakeEndpoint.requests if task_of(b) == "U-2__db")["messages"][1]["content"]
        self.assertIn("    2|     query = 'SELECT 1'", user)
        self.assertIn("pkg/api.py:3:load([])", user)
        self.assertIn("1. Check queries.", user)
        self.assertNotIn("match-line", user)

    def test_finding_line_is_re_located_from_its_anchor(self) -> None:
        finding = {"id": "F-1", "severity": "MAJOR", "file": "pkg/store.py", "line": 9,
                   "anchor": "query = 'SELECT 1'", "condition": "c", "evidence": "e", "fix": "f"}
        FakeEndpoint.respond = staticmethod(lambda body: answer([finding]) if task_of(body) == "U-2__db" else answer())
        self.assertEqual(self.run_sweep(), 0)
        anchored = self.read("U-2__db.json")["findings"][0]
        self.assertEqual((anchored["line"], anchored["anchor_status"], anchored["reported_line"]), (2, "moved", 9))
        self.assertEqual(self.read("summary.json")["findings_by_severity"]["MAJOR"], 1)

    def test_invalid_answer_is_retried_once(self) -> None:
        calls: dict[str, int] = {}

        def respond(body: dict) -> str:
            task = task_of(body)
            calls[task] = calls.get(task, 0) + 1
            return "not json" if task == "U-1__trace" and calls[task] == 1 else answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep(), 0)
        result = self.read("U-1__trace.json")
        self.assertEqual(result["attempts"], 2)
        self.assertTrue(result["errors"][0].startswith("sample 1: attempt 1: content is not JSON"))

    def test_enclosing_names_walk_out_to_the_top_level(self) -> None:
        lines = ["class Store:", "    x = 1", "", "    def load(self):", "        if True:", "            return 1", "def other():", "    pass"]
        self.assertEqual(sweep.enclosing_names(lines, 6), ["load", "Store"])
        self.assertEqual(sweep.enclosing_names(lines, 4), ["load", "Store"])
        self.assertEqual(sweep.enclosing_names(lines, 8), ["other"])
        self.assertEqual(sweep.enclosing_names(lines, 99), [])

    def test_answer_cut_at_max_tokens_is_not_retried(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: ('{"findings": [', "length") if task_of(body) == "U-1__trace" else answer())
        self.assertEqual(self.run_sweep("--max-tokens", "100"), 1)
        result = self.read("U-1__trace.json")
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
            if task == "U-1__trace":
                return {"status": 200, "payload": {"choices": []}}
            if task == "U-2__db":
                return {"status": 400, "payload": {"error": {"message": "maximum context length is 1000 tokens"}}}
            return answer()

        FakeEndpoint.respond = staticmethod(respond)
        self.assertEqual(self.run_sweep(), 1)
        self.assertEqual(self.read("summary.json")["failed"], ["U-1__trace", "U-2__db"])
        self.assertIn("not a chat completion", self.read("U-1__trace.json")["errors"][0])
        self.assertIn("HTTP 400", self.read("U-2__db.json")["errors"][0])
        self.assertIn("maximum context length is 1000 tokens", self.read("U-2__db.json")["errors"][0],
                      "the server's body names the cause; without it the operator cannot fix the task")

    def test_output_from_another_diff_does_not_count(self) -> None:
        self.assertEqual(self.run_sweep(), 0)
        stale = self.read("U-2__db.json")
        stale["source_sha256"] = "0" * 64
        (self.out / "U-2__db.json").write_text(json.dumps(stale), encoding="utf-8")
        self.assertEqual(self.run_sweep("--only", "U-1__trace"), 1)
        self.assertEqual(self.read("summary.json")["failed"], ["U-2__db"],
                         "a task file left by a run on another diff is not this plan's review of that task")

    def test_unit_without_perspectives_is_rejected(self) -> None:
        plan = json.loads(self.units.read_text(encoding="utf-8"))
        plan["units"][0]["perspectives"] = {}
        self.units.write_text(json.dumps(plan), encoding="utf-8")
        self.assertEqual(self.run_sweep(), 2)
        self.assertEqual(FakeEndpoint.requests, [], "a unit no task reviews must stop the round before any call")

    def test_line_windows_merge_when_they_touch(self) -> None:
        self.assertEqual(sweep.line_windows([(100, 100), (150, 150), (400, 400)], 420), [(40, 210), (340, 420)])

    def test_empty_checked_list_is_invalid(self) -> None:
        self.assertEqual(sweep.validate_answer(json.loads(answer(checked=[]))),
                         ["`checked` is empty: every checklist item of the perspective needs a row"])

    def test_task_without_valid_output_fails_coverage_until_rerun(self) -> None:
        FakeEndpoint.respond = staticmethod(lambda body: "{}" if task_of(body) == "U-2__db" else answer())
        self.assertEqual(self.run_sweep(), 1)
        self.assertEqual(self.read("summary.json")["failed"], ["U-2__db"])
        FakeEndpoint.requests = []
        FakeEndpoint.respond = staticmethod(lambda body: answer())
        self.assertEqual(self.run_sweep("--only", "U-2__db"), 0)
        self.assertEqual([task_of(b) for b in FakeEndpoint.requests], ["U-2__db"])
        summary = self.read("summary.json")
        self.assertEqual((summary["tasks"], summary["ok"], summary["failed"], summary["this_run_tasks"]), (3, 3, [], 1))

    def test_diff_that_is_not_the_plan_source_is_rejected(self) -> None:
        self.diff.write_text(DIFF + "diff --git a/x b/x\n", encoding="utf-8")
        self.assertEqual(self.run_sweep(), 2)
        self.assertEqual(FakeEndpoint.requests, [])


if __name__ == "__main__":
    unittest.main()
