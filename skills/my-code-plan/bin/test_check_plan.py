"""Pin the my-code-plan plan check: a complete plan passes, each gap in the tree or the algorithm table fails."""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("check_plan", Path(__file__).with_name("check-plan.py"))
assert SPEC and SPEC.loader
check_plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_plan)

TREE = """\
# Plan

## Plan tree

| id | depth | parents | node | check | code | status |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | 0 | - | "묶인 정보 중 중앙에 있는 것을 대표로 삼자" | the decision holds | - | settled |
| C1 | 1 | R1 | Each group's representative is its central member | test of the pick | - | settled |
| L1 | 2 | C1 | Pick the member nearest the centroid | `test_centre.py::test_pick` | `centre.sql` | settled |
"""

ALGORITHMS = """
## Algorithms

| node | problem | candidates | chosen | grounds |
| --- | --- | --- | --- | --- |
| L1 | 1-medoid of m vectors | sum of distances medoid: O(m²·d); nearest to centroid: O(m·d) | nearest to centroid | least sum of squared distances by the centroid identity |
"""


class CheckPlanTest(unittest.TestCase):
    def run_check(self, text):
        with tempfile.TemporaryDirectory() as repo:
            Path(repo, "centre.sql").write_text("", encoding="utf-8")
            plan = Path(repo, "plan.md")
            plan.write_text(text, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            argv = sys.argv
            sys.argv = ["check-plan.py", str(plan), "--repo", repo]
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = check_plan.main()
            finally:
                sys.argv = argv
            return code, out.getvalue(), err.getvalue()

    def assert_fails(self, text, message):
        code, _, err = self.run_check(text)
        self.assertEqual(code, 1, f"the plan should fail with `{message}`, but passed")
        self.assertIn(message, err)
        self.assertIn(check_plan.ALGORITHM_WHY, err)
        self.assertIn(check_plan.ALGORITHM_DONT, err)

    def test_complete_plan_passes(self):
        code, out, err = self.run_check(TREE + ALGORITHMS)
        self.assertEqual(code, 0, err)
        self.assertTrue(out.endswith(check_plan.OK_LINE + "\n"))

    def test_none_with_reason_passes(self):
        code, _, err = self.run_check(TREE + "\n## Algorithms\n\nnone: the change renames a column\n")
        self.assertEqual(code, 0, err)

    def test_missing_section_fails(self):
        self.assert_fails(TREE, "no `## Algorithms` heading")

    def test_none_without_reason_fails(self):
        self.assert_fails(TREE + "\n## Algorithms\n\nnone:\n", "holds that one line with its reason")

    def test_single_candidate_fails(self):
        self.assert_fails(TREE + ALGORITHMS.replace("sum of distances medoid: O(m²·d); ", ""),
                          "1 candidate; list at least two")

    def test_candidate_without_complexity_fails(self):
        self.assert_fails(TREE + ALGORITHMS.replace("O(m²·d)", "all pairs"), "with a big-O bound")

    def test_chosen_outside_candidates_fails(self):
        self.assert_fails(TREE + ALGORITHMS.replace("| nearest to centroid | least", "| geometric median | least"),
                          "chosen `geometric median` is not the name of a candidate")

    def test_unknown_node_fails(self):
        self.assert_fails(TREE + ALGORITHMS.replace("| L1 | 1-medoid", "| L9 | 1-medoid"),
                          "`L9` is not a plan-tree node id")


if __name__ == "__main__":
    unittest.main()
