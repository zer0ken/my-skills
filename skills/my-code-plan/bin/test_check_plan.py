"""Pin the my-code-plan plan check: a complete plan passes, each gap in the tree, the algorithm table, or the
known-solutions survey fails."""

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

SURVEY = """\
# Plan

## Known solutions

문제 유형: 1-medoid of a vector set
S1: nearest member to the centroid | https://en.wikipedia.org/wiki/Medoid | `centre.sql` computes in SQL
"""

TREE = SURVEY + """

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

    def assert_fails(self, text, message, why=check_plan.ALGORITHM_WHY, dont=check_plan.ALGORITHM_DONT):
        code, _, err = self.run_check(text)
        self.assertEqual(code, 1, f"the plan should fail with `{message}`, but passed")
        self.assertIn(message, err)
        self.assertIn(why, err)
        self.assertIn(dont, err)

    def assert_survey_fails(self, text, message):
        self.assert_fails(text, message, check_plan.SURVEY_WHY, check_plan.SURVEY_DONT)

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

    def test_missing_survey_fails(self):
        self.assert_survey_fails(TREE.replace(SURVEY, "# Plan\n") + ALGORITHMS, "no `## Known solutions` heading")

    def test_local_sources_only_fail(self):
        local = TREE.replace("https://en.wikipedia.org/wiki/Medoid", "`centre.sql:1`")
        self.assert_survey_fails(local + ALGORITHMS, "every source is local")

    def test_localhost_is_not_a_web_source(self):
        local = TREE.replace("https://en.wikipedia.org/wiki/Medoid", "http://localhost:8000/docs")
        self.assert_survey_fails(local + ALGORITHMS, "every source is local")

    def test_missing_problem_type_fails(self):
        self.assert_survey_fails(TREE.replace("문제 유형: 1-medoid of a vector set\n", "") + ALGORITHMS,
                                 "no `문제 유형:")

    def test_solution_without_three_fields_fails(self):
        self.assert_survey_fails(TREE.replace(" | `centre.sql` computes in SQL", "") + ALGORITHMS,
                                 "does not have the three fields")

    def test_run_record_with_survey_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp, "analyze.md")
            record.write_text("# analyze\n\n## 알려진 해법\n\n문제 유형: x\n", encoding="utf-8")
            text = TREE.replace(SURVEY, f"# Plan\n\n## Known solutions\n\nrun: {record}\n") + ALGORITHMS
            code, _, err = self.run_check(text)
            self.assertEqual(code, 0, err)

    def test_run_record_without_survey_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp, "analyze.md")
            record.write_text("# analyze\n", encoding="utf-8")
            text = TREE.replace(SURVEY, f"# Plan\n\n## Known solutions\n\nrun: {record}\n") + ALGORITHMS
            self.assert_survey_fails(text, "has no `## 알려진 해법` section")

    def test_backticked_new_leaf_is_new(self):
        text = TREE + "| L2 | 2 | C1 | Add the migration | migration test | `new:migrations/0012.sql` | settled |\n"
        code, out, err = self.run_check(text + ALGORITHMS)
        self.assertEqual(code, 0, err)
        self.assertIn("migrations/0012.sql", out)


if __name__ == "__main__":
    unittest.main()
