"""Pins check_pr_body.py to the body format of SKILL.md. Run: python3 test_check_pr_body.py"""
import unittest
from collections.abc import Sequence

from check_pr_body import check

GOOD = """Closes #12.
Refs #1111, #1112.

- LightRAG 질의 경로에 BM25 키워드 검색을 붙인다
  - 인덱스는 첫 질의 때 만든다

<details>
<summary><h3>배경과 범위</h3></summary>
<p>문서 추가만 포함한다. <code>null</code> 은 바꾸지 않는다.</p>
<pre><code>- literal `code`
</code></pre>
</details>
""".splitlines()


def rules(lines: Sequence[str]) -> list[str]:
    return [rule for _, rule, _ in check(lines)]


class CheckPrBodyTests(unittest.TestCase):
    def test_skill_format_passes(self) -> None:
        self.assertEqual(check(GOOD), [])

    def test_bare_heading_section_is_outside_details(self) -> None:
        self.assertEqual(check(GOOD + ["", "## 검증 범위", "본문"]),
                         [(14, "OUTSIDE", "after the summary write only <details> sections: ## 검증 범위")])

    def test_markdown_inside_details_is_refused(self) -> None:
        body = GOOD[:8] + ["- 목록", "[링크](https://example.com)"] + GOOD[8:]
        self.assertEqual(rules(body), ["HTML", "HTML"])

    def test_summary_over_ten_lines_is_refused(self) -> None:
        self.assertEqual(rules(GOOD[:3] + [f"- 항목 {n}" for n in range(11)] + GOOD[5:]), ["SUMMARY"])

    def test_refs_before_closes_is_refused(self) -> None:
        self.assertEqual(rules([GOOD[1], GOOD[0]] + GOOD[2:]), ["REFERENCE"])

    def test_section_needs_h3_summary(self) -> None:
        body = GOOD[:7] + ["<summary>배경</summary>"] + GOOD[8:]
        self.assertEqual(rules(body), ["DETAILS"])


if __name__ == "__main__":
    unittest.main()
