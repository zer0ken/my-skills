---
name: visuals
description: Apply the user's visual preferences to HTML, UI, data charts, diagrams, slides, and other visual materials; read it before making any data chart. Use ztd-charts for data charts and hand-positioned SVG for structural diagrams, with a light theme, readable fonts, and interaction where possible.
metadata:
  version: "1.1.0"
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

Use short labels to identify what shapes, colors, bars, and points represent; do not convey meaning through color alone. Do not put titles, subtitles, explanatory sentences, or annotation boxes inside a figure. Put numbering, captions, and explanations in the surrounding prose. Diagram-label rules do not apply to decorative abstract graphics.

## Structural visualization

For state machines, pipelines, and workflows, a row of nodes alone does not represent the graph. Express edge direction and type, returns (loops), branches, and joins as lines. Put lines behind nodes. Distinguish loop types by shape: judgment loops above nodes, dashed rework returns below nodes, coordination loops in a separate band outside the main flow. Include each node's contract so the structure can be read: gate id, machine or qualitative judgment, required loading count, artifacts, and execution count.

Every structural figure responds to interaction. Selecting a node opens contract details and leaves its incoming and outgoing edges prominent while lowering other edges. Provide branch/type filters and badge toggles. If the user points out that a delivered static figure lacks interaction, add interaction and structural expression instead of merely changing its layout.

Data is the source of the figure. Define nodes, edges, and loops first in a data file such as JSON. Pass referential integrity checks for missing vertices, duplicate ids, and invalid formats before rendering. Hardcoding structure in drawing code prevents interaction and filtering from understanding it.

Build controls only with APIs that actually exist. Check SDK type declarations for function names and parameters first. Do not invent navigation or opening functions and later report them as limitations. Omit unsupported interactions from the design and use an available action such as copying a value.

On surfaces that cannot load a library, such as a plugin runtime, use orthogonal paths and 1px lines at absolute coordinates instead of curves, and fix coordinates in a constant table. The edge, loop, and interaction requirements still apply.

## Explanation and examples

Explain structures and flows with figures; show the frame first for large visual work. Conceptual figures and figures with actual example values use the same layout and shapes, changing only labels to actual values. Connect the whole scene through one case selected from actual stored values and logs; never use unverified values.

When explaining a processing unit, first show a data structure with actual values and its reference rules. Separate a pipeline's stage graph from the timeline of actual execution records. In a timeline, give each document a horizontal lane with a light background, show stages as rectangles with distinct colors, and represent concurrent execution in subrows within the lane. Stage colors match the structural figure.

For a large PR, distinguish an abstract introductory figure before the body from conceptual diagrams beside their related paragraphs. Explain behavior through concrete example data instead of module/function lists.

For an as-is structure, first inspect the code that computes each element's position, such as rectangle calculations and layout branches, and check every sketch element against that code. For a to-be structure, compare each confirmed decision with the figure and follow the decision wherever the two disagree. Independent surfaces such as popups and borders remain separate even when touching.

## Render verification

Before publishing, inspect PNG output and the actual publishing width for overlaps, clipping, and label readability. Also inspect GitHub-body diagrams at about 900px width. If `rsvg-convert` cannot interpret CSS variables, render a copy with substituted values and preserve the original. Report a render issue as fixed only after inspecting the actual result. Follow `browser-render` for links accessible in the user's browser and for sharing scope.

For PPTX work, first read `~/.pi/agent/rules-optional/pptx-authoring.md` if it exists. If absent, do not infer its contents; report the constraints actually confirmed.
