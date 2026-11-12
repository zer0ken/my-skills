---
name: pov
description: "Investigate the current product and the related technologies, and collect and synthesize opinions from seven expert perspectives: programming language, DBMS and SQL, parallel processing, architecture, problem solving, marketing, and sales and business. Use when the user calls /pov or $pov, or asks for several expert perspectives or a cross-review from technical and business viewpoints (여러 전문가의 관점이나 기술·사업 관점의 교차 검토를 요청할 때)."
---

# POV

POV is a skill that collects the opinions needed for a decision, based on the current product's actual constraints and field-specific evidence. A perspective is an agent analysis that applies an expert's criteria of judgment, and it is not presented as the result of consulting or interviewing a real expert.

## Investigation scope

The product and question the user specified come first. If invoked without a question, review the product in the current working directory for improvement opportunities and risks. If there is no basis for identifying the product, ask for the product name or the location of the materials, and carry out the investigation possible within the verifiable range first.

The agent writes the common context by reading the applicable AGENTS.md, the product description, the dependency and version files, the main implementation, and the test and deployment settings. If connected materials exist, it checks customer needs and product strategy. If the intent of a document and the behavior confirmed in the implementation differ, it distinguishes them. In a review of existing changes, it also records the base commit and the working tree changes.

The common context includes the review question, the product's users and the problem it tries to solve, the current technology and execution environment, the confirmed constraints, the success criteria, and the unconfirmed assumptions. It distinguishes the scope of a whole-product investigation from that of a review of a specific feature, and does not widen the specified scope.

## Evidence investigation per perspective

Before writing an opinion, the agent investigates the criteria of judgment that apply to this product in each field. It does not repeat generalities that differ only in job title, and it makes the criteria concrete to the versions of the language and DBMS in use and to the product's operating and sales form.

Technical criteria are checked in official documentation, standards, and original papers. Facts that can change, such as market, competition, price, and purchasing practice, are checked against current material, and the date and source are recorded. The product's non-public code and customer information are not included in external search queries. If external material cannot be accessed, analyze with local evidence and state the scope that was not investigated.

Each cited source is linked to the judgment it supports. A specific person's name or authority is not needed, and statements or opinions of real experts are not fabricated. A defect in the product is not declared on the basis of external general principles alone.

## Seven perspectives

If the user does not limit the perspectives, review all seven of the following. A perspective with no applicable basis also leaves its review result and the reason, and does not invent unrelated problems. If the product has several languages or DBMSs, review them separately within that perspective according to their role and importance.

| Perspective | Criteria of judgment to investigate for the product | Focus of the opinion |
| --- | --- | --- |
| Programming language expert | Semantics of the actual language and runtime versions, types and error handling, resource lifetime, standard library and idiomatic implementation | Correctness, maintainability, implementation that fits the language's characteristics, and performance constraints |
| DBMS and SQL expert | Actual DBMS and extensions, data model and queries, constraints, transactions, isolation levels, execution plans and indexes | Integrity, placement of responsibility between the DB and the application, query cost, and operation and migration impact |
| Multi-processing and multi-threading parallel processing expert | Process, thread, and async task structure, shared state and synchronization, connection pools, cancellation, retry, and shutdown | Race conditions, deadlock, duplicate execution, backpressure, CPU and I/O bottlenecks, and resource limits |
| Software architect | Module and service boundaries, dependency direction and contracts, data flow, infrastructure and failure boundaries | Fitness of design patterns, cost of change, and the balance between scalability and operational complexity |
| Senior engineer in problem definition and solving | User problem, success criteria, reproduction evidence, cause hypotheses, existing constraints and alternatives | Validity of the problem definition, distinction between cause and symptom, the smallest effective solution, and the verification method |
| Product promotion and marketing | Target users and usage situations, substitute products, evidence for differentiators, messaging and adoption path | Value the customer understands, match between claims and actual features, and acquisition and activation experiments |
| Sales and business | Users, buyers, and decision makers, purchasing process, price and cost structure, adoption and support burden | Willingness to pay and ROI hypothesis, contract and procurement obstacles, revenue potential and delivery cost |

## Collecting opinions

If an agent delegation tool exists, assign an independent analysis per perspective. Proceed in divided batches within the concurrent execution limit, and hand every perspective the same common context and the related primary materials. Each assignee performs additional investigation in its field and submits its first opinion before seeing the conclusions of the other assignees. If there is no such tool, analyze perspective by perspective in sequence, and do not describe it as if several independent experts had verified it.

Each perspective's opinion includes the criteria of judgment and sources, the evidence confirmed in the product, the strengths to keep, the important concerns or opportunities, recommendations and alternatives, and the verification method. No fixed count is set for the purpose of filling out an opinion. Each recommendation is linked to the affected user or operational path.

Claims about code are linked to a file and line or an identifier, and external facts to a link to the original source. Distinguish measurements that were run, inferences derived by static analysis, and hypotheses that need verification. Do not confirm a bottleneck without an execution plan or load measurement, and do not write demand, revenue, or ROI figures as fact without customer evidence.

The analysis assignee performs only investigation and opinion writing. Changing code or settings, creating issues, contacting outside parties, and deploying are not part of collecting opinions. Additional execution follows the user's request and the existing approval scope.

## Cross-review and synthesis

The lead agent checks the evidence of the collected opinions and merges duplicate opinions with the same cause. It also checks whether opinions that look like different sources depend on the same primary material or the same unconfirmed assumption. Agreement among several perspectives alone does not raise confidence.

If opinions conflict, compare the goals and premises each perspective prioritizes and the cost of each alternative. When necessary, pass the counterargument and its evidence to the relevant assignee for re-review. If the evidence is insufficient, do not settle the conclusion by majority vote, and present the observation or experiment that would change the decision.

The final result first explains the review target and scope and the key judgment, and organizes the opinions of the seven perspectives so they can be compared. Add a paragraph that can explain the evidence and limits of each important opinion. Distinguish what was agreed, the remaining disagreements, and the unconfirmed assumptions, and state the expected effect, cost, regression risk, and verification method for each follow-up action. Do not set priority by technical elegance or expected revenue alone; also consider user impact and the product's current stage.

Before submitting the result, check whether all seven perspectives were reviewed, whether the product evidence is linked to the field-specific investigation evidence, whether facts, inferences, and hypotheses are distinguished, and whether verification not run is marked. Unless a separate request to save is made, provide the result in the conversation.
