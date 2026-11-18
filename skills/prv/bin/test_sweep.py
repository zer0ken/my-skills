"""Pin prv's one-call reviewers: citations become code in the request, one call per perspective and sample."""

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

SPEC = importlib.util.spec_from_file_location("prv_sweep", Path(__file__).with_name("sweep.py"))
assert SPEC and SPEC.loader
prv = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prv
SPEC.loader.exec_module(prv)

LONG = "".join(f"line {n} " + "x" * 100 + "\n" for n in range(1, 301))
PLAN = (
    "# Plan\n"
    "Change `merge/emem/store.py:150` so the writer locks first.\n"
    "Keep `emem/small.py` as it is; see `emem/store.py:10-12`.\n"
    "Ignore `missing/none.py:3` and this plan, `plan.md:1`.\n"
)


class Endpoint(http.server.BaseHTTPRequestHandler):
    requests: list = []  # noqa: RUF012 - one list shared by the test server's handler threads

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Endpoint.requests.append(body)
        finding = {"id": "F-1", "severity": "MAJOR", "file": "plan.md", "line": 9,
                   "anchor": "Keep `emem/small.py` as it is; see `emem/store.py:10-12`.",
                   "condition": "c", "evidence": "e", "fix": "f"}
        content = json.dumps({"findings": [finding], "checked": [{"item": "1", "location": "plan.md:2", "result": "ok"}]})
        payload = json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": {}})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload.encode())

    def log_message(self, format, *args) -> None:
        pass


class PrvSweepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        (self.repo / "emem").mkdir(parents=True)
        (self.repo / "emem" / "store.py").write_text(LONG, encoding="utf-8")
        (self.repo / "emem" / "small.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("Root rule.\n", encoding="utf-8")
        (self.repo / "emem" / "AGENTS.md").write_text("Package rule.\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        self.plan = root / "plan.md"
        self.plan.write_text(PLAN, encoding="utf-8")
        self.requirement = root / "issue.md"
        self.requirement.write_text("Lock the writer.\n", encoding="utf-8")
        self.methods = root / "methods"
        self.methods.mkdir()
        (self.methods / "trace.md").write_text("1. Trace the requirement.\n", encoding="utf-8")
        (self.methods / "query.md").write_text("1. Check queries.\n", encoding="utf-8")
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        Endpoint.requests = []

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_citations_resolve_through_checkout_prefixes_and_keep_their_lines(self) -> None:
        cited = prv.find_citations(PLAN, self.repo, {"plan.md"})
        self.assertEqual(cited, {"emem/store.py": [(150, 150), (10, 12)], "emem/small.py": []},
                         "a citation through a checkout name (`merge/`) still names the repository file")

    def test_cited_code_shows_windows_of_long_files_and_short_files_whole(self) -> None:
        text = prv.cited_code(self.repo, {"emem/store.py": [(150, 150)], "emem/small.py": []})
        self.assertIn("### emem/store.py (the lines around the plan's citations; the file has 300 lines)", text)
        self.assertIn("  130| line 130 ", text)
        self.assertIn("  170| line 170 ", text)
        self.assertNotIn("  129| ", text)
        self.assertIn("### emem/small.py\n    1| x = 1", text)

    def test_repository_rules_follow_the_cited_paths(self) -> None:
        text = prv.repository_rules(self.repo, {"emem/store.py": []})
        self.assertLess(text.index("### AGENTS.md"), text.index("### emem/AGENTS.md"))

    def test_one_call_per_perspective_and_sample_with_the_method_last(self) -> None:
        argv = ["--plan", str(self.plan), "--requirements", str(self.requirement), "--repo", str(self.repo),
                "--perspectives", str(self.methods), "--out", str(Path(self.tmp.name) / "out"),
                "--base-url", f"http://127.0.0.1:{self.server.server_port}/v1", "--model", "fake", "--samples", "2"]
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(prv.main(argv), 0)
        self.assertEqual(len(Endpoint.requests), 4, "two perspectives, two samples each")
        self.assertEqual(Endpoint.requests[0]["max_tokens"], 131072,
                         "a plan request is long (139k prompt tokens measured on #1303 r2) and the trace answer stopped at 65,536 "
                         "with reasoning; keep the default that held it instead of lowering it to pass")
        user = Endpoint.requests[0]["messages"][1]["content"]
        self.assertLess(user.index("# The plan: plan.md"), user.index("# Perspective: "),
                        "the plan and code come before the method, so every perspective shares one prompt prefix")
        self.assertIn("  150| line 150 ", user)
        result = json.loads((Path(self.tmp.name) / "out" / "plan__trace.json").read_text(encoding="utf-8"))
        self.assertEqual([(f["anchor_status"], f["line"], f["sample"]) for f in result["findings"]], [("moved", 3, 1), ("moved", 3, 2)],
                         "a finding on the plan is anchored in the plan copy")


if __name__ == "__main__":
    unittest.main()
