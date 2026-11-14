#!/usr/bin/env python3
"""Reject an rv review that leaves out a mandatory judgment section or a review item.

rv requires each review to answer the concept-definition, design, functionality, size, quality, test,
naming, and cleared-scope questions in its own section. A review that folds them
into a short "grounds" paragraph lets size growth and duplication pass without a
written judgment, so this check fails such a document before it is posted.

rv also examines each review item of `references/items.md` in its own turn and
records it in the item ledger. A ledger that misses an item, merges two items
into one turn, leaves a cell empty, or skips a sub-check makes the thoroughness
of the review unverifiable, so this check fails it too.

Usage: check-review.py REVIEW.md --ledger LEDGER.md
Exit codes: 0 the review and ledger pass, 1 a format violation,
2 a file could not be read.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

REQUIRED_SECTIONS = (
    "개념과 정의",
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
CONCEPT_SECTION = "개념과 정의"
VERDICT_COLUMN = "판정"
DEFINED = "정의됨"
FINDING_ID_RE = re.compile(r"\bR-?\d+\b")
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


def table_rows(lines: list[str]) -> list[list[str]]:
    """Return the cells of each row of the first table in lines, header first."""
    rows: list[list[str]] = []
    for line in lines:
        if not line.lstrip().startswith("|"):
            if rows:
                break
            continue
        if TABLE_SEPARATOR_RE.match(line):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def check_concepts(lines: list[str]) -> list[str]:
    """An undefined unit must become a finding: every row not judged defined names its R-ID."""
    body = content_lines(lines)
    if body and body[0].strip().startswith(NOT_APPLICABLE):
        return []
    rows = table_rows(lines)
    if not rows or VERDICT_COLUMN not in rows[0]:
        return [
            f"`## {CONCEPT_SECTION}` 절에 `{VERDICT_COLUMN}` 열이 있는 단위 표가 없다: 단위마다 정의와 판정이 없으면 정의 없는 구조를 찾았는지 확인할 수 없다."
        ]
    verdict_index = rows[0].index(VERDICT_COLUMN)
    violations = []
    for row in rows[1:]:
        verdict = row[verdict_index] if verdict_index < len(row) else ""
        if verdict != DEFINED and not FINDING_ID_RE.search(" ".join(row)):
            violations.append(
                f"`## {CONCEPT_SECTION}` 의 `{row[0].strip('`')}` 행이 `{DEFINED}` 이 아닌데 R-ID 가 없다: 정의 없는 단위는 서술이 아니라 finding 이다."
            )
    return violations


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
        elif title == CONCEPT_SECTION:
            violations.extend(check_concepts(lines))
        elif (
            title == SIZE_SECTION
            and not body[0].strip().startswith(NOT_APPLICABLE)
            and not has_table(lines)
        ):
            violations.append(
                f"`## {SIZE_SECTION}` 절에 base·head 차원별 표가 없다: 수치 비교 없이는 증가가 문제 해결에 비례하는지 판단할 수 없다."
            )
    return violations


class Item(NamedTuple):
    """One review item of the catalog in `references/items.md`."""

    id: str
    per_area: bool
    sub_checks: tuple[str, ...]


ITEMS_PATH = Path(__file__).resolve().parent.parent / "references" / "items.md"
CATALOG_SECTION = "Catalog"
LEDGER_COLUMNS = ("턴", "항목", "영역", "확인한 범위", "근거", "판정")
WHOLE_AREA = "전체"
CLEARED = "배제:"
TURN_RE = re.compile(r"^(.+):(\d+)$")
EVIDENCE_RE = re.compile(r"`[^`]+`|https?://|\S+:\d+")
R_ID_RE = re.compile(r"\bR-\d+(?:-C)?\b")


def read_catalog(text: str) -> dict[str, Item]:
    """Return the items of the `## Catalog` table, keyed by item id."""
    _, sections = split_sections(text)
    lines = next((body for title, body in sections if title == CATALOG_SECTION), [])
    rows = table_rows(lines)
    if not rows:
        raise ValueError(f"`## {CATALOG_SECTION}` 표가 없다")
    header = rows[0]
    id_col, area_col, sub_col = header.index("항목"), header.index("영역별"), header.index("세부")
    return {
        row[id_col]: Item(
            row[id_col],
            row[area_col] == "예",
            tuple(part.strip() for part in row[sub_col].split(",")),
        )
        for row in rows[1:]
    }


def check_ledger(ledger: str, review: str, catalog: dict[str, Item]) -> list[str]:
    """Every item has its own turn, a complete row, and findings the review contains."""
    rows = table_rows(ledger.splitlines())
    if not rows or tuple(rows[0]) != LEDGER_COLUMNS:
        return [
            "항목 원장 표의 열이 `"
            + " | ".join(LEDGER_COLUMNS)
            + "` 가 아니다: 열이 고정되어야 항목마다 범위·근거·판정을 확인할 수 있다."
        ]
    review_ids = set(R_ID_RE.findall(review))
    violations: list[str] = []
    turns: set[str] = set()
    seen: dict[str, list[str]] = {}
    for cells in rows[1:]:
        row = dict(zip(LEDGER_COLUMNS, cells + [""] * len(LEDGER_COLUMNS)))
        item_id, area, verdict = row["항목"].strip("`"), row["영역"], row["판정"]
        label = f"`{item_id}`({area})"
        item = catalog.get(item_id)
        if item is None:
            violations.append(f"항목 원장의 `{item_id}` 는 목록에 없는 항목이다: 항목은 `references/items.md` 목록에서만 고른다.")
            continue
        seen.setdefault(item_id, []).append(area)
        empty = [column for column in LEDGER_COLUMNS if not row[column]]
        if empty:
            violations.append(f"항목 원장의 {label} 행에 빈 칸이 있다({', '.join(empty)}): 빈 칸은 그 항목을 검토했는지 확인할 수 없게 한다.")
            continue
        if not TURN_RE.match(row["턴"]):
            violations.append(f"항목 원장의 {label} 행 턴 `{row['턴']}` 이 `<세션>:<번호>` 형식이 아니다.")
        elif row["턴"] in turns:
            violations.append(f"항목 원장의 턴 `{row['턴']}` 에 항목이 둘 이상이다: 한 턴에는 한 항목만 검토한다.")
        turns.add(row["턴"])
        if not item.per_area and area != WHOLE_AREA:
            violations.append(f"항목 원장의 {label} 행 영역이 `{WHOLE_AREA}` 가 아니다: 이 항목은 영역별 항목이 아니다.")
        if not EVIDENCE_RE.search(row["근거"]):
            violations.append(f"항목 원장의 {label} 행 근거에 `file:line`, 백틱 명령, URL 이 없다: 근거는 다시 확인할 수 있어야 한다.")
        cited = R_ID_RE.findall(verdict)
        if cited:
            missing = [rid for rid in cited if rid not in review_ids]
            if missing:
                violations.append(f"항목 원장의 {label} 행이 리뷰 문서에 없는 {', '.join(missing)} 를 가리킨다.")
        elif verdict.startswith(NOT_APPLICABLE + ":"):
            if not verdict[len(NOT_APPLICABLE) + 1 :].strip():
                violations.append(f"항목 원장의 {label} 행 `{NOT_APPLICABLE}` 에 이유가 없다.")
            continue
        elif not verdict.startswith(CLEARED) or not verdict[len(CLEARED) :].strip():
            violations.append(f"항목 원장의 {label} 행 판정이 R-ID, `{CLEARED} <이유>`, `{NOT_APPLICABLE}: <이유>` 가 아니다.")
        skipped = [check for check in item.sub_checks if check not in row["확인한 범위"]]
        if skipped:
            violations.append(f"항목 원장의 {label} 행 확인한 범위에 세부 점검 {', '.join(skipped)} 가 없다: 세부 점검마다 결과를 적는다.")

    areas = {area for item_id, areas_ in seen.items() if catalog[item_id].per_area for area in areas_}
    for item in catalog.values():
        expected = sorted(areas or {WHOLE_AREA}) if item.per_area else [WHOLE_AREA]
        got = seen.get(item.id, [])
        for area in expected:
            count = got.count(area)
            if count == 0:
                violations.append(f"항목 원장에 `{item.id}`({area}) 행이 없다: 모든 항목을 각자의 턴에서 검토해야 한다.")
            elif count > 1:
                violations.append(f"항목 원장에 `{item.id}`({area}) 행이 {count}개다: 한 항목은 영역마다 한 행이다.")
    return violations


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check an rv review document and its item ledger.")
    parser.add_argument("review", help="review markdown document")
    parser.add_argument("--ledger", required=True, help="item ledger markdown file (references/items.md)")
    args = parser.parse_args(argv)
    try:
        review, ledger, catalog = read_text(args.review), read_text(args.ledger), read_catalog(read_text(str(ITEMS_PATH)))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        print(f"읽기 실패: {error}", file=sys.stderr)
        return 2
    violations = [f"{args.review}: {v}" for v in check_document(review)]
    violations += [f"{args.ledger}: {v}" for v in check_ledger(ledger, review, catalog)]
    for violation in violations:
        print(violation)
    if violations:
        return 1
    print(f"rv review format: review and item ledger passed ({len(catalog)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
