"""Pin the srv verdict rule: blocking classes, withheld verdicts, and perspectives that must be accounted for."""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("verdict", Path(__file__).with_name("verdict.py"))
assert SPEC and SPEC.loader
verdict = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verdict
SPEC.loader.exec_module(verdict)

DECIDED = [{"id": "K-1", "decided": True}, {"id": "K-2", "decided": True}]


def cluster(severity: str, state: str = "CONFIRMED") -> dict:
    return {"id": f"R-{severity}", "severity": severity, "verdict": state, "evidence": "executed"}


class JudgeTest(unittest.TestCase):
    def decide(self, clusters=(), questions=(), perspectives=DECIDED) -> str:
        return verdict.judge({"clusters": list(clusters), "questions": list(questions), "perspectives": perspectives})["decision"]

    def test_confirmed_major_blocks(self) -> None:
        self.assertEqual(self.decide([cluster("MAJOR"), cluster("NIT")]), "차단")

    def test_plausible_blocker_withholds(self) -> None:
        self.assertEqual(self.decide([cluster("BLOCKER", "PLAUSIBLE")]), "증거 부족")

    def test_undecided_perspective_is_never_acceptance(self) -> None:
        judgment = verdict.judge({"perspectives": [{"id": "K-1", "decided": False, "note": "격리 실행 불가"}]})
        self.assertEqual(judgment["decision"], "증거 부족")
        self.assertEqual(judgment["residual_risk"], ["관점 K-1 는 점검을 정한 수단으로 다 판정하지 못했다: 격리 실행 불가"])

    def test_question_or_minor_is_conditional(self) -> None:
        self.assertEqual(self.decide(questions=[{"id": "Q-1"}]), "조건부 수용")
        self.assertEqual(self.decide([cluster("MINOR")]), "조건부 수용")

    def test_nothing_left_is_acceptance(self) -> None:
        self.assertEqual(self.decide(), "수용")


class FileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        design = {"ok": True, "perspectives": [{"id": "K-1"}, {"id": "K-2"}]}
        (self.root / "design").mkdir()
        (self.root / "design" / "perspectives.json").write_text(json.dumps(design), encoding="utf-8")
        (self.root / "design" / "U-1.json").write_text(json.dumps({"unit": "U-1", "ok": True, "changes": []}), encoding="utf-8")
        (self.root / "design" / "summary.json").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_verdict(self, body: dict) -> int:
        path = self.root / "verdict.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        stderr, stdout = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
            code = verdict.main(["--design", str(self.root / "design"), "--verdict", str(path)])
        self.stderr, self.stdout = stderr.getvalue(), stdout.getvalue()
        return code

    def test_a_perspective_left_out_stops_the_verdict(self) -> None:
        self.assertEqual(self.run_verdict({"perspectives": DECIDED[:1]}), 2)
        self.assertIn("perspectives ['K-2'] are not in the verdict file", self.stderr)

    def test_every_perspective_accounted_for_is_judged(self) -> None:
        self.assertEqual(self.run_verdict({"clusters": [cluster("BLOCKER")], "perspectives": DECIDED}), 0)
        self.assertEqual(json.loads(self.stdout)["decision"], "차단")


if __name__ == "__main__":
    unittest.main()
