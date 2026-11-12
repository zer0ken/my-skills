---
name: sql-expert
description: "Apply database expertise to relational, dimensional, and property-graph modeling, schema and storage contracts, SQL/Cypher correctness, indexes, execution plans, query optimization, transactions, locking, and backend equivalence."
metadata:
  version: "1.0.0"
---

# sql-expert

Database expertise concerns the representation, integrity, querying, execution, and transactional management of persistent data. This skill covers relational databases, data-warehouse schema design, and property graphs; application scheduling, model generation, and programming-language structure are neighboring concerns. Its knowledge-area headings follow the ACM/IEEE-CS/AAAI CS2023 Data Management curriculum; graph-query distinctions follow the surveyed literature; warehouse schema design follows the Kimball dimensional-modeling techniques. Source IDs resolve in [sources.md](sources.md). [D01, D11, D29]

## DM-Core: Core Database System Concepts

Keep conceptual requirements, logical schemas, and physical access paths distinct. Entities and relationships describe the domain; keys and dependencies describe legal relational states; indexes and execution plans describe how operations run. A fast access path cannot establish the correctness of a schema or query. [D02, D03, D12, D14]

Confirm the actual DBMS and server version, extensions, driver, isolation level, and settings relevant to the question from the deployed connection and configuration. Read that product/version's documentation for the behavior being used. SQL feature support and syntax differ between implementations, and server version is compatibility information; the manual editions cited here are evidence, not the version of an unknown target. [D23, D24, D18]

## DM-Modeling: Data Modeling

An **entity** is a distinguishable domain object; a **relationship** associates entities; an **attribute** describes one. Identify entity identity, relationship cardinality, and optional participation explicitly. Distinguish attributes of an entity from attributes of a relationship. A model whose entities, identifiers, or cardinalities cannot be stated leaves its integrity requirements undefined. [D02]

Represent 1:1, 1:n, and n:m relationships deliberately. In a relational implementation, an associative table represents an n:m relationship and can carry attributes of that association. Its identity and foreign keys must reflect the association being represented. Repeating identifiers in an undifferentiated attribute does not by itself define referential integrity. [D02, D04]

## DM-Relational: Relational Databases

A **functional dependency** `X -> Y` means that a given value of `X` determines one value of `Y`; a **candidate key** minimally identifies a row. Derive dependencies from the domain's rules, not merely the accidental contents of one sample. Distinguish a relation's identity from its non-key dependencies. [D03, D02]

**Normalization** analyzes redundancy through dependencies. Insertion, update, and deletion anomalies are concrete design defects: facts cannot be recorded independently, changes require inconsistent copies to be synchronized, or deleting one fact loses another. BCNF requires every determinant of a nontrivial functional dependency to be a superkey. Normal-form analysis and entity-relationship modeling complement each other. [D03, D02, D28]

Judge a decomposition on both **lossless join** and **dependency preservation**, as well as its normal form. The former concerns reconstructing the original relation; the latter concerns retaining enforceable dependencies in the decomposed schema. Intentional denormalization retains integrity obligations. Dimensional modeling is a warehouse schema-design discipline with its own logical organization, not merely a physical access-path change. [D01, D03, D39]

Express identity and integrity with the applicable primary-key, unique, not-null, foreign-key, check, or exclusion constraints. In PostgreSQL a check can succeed with a null result, unique constraints have configurable null treatment, and cross-row checks cannot safely be expressed as ordinary `CHECK` conditions. Constraint choice must match both the invariant and the engine's documented semantics. [D04]

For a **storage contract**, apply these relational and query semantics to the observable boundary: column names and types, identity, nullability, duplicate multiplicity, ordering when promised, and transactional effects. This is an application of the cited semantics to backend-equivalence review, not a new database normal form. Two adapters or a test fake are equivalent only over the contract they actually promise. [D04, D08, D09, D18, D23]

### Logical Database Design Antipatterns

Bill Karwin's published **SQL Antipatterns** catalog names **Jaywalking** for comma-separated lists representing multivalue associations, **Entity-Attribute-Value** for a generic attribute table supporting variable attributes, and **Keyless Entry** for leaving out constraints. Its listed alternatives are intersection tables, subtype modeling, and declared constraints, respectively. The catalog explicitly includes legitimate uses; a pattern name alone does not establish a defect. Detailed EAV tradeoffs beyond this catalog classification remain unsurveyed. [D40]

For Jaywalking, inspect whether identifiers are parsed with pattern matching, list length depends on string width, or foreign keys cannot validate individual members. These are concrete query and integrity failures of storing an association as an encoded list. An associative/intersection table represents the relationship explicitly. This criterion concerns relational associations, not every string containing commas. [D41, D02, D04, D40]

## DM-Querying: Query Construction

Use relational operations to state selection, projection, joins, aggregation, and set operations precisely. Preserve join cardinality and intended duplicate multiplicity during rewrites. PostgreSQL `UNION`, `INTERSECT`, and `EXCEPT` remove duplicates unless their `ALL` form is used; compatible column counts and types are required. [D01, D08]

SQL comparisons involving null generally yield **unknown**. Use the engine's documented null predicates and null-safe comparisons where required. Output order requires an explicit `ORDER BY`; define tie-breaking and null placement when deterministic order is part of the contract. [D26, D09]

For same-engine, same-snapshot query comparison, two empty `EXCEPT ALL` differences establish equal row multisets for the tested input. Plain `EXCEPT` cannot reveal duplicate-count differences. Order must be compared separately. Such a check demonstrates the tested instance, not equivalence for every legal database or another engine's type semantics. [D08, D09, D23]

Recursive queries require a defined state, expansion rule, and termination condition. PostgreSQL recursive CTEs iterate over a working table; `UNION` deduplicates whole output rows. Adding depth or path columns can keep revisited nodes distinct, so deduplication alone may not terminate a cyclic traversal. Use documented cycle detection and distinguish reachability from enumerating paths. [D10, D11]

## DM-Processing: Query Processing

An **execution plan** is a tree of physical operators. Evaluate access paths, join algorithms, sorting, materialization, row widths, selectivity, and repeated execution in the context of the actual data. Optimizer costs are model units, not measured milliseconds; a sequential scan or nested-loop join is not inherently a defect. [D14, D15]

Index design balances selective access against system overhead. Match index method and column order to documented predicate behavior. For PostgreSQL multicolumn B-trees, leading equality conditions and the first inequality determine the conventional scan range; later predicates may filter index entries without shrinking that range. Version-dependent skip-scan behavior can change the access path. Verify the chosen plan instead of applying a universal leftmost-column prohibition. [D12, D13]

Diagnose PostgreSQL query cost through estimated versus actual rows, operator loops, access/filter conditions, buffer activity, and sort/hash behavior. Per-loop actual rows and times must be interpreted with `loops`; parent measurements include child work. Cardinality estimates depend on statistics. Locate the operator-level discrepancy before changing indexes or planner settings, without inventing a universal error-ratio threshold. [D14, D15]

`EXPLAIN ANALYZE` executes the statement and adds instrumentation overhead. Its execution time does not include network transfer to the client. Separate planning, database execution, and end-to-end latency when explaining a measurement; use representative inputs and data rather than treating one plan as a workload result. [D14]

For Cypher, reduce intermediate rows with relevant predicates, retrieve only needed data, and use parameters for reusable plans. `EXPLAIN` plans without execution; `PROFILE` executes and reports operator information. Inspect estimated/actual rows, database hits, and memory in the target runtime. Database hits measure storage-engine work, not an interchangeable unit of wall time. [D16, D27]

Repeated per-record creation calls are inefficient when an equivalent batched operation fits: the Neo4j driver guide recommends `WITH`/`UNWIND` batching and describes per-transaction overhead. Batch size and transaction boundaries still affect memory, failure scope, and isolation. Whole-result eager loading can also consume unnecessary memory when streaming is appropriate. [D17]

## DM-Internals: DBMS Internals

Transaction analysis concerns **atomicity, consistency, isolation, and durability**; isolation levels specify which concurrent phenomena may occur. **Serializability** means the effect of committed transactions matches some serial execution. The DBMS's documented implementation determines its guarantees; an isolation-level name alone does not specify every product's behavior. [D01, D18]

In PostgreSQL Read Committed, successive commands can observe different committed snapshots. Repeatable Read can still admit serialization anomalies. Serializable transactions can fail and require a retry of the whole transaction, including the decisions based on its reads. A read-then-write invariant therefore needs an appropriate constraint, atomic operation, isolation guarantee, or locking argument. [D18, D04]

Model locks by resource, mode, acquisition order, and transaction lifetime. A lock wait differs from a cycle of conflicting waits. PostgreSQL's recommended deadlock prevention is consistent lock ordering; it detects deadlocks and aborts a participant. Row locks and table locks have distinct conflict rules, so reason from the documented modes rather than their names. [D19]

Neo4j's default read-committed behavior permits non-repeatable reads. Lost-update behavior depends on whether the query creates the dependency that acquires the relevant write lock. Analyze the actual read/write expression and documented locking behavior instead of importing PostgreSQL's snapshot or lock rules. [D20]

For durability, distinguish modified database pages from durable log records. PostgreSQL's **write-ahead logging** flushes the corresponding WAL before writing changed data pages, enabling REDO after a crash. WAL flushing, buffering, and recovery are part of the storage reasoning behind write cost and durability. [D22]

### Recovery Manager: unsurveyed

ARIES details, buffer-replacement algorithms, and configuration-specific crash-safety guarantees have not been surveyed for this draft; the curriculum identifies them as DBMS-internals topics. [D01]

## DM-NoSQL: NoSQL Systems

In a **property graph**, nodes represent entities, directed relationships connect source and target nodes, labels classify nodes, relationship types classify relationships, and properties carry values. Choose specific relationship types that describe the domain. A generic `CONNECTED_TO` type is a documented modeling weakness because it obscures meaning and relevant traversal paths. [D06, D07]

Graph querying separates **graph-pattern matching** from **navigational queries**. Specify whether the result is an existence answer, endpoint pairs, or complete paths; specify allowed node/edge repetition, and set versus bag semantics. These choices affect both answers and complexity. Reachability, shortest paths, and all simple paths are different problems; path-enumeration cost depends on the paths returned, not just distinct endpoints. The survey supplies the semantic distinctions, while current engine documentation determines the target language's behavior. [D11, D10]

Cypher `MERGE` matches a whole pattern and may create entities when that whole pattern is absent. Use bound identities and appropriate uniqueness/key constraints for the intended invariant. Under concurrent load, the documented existence guarantee of `MERGE` alone is insufficient to establish global uniqueness; analyze the particular pattern, constraints, and locks. [D21, D20]

## DM-Unstructured: Semi-structured and Unstructured Databases

JSON and relational structures can coexist. PostgreSQL recommends a predictable document structure even where schema flexibility is useful; `jsonb` supports query operators and indexing. Choose a document boundary according to an atomic datum and independent-update needs, since updates lock the whole row. An undefined collection of unrelated properties lacks the predictable structure needed for reliable queries. [D05]

### Vector, text, spatial, and time-series access methods: unsurveyed

Extension-specific vector approximation, filtered-nearest-neighbor recall, full-text ranking, spatial indexes, and specialized time-series access have not been surveyed for this draft. [D01]

## DM-Distributed: Distributed Databases/Cloud Computing: unsurveyed

Distributed transactions, replication consistency, quorums, sharding, failover, and distributed query planning require additional primary sources. [D01]

## DM-Security: Data Security and Privacy: unsurveyed

Database authorization, injection prevention, auditing, encryption, and privacy controls require additional primary sources. [D01]

## DM-Analytics: Data Analytics / Data-Warehouse Schema Design

**Dimensional modeling** organizes warehouse data around business-process measurements and their descriptive context for BI retrieval. It applies to the warehouse schema, while statistical and machine-learning analysis remain outside this skill. Normalized OLTP design emphasizes avoiding redundant updates and insertion/update/deletion anomalies; dimensional designs emphasize understandable analytical retrieval. A warehouse can combine a normalized foundation with dimensional presentation, so neither approach is a universal replacement for the other. [D29, D39]

### Fundamental Concepts

Kimball's four design decisions are to select the business process, declare the grain, identify dimensions, and identify facts, based on business requirements and available source data. **Grain** states exactly what one fact-table row represents; declare it before selecting dimensions or measures. Keep every fact and dimension consistent with that declaration. Mixing grains in one fact table violates Kimball's single-grain contract. [D42, D30]

A **fact table** records business-process measurements or events at the declared grain; facts are usually numeric, while factless fact tables record occurrences without numeric measures. A **dimension table** supplies descriptive context used to filter and group those facts. A **star schema** links fact tables to their dimensions through primary/foreign keys. Identify the represented event and contextual attributes rather than calling arbitrary lookup tables dimensions. [D31, D32, D33, D39]

### Basic Fact Table Techniques / Basic Dimension Table Techniques

A measure is **additive** across every associated dimension, **semi-additive** across some dimensions, or **non-additive**. Balances commonly cannot be summed over time; ratios commonly require aggregating their additive components before division. Aggregate according to the measure's semantics rather than applying `SUM` uniformly. Transaction, periodic-snapshot, and accumulating-snapshot fact tables represent different row meanings and update behavior. [D43, D39]

A **snowflake schema** normalizes dimension hierarchies into related tables; a flattened star dimension retains their descriptive attributes together. Kimball favors flattened dimensions for user navigation and warns that snowflaking can impair query performance. This is methodological guidance, not a universal engine-performance result; the target workload and documented engine behavior determine the physical choice. [D34, D39, D14]

A **dimension surrogate key** identifies a warehouse dimension row independently of operational business keys. Different source systems and multiple historical versions can make an operational key insufficient as the row's primary key. Distinguish business identity from version-row identity. Kimball recommends warehouse-controlled surrogate keys, while explicitly allowing meaningful keys for the stable date dimension. [D35, D37]

### Integration via Conformed Dimensions

**Conformed dimensions** share consistent attribute names and domain contents across business processes, enabling separately computed fact results to align on common grouping attributes. Matching table names alone does not establish conformance. Preserve the shared attribute meanings and values when combining results across stars. [D38, D39]

### Slowly Changing Dimension Techniques

A **slowly changing dimension** policy determines how attribute changes affect current and historical interpretation. **Type 1** overwrites the attribute and loses its former value; **Type 2** creates another dimension row with a new surrogate key. Type 2 uses effective/expiration timestamps and a current-row indicator, and fact foreign keys identify the applicable dimension version. Choose the history semantics explicitly; a Type 1 overwrite is unsuitable where the former attribute value must remain available. [D36, D37]

### Advanced Fact/Dimension Table Techniques: unsurveyed

Late-arriving facts and dimensions, multivalued-dimension bridges, SCD Types 4-7, allocations, and other advanced Kimball techniques have not been surveyed for this draft. [D29]

## DM-Data / DM-SEP: The Role of Data; Society, Ethics, and the Profession: unsurveyed

Retention, provenance, governance, ownership, and legal or ethical data obligations require additional primary sources. [D01]
