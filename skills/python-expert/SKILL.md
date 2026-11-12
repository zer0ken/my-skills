---
name: python-expert
description: "Use for Python software design and implementation: language semantics and idioms, typed data models, module boundaries and public APIs, standard-library choices, exceptions, profiling, tests, and refactoring."
metadata:
  version: "1.0.0"
---

# Python software design and implementation

Scope: Python language behavior, object and type models, modules and libraries, and the quality of Python implementations. Use `sql-expert` for DBMS and storage contracts, `llm-expert` for model behavior and evaluation, and `parallel-expert` for scheduling and concurrent failure protocols; this skill supplies their Python-language constraints. [PY01]

Organization follows selected topics in the IEEE Computer Society's SWEBOK Guide V4.0a: Software Design, Software Construction, and Software Testing. Topic numbers below identify its chapters and sections. Python references, PEPs, typing specifications, and refactoring literature supply the content within this professional knowledge map. Coverage is limited to the assigned Python field. [PY30]

## Software Design [PY30]

### Software Design Fundamentals (3.1) [PY30]

A Python module has a namespace; a package structures module names. These mechanisms provide organization but do not themselves establish a useful responsibility boundary. Parnas's design concept of a module is a responsibility assignment, which need not correspond to one Python file or subroutine. [PY05] [PY22]

Apply **information hiding**: isolate a difficult or changeable design decision behind an interface that reveals little of its representation. Parnas compares two decompositions of a KWIC system and favors hiding design decisions over assigning each processing phase its own module. The comparison supplies a design criterion, not a universal performance result. [PY22]

Use that criterion to investigate blurred boundaries: if changing a supposedly hidden representation requires changes in its callers, inspect what the interface exposes. File count and process-phase names alone do not show that information hiding has been achieved. [PY22]

### Software Design Processes (3.2) [PY30]

#### Detailed Design (3.2.2) [PY30]

Python's typing specification describes **gradual typing**. `Any` represents an unknown static type and permits operations a checker cannot validate; `object` is the static type encompassing all Python objects and permits only operations valid for that type. They express different contracts. [PY09]

Use `TypedDict` for a dictionary's named-key shape, `NamedTuple` for named tuple fields, and `NewType` when static distinction between otherwise similar values matters. A type alias expresses equivalence instead. Select the representation by its runtime and static semantics. Annotations, including `TypedDict` declarations, do not validate external data at runtime. [PY08]

Use `dataclasses` when generated initialization, representation, and comparison methods match the record's semantics. Use a default factory for per-instance mutable field defaults. `frozen=True` emulates read-only fields; it does not recursively freeze referenced objects. `slots=True` changes attribute storage and has inheritance and weak-reference constraints to check in the relevant version. Neither option is a universal record default. [PY11] [PY07]

### Software Design Quality Analysis and Evaluation (3.6) [PY30]

Fowler's practice text treats refactoring as small behavior-preserving transformations that improve an existing design. His definition fixes observable behavior as the preservation criterion. Tests support checking that criterion; line-count reduction alone does not establish it. [PY20] [PY29]

A **code smell** is a visible indication of a possible deeper problem. Investigate the cause before declaring a defect or applying a transformation. Method length and data-only classes are examples to examine, not automatic bans. [PY21]

A data carrier is supported by Python's dataclass facility. Fowler also discusses data-only classes as a possible code smell. These positions have different conditions: inspect whether behavior is misplaced; do not classify every record as a design defect. [PY11] [PY21]

#### Refactoring catalogue: unsurveyed [PY20]

The full book and transformation-specific mechanics were not inspected; the cited author pages support the definition and smell criterion above. [PY20] [PY21] [PY29]

## Software Construction [PY30]

### Software Construction Fundamentals (4.1) [PY30]

Apply the project's conventions consistently. PEP 8 explicitly gives project-specific guidance precedence and rejects breaking compatibility solely for style compliance. Readability and consistency are the criteria, rather than minimizing line count. [PY06]

Describe an object's purpose concisely, then document calling conventions and side effects where needed. Keep comments consistent with behavior; a comment contradicting the code is worse than no comment. [PY03] [PY06]

Look for standard-library support before implementing an equivalent facility. Adopt it when its documented behavior fits; existence in the library is not evidence of suitability for every workload or platform. [PY14]

### Managing Construction (4.2) [PY30]

#### Managing Dependencies (4.2.4) [PY30]

Confirm the actual implementation and language version separately: `sys.implementation` describes the implementation, while `sys.version_info` describes the language version. Establish the installed library and tooling versions and the project's supported Python range. Read the official documentation for those versions before relying on syntax, APIs, or implementation details; a documentation URL containing `/3/` does not establish what the target runs. This skill prescribes no minimum Python version. [PY02] [PY23] [PY27]

An application's required library versions can conflict with another application's requirements. Separate virtual environments isolate their installations. Inspect the actual environment and project metadata: `requires-python` declares language support, while dependency requirements constrain libraries. Neither a declared range nor an environment's existence proves which version the running process imports. [PY23] [PY27]

### Practical Considerations (4.3) [PY30]

#### Coding (4.3.3) [PY30]

Use the operation's semantics to choose a container: lists for mutable sequences, tuples for fixed sequences, dictionaries for keyed associations, and sets when uniqueness without sequence order is appropriate. Preserve required order and duplicate counts when changing representation. Dictionary keys and set elements must satisfy the hashability contract. [PY04] [PY07]

A list supports a stack with append and pop at the end. Repeated removal at the front of a list shifts remaining elements: the tutorial explicitly identifies this as an inefficient FIFO queue implementation and recommends `collections.deque`. This is a workload-specific reason to change the data structure. [PY04]

Use comprehensions for a clear collection-producing transformation. Use set operations for membership and set algebra when their uniqueness and ordering semantics fit the problem. These language facilities do not justify changing the meaning of the input data. [PY04]

Iterators are consumed through iteration; generators retain execution state between yields. Generator expressions can avoid materializing an equivalent list and tend to use less memory, but their consumption and retained state differ from reusable collections. Choose laziness only when those semantics fit the consumers. [PY24]

Container operations have different tradeoffs: the tutorial contrasts `deque`'s efficient ends with slower middle lookup, and introduces `bisect` for sorted-list operations and `heapq` for repeated minimum access. Re-sorting a whole list when only the next minimum is needed is a candidate for using a heap; confirm that the required access pattern matches. [PY28]

Binary floating point approximates many decimal fractions. Choose comparison tolerances according to the required accuracy; `math.isclose` supports approximate comparison. Exact decimal or rational requirements call for the corresponding arithmetic model, such as `decimal` or `fractions`, rather than assuming display rounding changes the underlying value. [PY25]

### Construction Technologies (4.4) [PY30]

#### API Design and Use (4.4.1) [PY30]

Treat positional-only, positional-or-keyword, and keyword-only parameters as parts of the calling contract. Choose them according to how callers should supply arguments; names exposed for keyword calls become part of that interface. Check syntax against the supported versions. [PY03]

Default arguments are evaluated once when the function is defined. A mutable default therefore shares state across calls; use a fresh value inside the function when sharing is unintended. This is a concrete aliasing defect, rather than a blanket prohibition on mutable values. [PY03]

Distinguish documented public interfaces from internal implementation names. Use explicit exports and leading underscores as PEP 8 describes; imported names are implementation details unless explicitly documented as exports. An undocumented transitive import is insufficient grounds for a public API. [PY06]

Avoid wildcard imports in program code when they obscure the names in use. Imports can execute module initialization and bind references into another namespace; reason about those bindings when changing an API or a patch target. [PY05] [PY19]

A `Protocol` expresses structural assignability through members with compatible types, rather than requiring inheritance from one implementation. Its members define a specific behavioral interface; neither a count of implementations nor the presence of a base class alone establishes the right abstraction. Runtime-checkable protocols do not perform full signature validation. [PY10] [PY08]

#### Object-Oriented Runtime Issues (4.4.2) [PY30]

Classes bundle data and functionality. Distinguish instance state from class state: a mutable class attribute can be shared by instances. Names can refer to the same object; assignment and passing an object do not establish independent ownership of its mutable contents. [PY24]

Apply the object model explicitly: identity, type, and value are different properties. An immutable container can still refer to mutable objects. Equality and hashing must agree: equal objects need equal hashes, and keys must not change their hash while held in hashed collections. [PY07]

When interpreter behavior matters, distinguish language guarantees from notes explicitly labeled as CPython implementation details. Object addresses, allocation behavior, and layout assumptions do not transfer automatically to other implementations. [PY07]

#### Error Handling, Exception Handling, and Fault Tolerance (4.4.5) [PY30]

Catch the specific exceptions the operation can handle and let unexpected exceptions propagate. Keep the protected `try` region narrow; an `else` clause separates success-path work that should not be caught by the same handler. Silently converting an unexpected failure into success defeats this distinction. [PY13]

Preserve causal information when translating exceptions with exception chaining; re-raise when merely adding diagnostics. Treat exception classes as error categories that callers can handle, rather than discarding the category in a generic fallback. [PY13]

Use `finally` for cleanup that must run whether an exception occurs or not. A `return`, `break`, or `continue` inside it can suppress the pending outcome; such control flow is discouraged by the tutorial. Specific compiler diagnostics vary by Python version. [PY13]

Distinguish text from bytes and choose file mode according to the data. Text-mode line-ending conversion can corrupt binary formats. Use a file context manager so the file closes when its suite exits, including through an exception. [PY12]

#### Concurrency Primitives (4.4.10) [PY30]

For threading-related Python behavior, distinguish a build supporting free threading from the GIL's current runtime state. Check the applicable version's documented mechanism and extension compatibility; importing an extension can re-enable the GIL. Synchronization design belongs to the concurrency field, and built-in container locks are not a substitute for that design. [PY26]

#### Performance Analysis and Tuning (4.4.14) [PY30]

Use profiling to locate execution costs. In a deterministic profile, call counts, internal time (`tottime`), and cumulative time (`cumtime`) answer different questions. Use the profiler supported by the actual interpreter and read its caveats; the documented `cProfile`/`pstats` interface is one such option, not an assumed universal tool installation. [PY15]

Separate profiling from benchmarking. Deterministic profiling introduces overhead that can distort Python-versus-C comparisons. For a small snippet, `timeit` excludes setup and repeats the operation; it disables garbage collection by default, which must be reconsidered when GC is part of the cost. [PY15] [PY16]

Interpret a repeated `timeit` minimum as a lower bound for that snippet under the documented assumptions; inspect the timing vector. It does not establish an application's latency distribution or the cost of work excluded from setup. [PY16]

Use `tracemalloc` for traced Python memory allocations: compare snapshots to locate growth and use current and peak traced sizes to distinguish retained from temporary allocations. Start tracing early enough to include the allocations of interest. A snapshot omits allocations made before tracing began; tracing itself adds overhead. These quantities describe traced allocations, not a census of all process or device memory. [PY17]

## Software Testing [PY30]

### Software Testing Fundamentals (5.1) [PY30]

A test case checks a specific response to a set of inputs. Choose assertions that express the required response, including expected exceptions. Keep fixtures and cleanup self-contained so tests can run alone or in arbitrary combinations. Cleanup must also work when setup fails; `unittest.addCleanup` explicitly supports this case. [PY18]

### Test Techniques (5.3): unsurveyed [PY30]

### Software Testing Tools (5.8) [PY30]

`doctest` checks examples against documentation; a separate test framework supports a broader maintained test collection. Select the facility that matches the intended checks rather than assuming examples alone cover the contract. [PY14]

Patch the namespace where the system under test looks up the object. Use specced or autospecced mocks when interface conformance matters, subject to their documented introspection limits. Autospeccing catches invalid attributes or call signatures; it does not establish the business correctness of a mock's returned values. [PY19]

[PY01]: https://docs.python.org/3/tutorial/
[PY02]: https://docs.python.org/3.12/library/sys.html
[PY03]: https://docs.python.org/3/tutorial/controlflow.html?highlight=lambda
[PY04]: https://docs.python.org/3/tutorial/datastructures.html
[PY05]: https://docs.python.org/3/tutorial/modules.html
[PY06]: https://peps.python.org/pep-0008/
[PY07]: https://docs.python.org/3.13/reference/datamodel.html
[PY08]: https://docs.python.org/3.13/library/typing.html
[PY09]: https://typing.python.org/en/latest/spec/concepts.html
[PY10]: https://typing.python.org/en/latest/spec/protocol.html
[PY11]: https://docs.python.org/3/library/dataclasses.html
[PY12]: https://docs.python.org/3/tutorial/inputoutput.html?highlight=stdout+write
[PY13]: https://docs.python.org/3/tutorial/errors.html
[PY14]: https://docs.python.org/3/tutorial/stdlib.html
[PY15]: https://docs.python.org/3.12/library/profile.html
[PY16]: https://docs.python.org/3/library/timeit.html
[PY17]: https://docs.python.org/3.11/library/tracemalloc.html
[PY18]: https://docs.python.org/3.11/library/unittest.html
[PY19]: https://docs.python.org/3/library/unittest.mock.html?highlight=mock
[PY20]: https://www.martinfowler.com/books/refactoring.html
[PY21]: https://martinfowler.com/bliki/CodeSmell.html
[PY22]: https://cw.fel.cvut.cz/old/_media/courses/a4m33sep/materialy/architecture_and_design/01-article_original_de_parnas.pdf
[PY23]: https://docs.python.org/3.12/tutorial/venv.html
[PY24]: https://docs.python.org/3/tutorial/classes.html?highlight=namespaces
[PY25]: https://docs.python.org/3/tutorial/floatingpoint.html?highlight=float+notation+format
[PY26]: https://docs.python.org/3/howto/free-threading-python.html
[PY27]: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/?highlight=2023
[PY28]: https://docs.python.org/3.12/tutorial/stdlib2.html
[PY29]: https://martinfowler.com/bliki/DefinitionOfRefactoring.html?trk=article-ssr-frontend-pulse_little-text-block

[PY30]: https://ieeecs-media.computer.org/media/education/swebok/swebok-v4.pdf
