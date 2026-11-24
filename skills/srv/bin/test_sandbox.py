"""Pin the execution sandbox: nothing the reviewed change could misuse is reachable, and the run is recorded."""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("sandbox", Path(__file__).with_name("sandbox.py"))
assert SPEC and SPEC.loader
sandbox = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sandbox
SPEC.loader.exec_module(sandbox)


@unittest.skipIf(shutil.which("bwrap") is None, "bubblewrap is not installed")
class SandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        (self.repo / "app.txt").write_text("head\n", encoding="utf-8")
        for command in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "head"]):
            subprocess.run(["git", "-C", str(self.repo), *command], check=True)
        (self.repo / ".env").write_text("TOKEN=untracked\n", encoding="utf-8")
        self.out = root / "run"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_in_sandbox(self, script: str, *extra: str) -> int:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = sandbox.main(["--repo", str(self.repo), "--out", str(self.out), *extra, "--", "sh", "-c", script])
        self.stderr = stderr.getvalue()
        return code

    def test_the_host_network_is_unreachable(self) -> None:
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        try:
            code = self.run_in_sandbox(
                f"python3 -c \"import socket; socket.create_connection(('127.0.0.1', {port}), timeout=2)\""
            )
        finally:
            server.close()
        self.assertNotEqual(code, 0, "a listener on the host's loopback must not be reachable from the sandbox")
        self.assertIn("ConnectionRefusedError", (self.out / "stderr.txt").read_text(),
                      "the run must fail at the connection, not before it (a missing interpreter proves nothing)")
        self.assertTrue(json.loads((self.out / "run.json").read_text())["started"])

    def test_the_callers_environment_is_dropped(self) -> None:
        os.environ["SRV_SANDBOX_SECRET"] = "token"
        try:
            self.assertEqual(self.run_in_sandbox("test -z \"$SRV_SANDBOX_SECRET\""), 0)
        finally:
            del os.environ["SRV_SANDBOX_SECRET"]

    def test_home_and_daemon_sockets_are_absent(self) -> None:
        home = str(Path.home())
        self.assertEqual(self.run_in_sandbox(f"! test -e '{home}' && ! test -e /run && ! test -e /var/run/docker.sock"), 0)

    def test_the_run_writes_to_a_copy_of_the_tracked_files(self) -> None:
        self.assertEqual(self.run_in_sandbox("cat app.txt && ! test -e .env && echo changed > app.txt"), 0)
        self.assertEqual((self.repo / "app.txt").read_text(), "head\n", "the head worktree must not change")
        self.assertEqual((self.out / "stdout.txt").read_text(), "head\n")
        record = json.loads((self.out / "run.json").read_text())
        self.assertEqual((record["exit_code"], record["timed_out"], record["files_copied"]), (0, False, 1))

    def test_the_commands_exit_code_is_returned(self) -> None:
        self.assertEqual(self.run_in_sandbox("exit 3"), 3)

    def test_a_run_past_the_timeout_is_killed(self) -> None:
        self.assertEqual(self.run_in_sandbox("sleep 30", "--timeout", "1"), sandbox.TIMED_OUT)
        self.assertTrue(json.loads((self.out / "run.json").read_text())["timed_out"])

    def test_mounting_the_home_directory_is_refused(self) -> None:
        self.assertEqual(self.run_in_sandbox("true", "--ro", str(Path.home())), sandbox.NOT_STARTED)
        self.assertIn("home directory", self.stderr)
        self.assertFalse((self.out / "run.json").exists(), "a refused mount must not start the run")

    def test_a_prepared_directory_is_mounted_read_only(self) -> None:
        env = Path(self.tmp.name) / "env"
        env.mkdir()
        (env / "tool").write_text("ok\n", encoding="utf-8")
        self.assertEqual(self.run_in_sandbox("cat /opt/env/tool && ! touch /opt/env/x", "--ro", f"{env}:/opt/env"), 0)


if __name__ == "__main__":
    unittest.main()
