"""Pins check_pr_body.py to the body format of SKILL.md. Run: python3 test_check_pr_body.py"""
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from check_pr_body import check

VISUAL = "![같은 기사에서 뽑힌 정보: 변경 전과 변경 후](https://github.com/user-attachments/assets/0)"
GOOD = [VISUAL, ""] + """Closes #12.
Refs #1111, #1112.

- LightRAG 질의 경로에 BM25 키워드 검색을 붙인다
  - 인덱스는 첫 질의 때 만든다

<details>
<summary><h3>배경과 범위</h3></summary>
<p>문서 추가만 포함한다. <code>null</code> 은 바꾸지 않는다.</p>
<pre><code>- literal `code`
</code></pre>
</details>

<details>
<summary><h3>검증</h3></summary>
<p>단위 시험을 실행했다.</p>
</details>
""".splitlines()


def rules(lines: Sequence[str]) -> list[str]:
    return [rule for _, rule, _ in check(lines)]


class CheckPrBodyTests(unittest.TestCase):
    def test_skill_format_passes(self) -> None:
        self.assertEqual(check(GOOD), [])

    def test_bare_heading_section_is_outside_details(self) -> None:
        self.assertEqual(check(GOOD + ["", "## 검증 범위", "본문"]),
                         [(21, "OUTSIDE", "after the summary write only <details> sections: ## 검증 범위")])

    def test_markdown_inside_details_is_refused(self) -> None:
        body = GOOD[:10] + ["- 목록", "[링크](https://example.com)"] + GOOD[10:]
        self.assertEqual(rules(body), ["HTML", "HTML"])

    def test_summary_over_ten_lines_is_refused(self) -> None:
        self.assertEqual(rules(GOOD[:5] + [f"- 항목 {n}" for n in range(11)] + GOOD[7:]), ["SUMMARY"])

    def test_refs_before_closes_is_refused(self) -> None:
        self.assertEqual(rules(GOOD[:2] + [GOOD[3], GOOD[2]] + GOOD[4:]), ["REFERENCE"])

    def test_section_needs_h3_summary(self) -> None:
        body = GOOD[:9] + ["<summary>배경</summary>"] + GOOD[10:]
        self.assertEqual(rules(body), ["DETAILS"])

    def test_rule_between_sections_is_refused(self) -> None:
        body = GOOD[:15] + ["---", ""] + GOOD[15:]
        self.assertEqual(rules(body), ["SEPARATOR"])
        self.assertEqual(check(body)[0][0], 16)

    def test_sections_without_blank_line_are_refused(self) -> None:
        self.assertEqual(check(GOOD[:14] + GOOD[15:]),
                         [(15, "SEPARATOR", "separate consecutive <details> sections with exactly one blank line")])

    def test_trailing_rule_is_refused(self) -> None:
        self.assertEqual(rules(GOOD + ["", "---"]), ["SEPARATOR"])

    def test_body_without_change_visual_is_refused(self) -> None:
        self.assertEqual(rules(GOOD[2:]), ["VISUAL"])

    def test_visual_below_references_is_refused(self) -> None:
        self.assertEqual(check(GOOD[2:4] + ["", VISUAL] + GOOD[4:])[0][:2], (1, "VISUAL"))

    def test_visual_needs_blank_line_after_it(self) -> None:
        self.assertEqual(check([VISUAL] + GOOD[2:])[0][:2], (2, "VISUAL"))

    def test_html_visual_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "change.html").write_text("<p>x</p>")
            self.assertEqual([r for _, r, _ in check(["![변경 전과 후](change.html)"] + GOOD[1:], [Path(root)])],
                             ["VISUAL"])

    def test_local_visual_must_exist_and_passes_when_it_does(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            body = ["![변경 전과 후](./change.png)"] + GOOD[1:]
            self.assertEqual([r for _, r, _ in check(body, [Path(root)])], ["VISUAL"])
            (Path(root) / "change.png").write_bytes(b"\x89PNG")
            self.assertEqual(check(body, [Path(root)]), [])


if __name__ == "__main__":
    unittest.main()
