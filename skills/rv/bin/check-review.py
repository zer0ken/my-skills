#!/usr/bin/env python3
"""Reject an rv review that leaves out a mandatory judgment section or a review item.

rv requires each review to answer the concept-definition, design, functionality, size, quality, test,
naming, and cleared-scope questions in its own section. A review that folds them
into a short "grounds" paragraph lets size growth and duplication pass without a
written judgment, so this check fails such a document before it is posted.

rv also examines each review item of `references/items.md` in its own turn and
records it in the item ledger; a per-area item covers every area of its session
in that one turn and writes one row per area, so its rows share the turn. A
ledger that misses an item or an area, merges two items into one turn, leaves a
cell empty, or skips a sub-check makes the thoroughness of the review
unverifiable, so this check fails it too. With `--units`, the
areas of the per-area items must be the units of `bin/plan-units.py`, so a
unit that no row reviewed fails as well.

Round reviews use a visible summary table and folded HTML detail and judgment
sections. Archived Markdown reviews and their item ledgers remain readable.

Usage: check-review.py REVIEW.md --ledger LEDGER.md [--units units.json]
Exit codes: 0 the review and ledger pass, 1 a format violation,
2 a file could not be read.
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from xml.etree.ElementTree import Element, TreeBuilder
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
HEADING_RE = re.compile(r"^(?:## (.+?)\s*#*|<summary><h3>(.+?)</h3></summary>)\s*$")
FOLD_TAG_RE = re.compile(r"^\s*</?(?:details|summary)>\s*$")
CELL_SEPARATOR_RE = re.compile(r"(?<!\\)\|")
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
            sections.append((heading.group(1) or heading.group(2), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return preamble, sections


def content_lines(lines: list[str]) -> list[str]:
    return [
        line for line in lines if line.strip() and not COMMENT_RE.match(line) and not FOLD_TAG_RE.match(line)
    ]


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
        cells = CELL_SEPARATOR_RE.split(line.strip().removeprefix("|").removesuffix("|"))
        rows.append([cell.strip().replace("\\|", "|") for cell in cells])
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


class ReviewHTML(HTMLParser):
    """Build a tree of the posted fragment, including inline text in table cells."""

    def __init__(self):
        super().__init__()
        self.tree = TreeBuilder()
        self.tree.start("review", {})
        self.open_tags = []

    def handle_starttag(self, tag, attrs):
        self.tree.start(tag, dict(attrs))
        if tag in {"br", "hr", "img", "input", "wbr"}:
            self.tree.end(tag)
        else:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tree.start(tag, dict(attrs))
        self.tree.end(tag)

    def handle_endtag(self, tag):
        if not self.open_tags or self.open_tags.pop() != tag:
            raise ValueError(f"닫는 HTML 태그를 확인한다: {tag}")
        self.tree.end(tag)

    def handle_data(self, data):
        self.tree.data(data)

    def parse(self, source):
        self.feed(source)
        self.close()
        if self.open_tags:
            raise ValueError(f"닫히지 않은 HTML 태그: {self.open_tags[-1]}")
        self.tree.end("review")
        return self.tree.close()


def node_text(node: Element) -> str:
    return "".join(node.itertext()).strip()


def html_rows(table):
    return [[node_text(cell) for cell in row if cell.tag in {"td", "th"}]
            for row in table.iter("tr")]


def fold_title(fold, level):
    if len(fold) and fold[0].tag == "summary":
        heading = fold[0].find(level)
        if heading is not None:
            return node_text(heading)
    return ""


def check_round(text):
    try:
        root = ReviewHTML().parse(text)
    except ValueError as error:
        return [str(error)]
    folds = root.findall("details")
    if [fold_title(fold, "h2") for fold in folds] != ["지적 사항 상세", "기타 정보"]:
        return ["지적 사항 상세와 기타 정보를 이 순서로 접는다."]
    detail, info = folds
    opening = list(root)[:list(root).index(detail)]
    tables = [table for element in opening for table in element.iter("table")]
    if len(tables) != 1:
        return ["지적 사항 요약 표가 하나여야 한다."]
    rows = html_rows(tables[0])
    columns = "ID 심각도 신뢰도 근거 분류 이름 요약 권고".split()
    if not rows or rows[0] != columns:
        return ["지적 사항 요약 표의 열을 확인한다."]
    severities = ["BLOCKER", "MAJOR", "MINOR", "NIT"]
    confidence = ["높음", "조건부", "낮음"]
    titles, ranks, ids = [], [], set()
    for row in rows[1:]:
        if len(row) != len(columns) or not all(row):
            return ["요약 행에 빈 값 또는 열 누락이 있다."]
        rid, severity, trust, evidence, _, name, _, _ = row
        if not re.fullmatch(r"R-\d+", rid) or rid in ids:
            return ["지적 ID가 잘못되거나 중복되었다."]
        ids.add(rid)
        if severity not in severities or trust not in confidence or evidence not in {"재현", "관찰", "추론"}:
            return ["심각도, 신뢰도 또는 근거 값을 확인한다."]
        titles.append(f"{rid} {severity}: {name}")
        ranks.append((severities.index(severity), confidence.index(trust)))
    violations = []
    preamble = text.split("<details", 1)[0].split("<table", 1)[0]
    plain = re.sub(r"<[^>]+>", " ", preamble).replace("*", "")
    if not re.search(r"판정\s*[:/]?\s*(APPROVE|REQUEST_CHANGE|COMMENT)\b", plain):
        violations.append("여는말에 리뷰 판정을 적는다.")
    total = re.search(r"지적 사항 총계\s*[:/]?\s*(?:미해결\s*)?(\d+)\s*건", plain)
    if not total or int(total[1]) != len(rows) - 1:
        violations.append("지적 사항 총계와 요약의 행 수가 다르다.")
    counts = [(severity, str(sum(rank[0] == index for rank in ranks)))
              for index, severity in enumerate(severities) if any(rank[0] == index for rank in ranks)]
    if re.findall(r"\b(BLOCKER|MAJOR|MINOR|NIT)\s*[:/]?\s*(\d+)\s*건", plain) != counts:
        violations.append("심각도별 건수와 요약을 대조한다.")
    if ranks != sorted(ranks):
        violations.append("지적을 심각도와 신뢰도 순으로 정렬한다.")
    if titles != [fold_title(fold, "h3") for fold in detail.findall("details")]:
        violations.append("요약과 상세의 지적 ID, 심각도, 이름, 순서가 다르다.")

    # Reuse the judgment checks for both archived Markdown and the new HTML body.
    judgment_lines = ["판정"]
    for child in info:
        if child.tag == "summary":
            continue
        if child.tag == "h3":
            judgment_lines.append("## " + node_text(child))
        elif child.tag == "table":
            for index, row in enumerate(html_rows(child)):
                judgment_lines.append("| " + " | ".join(v.replace("|", r"\|") for v in row) + " |")
                if index == 0:
                    judgment_lines.append("|" + "---|" * len(row))
            judgment_lines.append("")
        else:
            judgment_lines.append(node_text(child))
    return violations + check_judgments("\n".join(judgment_lines))


def check_document(text: str) -> list[str]:
    if re.match(r"^# [1-9]\d*차 리뷰[ \t]*$", text.lstrip().splitlines()[0] if text.strip() else ""):
        return check_round(text)
    return check_judgments(text)


def check_judgments(text: str) -> list[str]:
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
                f"`## {required}` 절이 없다: 이 판단을 쓰지 않은 리뷰는 그 기준을 검토했는지 독자가 확인할 수 없다. "
                f"50줄 넘는 글로 접었다면 그 제목 줄은 `<summary><h3>{required}</h3></summary>` 로 쓴다."
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
    always: bool  # its 고르는 조건 is `항상`: it is never cleared in the selection turn


ITEMS_PATH = Path(__file__).resolve().parent.parent / "references" / "items.md"
CATALOG_SECTION = "Catalog"
LEDGER_COLUMNS = ("턴", "항목", "영역", "확인한 범위", "근거", "판정")
WHOLE_AREA = "전체"
ALWAYS = "항상"
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
    pick_col = header.index("고르는 조건")
    return {
        row[id_col]: Item(
            row[id_col],
            row[area_col] == "예",
            tuple(part.strip() for part in row[sub_col].split(",")),
            row[pick_col] == ALWAYS,
        )
        for row in rows[1:]
    }


def check_ledger(ledger: str, review: str, catalog: dict[str, Item]) -> list[str]:
    """Every item has its own turn, a complete row per area, and findings the review contains."""
    rows = table_rows(ledger.splitlines())
    if not rows or tuple(rows[0]) != LEDGER_COLUMNS:
        return [
            "항목 원장 표의 열이 `"
            + " | ".join(LEDGER_COLUMNS)
            + "` 가 아니다: 열이 고정되어야 항목마다 범위·근거·판정을 확인할 수 있다."
        ]
    review_ids = set(R_ID_RE.findall(review))
    violations: list[str] = []
    turn_rows: dict[str, list[tuple[str, bool]]] = {}
    seen: dict[str, list[str]] = {}
    for cells in rows[1:]:
        if len(cells) != len(LEDGER_COLUMNS):
            # The 턴, 항목, and 영역 cells come first and hold no `|`, so the row still counts for its item.
            padded = cells + [""] * len(LEDGER_COLUMNS)
            item_id, area = padded[1].strip("`"), padded[2]
            if item_id in catalog:
                seen.setdefault(item_id, []).append(area)
            violations.append(
                f"항목 원장의 `{item_id}` 행 칸이 {len(cells)}개다(열은 {len(LEDGER_COLUMNS)}개): "
                "칸 안의 `|` 는 GFM 표 규칙대로 `\\|` 로 쓴다. `&#124;` 는 백틱 안에서 글자 그대로 남으니 쓰지 말고, 칸을 지우거나 합치지 않는다."
            )
            continue
        row = dict(zip(LEDGER_COLUMNS, cells))
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
        else:
            cleared = verdict.startswith(NOT_APPLICABLE + ":") and not item.always
            turn_rows.setdefault(row["턴"], []).append((item_id, cleared))
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

    for turn, members in turn_rows.items():
        items = list(dict.fromkeys(item_id for item_id, _ in members))
        if len(items) > 1 and not all(cleared for _, cleared in members):
            # The selection turn may clear several conditional items together; any other turn holds one item.
            examined = items[1]
            violations.append(
                f"항목 원장의 턴 `{turn}` 에 `{items[0]}` 와 `{examined}` 가 함께 있다: 한 턴에는 한 항목만 검토한다. "
                f"한 턴에 여러 항목을 둘 수 있는 것은 고르는 조건에 맞지 않는 항목의 `{NOT_APPLICABLE}` 행만 쓰는 선별 턴뿐이다. "
                f"턴 값만 바꿔 맞추지 말고 `{examined}` 를 자기 턴에서 다시 검토하고 그 턴에서 행을 쓴다."
            )
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


def check_units(ledger: str, catalog: dict[str, Item], unit_ids: list[str]) -> list[str]:
    """The areas of the per-area items are exactly the units of the unit plan.

    U3 is split by review unit (`bin/plan-units.py`), so every hunk of the change
    is reviewed by the per-area items of the unit that holds it. A unit with no
    rows is a part of the change that nobody reviewed.
    """
    rows = table_rows(ledger.splitlines())
    if not rows or tuple(rows[0]) != LEDGER_COLUMNS:
        return []
    areas = {
        cells[2]
        for cells in rows[1:]
        if len(cells) > 2 and cells[1].strip("`") in catalog and catalog[cells[1].strip("`")].per_area
    }
    violations = [
        f"항목 원장에 단위 `{unit}` 의 영역별 항목 행이 없다: 이 단위의 hunk 를 아무도 리뷰하지 않았다. "
        f"행만 채우지 말고 `{unit}` 의 hunk 를 영역별 항목마다 리뷰한 뒤 그 턴에서 행을 쓴다."
        for unit in unit_ids
        if unit not in areas
    ]
    violations += [
        f"항목 원장의 영역 `{area}` 은 단위 계획에 없는 단위다: 영역은 `units.json` 의 단위 id 로 나눈다. "
        "영역 이름을 바꿔 맞추지 말고 그 행이 리뷰한 hunk 가 속한 단위 id 를 적는다."
        for area in sorted(areas - set(unit_ids))
    ]
    return violations


def read_unit_ids(path: str) -> list[str]:
    plan = json.loads(read_text(path))
    units = plan.get("units") if isinstance(plan, dict) else None
    if not isinstance(units, list) or not all(isinstance(u, dict) and isinstance(u.get("id"), str) for u in units):
        raise ValueError(f"{path} 는 plan-units.py 의 단위 계획이 아니다(`units` 목록과 각 단위의 `id` 가 없다). plan-units.py 로 다시 만든다")
    return [unit["id"] for unit in units]


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check an rv review document and its item ledger.")
    parser.add_argument("review", help="review markdown document")
    parser.add_argument("--ledger", required=True, help="item ledger markdown file (references/items.md)")
    parser.add_argument("--units", help="unit plan from bin/plan-units.py; the per-area rows must cover every unit")
    args = parser.parse_args(argv)
    try:
        review, ledger, catalog = read_text(args.review), read_text(args.ledger), read_catalog(read_text(str(ITEMS_PATH)))
        unit_ids = read_unit_ids(args.units) if args.units else None
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as error:
        print(f"읽기 실패: {error}", file=sys.stderr)
        return 2
    violations = [f"{args.review}: {v}" for v in check_document(review)]
    violations += [f"{args.ledger}: {v}" for v in check_ledger(ledger, review, catalog)]
    if unit_ids is not None:
        violations += [f"{args.ledger}: {v}" for v in check_units(ledger, catalog, unit_ids)]
    for violation in violations:
        print(violation)
    if violations:
        return 1
    print(f"rv review format: review and item ledger passed ({len(catalog)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
