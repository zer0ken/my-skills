"""Pin the srv reviewer jail: what an omp session can reach, and how its event stream becomes an answer.

The jail tests run a stand-in for omp, a shell script that probes the jail from inside and prints its findings as
the final assistant message, so they need bwrap but neither omp nor a model.
"""
import argparse
import http.server
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location("srv_reviewer", Path(__file__).with_name("reviewer.py"))
assert SPEC and SPEC.loader
reviewer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reviewer
SPEC.loader.exec_module(reviewer)


def event(kind: str, **fields) -> str:
    return json.dumps({"type": kind, **fields})


def assistant(text: str, stop: str = "stop", **usage) -> str:
    return event("message_end", message={"role": "assistant", "stopReason": stop, "usage": usage,
                                          "content": [{"type": "text", "text": text}]})


class EventsTest(unittest.TestCase):
    def test_the_answer_is_the_last_assistant_text_and_usage_is_summed(self) -> None:
        stream = "\n".join([
            event("session"), assistant("", "toolUse", input=100, cacheRead=50, output=5),
            event("tool_execution_start", toolName="read", args={"path": "/work/a.py"}),
            assistant('```json\n{"findings": []}\n```', input=200, output=7),
        ])
        content, usage, finish, tools = reviewer.read_events(stream)
        self.assertEqual(content, '{"findings": []}', "a ```json fence around the answer is not part of it")
        self.assertEqual(usage, {"prompt_tokens": 350, "completion_tokens": 12, "tool_calls": 1})
        self.assertEqual((finish, tools), ("stop", [{"tool": "read", "args": {"path": "/work/a.py"}}]))

    def test_the_answer_is_the_json_object_the_text_ends_with(self) -> None:
        self.assertEqual(reviewer.answer_object('검토를 마쳤다. {"a": 1} 다음이 답이다:\n{"findings": [], "checked": [{"x": "}"}]}'),
                         '{"findings": [], "checked": [{"x": "}"}]}')
        self.assertEqual(reviewer.answer_object('```json\n{"a": 1}\n```'), '{"a": 1}')
        self.assertEqual(reviewer.answer_object("no json here"), "no json here", "the caller reports what is not JSON")

    def test_a_session_that_ends_on_an_error_has_no_answer(self) -> None:
        stream = event("message_end", message={"role": "assistant", "stopReason": "error", "errorMessage": "HTTP 500",
                                               "content": []})
        with self.assertRaisesRegex(ValueError, "HTTP 500"):
            reviewer.read_events(stream)
        with self.assertRaisesRegex(ValueError, "no final assistant message"):
            reviewer.read_events(event("session"))


class Upstream(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"model-server"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        del format, args


# Runs in place of omp inside the jail. Each line of the report is one property of the jail, measured from inside.
PROBE = r"""#!/bin/sh
cat > /dev/null
python3 -I - "$@" <<'PY' > /tmp/report.json
import json, os, socket, subprocess, sys, urllib.request
report = {}
def reach(url):
    try:
        return urllib.request.urlopen(url, timeout=3).read().decode()
    except Exception as error:
        return type(error).__name__
report["model_via_relay"] = reach("http://127.0.0.1:18000/")
report["host_loopback"] = reach("http://127.0.0.1:%s/" % os.environ.get("SRV_TEST_PORT", "1"))
report["cwd"] = [os.getcwd(), sorted(os.listdir("."))]
try:
    open("/work/app.txt", "a").close()
    report["head_writable"] = True
except OSError:
    report["head_writable"] = False
report["secret"] = os.environ.get("SRV_TEST_SECRET")
report["home_listing"] = os.path.exists(os.path.expanduser("~hrlee"))
report["args"] = sys.argv[1:]
if os.path.exists("/opt/srv/sandbox.py"):
    script = "python3 -I -c \"import socket; s=socket.socket(socket.AF_UNIX); s.connect('/relay/model.sock')\""
    out = "/tmp/run"
    code = subprocess.run(["/usr/bin/python3", "-I", "/opt/srv/sandbox.py", "--repo", "/work", "--files",
                           "/opt/srv/tracked.txt", "--out", out, "--", "/bin/sh", "-c", script]).returncode
    report["sandbox_relay"] = [code, open(out + "/stderr.txt").read()[-200:]]
    code = subprocess.run(["/usr/bin/python3", "-I", "/opt/srv/sandbox.py", "--repo", "/work", "--files",
                           "/opt/srv/tracked.txt", "--out", out, "--", "/bin/sh", "-c", "cat app.txt"]).returncode
    report["sandbox_head"] = [code, open(out + "/stdout.txt").read()]
print(json.dumps(report))
PY
python3 -I -c 'import json; print(json.dumps({"type": "message_end", "message": {"role": "assistant", "stopReason": "stop", "usage": {}, "content": [{"type": "text", "text": open("/tmp/report.json").read()}]}}))'
"""


class ToolsTest(unittest.TestCase):
    def test_the_design_session_reads_and_every_review_session_can_also_run(self) -> None:
        options = argparse.Namespace(model="m", reasoning_effort="high", timeout=60)
        design = reviewer.omp_arguments(options, "s", reviewer.DESIGN_TOOLS)
        self.assertEqual(design[design.index("--tools") + 1], "read,grep,glob")
        self.assertNotIn("/opt/srv/sandbox_tool.ts", design, "the design session builds yardsticks and runs nothing")
        review = reviewer.omp_arguments(options, "s", reviewer.REVIEW_TOOLS)
        self.assertEqual(review[review.index("--tools") + 1], "read,grep,glob,sandbox_run")
        self.assertIn("/opt/srv/sandbox_tool.ts", review)


class AdmissionTest(unittest.TestCase):
    def test_sessions_fit_the_free_thread_budget(self) -> None:
        # The user's process limit counts threads; a session past it fails at start (EAGAIN), so the jail admits only
        # what fits, keeping a fifth of the free threads for the user's other work.
        with mock.patch.object(reviewer.resource, "getrlimit", return_value=(8192, 8192)), \
             mock.patch.object(reviewer, "user_threads", return_value=1292):
            self.assertEqual(reviewer.session_slots(), (8192 - 1292) * 4 // 5 // reviewer.THREADS_PER_SESSION)
        with mock.patch.object(reviewer.resource, "getrlimit", return_value=(8192, 8192)), \
             mock.patch.object(reviewer, "user_threads", return_value=8000):
            self.assertEqual(reviewer.session_slots(), 1, "a full budget still admits one session, one at a time")


class RelayTest(unittest.TestCase):
    def test_a_failed_connect_does_not_stop_the_relay(self) -> None:
        # In the first full run the accept loop ended while 29 sessions waited; every later connection then stayed
        # in the accept queue. One failed upstream connect must cost only its own connection.
        with tempfile.TemporaryDirectory() as tmp:
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(f"{tmp}/s")
            listener.listen(8)
            attempts = []

            def connect():
                attempts.append(1)
                if len(attempts) == 1:
                    raise ConnectionRefusedError("first upstream refused")
                server, peer = socket.socketpair()
                threading.Thread(target=lambda: (server.sendall(server.recv(5)), server.close()), daemon=True).start()
                return peer

            errors: list[str] = []
            threading.Thread(target=reviewer.serve, args=(listener, connect, errors), daemon=True).start()
            for expected in (b"", b"hello"):
                client = socket.socket(socket.AF_UNIX)
                client.settimeout(5)
                client.connect(f"{tmp}/s")
                if expected:
                    client.sendall(expected)
                self.assertEqual(client.recv(5), expected)
                client.close()
            listener.close()
        self.assertEqual(errors, ["relay: upstream connect failed: first upstream refused"])

    def test_the_upstream_connection_has_no_read_timeout(self) -> None:
        # A model may stay silent for minutes while it reasons; a read timeout would cut the answer off.
        server = socket.create_server(("127.0.0.1", 0))
        jail = reviewer.Jail.__new__(reviewer.Jail)
        jail.upstream = server.getsockname()
        upstream = jail.connect_upstream()
        self.assertIsNone(upstream.gettimeout())
        upstream.close()
        server.close()


@unittest.skipUnless(shutil.which("bwrap"), "the jail needs bubblewrap")
class JailTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "head"
        self.repo.mkdir()
        (self.repo / "app.txt").write_text("head\n", encoding="utf-8")
        for command in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "h"]):
            subprocess.run(["git", "-C", str(self.repo), *command], check=True)
        self.fake = root / "omp"
        self.fake.write_text(PROBE, encoding="utf-8")
        self.fake.chmod(0o755)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.options = argparse.Namespace(
            repo=str(self.repo), base_url=f"http://127.0.0.1:{self.server.server_port}/v1", model="m",
            api_key_env=None, max_tokens=100, reasoning_effort="", timeout=60, sandbox_ro=[],
        )
        os.environ["SRV_TEST_SECRET"] = "token"
        os.environ["SRV_TEST_PORT"] = str(self.server.server_port)

    def tearDown(self) -> None:
        del os.environ["SRV_TEST_SECRET"], os.environ["SRV_TEST_PORT"]
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def probe(self, tools: tuple[str, ...]) -> dict:
        which = shutil.which
        fake = mock.patch.object(reviewer.shutil, "which", lambda name: str(self.fake) if name == "omp" else which(name))
        with fake, reviewer.Jail(self.options) as jail:
            content, _usage, _finish = jail.call([{"role": "user", "content": "q"}], self.options, {}, "t", tools=tools)
        return json.loads(content)

    def test_the_session_reaches_only_the_model_and_reads_the_head(self) -> None:
        report = self.probe(reviewer.DESIGN_TOOLS)
        self.assertEqual(report["model_via_relay"], "model-server", "the relay is the session's way to the model")
        self.assertNotEqual(report["host_loopback"], "model-server",
                            "the session has its own network namespace: the host's loopback is not reachable")
        self.assertEqual(report["cwd"], ["/review", []],
                         "omp discovers extensions and rules from its cwd, so the cwd must be empty and not the head")
        self.assertFalse(report["head_writable"])
        self.assertIsNone(report["secret"], "the caller's environment, tokens included, is cleared")
        self.assertFalse(report["home_listing"])
        self.assertIn("--no-extensions", report["args"])
        self.assertNotIn("sandbox_run", report["args"][report["args"].index("--tools") + 1])

    def test_a_counterexample_run_cannot_reach_the_relay_and_starts_from_the_head(self) -> None:
        report = self.probe(reviewer.REVIEW_TOOLS)
        code, stderr = report["sandbox_relay"]
        self.assertNotEqual(code, 0, "code run by sandbox_run must not reach the model relay")
        self.assertTrue("FileNotFoundError" in stderr or "ConnectionRefusedError" in stderr, stderr)
        self.assertEqual(report["sandbox_head"], [0, "head\n"])
        self.assertIn("sandbox_run", report["args"][report["args"].index("--tools") + 1])


if __name__ == "__main__":
    unittest.main()
