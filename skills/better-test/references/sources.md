# Testing references by question

| Question | Primary source | What to look for |
| --- | --- | --- |
| Which interface should an assertion observe? | [Google Testing Blog, Test Behavior, Not Implementation](https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html) | A calculator changes its implementation while its public examples remain valid. Interaction checks still matter when the interaction itself fulfills a requirement. |
| Why does a test pass alone and fail in parallel? | [pytest, Flaky tests](https://docs.pytest.org/en/stable/explanation/flaky.html) | Shared state, teardown and order dependencies. Preserve the failing order and inspect the fixture's lifetime before relaxing an assertion. |
| How do I exercise many inputs against one rule? | [Hypothesis, Quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html) | Use a strategy to define the input domain and an assertion to express the property. Generation still needs a meaningful oracle. |
| What can mutation testing establish? | [Just et al., FSE 2014](https://homes.cs.washington.edu/~mernst/pubs/mutation-effectiveness-fse2014-abstract.html) | The authors compared mutant detection with detection of 357 real faults in five applications. The observed association does not turn a hand-picked sample into a suite-wide estimate. |

For a test oracle or boundary example, open [Designing a test](design.md). For a concrete mutation experiment with controls, open [Preserving fault detection](review.md).
