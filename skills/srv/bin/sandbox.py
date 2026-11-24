#!/usr/bin/env python3
"""Run one command against a copy of the head in an isolated sandbox, for an execute-depth perspective.

The code under review is untrusted input, so it runs where it reaches nothing it
could misuse: no network (not even the host's loopback or the model server), no
environment from the caller (no tokens), no home directory, no `/run` or `/var`
(so no Docker or other daemon socket), and a writable copy of the head's tracked
files instead of the head worktree itself. The user's words (2026-11-24): "실제
실행도 가능해야돼. 에이전트 하네스를 사용하는데 그걸 못할 이유가 없어"; the
isolation keeps the project rule that the reviewed change never reaches a token
or the host network.

The sandbox is bubblewrap (https://github.com/containers/bubblewrap):
`--unshare-all` gives new user, IPC, PID, network, UTS, and cgroup namespaces, so
only a private loopback exists; `--clearenv` drops every variable; only the system
directories and the paths passed with `--ro` are mounted, read-only.

Dependencies are prepared before, outside the sandbox, without running the
change's own build or install scripts (for example `uv sync --frozen --no-build`,
`npm ci --ignore-scripts`, `cargo fetch`), and mounted with `--ro`.

Usage:
  python3 -I sandbox.py --repo HEAD_WORKTREE --out RUN_DIR [--ro SRC[:DEST] ...] [--timeout S] -- COMMAND ...
The command runs in /work, the copy of the head. RUN_DIR receives stdout.txt,
stderr.txt, and run.json. Exit codes: the command's own, 124 when it ran past
--timeout, 125 when the sandbox could not start or the input is invalid.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SYSTEM_DIRS = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/etc")
SANDBOX_PATH = "/usr/local/bin:/usr/bin:/bin"
SANDBOX_HOME = "/home/sandbox"
FORBIDDEN = ("/run", "/var/run", "/var")
TIMED_OUT, NOT_STARTED = 124, 125


def tracked_files(repo: Path) -> list[str]:
    """The head's tracked paths; the copy holds what the change commits, not local caches or credentials."""
    result = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True)
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def copy_head(repo: Path, work: Path) -> int:
    count = 0
    for relative in tracked_files(repo):
        source = repo / relative
        target = work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            continue  # a submodule or a file deleted from the worktree
        count += 1
    return count


def mount_problem(source: Path) -> str | None:
    """Why `source` must not be mounted, or None. Home and daemon-socket directories hold what the change must not reach."""
    home = Path.home().resolve()
    resolved = source.resolve()
    if resolved == home or home.is_relative_to(resolved):
        return f"{source} is the home directory or contains it, and the home directory holds credentials"
    for forbidden in FORBIDDEN:
        if resolved == Path(forbidden) or resolved.is_relative_to(forbidden) or Path(forbidden).is_relative_to(resolved):
            return f"{source} overlaps {forbidden}, where daemon sockets live"
    return None


def bwrap_command(work: Path, mounts: list[tuple[Path, str]], command: list[str]) -> list[str]:
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
           "--setenv", "PATH", SANDBOX_PATH, "--setenv", "HOME", SANDBOX_HOME, "--setenv", "LANG", "C.UTF-8",
           "--setenv", "TMPDIR", "/tmp"]
    for directory in SYSTEM_DIRS:
        path = Path(directory)
        if path.is_symlink():
            cmd += ["--symlink", os.readlink(path), directory]
        elif path.is_dir():
            cmd += ["--ro-bind", directory, directory]
    cmd += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/home", "--dir", SANDBOX_HOME,
            "--bind", str(work), "/work"]
    for source, dest in mounts:
        cmd += ["--ro-bind", str(source), dest]
    return [*cmd, "--chdir", "/work", "--", *command]


def parse_mount(value: str) -> tuple[Path, str]:
    source, _, dest = value.partition(":")
    return Path(source), dest or str(Path(source).resolve())


def run(options: argparse.Namespace) -> int:
    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    mounts = [parse_mount(value) for value in options.ro]
    for source, _ in mounts:
        problem = mount_problem(source) if source.exists() else f"{source} does not exist"
        if problem:
            print(f"sandbox: --ro {source}: {problem}. Mount the narrower directory the run needs (a toolchain or an "
                  "environment directory), not a parent that also holds credentials or sockets.", file=sys.stderr)
            return NOT_STARTED
    if shutil.which("bwrap") is None:
        print("sandbox: bwrap is not installed; an execute-depth check stays unrun and goes to residual risk", file=sys.stderr)
        return NOT_STARTED
    record: dict = {"command": options.command, "repo": str(options.repo), "mounts": [[str(s), d] for s, d in mounts],
                    "timeout_s": options.timeout}
    with tempfile.TemporaryDirectory(prefix="srv-sandbox-", dir=options.scratch) as scratch:
        work = Path(scratch) / "work"
        work.mkdir()
        record["files_copied"] = copy_head(Path(options.repo), work)
        started = time.monotonic()
        with open(out / "stdout.txt", "wb") as stdout, open(out / "stderr.txt", "wb") as stderr:
            process = subprocess.Popen(bwrap_command(work, mounts, options.command), stdout=stdout, stderr=stderr,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                code = process.wait(timeout=options.timeout)
                record["timed_out"] = False
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                code = TIMED_OUT
                record["timed_out"] = True
        record["seconds"] = round(time.monotonic() - started, 2)
    stderr_text = (out / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    record["exit_code"] = code
    # bwrap reports its own setup failures as `bwrap: ...` and exits 1 before the command runs.
    record["started"] = not (code == 1 and stderr_text.startswith("bwrap:"))
    (out / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("exit_code", "timed_out", "started", "seconds")}), file=sys.stderr)
    return code if record["started"] else NOT_STARTED


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a command on a copy of the head with no network, token, or home.")
    parser.add_argument("--repo", required=True, help="head worktree; its tracked files are copied")
    parser.add_argument("--out", required=True, help="run directory for stdout.txt, stderr.txt, run.json")
    parser.add_argument("--ro", action="append", default=[], help="SRC[:DEST] mounted read-only, such as a prepared environment")
    parser.add_argument("--timeout", type=float, default=300, help="seconds before the run is killed (exit 124)")
    parser.add_argument("--scratch", help="directory for the copy of the head (default: the system temporary directory)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- then the command to run in /work")
    options = parser.parse_args(argv)
    if options.command[:1] == ["--"]:
        options.command = options.command[1:]
    if not options.command:
        parser.error("give the command after --")
    return options


def main(argv: list[str]) -> int:
    try:
        return run(parse_args(argv))
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"sandbox: {error}", file=sys.stderr)
        return NOT_STARTED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
