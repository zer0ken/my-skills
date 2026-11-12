"""Pin the rv review format check: a complete document passes, each gap fails."""

import importlib.util
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


class CheckReviewTest(unittest.TestCase):
    def test_complete_document_passes(self):
        self.assertEqual(check_review.check_document(COMPLETE), [])

    def test_missing_section_fails(self):
        text = COMPLETE.replace("## 시험\n새 시험이 결함 코드에서 실패한다.\n\n", "")
        self.assertEqual(
            check_review.check_document(text),
            [
                "`## 시험` 절이 없다: 이 판단을 쓰지 않은 리뷰는 그 기준을 검토했는지 독자가 확인할 수 없다."
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
                "필수 절의 순서가 다르다: 설계와 원인 → 기능과 완료 기준 → 크기와 증가 → 시험 → 품질 → 이름과 문서 → 확인하고 배제한 항목 → 검증 범위. 순서가 고정되어야 독자와 자동화가 같은 위치에서 판단을 찾는다.",
                "마지막 절이 `## 부록` 이다: `## 검증 범위` 가 마지막이어야 실행하지 않은 검증이 끝에서 드러난다.",
            ],
        )

    def test_old_grounds_paragraph_format_fails(self):
        text = "@a 판정은 승인이다.\n\n## 판정 근거와 구조·품질 판단\n순증가 1,937줄.\n\n## 검증 범위\n없음.\n"
        violations = check_review.check_document(text)
        self.assertEqual(len(violations), 7)


if __name__ == "__main__":
    unittest.main()
