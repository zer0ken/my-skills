#!/usr/bin/env python3
"""Re-locate each finding's line from the code it quotes, before anyone verifies it.

A model reviewer often reports the right defect at the wrong line: it counts
lines in a prompt, or cites the line of a neighbouring hunk. A verifier then
spends its time finding the place before it can judge the claim. Each finding
therefore carries an anchor, the verbatim text of the line it points at, and
this tool finds that text in the head file and rewrites `line`:

- `exact`: the anchor is at the reported line.
- `moved`: the anchor occurs at exactly one other line; `line` is rewritten.
- `nearest`: the anchor occurs at several lines; the one nearest the reported
  line is taken, and `anchor_candidates` says how many there were.
- `missing`: the file does not exist at the head or the anchor is not in it;
  the finding goes to the verifier as it is, marked so.

A multi-line anchor matches consecutive lines; whitespace at both ends of each
line is ignored. Nothing looser counts: a line that only contains the anchor
is not the line the reviewer quoted, and calling it `exact` or `moved` would
send the verifier to the wrong place with no sign of doubt.

Usage: anchor-findings.py --repo HEAD_WORKTREE findings.json [--out anchored.json]
`findings.json` is a list of findings, or an object with a `findings` list; each
finding has `file` (relative to the repository), `line`, and `anchor`.
Exit codes: 0 written, 2 an input could not be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def anchor_lines(anchor: str) -> list[str]:
    return [line.strip() for line in anchor.splitlines() if line.strip()]


def find_anchor(lines: list[str], anchor: str) -> list[int]:
    """1-based line numbers where the anchor starts."""
    wanted = anchor_lines(anchor)
    if not wanted:
        return []
    stripped = [line.strip() for line in lines]
    return [i + 1 for i in range(len(stripped) - len(wanted) + 1) if stripped[i : i + len(wanted)] == wanted]


def head_lines(repo: Path, relative: str) -> list[str] | None:
    """Lines of a file inside the head worktree, or None when it is absent or outside it."""
    root = repo.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def anchor_finding(finding: dict, repo: Path) -> dict:
    """Return the finding with `line`, `anchor_status`, and `anchor_candidates` set."""
    result = dict(finding)
    lines = head_lines(repo, str(finding.get("file", "")))
    reported = int(finding.get("line") or 0)
    found = find_anchor(lines, str(finding.get("anchor", ""))) if lines is not None else []
    result["anchor_candidates"] = len(found)
    if not found:
        result["anchor_status"] = "missing"
    elif reported in found:
        result["anchor_status"] = "exact"
    elif len(found) == 1:
        result["anchor_status"] = "moved"
        result["reported_line"] = reported
        result["line"] = found[0]
    else:
        result["anchor_status"] = "nearest"
        result["reported_line"] = reported
        result["line"] = min(found, key=lambda line: (abs(line - reported), line))
    return result


def anchor_findings(findings: list[dict], repo: Path) -> list[dict]:
    return [anchor_finding(finding, repo) for finding in findings]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Re-locate finding lines from their quoted anchors.")
    parser.add_argument("findings", help="JSON list of findings, or an object with a `findings` list")
    parser.add_argument("--repo", required=True, help="head worktree the findings point into")
    parser.add_argument("--out", help="write here instead of stdout")
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"anchor-findings: {error}", file=sys.stderr)
        return 2
    findings = data.get("findings") if isinstance(data, dict) else data
    if not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        print(f"anchor-findings: {args.findings} is neither a list of finding objects nor an object with a `findings` list", file=sys.stderr)
        return 2
    anchored = anchor_findings(findings, Path(args.repo))
    output = {**data, "findings": anchored} if isinstance(data, dict) else anchored
    text = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    counts: dict[str, int] = {}
    for finding in anchored:
        counts[finding["anchor_status"]] = counts.get(finding["anchor_status"], 0) + 1
    print("anchor-findings: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
