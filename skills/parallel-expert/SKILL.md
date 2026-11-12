---
name: parallel-expert
description: Apply parallel and concurrent computing expertise to task DAGs, scheduling, admission control, queues, shared-state correctness, failure isolation, cancellation, crash recovery, and idempotent distributed processing. Use when designing, implementing, diagnosing, or reviewing worker pools and concurrent pipelines.
metadata:
  version: "1.0.0"
---

# Parallel and concurrent computing

This skill concerns computations that overlap in time or execute across places, their interactions, and their correctness and performance. Parallelism, distribution, and concurrency emphasize different aspects of those computations; asynchronous syntax alone does not establish physical parallel execution. [P01](sources.md#p01)

Editorial boundary: use this skill for execution dependencies, resource ownership, scheduling and recovery protocols. Use `sql-expert` for the datastore's schema, transactions and query implementation, `python-expert` for Python language structure, and `llm-expert` for model semantics and serving-specific capacity. These are ownership boundaries for this skill, not claims that the disciplines are disjoint. [P01](sources.md#p01)

The five knowledge units below follow CS2023's Parallel and Distributed Computing curriculum. Product examples illustrate particular contracts: confirm the actual runtime, language implementation, scheduler, broker, datastore and versions from the target's code, lockfiles, configuration and execution; read their corresponding official documentation before relying on those contracts. Do not infer the deployed version from these links or assume another product has the same semantics. [P01](sources.md#p01) [P06](sources.md#p06) [P08](sources.md#p08) [P12](sources.md#p12)

## PDC-Programs: Programs

Represent necessary ordering as a partial order: a DAG edge or a happens-before relation, rather than an arbitrary sequence of stages. Distinguish data dependence, synchronization and resource availability. Unordered actions require reasoning about independence or commutativity; removing an ordering edge requires preserving the computation's contract. [P01](sources.md#p01) [P03](sources.md#p03)

Use Foster's **PCAM** vocabulary to make decomposition concrete: partition computation/data, determine communication, agglomerate tasks, and map them to processors. Early decomposition exposes concurrency; agglomeration trades concurrency for lower communication and implementation costs. A conceptual partition is not an instruction to create one runtime task per piece. Mapping may be static or use dynamic load balancing. [P02](sources.md#p02)

Undefined dependencies and unspecified execution places are incomplete program models. Distinguish an algorithmic task from its execution thread/process and its assigned processor; their counts need not coincide. Name the actual data and ordering dependencies rather than using a stage label as their substitute. [P01](sources.md#p01) [P02](sources.md#p02) [P03](sources.md#p03)

## PDC-Communication: Communication

Choose explicitly among channels/message passing, shared memory and shared datastores. Their ordering and visibility guarantees differ. In shared memory, account for the language memory model and synchronization; for messages, account for buffering, delivery and acknowledgment. Communication cost includes latency, bandwidth, contention and data placement. [P01](sources.md#p01)

### Queueing and admission

For a stable observation boundary with existing long-run averages and equal admitted-arrival/departure rates, **Little's Law** is `L = λW`: mean number in the system equals effective arrival rate times mean time in it. Applying the boundary to waiting alone gives `Lq = λWq`. Keep the population, rate, time interval and units consistent; include rejected traffic only if that traffic belongs inside the defined boundary. The law relates means, not response-time percentiles or an optimal worker count. [P05](sources.md#p05)

For a single device under the stated stability assumptions, utilization is `ρ = λ/μ = λ E[S]`. This is a resource model, not a universal queue-delay formula. Queue discipline, arrival/service variability and the number of servers belong in a queueing model before predicting delay. [P05](sources.md#p05)

Capacity planning based only on task counts or QPS is naive when work has different resource costs. Model the constrained resources and observe their consumption. Protect scarce capacity with admission and an explicit overload response; merely accumulating more work can exhaust memory and spread failures. Include connection establishment and maintenance costs. [P07](sources.md#p07)

Separate **logical resource admission** from **physical isolation**. For example, Ray's logical resource requests constrain scheduling but do not cap a task's physical CPU consumption. Account for nested threads and actual resource use; do not claim that a scheduler reservation enforces an OS limit. Verify how the chosen runtime handles those limits. [P06](sources.md#p06)

### Delivery and acknowledgment

Define the delivery boundary before claiming processing guarantees. RabbitMQ publisher confirms concern publisher-to-broker acceptance; consumer acknowledgments concern broker-to-consumer delivery/processing. They are orthogonal. A confirmed publish does not establish that application effects committed. With manual acknowledgments, connection/channel loss requeues outstanding deliveries, so processing must tolerate redelivery. [P12](sources.md#p12) [P11](sources.md#p11)

Bound outstanding work where the broker/runtime supports it, and distinguish prefetched deliveries from actively executing work. In RabbitMQ, unlimited prefetch can increase memory consumption; immediate repeated requeueing can create a costly **requeue/redelivery loop**. Acknowledge only at the processing boundary actually promised, and keep failure/retry policy explicit. [P12](sources.md#p12)

## PDC-Coordination: Coordination

Distinguish completion-based coordination (joins/barriers), data-enabled coordination (queues), and condition-based coordination (signals, waits, retries and timeouts). Unnecessary dependency cycles threaten progress; a barrier is appropriate only when its global dependency is required. [P01](sources.md#p01)

Treat a shared-state operation's atomicity boundary as part of its specification. **Check-then-act races**, missing synchronization, and holding locks while invoking unknown operations are named errors in the curriculum. Evaluate deadlock, starvation/fairness and livelock separately from race freedom; optimistic retry is not itself a progress guarantee. Contention and lock granularity affect both correctness and scalability. [P01](sources.md#p01)

### Task lifetimes and cancellation

Use a task group when its related tasks share a completion and failure scope. In Python `asyncio.TaskGroup`, scope exit awaits the group's tasks and an ordinary child failure cancels the remaining tasks. This contract is suitable for related subtasks; placing independent jobs in the same failure scope changes their isolation. Inspect the actual runtime's policy rather than assuming all groups supervise children identically. [P08](sources.md#p08) [P09](sources.md#p09)

Distinguish cancellation requested, cancellation observed and task completion. Python asyncio delivers cancellation at an opportunity in task execution, recommends cleanup in `finally`, and warns that swallowing cancellation can break structured-concurrency components. Cancellation does not establish that a remote operation failed or that an external effect was rolled back; a timeout can leave a successful side effect. [P08](sources.md#p08) [P10](sources.md#p10)

### Failure isolation and retry control

The **Bulkhead pattern** partitions resources so one failing dependency or consumer cannot exhaust every other consumer's capacity. Choose boundaries according to availability requirements, and weigh isolation against utilization and management overhead. Fail-fast related subtasks and isolated independent jobs are different requirements; neither is universally correct. [P09](sources.md#p09) [P08](sources.md#p08)

A timeout bounds waiting, not certainty about remote execution. Prefer the client's documented timeout facilities and check whether they cover connection establishment, DNS/TLS and the request. Select timeouts using downstream latency and the tolerated false-timeout rate, with network/connection costs included. [P10](sources.md#p10)

Retries add demand and can amplify overload. Use the actual operation's retryability and idempotency contract, finite attempts, capped backoff, jitter and a retry budget appropriate to the system. Account for SDK retries before adding another retrying layer: independent layers multiply attempts. Jitter addresses correlated retry timing; it does not create capacity or safe side effects. [P10](sources.md#p10) [P07](sources.md#p07)

### Idempotency and crash recovery

**Idempotency** means repeated execution of one logical operation does not add effects beyond its intended effect. Distinguish logical request identity from attempt identity. In the token-based API pattern, caller/request identity, original parameters and repeat responses have defined semantics; account for concurrent duplicates, late requests, retention and reuse of a token with changed parameters. [P11](sources.md#p11)

An idempotency record written independently of the mutation leaves a crash window: the effect can exist without its record, or the record without the effect. The cited API pattern requires an atomic, durable operation across both. This is a required scope of atomicity, not proof that a local database transaction covers an external service. Keep application-effect guarantees within the boundary actually provided by the participating systems. [P11](sources.md#p11)

**Rollback recovery** restores a consistent computation state using checkpoints or checkpoints plus event logs. In the survey's fail-stop message-passing model, a consistent global state cannot contain a received message without the corresponding send. Independent checkpoints can cause cascading rollback, the **domino effect**. Coordinated checkpoints and logging have different synchronization, storage and recovery costs; arbitrary per-worker snapshots are not automatically a recoverable global checkpoint. [P13](sources.md#p13)

The survey's **output commit problem** separates recoverable internal state from effects already visible to the outside world. Checkpointing alone cannot undo those effects. Log-based replay also depends on capturing the required nondeterministic events under the stated model; restarting workers is not evidence that recovery preserves completed work or avoids duplicate effects. [P13](sources.md#p13)

For leader/follower coordination, a **generation clock** (term/epoch) distinguishes current leadership from a deposed leader that resumes after a pause or disconnection. Persist the generation as required by the protocol, and have the receiving participant reject stale generations. Merely issuing a number locally supplies no protection unless the operation's receiver validates it. [P15](sources.md#p15)

## PDC-Evaluation: Evaluation

**Safety** constrains what must always hold; **liveness** constrains eventual progress. Specify the relevant invariants and progress assumptions. Check atomicity, ordering and termination separately; an implementation that produces correct values only when it terminates has not established liveness. [P01](sources.md#p01)

### Work, span and scalability

In the idealized DAG model, **work** `W` is total work and **span** `S` is the longest dependent path. On `P` identical processors, `T_P ≥ max(W/P, S)`; an ideal greedy schedule has `T_P ≤ W/P + S(P−1)/P`. These bounds assume the model's scheduling/communication costs, not arbitrary distributed wall time. `W/S` expresses available parallelism; it is not a command to allocate that many workers. [P03](sources.md#p03) [P04](sources.md#p04)

A large span identifies a dependency limit; large work per processor identifies a work/capacity limit in that model. Actual shortfalls also involve scheduling burden, memory bandwidth, contention and false sharing. Diagnose which costs are observed instead of attributing every idle period to insufficient worker count. Cilkscale's burdened span is explicitly a heuristic, not a complete prediction of speedup. [P03](sources.md#p03) [P04](sources.md#p04)

Distinguish **strong scaling** (fixed total problem size) from **weak scaling** (fixed problem size per task). Compare the correct workloads. Poor strong scaling can mean too many tasks relative to useful computation; communication/computation ratio, memory contention and synchronization can limit gains. A throughput improvement on a larger problem does not establish reduced latency for the original fixed problem. [P16](sources.md#p16)

### Correctness diagnostics

Systematic concurrency testing explores controlled interleavings and replays the failing schedule. The CHESS work distinguishes synchronization and shared-memory communication in its happens-before graph; missing modeled nondeterminism can reduce coverage or reproducibility, and invented behaviors can produce false errors. Use a runtime-compatible controlled scheduler or model checker where applicable. State-space bounds and modeled operations limit what a passing exploration establishes. [P14](sources.md#p14)

## PDC-Algorithms: Algorithms

Separate algorithmic decomposition from scheduling machinery. A **ready task** has its dependency predecessors satisfied; a greedy scheduler assigns ready work when processors are available. **Work stealing** uses local queues and idle workers taking work from others. It addresses dynamic load balance, not correctness of shared state or remote effects. A centralized queue is a possible starting point, but serialized queue operations and scheduling friction can limit scaling; use evidence before replacing the runtime scheduler. [P03](sources.md#p03)

Assess task granularity against useful work, communication and scheduling friction. More tasks are not inherently more parallel performance. Agglomeration can reduce overhead and improve locality while sacrificing some concurrency; mapping balances utilization against communication cost. Distinguish a valid optimization tradeoff from a missing dependency or unspecified coordination contract. [P02](sources.md#p02) [P03](sources.md#p03)

### Numerical and accelerator algorithms — unsurveyed

### Consensus protocol design and Byzantine fault tolerance — unsurveyed
