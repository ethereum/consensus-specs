# consensus-specs — glossary

This guide leans on engineering vocabulary that may not be familiar
to every reader: refactoring smells from Fowler, SOLID principles from
Martin, Pragmatic Programmer tips from Hunt & Thomas, audit-coined
terms ("load-bearing", "shadow", "kitchen-sink package"), and Python
packaging / pytest jargon. This file defines that vocabulary in plain
English, with a one-line pointer to the deep-dive where each term has
its most prominent usage.

**Out of scope.** Ethereum protocol terms (SSZ, BLS, KZG, fork-meta,
preset, vector, phase0, electra, …) are not defined here. They are
documented in consensus-specs's own specification under
`specs/<fork>/*.md`.

**How to use this file.** The alphabetical index below is the quick
lookup. Each term links to the section that defines it; sections are
short enough to scan.

---

## Alphabetical index

- **`__init__.py` as a marker file** — [Python packaging](#python-packaging)
- **`autouse` fixture** — [Pytest](#pytest)
- **Blast radius** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **Characterisation test** — [TDD and legacy code](#tdd-and-legacy-code-beck-feathers)
- **Comments-as-Deodorant** — [Refactoring smells](#refactoring-smells-fowler)
- **conftest.py** — [Pytest](#pytest)
- **Configure, Don't Integrate (Tip 38)** — [Pragmatic Programmer tips](#pragmatic-programmer-tips-hunt--thomas)
- **Data Clumps** — [Refactoring smells](#refactoring-smells-fowler)
- **Dead Code** — [Refactoring smells](#refactoring-smells-fowler)
- **DIP — Dependency Inversion Principle** — [SOLID and Clean Code](#solid-and-clean-code-martin)
- **Divergent Change** — [Refactoring smells](#refactoring-smells-fowler)
- **DRY (Tip 11)** — [Pragmatic Programmer tips](#pragmatic-programmer-tips-hunt--thomas)
- **Dual-mode flags / `is_pytest` / `is_generator`** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **Duplicated Code** — [Refactoring smells](#refactoring-smells-fowler)
- **Editable install (`pip install -e .`)** — [Python packaging](#python-packaging)
- **Eliminate Effects Between Unrelated Things (Tip 17)** — [Pragmatic Programmer tips](#pragmatic-programmer-tips-hunt--thomas)
- **Feature Envy** — [Refactoring smells](#refactoring-smells-fowler)
- **`find_packages`** — [Python packaging](#python-packaging)
- **FIRST tests** — [TDD and legacy code](#tdd-and-legacy-code-beck-feathers)
- **Fixture** — [Pytest](#pytest)
- **Frame inspection** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **God module / god class** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **`importmode` (`prepend` vs `importlib`)** — [Python packaging](#python-packaging)
- **`include_package_data` / `package_data`** — [Python packaging](#python-packaging)
- **Inappropriate Intimacy** — [Refactoring smells](#refactoring-smells-fowler)
- **ISP — Interface Segregation Principle** — [SOLID and Clean Code](#solid-and-clean-code-martin)
- **just / Justfile** — [Build tooling](#build-tooling)
- **Kitchen-sink package** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **Literate programming** — [Literate programming](#literate-programming-knuth)
- **Load-bearing** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **Long Method** — [Refactoring smells](#refactoring-smells-fowler)
- **Long Parameter List** — [Refactoring smells](#refactoring-smells-fowler)
- **Make / Makefile** — [Build tooling](#build-tooling)
- **Marker (`@pytest.mark.X`)** — [Pytest](#pytest)
- **MiniZinc** — [Build tooling](#build-tooling)
- **Misplaced Class** — [Refactoring smells](#refactoring-smells-fowler)
- **Monkey-patching** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **OCP — Open/Closed Principle** — [SOLID and Clean Code](#solid-and-clean-code-martin)
- **`package_dir`** — [Python packaging](#python-packaging)
- **`parametrize`** — [Pytest](#pytest)
- **PEP 420 (namespace packages)** — [Python packaging](#python-packaging)
- **PEP 517 (build backends)** — [Python packaging](#python-packaging)
- **PEP 735 (dependency groups)** — [Python packaging](#python-packaging)
- **Plugin (pytest)** — [Pytest](#pytest)
- **Primitive Obsession** — [Refactoring smells](#refactoring-smells-fowler)
- **`py_modules`** — [Python packaging](#python-packaging)
- **`pyproject.toml` vs `setup.py`** — [Python packaging](#python-packaging)
- **`pytest_collection_modifyitems`** — [Pytest](#pytest)
- **Replace Conditional with Polymorphism** — [Refactoring smells](#refactoring-smells-fowler)
- **Reversibility (Tip 26)** — [Pragmatic Programmer tips](#pragmatic-programmer-tips-hunt--thomas)
- **Separate Query from Modifier** — [Refactoring smells](#refactoring-smells-fowler)
- **Shadow (shadow code, shadow copy)** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **Shotgun Surgery** — [Refactoring smells](#refactoring-smells-fowler)
- **Smell** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **Speculative Generality** — [Refactoring smells](#refactoring-smells-fowler)
- **SRP — Single Responsibility Principle** — [SOLID and Clean Code](#solid-and-clean-code-martin)
- **Strategy** — [Design patterns](#design-patterns-gof)
- **Stringly Typed** — [Refactoring smells](#refactoring-smells-fowler)
- **Switch Statements** — [Refactoring smells](#refactoring-smells-fowler)
- **Tautological oracle** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)
- **Template Method** — [Design patterns](#design-patterns-gof)
- **Test seam** — [TDD and legacy code](#tdd-and-legacy-code-beck-feathers)
- **`top_level.txt`** — [Python packaging](#python-packaging)
- **tox** — [Build tooling](#build-tooling)
- **uv** — [Build tooling](#build-tooling)
- **Visitor** — [Design patterns](#design-patterns-gof)
- **WET (Write Everything Twice)** — [Audit-coined and colloquial-engineering terms](#audit-coined-and-colloquial-engineering-terms)

---

## Refactoring smells (Fowler)

### Comments-as-Deodorant

A comment used to explain or apologise for a confusing piece of code instead of cleaning the code up. The smell is the code, not the comment: a name change, an extracted helper, or an assertion would usually replace the prose. The comment also tends to drift out of sync with the code it explains, so it ends up actively misleading.

*Source:* Fowler, *Refactoring* (1999), p. 87.
*In this audit:* [decorator-stack.md](deep-dives/decorator-stack.md), [build-orchestration.md](deep-dives/build-orchestration.md), [package-export-boundary.md](deep-dives/package-export-boundary.md).

### Data Clumps

Several values that always travel together as separate parameters or fields, but never get wrapped in a type. The smell signals a missing concept: the clump wants to be a class with a name, validation, and behaviour. As long as it stays loose, every signature has to repeat all the parts in the right order, and a swap or a missing element fails late.

*Source:* Fowler, *Refactoring* (1999), p. 81.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) — `(spec, state)` is the canonical clump, threaded through nearly every helper without ever being bundled into a context object.

### Dead Code

Code that is no longer reached by any caller — an unreferenced function, a flag that nothing reads, an entire module nobody imports. It still has to be read, understood, and maintained when neighbouring code changes, so it imposes cost without paying any back. The fix is deletion; version control is the archive.

*Source:* Fowler, *Refactoring* (1999), p. 95.
*In this audit:* [build-orchestration.md](deep-dives/build-orchestration.md) and [secondary-findings.md](secondary-findings.md) (`helpers/shard_block.py`, unreachable generator scripts, the `disallow_untyped_defs` mypy line).

### Divergent Change

One module that changes for many unrelated reasons — adding a feature touches it, fixing a bug touches it, refactoring something else touches it. It is the inverse of Shotgun Surgery: there one change touches many modules; here many kinds of change touch one module. Either way the module is doing too much, and the fix is to split the responsibilities apart.

*Source:* Fowler, *Refactoring* (1999), p. 79.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) (helpers change for any rule tweak), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md) (`md_to_spec.py` changes for unrelated reasons).

### Duplicated Code

The same logic copied into two or more places — sometimes verbatim, sometimes with cosmetic edits. When the logic needs to change, every copy must be found and updated identically; missing one creates a subtle divergence that is hard to detect. The fix is to extract a single named function or class and have every site call it.

*Source:* Fowler, *Refactoring* (1999), p. 76.
*In this audit:* [fork-registration.md](deep-dives/fork-registration.md) (five near-identical builder functions), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md) (three caches loading from the same files).

### Feature Envy

A method that seems more interested in another object than the one it lives on — it pulls many fields off the other object and does most of its work there. It is a misplaced behaviour; moving the method onto the object it envies usually shortens the code and makes both classes more cohesive. The classic give-away is a method whose body is full of `other.x`, `other.y`, `other.z`.

*Source:* Fowler, *Refactoring* (1999), p. 80.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) — helpers operate almost entirely on `spec.<anything>` rather than on values they own.

### Inappropriate Intimacy

Two modules that know far too much about each other's internals — reaching into private state, depending on undocumented invariants, or coupling tightly through implementation details rather than a stable interface. A change in one is forced to ripple into the other for reasons that have nothing to do with their public contract. The fix is usually to introduce a clean boundary and respect it.

*Source:* Fowler, *Refactoring* (1999), p. 85.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md), [package-export-boundary.md](deep-dives/package-export-boundary.md), [decorator-stack.md](deep-dives/decorator-stack.md), [build-orchestration.md](deep-dives/build-orchestration.md).

### Long Method

A function or method long enough that you have to read it carefully to know what it does. The longer it grows, the more responsibilities it accumulates, and the harder it is to test or reuse any part of it. The fix is Extract Method: pull cohesive chunks out into well-named helpers and let the original function read like a table of contents.

*Source:* Fowler, *Refactoring* (1999), p. 76.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) (e.g. 67-line fork-conditional helpers), [decorator-stack.md](deep-dives/decorator-stack.md), [build-orchestration.md](deep-dives/build-orchestration.md), [secondary-findings.md](secondary-findings.md) (test functions over 100 lines).

### Long Parameter List

A function whose signature has so many parameters that callers have trouble remembering the order or filling in the right values. Often each new parameter was added defensively over time. The fix is usually to introduce a parameter object — most of the items belong together as a piece of state — or to push behaviour onto an object that already has the data.

*Source:* Fowler, *Refactoring* (1999), p. 78.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md), [secondary-findings.md](secondary-findings.md).

### Misplaced Class

A class — or, by extension, a module — that lives in the wrong package, far from the code it actually collaborates with. Readers expect to find behaviour next to the data it operates on; when it is parked elsewhere, navigation, testing, and ownership all suffer. The fix is to move it to the package where it belongs and let imports follow.

*Source:* Fowler, *Refactoring* (1999); also called "feature placement" in later editions.
*In this audit:* [directory-structure.md](deep-dives/directory-structure.md) and [helper-layer.md](deep-dives/helper-layer.md) (helpers split across `tests/` and `infra/`).

### Primitive Obsession

Using a built-in primitive (string, int, tuple, dict) where a small dedicated type would carry meaning. A `str` named `fork` is just a string to the type checker; nothing prevents it being passed where a validator name is expected. Wrapping it in a class — even a thin one — makes invalid combinations unrepresentable, gives a place to attach validation, and turns silent typos into compile-time errors.

*Source:* Fowler, *Refactoring* (1999), p. 80.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) (`SpecForkName = str`, fork names threaded as raw strings everywhere), [decorator-stack.md](deep-dives/decorator-stack.md), [secondary-findings.md](secondary-findings.md) (`parse_config_vars`, fork ordering as int).

### Replace Conditional with Polymorphism

A refactoring, not a smell — the canonical fix for the Switch Statements smell. The conditional is replaced by a small class hierarchy (one subclass per branch) where each subclass carries the behaviour for its own case. New cases extend the system by adding a class rather than by editing every existing call site.

*Source:* Fowler, *Refactoring* (1999), p. 255.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) is the deep-dive that names this refactoring as the cure for the `is_post_<fork>` cascades.

### Separate Query from Modifier

A refactoring (and a design rule, also known as Command-Query Separation) that says a function should either return a value or change state, not both. Functions that do both are surprising: callers cannot inspect a value without triggering side effects, and tests cannot exercise the read path independently of the write. The fix is to split the function into a pure query and a void command.

*Source:* Fowler, *Refactoring* (1999), p. 279; Meyer, *Object-Oriented Software Construction*, ch. 23.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) — helpers that yield, return, and mutate at once.

### Shotgun Surgery

A single conceptual change forces edits in many unrelated files. Adding a new fork, for example, touches `forks.py`, `constants.py`, the `.gitignore`, several Makefile recipes, and a YAML matrix — every site is a chance to forget one and ship a partial change. The remedy is to centralise the variation behind one extension point so a single edit propagates.

*Source:* Fowler, *Refactoring* (1999), p. 79.
*In this audit:* the most-cited smell in the audit — see [fork-registration.md](deep-dives/fork-registration.md), [helper-layer.md](deep-dives/helper-layer.md), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md), [build-orchestration.md](deep-dives/build-orchestration.md), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md), [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md).

### Speculative Generality

Abstractions, hooks, or extension points added "in case we need them" that no actual code ever uses. The generality has to be read, navigated, and maintained, but pays no rent. Worse, when a real need arrives, it usually does not fit the speculative shape and the abstraction has to be torn out anyway.

*Source:* Fowler, *Refactoring* (1999), p. 109.
*In this audit:* [compliance-runners.md](deep-dives/compliance-runners.md) (a runner framework with one user), [helper-layer.md](deep-dives/helper-layer.md) (`Spec` Protocol declared but unused), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md), [fork-registration.md](deep-dives/fork-registration.md).

### Stringly Typed

A sub-form of Primitive Obsession: encoding domain concepts as strings (operator names, fork names, mode flags, dispatch keys) and then dispatching on them with `if` chains or dict lookups. A typo is a runtime error at best and a silent fallthrough at worst, since the type system cannot tell one string from another. The fix is an enum, a dataclass, or a small class hierarchy that makes only valid values constructable.

*Source:* Fowler-derived; popularised online and used throughout the audit.
*In this audit:* [compliance-runners.md](deep-dives/compliance-runners.md) (mutation-operator dispatch, YAML behaviour-flag keys), [decorator-stack.md](deep-dives/decorator-stack.md) (`yield_fork_meta` payloads), [secondary-findings.md](secondary-findings.md) (BLS-backend selection, runner-to-handler dispatch).

### Switch Statements

A long `if`/`elif` chain or `match` block that selects behaviour based on a type or a tag. The smell is that adding a new case requires editing every site that switches on the same tag, instead of letting the new case bring its own behaviour with it. The standard fix is Replace Conditional with Polymorphism — turn the cases into subclasses (or strategies) that the switch dispatches to once, not many times.

*Source:* Fowler, *Refactoring* (1999), p. 82.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) (`is_post_<fork>` cascades), [fork-registration.md](deep-dives/fork-registration.md), [secondary-findings.md](secondary-findings.md) (epoch-processing dispatch, `get_random_ssz_object`).

---

## SOLID and Clean Code (Martin)

### DIP — Dependency Inversion Principle

High-level modules should not depend on low-level modules; both should depend on abstractions. In practice: the policy code (the spec, the helpers) should not import or know the names of concrete tools (a specific YAML library, a particular cache backend, the build system); it should depend on a small interface that someone else implements. Inverting the dependency lets pieces be tested and replaced independently.

*Source:* Martin, *Clean Architecture* (2017); originally Martin, "The Dependency Inversion Principle" (1996).
*In this audit:* [package-export-boundary.md](deep-dives/package-export-boundary.md) (runtime spec depends on test infra), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md), [secondary-findings.md](secondary-findings.md).

### ISP — Interface Segregation Principle

Clients should not be forced to depend on interfaces they do not use. A "fat" interface (or, in Python, a fat module that exposes everything) couples every consumer to every member, so any change ripples to all of them. The fix is many small role-shaped interfaces, each consumer depending only on what it actually needs.

*Source:* Martin, *Clean Architecture* (2017); originally Martin, *Agile Software Development* (2002).
*In this audit:* [fork-registration.md](deep-dives/fork-registration.md) — every fork's builder file gets handed the full spec surface even when it only contributes a couple of attributes.

### OCP — Open/Closed Principle

Software entities should be open for extension but closed for modification: adding a new case should add new code, not require editing existing code. A registration table, a polymorphic dispatch, or a plugin discovery mechanism are all ways to keep the existing code closed while letting new behaviour plug in. When OCP is violated you see the same edit repeated in many files for every new case (which is exactly Shotgun Surgery).

*Source:* Meyer, *Object-Oriented Software Construction* (1988); reformulated by Martin in *Clean Architecture* (2017).
*In this audit:* [README.md](README.md) names OCP as a guiding principle; the violations are concentrated in [fork-registration.md](deep-dives/fork-registration.md), [helper-layer.md](deep-dives/helper-layer.md), and [build-orchestration.md](deep-dives/build-orchestration.md).

### SRP — Single Responsibility Principle

A module, class, or function should have one reason to change. When several concerns share one piece of code, every concern's churn becomes that code's churn, and a change for one reason can break code that was only there for another. The remedy is to split along the axes of change, so each piece has a single owner and a single trigger for revision.

*Source:* Martin, *Clean Code* (2008), ch. 10; Martin, *Clean Architecture* (2017).
*In this audit:* [README.md](README.md) names SRP as a guiding principle; concrete violations in [build-orchestration.md](deep-dives/build-orchestration.md), [fork-registration.md](deep-dives/fork-registration.md), and [secondary-findings.md](secondary-findings.md) (long multi-purpose test functions, the YAML output writer).

---

## Design patterns (GoF)

### Strategy

A design pattern where interchangeable variants of an algorithm are packaged as objects implementing a common interface, and the caller picks one at runtime. It replaces a `switch` over a string or enum with a polymorphic call: each strategy carries its own logic, and adding a strategy means adding a class, not editing every call site. The classic use case in this audit would be one Strategy per fork, or one per BLS backend.

*Source:* Gamma, Helm, Johnson, Vlissides, *Design Patterns* (1994), p. 315.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md), [decorator-stack.md](deep-dives/decorator-stack.md), [secondary-findings.md](secondary-findings.md) (proposed `BLSBackend` Strategy).

### Template Method

A design pattern where a base class fixes the overall shape of an algorithm — the order of steps — and subclasses fill in specific steps by overriding hook methods. It is the right shape when the skeleton is genuinely shared and only the variant pieces differ. It becomes an anti-pattern when there is no real base class, just a long function with embedded conditionals and ad-hoc extension points pretending to be hooks.

*Source:* Gamma, Helm, Johnson, Vlissides, *Design Patterns* (1994), p. 325.
*In this audit:* [fork-registration.md](deep-dives/fork-registration.md) — `objects_to_spec` is identified as a degraded Template Method (the skeleton is there, but there is no class hierarchy and the "hooks" are inline conditionals).

### Visitor

A design pattern that separates an operation from the object structure it traverses: each visitor is a class with one method per node type, and the structure calls back into the visitor as it walks. It pays off when many different operations need to run over the same shape, since each operation lives in one class instead of being scattered across the nodes. The trade-off is that adding a new node type requires updating every visitor.

*Source:* Gamma, Helm, Johnson, Vlissides, *Design Patterns* (1994), p. 331.
*In this audit:* [secondary-findings.md](secondary-findings.md) — proposed as the right shape for SSZ-type traversal and for the AST/markdown walks currently done with isinstance chains.

---

## Pragmatic Programmer tips (Hunt & Thomas)

### Configure, Don't Integrate (Tip 38)

Variation should live in declarative configuration that the code reads at runtime, not in code branches that hard-code each variant. The test is whether adding a new variant requires editing source files in many places (integrate) or adding one entry to a config file (configure). Hard-coded fork names, runner names, and format names are the audit's recurring failure mode here.

*Source:* Hunt & Thomas, *The Pragmatic Programmer* (1999), Tip 38.
*In this audit:* [compliance-runners.md](deep-dives/compliance-runners.md), [vector-formats.md](deep-dives/vector-formats.md), [package-export-boundary.md](deep-dives/package-export-boundary.md), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md).

### DRY (Tip 11) — Don't Repeat Yourself

Every piece of knowledge should have a single, unambiguous, authoritative representation in the system. Where the same fact lives in two places, the two will eventually disagree, and the system has to keep them in sync — by convention, by code review, or by code that copies one into the other. The audit treats DRY violations as the smell most likely to become Shotgun Surgery later.

*Source:* Hunt & Thomas, *The Pragmatic Programmer* (1999), Tip 11.
*In this audit:* [fork-registration.md](deep-dives/fork-registration.md), [vector-formats.md](deep-dives/vector-formats.md), [helper-layer.md](deep-dives/helper-layer.md).

### Eliminate Effects Between Unrelated Things (Tip 17)

Modules and components should not influence each other through hidden channels — global state, import order, monkey-patches, side-effecting imports. The point isn't "no globals ever"; it's that two pieces of code which look unrelated should also *be* unrelated. When this is violated, a change in one place silently breaks something far away.

*Source:* Hunt & Thomas, *The Pragmatic Programmer* (1999), Tip 17.
*In this audit:* [decorator-stack.md](deep-dives/decorator-stack.md), [package-export-boundary.md](deep-dives/package-export-boundary.md), [compliance-runners.md](deep-dives/compliance-runners.md), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md).

### Reversibility (Tip 26)

There are no final decisions; design so that today's choice can be undone tomorrow. Architecture should keep options open — file formats, build tools, dependency managers, directory layouts. The audit cites Reversibility when a tool choice ossifies because too many other things have grown to depend on it.

*Source:* Hunt & Thomas, *The Pragmatic Programmer* (1999), Tip 26.
*In this audit:* [build-orchestration.md](deep-dives/build-orchestration.md).

---

## TDD and legacy code (Beck, Feathers)

### Characterisation test

A test written *after* the code, whose only job is to capture and lock in the system's current behaviour — including the buggy parts. You run the system, observe what it does, and encode that as the assertion. Characterisation tests are the safety net you build before refactoring legacy code; without them, every behaviour-preserving refactor is a guess. (Spelled "characterization" in Feathers; the audit uses the British spelling.)

*Source:* Feathers, *Working Effectively with Legacy Code* (2004).
*In this audit:* [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md).

### FIRST tests (Beck's properties of good unit tests)

A test should be **F**ast (runs in milliseconds), **I**ndependent (any order, no shared state), **R**epeatable (deterministic — same input, same outcome), **S**elf-validating (passes or fails on its own; no human eyeballs the output), and **T**imely (written close to the code, not bolted on later). The audit cites FIRST mostly to call out Self-validating violations — tests that produce output a human or another tool has to grade.

*Source:* Beck, *Test-Driven Development: By Example* (2002).
*In this audit:* [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md), [compliance-runners.md](deep-dives/compliance-runners.md), [decorator-stack.md](deep-dives/decorator-stack.md), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md).

### Test seam

A place in the code where you can change behaviour for tests without editing the production code path — an injection point, a configurable hook, a mockable dependency. Feathers's central insight is that legacy code is hard to test precisely because it has too few seams. The audit flags a particularly bad failure mode: an *invisible* seam, where the production code is silently replaced by a test-time substitute through import-order tricks or module-level shadowing.

*Source:* Feathers, *Working Effectively with Legacy Code* (2004).
*In this audit:* [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md), [decorator-stack.md](deep-dives/decorator-stack.md), [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md), [static-analysis-config.md](deep-dives/static-analysis-config.md).

---

## Literate programming (Knuth)

### Literate programming

A style, due to Knuth, where the source artefact is prose with code embedded inside it — the program is meant to be read by humans first and tangled into compilable code by a tool. The canonical implementation is Knuth's WEB: one source, two outputs (a typeset document for humans, source files for the compiler). The audit uses "literate-programming half-step" to describe code that pays the cost of being authored as prose-with-embedded-code without buying the benefit of a single source of truth.

*Source:* Knuth, *Literate Programming* (1984).
*In this audit:* [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md).

---

## Audit-coined and colloquial-engineering terms

### Blast radius

The set of code that has to change, or is at risk of breaking, when you change one thing. A change with a small blast radius is local — it touches one file. A change with a large blast radius ripples through the codebase. The audit uses blast radius to describe what makes Shotgun Surgery painful and to argue that DRY violations and god modules raise the cost of every future change.

*Source:* engineering colloquialism, no canonical source.
*In this audit:* used as background vocabulary for Shotgun Surgery findings throughout [fork-registration.md](deep-dives/fork-registration.md) and [helper-layer.md](deep-dives/helper-layer.md).

### Dual-mode flags (`is_pytest` / `is_generator`)

A boolean (or set of booleans) that branches the same code between two execution contexts — typically "running under pytest" vs "running under the test-vector generator". The flag has to be threaded through the code, set at exactly the right moment, and read by exactly the right callers; getting it wrong means tests pass under one mode and fail under the other. The audit's canonical instances are the `is_pytest` and `is_generator` flags on a context object, branched at six-plus call sites; the modern pytest replacement is two distinct entry points (a runner and a CLI) sharing a fixture, or a marker plus a `pytest_collection_modifyitems` hook that picks tests for the generator job, with no flag check inside the test body.

*Source:* audit-coined; engineering colloquialism for "mode flag".
*In this audit:* [decorator-stack.md](deep-dives/decorator-stack.md) (the canonical write-up), [compliance-runners.md](deep-dives/compliance-runners.md), [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md).

### Frame inspection

Walking the Python call stack at runtime — typically via `sys._getframe()` or the `inspect` module — to read a caller's local variables, module name, or filename. It's a fragile dynamic technique because the result depends on *who called you and from where*, which static analysis cannot see; rename a caller, and the inspection silently picks up a different frame.

*Source:* engineering colloquialism, no canonical source (Python jargon).
*In this audit:* [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md).

### God module / god class

A module or class that knows or does too much — cousin of Fowler's Long Method, but at module scale. The symptom is a single file in the high hundreds or low thousands of lines, importing widely and exporting widely, where every change to the system seems to require editing it. The audit's canonical example is a 996-line helper module threaded with `is_post_<fork>(spec)` cascades.

*Source:* Riel, *Object-Oriented Design Heuristics* (1996), "God Class"; engineering colloquialism for the module-scale variant.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md), [package-export-boundary.md](deep-dives/package-export-boundary.md), [README.md](README.md).

### Kitchen-sink package

A distribution package that exports everything its repository contains, with no curation of what's part of the public API and what isn't. Tests, internal helpers, generated data, build scripts — all of it ships in the wheel. Consumers can import any of it, so any of it becomes a de-facto public surface that the maintainers cannot change without breaking somebody.

*Source:* engineering colloquialism, no canonical source.
*In this audit:* [package-export-boundary.md](deep-dives/package-export-boundary.md).

### Load-bearing

A piece of code, configuration, file path, import order, or naming convention that lots of other things depend on — silently. If you change it, things break in places that had no obvious connection to it, and the failure mode is rarely a clear error message. The audit uses load-bearing as a warning label: this looks innocuous, but it isn't.

*Source:* engineering colloquialism, no canonical source.
*In this audit:* used heavily as section headings; see [helper-layer.md](deep-dives/helper-layer.md), [build-orchestration.md](deep-dives/build-orchestration.md), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md), [compliance-runners.md](deep-dives/compliance-runners.md), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md), [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md), [package-export-boundary.md](deep-dives/package-export-boundary.md).

### Monkey-patching

Replacing a function, method, or attribute at runtime by reassigning the name — typically `module.func = my_replacement` — instead of changing the source. It's a quick way to insert a test substitute or a cache, but it leaves the source code lying about what runs at runtime. The audit treats module-level monkey-patches as a particular kind of invisible test seam.

*Source:* engineering colloquialism, no canonical source (long-standing Python jargon).
*In this audit:* [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md), [secondary-findings.md](secondary-findings.md).

### Shadow (shadow code, shadow copy)

A second copy of a name — a function, a module, an import path — created at runtime so that lookups resolve to the copy instead of the original. A "shadow function" hides the original behind an identically named replacement; a "shadow copy" of a module makes `import a.b.c` and `import b.c` both resolve, but to different objects. Shadows are usually invisible to static analysis because they exist only after the import system has run, and reviewers reading the source see only one name where two exist at runtime.

*Source:* engineering colloquialism, no canonical source.
*In this audit:* [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md) (`cache_this` shadow), [decorator-stack.md](deep-dives/decorator-stack.md) (dual-import-path shadow), [package-export-boundary.md](deep-dives/package-export-boundary.md).

### Smell

A structural cue that something is off in the code, without proving that anything is wrong. Smells aren't bugs — code with a smell can be correct — but they're the patterns that experience says will turn into bugs or maintenance pain later. Fowler's *Refactoring* catalogues the canonical list (Long Method, Shotgun Surgery, Primitive Obsession, etc.) and the audit uses "smell" as an umbrella for findings whose problem is structural rather than behavioural.

*Source:* Fowler, *Refactoring* (1999), Chapter 3, "Bad Smells in Code"; engineering colloquialism in wider use.
*In this audit:* used throughout; see [README.md](README.md) for the smell-by-scale framing.

### Tautological oracle

A test setup where the system-under-test is its own oracle for correctness — the test asks the implementation what the right answer is and then checks that the implementation produces it. Round-trip tests (encode then decode, expect equality) are the textbook example: they prove the implementation is internally consistent, not that it's correct against any external definition. A tautological oracle catches nothing the implementation has agreed with itself about.

*Source:* audit-coined; defined in [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md).
*In this audit:* [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md).

### WET (Write Everything Twice)

The deliberate or accidental opposite of DRY: the same knowledge expressed in two or more places. Sometimes glossed as "We Enjoy Typing". The audit distinguishes intentional WET (the `execution-specs` per-fork copies, where each fork's source is a full copy of its predecessor as a deliberate readability and review choice) from accidental WET (duplicated decorator stacks, duplicated import sets, duplicated YAML schemas — duplication that nobody chose).

*Source:* engineering colloquialism, no canonical source; coined as the negation of Hunt & Thomas's DRY.
*In this audit:* [fork-registration.md](deep-dives/fork-registration.md), [directory-structure.md](deep-dives/directory-structure.md), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md), [decorator-stack.md](deep-dives/decorator-stack.md), [secondary-findings.md](secondary-findings.md).

---

## Python packaging

### `__init__.py` as a marker file

A file whose presence turns a directory into a *regular* Python package — distinct from a PEP 420 *namespace* package. A regular package owns a single location on disk and lets pytest's default `prepend` import mode disambiguate same-named modules across siblings via the full dotted path; a namespace package has none of that and is only needed when the same logical package is split across multiple distributions. The file does not need to contain any code; its mere existence is the signal.

*Source:* Python documentation — *The import system: regular packages*.
*In this audit:* [secondary-findings.md](secondary-findings.md) (119 empty `__init__.py` files load-bearing under `importmode=prepend`), [package-export-boundary.md](deep-dives/package-export-boundary.md), [fork-registration.md](deep-dives/fork-registration.md).

### Editable install (`pip install -e .`)

An install mode that points the Python environment at a working copy of the source tree rather than copying files into `site-packages`, so edits in the repo show up at the next import without reinstalling. Modern editable installs are standardised by PEP 660 on top of PEP 517 build backends, and most backends materialise the link as a `__editable___<name>_finder.py` shim in `site-packages`. Editable installs are how a contributor gets a development environment that matches what tests and CI see.

*Source:* PEP 660 — *Editable installs for pyproject.toml based builds (wheel based)* (2021).
*In this audit:* [self-referential-package-layout.md](deep-dives/self-referential-package-layout.md) (the editable-install finder is the route by which the same module ends up reachable under two import paths), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md), [compliance-runners.md](deep-dives/compliance-runners.md).

### `find_packages`

A setuptools helper, called inside `setup.py`, that walks a directory and returns the list of regular packages it finds — anywhere a directory contains `__init__.py`. It is the conventional way to populate the `packages=` argument of `setup()` without hand-listing every subpackage. The walk respects `where=` and exclude patterns but otherwise picks up *everything* under that root, which is why a misplaced `__init__.py` can silently widen the wheel.

*Source:* setuptools documentation — *Package discovery*.
*In this audit:* [package-export-boundary.md](deep-dives/package-export-boundary.md) (`find_packages(where="tests/core/pyspec")` is the line that turns the entire test-helper tree into installed wheel content), [secondary-findings.md](secondary-findings.md).

### `importmode` (pytest's `prepend` vs `importlib`)

A pytest configuration option that controls how test files are loaded into `sys.modules`. The default `prepend` mode prepends each test file's directory onto `sys.path` and imports the file under its short module name, which means duplicate filenames across the tree must be disambiguated by `__init__.py` chains forming unique dotted paths. The newer `importlib` mode uses `importlib` machinery directly, requires no `__init__.py` files, and is the recommended setting for modern test trees; it is opt-in for backwards compatibility.

*Source:* pytest documentation — *Choosing an import mode*.
*In this audit:* [secondary-findings.md](secondary-findings.md) ("119 `__init__.py` files load-bearing because of `importmode=prepend`" — the audit's clearest illustration of the cost of the default).

### `include_package_data` / `package_data`

Two `setup.py` keyword arguments that control which non-Python files travel into the built wheel. `package_data` is a per-package mapping of glob patterns; `include_package_data=True` instead delegates to whatever the source-control plugin (typically `setuptools-scm` or `MANIFEST.in`) reports as tracked. The two are usually mutually exclusive in practice, and setting `include_package_data=False` while populating `package_data` is the explicit "I will list the data files myself" stance.

*Source:* setuptools documentation — *Including data files*.
*In this audit:* [package-export-boundary.md](deep-dives/package-export-boundary.md) (the wheel's data-shipping shape is achieved by listing non-package directories — `configs`, `presets`, `specs`, `sync` — in `packages=` so `package_data` can attach files to them).

### `package_dir`

A `setup.py` keyword argument that maps logical package names to filesystem locations, decoupling the dotted import name from where the source lives on disk. A typical value is `{"" : "src"}` for a `src/` layout, or `{"foo": "vendor/foo"}` to ship a renamed vendor tree. Without `package_dir` the package name and the directory name must match.

*Source:* setuptools documentation — *Using a "src" layout*.
*In this audit:* [self-referential-package-layout.md](deep-dives/self-referential-package-layout.md) (`package_dir = {"eth_consensus_specs": "tests/core/pyspec/eth_consensus_specs"}` is the line that tells the build the package lives under `tests/`), [package-export-boundary.md](deep-dives/package-export-boundary.md).

### PEP 420 (namespace packages)

The PEP that defines *namespace packages* — a package whose directory does not contain `__init__.py` and whose contents may be assembled across multiple distributions on `sys.path`. The relevant practical consequence is that the absence of `__init__.py` no longer means "not a package"; under PEP 420 every bare directory on the path is a candidate namespace contribution. Most projects do not want namespace packages and should keep `__init__.py` to opt out.

*Source:* PEP 420 — *Implicit Namespace Packages* (2012).
*In this audit:* [static-analysis-config.md](deep-dives/static-analysis-config.md) (the ruff rule `INP` / `flake8-no-pep420` flags missing `__init__.py` to prevent accidental namespace packages), [secondary-findings.md](secondary-findings.md).

### PEP 517 (build backends)

The PEP that defines a build-system-independent interface between packaging frontends (`pip`, `build`, `uv`) and build backends (`setuptools`, `hatchling`, `flit-core`, `poetry-core`). It moved the build-backend choice into `pyproject.toml`'s `[build-system]` table, replacing the implicit "everyone calls `setup.py` directly" model. Among other things, it allows a backend to declare its own build-time dependencies and to produce wheels via a defined hook protocol rather than ad-hoc invocation.

*Source:* PEP 517 — *A build-system independent format for source trees* (2015).
*In this audit:* [package-export-boundary.md](deep-dives/package-export-boundary.md), [directory-structure.md](deep-dives/directory-structure.md), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md) (the spec generator could plausibly be a PEP 517 backend hook rather than a Make target).

### PEP 735 (dependency groups)

The PEP that adds a `[dependency-groups]` table to `pyproject.toml` for declaring named groups of development dependencies — `lint`, `test`, `docs`, etc. — outside of the `[project.optional-dependencies]` table that ships with the wheel. Groups are not extras and do not become part of the distribution; they exist for tools like `uv`, `pip`, and `tox-uv` to install in a development environment. Accepted October 2024 and supported by `uv` natively.

*Source:* PEP 735 — *Dependency Groups in pyproject.toml* (2024).
*In this audit:* [static-analysis-config.md](deep-dives/static-analysis-config.md) (both comparables use PEP 735 dependency groups; consensus-specs does not), [build-orchestration.md](deep-dives/build-orchestration.md), [package-export-boundary.md](deep-dives/package-export-boundary.md), [README.md](README.md).

### `py_modules`

A `setup.py` keyword argument listing top-level *single-file* modules to include in the distribution — used when something is a `foo.py` file rather than a `foo/` package. It is mutually exclusive in spirit with `packages=` for the same name: a name should be one or the other, not both. Listing the same name in both `packages=` and `py_modules=` is redundant and tends to be a holdover from refactoring.

*Source:* setuptools documentation — *setup() keyword arguments*.
*In this audit:* [package-export-boundary.md](deep-dives/package-export-boundary.md) (`py_modules=["eth_consensus_specs"]` alongside `packages=find_packages(...)` is the redundant case).

### `pyproject.toml` vs `setup.py`

Two configuration files that can declare a Python distribution. `pyproject.toml` is the modern, declarative format introduced by PEP 518 / 517 / 621 and now holds project metadata, build-backend choice, dependencies, and tool config; `setup.py` is the legacy imperative `setuptools` entry point. New projects should use `pyproject.toml` exclusively; a `setup.py` survives where the build needs to run arbitrary Python code at install time, which is itself usually a smell.

*Source:* PEP 621 — *Storing project metadata in pyproject.toml* (2020).
*In this audit:* [self-referential-package-layout.md](deep-dives/self-referential-package-layout.md), [build-orchestration.md](deep-dives/build-orchestration.md), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md) (a 28-line `setup.py` survives because the package is generated by Make, not because setuptools needs it).

### `top_level.txt`

A wheel-metadata file, written into `<dist-info>/top_level.txt`, that lists every top-level importable name the wheel introduces into `site-packages`. It is generated by setuptools from the union of `packages=` and `py_modules=` and is the canonical list of what installing the wheel makes globally importable. It is also the shortest correct answer to the question "what name collisions am I introducing into a downstream environment?".

*Source:* setuptools / wheel documentation — *Wheel metadata*.
*In this audit:* [package-export-boundary.md](deep-dives/package-export-boundary.md) (the produced `top_level.txt` shows that installing the wheel introduces `eth_consensus_specs`, `configs`, `presets`, `specs`, `sync` as global top-level names, which is the import-collision surface the deep-dive analyses).

---

## Pytest

### `autouse` fixture

A pytest fixture that runs automatically for every test in its scope without the test having to request it by name. It is the right tool for cross-cutting setup that every test in a module or session needs (one-time database connect, monkey-patches, environment toggles); it is the wrong tool for per-test state because invisibility makes the test's preconditions impossible to read off the signature. Two `autouse` fixtures with conflicting effects in sibling conftests will execute in both contexts, which is a frequent source of "why does this test pass here but not there" bugs.

*Source:* pytest documentation — *Autouse fixtures*.
*In this audit:* [decorator-stack.md](deep-dives/decorator-stack.md) (four `autouse` fixtures rebind module-level globals as a side channel), [compliance-runners.md](deep-dives/compliance-runners.md) (two conftests with opposite `autouse` BLS state), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md).

### conftest.py (discovery rules)

The pytest-specific filename for a per-directory plugin. Pytest collects every `conftest.py` from the rootdir down to the test file and chains them: fixtures and hooks defined higher up are inherited by everything below, and a deeper conftest can override or extend its parents. There is no import; collection is filename-based and automatic, which is what makes conftests both convenient and easy to over-use.

*Source:* pytest documentation — *conftest.py: sharing fixtures across multiple files*.
*In this audit:* [self-referential-package-layout.md](deep-dives/self-referential-package-layout.md) (the dual-mutation conftest workaround), [compliance-runners.md](deep-dives/compliance-runners.md) (two conftests with deliberately opposite BLS state), [decorator-stack.md](deep-dives/decorator-stack.md), [helper-layer.md](deep-dives/helper-layer.md).

### Fixture

In pytest, a function decorated with `@pytest.fixture` whose return value is injected into any test that names the fixture as an argument; pytest handles setup, teardown, and caching by scope (`function`, `module`, `session`). Fixtures are how dependencies are made explicit — a test signature reads as a list of preconditions — and how teardown is made deterministic. The term is unrelated to Django or Rails fixtures, which mean "preloaded test data files".

*Source:* pytest documentation — *About fixtures*.
*In this audit:* [helper-layer.md](deep-dives/helper-layer.md) (the helper layer is largely state-builders that should be fixtures), [decorator-stack.md](deep-dives/decorator-stack.md), [ad-hoc-caching.md](deep-dives/ad-hoc-caching.md), [compliance-runners.md](deep-dives/compliance-runners.md), [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md).

### Marker (`@pytest.mark.X`)

A label attached to a test (or a class of tests) using the `@pytest.mark.<name>` decorator. Markers do not change behaviour on their own; they are metadata that hooks, plugins, or `-m <expr>` filters consult to select, skip, or transform tests. Custom markers should be declared in `pyproject.toml`'s `[tool.pytest.ini_options].markers` so a typo is a warning, not a silent no-op.

*Source:* pytest documentation — *How to mark test functions with attributes*.
*In this audit:* [decorator-stack.md](deep-dives/decorator-stack.md) (the eleven hand-rolled `with_*` decorators reduce to `@pytest.mark.fork(...)` plus a collection hook), [fork-registration.md](deep-dives/fork-registration.md), [compliance-runners.md](deep-dives/compliance-runners.md), [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md), [README.md](README.md).

### `parametrize`

The pytest marker `@pytest.mark.parametrize("name", [...])` that runs a test once per element of an input list, with each iteration appearing as a separately named test in the run report. It is the idiomatic alternative to a hand-written loop inside a test and to the older "generate one test class per case" patterns. Parametrize composes with fixtures: fixtures can themselves be `params=`-decorated, which gives factory-shaped test data without the test body having to know.

*Source:* pytest documentation — *How to parametrize fixtures and test functions*.
*In this audit:* [ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md) (the 10 cases files become `parametrize` parameters), [compliance-runners.md](deep-dives/compliance-runners.md), [decorator-stack.md](deep-dives/decorator-stack.md).

### Plugin (pytest)

A Python package (or a single `conftest.py`) that registers hooks, fixtures, or markers via pytest's plugin protocol. Plugins are how pytest's behaviour is extended without monkey-patching: registration is by entry point (for installed plugins) or by file presence (for `conftest.py`). The user-author-facing payoff is that a project's bespoke testing concepts (fork selection, BLS toggle, yield-collection) can live in a single named plugin rather than being scattered across decorators, autouse fixtures, and module-level globals.

*Source:* pytest documentation — *Writing plugins*.
*In this audit:* [decorator-stack.md](deep-dives/decorator-stack.md) (proposes a single `framework/plugins/pyspec.py` plugin to absorb the decorator stack), [package-export-boundary.md](deep-dives/package-export-boundary.md), [fork-registration.md](deep-dives/fork-registration.md), [directory-structure.md](deep-dives/directory-structure.md).

### `pytest_collection_modifyitems`

A pytest hook that runs after test discovery and receives the full list of collected items, letting a plugin reorder, deselect, or re-mark them before the run starts. It is the canonical place to implement marker-based filtering: e.g. `@pytest.mark.fork("electra")` on tests, plus a `pytest_collection_modifyitems` that drops items whose marker does not match the run's target fork. Doing the same selection at decorator-application time (as the audit subject does) means each test has to be re-decorated rather than re-filtered, which is a much heavier operation.

*Source:* pytest documentation — *Hookspec: `pytest_collection_modifyitems`*.
*In this audit:* [decorator-stack.md](deep-dives/decorator-stack.md) (the modern pytest replacement for the `with_*` decorator family is a marker plus a `pytest_collection_modifyitems` hook), [fork-registration.md](deep-dives/fork-registration.md).

---

## Build tooling

### just / Justfile

A declarative task runner whose `Justfile` is a list of named recipes — closer to a config file than to Make's procedural rule graph. Recipes can take arguments, depend on each other, group under namespaces, and run in any shell; there is no incremental-build / dependency-tracking layer (that is what makes it declarative rather than a build system). It is the comparable's chosen orchestration layer for `execution-specs`.

*Source:* `just` — *A handy way to save and run project-specific commands*.
*In this audit:* [build-orchestration.md](deep-dives/build-orchestration.md) (`execution-specs/Justfile` is the comparable's reference shape: ~365 lines of grouped, named recipes).

### Make / Makefile

The 1976-vintage build system for Unix, organised around *rules* of the form "target: prerequisites; recipe". Make's strength is incremental builds — it skips a recipe if its target is newer than every prerequisite — and its weakness is that the recipe language is shell, the variable language is Make-specific, and the two compose poorly into anything resembling structured configuration. The axis the audit highlights is *imperative* (Make: rules with side effects, ordering matters) versus *declarative* (Justfile / tox: named recipes that say what to run, not how to compose).

*Source:* GNU Make manual.
*In this audit:* [build-orchestration.md](deep-dives/build-orchestration.md) (the 332-line hand-written `Makefile` is the primary orchestration layer, and the deep-dive's central thesis is that an imperative cascade should be replaced by a declarative orchestrator), [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md), [self-referential-package-layout.md](deep-dives/self-referential-package-layout.md).

### MiniZinc

A high-level constraint-modelling language with a separate solver toolchain — a `.mzn` model declares variables and constraints, the `minizinc` CLI compiles it to a back-end solver (Gecode, Chuffed, OR-Tools), and a Python binding (`minizinc` on PyPI) wraps invocation as `Instance`/`Model`/`Solver` objects. The engineering-relevant gist for this audit is that pulling MiniZinc in makes a Python test dependency depend on a system-wide non-Python toolchain, with all the install-friction that implies.

*Source:* MiniZinc — *A free and open-source constraint modeling language*.
*In this audit:* [compliance-runners.md](deep-dives/compliance-runners.md) (`compliance_runners/fork_choice/model/*.mzn` are MiniZinc constraint models that generate test instances), [package-export-boundary.md](deep-dives/package-export-boundary.md) (the wheel currently ships `minizinc` as a runtime dep alongside `pytest`, `pytest-xdist`, `ckzg`, `deepdiff`, `psutil`).

### tox

A test-environment manager that creates an isolated virtualenv per declared `[testenv:<name>]` in `tox.ini` and runs the configured commands inside it. With the modern `tox-uv` runner it uses `uv` for environment construction, which is dramatically faster than the legacy `virtualenv` path. tox is older than Justfile and has a stricter "one env per recipe" model; both are declarative compared to Make.

*Source:* tox documentation.
*In this audit:* [build-orchestration.md](deep-dives/build-orchestration.md) (`leanSpec` uses `tox.ini` with `runner = uv-venv-lock-runner`; `execution-specs` migrated *away* from tox to `just`; consensus-specs has a non-functioning `tox.ini`).

### uv

The Astral package and project manager — a single Rust binary that subsumes `pip`, `pip-tools`, `virtualenv`, and `pyenv`, plus a `uv run` command that resolves and executes a project's commands inside the right environment without a manual activate step. It supports PEP 735 dependency groups natively and ships a `[tool.uv]` table for project-level configuration. It is the de facto runtime for both comparable repos.

*Source:* uv documentation (`docs.astral.sh/uv`).
*In this audit:* [build-orchestration.md](deep-dives/build-orchestration.md) (`uv` is underneath everything via `UV_RUN := uv run` but with no `[tool.uv]` block in `pyproject.toml`), [static-analysis-config.md](deep-dives/static-analysis-config.md), [package-export-boundary.md](deep-dives/package-export-boundary.md).
