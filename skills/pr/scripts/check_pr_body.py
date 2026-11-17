#!/usr/bin/env python3
"""Check a PR body file against the body format of the pr skill (SKILL.md: Issue reference, Summary, Details).

The body is, in order: the change visual, one Markdown image line `![alt](target)` and a blank line, whose target
is either a local image file to be uploaded with `gh pr create --attach` or the https URL it was uploaded to;
at most two issue reference lines (`Closes #N` first, then `Refs #N`) and a blank line,
a summary of `-` bullets (sub-bullets indented two spaces) of at most 10 lines with no heading, bold or
checkbox, and then only `<details>` sections, each opening with `<summary><h3>name</h3></summary>` and
written in HTML with no Markdown syntax, and two consecutive sections separated by exactly one blank line
with no `---` line. Anything else outside `<details>`, such as a bare `## heading`, is a violation,
because every detail section is folded.

Usage: check_pr_body.py BODY.md [--json RECEIPT.json]   (run from the directory gh runs in)
Prints one `path:line: RULE message` per violation and exits 1 when there is any, 0 otherwise. The receipt
records the body's sha256 so a gate can tell that the check read the body it is about to post.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

SUMMARY_MAX_LINES = 10
VISUAL = re.compile(r"^!\[([^\]]+)\]\((\S+)\)$")
# Image types `gh --attach` uploads and GitHub renders inline (docs.github.com, Attaching files).
VISUAL_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
REFERENCE = re.compile(r"^(Closes #\d+(\. Closes #\d+)*\.?|Refs #\d+(, #\d+)*\.?)$")
BULLET = re.compile(r"^(  )?- \S")
# The gap between two `<details>` sections: one blank line. The `<h3>` summaries already mark the sections.
SEPARATOR = [""]
SUMMARY_TAG = re.compile(r"^<summary><h3>[^<]+</h3></summary>$")
# Markdown syntax that GitHub leaves literal inside an HTML block (SKILL.md Details).
MARKDOWN_IN_HTML = [
    (re.compile(r"^\s*#{1,6} "), "Markdown heading"),
    (re.compile(r"^\s*([-*+]|\d+\.) "), "Markdown list item"),
    (re.compile(r"^\s*\|"), "Markdown table row"),
    (re.compile(r"^\s*>"), "Markdown quote"),
    (re.compile(r"`"), "backtick (use <code>)"),
    (re.compile(r"\]\("), "Markdown link (use <a href>)"),
    (re.compile(r"\*\*"), "Markdown bold (use <b>)"),
]


def check_visual(lines: Sequence[str], root: Path) -> list[tuple[int, str, str]]:
    """Violations of the change visual on the first line; local targets resolve against `root`."""
    match = VISUAL.match(lines[0]) if lines else None
    if not match:
        return [(1, "VISUAL", "the body opens with the change visual, `![<what it compares>](<image>)`: a reader "
                 "sees what the PR changes before any prose (SKILL.md Change visual); build it from real data run "
                 "through the base and the head, do not replace it with a prose summary or move it lower")]
    violations: list[tuple[int, str, str]] = []
    target = match[2]
    if not target.startswith("https://"):
        if PurePosixPath(target).suffix.lower() not in VISUAL_SUFFIXES:
            violations.append((1, "VISUAL", f"{target} is not an image `gh --attach` uploads; render the HTML "
                               "source to PNG and reference the PNG, do not link the HTML file"))
        elif not (root / target).is_file():
            violations.append((1, "VISUAL", f"{target} does not exist from {root}; run this check from the "
                               "directory where `gh pr create --attach` will run, with the same path in the body "
                               "and the flag, so gh rewrites this line to the uploaded URL"))
    if len(lines) < 2 or lines[1].strip():
        violations.append((2, "VISUAL", "leave a blank line after the change visual"))
    return violations


def check(lines: Sequence[str], root: Path = Path(".")) -> list[tuple[int, str, str]]:
    """Violations of the body format as (1-based line, rule, message)."""
    violations = check_visual(lines, root)
    at = 2 if lines and VISUAL.match(lines[0]) else 0
    references = 0
    while at < len(lines) and REFERENCE.match(lines[at]):
        references += 1
        at += 1
    keywords = [line.split()[0] for line in lines[at - references:at]]
    if keywords not in ([], ["Closes"], ["Refs"], ["Closes", "Refs"]):
        violations.append((at - references + 1, "REFERENCE", "at most one Closes line, then at most one Refs line"))
    if references and (at >= len(lines) or lines[at].strip()):
        violations.append((at + 1, "REFERENCE", "leave a blank line after the reference lines"))
    while at < len(lines) and not lines[at].strip():
        at += 1
    summary_start = at
    while at < len(lines) and lines[at].strip() and not lines[at].startswith("<details>"):
        line = lines[at]
        if not BULLET.match(line):
            violations.append((at + 1, "SUMMARY", "the summary holds only `-` bullets and two-space sub-bullets"))
        elif re.search(r"\*\*|^\s*- \[[ xX]\]", line):
            violations.append((at + 1, "SUMMARY", "no bold text or checkbox in the summary"))
        at += 1
    if at == summary_start:
        violations.append((at + 1, "SUMMARY", "the body needs a `-` bullet summary"))
    elif at - summary_start > SUMMARY_MAX_LINES:
        violations.append((summary_start + 1, "SUMMARY",
                           f"the summary has {at - summary_start} lines; at most {SUMMARY_MAX_LINES}"))
    in_details = in_pre = outside = False
    expect_summary = False
    gap_start: int | None = None  # index after the last `</details>`, while outside a section
    for index in range(at, len(lines)):
        line, number = lines[index], index + 1
        if not in_details:
            if not line.strip():
                outside = False
                continue
            if line.strip() == "<details>":
                gap = [line.strip() for line in lines[gap_start:index]] if gap_start is not None else SEPARATOR
                if gap != SEPARATOR and "---" not in gap:
                    violations.append((number, "SEPARATOR", "separate consecutive <details> sections with exactly "
                                       "one blank line"))
                in_details, expect_summary, outside, gap_start = True, True, False, None
                continue
            if line.strip() == "---":
                violations.append((number, "SEPARATOR", "delete this `---` line: the <summary><h3> headings already "
                                   "mark each section, and a rule between folded sections only adds lines; do not "
                                   "replace it with another divider"))
                continue
            if not outside:  # one violation per paragraph outside <details>
                violations.append((number, "OUTSIDE", "after the summary write only <details> sections: "
                                   + line.strip()[:60]))
            outside = True
            continue
        if expect_summary:
            expect_summary = False
            if not SUMMARY_TAG.match(line.strip()):
                violations.append((number, "DETAILS", "open a section with <summary><h3>name</h3></summary>: a "
                                   "plain-text summary renders as a small fold marker, so the section reads as a "
                                   "folded piece of the paragraph above instead of a titled section; write the "
                                   "section's title in <h3>, do not drop the <summary>"))
            continue
        if line.strip() == "</details>":
            in_details = in_pre = False
            gap_start = index + 1
            continue
        if "<pre" in line:
            in_pre = True
        if not in_pre:
            for pattern, name in MARKDOWN_IN_HTML:
                if pattern.search(line):
                    violations.append((number, "HTML", f"{name} inside <details>; write HTML only"))
                    break
        if "</pre>" in line:
            in_pre = False
    if in_details:
        violations.append((len(lines), "DETAILS", "a <details> section is not closed"))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a PR body file against the pr skill's body format.")
    parser.add_argument("body", type=Path)
    parser.add_argument("--json", type=Path, help="write {body, sha256, violations} to this receipt")
    arguments = parser.parse_args()
    data = arguments.body.read_bytes()
    violations = check(data.decode("utf-8").splitlines())
    for line, rule, message in violations:
        print(f"{arguments.body}:{line}: {rule} {message}")
    if arguments.json:
        arguments.json.write_text(json.dumps({
            "body": str(arguments.body), "sha256": hashlib.sha256(data).hexdigest(),
            "violations": [{"line": line, "rule": rule, "message": message} for line, rule, message in violations],
        }, ensure_ascii=False, indent=2) + "\n")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
