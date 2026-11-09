---
name: teqr
description: "사용자가 /teqr 또는 $teqr로 직접 호출할 때만 근거 기반 기술 보고서, runbook, 실험 기록, 시험과 benchmark 계획을 작성하거나 수정한다. 리뷰나 문서 작성 요청, 다른 스킬의 참조만으로 자동 적용하지 않는다."
metadata:
  version: "1.0.1"
---

# teqr - technical report guide

에이전트는 사용자가 `/teqr`나 `$teqr`로 직접 호출한 경우에만 이 스킬을 적용한다. 리뷰나 문서 작성 요청, 다른 스킬의 참조는 호출을 대신하지 않는다.

Read [Technical Report Guide](TECHNICAL_REPORT_GUIDE.md) before writing or revising the requested document. Apply its evidence, terminology, structure, figure, table, and verification rules at the depth needed for the current task. Keep the user's requested format and destination; the guide's example structures do not require unnecessary sections.

## Supporting Guides

The supplied report guide references workspace documents that are not bundled here: `TECHNICAL_RETROSPECTIVE_GUIDE.md`, `SYSTEM_ANALYSIS_REPORT_GUIDE.md`, `REVISION_GUIDE.md`, `references/README.md`, and `references/charts/README.md`. Locate and read applicable resources in the target workspace when needed. Do not invent their contents or copy historical measurements from examples. If a resource is unavailable, continue with the supplied guide and disclose the limitation only when it affects the document or verification.

For code, design, and pull request review policy, use the `osiri` skill and its bundled `TECHNICAL_REVIEW_GUIDE.md` when available. Use this skill for the report-level evidence and presentation rules in a mixed task.

## Scope and Verification

Document existing evidence and distinguish measured results, inference, decisions, and unverified claims. A request to write a report or plan does not authorize running its benchmarks, changing product code, or publishing externally. Run only checks within the authorized task scope, and identify skipped checks and missing evidence without reporting them as passed.

Apply product-specific naming rules only when reporting on the named product. When figures are needed, default to a light theme and readable typography; use interactive visuals when they help exploration, and standalone exportable artifacts for report figures.

## Install and Update

PowerShell (Windows):

```powershell
irm https://raw.githubusercontent.com/zer0ken/skills/main/codex/teqr/install.ps1 | iex
```

Bash (macOS / Linux / WSL):

```bash
curl -fsSL https://raw.githubusercontent.com/zer0ken/skills/main/codex/teqr/install.sh | bash
```

Re-running the command installs the latest version. Start a new agent session to load it.
