#!/usr/bin/env python3
"""Check a my-code-plan plan tree and print the leaves it approves for editing.

Usage: python3 -I check-plan.py <plan.md> --repo <repository or worktree root>

The plan file holds one Markdown table under the heading `## Plan tree` with the
columns id, depth, parents, node, check, code, status (see ../SKILL.md). The check
enforces the structure of top-down refinement: every node descends exactly one
depth from its parents, a depth is settled before the next is written, and every
branch ends in a leaf that names a real code change. On success it prints one
`approved: <absolute path>` line per leaf and `my-code-plan: plan OK`, which the
Claude Code hook code-plan-gate.py reads to allow edits of those files.
"""

import argparse
import os
import re
import sys

COLUMNS = ["id", "depth", "parents", "node", "check", "code", "status"]
STATUSES = {"draft", "settled"}
MIN_LEAF_DEPTH = 2
OK_LINE = "my-code-plan: plan OK"

WHY = (
    "The plan tree exists so that code changes are derived top-down from the requirement at depth 0, one depth"
    " at a time, instead of from the code in hand; an edit no settled leaf names is an edit nobody derived."
)
DONT = (
    "Do not satisfy this check by renumbering depths, marking draft rows settled without checking them, deleting"
    " rows, or pointing a leaf at whatever file you were about to edit; fix the node whose content is missing."
)


def read_rows(text):
    """Rows of the table under `## Plan tree` as dicts, with their line numbers."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if re.fullmatch(r"##\s+Plan tree\s*", line))
    except StopIteration:
        return None, ["the file has no `## Plan tree` heading; write the tree as the table that SKILL.md shows"]
    header, rows, errors = None, [], []
    for number, line in enumerate(lines[start + 1:], start + 2):
        if line.startswith("#"):
            break
        if not line.strip().startswith("|"):
            if header and line.strip():
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None:
            header = [cell.lower() for cell in cells]
            if header != COLUMNS:
                return None, [f"line {number}: the columns are {header}, but must be exactly {COLUMNS}"]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) != len(COLUMNS):
            errors.append(f"line {number}: {len(cells)} cells, expected {len(COLUMNS)}")
            continue
        rows.append(dict(zip(COLUMNS, cells), line=number))
    if header is None:
        return None, ["no table follows `## Plan tree`"]
    return rows, errors


def leaf_path(code, repo):
    """(absolute path, is new) of a leaf's code cell `path`, `path::symbol`, or `new:path`."""
    new = code.startswith("new:")
    path = code[4:] if new else code
    path = path.split("::", 1)[0].strip().strip("`")
    return os.path.normpath(os.path.join(repo, path)), new


def check(rows, repo):
    errors = []
    by_id = {}
    for row in rows:
        where = f"line {row['line']} ({row['id'] or 'no id'})"
        if not row["id"]:
            errors.append(f"{where}: empty id")
        elif row["id"] in by_id:
            errors.append(f"{where}: id repeats line {by_id[row['id']]['line']}; ids must be unique")
        else:
            by_id[row["id"]] = row
        if not re.fullmatch(r"\d+", row["depth"]):
            errors.append(f"{where}: depth `{row['depth']}` is not a non-negative integer")
        if row["status"] not in STATUSES:
            errors.append(f"{where}: status `{row['status']}` must be one of {sorted(STATUSES)}")
        if not row["check"] or row["check"] == "-":
            errors.append(f"{where}: no check; name the test or observation that shows this node holds")
        if not row["node"] or row["node"] == "-":
            errors.append(f"{where}: no node statement")
    if errors:
        return errors, []
    for row in rows:
        row["depth"] = int(row["depth"])
        row["parent_ids"] = [] if row["parents"] in ("", "-") else [p.strip() for p in row["parents"].split(",")]
        row["children"] = []
    if not any(row["depth"] == 0 for row in rows):
        errors.append("no depth-0 node; start the tree with the requirement quoted in its original wording")
    for row in rows:
        where = f"line {row['line']} ({row['id']})"
        if row["depth"] == 0 and row["parent_ids"]:
            errors.append(f"{where}: a depth-0 node has no parents; it is the requirement itself")
        if row["depth"] > 0 and not row["parent_ids"]:
            errors.append(f"{where}: depth {row['depth']} needs parents at depth {row['depth'] - 1}")
        for pid in row["parent_ids"]:
            parent = by_id.get(pid)
            if parent is None:
                errors.append(f"{where}: parent `{pid}` is not a node id")
            elif parent["depth"] != row["depth"] - 1:
                errors.append(f"{where}: parent {pid} is at depth {parent['depth']}, not {row['depth'] - 1};"
                              " a node refines its parent by exactly one depth, so add the missing depth between")
            else:
                parent["children"].append(row["id"])
    if errors:
        return errors, []
    draft_depths = [row["depth"] for row in rows if row["status"] == "draft"]
    deepest = max(row["depth"] for row in rows)
    if draft_depths and min(draft_depths) < deepest:
        errors.append(f"depth {min(draft_depths)} still has draft nodes while depth {deepest} exists; settle one"
                      " depth (completeness, necessity, one step, grounds) before writing the next")
    if draft_depths:
        errors.append(f"depth {min(draft_depths)} is draft; settle it and descend until every branch is a leaf")
    approved = []
    for row in rows:
        where = f"line {row['line']} ({row['id']})"
        is_leaf = row["code"] not in ("", "-")
        if is_leaf and row["children"]:
            errors.append(f"{where}: a leaf names code, so it has no children; move the code to the deepest node")
        if not is_leaf and not row["children"]:
            errors.append(f"{where}: inner node with no children; refine it one depth further until it is a leaf,"
                          " or remove it if nothing needs it")
        if not is_leaf:
            continue
        if row["depth"] < MIN_LEAF_DEPTH:
            errors.append(f"{where}: a leaf at depth {row['depth']}; a code change sits at depth {MIN_LEAF_DEPTH} or"
                          " deeper, under a completion condition at depth 1")
        path, new = leaf_path(row["code"], repo)
        if not os.path.isabs(row["code"].removeprefix("new:")) and not path.startswith(repo + os.sep):
            errors.append(f"{where}: `{row['code']}` resolves outside --repo {repo}")
        elif new and os.path.exists(path):
            errors.append(f"{where}: `{row['code']}` is marked new: but {path} exists")
        elif not new and not os.path.exists(path):
            errors.append(f"{where}: {path} does not exist; confirm the path with `git ls-files` or mark it new:")
        else:
            approved.append(path)
    return errors, approved


def main():
    parser = argparse.ArgumentParser(description="Check a my-code-plan plan tree.")
    parser.add_argument("plan")
    parser.add_argument("--repo", required=True, help="root the leaf paths are relative to")
    args = parser.parse_args()
    repo = os.path.realpath(args.repo)
    with open(args.plan, encoding="utf-8") as handle:
        rows, errors = read_rows(handle.read())
    approved = []
    if rows is not None and not errors:
        if not rows:
            errors = ["the plan tree table has no rows"]
        else:
            errors, approved = check(rows, repo)
    if errors:
        print(f"my-code-plan: plan {args.plan} is not ready for editing.\n{WHY}", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print(DONT, file=sys.stderr)
        return 1
    for path in sorted(set(approved)):
        print(f"approved: {path}")
    print(OK_LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
