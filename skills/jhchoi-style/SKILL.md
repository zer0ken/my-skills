---
name: jhchoi-style
description: "Write a Korean technical document (a PR, an issue, a design, a measurement report) as a paper-style PDF in the documentation and figure style of 최진혁 (Jinhyeok Choi, KAIST BDI Lab). Holds the section skeleton, caption and table conventions, hand-positioned SVG figures (as-is/to-be panels, stage pipelines, real values), the HTML and Chrome print-to-pdf path with its pagination traps, and the evidence rules for numbers and references. Use when the user asks for a paper-style PDF or for a document in jhchoi or 최진혁 style (논문처럼 정리, 논문 스타일 PDF, jhchoi 스타일로 문서 작성)."
metadata:
  author: hrlee
  version: "0.1.0"
  domain: writing
  triggers: 논문 스타일, 논문처럼, jhchoi, 최진혁, paper style, pdf 보고서, as-is to-be 그림
  role: producer
  scope: output
---

# jhchoi-style - 논문 형식 기술 문서

This skill produces one artifact: a Korean technical document, usually a PDF, written in the documentation and figure style of 최진혁 (Jinhyeok Choi). The style fits a change or a problem that a reader who did not follow the work must be able to check: notation is defined before it is used, every number names its record, and every figure shows a concrete example rather than a promise.

The style's sources, all read in full before writing:

| Source | What it contributes |
| --- | --- |
| 최진혁, MonTi, AAAI 2025 (arXiv:2412.18370) | as-is/to-be comparison panel with a marker legend row, the multi-stage pipeline figure, the check-mark comparison table |
| 최진혁, SpoT-Mamba, IJCAI 2024 STRL workshop (CEUR Vol-3827 paper6) | numbered sections with bold run-in sub-heads, symbol introduction in the problem section |
| 최진혁, DRAG, ICDM 2023 MLoG workshop (arXiv:2310.04171) | abstract and index terms, the order of sections |
| enterprise-memory issue #1554 | the same style written in Korean for a repository issue: numbered steps, `그림 N:` captions carrying real values, LaTeX symbols |

He is 최진혁, M.S. in Computing, KAIST, February 2025, Big Data Intelligence Lab (Joyce Jiyoung Whang). Check the lab page (`https://bdi-lab.kaist.ac.kr/`) before naming further papers; the name is common and a namesake's paper is not his.

Read the papers by looking at their pages, not only at their text: download each PDF (arXiv or CEUR), render the pages that hold figures with `pdftoppm -r 110 -png`, and inspect them. The style lives in the figures and in the caption wording.

A worked implementation to copy is `~/agent-assets/enterprise-memory/pr1386-paper/`: `paper.html`, `figs/*.svg`, `build.py`, and the rendered PDF. Read `paper.html` and one figure file before writing a new document, and copy their structure rather than describing it again.

## Document skeleton

1. Title: a noun phrase. A second line may name the mechanism the document proposes.
2. Author block: name, team, email. The document is the user's, so the user is the author.
3. Abstract: one paragraph in this order: the problem in the system's terms, why the existing behavior fails, what is proposed with its name, then the measured result numbers.
4. A note line under the abstract: which records the document summarizes (PR, issue, merge commit) and that unmeasured items are marked as such.
5. Numbered sections, in this order and with these jobs.

| Section | Content |
| --- | --- |
| 1. 서론 | The problem, with one concrete example of the symptom, then the contributions as a bullet list of three or four items, each stating what was built and what it measured |
| 2. 배경과 문제 정의 | The terms introduced in a running situation, then requirements R1..Rn as bullets, then the metrics and how each is measured |
| 3. 방법 | One subsection per mechanism, each explaining why that mechanism and not the obvious alternative |
| 4. 구현 | Where the contract lives: functions, constraints, schema, backend parity |
| 5. 검증 | Tests, quality, cost, and a case study, each naming the commit or run it came from |
| 6. 한계 | Each limitation with what it is, when it appears, and what the next measurement must separate |
| 7. 관련 연구 | Established methods the work connects to, each with what this work takes and what it adds |
| 8. 결론 | What was built and the numbers, without promises |
| 참고 문헌 | Numbered `[1]`, `[2]` in citation order |

6. Deeper structure is a bold run-in head at the start of the paragraph, not another numbering level: `<span class="runin">용어.</span> 설명`. The section titles stay noun phrases.
7. Equations are numbered on the right, `(1)`, `(2)`, and every symbol is defined in the sentence before.
8. A comparison table of the old and the new behavior belongs in the prose, not in a table, unless it fits in a column (see the layout traps).

The same skeleton without the PDF path serves a repository issue: numbered steps as `### 1. <단계>`, each step's bullets under it, a figure per step, and a `그림 N:` bullet that names the values in that figure, as enterprise-memory issue #1554 does.

## Figure conventions

A caption sits below its figure and starts with a bold `그림 N:` label. It states what is drawn, then what happens in it with the actual values the figure shows. A table caption sits above, starts with `표 N:`, and states the dataset, the unit, and what each column means.

| Element | Rule |
| --- | --- |
| as-is/to-be | Two panels of the same elements; unchanged parts in gray, changed parts in one accent color; a legend row of marker glyphs and short names at the bottom |
| pipeline | One row or one column of stages; the stage name outside the panel, below or to the left; arrows only where data flows |
| values | The figure carries the real values (distances, counts, thresholds, ids) that the measurement produced; a placeholder is a defect |
| labels | Short labels only; no sentences, no title, no explanation box inside the figure, because the caption carries them |
| palette | White background; ink `#14181f`, muted `#5c6673`, rule `#c6ccd4`, accent `#2f5bd3`; a second color only when it means a second thing |
| drawing | Hand-positioned SVG with explicit coordinates; no automatic layout, no Mermaid, no Graphviz |

`~/.agents/skills/visuals/SKILL.md` holds the general visual rules. Where it forbids a title inside a figure, this style agrees; where it asks for interaction, a printed PDF cannot provide it, so the interaction rules do not apply to this artifact.

## Production path

1. Write the body as one HTML file: A4, two columns (`column-count: 2; column-gap: 6.5mm`), body font `Noto Serif CJK KR`, figure labels `Noto Sans CJK KR`.
2. Keep each figure in its own SVG file under `figs/` and put a placeholder `<!--SVG:figN-->` in the HTML. A ten-line build script replaces the placeholders and writes the printable file, so the PDF keeps vector figures and a figure can be redrawn alone.
3. Print with an HTML-to-PDF renderer that keeps the SVG figures as vector output. The measured path is `google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer --print-to-pdf=out.pdf page.built.html`; another renderer is acceptable only after its pagination passes the same page-by-page check.
4. Verify by rendering every page, `pdftoppm -r 110 -png out.pdf pg`, and reading each page image. Fix overlaps, clipping, and a page left half empty, then render again. A page you did not look at is not verified.
5. Keep the PDF, the HTML source, `figs/`, the build script, and a README that lists the sources under `~/agent-assets/<project>/<asset>/`, and give the user the absolute path.

## Layout traps

Each of these was measured on 2026-11-23 while building the worked example.

1. `column-span: all` inside a multi-column container breaks Chrome's pagination: after the spanning block the columns collapse to one, or a page is left with two lines. Do not use it. Draw every figure and table at column width instead.
2. An SVG with only a `viewBox` and `height: auto` takes the default 150px height and is clipped. Write `width`, `height`, and `viewBox` together.
3. A 330-unit figure in an 86 mm column prints a 9-unit label at about 6.6pt. Design at column width with labels of at least 9 units; shrinking a wide drawing makes the figure unreadable in print.
4. A headless screenshot whose window is shorter than the figure scales or clips it. Screenshot with a window at least 200px taller than the figure, or judge from the rendered PDF page instead.
5. A table in a column fits at most four columns with short headers. A three-column comparison whose cells hold sentences splits Korean words into vertical fragments; remove that table and say the comparison in prose.
6. An equation with a number uses `display: grid; grid-template-columns: 1fr auto`, the formula centered in the first cell and the number in the second. Absolute positioning collides as soon as the formula is wide.
7. Each reference entry needs `break-inside: avoid`, or the column flow splits one entry across columns.
8. Korean body text is `text-align: left` with `word-break: keep-all`. Justifying a narrow Korean column stretches the spaces into rivers.

## Evidence

1. Every number names the record it came from: a commit, a measurement file, a CI run. The document says which conditions were not measured, in the section that reports the number.
2. Recompute derived numbers (percentages, differences, totals) from the raw measurement, not from another document's summary of it.
3. Verify each citation in its original source. When a claim rests on a source you could not verify, cite the repository record that holds the claim and say so in the report, as the worked example does for a clustering rule it could not trace to its paper.

## Korean prose

Write the body in Korean in the neutral technical written style of `~/.agents/skills/sucks/SKILL.md`: titles as noun phrases, no em dash, no exclamation mark, technical terms kept in English, and each fact tied to what it explains.
