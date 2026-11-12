#!/usr/bin/env python3
"""Reject an rv review document that leaves out a mandatory judgment section.

rv requires each review to answer the design, functionality, size, quality, test,
naming, and cleared-scope questions in its own section. A review that folds them
into a short "grounds" paragraph lets size growth and duplication pass without a
written judgment, so this check fails such a document before it is posted.

Usage: check-review.py REVIEW.md [REVIEW.md ...]
Exit codes: 0 every document passes, 1 a document violates the format,
2 a document could not be read.
"""

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = (
    "설계와 원인",
    "기능과 완료 기준",
    "크기와 증가",
    "품질",
    "시험",
    "이름과 문서",
    "확인하고 배제한 항목",
    "검증 범위",
)
SIZE_SECTION = "크기와 증가"
NOT_APPLICABLE = "해당 없음"
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^## (.+?)\s*#*\s*$")
COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def split_sections(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Return the lines before the first level-2 heading and each level-2 section."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        heading = None if in_fence else HEADING_RE.match(line)
        if heading:
            sections.append((heading.group(1), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return preamble, sections


def content_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip() and not COMMENT_RE.match(line)]


def has_table(lines: list[str]) -> bool:
    return any(
        line.lstrip().startswith("|") and TABLE_SEPARATOR_RE.match(lines[index + 1])
        for index, line in enumerate(lines[:-1])
    )


def check_document(text: str) -> list[str]:
    preamble, sections = split_sections(text)
    violations: list[str] = []
    if not [line for line in content_lines(preamble) if not line.startswith("# ")]:
        violations.append(
            "판정 첫 문단이 없다: 독자가 판정, head, finding 수를 첫 문단에서 찾지 못한다."
        )

    titles = [title for title, _ in sections]
    positions = []
    for required in REQUIRED_SECTIONS:
        count = titles.count(required)
        if count == 0:
            violations.append(
                f"`## {required}` 절이 없다: 이 판단을 쓰지 않은 리뷰는 그 기준을 검토했는지 독자가 확인할 수 없다."
            )
        elif count > 1:
            violations.append(f"`## {required}` 절이 {count}번 있다: 같은 판단은 한 절에만 둔다.")
        else:
            positions.append((titles.index(required), required))

    ordered = [name for _, name in sorted(positions)]
    expected = [name for name in REQUIRED_SECTIONS if name in ordered]
    if ordered != expected:
        violations.append(
            "필수 절의 순서가 다르다: "
            + " → ".join(ordered)
            + ". 순서가 고정되어야 독자와 자동화가 같은 위치에서 판단을 찾는다."
        )
    if titles and titles[-1] != "검증 범위":
        violations.append(
            f"마지막 절이 `## {titles[-1]}` 이다: `## 검증 범위` 가 마지막이어야 실행하지 않은 검증이 끝에서 드러난다."
        )

    for title, lines in sections:
        if title not in REQUIRED_SECTIONS:
            continue
        body = content_lines(lines)
        if not body:
            violations.append(
                f"`## {title}` 절이 비어 있다: 판단이 없으면 `{NOT_APPLICABLE}: <이유>` 를 쓴다."
            )
        elif (
            title == SIZE_SECTION
            and not body[0].strip().startswith(NOT_APPLICABLE)
            and not has_table(lines)
        ):
            violations.append(
                f"`## {SIZE_SECTION}` 절에 base·head 차원별 표가 없다: 수치 비교 없이는 증가가 문제 해결에 비례하는지 판단할 수 없다."
            )
    return violations


def main(paths: list[str]) -> int:
    if not paths:
        print("Usage: check-review.py REVIEW.md [REVIEW.md ...]", file=sys.stderr)
        return 2
    status = 0
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"{path}: 읽기 실패: {error}", file=sys.stderr)
            return 2
        violations = check_document(text)
        for violation in violations:
            print(f"{path}: {violation}")
        if violations:
            status = 1
    if status == 0:
        print(f"rv review format: {len(paths)} document(s) passed")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
