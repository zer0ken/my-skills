# Sources for llm-expert

F01 supplies the ten-area chapter structure; F02 supplies author-written summaries. P01 and R01 supply survey taxonomies, E04 supplies judge meta-evaluation dimensions, and E02 supplies a conference experiment with explicit scope. Product-maintainer documentation and engineering articles supply attributed implementation guidance. The bounded search did not establish a formal professional body of knowledge for the whole field. No claim of universal consensus is made.

Practice-source selection: the reference is an author-published engineering book companion; provider and engine guidance comes from maintainers operating the systems concerned. This establishes provenance and practical relevance, not an independently measured level of community acceptance. The publisher page was readable in the browser but returned HTTP 403 to curl, so it is excluded from cited evidence.

The quoted source locations were fetched with curl -sSL -m 20. Quote matching uses the saved response body directly or its extracted HTML text, with only entity decoding and whitespace normalization. A matching quotation verifies location, not the truth or generality of all nearby claims. Evidence-table.json records timestamps, hashes, search provenance, limits and unsurveyed scope.

| ID | URL | Section read | Quoted sentence or contents heading | HTTP status | Quote found |
| --- | --- | --- | --- | --- | --- |
| F01 | [AI Engineering table of contents](https://raw.githubusercontent.com/chiphuyen/aie-book/refs/heads/main/ToC.md) | Contents: chapters 1-10; evaluation pipeline, structured outputs, inference, architecture | Step 1. Evaluate All Components in a System | 200 | yes |
| F02 | [AI Engineering chapter summaries](https://raw.githubusercontent.com/chiphuyen/aie-book/refs/heads/main/chapter-summaries.md) | Chapter summaries 1-4 and 10 | Working with AI models requires building your workflows around their probabilistic nature. | 200 | yes |
| P01 | [The Prompt Report](https://arxiv.org/html/2406.06608v6) | Sections 1.1-1.2, 2.2 and 4.2: terminology, components, prompting techniques, evaluation | The lack of a consistent vocabulary hampers the community’s ability to clearly describe the various prompting techniques in use. | 200 | yes |
| E01 | [Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) | Terminology; grader types; capability/regression; steps 2, 3, 5, 6; production evaluation | Ambiguity in task specifications becomes noise in metrics. | 200 | yes |
| E02 | [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://papers.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract-Datasets_and_Benchmarks.html) | Conference abstract; linked paper sections 3-4 and position-bias analysis read using browser | To address this, we explore using strong LLMs as judges to evaluate these models on more open-ended questions. | 200 | yes |
| E03 | [Define success criteria and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests) | Success criteria; task-specific evals and edge cases; held-out evaluation diagram; grading methods | Most use cases need multidimensional evaluation along several success criteria. | 200 | yes |
| P02 | [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | How it works; SDK schema transformation; JSON Schema limitations; invalid outputs | The output might not match your schema because the refusal message takes precedence over schema constraints. | 200 | yes |
| P04 | [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) | JSON mode comparison; handling user-generated input and mistakes; schema divergence; refusals/incomplete output | Structured Outputs can still contain mistakes. | 200 | yes |
| R01 | [Retrieval-Augmented Generation for Large Language Models: A Survey](https://arxiv.org/html/2312.10997v5) | II: Naive/Advanced/Modular RAG and failure categories; III-V components; VI-C quality dimensions | The retrieval phase often struggles with precision and recall, leading to the selection of misaligned or irrelevant chunks, and the missing of crucial information. | 200 | yes |
| A01 | [Building effective agents](https://www.anthropic.com/research/building-effective-agents) | Workflow/agent definitions; complexity; frameworks; named workflow patterns | Workflows are systems where LLMs and tools are orchestrated through predefined code paths. | 200 | yes |
| I01 | [On Evaluating Performance of LLM Inference Systems](https://arxiv.org/html/2507.09019v1) | Sections 2-3: inference phases, metrics, and evaluation anti-patterns | Focusing solely on summary statistics (like median latency) while ignoring the full performance distribution is a prevalent anti-pattern. | 200 | yes |
| I02 | [Optimization and Tuning](https://docs.vllm.ai/en/latest/configuration/optimization/) | Preemption; chunked prefill; parallelism tradeoffs | While this mechanism ensures system robustness, preemption and recomputation can adversely affect end-to-end latency. | 200 | yes |
| I03 | [Automatic Prefix Caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/) | Introduction; shared-prefix reuse; limits | This helps when many requests share a long system prompt and then diverge. | 200 | yes |
| I04 | [Production Metrics](https://docs.vllm.ai/en/latest/usage/metrics/) | Production metrics: queue/running requests, tokens, cache, preemptions, latency histograms | These metrics are exposed via the /metrics endpoint on the vLLM OpenAI compatible API server. | 200 | yes |
| I05 | [Reproducibility](https://docs.vllm.ai/en/v0.20.1/usage/reproducibility/) | Reproducibility requirements and seeding | Even with the above settings, vLLM only provides reproducibility when it runs on the same hardware and the same vLLM version. | 200 | yes |
| E04 | [A survey on LLM-as-a-judge](https://pmc.ncbi.nlm.nih.gov/articles/PMC13237853/) | Background/method; evaluation of LLM-as-a-judge: human agreement, bias, adversarial robustness | These include methods to mitigate biases, control variability, and confirm robustness against adversarial inputs. | 200 | yes |

F01 is a table of contents and therefore quotes a heading rather than inventing a prose sentence. E02 uses the conference abstract for the mechanical check; the linked full paper was read with the browser. Neither is represented as a successful curl fetch of the full paper.

## Excluded access attempts

| URL | Fetch result | Disposition |
| --- | --- | --- |
| https://www.oreilly.com/library/view/ai-engineering/9781098166298/ | HTTP 403; no verified quotation | Not cited by SKILL.md. |
| https://papers.neurips.cc/paper_files/paper/2023/file/91f18a1287b398d378ef22505bf41832-Paper-Datasets_and_Benchmarks.pdf | Incomplete PDF; pdftotext rejected missing trailer/xref | Replaced by the conference HTML publication record for mechanical verification. |

## Verification scope

All sixteen cited URLs returned HTTP 200 with curl exit 0, and all sixteen quotations matched their captures. SKILL.md citation IDs, frontmatter, ten knowledge areas and the 250-line limit were checked. No live LLM quality evaluation, server measurement, finetuning, deployment, security test, or independent expert review was performed.
