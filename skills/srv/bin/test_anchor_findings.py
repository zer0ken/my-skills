"""Pin finding re-location: each anchor status and the line it leaves."""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("anchor_findings", Path(__file__).with_name("anchor-findings.py"))
assert SPEC and SPEC.loader
anchor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = anchor
SPEC.loader.exec_module(anchor)

SOURCE = """\
def f(x):
    return x + 1


def g(x):
    return x + 1
    # done
"""


class AnchorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "m.py").write_text(SOURCE, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_one(self, line: int, text: str, file: str = "pkg/m.py") -> dict:
        return anchor.anchor_finding({"id": "F-1", "file": file, "line": line, "anchor": text}, self.repo)

    def test_exact_keeps_the_line(self) -> None:
        result = self.run_one(1, "def f(x):")
        self.assertEqual((result["anchor_status"], result["line"]), ("exact", 1))

    def test_moved_rewrites_the_line_and_keeps_the_report(self) -> None:
        result = self.run_one(3, "def g(x):")
        self.assertEqual((result["anchor_status"], result["line"], result["reported_line"]), ("moved", 5, 3))

    def test_nearest_picks_the_closest_of_several(self) -> None:
        result = self.run_one(5, "    return x + 1")
        self.assertEqual((result["anchor_status"], result["line"], result["anchor_candidates"]), ("nearest", 6, 2))

    def test_multi_line_anchor_matches_consecutive_lines(self) -> None:
        result = self.run_one(1, "return x + 1\n# done")
        self.assertEqual((result["anchor_status"], result["line"]), ("moved", 6))

    def test_partial_line_is_not_the_quoted_line(self) -> None:
        for text in ("def g(", "return x + 1\n# not here"):
            result = self.run_one(9, text)
            self.assertEqual((result["anchor_status"], result["line"]), ("missing", 9),
                             f"{text!r} is not a quoted head line; exact or moved would point the verifier at a line the reviewer never quoted")

    def test_findings_file_of_the_wrong_shape_exits_2(self) -> None:
        bad = self.repo / "bad.json"
        for content in ('{"items": []}', "3", '["x"]'):
            bad.write_text(content, encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(anchor.main([str(bad), "--repo", str(self.repo)]), 2, content)

    def test_missing_anchor_and_missing_file(self) -> None:
        self.assertEqual(self.run_one(1, "def h(x):")["anchor_status"], "missing")
        self.assertEqual(self.run_one(1, "def f(x):", file="pkg/none.py")["anchor_status"], "missing")

    def test_path_outside_the_repository_is_not_read(self) -> None:
        self.assertEqual(self.run_one(1, "root", file="../../etc/passwd")["anchor_status"], "missing")

    def test_empty_anchor_is_missing(self) -> None:
        self.assertEqual(self.run_one(1, "  \n")["anchor_status"], "missing")


if __name__ == "__main__":
    unittest.main()
