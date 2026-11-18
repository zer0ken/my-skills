#!/usr/bin/env python3
"""Split a change into review units, deterministically, so no hunk goes unreviewed.

A review unit is a group of changed files reviewed together; every hunk of the
change belongs to exactly one unit. An agent asked to review a large diff tends
to read some files and skip others, and nothing shows which hunks it never
opened. Deciding the units in code, and checking coverage against them
(`check-review.py --units` in rv, `srv/bin/sweep.py` in srv), makes a skipped
hunk a visible failure instead of a silent gap.

Rules, applied in this order:

1. Exclude files no reviewer should read: binary diffs, lockfiles, and paths git
   marks `linguist-generated` at the head. Each exclusion is kept with its reason.
2. Bundle a source file with its tests (`test_x.py`/`x_test.py` with `x.py`,
   `x_test.go` with `x.go`, `x.test.ts`/`x.spec.ts` with `x.ts`, ...); a test
   named by topic, `test_x_topic.py`, goes with `x.py`.
3. Bundle locale siblings (`messages_en.properties` with `messages_zh.properties`).
4. Pack the remaining files of one directory, in path order, while the changed
   lines of the unit stay within the budget; a file larger than the budget is a
   unit of its own. Hunks are never split.

With `--perspectives`, each unit also lists the srv perspectives whose
frontmatter `match-*` lines it satisfies, with the matched reason.

Usage: plan-units.py --diff diff.patch [--repo HEAD_WORKTREE] [--perspectives DIR]
                     [--budget 400] [--out units.json]
Exit codes: 0 the plan was written, 2 an input could not be read.
"""

from __future__ import annotations

import argparse
import codecs
import fnmatch
import hashlib
import json
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BUDGET = 400
LOCKFILES = frozenset(
    {
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lockb",
        "Cargo.lock",
        "go.sum",
        "Gemfile.lock",
        "composer.lock",
        "flake.lock",
    }
)
LOCALE_EXTENSIONS = frozenset({"properties", "json", "yaml", "yml", "po", "strings", "xml", "resx", "arb", "toml", "ini"})
LOCALE_RE = re.compile(r"^(?P<base>.+?)[._-](?P<locale>[a-z]{2}(?:[_-][A-Za-z]{2,4})?)\.(?P<ext>[^.]+)$")
SOURCE_EXTENSIONS = (".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".java", ".kt", ".rb", ".php", ".cs")
TEST_NAME_RES = (
    re.compile(r"^test_(?P<stem>.+)(?P<ext>\.py)$"),
    re.compile(r"^(?P<stem>.+)_test(?P<ext>\.(?:py|go|rs|rb|php))$"),
    re.compile(r"^(?P<stem>.+)\.(?:test|spec)(?P<ext>\.(?:ts|tsx|js|jsx|mjs|cjs))$"),
    re.compile(r"^(?P<stem>.+)(?:Test|Tests)(?P<ext>\.(?:java|kt|cs|php))$"),
)
SAME_EXTENSION_TESTS = (".py", ".go", ".rs", ".rb", ".php")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
QUOTED_PATH = r'"(?:[^"\\]|\\.)*"'
DIFF_GIT_RE = re.compile(rf"^diff --git (?P<old>{QUOTED_PATH}|a/.+?) (?P<new>{QUOTED_PATH}|b/.+)$")
FRONTMATTER_KEYS = ("match", "match-path", "match-status", "match-line")
# Prose files whose changed lines `match-line` does not read: its patterns name
# code (`execute(`, `timeout`, `llm`), and the same words in prose would hand a
# document a code perspective. Documents get their perspectives by `match-path`.
PROSE_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")


@dataclass
class Hunk:
    """One `@@` block: its coordinates on both sides and its body lines."""

    header: str
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: list[str] = field(default_factory=list)

    @property
    def changed_lines(self) -> list[str]:
        """Added and removed lines without their `+`/`-` marker."""
        return [line[1:] for line in self.lines if line[:1] in "+-"]


@dataclass
class FileChange:
    """One file of the diff, named by its path at the head (the old path when deleted)."""

    path: str
    old_path: str
    status: str  # added, deleted, renamed, modified
    binary: bool = False
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return sum(len(h.changed_lines) for h in self.hunks)


def unquote_path(token: str) -> str:
    """A diff path as git wrote it, decoded.

    git quotes a path holding non-ASCII bytes or control characters and writes
    those bytes as C escapes (`core.quotePath`, on by default), so `문서.md`
    arrives as `"b/\\353\\254\\270\\354\\204\\234.md"`; read raw, it names no file.
    """
    if len(token) >= 2 and token[0] == token[-1] == '"':
        return codecs.escape_decode(token[1:-1].encode("utf-8"))[0].decode("utf-8")
    return token


def parse_diff(text: str) -> list[FileChange]:
    """Parse a unified `git diff` into files and hunks."""
    files: list[FileChange] = []
    current: FileChange | None = None
    hunk: Hunk | None = None
    for line in text.splitlines():
        match = DIFF_GIT_RE.match(line)
        if match:
            old, new = unquote_path(match.group("old"))[2:], unquote_path(match.group("new"))[2:]
            current = FileChange(path=new, old_path=old, status="modified")
            files.append(current)
            hunk = None
            continue
        if current is None:
            continue
        if hunk is None:
            if line.startswith("new file mode"):
                current.status = "added"
            elif line.startswith("deleted file mode"):
                current.status = "deleted"
                current.path = current.old_path
            elif line.startswith("rename from "):
                current.status = "renamed"
                current.old_path = unquote_path(line[len("rename from ") :])
            elif line.startswith("rename to "):
                current.path = unquote_path(line[len("rename to ") :])
            elif line.startswith(("Binary files ", "GIT binary patch")):
                current.binary = True
        match = HUNK_RE.match(line)
        if match:
            old_start, old_len, new_start, new_len = match.groups()
            hunk = Hunk(
                header=line,
                old_start=int(old_start),
                old_len=int(old_len) if old_len is not None else 1,
                new_start=int(new_start),
                new_len=int(new_len) if new_len is not None else 1,
            )
            current.hunks.append(hunk)
        elif hunk is not None and line[:1] in (" ", "+", "-", "\\"):
            hunk.lines.append(line)
    return files


def generated_paths(repo: Path, paths: list[str]) -> set[str]:
    """Paths whose `linguist-generated` attribute is set at the head worktree."""
    if not paths:
        return set()
    result = subprocess.run(
        ["git", "-C", str(repo), "check-attr", "-z", "linguist-generated", "--", *paths],
        capture_output=True,
        check=True,
    )
    fields = result.stdout.decode("utf-8").split("\0")
    triples = zip(fields[0::3], fields[1::3], fields[2::3])
    return {path for path, _, value in triples if value in ("set", "true")}


def exclusion_reason(change: FileChange, generated: set[str]) -> str | None:
    """Why no reviewer reads this file, or None when it is reviewed."""
    if change.binary:
        return "binary"
    if posixpath.basename(change.path) in LOCKFILES:
        return "lockfile"
    if change.path in generated:
        return "linguist-generated"
    return None


class Groups:
    """Union-find over file paths, keeping the rule that joined each group."""

    def __init__(self, paths: list[str]) -> None:
        self.parent = {path: path for path in paths}
        self.rule = {path: "single" for path in paths}

    def find(self, path: str) -> str:
        while self.parent[path] != path:
            self.parent[path] = self.parent[self.parent[path]]
            path = self.parent[path]
        return path

    def join(self, a: str, b: str, rule: str) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a == root_b:
            return
        root, child = sorted((root_a, root_b))
        self.parent[child] = root
        self.rule[root] = rule

    def members(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for path in sorted(self.parent):
            groups.setdefault(self.find(path), []).append(path)
        return groups


def find_test_source_pairs(paths: list[str]) -> list[tuple[str, str]]:
    """(test, source) pairs: a test file and the one source file it tests in the diff.

    The source's stem equals the test's stem, or is its longest prefix ending at
    `_` (`test_judge_chunk_no_fact.py` tests `judge_chunk.py`), because test
    modules are often split by topic under the name of the module they test.
    A `-` in the source's stem counts as `_`, because a test module cannot
    carry `-` in its name (`test_plan_units.py` tests `plan-units.py`).
    """
    sources: dict[tuple[str, str], list[str]] = {}
    for path in paths:
        stem, ext = posixpath.splitext(posixpath.basename(path))
        sources.setdefault((stem.replace("-", "_"), ext), []).append(path)
    pairs = []
    for path in paths:
        name = posixpath.basename(path)
        for pattern in TEST_NAME_RES:
            match = pattern.match(name)
            if not match:
                continue
            stem, ext = match.group("stem"), match.group("ext")
            extensions = (ext,) if ext in SAME_EXTENSION_TESTS else SOURCE_EXTENSIONS
            prefixes = [stem] + [stem[:i] for i in range(len(stem) - 1, 0, -1) if stem[i] == "_"]
            for prefix in prefixes:
                candidates = [c for e in extensions for c in sources.get((prefix, e), []) if c != path]
                same_dir = [c for c in candidates if posixpath.dirname(c) == posixpath.dirname(path)]
                chosen = same_dir or candidates
                if len(chosen) == 1:
                    pairs.append((path, chosen[0]))
                if candidates:
                    break
            break
    return pairs


def find_locale_siblings(paths: list[str]) -> list[list[str]]:
    """Groups of two or more files that differ only by a locale tag."""
    keyed: dict[tuple[str, str, str], list[str]] = {}
    for path in paths:
        match = LOCALE_RE.match(posixpath.basename(path))
        if match and match.group("ext") in LOCALE_EXTENSIONS:
            key = (posixpath.dirname(path), match.group("base"), match.group("ext"))
            keyed.setdefault(key, []).append(path)
    return [group for group in keyed.values() if len(group) > 1]


def bundle_files(changes: list[FileChange], budget: int) -> list[tuple[str, list[FileChange]]]:
    """Return (rule, files) per unit, ordered by the path of each unit's first file."""
    by_path = {change.path: change for change in changes}
    groups = Groups(sorted(by_path))
    for test, source in find_test_source_pairs(sorted(by_path)):
        groups.join(test, source, "source-test")
    for siblings in find_locale_siblings(sorted(by_path)):
        for other in siblings[1:]:
            groups.join(siblings[0], other, "locale")

    units: list[tuple[str, list[str]]] = []
    loose: dict[str, list[str]] = {}
    for root, members in groups.members().items():
        if len(members) > 1:
            units.append((groups.rule[root], members))
        else:
            loose.setdefault(posixpath.dirname(members[0]), []).append(members[0])
    for directory in sorted(loose):
        pack: list[str] = []
        size = 0
        for path in loose[directory]:
            changed = by_path[path].changed
            if pack and size + changed > budget:
                units.append(("directory" if len(pack) > 1 else "single", pack))
                pack, size = [], 0
            pack.append(path)
            size += changed
        units.append(("directory" if len(pack) > 1 else "single", pack))
    units.sort(key=lambda unit: unit[1][0])
    return [(rule, [by_path[path] for path in members]) for rule, members in units]


@dataclass
class Perspective:
    """The `match-*` frontmatter of one srv perspective method file."""

    id: str
    always: bool = False
    paths: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    lines: list[re.Pattern[str]] = field(default_factory=list)


def read_perspective(path: Path) -> Perspective:
    """Parse the leading `---` block of a perspective file; its keys are `FRONTMATTER_KEYS`."""
    perspective = Perspective(id=path.stem)
    text = path.read_text(encoding="utf-8").splitlines()
    if not text or text[0].strip() != "---":
        raise ValueError(
            f"{path}: no `---` frontmatter. Each perspective declares when it applies with "
            "`match: always` or `match-path`/`match-status`/`match-line` lines, so units pick "
            "perspectives by rule; add the lines that describe the code this method reviews."
        )
    for line in text[1:]:
        if line.strip() == "---":
            return perspective
        key, sep, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not sep or key not in FRONTMATTER_KEYS:
            raise ValueError(f"{path}: frontmatter line `{line}` is not one of {', '.join(FRONTMATTER_KEYS)}")
        if key == "match":
            if value != "always":
                raise ValueError(f"{path}: `match:` takes only `always`")
            perspective.always = True
        elif key == "match-path":
            perspective.paths.append(value)
        elif key == "match-status":
            perspective.statuses.append(value)
        else:
            perspective.lines.append(re.compile(value))
    raise ValueError(f"{path}: frontmatter is not closed with `---`")


def read_perspectives(directory: Path) -> list[Perspective]:
    return [read_perspective(path) for path in sorted(directory.glob("*.md"))]


def match_reasons(perspective: Perspective, files: list[FileChange]) -> list[str]:
    """Why a perspective applies to a unit; empty when it does not."""
    if perspective.always:
        return ["always"]
    reasons: list[str] = []
    for change in files:
        for pattern in perspective.paths:
            if fnmatch.fnmatch(change.path, pattern) or fnmatch.fnmatch(posixpath.basename(change.path), pattern):
                reasons.append(f"path {change.path} ~ {pattern}")
        if change.status in perspective.statuses:
            reasons.append(f"status {change.path} {change.status}")
        for pattern in perspective.lines if not change.path.lower().endswith(PROSE_SUFFIXES) else ():
            hit = next((line for h in change.hunks for line in h.changed_lines if pattern.search(line)), None)
            if hit is not None:
                reasons.append(f"line {change.path} ~ /{pattern.pattern}/: {hit.strip()[:80]}")
    return reasons


def plan_units(
    diff_text: str,
    repo: Path | None = None,
    perspectives: list[Perspective] | None = None,
    budget: int = DEFAULT_BUDGET,
) -> dict:
    """Build the unit plan: units with their hunks and perspectives, and the excluded files."""
    changes = parse_diff(diff_text)
    generated = generated_paths(repo, [c.path for c in changes if c.status != "deleted"]) if repo else set()
    excluded, kept = [], []
    for change in changes:
        reason = exclusion_reason(change, generated)
        if reason:
            excluded.append({"file": change.path, "reason": reason})
        else:
            kept.append(change)
    units = []
    for number, (rule, files) in enumerate(bundle_files(kept, budget), start=1):
        unit = {
            "id": f"U-{number}",
            "rule": rule,
            "changed_lines": sum(f.changed for f in files),
            "files": [
                {
                    "path": f.path,
                    "old_path": f.old_path,
                    "status": f.status,
                    "hunks": [
                        {"header": h.header, "old_start": h.old_start, "old_len": h.old_len, "new_start": h.new_start, "new_len": h.new_len}
                        for h in f.hunks
                    ],
                }
                for f in files
            ],
        }
        if perspectives is not None:
            matched = {p.id: match_reasons(p, files) for p in perspectives}
            unit["perspectives"] = {pid: reasons for pid, reasons in matched.items() if reasons}
        units.append(unit)
    return {
        "diff_sha256": hashlib.sha256(diff_text.encode("utf-8")).hexdigest(),
        "budget": budget,
        "units": units,
        "excluded": excluded,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Split a git diff into review units.")
    parser.add_argument("--diff", required=True, help="unified diff, `git diff <merge base>...<head>`")
    parser.add_argument("--repo", help="head worktree, for `linguist-generated` attributes")
    parser.add_argument("--perspectives", help="srv perspective directory with `match-*` frontmatter")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="changed lines per directory unit")
    parser.add_argument("--out", help="write the plan here instead of stdout")
    args = parser.parse_args(argv)
    try:
        diff_text = Path(args.diff).read_text(encoding="utf-8")
        perspectives = read_perspectives(Path(args.perspectives)) if args.perspectives else None
        plan = plan_units(diff_text, Path(args.repo) if args.repo else None, perspectives, args.budget)
    except (OSError, UnicodeDecodeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"plan-units: {error}", file=sys.stderr)
        return 2
    text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    tasks = sum(len(u.get("perspectives", {})) for u in plan["units"])
    print(
        f"plan-units: {len(plan['units'])} units, {sum(len(u['files']) for u in plan['units'])} files, "
        f"{len(plan['excluded'])} excluded, {tasks} tasks",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
