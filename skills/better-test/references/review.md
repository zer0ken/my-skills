# Preserving fault detection during a test refactor

Read the base test before the replacement. Follow the fixture and helper calls to the last point where a wrong result could be observed. Record the comparison for each changed behavior.

| Base item and head item | Input and precondition | Actual entry point and dependency | Observation that must fail | CI selection and backend | Evidence or remaining gap |
| --- | --- | --- | --- | --- | --- |
| Example: old batch case → new shared-fixture case | 32 distinct edits, empty store | Public batch writer → storage adapter | Full mapping differs if only the first 16 edits persist | Verify the case is collected on the adapter it targets | Compare normal and truncated-writer runs |

Inspect reduced input sizes, omitted parameters that became explicit, full-result assertions narrowed to owned IDs, fake boundaries moved earlier, and independent cases merged into one sequence. A helper can retain the same name while changing setup or filtering out the failure. When CI selection changes, check both collection and the workflow event that actually schedules the suite.

**Paired mutation experiment.** Use this when inspection leaves a consequential gap. Pin base and head, choose one plausible defect and run the relevant unchanged product on both as controls. Apply the same defect in disposable checkouts. Record the failing item and its assertion. A control pass followed by the intended assertion failure detects the defect. A control pass followed by a mutant pass is a survivor. Explain an equivalent mutant only when the change cannot alter behavior in the stated domain. Record setup failures, timeouts and unexecuted cases separately. Keep the patch, commands, revisions and results together.

**Worked review finding.** A real optimization reduced a 32-edit integration case to smaller examples. Both normal suites were green. Given the same fault that saved only the first 16 edits, the old test failed and the reduced suite passed. Restoring the multi-edit case made the result length assertion fail again on that fault. The finding was the loss of a specific supported input and its observation. Line coverage and the number of passing items could not establish whether that input was still protected.

For each finding, name the base behavior, the wrong implementation that could pass, the replacement assertion and the evidence. Label a reasoned counterexample as a hypothesis until exercised. Report time savings separately from detection results and keep any detection rate scoped to the sampled faults.
