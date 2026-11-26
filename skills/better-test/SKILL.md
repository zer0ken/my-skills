---
name: better-test
description: Design behavior-focused tests, review a test refactor for lost fault detection, or look up testing principles and primary references. Use for /better-test, 테스트 설계, 테스트 검출력 검토, or 테스트 참고문서.
---

# Better tests

Start from the behavior the caller relies on. Choose the section that answers the request. For a bare invocation, give a short index of the three uses below with one example each. Answer in the user's language.

- **Design a test.** Read [Test design](references/design.md). Identify the entry point, initial state, discriminating input, observable result and one plausible defect. Return the smallest case that would expose that defect, with its expected failure. In a repository, name the actual test file and the fixture or public interface it should use.
- **Review a change to tests.** Read [Preserving fault detection](references/review.md). Compare the base and head tests together with their fixtures and CI selection. Report concrete lost behavior, evidence of equivalent coverage elsewhere, and unresolved candidates separately. If the user requests fixes, restore the missing observation and run its normal entry point.
- **Look up a testing principle.** Use the [annotated reference index](references/sources.md). Explain the term, give one example in the user's context, and link the relevant primary source. A reference request alone needs no repository change.

Example requests: `/better-test 배치 저장 API 테스트를 설계해줘`, `/better-test 이 diff에서 놓치게 된 결함을 찾아줘`, `/better-test test oracle과 mutation testing 참고문서를 보여줘`.
