# Designing a test

A **test oracle** determines whether the observed behavior is correct. Derive the expected value from a contract, a hand-calculated example, an independent model or a property that valid outputs must satisfy. Reusing the production calculation to build the expectation can reproduce the same bug on both sides.

| Design question | Choose a case by asking |
| --- | --- |
| What can the caller observe? | Which return value, persisted state, emitted event, error, or externally required interaction would change if the feature broke? |
| Which inputs distinguish implementations? | Partition inputs by behavior. At a meaningful boundary, try the last valid and first invalid values. Consider omitted values separately from explicit defaults when callers can distinguish them. |
| Which dependency must be real? | Use a unit test for a pure rule. Keep the real serializer, transaction, process lifecycle or storage adapter when the defect could occur at that boundary. A fake should preserve the conditions the test claims to exercise. |
| What state carries between cases? | Own and clean up mutable data. Share expensive read-only setup. If the contract covers every returned row, isolate the dataset so an unexpected extra row stays observable. |
| How can failure be reproduced? | Control the clock or synchronization when elapsed time is incidental. When a real timeout or restart is the contract, exercise that transition with a bounded wait. Record inputs or a seed for generated cases. |

**Worked example.** A batch writer must persist every supplied ID and its value. A status code shows acceptance. A count still allows a duplicate to replace a missing row. For an example implementation with a 16-entry boundary, send 17 distinct entries through the writer and read the complete ID-to-value mapping from a clean store. A writer that drops entry 17 must fail the comparison. Keep a separate 32-entry input if it exposed a known regression and equivalence with the smaller input is unverified.

**Property-based testing.** When many inputs obey one rule, define the input domain and a property that constrains the result. For example, a lossless encoder must round-trip every supported value. Also keep fixed compatibility vectors when an encoder and decoder could agree on the same incorrect format.
