"""Pin the rv review format check: a complete document passes, each gap fails."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check_review", Path(__file__).with_name("check-review.py")
)
assert SPEC and SPEC.loader
check_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_review)

COMPLETE = """\
@author 판정은 변경 요청이며 head `abc`, finding 1건(MAJOR 1)이다.

## 개념과 정의
| 단위 | 정의 | 정의한 곳 | 판정 |
|---|---|---|---|
| `merge_edges` | 같은 두 노드 사이 엣지를 하나로 합친다 | `relation.py:10` docstring | 정의됨 |

## 설계와 원인
원인을 제거한다. 대안: 단일 요청 판정.

## 기능과 완료 기준
이슈의 완료 기준 두 항목을 충족한다.

## 크기와 증가
| 차원 | base | head | 차이 |
|---|---|---|---|
| 제품 줄 | 100 | 180 | +80 |

| 새 단위 | 호출자 | 재사용 검색 | 판단 |
|---|---|---|---|
| `merge_edges` | `relation.py:10` | `rg merge_` 0건 | 유지 |

## 품질
측정 없음: 측정 공백으로 기록한다.

## 시험
새 시험이 결함 코드에서 실패한다.

## 이름과 문서
해당 없음: 이름과 문서 변경이 없다.

## 엣지 생성
```
## 설계와 원인
```
- R-001 MAJOR, 관찰: 문제. `a.py:1`. 조치.

## 확인하고 배제한 항목
캐시 무효화: 죽은 항목만 지운다(`cache.py:20`).

## 검증 범위
시험 미실행.
<!-- emem-review-verdict: REQUEST_CHANGES blocking=1 -->
"""


def fold(document: str) -> str:
    """Fold every `## 제목` of a review the way `references/posting.md` folds a body over 50 lines."""
    lines, open_section, in_fence = [], False, False
    for line in document.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        if line.startswith("## ") and not in_fence:
            if open_section:
                lines += ["", "</details>", ""]
            lines += ["<details>", f"<summary><h3>{line[3:]}</h3></summary>", ""]
            open_section = True
        else:
            lines.append(line)
    return "\n".join(lines + ["", "</details>", ""])


CATALOG = check_review.read_catalog(check_review.ITEMS_PATH.read_text(encoding="utf-8"))
HEADER = "| 턴 | 항목 | 영역 | 확인한 범위 | 근거 | 판정 |\n|---|---|---|---|---|---|\n"


def ledger_row(turn: int, item, area: str = "전체", verdict: str = "배제: 결함 없음") -> str:
    scope = "; ".join(f"{check} 확인" for check in item.sub_checks)
    return f"| 리뷰어:{turn} | {item.id} | {area} | {scope} | `relation.py:10` | {verdict} |"


def build_ledger(areas=("전체",), verdicts=None) -> str:
    """One turn per item; a per-area item writes one row per area in its turn."""
    verdicts = verdicts or {}
    rows = []
    for turn, item in enumerate(CATALOG.values(), start=1):
        for area in areas if item.per_area else ("전체",):
            rows.append(ledger_row(turn, item, area, verdicts.get(item.id, "배제: 결함 없음")))
    return HEADER + "\n".join(rows) + "\n"


LEDGER = build_ledger(verdicts={"U1-size": "R-001", "U0-prior": "해당 없음: 첫 리뷰다"})


class CheckLedgerTest(unittest.TestCase):
    def test_catalog_lists_every_item(self):
        self.assertEqual(len(CATALOG), 20)
        self.assertEqual(CATALOG["U1-import"].sub_checks, ("1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"))
        self.assertTrue(CATALOG["U3-db"].per_area)
        self.assertFalse(CATALOG["U2-concepts"].per_area)

    def test_complete_ledger_passes(self):
        self.assertEqual(check_review.check_ledger(LEDGER, COMPLETE, CATALOG), [])

    def test_missing_item_fails(self):
        text = "\n".join(line for line in LEDGER.splitlines() if "| U3-security |" not in line)
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장에 `U3-security`(전체) 행이 없다: 모든 항목을 각자의 턴에서 검토해야 한다."],
        )

    def test_two_items_in_one_turn_fails(self):
        text = LEDGER.replace("| 리뷰어:3 |", "| 리뷰어:2 |")
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            [
                (
                    "항목 원장의 턴 `리뷰어:2` 에 `U1-import` 와 `U1-layout` 가 함께 있다: 한 턴에는 한 항목만 검토한다. "
                    "턴 값만 바꿔 맞추지 말고 `U1-layout` 를 자기 턴에서 다시 검토하고 그 턴에서 행을 쓴다."
                )
            ],
        )

    def test_per_area_item_covers_its_areas_in_one_turn(self):
        text = build_ledger(areas=("U-1", "U-2"), verdicts={"U1-size": "R-001", "U0-prior": "해당 없음: 첫 리뷰다"})
        turns = [line.split("|")[1].strip() for line in text.splitlines() if "| U3-db |" in line]
        self.assertEqual(len(turns), 2)
        self.assertEqual(len(set(turns)), 1, "U3-db 의 두 단위 행은 한 턴에서 나온다")
        self.assertEqual(check_review.check_ledger(text, COMPLETE, CATALOG), [])

    def test_skipped_sub_check_fails(self):
        text = LEDGER.replace("1.6 확인; ", "")
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장의 `U1-import`(전체) 행 확인한 범위에 세부 점검 1.6 가 없다: 세부 점검마다 결과를 적는다."],
        )

    def test_finding_absent_from_review_fails(self):
        text = LEDGER.replace("| R-001 |", "| R-002 |")
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장의 `U1-size`(전체) 행이 리뷰 문서에 없는 R-002 를 가리킨다."],
        )

    def test_verdict_without_reason_fails(self):
        row = ledger_row(4, CATALOG["U1-names"])
        text = LEDGER.replace(row, row.replace("배제: 결함 없음", "문제없음"))
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장의 `U1-names`(전체) 행 판정이 R-ID, `배제: <이유>`, `해당 없음: <이유>` 가 아니다."],
        )

    def test_evidence_without_location_fails(self):
        row = ledger_row(4, CATALOG["U1-names"])
        text = LEDGER.replace(row, row.replace("`relation.py:10`", "코드를 읽었다"))
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장의 `U1-names`(전체) 행 근거에 `file:line`, 백틱 명령, URL 이 없다: 근거는 다시 확인할 수 있어야 한다."],
        )

    def test_empty_cell_fails(self):
        row = ledger_row(4, CATALOG["U1-names"])
        text = LEDGER.replace(row, row.replace("| `relation.py:10` |", "|  |"))
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장의 `U1-names`(전체) 행에 빈 칸이 있다(근거): 빈 칸은 그 항목을 검토했는지 확인할 수 없게 한다."],
        )

    def test_per_area_item_missing_for_one_area_fails(self):
        text = build_ledger(areas=("DB", "프롬프트"), verdicts={"U1-size": "R-001"})
        text = "\n".join(line for line in text.splitlines() if "| U3-db | 프롬프트 |" not in line)
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장에 `U3-db`(프롬프트) 행이 없다: 모든 항목을 각자의 턴에서 검토해야 한다."],
        )

    def test_whole_item_with_area_fails(self):
        row = ledger_row(4, CATALOG["U1-names"])
        text = LEDGER.replace(row, row.replace("| U1-names | 전체 |", "| U1-names | DB |"))
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            [
                "항목 원장의 `U1-names`(DB) 행 영역이 `전체` 가 아니다: 이 항목은 영역별 항목이 아니다.",
                "항목 원장에 `U1-names`(전체) 행이 없다: 모든 항목을 각자의 턴에서 검토해야 한다.",
            ],
        )

    def test_unknown_item_fails(self):
        text = LEDGER + "| 리뷰어:99 | U9-extra | 전체 | 확인 | `a.py:1` | 배제: 없음 |\n"
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            ["항목 원장의 `U9-extra` 는 목록에 없는 항목이다: 항목은 `references/items.md` 목록에서만 고른다."],
        )

    def test_escaped_pipe_stays_inside_cell(self):
        row = ledger_row(4, CATALOG["U1-names"])
        text = LEDGER.replace(row, row.replace("`relation.py:10`", "`rg -n merge_ \\| wc -l`"))
        self.assertEqual(check_review.check_ledger(text, COMPLETE, CATALOG), [])

    def test_unescaped_pipe_in_cell_fails(self):
        row = ledger_row(4, CATALOG["U1-names"])
        text = LEDGER.replace(row, row.replace("`relation.py:10`", "`rg -n merge_ | wc -l`"))
        self.assertEqual(
            check_review.check_ledger(text, COMPLETE, CATALOG),
            [
                ("항목 원장의 `U1-names` 행 칸이 7개다(열은 6개): 칸 안의 `|` 는 GFM 표 규칙대로 `\\|` 로 쓴다. "
                "`&#124;` 는 백틱 안에서 글자 그대로 남으니 쓰지 말고, 칸을 지우거나 합치지 않는다.")
            ],
        )

    def test_units_covered_by_per_area_rows_pass(self):
        text = build_ledger(areas=("U-1", "U-2"), verdicts={"U1-size": "R-001"})
        self.assertEqual(check_review.check_units(text, CATALOG, ["U-1", "U-2"]), [])

    def test_unit_without_rows_fails(self):
        text = build_ledger(areas=("U-1",), verdicts={"U1-size": "R-001"})
        self.assertEqual(
            check_review.check_units(text, CATALOG, ["U-1", "U-2"]),
            [
                (
                    "항목 원장에 단위 `U-2` 의 영역별 항목 행이 없다: 이 단위의 hunk 를 아무도 리뷰하지 않았다. "
                    "행만 채우지 말고 `U-2` 의 hunk 를 영역별 항목마다 리뷰한 뒤 그 턴에서 행을 쓴다."
                )
            ],
        )

    def test_area_outside_the_unit_plan_fails(self):
        text = build_ledger(areas=("U-1", "DB"), verdicts={"U1-size": "R-001"})
        self.assertEqual(
            check_review.check_units(text, CATALOG, ["U-1"]),
            [
                (
                    "항목 원장의 영역 `DB` 은 단위 계획에 없는 단위다: 영역은 `units.json` 의 단위 id 로 나눈다. "
                    "영역 이름을 바꿔 맞추지 말고 그 행이 리뷰한 hunk 가 속한 단위 id 를 적는다."
                )
            ],
        )

    def test_main_checks_units_when_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            review, ledger, units = Path(tmp, "review.md"), Path(tmp, "ledger.md"), Path(tmp, "units.json")
            review.write_text(COMPLETE, encoding="utf-8")
            ledger.write_text(build_ledger(areas=("U-1",), verdicts={"U1-size": "R-001", "U0-prior": "해당 없음: 첫 리뷰다"}), encoding="utf-8")
            units.write_text('{"units": [{"id": "U-1"}, {"id": "U-2"}]}', encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(check_review.main([str(review), "--ledger", str(ledger), "--units", str(units)]), 1)
            self.assertIn("단위 `U-2`", out.getvalue())

    def test_unit_plan_of_the_wrong_shape_is_a_read_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            review, ledger, units = Path(tmp, "review.md"), Path(tmp, "ledger.md"), Path(tmp, "units.json")
            review.write_text(COMPLETE, encoding="utf-8")
            ledger.write_text(LEDGER, encoding="utf-8")
            for content in ("[1, 2]", '{"units": ["U-1"]}', '{"units": [{"name": "U-1"}]}'):
                units.write_text(content, encoding="utf-8")
                err = io.StringIO()
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(check_review.main([str(review), "--ledger", str(ledger), "--units", str(units)]), 2, content)
                self.assertIn("plan-units.py 로 다시 만든다", err.getvalue())

    def test_main_requires_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            review, ledger = Path(tmp, "review.md"), Path(tmp, "ledger.md")
            review.write_text(COMPLETE, encoding="utf-8")
            ledger.write_text(LEDGER, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(check_review.main([str(review), "--ledger", str(ledger)]), 0)
            self.assertEqual(out.getvalue(), "rv review format: review and item ledger passed (20 items)\n")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                check_review.main([str(review)])
            self.assertEqual(raised.exception.code, 2)


class CheckReviewTest(unittest.TestCase):
    def test_complete_document_passes(self):
        self.assertEqual(check_review.check_document(COMPLETE), [])

    def test_missing_section_fails(self):
        text = COMPLETE.replace("## 시험\n새 시험이 결함 코드에서 실패한다.\n\n", "")
        self.assertEqual(
            check_review.check_document(text),
            [
                ("`## 시험` 절이 없다: 이 판단을 쓰지 않은 리뷰는 그 기준을 검토했는지 독자가 확인할 수 없다. "
                "50줄 넘는 글로 접었다면 그 제목 줄은 `<summary><h3>시험</h3></summary>` 로 쓴다.")
            ],
        )

    def test_size_section_without_table_fails(self):
        start = COMPLETE.index("| 차원")
        end = COMPLETE.index("## 품질")
        text = COMPLETE[:start] + "순증가 80줄이다.\n\n" + COMPLETE[end:]
        self.assertEqual(
            check_review.check_document(text),
            [
                "`## 크기와 증가` 절에 base·head 차원별 표가 없다: 수치 비교 없이는 증가가 문제 해결에 비례하는지 판단할 수 없다."
            ],
        )

    def test_empty_section_fails(self):
        text = COMPLETE.replace("측정 없음: 측정 공백으로 기록한다.\n", "")
        self.assertEqual(
            check_review.check_document(text),
            ["`## 품질` 절이 비어 있다: 판단이 없으면 `해당 없음: <이유>` 를 쓴다."],
        )

    def test_out_of_order_and_not_last_fails(self):
        text = COMPLETE + "\n## 부록\n자료.\n"
        text = text.replace("## 품질", "## 임시").replace("## 시험", "## 품질").replace("## 임시", "## 시험")
        self.assertEqual(
            check_review.check_document(text),
            [
                "필수 절의 순서가 다르다: 개념과 정의 → 설계와 원인 → 기능과 완료 기준 → 크기와 증가 → 시험 → 품질 → 이름과 문서 → 확인하고 배제한 항목 → 검증 범위. 순서가 고정되어야 독자와 자동화가 같은 위치에서 판단을 찾는다.",
                "마지막 절이 `## 부록` 이다: `## 검증 범위` 가 마지막이어야 실행하지 않은 검증이 끝에서 드러난다.",
            ],
        )

    def test_undefined_concept_without_finding_fails(self):
        row = "| `merge_edges` | 같은 두 노드 사이 엣지를 하나로 합친다 | `relation.py:10` docstring | 정의됨 |"
        text = COMPLETE.replace(row, row + "\n| `metadata` | 단계마다 키를 덧붙이는 JSON | 없음 | 정의 없음 |")
        self.assertEqual(
            check_review.check_document(text),
            ["`## 개념과 정의` 의 `metadata` 행이 `정의됨` 이 아닌데 R-ID 가 없다: 정의 없는 단위는 서술이 아니라 finding 이다."],
        )
        self.assertEqual(check_review.check_document(text.replace("| 정의 없음 |", "| 정의 없음, R-001 |")), [])

    def test_concept_table_without_verdict_column_fails(self):
        text = COMPLETE.replace("| 단위 | 정의 | 정의한 곳 | 판정 |", "| 단위 | 정의 | 정의한 곳 | 결과 |")
        self.assertEqual(
            check_review.check_document(text),
            ["`## 개념과 정의` 절에 `판정` 열이 있는 단위 표가 없다: 단위마다 정의와 판정이 없으면 정의 없는 구조를 찾았는지 확인할 수 없다."],
        )

    def test_folded_document_passes(self):
        self.assertEqual(check_review.check_document(fold(COMPLETE)), [])

    def test_folded_empty_section_fails(self):
        text = fold(COMPLETE.replace("측정 없음: 측정 공백으로 기록한다.\n", ""))
        self.assertEqual(
            check_review.check_document(text),
            ["`## 품질` 절이 비어 있다: 판단이 없으면 `해당 없음: <이유>` 를 쓴다."],
        )

    def test_folded_document_without_verdict_paragraph_fails(self):
        text = fold(COMPLETE.replace("@author 판정은 변경 요청이며 head `abc`, finding 1건(MAJOR 1)이다.\n", ""))
        self.assertEqual(
            check_review.check_document(text),
            ["판정 첫 문단이 없다: 독자가 판정, head, finding 수를 첫 문단에서 찾지 못한다."],
        )

    def test_missing_section_names_folded_form(self):
        text = fold(COMPLETE).replace("<summary><h3>시험</h3></summary>", "<summary>시험</summary>")
        self.assertIn(
            "`## 시험` 절이 없다: 이 판단을 쓰지 않은 리뷰는 그 기준을 검토했는지 독자가 확인할 수 없다. "
            "50줄 넘는 글로 접었다면 그 제목 줄은 `<summary><h3>시험</h3></summary>` 로 쓴다.",
            check_review.check_document(text),
        )

    def test_old_grounds_paragraph_format_fails(self):
        text = "@a 판정은 승인이다.\n\n## 판정 근거와 구조·품질 판단\n순증가 1,937줄.\n\n## 검증 범위\n없음.\n"
        violations = check_review.check_document(text)
        self.assertEqual(len(violations), 8)
        self.assertTrue(any("`## 개념과 정의`" in v for v in violations))


if __name__ == "__main__":
    unittest.main()
