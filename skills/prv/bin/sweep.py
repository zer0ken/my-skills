#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tqdm"]
# ///
"""prv reviewers: review a plan from every perspective with independent structured-output model calls.

A task is one perspective; it runs `--samples` independent requests to an
OpenAI-compatible endpoint at once, and all tasks run together, so the round
takes about as long as its slowest call. A reviewer session with tools spends
most of its time finding the code a plan talks about; the plan already names it,
as `path` or `path:line` citations. This script finds those citations, reads the
cited files at the review base, and puts the lines around each citation (the
whole file when it is short) into the request, with the AGENTS.md files on the
cited paths. The request holds the requirement copies, the plan with line
numbers, that code, those rules, and the perspective method last, so every
perspective shares one prompt prefix.

Calls, validation, retries, sample pooling, and the summary are srv's round
runner (`~/.agents/skills/srv/bin/sweep.py`); finding lines are re-located from
their anchors in the plan or the cited file.

Usage:
  uv run sweep.py --plan PLAN.md --requirements FILE [FILE ...] --repo REVIEW_BASE_WORKTREE \
      --perspectives DIR [--only trace query] --out reviewers --base-url URL --model MODEL \
      [--api-key-env NAME] [--samples 3]
Exit codes: 0 every perspective has a valid output, 1 some failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import posixpath
import re
import sys
import time
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
BRIEF_PATH = Path(__file__).resolve().parents[1] / "references" / "call-brief.md"
CITE_RE = re.compile(
    r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:py|sql|cypher|md|toml|ya?ml|json|ts|tsx|js|go|rs|sh))"
    r"(?::(\d+)(?:-(\d+))?)?(?![\w/])"
)
CITE_RADIUS = 20
SHORT_FILE_CHARS = 12_000
CITED_CHARS_TOTAL = 300_000


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


srv = load_module("srv_sweep", SKILLS / "srv" / "bin" / "sweep.py")


def resolve_cited_path(repo: Path, cited: str) -> str | None:
    """The repository path a citation names, dropping leading directories the repository does not have.

    Plans often cite through a worktree or checkout name (`merge/emem/x.py` for `emem/x.py`).
    """
    parts = cited.split("/")
    for start in range(len(parts)):
        candidate = "/".join(parts[start:])
        path = (repo / candidate).resolve()
        if path.is_relative_to(repo.resolve()) and path.is_file():
            return candidate
    return None


def find_citations(plan_text: str, repo: Path, skip: set[str]) -> dict[str, list[tuple[int, int]]]:
    """Cited repository files in order of first citation, each with its cited line ranges."""
    cited: dict[str, list[tuple[int, int]]] = {}
    for match in CITE_RE.finditer(plan_text):
        if posixpath.basename(match.group(1)) in skip:
            continue
        path = resolve_cited_path(repo, match.group(1))
        if path is None:
            continue
        ranges = cited.setdefault(path, [])
        if match.group(2):
            first = int(match.group(2))
            ranges.append((first, max(first, int(match.group(3) or first))))
    return cited


def merge_ranges(ranges: list[tuple[int, int]], radius: int, length: int) -> list[tuple[int, int]]:
    """Cited ranges widened by `radius` lines, clipped to 1..length, overlapping ones merged."""
    merged: list[list[int]] = []
    for first, last in sorted((max(1, a - radius), min(length, b + radius)) for a, b in ranges if a <= length):
        if merged and first <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    return [(a, b) for a, b in merged]


def numbered(lines: list[str], spans: list[tuple[int, int]]) -> str:
    return "\n  ...\n".join(
        "\n".join(f"{n:>5}| {lines[n - 1]}" for n in range(first, last + 1)) for first, last in spans
    )


def cited_code(repo: Path, citations: dict[str, list[tuple[int, int]]]) -> str:
    """The cited files at the review base, within `CITED_CHARS_TOTAL`, in citation order."""
    parts, used, left_out = [], 0, []
    for path, ranges in citations.items():
        lines = (repo / path).read_text(encoding="utf-8", errors="replace").splitlines()
        size = sum(len(line) + 1 for line in lines)
        if size <= SHORT_FILE_CHARS:
            title, spans = f"### {path}", [(1, len(lines))] if lines else []
        elif ranges:
            title = f"### {path} (the lines around the plan's citations; the file has {len(lines)} lines)"
            spans = merge_ranges(ranges, CITE_RADIUS, len(lines))
        else:
            left_out.append(f"{path} (cited without a line; {len(lines)} lines)")
            continue
        block = title + "\n" + numbered(lines, spans)
        if used + len(block) > CITED_CHARS_TOTAL:
            left_out.append(f"{path} (over the request budget)")
            continue
        parts.append(block)
        used += len(block)
    if left_out:
        parts.append("### Cited but not shown\n\n" + "\n".join(f"- {item}" for item in left_out))
    return "\n\n".join(parts) if parts else "(the plan cites no file of the repository)"


def repository_rules(repo: Path, citations: dict[str, list[tuple[int, int]]]) -> str:
    """AGENTS.md at the root and in every directory on the cited paths, root first."""
    found: list[str] = []
    for path in ["AGENTS.md"] + [
        posixpath.join(*Path(cited).parts[:depth], "AGENTS.md")
        for cited in citations
        for depth in range(1, len(Path(cited).parts))
    ]:
        if path not in found and (repo / path).is_file():
            found.append(path)
    return "\n\n".join(f"### {path}\n\n{(repo / path).read_text(encoding='utf-8')}" for path in found) or "(none)"


def build_messages(task, context: dict) -> list[dict]:
    method = srv.strip_frontmatter((context["perspectives"] / f"{task.perspective}.md").read_text(encoding="utf-8"))
    user = "\n\n".join(
        [
            context["shared"],
            f"# Perspective: {task.perspective}\n\n{method}",
            "# Output JSON Schema\n\n```json\n" + json.dumps(srv.FINDINGS_SCHEMA, indent=1) + "\n```",
        ]
    )
    return [{"role": "system", "content": context["brief"]}, {"role": "user", "content": user}]


def anchor_against(plan: Path, repo: Path):
    """Anchor a finding in the plan copy when it cites the plan, else in the review base."""

    def anchor(findings: list[dict]) -> list[dict]:
        return [
            srv.anchor_findings.anchor_finding({**f, "file": plan.name}, plan.parent)
            if posixpath.basename(str(f.get("file", ""))) == plan.name
            else srv.anchor_findings.anchor_finding(f, repo)
            for f in findings
        ]

    return anchor


def run(options: argparse.Namespace) -> int:
    started = time.monotonic()
    plan, repo, out = Path(options.plan), Path(options.repo), Path(options.out)
    perspectives = Path(options.perspectives)
    ids = options.only or sorted(path.stem for path in perspectives.glob("*.md"))
    missing = [pid for pid in ids if not (perspectives / f"{pid}.md").is_file()]
    if missing or not ids:
        print(f"prv sweep: no method file for perspectives {missing or ids} in {perspectives}", file=sys.stderr)
        return 2
    plan_text = plan.read_text(encoding="utf-8")
    requirements = "\n\n".join(Path(path).read_text(encoding="utf-8") for path in options.requirements)
    citations = find_citations(plan_text, repo, {plan.name, *(Path(p).name for p in options.requirements)})
    shared = "\n\n".join(
        [
            "# Requirement copies (what the plan answers)\n\n" + requirements,
            f"# The plan: {plan.name} (line number, `|`, then the line)\n\n" + numbered(plan_text.splitlines(), [(1, len(plan_text.splitlines()))]),
            "# Code the plan cites, at the review base\n\n" + cited_code(repo, citations),
            "# Repository rules on the cited paths\n\n" + repository_rules(repo, citations),
        ]
    )
    context = {"brief": BRIEF_PATH.read_text(encoding="utf-8"), "perspectives": perspectives, "shared": shared}
    tasks = [srv.Task({"id": "plan"}, pid) for pid in ids]
    out.mkdir(parents=True, exist_ok=True)
    source = hashlib.sha256((plan_text + "\0" + requirements).encode("utf-8")).hexdigest()
    return srv.run_round(
        tasks, tasks, lambda task: build_messages(task, context), anchor_against(plan, repo), options, out, source, started
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="prv reviewers: one structured-output call per perspective and sample.")
    parser.add_argument("--plan", required=True, help="the plan copy under review")
    parser.add_argument("--requirements", required=True, nargs="+", help="requirement copies")
    parser.add_argument("--repo", required=True, help="worktree at the review base")
    parser.add_argument("--perspectives", required=True, help="perspective method directory")
    parser.add_argument("--only", nargs="+", help="perspective ids (method file stems); default every method file")
    parser.add_argument("--out", required=True, help="directory for the per-perspective outputs and summary.json")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible endpoint, ending in /v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", help="environment variable holding the API key")
    parser.add_argument("--samples", type=int, default=3, help="independent calls per perspective, pooled")
    parser.add_argument("--max-concurrency", type=int, default=32)
    parser.add_argument("--max-tokens", type=int, default=131072, help="covers reasoning and answer tokens; 65,536 cut the trace answer on #1303 r2")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per call")
    parser.add_argument("--reasoning-effort", default="high", help="empty string to omit")
    options = parser.parse_args(argv)
    if options.samples < 1:
        parser.error("--samples must be 1 or more: a perspective with no sample is unreviewed")
    return options


def main(argv: list[str]) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
