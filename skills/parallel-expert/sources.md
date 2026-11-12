# Primary sources

This is a source audit, not a semantic proof of every application rule. Quotes are literal substrings after HTML entity decoding, HTML text extraction or `pdftotext`, Unicode NFKC normalization, and whitespace folding. No words are inserted or corrected. HTTP success also requires curl exit code 0 and a nonempty body; a resumed PDF records both transfers in the evidence JSON.

Mechanical evidence: `checks/run-1/evidence.json`. Reproduce in a new numbered directory with `uv run --no-project python check_citations.py <run-number>`. Each source is fetched using `curl -sSL -m 20 --compressed`; interrupted PDFs can use curl's native resume once.

Source types: P01 is the professional curriculum that determines the section structure; P02, P03, P05 and P16 are textbook/academic teaching references; P13 is a recovery survey; P14 is an OSDI paper. P04, P06, P08 and P12 are product-maintainer documentation. P07 is Google's SRE reference book, P09 Microsoft's architecture pattern catalog, P10-P11 Amazon's operator-authored Builders' Library, and P15 a pattern excerpt explicitly linked to the published *Patterns of Distributed Systems* book. The practice references are used for their stated operating contexts, not as universal standards.

| ID | URL | Section read | Quoted sentence | HTTP status from fetch | Quote found |
| --- | --- | --- | --- | --- | --- |
| <a id="p01"></a>P01 | [ACM/IEEE-CS/AAAI Computer Science Curricula 2023](https://csed.acm.org/wp-content/uploads/2025/11/CS2023-Report.htm) | PDC preamble; PDC-Programs, Communication, Coordination, Evaluation, Algorithms | Parallel and distributed programming arranges, coordinates, and controls multiple computations occurring at the same time across different places. | 200 | yes |
| <a id="p02"></a>P02 | [Ian Foster, Designing and Building Parallel Programs](https://www.mcs.anl.gov/~itf/dbpp/text/node15.html) | 2.1 Methodical Design (PCAM) | This methodology structures the design process as four distinct stages: partitioning, communication, agglomeration, and mapping. | 200 | yes |
| <a id="p03"></a>P03 | [Umut A. Acar, Parallel Computing: Theory and Practice](https://www.cs.cmu.edu/afs/cs/academic/class/15210-f17/www/concurrency.html) | 1.1-1.6 DAG representation, work/span, lower bounds, offline/online scheduling; scheduling friction | Every execution schedule has length at least $S$. | 200 | yes |
| <a id="p04"></a>P04 | [OpenCilk Cilkscale reference](https://www.opencilk.org/doc/reference/cilkscale/) | Work/span analysis measurements; compiler options | The scheduling burden is based on a heuristic estimate of the costs associated with migrating and synchronizing parallel tasks among processors. | 200 | yes |
| <a id="p05"></a>P05 | [Mor Harchol-Balter, Introduction to Probability for Computing, Chapter 27](https://www.cs.cmu.edu/~harchol/Probability/chapters/chpt27.pdf) | 27.2-27.6 queue models and utilization; 27.7-27.11 Little's Law and corollaries | The device utilization, denoted by 𝜌, is the long-run fraction of time the device is busy. | 200 | yes |
| <a id="p06"></a>P06 | [Ray official documentation: Resources](https://docs.ray.io/en/latest/ray-core/scheduling/resources.html) | Physical Resources and Logical Resources; resource requirements | They are mainly used for admission control during scheduling. | 200 | yes |
| <a id="p07"></a>P07 | [Google Site Reliability Engineering, Handling Overload](https://sre.google/sre-book/handling-overload/) | Pitfalls of Queries per Second; client throttling; criticality; retry budgets; connections | Different queries can have vastly different resource requirements. | 200 | yes |
| <a id="p08"></a>P08 | [Python official documentation: Coroutines and tasks](https://docs.python.org/3/library/asyncio-task.html?highlight=to_thread) | Task cancellation; Task groups | All tasks are awaited when the context manager exits. | 200 | yes |
| <a id="p09"></a>P09 | [Microsoft Azure Architecture Center: Bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead) | Context and problem; Solution; Problems and considerations | Isolate the elements of an application into pools so that if one element fails, the others continue to function. | 200 | yes |
| <a id="p10"></a>P10 | [Marc Brooker, Amazon Builders' Library: Timeouts, retries, and backoff with jitter](https://d1.awsstatic.com/builderslibrary/pdfs/timeouts-retries-and-backoff-with-jitter.pdf) | Timeouts; Retries and backoff; Jitter | It's not always safe to retry. | 200 | yes |
| <a id="p11"></a>P11 | [Malcolm Featonby, Amazon Builders' Library: Making retries safe with idempotent APIs](https://d1.awsstatic.com/builderslibrary/pdfs/making-retries-safe-with-idempotent-apis-malcolm-featonby.pdf) | Reducing client complexity; Retries and semantic equivalence; Late arriving requests; changed parameters | An ACID server-side operation needs to be an “all or nothing” or atomic process. | 200 | yes |
| <a id="p12"></a>P12 | [RabbitMQ official documentation source: Consumer Acknowledgements and Publisher Confirms](https://github.com/rabbitmq/rabbitmq-website/raw/refs/heads/main/docs/confirms.md) | Relation between confirms and acknowledgements; requeue loops; prefetch; automatic requeueing; publisher data safety | The two features, however, are entirely orthogonal and unaware of each other. | 200 | yes |
| <a id="p13"></a>P13 | [Elnozahy, Alvisi, Wang and Johnson: A Survey of Rollback-Recovery Protocols in Message-Passing Systems](https://www.cs.utexas.edu/~lorenzo/papers/SurveyFinal.pdf) | 2 Background (system model, consistent states, outside world); 3.1-3.2 checkpointing; overview of log-based protocols | Coordinated checkpointing requires processes to orchestrate their checkpoints in order to form a consistent global state. | 206 | yes |
| <a id="p14"></a>P14 | [Musuvathi et al., OSDI 2008: Finding and Reproducing Heisenbugs in Concurrent Programs](https://static.usenix.org/events/osdi08/tech/full_papers/musuvathi/musuvathi_html/index.html) | 1 Introduction; 3 scheduler and happens-before graph; 4 search strategy | The main contribution of this paper is a new tool called Chess for systematic and deterministic testing of concurrent programs. | 200 | yes |
| <a id="p15"></a>P15 | [Unmesh Joshi, Patterns of Distributed Systems: Generation Clock](https://martinfowler.com/articles/patterns-of-distributed-systems/generation-clock.html) | Problem; Solution | The follower then replies with a failure response. | 200 | yes |
| <a id="p16"></a>P16 | [Cornell Center for Advanced Computing, Virtual Workshop: Scaling](https://cvw.cac.cornell.edu/parallel/efficiency/scaling) | Scaling; Strong Scaling; Weak Scaling | Strong scaling is concerned with a slice of the scaling surface at a particular problem size. | 200 | yes |

## Limits and unresearched scope

**P01.** Limits: A curriculum identifies competencies; it does not specify a scheduler or runtime contract. Unresearched: Detailed GPU, numerical and Byzantine-consensus algorithms; repository-specific decisions.

**P02.** Limits: Algorithm-design methodology; not a requirement that every stage become a runtime task or durable record. Unresearched: Other textbook chapters and product-specific implementations.

**P03.** Limits: Idealized instruction DAG and homogeneous processors; excludes actual distributed communication and scheduling costs. Unresearched: A proof of the fully strict randomized work-stealing theorem and heterogeneous scheduling bounds.

**P04.** Limits: Cilk-specific instrumentation; burdened span is a heuristic and omits other slowdown factors. Unresearched: Installed target toolchain and empirical accuracy on a particular program.

**P05.** Limits: Little's Law needs consistent system boundaries, matching rates and existing long-run averages; means do not determine tail latency. Unresearched: Product-specific arrival/service distributions and optimal scheduling policies.

**P06.** Limits: Ray-specific logical resources; resource requests do not enforce physical CPU or memory limits. Unresearched: Installed Ray version, configuration, placement groups and physical isolation.

**P07.** Limits: Serving-system operational practice; examples and thresholds are not universal capacity limits. Unresearched: Capacity and overload behavior of any concrete workload.

**P08.** Limits: Python asyncio example only; API availability and cancellation semantics must be checked for the actual runtime version. Unresearched: Other languages' cancellation contracts and the target Python build.

**P09.** Limits: Resource/failure partitioning has utilization and management costs; boundaries depend on business requirements. Unresearched: Concrete pool sizes, fault domains and tenant service objectives.

**P10.** Limits: Amazon operational experience; concrete percentiles, retry counts and timeout values require workload evidence. Unresearched: Target SDK's built-in retries, timeout coverage and error classification.

**P11.** Limits: An API pattern, not a guarantee of exactly-once arbitrary external side effects; retention and atomicity scope are essential. Unresearched: Target datastore's transaction implementation and external sink guarantees.

**P12.** Limits: RabbitMQ AMQP 0-9-1 contract; fetch uses the official repository's Raw link because the published website returned 403. Unresearched: Installed broker/client versions, queue type, replication and durability configuration.

**P13.** Limits: Fail-stop message-passing rollback recovery; logging needs the stated determinism/event-capture assumptions and outside-world output treatment. Unresearched: Byzantine recovery, target storage atomicity and application-specific checkpoint protocol proofs.

**P14.** Limits: Exploration covers modeled synchronization and bounded schedules; a passing run is not an unbounded correctness proof. Unresearched: Availability of a compatible scheduler/model checker for the actual runtime.

**P15.** Limits: Leader/follower generation pattern; a local token counter alone does not protect an external sink unless the receiver validates it. Unresearched: Leader election/consensus algorithm proofs, clock/lease guarantees and target storage enforcement.

**P16.** Limits: Scaling concepts and diagnostic guidance; ideal scaling is not a guarantee for any concrete application. Unresearched: Benchmarks for a particular system, workload, hardware and network.
