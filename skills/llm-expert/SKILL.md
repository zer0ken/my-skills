---
name: llm-expert
description: Apply source-backed AI engineering knowledge when designing LLM pipelines, prompts, output contracts, structured outputs, evaluation sets, error analysis, LLM judges, or model-serving resource and cost decisions. Covers applications built on existing models rather than training foundation models.
metadata:
  version: "1.0.0"
---

# LLM application engineering

This skill concerns applications built on existing foundation models: their adaptation, evaluation, and inference. Its scope follows the application-engineering reference in [F01, F02]. Database internals, general concurrency correctness, and programming-language design remain outside this skill's boundary.

The numbered knowledge areas follow the chapter order of Chip Huyen's *AI Engineering*, using the author's published contents and chapter summaries [F01, F02]. This is a practice-reference structure, not a claim that the field has a standardized body of knowledge. The Prompt Report explicitly identifies inconsistent and developing terminology [P01]. Provider engineering articles below are attributed practice; surveys and experiments retain their stated scope, rather than becoming universal laws [P01, E02, A01, I01]. Source IDs resolve in [sources.md](sources.md).

## 1. Applications built on foundation models [F01]

Application engineering adapts available models to a use case; selecting a model and evaluating the resulting application are distinct from developing a foundation model [F02].

Task fidelity, consistency, latency, and price are separate application criteria. Replace labels such as “good output” with task-specific measurable criteria or an explicit qualitative scale. A benchmark's example thresholds are not defaults for another application [E03].

## 2. Understanding foundation models [F01]

Training data, model architecture, post-training, and sampling affect the behavior of a ready-made model. Coverage of a general model's training data does not establish capability on the application's language or domain [F02].

Identify the actual model/checkpoint, tokenizer and chat template, SDK/API, serving engine, hardware, and relevant generation/decoding settings from the working system. Consult the documentation for those actual versions before relying on feature support, parameter names, defaults, or numerical reproducibility; the cited product pages are examples to refresh, not fixed deployment specifications [P02, P04, I05].

### Structured output and its contract

Distinguish parseable JSON, compliance with a supported schema, and semantic correctness. OpenAI documents that Structured Outputs can still make mistakes. An output contract therefore needs semantic evaluation as well as parsing/schema validation [P04].

Constrained decoding enforces an allowed output grammar. Schema support and SDK transformations are product-specific: Claude's documentation distinguishes the schema sent to the model from constraints enforced by a validating SDK helper. Check which constraints are actually enforced; wording a constraint in a field description does not turn it into a decoder constraint [P02].

Handle documented refusal and incomplete-output cases as distinct response states. A successful HTTP status alone does not prove a completed schema-conforming answer. Keep schema definitions and application types consistent through supported schema helpers or generation, rather than maintaining divergent copies [P02, P04].

## 3. Evaluation methodology [F01]

A grader scores behavior, a transcript records interactions, and an outcome is final environment state. Check state-changing tasks against their outcomes [E01].

| Grader | Appropriate evidence | Limitation |
| --- | --- | --- |
| Code-based | Executable conditions | Can reject valid variation. [E01] |
| Model-based | Open-ended responses | Requires human calibration. [E01] |
| Human | Expert judgments | Expensive. [E01] |

Validate an LLM judge against human judgments; specify each grading dimension and permit unknown judgments. Vague rubrics produce inconsistent scores [E01].

The judge survey separates agreement with human judgments, bias, and adversarial robustness. Use agreement measures such as Cohen's kappa or Spearman correlation as appropriate to the labels or scores; inspect position consistency, length sensitivity, and robustness to prompt variations separately. These dimensions measure different failure modes, so agreement alone does not establish reliability [E04].

The MT-Bench study identifies position bias, verbosity bias, self-enhancement bias, and reasoning limitations. Its agreement findings concern particular models, tasks, and raters, not an accuracy guarantee for a new judge [E02]. As an application of these findings, check whether changing answer order or irrelevant verbosity changes a verdict; investigate disagreements rather than treating a confident explanation as correctness evidence [E02].

## 4. Evaluating AI systems [F01]

Use evaluation data that reflects the application's task distribution and edge cases, including missing, irrelevant, ambiguous, and unusually long inputs. Keep held-out evaluation separate from prompt refinement. Select metrics appropriate to the task instead of substituting an unrelated public benchmark [E03].

Capability evaluation measures abilities; regression evaluation checks retained behavior [E01].

### Diagnosis of bad results

Read failed transcripts and grades to distinguish agent errors from ambiguous tasks, incorrect grading, and harness/environment constraints [E01].

Evaluate all system components, not only the final model response. Localize a RAG failure to retrieval, generation, or integration of retrieved information; missing evidence and failure to use supplied evidence are different diagnoses [F01, R01].

Isolate trials: leftover state and resource exhaustion can correlate failures or inflate scores [E01].

## 5. Prompt engineering [F01]

A prompt is the instantiated model input; a prompt template produces that input by substituting variables. Evaluate the instantiated input rather than assuming the template is what the model received [P01].

The Prompt Report distinguishes directive, examples, output formatting, style instructions, role, and additional information. Give each its stated meaning: a role/persona is a prompt component, while task competence is established by evaluation. “Context” is overloaded in the literature; name whether it means supplied task information or tokens processed by the model [P01, E03].

Few-shot prompting supplies demonstrations; prompt chaining passes one template's output into subsequent templates. The survey catalogs multiple technique families rather than prescribing one technique for every task. Its output-formatting discussion contains conflicting empirical findings: measure the chosen format on the actual task instead of assuming structured output always improves or harms accuracy [P01].

Schema descriptions, examples, and instructions must express the same intended output. Treat format and semantic checks separately, and assess changed schema wording or structure with task evaluations. Use native schema facilities where supported rather than relying solely on prose to obtain machine-readable output [P02, P04].

## 6. RAG and agents [F01]

### Retrieval-augmented generation

RAG supplies retrieved external information to a generator. The survey separates retrieval, generation, and augmentation, and describes Naive, Advanced, and Modular RAG. “Naive RAG” names a baseline indexing/retrieval/generation paradigm, not proof that every instance is defective [R01].

The survey's failure categories are retrieval precision/recall problems, unsupported or irrelevant generation, and augmentation problems such as redundant or incoherently integrated evidence. Measure context relevance, answer faithfulness to retrieved information, and answer relevance separately; a faithful answer can still lack information the retriever missed [R01].

Choose retrieval or generation changes against the corresponding failure category. A more elaborate retrieval pipeline is not itself evidence of higher answer quality [R01].

### Workflows and agents

Use Anthropic's architectural distinction explicitly: a workflow follows predefined code paths; an agent lets the LLM direct its process and tool use. Its article warns that “agent” has multiple meanings. State which control model a component implements instead of using the label for both [A01].

Anthropic's patterns include prompt chaining, routing, parallelization, orchestrator-workers, and evaluator-optimizer. They have different conditions: chaining suits fixed decomposable subtasks; routing directs inputs to specialized tasks; evaluator-optimizer requires clear evaluation criteria and measurable improvement [A01].

Start with the least complex arrangement that satisfies measured needs. Additional calls and autonomous control trade latency and cost for potential task gains. Anthropic identifies abstraction layers that obscure actual prompts and responses, and unnecessary agentic complexity, as sources of debugging difficulty and errors [A01].

## 7. Finetuning [F01]: unsurveyed

The contents identify this knowledge area, but finetuning methods and selection criteria have not been surveyed for this draft. No finetuning prescription is supplied.

## 8. Dataset engineering [F01]: unsurveyed

Training-data curation, synthesis, and distillation have not been surveyed for this draft. Evaluation-set design is covered under area 4; it does not establish expertise in training-dataset engineering.

## 9. Inference optimization [F01]

### Inference process and metrics

Autoregressive inference has prefill and decode phases with different resource demands. Treat compute-bound prefill and memory-bandwidth-bound decode as the surveyed serving model, then confirm the actual bottleneck for the workload, architecture, and engine [I01].

Distinguish time to first token (TTFT), time between tokens (TBT), total latency, and serving capacity under application latency limits. Aggregate throughput alone does not establish an interactive system's capacity [I01].

The inference-evaluation paper names anti-patterns: unequal implementation effort or tuning, irrelevant models, nonrepresentative workloads, ignoring practical latency bounds, opaque metrics, summary-only statistics, and normalization hiding user-facing stalls. Compare workloads and tuning fairly, and retain latency distributions and absolute user-visible times [I01].

### Serving resources and repeated work

KV-cache pressure can cause vLLM to preempt and recompute requests, worsening latency. Its tuning guide discusses reducing batch demand or changing memory/parallelism allocation, with synchronization and latency tradeoffs. Diagnose measured pressure before choosing a change; more parallelism is not an unconditional improvement [I02].

Automatic prefix caching reuses KV computation for shared prefixes. The vLLM guide states that it reduces prefill work, not new-token decoding time. Check prefix reuse and which phase dominates before attributing a latency gain to caching [I03].

Use the actual engine's telemetry. vLLM's metrics include running/waiting requests, preemptions, cache usage/reuse, input/output token counts, and queue/prefill/decode and end-to-end latency. Read the version-specific metric definitions before interpreting units or combining measurements [I04].

vLLM does not guarantee reproducibility by default; its reproducibility documentation conditions guarantees on supported settings, the same hardware, and the same engine version. A seed alone does not establish reproducibility across deployments [I05].

Track latency, tokens, cost per task, and errors on a stable task bank [E01].

## 10. Architecture and user feedback [F01]

The reference architecture separates context enhancement, guardrails, routing/gateways, caching, agent patterns, and observability. Each added component also adds potential failure modes. Component boundaries should make failures detectable and traceable, rather than hiding responsibility behind a general “LLM pipeline” label [F01, F02].

Complement offline evaluation with production monitoring, user feedback, and transcript review [E01].

### Defensive prompting and production feedback: unsurveyed

Prompt-injection defenses, application security architecture, and feedback-collection design are identified in the reference contents but have not been surveyed here. This draft supplies no security guarantee or feedback-design prescription [F01].
