---
name: teqr
description: "Write or revise evidence-based technical reports, runbooks, experiment records, and test and benchmark plans, only when the user calls /teqr or $teqr directly. Do not apply automatically on a request for a review or for document writing, or on a reference from another skill alone."
metadata:
  version: "1.0.2"
---

# teqr - technical report guide

The agent applies this skill only when the user called it directly with `/teqr` or `$teqr`. A request for a review or for document writing, or a reference from another skill, does not stand in for the call.

Read [Technical Report Guide](TECHNICAL_REPORT_GUIDE.md) before writing or revising the requested document. Apply its evidence, terminology, structure, figure, table, and verification rules at the depth needed for the current task. Keep the user's requested format and destination; the guide's example structures do not require unnecessary sections.

## Supporting Guides

The supplied report guide references workspace documents that are not bundled here: `TECHNICAL_RETROSPECTIVE_GUIDE.md`, `SYSTEM_ANALYSIS_REPORT_GUIDE.md`, `REVISION_GUIDE.md`, `references/README.md`, and `references/charts/README.md`. Locate and read applicable resources in the target workspace when needed. Do not invent their contents or copy historical measurements from examples. If a resource is unavailable, continue with the supplied guide and disclose the limitation only when it affects the document or verification.

For code, design, and pull request review policy, use the `osiri` skill and its bundled `TECHNICAL_REVIEW_GUIDE.md` when available. Use this skill for the report-level evidence and presentation rules in a mixed task.

## Scope and Verification

Document existing evidence and distinguish measured results, inference, decisions, and unverified claims. A request to write a report or plan does not authorize running its benchmarks, changing product code, or publishing externally. Run only checks within the authorized task scope, and identify skipped checks and missing evidence without reporting them as passed.

Apply product-specific naming rules only when reporting on the named product. When figures are needed, default to a light theme and readable typography; use interactive visuals when they help exploration, and standalone exportable artifacts for report figures.
