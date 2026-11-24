#!/usr/bin/env python3
"""srv context pack: the repository context every session of one review shares, built once.

Fagan's inspection opens with an overview whose objective is "Education" of the whole team
before anyone looks for errors (Fagan 1976, IBM Systems Journal 15(3), Table: "1. Overview
Education (Group)"). The user asked for the same thing (2026-11-24): "그에 필요한 저장소 전체
맥락을 정리해서 전달하고." So instead of every reviewer searching the repository for the same
rules and callers, this script collects them once, deterministically, and every request of
the review starts with the same pack (which also lets the model server reuse its prefix).

The pack holds, each line numbered so a session can cite it:
- requirement copies: what the change answers;
- documents found by location: tracked Markdown and reStructuredText files in the
  directories on the path from the repository root to each changed file, and in `.github/`.
  No file name is assumed; a rule document is whatever sits where the change lives;
- callers: lines outside the change that name a symbol the change defines or edits;
- concept occurrences: every head line that names an identifier, constant, or literal the
  diff adds, inside or outside the changed files, so a reviewer sees at once where one
  concept is represented, written, or tested.

Usage:
  python3 -I context.py --units units.json --diff diff.patch --repo HEAD_WORKTREE \
      --requirements FILE [FILE ...] --out context
Writes context/pack.md and context/pack.json. Exit codes: 0 written, 2 bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
DOCUMENT_SUFFIXES = (".md", ".rst")
DOCUMENT_CHARS = 10_000  # one document's share; a long README or changelog is cut, rules are usually short
DOCUMENTS_CHARS = 40_000  # all documents together, smallest first
TERMS_MAX = 40
HITS_PER_TERM = 12
TERM_FILES_MAX = 30  # a term named in more files is a common word, not one concept's name
TERM_CHARS = 6
TERM_CANDIDATES = 400
IDENTIFIER_RE = re.compile(rf"[A-Za-z_][A-Za-z0-9_]{{{TERM_CHARS - 1},}}")
LITERAL_RE = re.compile(r"""["'`]([A-Za-z_][\w.:/-]{4,59})["'`]""")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sweep = load_module("srv_sweep_for_context", BIN / "sweep.py")


def tracked(repo: Path, pathspecs: list[str]) -> list[str]:
    result = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--", *pathspecs],
                            capture_output=True, check=True)
    return [p for p in result.stdout.decode("utf-8", errors="replace").split("\0") if p]


def document_paths(repo: Path, changed: list[str]) -> list[str]:
    """Tracked documents directly in each ancestor directory of a changed path, and in `.github/`."""
    directories = {""} | {".github"}
    for path in changed:
        parts = Path(path).parts[:-1]
        directories.update("/".join(parts[:n]) for n in range(1, len(parts) + 1))
    specs = [f":(glob){d + '/' if d else ''}*{suffix}" for d in sorted(directories) for suffix in DOCUMENT_SUFFIXES]
    return sorted(set(tracked(repo, specs)))


def documents_section(repo: Path, changed: list[str]) -> tuple[str, list[str]]:
    texts = {p: sweep.anchor_findings.head_lines(repo, p) or [] for p in document_paths(repo, changed)}
    parts, used, shown = [], 0, []
    for path in sorted(texts, key=lambda p: (sum(len(x) + 1 for x in texts[p]), p)):
        lines, budget, count = texts[path], min(DOCUMENT_CHARS, DOCUMENTS_CHARS - used), 0
        if budget <= 0:
            parts.append(f"### {path} (not shown: the document budget of {DOCUMENTS_CHARS} characters is spent)")
            continue
        size = 0
        for line in lines:
            if size + len(line) + 1 > budget:
                break
            size += len(line) + 1
            count += 1
        used += size
        cut = f" (first {count} of {len(lines)} lines)" if count < len(lines) else ""
        parts.append(f"### {path}{cut}\n" + (sweep.numbered_lines(lines, [(1, count)]) if count else "(empty)"))
        shown.append(path)
    return "\n\n".join(parts) or "(no tracked document on the paths of the change)", shown


def added_terms(changes: dict) -> dict[str, int]:
    """Identifiers and literals on the diff's added lines, with how many added lines name each, most first.

    An identifier here is a word of at least `TERM_CHARS` characters with an underscore or an inner capital
    (`record_prefix`, `RecordIdentity`), the shape names of variables, parameters, constants, and types take in
    most languages; a quoted literal is a short string without spaces. Both are taken by shape, not by language.
    """
    counts: dict[str, int] = {}
    for change in changes.values():
        for hunk in change.hunks:
            for line in hunk.lines:
                if line.startswith("+"):
                    for term in set(IDENTIFIER_RE.findall(line[1:])) | set(LITERAL_RE.findall(line[1:])):
                        if ("_" in term.strip("_") or re.search(r"[a-z][A-Z]", term)) and not term.startswith("test"):
                            counts[term] = counts.get(term, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: -item[1]))


def occurrences_section(repo: Path, counts: dict[str, int], changed: set[str]) -> tuple[str, list[str]]:
    """Every head line naming each term the diff adds on two or more lines, from one `git grep -F` call.

    A concept the change introduces and repeats is what one reviewer cannot see from its own hunks, so terms named
    nowhere outside the changed files come first, then by how many added lines repeat them. A term named in more
    than `TERM_FILES_MAX` files is a common word, and one named in a single file has no other place to show.
    """
    terms = [t for t, n in counts.items() if n >= 2][:TERM_CANDIDATES]
    if not terms:
        return "(the diff repeats no name or literal)", []
    arguments = [part for term in terms for part in ("-e", term)]
    result = subprocess.run(["git", "-C", str(repo), "grep", "-n", "-I", "-F", "-w", *arguments],
                            capture_output=True, text=True, check=False)  # exit 1 means no match
    hits: dict[str, list[str]] = {term: [] for term in terms}
    for row in result.stdout.splitlines():
        for term in terms:
            if re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", row):
                hits[term].append(row)
    files = {t: sorted({row.split(":", 1)[0] for row in hits[t]}) for t in terms}
    outside = {t: [f for f in files[t] if f not in changed] for t in terms}
    kept = sorted((t for t in terms if 2 <= len(files[t]) <= TERM_FILES_MAX),
                  key=lambda t: (bool(outside[t]), -counts[t]))[:TERMS_MAX]
    parts = []
    for term in kept:
        rows = hits[term]
        head = (f"#### {term}: {len(rows)} lines in {len(files[term])} files ({len(outside[term])} outside the change; "
                f"{counts[term]} added lines)")
        shown = "\n".join(f"  {row[:220]}" for row in rows[:HITS_PER_TERM])
        more = f"\n  ({len(rows) - HITS_PER_TERM} more)" if len(rows) > HITS_PER_TERM else ""
        parts.append(head + ("\n" + shown + more if rows else ""))
    return "\n".join(parts) or "(no name the diff repeats is named in two to TERM_FILES_MAX files)", kept


def build_pack(plan: dict, diff_text: str, repo: Path, requirements: list[Path]) -> tuple[str, dict]:
    changes = {c.path: c for c in sweep.plan_units.parse_diff(diff_text)}
    changed = [p for p in changes]
    whole = {"id": "change", "files": [f for u in plan["units"] for f in u["files"]]}
    documents, shown = documents_section(repo, changed)
    occurrences, terms = occurrences_section(repo, added_terms(changes), set(changed))
    pack = "\n\n".join([
        "# Repository context of this review (shared by every session; line-numbered so it can be cited)",
        "## Requirement copies (what the change answers)\n\n"
        + "\n\n".join(path.read_text(encoding="utf-8") for path in requirements),
        "## Documents on the paths of the change (cite a rule as `rule: <path>:<line>`)\n\n" + documents,
        "## Lines outside the change that name a symbol it defines or edits\n\n"
        + sweep.find_callers(repo, whole, sweep.changed_symbols(repo, changes, whole)),
        "## Head lines that name what the diff adds (where each concept is represented, written, or tested)\n\n"
        + occurrences,
        "## Files of the whole change\n\n" + "\n".join(f"- {c.path} ({c.status})" for c in changes.values()),
    ])
    meta = {"source_sha256": hashlib.sha256(diff_text.encode("utf-8")).hexdigest(), "chars": len(pack),
            "documents": shown, "terms": terms}
    return pack, meta


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the srv context pack every session of one review shares.")
    parser.add_argument("--units", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--requirements", required=True, nargs="+")
    parser.add_argument("--out", required=True)
    options = parser.parse_args(argv)
    plan = json.loads(Path(options.units).read_text(encoding="utf-8"))
    diff_text = Path(options.diff).read_text(encoding="utf-8")
    if hashlib.sha256(diff_text.encode("utf-8")).hexdigest() != plan["diff_sha256"]:
        print("context: the diff is not the one the unit plan was made from; rerun plan-units.py on it", file=sys.stderr)
        return 2
    pack, meta = build_pack(plan, diff_text, Path(options.repo), [Path(p) for p in options.requirements])
    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / sweep.PACK_FILE).write_text(pack + "\n", encoding="utf-8")
    (out / "pack.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"chars": meta["chars"], "documents": len(meta["documents"]), "terms": len(meta["terms"])}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
