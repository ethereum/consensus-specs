# consensus-specs — fork registration (deep-dive)

Adding one new fork to `consensus-specs` is not "edit one place" but
rather "edit a dozen places, plus write a new builder class that
copy-pastes most of its peers". The codebase models a fork as nine to
twelve separate registrations spread across `pysetup/`, the build
system (`Makefile`, `setup.py`), version control hygiene
(`.gitignore`), and CI configuration (four workflow files plus a
labeler config). None of these registrations is derived from any of
the others; each is a distinct manual edit to a distinct file.

Adjacent guides:
[directory-structure.md](directory-structure.md) (the per-fork
`.gitignore` block goes away when the package leaves `tests/`),
[self-referential-package-layout.md](self-referential-package-layout.md)
(same root cause for the `.gitignore` enumeration),
[ad-hoc-caching.md](ad-hoc-caching.md) (the `cache_this` string-
template that lives in the largest builder, `phase0.py`, is mechanism
#8 of the caching system).

## The shape of the problem

A "fork" is, conceptually, a single new artifact: a spec name, a
parent fork, a directory of markdown specs, possibly a custom
`ExecutionEngine` shape, and a small set of new types and functions.
The codebase models that artifact as nine to twelve separate
registrations spread across `pysetup/`, the build system
(`Makefile`, `setup.py`), version control hygiene (`.gitignore`),
and CI configuration (four workflow files plus a labeler config).
None of these registrations is derived from any of the others: each is
a distinct manual edit to a distinct file. The result is the canonical
**Shotgun Surgery** smell (Fowler, *Refactoring*, 1999, p. 79) — a
single conceptual change that fans out across many physical sites.

The per-fork builder class compounds the problem: each `<fork>.py`
under `pysetup/spec_builders/` is, on closer inspection, a near-
verbatim copy of a sibling, with one or two methods overridden.
`NoopExecutionEngine` is duplicated five times. Most builders override
two of `BaseSpecBuilder`'s twelve hooks and inherit the rest as no-ops.

## Proof, by line (the N places, with concrete count)

To register a hypothetical new fork "foobar" whose parent is `heze`,
the maintainer must edit **at least 11 files** at **at least 15 distinct
loci**, and write **one new file**:

1. **`pysetup/constants.py:1–11`** — add `FOOBAR = "foobar"` to the
   bare-string fork-name registry.
2. **`pysetup/md_doc_paths.py:3–14`** — add `FOOBAR` to the import
   block; **`md_doc_paths.py:16–27`** — add the genealogy entry
   `FOOBAR: HEZE,` to the `PREVIOUS_FORK_OF` dict. This dict is the
   only place the fork tree is encoded; it is enforced nowhere.
3. **NEW `pysetup/spec_builders/foobar.py`** — write a class deriving
   from `BaseSpecBuilder`. Realistically the maintainer copies the
   nearest sibling (`heze.py`, ~77 lines) wholesale and edits names.
4. **`pysetup/spec_builders/__init__.py:1–10`** — add
   `from .foobar import FoobarSpecBuilder`; **`__init__.py:12–26`** —
   add `FoobarSpecBuilder,` to the tuple inside `spec_builders`. The
   import list and the tuple are two separate places that must stay in
   sync.
5. **`Makefile:5–15`** — add `foobar` to the line-continued
   `ALL_EXECUTABLE_SPEC_NAMES` variable. This variable feeds
   `Makefile:218` (`COV_SCOPE_ALL`) and `Makefile:273` (`MYPY_SCOPE`)
   transitively; forgetting it silently disables coverage and type
   checking for the new fork rather than failing.
6. **`.gitignore:18–27`** — add
   `tests/core/pyspec/eth_consensus_specs/foobar/`. This is the
   per-fork shotgun documented in
   [self-referential-package-layout.md](self-referential-package-layout.md).
7. **`.github/labeler.yml`** — add a 4-line block (`foobar:` /
   `changed-files:` / `any-glob-to-any-file:` / three globs).
8. **`.github/workflows/checks.yml:119–128`** — add `- foobar` to the
   matrix list.
9. **`.github/workflows/tests.yml`** — four separate edits in one
   file: (a) `inputs.foobar` declaration block at lines 24–58; (b) the
   `default: true` boolean toggle; (c) the schedule list literal at
   line 106 (`forks='[..."foobar"]'`); (d) the bash `selected+=`
   conditional at lines 109–117.
10. **`.github/workflows/release.yml:53–61`** — add `- foobar` to the
    fork matrix.
11. **`.github/workflows/comptests.yml`** — add input block (4 lines),
    the schedule list at line 90, and the `selected+=` block at
    lines 93–99 (three edits).

That is 11 files, ≥15 distinct edit loci, and one new file —
**>16 manual touch points** for a single conceptual addition. Most of
these are unguarded by any cross-checking: there is no test that
asserts "every name in `PREVIOUS_FORK_OF` has a builder", no
assertion that `ALL_EXECUTABLE_SPEC_NAMES` matches `spec_builders`,
no check that the labeler config covers every builder file, no check
that the four workflow matrices agree. Forgetting any single edit
produces a silent partial registration: the fork either generates
without a label, runs without coverage, or is skipped from one
workflow but not another.

For comparison: in `execution-specs`, adding a fork is one
`mkdir src/ethereum/forks/<fork>/` plus a recursive copy of the
predecessor. There is no central registry to update; the directory
name *is* the registration.

## Critique / inventory

### Scattered constants — three registries, no single source of truth

The fork tree is stored three times: once in `pysetup/constants.py`
as a bare-string identifier list, once in `pysetup/md_doc_paths.py`'s
`PREVIOUS_FORK_OF` as a parent map, and once in
`pysetup/spec_builders/__init__.py` as an unordered tuple keyed by
`builder.fork`. None of these is derived from any other; all three
must be edited and kept consistent. The `Makefile`'s
`ALL_EXECUTABLE_SPEC_NAMES` is a fourth registry, the CI workflows are
a fifth and sixth, and `.github/labeler.yml` is a seventh. The
**single source of truth** principle (Hunt & Thomas,
*The Pragmatic Programmer*, Tip 11 — DRY) is not just violated but
inverted: the same list is hand-maintained in seven places, three of
them in different formats (Python identifier, YAML matrix entry, Make
shell list).

### Copy-paste builders — the `NoopExecutionEngine` family

Every fork that touches the `ExecutionEngine` interface re-defines
`NoopExecutionEngine` from scratch as a string template inside
`execution_engine_cls()`. The pattern appears in:

- `bellatrix.py:31–57` — five methods.
- `deneb.py:45–78` — six methods (adds `is_valid_versioned_hashes`
  and a `parent_beacon_block_root` parameter).
- `electra.py:39–74` — six methods (adds
  `execution_requests_list` parameter).
- `heze.py:23–67` — eight methods (adds inclusion-list pair).
- `eip8025.py:15–50` — six methods, plus a sibling
  `NoopProofEngine` class, lines 53–76.

Each successive fork copies the prior fork's class verbatim and adds
one or two methods or one parameter. Common methods like
`get_payload`, `notify_forkchoice_updated`, and the
`return True` no-op pattern are present in every copy in identical
form, only the signature drifts. This is **Duplicated Code** (Fowler,
*Refactoring*, p. 76) at the most literal level — the duplication is
not even structurally disguised; the strings are textually similar
enough that diffing two builders shows the actual EIP delta as a
handful of lines surrounded by re-asserted boilerplate.

The duplication is hard to deduplicate *because* it lives inside a
triple-quoted string template. The builder doesn't return Python
objects that can be combined or inherited; it returns *Python source
code as text*, generated and concatenated by `helpers.objects_to_spec`
(see [ad-hoc-caching.md](ad-hoc-caching.md) for the parallel cost of
this representation choice in `phase0.py:47–104`'s `cache_this`
template). String concatenation cannot inherit. So every fork that
reshapes the engine signature must re-emit the entire class.

### Speculative-Generality hooks in `BaseSpecBuilder`

`pysetup/spec_builders/base.py` declares twelve hook methods:
`fork`, `imports`, `classes`, `preparations`, `sundry_functions`,
`execution_engine_cls`, `hardcoded_ssz_dep_constants`,
`hardcoded_func_dep_presets`, `implement_optimizations`,
`deprecate_constants`, `deprecate_presets`, `deprecate_containers`,
`deprecate_functions`. Most are no-op defaults. A grep across the ten
concrete builders shows:

- `implement_optimizations` is overridden by **only one** builder
  (`altair.py:47–51`).
- `hardcoded_func_dep_presets` is overridden by two (deneb, fulu).
- `hardcoded_ssz_dep_constants` by four.
- `deprecate_constants` by zero.
- `deprecate_presets` by one (gloas).
- `classes` by three; `preparations` by three; `sundry_functions` by
  five; `execution_engine_cls` by five.

This is **Speculative Generality** (Fowler, *Refactoring*, p. 83) —
hooks added "in case a future fork needs them", most of which never
fire. The cost is twofold: every reader of `BaseSpecBuilder` must
mentally simulate twelve possible extension points to decide which
ones are real, and every concrete builder is implicitly a partial
implementation of an interface that nobody fully implements. The
**Interface Segregation Principle** (Martin, *Clean Architecture*) is
violated by accretion: clients depend on twelve methods to receive
value from two.

The hooks are also duck-typed contracts — a misspelt override silently
becomes a new method rather than overriding the base. There is no
`@override` decorator in the codebase; nothing fails if a maintainer
writes `def hardcoded_ssz_dep_constant(cls)` (singular) by mistake.

### Implicit fork genealogy with no validation

`PREVIOUS_FORK_OF` (`md_doc_paths.py:16–27`) is a flat dict of strings
to strings. It is the *only* source of fork ordering, and it is used
recursively by `is_post_fork` (`md_doc_paths.py:41–54`) and by
`collect_prev_forks` (`helpers.py:16–22`). Both of these walk the
chain by repeated dict lookup — no fixed-point check, no cycle guard,
no validation that every name in the dict has a corresponding
builder, and no validation that `EIP8025`'s parent (`FULU`) is itself
in the dict. The recursion in `is_post_fork` is unbounded; a typo
that introduces a cycle would produce infinite recursion or a stack
overflow at runtime, not a clear startup error.

The `EIP8025: FULU` entry on line 26 is the more interesting one:
it documents that the fork tree is no longer linear. EIP forks
branch from a non-tip node. None of the iteration code anticipates
branching: `collect_prev_forks` returns a list, and `objects_to_spec`
reverses it to fold builders left-to-right. There is no notion of
"sibling fork" or "fork range"; the architecture assumes a totally
ordered chain even though the data structure is a tree.

### `.gitignore` enumeration

`.gitignore:18–27` enumerates ten generated fork output directories
under `tests/core/pyspec/eth_consensus_specs/`. The
`eip*` glob on line 27 hints at the recurrence — the maintainer who
added EIP forks gave up enumerating individually and switched to a
glob halfway through. This is a fork-registration symptom of the
self-referential package layout; see
[self-referential-package-layout.md](self-referential-package-layout.md)
for why generated output lands inside the package source in the first
place. As long as it does, every new fork adds another `.gitignore`
line; once the package moves out of `tests/`, the entire block
collapses to a single ignore on the build directory.

### The `objects_to_spec` Template Method anti-pattern

`pysetup/helpers.py:47–258` is one 211-line function that drives the
whole code-generation pipeline. It calls eleven of the twelve builder
hooks via `reduce(..., builders, initial)` folds (lines 86–94, 96–98,
164–172, 174–189, 192–206). Each hook contributes a string fragment;
`objects_to_spec` concatenates them in a fixed order (`spec_strs`,
lines 232–257) and returns the result. The function is, in effect,
the **template method** (Gamma et al., *Design Patterns*, 1994) — but
upside down: instead of the algorithm calling overridable steps on
`self`, it iterates a list of foreign builder objects and accumulates
their text outputs. The control flow is in the helper; the
extension points are the hooks; the result is a function so long
that the maintainer must scroll multiple screens to verify a single
fork's contribution. The **Single Responsibility Principle**
(Martin) is violated: this function chooses fork order, applies
optimizations, deletes deprecated symbols, formats config, formats
constants, generates assertions, and stitches the file together.

The Template Method pattern in its proper form (a base class with
overridable steps) does not actually require this shape — it requires
that the base class know the algorithm. Here the algorithm lives in a
free function, and the "base" only declares slots for the steps. That
is closer to a **Visitor without a class hierarchy**, or simply
**procedural code with extension hooks** — neither is the canonical
Template Method.

## Named anti-patterns

This finding is a stack of seven reinforcing smells. They appear in
the literature under these names:

1. **Shotgun Surgery** (Fowler, *Refactoring*, 1999, p. 79) — one
   conceptual change fans out to many files. Adding `foobar` touches
   ≥11 files at ≥15 loci.
2. **Duplicated Code** (Fowler, *Refactoring*, p. 76) — five
   `NoopExecutionEngine` copies, four overlapping fork-name registries.
3. **Speculative Generality** (Fowler, *Refactoring*, p. 83) — twelve
   `BaseSpecBuilder` hooks, half of them used by ≤2 forks.
4. **Switch Statements** (Fowler, *Refactoring*, p. 82) — the implicit
   "switch on fork name" via repeated `if fork == "altair"` style
   recursion in `is_post_fork`. Polymorphism via builder classes is
   present *but does not cover the genealogy*; the genealogy is still
   a switch in disguise.
5. **OCP violation** (Meyer, *Object-Oriented Software Construction*;
   Martin, *Clean Architecture*) — the system is not open for
   extension. Adding a fork modifies eleven files. A system obeying
   OCP would let the new builder file be the only edit.
6. **DRY violation** (Hunt & Thomas, *The Pragmatic Programmer*,
   Tip 11) — fork-name list maintained in seven places.
7. **Configure-don't-integrate violation** (Hunt & Thomas, Tip 38) —
   each new fork is integrated, not configured. There is no fork
   manifest from which the registries could be derived; instead, the
   registries are individually hand-edited.

The umbrella label is **"fork registration as a manual ritual"**:
adding a fork is not a code change followed by a config flip, it is a
twelve-step checklist that lives in tribal memory and the diffs of
prior fork additions.

## Comparable contrast

**execution-specs.** Adding a fork is one of two operations:
`mkdir src/ethereum/forks/<new_fork>/` and copy the predecessor
directory's contents (per the project's own architecture note in
`execution-specs/CLAUDE.md`: "Each fork under `src/ethereum/forks/` is
a complete copy of its predecessor (WET principle). Do NOT abstract
across forks."). The fork registry at
`packages/testing/src/execution_testing/forks/forks/__init__.py` is a
one-line module (`"""Listings of all forks, current and upcoming."""`)
that re-exports from sibling files in the same directory; the
registry is the directory listing. There is no
`PREVIOUS_FORK_OF`-style central genealogy dict, no shared builder
hierarchy, no spec_builders subpackage, no per-fork CI matrix
enumeration, no per-fork `.gitignore`. The WET-fork pattern looks
like duplication on paper but concentrates the duplication in *one
location* (the new fork's directory) and removes the cross-cutting
edits everywhere else. The fork registration is **co-located** with
the fork content, not scattered.

**leanSpec.** A single fork (`lstar`) lives at
`src/lean_spec/forks/lstar/`. The registry at
`src/lean_spec/forks/registry.py` is a runtime `ForkRegistry` class
that takes a list of fork-protocol implementations and validates
their `VERSION` is monotonic and `NAME` is unique. The
`src/lean_spec/forks/__init__.py` exposes
`FORK_SEQUENCE: list[ForkProtocol] = [LstarSpec()]`. Adding a fork is
one `import` and one list append in one file. No shotgun. The
genealogy is enforced (the registry checks ordering and uniqueness at
construction time); the consensus-specs `PREVIOUS_FORK_OF` dict is
checked nowhere. The architectural shape this is being generalised
into — a `ForkProtocol` ABC, concrete per-fork classes inheriting
incrementally, and capability `Protocol`s (`PQCapable`,
`ForkChoiceCapable`, `NetworkCapable`) for sub-spec conformance — is
documented in [*Proposal: Multi-Fork Architecture for
leanSpec*](https://hackmd.io/1iYMp6k_RXu0g9vGloV2ag) and is the
reference design for the fix sketch below. The same proposal is the
reference for [helper-layer.md](helper-layer.md)'s fix; the two
deep-dives converge on the same end state.

In both comparables, the fork tree is a first-class data structure
with a single canonical home. In consensus-specs, it is reconstructed
ad-hoc in seven different files in three different formats.

## Why this is load-bearing

This finding is the largest single source of "why is adding a fork
so painful?" friction reported by maintainers, and it is the largest
single barrier to anyone outside the core team contributing a new
fork or EIP variant. The damage spreads four ways:

- **Onboarding cost.** A new contributor wishing to add an EIP fork
  must discover the eleven edit sites by reading prior fork-addition
  PRs. There is no documented checklist; the canonical "how to add a
  fork" knowledge is the diff of the most recent fork-addition PR.
- **Silent partial registrations.** Forget the `Makefile` line and
  coverage silently drops the fork. Forget the labeler entry and PR
  triage breaks for that fork. Forget the `comptests.yml` schedule
  list and the fork is excluded from nightly test generation. None of
  these fail loudly.
- **Refactoring tax on the spec_builders subpackage.** Every change
  to the `BaseSpecBuilder` interface — adding a hook, renaming one,
  changing a return type — must be reconciled with ten subclasses,
  five of which contain triple-quoted string templates that hide the
  call sites from static tools. Renaming `execution_engine_cls` is a
  ten-place edit.
- **Implicit coupling to fork order.** `objects_to_spec` reduces
  builder outputs left-to-right via `collect_prev_forks(fork)[::-1]`.
  This bakes in the assumption that forks form a totally ordered
  chain. The `EIP8025: FULU` branch makes the data structure a tree,
  but the consumer code still treats it as a chain. Future EIP-style
  side-forks will accumulate latent bugs in the fold order until
  someone notices that an EIP fork branched from `FULU` re-emits
  `gloas` and `heze` deprecations or skips them inconsistently.

Several of the audit findings collapse once fork registration
is centralized: the `.gitignore` shotgun (§9), the speculative-
generality hooks (§6), the duplicated `NoopExecutionEngine` (§6), the
implicit fork genealogy (§6), and the partial-registration silent-
failure modes (§6). The Template Method anti-pattern in
`objects_to_spec` survives a centralization fix only partially — the
function would still be 200 lines, but each call site would dispatch
through a single registry rather than concatenating eleven hand-rolled
folds.

## What fixing it would entail

The same leanSpec proposal that addresses the helper-layer's
fork-conditional cascades —
[*Proposal: Multi-Fork Architecture for
leanSpec*](https://hackmd.io/1iYMp6k_RXu0g9vGloV2ag), detailed in
[helper-layer.md](helper-layer.md)'s fix sketch — also addresses
fork registration. The same three-layer design (`ForkProtocol`
ABC, concrete fork classes inheriting incrementally, capability
`Protocol`s for sub-spec conformance) collapses **five of the
seven registrations** the audit catalogues into one class
hierarchy plus one `forks/registry.py` import. The remaining two
(CI matrices, `Makefile` / `labeler.yml` configuration) become a
thin exporter that reads the registry rather than a hand-
maintained list.

The same fork class serves both the *runtime* role (the polymorphic
spec object that helpers and tests dispatch on) and the
*registration* role (the entry in `FORK_SEQUENCE`). One class
identity, one source of truth.

### How each finding maps onto the design

1. **§3.1 Scattered constants → one class hierarchy plus one
   registry import.** The four *internal* registries
   (`pysetup/constants.py`, `pysetup/md_doc_paths.py`'s
   `PREVIOUS_FORK_OF`, `pysetup/spec_builders/__init__.py`, the
   `spec_builders/` directory itself) collapse into the
   `forks/<name>/spec.py` class hierarchy plus
   `forks/registry.py`'s `FORK_SEQUENCE`. The DRY violation
   inverts: from "the same list in seven places" to "the list
   *is* the class hierarchy".

2. **§3.2 Copy-paste `NoopExecutionEngine` → method
   inheritance.** `NoopExecutionEngine` is a method (or a class
   field) on the fork that first introduced it; later forks
   inherit it unchanged. The five textual copies disappear
   because Python's MRO already provides "fold previous fork's
   behaviour into this fork's behaviour" — there is nothing to
   copy. The proposal's `Devnet1._check_attestation_signatures`
   example is the canonical shape: only the changed method is
   overridden, the rest is inherited.

3. **§3.3 12-hook `BaseSpecBuilder` Speculative Generality →
   minimal `ForkProtocol` plus opt-in capability Protocols.**
   The hooks that "most builders never use" don't exist on
   `ForkProtocol`; the genuinely-varying ones get factored into
   capability Protocols (`PQCapable`, `ForkChoiceCapable`,
   `NetworkCapable`). A fork has a capability or it doesn't —
   no "implements 12 methods, two of them meaningfully" pattern.
   ISP is satisfied. Misspelt overrides are caught by mypy /
   pyright (with `@override` available in Python 3.12+) rather
   than silently becoming new methods.

4. **§3.4 Implicit fork genealogy → class hierarchy.**
   `PREVIOUS_FORK_OF: dict[str, str]` becomes
   `class Devnet1(Devnet0):`; the genealogy is enforced by Python
   at class-definition time. Cycles are structurally impossible
   (Python won't compile a circular base class). Branching is
   first-class: `RainbowExperiment(Devnet0)` is a sibling of
   `Devnet1(Devnet0)`, both with their own MRO that doesn't
   include the other's changes — the `EIP8025: FULU` branching
   case the audit flags becomes the natural shape, not a special
   case.

5. **§3.5 `.gitignore` enumeration → indirect.** The package-
   source move that
   [directory-structure.md](directory-structure.md) and
   [self-referential-package-layout.md](self-referential-package-layout.md)
   recommend lands the spec sources at
   `src/eth_consensus_specs/forks/<fork>/`; once the build target
   is outside the test tree, there's nothing per-fork to ignore.
   The proposal's directory layout already assumes this shape.

6. **§3.6 `objects_to_spec` Template Method anti-pattern →
   class polymorphism.** The 211-line god function and its
   eleven `reduce(..., builders, initial)` folds disappear.
   Classes already provide the "compose previous fork's behaviour
   with this fork's overrides" semantics that `objects_to_spec`
   is hand-rolling with string concatenation. There's no
   concatenation because Python classes are the spec.

7. **§3.7 Implicit total-ordering coupling → MRO graph.**
   `collect_prev_forks(fork)[::-1]` is replaced by Python's MRO.
   Branching forks have their own MRO that doesn't include their
   siblings' deprecations or extensions; the architecture stops
   assuming a totally ordered chain.

### The residual layer: a thin CI / build-config exporter

Three of the audit's seven registrations are outside the
spec/test code:

- The four CI workflow matrices (`checks.yml`, `tests.yml`,
  `release.yml`, `comptests.yml`).
- `Makefile`'s `ALL_EXECUTABLE_SPEC_NAMES` variable.
- `.github/labeler.yml`'s per-fork blocks.

The proposal makes these **derivable** but does not itself
populate them. The fix is a thin exporter — a small script (or a
build step) that reads `FORK_SEQUENCE` and emits the JSON that
GitHub Actions matrices expect, the Make-list that `make`
consumes, and the YAML the labeler reads. This is the *single
fork manifest* that the prior fix-sketch step 1 named — but its
*source* is now the class hierarchy, not a separate YAML file.
Hunt & Thomas Tip 38 ("Configure, don't integrate") still
applies; the configuration is the code.

The startup-time validator the prior step 5 asked for — "every
name has a builder and a label entry, no cycles, every workflow
matrix matches the manifest" — is built into the registry: the
`ForkRegistry` constructor already validates uniqueness and
ordering, and the exporter step is what asserts the CI files
agree.

### Pytest integration

The same pytest plugin that absorbs the decorator stack
([decorator-stack.md](decorator-stack.md)) is the right home
for fork-aware test selection:

- `@pytest.mark.fork(<name>)` marker derived from `FORK_SEQUENCE`
  at plugin-startup time. No hard-coded fork-name list in the
  marker declaration; the registry is the source.
- Fork-range markers (the `with_altair_and_later`-equivalent)
  evaluate against the class hierarchy: `Altair in
  type(active_fork).__mro__` is the predicate; no string
  comparison, no `is_post_<fork>` chain.
- A `pytest_collection_modifyitems` hook filters by
  `-m "fork(electra)"` at the CLI; CI workflows stop listing
  fork names individually because the registry tells pytest
  what exists.

### Effort and sequencing

This is intertwined with [helper-layer.md](helper-layer.md) —
both deep-dives propose the same `ForkProtocol` + concrete-fork-
class shape because the same shape solves the same problem at
two layers (build-time fork registration here, run-time helper
dispatch there). The proposal's phased migration applies
directly:

1. **Phase 1 (mechanical, non-disruptive).** Wrap each existing
   `pysetup/spec_builders/<fork>.py` as a concrete fork class
   implementing `ForkProtocol`; register them in
   `forks/registry.py`. All existing tests pass; no behaviour
   changes.
2. **Phases 2–3 (incremental).** Replace string-template builder
   bodies with class-method overrides as each fork is touched;
   extract capability Protocols when sub-spec features mature.
   Each fork migrates independently.
3. **Phase 4 (clean-up).** Remove `pysetup/spec_builders/`,
   `PREVIOUS_FORK_OF`, and `pysetup/constants.py`'s fork list
   once nothing references them. Add the manifest exporter for
   CI / Makefile / labeler. The `.gitignore` block has already
   evaporated by this point if the package-source move from
   [directory-structure.md](directory-structure.md) has happened.

Phase 1 alone collapses none of the audit's findings; it makes
every subsequent phase mechanical. The proposal is explicit that
Phase 1 is non-disruptive — no test changes, no behaviour
changes, just a structural wrap of what already exists.

## References

- Fowler, M. *Refactoring: Improving the Design of Existing Code*
  (1999) — Shotgun Surgery (p. 79), Duplicated Code (p. 76),
  Speculative Generality (p. 83), Switch Statements (p. 82).
- Gamma, E. et al. *Design Patterns: Elements of Reusable
  Object-Oriented Software* (1994) — Template Method, Builder,
  Factory.
- Martin, R. *Clean Code* / *Clean Architecture* — OCP, ISP, DIP,
  SRP.
- Hunt, A. & Thomas, D. *The Pragmatic Programmer* — Tip 11 (DRY),
  Tip 17 (Eliminate effects between unrelated things), Tip 38
  (Configure, don't integrate).
- Meyer, B. *Object-Oriented Software Construction* (1988/1997) —
  the Open/Closed Principle in its original formulation.
