#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""srv round 1: review every (unit, perspective) task with one structured-output model call.

A task is one review unit of `rv/bin/plan-units.py` and one perspective the unit
plan matched to it. Each task is one request to an OpenAI-compatible endpoint;
all tasks run in parallel, so the round takes about as long as its slowest call.
The request carries everything the reviewer needs: the brief
(`references/brief.md`), the perspective method, the requirement copies, the
unit's hunks, the unit's files at the head with line numbers, and the lines
elsewhere in the head that name a symbol the hunks define or change. The answer
is held to a JSON Schema, validated here, retried once when invalid, and its
finding lines are re-located from their anchors (`anchor-findings.py`).

Coverage is this script's job: it exits 1 when any task has no valid output,
because a task without output is a unit the swarm did not review.

Usage:
  uv run sweep.py --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --perspectives DIR --requirements FILE [FILE ...] --out round-1 \
      --base-url URL --model MODEL [--api-key-env NAME] [--max-concurrency 32]
Exit codes: 0 every task has a valid output, 1 some task failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.client
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
BRIEF_PATH = Path(__file__).resolve().parents[1] / "references" / "brief.md"
SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "NIT")
HEAD_CHARS_PER_UNIT = 60_000
WINDOW_LINES = 60
CALLER_LINES_PER_SYMBOL = 15
CALLER_LINES_TOTAL = 150
SYMBOL_RES = (
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*class\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
)
HUNK_CONTEXT_RE = re.compile(r"^@@[^@]*@@\s*(.*)$")

FINDINGS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["findings", "checked"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "severity", "file", "line", "anchor", "condition", "evidence", "fix"],
                "properties": {
                    "id": {"type": "string"},
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "anchor": {"type": "string"},
                    "condition": {"type": "string"},
                    "evidence": {"type": "string"},
                    "fix": {"type": "string"},
                },
            },
        },
        "checked": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item", "location", "result"],
                "properties": {
                    "item": {"type": "string"},
                    "location": {"type": "string"},
                    "result": {"type": "string"},
                },
            },
        },
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


plan_units = load_module("plan_units", SKILLS / "rv" / "bin" / "plan-units.py")
anchor_findings = load_module("anchor_findings", Path(__file__).resolve().with_name("anchor-findings.py"))


@dataclass(frozen=True)
class Task:
    unit: dict
    perspective: str

    @property
    def name(self) -> str:
        return f"{self.unit['id']}__{self.perspective}"


def list_tasks(plan: dict) -> list[Task]:
    return [Task(unit, perspective) for unit in plan["units"] for perspective in sorted(unit.get("perspectives", {}))]


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[index + 1 :]).lstrip("\n")
    return text


def unit_diff(changes: dict, unit: dict) -> str:
    """The unit's hunks as a unified diff."""
    parts = []
    for file in unit["files"]:
        change = changes[file["path"]]
        parts.append(f"--- a/{change.old_path}\n+++ b/{change.path}  ({change.status})")
        for hunk in change.hunks:
            parts.append(hunk.header)
            parts.extend(hunk.lines)
    return "\n".join(parts)


def numbered_head_files(repo: Path, changes: dict, unit: dict) -> str:
    """Each unit file at the head, every line prefixed with its number.

    Whole files fill at most `HEAD_CHARS_PER_UNIT` characters per unit, smallest
    first; every other file is shown only around its changed lines
    (`WINDOW_LINES` on each side), so the prompt grows with the changed lines,
    not with the size of the files they sit in: on enterprise-memory#1415 two
    whole documents made one request 166k tokens.
    """
    texts = {}
    for file in unit["files"]:
        if file["status"] != "deleted":
            texts[file["path"]] = anchor_findings.head_lines(repo, file["path"])
    whole, used = set(), 0
    for path, lines in sorted(((p, l) for p, l in texts.items() if l is not None), key=lambda item: sum(len(x) + 1 for x in item[1])):
        size = sum(len(line) + 1 for line in lines)
        if used + size <= HEAD_CHARS_PER_UNIT:
            whole.add(path)
            used += size
    parts = []
    for file in unit["files"]:
        if file["status"] == "deleted":
            parts.append(f"### {file['path']} (deleted at the head; see its hunks)")
            continue
        lines = texts[file["path"]]
        if lines is None:
            parts.append(f"### {file['path']} (not readable at the head)")
            continue
        if file["path"] in whole:
            shown = [(1, len(lines))]
            title = f"### {file['path']}"
        else:
            shown = line_windows(changed_line_numbers(changes[file["path"]]), len(lines))
            title = f"### {file['path']} (only the lines around its changes; the file has {len(lines)} lines)"
        blocks = [
            "\n".join(f"{number:>5}| {lines[number - 1]}" for number in range(first, last + 1))
            for first, last in shown
        ]
        parts.append(title + "\n" + "\n  ...\n".join(blocks))
    return "\n\n".join(parts)


def line_windows(line_numbers: list[int], length: int) -> list[tuple[int, int]]:
    """Merged ranges of `WINDOW_LINES` lines around each line number, within 1..length."""
    windows: list[tuple[int, int]] = []
    for number in sorted(set(line_numbers)):
        first, last = max(1, number - WINDOW_LINES), min(length, number + WINDOW_LINES)
        if windows and first <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], max(windows[-1][1], last))
        else:
            windows.append((first, last))
    return windows


def changed_line_numbers(change) -> list[int]:
    """Head line numbers the change touches: each added line, and the place of each removal."""
    numbers: list[int] = []
    for hunk in change.hunks:
        line_no = hunk.new_start
        for line in hunk.lines:
            if line.startswith("+"):
                numbers.append(line_no)
                line_no += 1
            elif line.startswith("-"):
                numbers.append(max(line_no, 1))
            elif line.startswith(" "):
                line_no += 1
    return numbers


def defined_name(line: str) -> str | None:
    for pattern in SYMBOL_RES:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return None


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def enclosing_names(lines: list[str], line_no: int) -> list[str]:
    """The definition on a head line and every definition enclosing it, innermost first.

    A definition encloses the line when it is the nearest one above it with a
    smaller indent; the walk stops at a top-level definition.
    """
    if not 1 <= line_no <= len(lines):
        return []
    names: list[str] = []
    own = defined_name(lines[line_no - 1])
    if own:
        names.append(own)
    target = lines[line_no - 1]
    limit = indent_of(target) if target.strip() else float("inf")
    for line in reversed(lines[: line_no - 1]):
        if limit == 0:
            break
        name = defined_name(line)
        if name and indent_of(line) < limit:
            names.append(name)
            limit = indent_of(line)
    return names


def changed_symbols(repo: Path, changes: dict, unit: dict) -> list[str]:
    """Names the unit's changes define or sit inside, read from the head files."""
    names: list[str] = []
    for file in unit["files"]:
        change = changes[file["path"]]
        lines = anchor_findings.head_lines(repo, change.path) if change.status != "deleted" else None
        candidates: list[str] = []
        if lines is not None:
            for line_no in changed_line_numbers(change):
                candidates += enclosing_names(lines, line_no)
        for hunk in change.hunks:
            context = HUNK_CONTEXT_RE.match(hunk.header)
            for line in ([context.group(1)] if context else []) + hunk.changed_lines:
                name = defined_name(line)
                if name:
                    candidates.append(name)
        for name in candidates:
            if name not in names and not name.startswith("test"):
                names.append(name)
    return names


def find_callers(repo: Path, unit: dict, symbols: list[str]) -> str:
    """Lines outside the unit that name each symbol, from `git grep -n -w` at the head."""
    excluded = [f":(exclude){file['path']}" for file in unit["files"]]
    parts, total = [], 0
    for symbol in symbols:
        if total >= CALLER_LINES_TOTAL:
            parts.append(f"(caller lines stop at {CALLER_LINES_TOTAL}; symbols after this point are not listed)")
            break
        result = subprocess.run(
            ["git", "-C", str(repo), "grep", "-n", "-w", "-I", "-e", symbol, "--", ".", *excluded],
            capture_output=True,
            check=False,  # exit 1 means no match; the output decides
            text=True,
        )
        hits = result.stdout.splitlines()
        if not hits:
            continue
        shown = hits[: min(CALLER_LINES_PER_SYMBOL, CALLER_LINES_TOTAL - total)]
        total += len(shown)
        more = f"\n  ({len(hits) - len(shown)} more)" if len(hits) > len(shown) else ""
        parts.append(f"#### {symbol}\n" + "\n".join(f"  {hit[:200]}" for hit in shown) + more)
    return "\n".join(parts) if parts else "(no line outside the unit names a changed symbol)"


def build_messages(task: Task, context: dict) -> list[dict]:
    method_path = context["perspectives"] / f"{task.perspective}.md"
    method = strip_frontmatter(method_path.read_text(encoding="utf-8"))
    unit = task.unit
    user = "\n\n".join(
        [
            f"# Perspective: {task.perspective}\n\n{method}",
            "# Requirement copies (what the change answers)\n\n" + context["requirements"],
            f"# Unit {unit['id']} ({unit['rule']}): its hunks\n\n```diff\n{unit_diff(context['changes'], unit)}\n```",
            "# Unit files at the head (line number, `|`, then the line)\n\n" + numbered_head_files(context["repo"], context["changes"], unit),
            "# Lines elsewhere at the head that name a changed symbol\n\n" + context["callers"][unit["id"]],
            "# Output JSON Schema\n\n```json\n" + json.dumps(FINDINGS_SCHEMA, indent=1) + "\n```",
        ]
    )
    return [{"role": "system", "content": context["brief"]}, {"role": "user", "content": user}]


def validate_answer(answer: object) -> list[str]:
    """Schema violations of a parsed answer; empty when it is valid."""
    if not isinstance(answer, dict) or set(answer) != {"findings", "checked"}:
        return ["answer is not an object with exactly `findings` and `checked`"]
    problems = []
    for field_name in ("findings", "checked"):
        entries = answer[field_name]
        required = set(FINDINGS_SCHEMA["properties"][field_name]["items"]["required"])
        if not isinstance(entries, list):
            problems.append(f"`{field_name}` is not a list")
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or set(entry) != required:
                problems.append(f"`{field_name}[{index}]` keys are not {sorted(required)}")
            elif field_name == "findings":
                if entry["severity"] not in SEVERITIES:
                    problems.append(f"`findings[{index}].severity` is not one of {SEVERITIES}")
                if not isinstance(entry["line"], int):
                    problems.append(f"`findings[{index}].line` is not an integer")
    if answer["checked"] == []:
        problems.append("`checked` is empty: every checklist item of the perspective needs a row")
    return problems


def call_model(messages: list[dict], options: argparse.Namespace) -> tuple[str, dict, str]:
    """POST one chat completion; return the message content, the usage block, and the finish reason."""
    body = {
        "model": options.model,
        "messages": messages,
        "max_tokens": options.max_tokens,
        "response_format": {"type": "json_schema", "json_schema": {"name": "srv-findings", "schema": FINDINGS_SCHEMA}},
    }
    if options.reasoning_effort:
        body["reasoning_effort"] = options.reasoning_effort
    headers = {"Content-Type": "application/json"}
    key = os.environ.get(options.api_key_env, "") if options.api_key_env else ""
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        options.base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"), headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=options.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # The server states the cause (context length, schema) in the body, not in the status line.
        body = error.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"HTTP {error.code}: {body}") from error
    try:
        choice = payload["choices"][0]
        return choice["message"].get("content") or "", payload.get("usage") or {}, choice.get("finish_reason") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise ValueError(f"the response is not a chat completion ({type(error).__name__}: {error}): {str(payload)[:300]}") from error


def run_task(task: Task, context: dict, options: argparse.Namespace) -> dict:
    """Review one task; one retry when the call fails or the answer is invalid."""
    messages = build_messages(task, context)
    attempts, errors, usage_total = 0, [], {"prompt_tokens": 0, "completion_tokens": 0}
    started = time.monotonic()
    while attempts < 2:
        attempts += 1
        try:
            content, usage, finish_reason = call_model(messages, options)
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as error:
            errors.append(f"attempt {attempts}: call failed: {error}")
            continue
        for key in usage_total:
            usage_total[key] += int(usage.get(key) or 0)
        if finish_reason == "length":
            errors.append(
                f"attempt {attempts}: the answer stopped at --max-tokens {options.max_tokens} (finish_reason length); "
                "reasoning tokens count toward it, so rerun the task with a larger --max-tokens"
            )
            break
        try:
            answer = json.loads(content)
        except ValueError as error:
            errors.append(f"attempt {attempts}: content is not JSON: {error}")
            continue
        problems = validate_answer(answer)
        if problems:
            errors.append(f"attempt {attempts}: " + "; ".join(problems))
            continue
        findings = anchor_findings.anchor_findings(answer["findings"], context["repo"])
        return {
            "task": task.name,
            "unit": task.unit["id"],
            "perspective": task.perspective,
            "ok": True,
            "attempts": attempts,
            "errors": errors,
            "seconds": round(time.monotonic() - started, 1),
            "usage": usage_total,
            "findings": findings,
            "checked": answer["checked"],
        }
    return {
        "task": task.name,
        "unit": task.unit["id"],
        "perspective": task.perspective,
        "ok": False,
        "attempts": attempts,
        "errors": errors,
        "seconds": round(time.monotonic() - started, 1),
        "usage": usage_total,
    }


class Progress:
    """A tqdm bar for the person watching and `progress.json` for the record."""

    def __init__(self, total: int, out: Path) -> None:
        self.total, self.done, self.failed = total, 0, 0
        self.path = out / "progress.json"
        self.started = time.monotonic()
        self.lock = threading.Lock()
        try:
            from tqdm import tqdm

            self.bar = tqdm(total=total, desc="srv round 1", unit="task")
        except ImportError:
            self.bar = None
        self.write()

    def advance(self, result: dict) -> None:
        with self.lock:
            self.done += 1
            self.failed += 0 if result["ok"] else 1
            if self.bar is not None:
                self.bar.set_postfix(failed=self.failed)
                self.bar.update(1)
            else:
                print(f"srv round 1: {self.done}/{self.total} ({result['task']}, failed {self.failed})", file=sys.stderr)
            self.write()

    def write(self) -> None:
        elapsed = time.monotonic() - self.started
        remaining = elapsed / self.done * (self.total - self.done) if self.done else None
        record = {"done": self.done, "total": self.total, "failed": self.failed, "elapsed_s": round(elapsed, 1)}
        record["eta_s"] = round(remaining, 1) if remaining is not None else None
        self.path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    def close(self) -> None:
        if self.bar is not None:
            self.bar.close()


def read_result(out: Path, task: Task, diff_sha256: str) -> dict | None:
    """The task's output for this plan; an output left by a run on another diff does not count."""
    path = out / f"{task.name}.json"
    if not path.is_file():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    return result if result.get("diff_sha256") == diff_sha256 else None


def failed_result(task: Task, error: BaseException) -> dict:
    """A task that raised: kept as a failed output so the round still reports every task."""
    return {
        "task": task.name, "unit": task.unit["id"], "perspective": task.perspective, "ok": False, "attempts": 0,
        "errors": [f"the task raised {type(error).__name__}: {error}"], "seconds": 0.0,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }


def run_sweep(options: argparse.Namespace) -> int:
    started = time.monotonic()
    plan = json.loads(Path(options.units).read_text(encoding="utf-8"))
    diff_text = Path(options.diff).read_text(encoding="utf-8")
    diff_sha256 = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    if diff_sha256 != plan["diff_sha256"]:
        print("sweep: the diff is not the one the unit plan was made from; rerun plan-units.py on this diff", file=sys.stderr)
        return 2
    bare = [unit["id"] for unit in plan["units"] if not unit.get("perspectives")]
    if bare:
        print(
            f"sweep: units {bare} have no perspective, so no task would review them. Make the plan with "
            "`plan-units.py --perspectives <srv perspectives>`; every unit matches the `match: always` methods. "
            "Do not run the round on this plan or drop those units.",
            file=sys.stderr,
        )
        return 2
    repo, out = Path(options.repo), Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    changes = {change.path: change for change in plan_units.parse_diff(diff_text)}
    context = {
        "brief": BRIEF_PATH.read_text(encoding="utf-8"),
        "perspectives": Path(options.perspectives),
        "requirements": "\n\n".join(Path(path).read_text(encoding="utf-8") for path in options.requirements),
        "changes": changes,
        "repo": repo,
        "callers": {u["id"]: find_callers(repo, u, changed_symbols(repo, changes, u)) for u in plan["units"]},
    }
    all_tasks = list_tasks(plan)
    tasks = [task for task in all_tasks if not options.only or task.name in options.only]
    missing_methods = sorted({t.perspective for t in tasks if not (context["perspectives"] / f"{t.perspective}.md").is_file()})
    if missing_methods:
        print(f"sweep: no method file for perspectives {missing_methods} in {options.perspectives}", file=sys.stderr)
        return 2
    progress = Progress(len(tasks), out)
    with concurrent.futures.ThreadPoolExecutor(max_workers=options.max_concurrency) as pool:
        futures = {pool.submit(run_task, task, context, options): task for task in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001 - recorded as the task's failure; the round must still report every task
                result = failed_result(futures[future], error)
            result["diff_sha256"] = diff_sha256
            (out / f"{result['task']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            progress.advance(result)
    progress.close()
    results = [read_result(out, task, diff_sha256) for task in all_tasks]
    failed = sorted(task.name for task, result in zip(all_tasks, results) if not (result and result["ok"]))
    results = [result for result in results if result]
    severities = {s: 0 for s in SEVERITIES}
    for result in results:
        for finding in result.get("findings", []):
            severities[finding["severity"]] += 1
    summary = {
        "tasks": len(all_tasks),
        "ok": len(all_tasks) - len(failed),
        "failed": failed,
        "wall_s": round(time.monotonic() - started, 1),
        "slowest_s": max((r["seconds"] for r in results), default=0),
        "this_run_tasks": len(tasks),
        "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in results),
        "completion_tokens": sum(r["usage"]["completion_tokens"] for r in results),
        "findings_by_severity": severities,
        "model": options.model,
        "base_url": options.base_url,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary), file=sys.stderr)
    if failed:
        print(
            f"sweep: {len(failed)} tasks have no valid output ({', '.join(failed)}). Their units are unreviewed "
            "for that perspective: read each task file's `errors`, fix the cause (endpoint, token limit, schema), "
            "and rerun those tasks with --only; do not drop them from the review or mark them reviewed.",
            file=sys.stderr,
        )
        return 1
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="srv round 1: one structured-output call per (unit, perspective).")
    parser.add_argument("--units", required=True, help="unit plan from rv/bin/plan-units.py with --perspectives")
    parser.add_argument("--diff", required=True, help="the diff the unit plan was made from")
    parser.add_argument("--repo", required=True, help="head worktree")
    parser.add_argument("--perspectives", required=True, help="perspective method directory")
    parser.add_argument("--requirements", required=True, nargs="+", help="requirement copies")
    parser.add_argument("--out", required=True, help="round directory for task outputs and summary.json")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible endpoint, ending in /v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", help="environment variable holding the API key")
    parser.add_argument("--max-concurrency", type=int, default=32)
    parser.add_argument("--max-tokens", type=int, default=65536, help="covers reasoning and answer tokens")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per call")
    parser.add_argument("--reasoning-effort", default="high", help="empty string to omit")
    parser.add_argument("--only", nargs="+", help="task names `<unit>__<perspective>` to run, for a rerun of failed tasks")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    try:
        return run_sweep(options)
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as error:
        print(f"sweep: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
