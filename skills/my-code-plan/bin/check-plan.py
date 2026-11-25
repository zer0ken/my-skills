#!/usr/bin/env python3
"""Check a my-code-plan plan tree and print the leaves it approves for editing.

Usage: python3 -I check-plan.py <plan.md> --repo <repository or worktree root>

The plan file holds one Markdown table under the heading `## Plan tree` with the
columns id, depth, parents, node, check, code, status, and under `## Algorithms`
either a table with the columns node, problem, candidates, chosen, grounds or the
one line `none: <reason>`, and under `## Known solutions` the survey the plan rests on:
a `문제 유형:` line and `S<n>: <solution> | <source read> | <support in the target>` lines
with at least one web URL among the sources, or, inside a my-workflow run, the one line
`run: <analyze record path>` (see ../SKILL.md). The check enforces the structure of
top-down refinement: every node descends exactly one depth from its parents, a
depth is settled before the next is written, every branch ends in a leaf that names
a real code change, and every computation the plan records was chosen from at least
two known candidates with their complexity. On success it prints one
`approved: <absolute path>` line per leaf and `my-code-plan: plan OK`.
"""

import argparse
import os
import re
import sys

COLUMNS = ["id", "depth", "parents", "node", "check", "code", "status"]
ALGORITHM_COLUMNS = ["node", "problem", "candidates", "chosen", "grounds"]
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
ALGORITHM_WHY = (
    "The algorithm table exists because the first algorithm that meets a computation's definition is often not"
    " the cheapest known one (an all-pairs medoid where the member nearest the centroid takes one pass), and an"
    " implementer who never names the problem and lists the known algorithms with their complexity never sees it."
)
ALGORITHM_DONT = (
    "Do not satisfy it by writing `none:` for a plan that computes something, padding the candidates with a"
    " strawman, or copying the definition you already implemented into `chosen`; name the problem by its known"
    " type, look up its known algorithms and the platform's native features, and choose by complexity."
)
SURVEY_WHY = (
    "The known-solutions survey exists because a plan built from the code in hand and memory repeats what the"
    " field already solved better: the instructions' research order is the official documentation on the web,"
    " then a web search, then the repository's own records, and it ends before the plan (user, 2026-11-25:"
    " \"계획을 세울 때 웹 조사를 안한다. 개선해라.\")."
)
SURVEY_DONT = (
    "Do not satisfy it by writing a URL from memory, a documentation front page you did not read, or a single"
    " solution line with no search behind it; search now, read the pages, and write what they say. Inside a"
    " my-workflow run, point `run:` at the analyze record instead of surveying twice."
)
WEB_URL = re.compile(r"https?://(?!localhost|127\.|0\.0\.0\.0)[^\s|`)>]+")
SOLUTION = re.compile(r"S\d+:\s*(.*)")


def read_rows(text, heading="Plan tree", columns=COLUMNS):
    """Rows of the table under `## <heading>` as dicts, with their line numbers."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if re.fullmatch(rf"##\s+{heading}\s*", line))
    except StopIteration:
        return None, [f"the file has no `## {heading}` heading; write it as SKILL.md shows"]
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
            if header != columns:
                return None, [f"line {number}: the columns are {header}, but must be exactly {columns}"]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) != len(columns):
            errors.append(f"line {number}: {len(cells)} cells, expected {len(columns)}")
            continue
        rows.append(dict(zip(columns, cells), line=number))
    if header is None:
        return None, [f"no table follows `## {heading}`"]
    return rows, errors


def check_algorithms(text, node_ids):
    """Errors of the `## Algorithms` section: a `none: <reason>` line, or rows whose choice names one of at least
    two candidates, each written `<name>: <complexity>` with a big-O bound."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.fullmatch(r"##\s+Algorithms\s*", line)), None)
    if start is None:
        return ["the file has no `## Algorithms` heading; add the algorithm table, or `none: <reason>` when no node"
                " computes anything"]
    body = []
    for line in lines[start + 1:]:
        if line.startswith("#"):
            break
        if line.strip():
            body.append(line.strip())
    if body and re.match(r"none:", body[0]):
        if len(body) > 1 or not body[0][len("none:"):].strip():
            return ["`## Algorithms` with `none:` holds that one line with its reason and no table"]
        return []
    rows, errors = read_rows(text, "Algorithms", ALGORITHM_COLUMNS)
    if rows is None:
        return errors
    if not rows and not errors:
        return ["the algorithm table has no rows; give one row per node that specifies a computation, or write"
                " `none: <reason>`"]
    for row in rows:
        where = f"line {row['line']} (algorithm row for {row['node'] or 'no node'})"
        if row["node"] not in node_ids:
            errors.append(f"{where}: `{row['node']}` is not a plan-tree node id; name the node that specifies the"
                          " computation")
        if not row["problem"] or row["problem"] == "-":
            errors.append(f"{where}: no problem; name the problem the computation solves by its known type")
        candidates = [c.strip() for c in row["candidates"].split(";") if c.strip()]
        if len(candidates) < 2:
            errors.append(f"{where}: {len(candidates)} candidate; list at least two, the one that first meets the"
                          " definition and the known alternatives, separated by `;`")
        names = []
        for candidate in candidates:
            name, _, cost = candidate.partition(":")
            if not name.strip() or "O(" not in cost:
                errors.append(f"{where}: candidate `{candidate}` is not `<name>: <complexity>` with a big-O bound"
                              " in the input sizes")
            names.append(name.strip())
        if row["chosen"] not in names:
            errors.append(f"{where}: chosen `{row['chosen']}` is not the name of a candidate in the row")
        if not row["grounds"] or row["grounds"] == "-":
            errors.append(f"{where}: no grounds; say why the choice is the cheapest candidate that meets the"
                          " requirement, with its source")
    return errors


def check_survey(text):
    """Errors of the `## Known solutions` section: a `run: <analyze record>` line naming a file with a
    `## 알려진 해법` section, or a `문제 유형:` line and `S<n>:` lines of three `|` fields, one source a web URL."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.fullmatch(r"##\s+Known solutions\s*", line)), None)
    if start is None:
        return ["the file has no `## Known solutions` heading; survey the problem's known solutions on the web"
                " first and write them there as SKILL.md shows"]
    body = []
    for line in lines[start + 1:]:
        if line.startswith("#"):
            break
        if line.strip():
            body.append(line.strip())
    if body and body[0].startswith("run:"):
        record = os.path.expanduser(body[0][len("run:"):].strip().strip("`"))
        if len(body) > 1:
            return ["`## Known solutions` with `run:` holds that one line only"]
        if not os.path.isfile(record):
            return [f"`run:` names {record}, which is not a file; give the path of the run's analyze record"]
        with open(record, encoding="utf-8") as handle:
            if not re.search(r"^##\s+알려진 해법\s*$", handle.read(), re.M):
                return [f"{record} has no `## 알려진 해법` section; finish the analyze survey first"]
        return []
    errors = []
    if not any(re.match(r"문제 유형:\s*\S", line) for line in body):
        errors.append("no `문제 유형: <known problem>` line; name the known problem this change is an instance of")
    solutions = [m.group(1) for m in map(SOLUTION.match, body) if m]
    if not solutions:
        errors.append("no `S<n>: <solution> | <source read> | <support in the target>` line")
    sources = []
    for solution in solutions:
        fields = [field.strip() for field in solution.split("|")]
        if len(fields) != 3 or not all(fields):
            errors.append(f"`S: {solution}` does not have the three fields solution | source read | support")
        else:
            sources.append(fields[1])
    if solutions and not any(WEB_URL.search(source) for source in sources):
        errors.append("every source is local; at least one must be a web URL you read in this task (official"
                      " documentation first, then a web search)")
    return errors


def leaf_path(code, repo):
    """(absolute path, is new) of a leaf's code cell `path`, `path::symbol`, or `new:path`."""
    code = code.strip("`")
    new = code.startswith("new:")
    path = code[4:] if new else code
    path = path.split("::", 1)[0].strip()
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
        if not os.path.isabs(row["code"].strip("`").removeprefix("new:")) and not path.startswith(repo + os.sep):
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
        text = handle.read()
    rows, errors = read_rows(text)
    approved = []
    if rows is not None and not errors:
        if not rows:
            errors = ["the plan tree table has no rows"]
        else:
            errors, approved = check(rows, repo)
    algorithm_errors = check_algorithms(text, {row["id"] for row in rows or []})
    survey_errors = check_survey(text)
    if errors or algorithm_errors or survey_errors:
        print(f"my-code-plan: plan {args.plan} is not ready for editing.", file=sys.stderr)
        if errors:
            print(WHY, file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            print(DONT, file=sys.stderr)
        if algorithm_errors:
            print(ALGORITHM_WHY, file=sys.stderr)
            for error in algorithm_errors:
                print(f"  - {error}", file=sys.stderr)
            print(ALGORITHM_DONT, file=sys.stderr)
        if survey_errors:
            print(SURVEY_WHY, file=sys.stderr)
            for error in survey_errors:
                print(f"  - {error}", file=sys.stderr)
            print(SURVEY_DONT, file=sys.stderr)
        return 1
    for path in sorted(set(approved)):
        print(f"approved: {path}")
    print(OK_LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
