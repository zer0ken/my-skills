"""Pin the review unit planner: every reviewed hunk lands in exactly one unit, by fixed rules."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("plan_units", Path(__file__).with_name("plan-units.py"))
assert SPEC and SPEC.loader
plan_units = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = plan_units
SPEC.loader.exec_module(plan_units)


def file_diff(path: str, added: int, header: str = "", start: int = 1) -> str:
    """A modified-file diff that adds `added` lines at `start`."""
    body = "".join(f"+line {i}\n" for i in range(added))
    return (
        f"diff --git a/{path} b/{path}\n{header}--- a/{path}\n+++ b/{path}\n"
        f"@@ -{start},0 +{start},{added} @@\n{body}"
    )


DIFF = "".join(
    [
        file_diff("pkg/core.py", 3),
        file_diff("tests/test_core.py", 2),
        file_diff("pkg/util_a.py", 150),
        file_diff("pkg/util_b.py", 150),
        file_diff("pkg/util_c.py", 150),
        file_diff("i18n/messages_en.properties", 1),
        file_diff("i18n/messages_zh.properties", 1),
        "diff --git a/uv.lock b/uv.lock\n--- a/uv.lock\n+++ b/uv.lock\n@@ -1 +1 @@\n-a\n+b\n",
        "diff --git a/img.png b/img.png\nindex 1..2 100644\nBinary files a/img.png and b/img.png differ\n",
        (
            "diff --git a/old/name.py b/new/name.py\nsimilarity index 90%\nrename from old/name.py\nrename to new/name.py\n"
            "--- a/old/name.py\n+++ b/new/name.py\n@@ -2,1 +2,1 @@\n-x = 1\n+x = 2\n"
        ),
        "diff --git a/gone.py b/gone.py\ndeleted file mode 100644\n--- a/gone.py\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-SELECT 1\n",
        "diff --git a/docs/new.md b/docs/new.md\nnew file mode 100644\n--- /dev/null\n+++ b/docs/new.md\n@@ -0,0 +1,1 @@\n+# Title\n",
    ]
)


def unit_of(plan: dict, path: str) -> dict:
    return next(u for u in plan["units"] if any(f["path"] == path for f in u["files"]))


class ParseDiffTest(unittest.TestCase):
    def test_statuses_and_paths(self) -> None:
        changes = {c.path: c for c in plan_units.parse_diff(DIFF)}
        self.assertEqual(changes["new/name.py"].status, "renamed")
        self.assertEqual(changes["new/name.py"].old_path, "old/name.py")
        self.assertEqual(changes["gone.py"].status, "deleted")
        self.assertEqual(changes["docs/new.md"].status, "added")
        self.assertTrue(changes["img.png"].binary)
        self.assertEqual(changes["pkg/util_a.py"].changed, 150)

    def test_hunk_without_counts_defaults_to_one(self) -> None:
        hunk = plan_units.parse_diff(DIFF)[7].hunks[0]
        self.assertEqual((hunk.old_start, hunk.old_len, hunk.new_start, hunk.new_len), (1, 1, 1, 1))


class PlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = plan_units.plan_units(DIFF, budget=400)

    def test_every_reviewed_file_in_exactly_one_unit(self) -> None:
        reviewed = [f["path"] for u in self.plan["units"] for f in u["files"]]
        excluded = [e["file"] for e in self.plan["excluded"]]
        all_paths = [c.path for c in plan_units.parse_diff(DIFF)]
        self.assertEqual(sorted(reviewed + excluded), sorted(all_paths), "a file is missing from both units and exclusions, or appears twice")
        self.assertEqual(len(reviewed), len(set(reviewed)))

    def test_exclusions_keep_their_reason(self) -> None:
        self.assertEqual(
            sorted((e["file"], e["reason"]) for e in self.plan["excluded"]),
            [("img.png", "binary"), ("uv.lock", "lockfile")],
        )

    def test_source_and_test_are_bundled_across_directories(self) -> None:
        unit = unit_of(self.plan, "pkg/core.py")
        self.assertEqual(unit["rule"], "source-test")
        self.assertEqual([f["path"] for f in unit["files"]], ["pkg/core.py", "tests/test_core.py"])

    def test_topic_test_goes_with_the_longest_prefix_source(self) -> None:
        diff = file_diff("pkg/judge.py", 1) + file_diff("pkg/judge_chunk.py", 1) + file_diff("tests/test_judge_chunk_no_fact.py", 1)
        plan = plan_units.plan_units(diff, budget=0)
        unit = unit_of(plan, "tests/test_judge_chunk_no_fact.py")
        self.assertEqual([f["path"] for f in unit["files"]], ["pkg/judge_chunk.py", "tests/test_judge_chunk_no_fact.py"])

    def test_hyphenated_source_goes_with_its_underscored_test(self) -> None:
        diff = file_diff("bin/plan-units.py", 1) + file_diff("bin/test_plan_units.py", 1)
        unit = unit_of(plan_units.plan_units(diff, budget=0), "bin/plan-units.py")
        self.assertEqual(unit["rule"], "source-test", "a test module cannot carry `-`, so `-` in the source stem must pair as `_`")
        self.assertEqual([f["path"] for f in unit["files"]], ["bin/plan-units.py", "bin/test_plan_units.py"])

    def test_quoted_non_ascii_paths_are_decoded(self) -> None:
        quoted = '"a/docs/\\353\\254\\270\\354\\204\\234.md" "b/docs/\\353\\254\\270\\354\\204\\234.md"'
        diff = f"diff --git {quoted}\n--- x\n+++ y\n@@ -1 +1 @@\n-a\n+b\n"
        diff += 'diff --git "a/\\354\\225\\204.py" "b/\\353\\260\\224.py"\nrename from "\\354\\225\\204.py"\nrename to "\\353\\260\\224.py"\n'
        changes = plan_units.parse_diff(diff)
        self.assertEqual([(c.path, c.old_path, c.status) for c in changes],
                         [("docs/문서.md", "docs/문서.md", "modified"), ("바.py", "아.py", "renamed")],
                         "git C-escapes non-ASCII paths (core.quotePath); undecoded, the reviewer gets no file")

    def test_locale_siblings_are_bundled(self) -> None:
        unit = unit_of(self.plan, "i18n/messages_en.properties")
        self.assertEqual(unit["rule"], "locale")
        self.assertEqual(len(unit["files"]), 2)

    def test_directory_packing_respects_the_budget(self) -> None:
        first, last = unit_of(self.plan, "pkg/util_a.py"), unit_of(self.plan, "pkg/util_c.py")
        self.assertEqual([f["path"] for f in first["files"]], ["pkg/util_a.py", "pkg/util_b.py"])
        self.assertEqual(first["rule"], "directory")
        self.assertEqual([f["path"] for f in last["files"]], ["pkg/util_c.py"])
        self.assertEqual(last["rule"], "single")

    def test_unit_ids_are_sequential_in_path_order(self) -> None:
        ids = [u["id"] for u in self.plan["units"]]
        self.assertEqual(ids, [f"U-{n}" for n in range(1, len(ids) + 1)])
        firsts = [u["files"][0]["path"] for u in self.plan["units"]]
        self.assertEqual(firsts, sorted(firsts))

    def test_same_input_gives_the_same_plan(self) -> None:
        self.assertEqual(plan_units.plan_units(DIFF, budget=400), self.plan)


class GeneratedTest(unittest.TestCase):
    def test_linguist_generated_paths_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            Path(tmp, ".gitattributes").write_text("pkg/util_b.py linguist-generated\n", encoding="utf-8")
            plan = plan_units.plan_units(DIFF, repo=Path(tmp), budget=400)
        self.assertIn({"file": "pkg/util_b.py", "reason": "linguist-generated"}, plan["excluded"])


if __name__ == "__main__":
    unittest.main()
