---
name: visuals
description: Apply the user's visual preferences to HTML, UI, data charts, diagrams, slides, and other visual materials; read it before making any data chart. Use ztd-charts for data charts and hand-positioned SVG for structural diagrams, with a light theme, readable fonts, and interaction where possible.
metadata:
  version: "1.5.0"
---

# Visual materials

Apply these preferences when creating visual materials. An explicit different user request takes precedence. See `browser-render` for actual browser inspection and sharing.

## Theme and screen

Use a light theme, readable fonts, and interaction wherever possible. Developer-facing visualizations use these default tokens.

| Element | Default |
| --- | --- |
| Body | IBM Plex Sans KR |
| Code | IBM Plex Mono |
| Background | `#f6f7f9` |
| Panel | `#ffffff` |
| Body text | `#1d2430` |
| Accent | `#2f5bd3` |

Arrange the screen in this order: top bar, statistics chips, legend, SVG graph, detail panel. Provide node details and comparison toggles as needed. Edge meanings and colors follow the product's contract. Inspect the actual screen before applying a reference design. Style buttons and scrollbars with the page tokens; do not arbitrarily constrain body width with `max-width`. Apply `word-break: keep-all` to Korean text.

## Charts and diagrams

Use `ztd-charts` for data charts. Read the installed `~/.agents/skills/ztd-charts/SKILL.md` and its referenced chart schema before choosing channels and options. The shared CLI is `~/.local/bin/ztd-charts` (package `ztd-charts-cli`, runtime `~/.local/share/ztd-charts-runtime`); validate the spec before rendering and inspect the actual output. Use the light theme, Korean labels and `options.locale: "ko-KR"`; CLI rendering uses `--theme light --locale ko`. For example, run `ztd-charts validate spec.json` followed by `ztd-charts render spec.json --out chart.png --theme light --locale ko`. Keep the theme preferences above and real render checks. The hand-positioned SVG rule below continues to govern structural diagrams and other visuals outside data charts. For structural diagrams and visuals outside data charts, use SVG with explicitly chosen coordinates and paths; do not use automatic layout engines such as Mermaid or Graphviz. Give each figure one central point and highlight only its relevant elements. Lower context elements to grayscale and omit unrelated elements. Reduce crowding with grid alignment, consistent generous spacing, and two or three meaningful colors.

Flows run left to right and top to bottom. Draw arrows as smooth curves without crossings. Show only one unavoidable return path, with a dashed line. ERDs also follow the latest curved-line instruction: connect relationships at the referenced column's row and show multiplicity as `1` and `N`, never `0..*`.

Use short labels to identify what shapes, colors, bars, and points represent; do not convey meaning through color alone. Do not put titles, subtitles, explanatory sentences, or annotation boxes inside a figure; the PR change visual below is the one exception. Put numbering, captions, and explanations in the surrounding prose. Diagram-label rules do not apply to decorative abstract graphics.

## Structural visualization

For state machines, pipelines, and workflows, a row of nodes alone does not represent the graph. Express edge direction and type, returns (loops), branches, and joins as lines. Put lines behind nodes. Distinguish loop types by shape: judgment loops above nodes, dashed rework returns below nodes, coordination loops in a separate band outside the main flow. Include each node's contract so the structure can be read: gate id, machine or qualitative judgment, required loading count, artifacts, and execution count.

Every structural figure responds to interaction. Selecting a node opens contract details and leaves its incoming and outgoing edges prominent while lowering other edges. Provide branch/type filters and badge toggles. If the user points out that a delivered static figure lacks interaction, add interaction and structural expression instead of merely changing its layout.

Data is the source of the figure. Define nodes, edges, and loops first in a data file such as JSON. Pass referential integrity checks for missing vertices, duplicate ids, and invalid formats before rendering. Hardcoding structure in drawing code prevents interaction and filtering from understanding it.

Build controls only with APIs that actually exist. Check SDK type declarations for function names and parameters first. Do not invent navigation or opening functions and later report them as limitations. Omit unsupported interactions from the design and use an available action such as copying a value.

On surfaces that cannot load a library, such as a plugin runtime, use orthogonal paths and 1px lines at absolute coordinates instead of curves, and fix coordinates in a constant table. The edge, loop, and interaction requirements still apply.

## Explanation and examples

Explain structures and flows with figures; show the frame first for large visual work. Conceptual figures and figures with actual example values use the same layout and shapes, changing only labels to actual values. Connect the whole scene through one case selected from actual stored values and logs; never use unverified values.

When explaining a processing unit, first show a data structure with actual values and its reference rules. Separate a pipeline's stage graph from the timeline of actual execution records. In a timeline, give each document a horizontal lane with a light background, show stages as rectangles with distinct colors, and represent concurrent execution in subrows within the lane. Stage colors match the structural figure.

Every PR body opens with the change visual described in the next section; conceptual diagrams of a large PR go beside their related paragraphs. Explain behavior through concrete example data instead of module/function lists.

For an as-is structure, first inspect the code that computes each element's position, such as rectangle calculations and layout branches, and check every sketch element against that code. For a to-be structure, compare each confirmed decision with the figure and follow the decision wherever the two disagree. Independent surfaces such as popups and borders remain separate even when touching.

## PR change visual

The change visual is the one image at the top of a PR body that shows what the PR changes at a glance; the `pr` skill (`~/.agents/skills/pr/SKILL.md`, "Change visual") holds the requirement and how it is posted. It takes one of two forms by the kind of change. The user's words (2026-11-17), after approving three as-is/to-be examples: "기능 변경의 경우 이런 시각화가 유용하고, 성능 개선의 경우는 chart 시각화를 넣어라."

A change of behaviour or output uses the as-is/to-be drawing: a hand-positioned SVG that draws what the change does to the same real input in both states, `AS-IS · main` and `TO-BE · 이 PR`. **The change visual is a drawing, not text in boxes.** The user's words (2026-11-17), shown PR change visuals that listed each state's items as text rows in boxes: "야. PR에 그림 넣는거, (…) 그냥 글자만 대충 상자 안에 넣고 올리잖아. 장난하냐? 그림을 그리라고 그림을", then "SVG 몰라?" and "강조해". So the body is an SVG whose shapes, positions, connectors, and arrows carry the change, with text only as short labels on them, as the "Charts and diagrams" and "Structural visualization" sections describe; two columns of text rows, with or without colored tags, are not a change visual however the rows are styled.

Choose the drawing by what the change acts on, and draw that thing:

| The change acts on | Draw |
| --- | --- |
| Flow of data, such as which input becomes which output | The input pieces and the outputs as shapes joined by arrows; a dropped path ends in a cut mark where it stops |
| Relations, such as a reference, a merge, or a split | Nodes and the edges between them, with the new or removed edge in the accent color |
| Time, such as a lifetime, an order, a timeout, or a retry | One shared time axis with a lane per state and bars for what lives when, the event that ends each bar drawn as an arrow from its cause |
| Text, such as a document, a rule, or a prompt | The real passage before and after, with the changed spans marked on the text and joined to what they cause |

Each state comes from the same real input, read from an actual run of the base commit and of the PR head, or the actual text of the file before and after. What the change touches is in the accent color, what the change removes stays in place in gray with its path cut, so the two states line up, and unchanged parts stay neutral gray. Each state ends with one line of numbers that measures the difference, such as the count of extracted items. Pick the input that shows the difference most plainly and cut it to the part where the difference lies.

A performance change uses a `ztd-charts` chart of the measured or proved numbers, main against this PR for each case, such as a grouped bar of the two values per case or a bar of the speedup per path. Write the spec and render it as the "Charts and diagrams" section says.

Both forms share one card style, the `ztd-charts` light theme card: a title, a one-line subtitle naming what is compared, the body, a bold one-line takeaway at the bottom, one accent color for what changed and neutral gray for the rest, and a small source line naming the input or the measurement. The user's words (2026-11-17), asking for this while the examples were made: "디자인 스타일을 좀 통일해주면 좋겠어", and, told that the card puts a title inside the figure against the rule above: "좋아. 일단 이렇게 하자". So the rule against titles and explanatory sentences inside a figure does not apply to the change visual. For the as-is/to-be drawing, write HTML on `examples/card.css`, which holds the theme tokens, the card frame, and the SVG classes, with the drawing as an inline `<svg class="fig">` between the subtitle and the takeaway, with a `fonts/` directory beside it holding the Pretendard files copied from `~/.local/share/ztd-charts-runtime/node_modules/ztd-charts-cli/fonts`, and render it to PNG with `~/.agents/skills/browser-render/SKILL.md` using `--viewport 900x100 --fullpage`, which keeps the page 900px wide, about the width GitHub shows a body at, and grows its height to the content. Inspect the PNG before posting: Korean text renders in Pretendard, nothing overlaps or is clipped, the difference is visible without zooming, and a reader who skips every label still sees what changed from the shapes and arrows.

The examples in `examples/` are drawn on placeholder data for shape only; a real PR uses real data. `pr1415` (flow: lines without facts cut before they become nodes), `pr1437` (relation: a `refers_to` edge merges two nodes), and `container-cleanup` (time: a container's lifetime after its runner is killed, ended by Ryuk) are as-is/to-be drawings, each as its HTML source and PNG. `pr1460-chart` (keyword search: p50 speedup per path) and `pr1423-chart` (thread count, main against this PR per case) are performance charts, each as its `ztd-charts` spec and PNG.

## Render verification

Before publishing, inspect PNG output and the actual publishing width for overlaps, clipping, and label readability. Also inspect GitHub-body diagrams at about 900px width. If `rsvg-convert` cannot interpret CSS variables, render a copy with substituted values and preserve the original. Report a render issue as fixed only after inspecting the actual result. Follow `browser-render` for links accessible in the user's browser and for sharing scope.

For PPTX work, first read `~/.pi/agent/rules-optional/pptx-authoring.md` if it exists. If absent, do not infer its contents; report the constraints actually confirmed.
