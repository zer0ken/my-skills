#!/usr/bin/env python3
"""Check a PR body file against the body format of the pr skill (SKILL.md: Issue reference, Summary, Details).

The body is, in order: at most two issue reference lines (`Closes #N` first, then `Refs #N`) and a blank line,
a summary of `-` bullets (sub-bullets indented two spaces) of at most 10 lines with no heading, bold or
checkbox, and then only `<details>` sections, each opening with `<summary><h3>name</h3></summary>` and
written in HTML with no Markdown syntax. Anything else outside `<details>`, such as a bare `## heading`,
is a violation, because every detail section is folded.

Usage: check_pr_body.py BODY.md [--json RECEIPT.json]
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
from pathlib import Path

SUMMARY_MAX_LINES = 10
REFERENCE = re.compile(r"^(Closes #\d+(\. Closes #\d+)*\.?|Refs #\d+(, #\d+)*\.?)$")
BULLET = re.compile(r"^(  )?- \S")
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


def check(lines: Sequence[str]) -> list[tuple[int, str, str]]:
    """Violations of the body format as (1-based line, rule, message)."""
    violations: list[tuple[int, str, str]] = []
    at = 0
    references = 0
    while at < len(lines) and REFERENCE.match(lines[at]):
        references += 1
        at += 1
    keywords = [line.split()[0] for line in lines[:references]]
    if keywords not in ([], ["Closes"], ["Refs"], ["Closes", "Refs"]):
        violations.append((1, "REFERENCE", "at most one Closes line, then at most one Refs line"))
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
    for index in range(at, len(lines)):
        line, number = lines[index], index + 1
        if not in_details:
            if not line.strip():
                outside = False
                continue
            if line.strip() == "<details>":
                in_details, expect_summary, outside = True, True, False
                continue
            if not outside:  # one violation per paragraph outside <details>
                violations.append((number, "OUTSIDE", "after the summary write only <details> sections: "
                                   + line.strip()[:60]))
            outside = True
            continue
        if expect_summary:
            expect_summary = False
            if not SUMMARY_TAG.match(line.strip()):
                violations.append((number, "DETAILS", "open a section with <summary><h3>name</h3></summary>"))
            continue
        if line.strip() == "</details>":
            in_details = in_pre = False
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
