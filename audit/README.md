# consensus-specs — tech debt guide

## Goal

Make the repository easier and better to use for the people who write
specs and tests.

A test author should be able to add a test as a single file in a
flat tree, not navigate nine path components and a five-decorator
stack. A maintainer adding a new fork should edit one place, not
eleven. The build system should have one declarative entry point,
not five overlapping ad-hoc orchestrators.

The codebase has accumulated tooling debt at the layers most relevant
to those goals. This guide enumerates the issues, links to in-depth
analysis for each, and lists the engineering principles to apply when
addressing them. Each topic has its own deep-dive at
`deep-dives/<topic>.md`. Less-substantive findings are listed in
[`secondary-findings.md`](secondary-findings.md).

## Principles

These principles are applied throughout the recommended fixes. They
are not new; they are the standard names for what the comparable
projects (`execution-specs`, `leanSpec`) already do well, and what
this codebase will do well after the refactors.

- **Single Responsibility (SRP).** Each module, class, and function
  does one thing. The 996-line `light_client_data_collection.py` and
  the 332-line `Makefile`'s 15-variable `test:` recipe are the same
  smell at different scales: too much in one place.
- **Open/Closed (OCP).** Extend by adding new code, not by editing
  existing code. The seven `is_post_<fork>(spec)` predicates and the
  N-place fork registration footprint both fail this — every new
  fork means edits to existing helpers and config files.
- **Dependency Inversion (DIP).** Depend on interfaces, not on
  concrete implementations. Test code should not know that the
  package being tested lives at a specific filesystem path; pytest
  should not have to know that one of two import names is "the real
  one". Module-level globals depended on by import order are the
  worst form of this.
- **DRY** (Hunt & Thomas, *The Pragmatic Programmer*, Tip 11). Every
  piece of knowledge has one canonical home. The fork list lives in
  eleven places; KZG trusted-setup loaders live in three; LRU(10)
  state-prep wrappers live in three near-identical copies. Each is
  Shotgun Surgery (Fowler) for any cross-cutting change.
- **Eliminate effects between unrelated things** (Tip 17). No global
  mutable state hidden behind import-order side effects, no
  autouse fixtures patching module-level variables that other tests
  depend on. The `is_pytest`/`is_generator` flags and the
  `DEFAULT_TEST_PRESET` global are the canonical examples.
- **Configure, don't integrate** (Tip 38). Declarative config with
  schema validation, not procedural recipes. `Justfile` or `tox.ini`
  is declarative; the current `Makefile` is procedural.
- **Author specs as code (with caveats).** Both alternative repos
  author the spec in `.py` files; this codebase authors specs as
  Python embedded in markdown, with `pysetup/` extracting at build
  time. The markdown-as-source choice has real readability
  advantages and the team has made it deliberately — but most
  tooling failure modes (static-analysis blind spots, the gitignored
  generated runtime, the helper-layer's `is_post_<fork>` chains)
  trace back to that decision. The deep-dive lays out both sides.
- **Lean on pytest.** pytest fixtures, markers, and plugins replace
  most of the ad-hoc test machinery. The seven-decorator stack, the
  three hand-rolled LRU caches, the `template_test` frame-inspection
  registration, and the dual-mode `is_pytest`/`is_generator` flags
  all collapse into framework-standard mechanisms when expressed as
  a proper plugin.
- **Strict typing is a force multiplier.** A toothed mypy/ruff config
  catches the helper layer's primitive obsession, the dual-mode
  flags, and most of the `Stringly Typed` smells without anyone
  doing manual review. The current `ignore_missing_imports = true`
  defeats most of the typing surface.

These map cleanly onto Fowler's *Refactoring* smell catalogue, Martin's
*Clean Code* / *Clean Architecture*, Gamma et al.'s *Design Patterns*,
Hunt & Thomas's *The Pragmatic Programmer*, Beck's *Test-Driven
Development* (FIRST tests), Feathers's *Working Effectively with
Legacy Code* (test seams), and Meyer's *Object-Oriented Software
Construction* (Open/Closed). Each deep-dive cites the relevant page
or chapter where it applies.

## How to read this guide

The thirteen topics below are the high-impact items. Twelve are
grouped into four themes of code-level tech debt; build
orchestration is treated separately because it's about tooling
evolution rather than code-level smells. Each topic has its own
deep-dive at `deep-dives/<topic>.md` covering the shape of the
problem, line-cited evidence, named anti-patterns, contrast with
how the comparable repos handle the concern, scope of impact, and
a fix sketch (with explicit pytest-plugin angles where relevant).

The themes are ordered by *foundational dependence*: items in earlier
themes are upstream of items in later ones. Within a theme, items are
ordered by friction-per-day on the team. Specific fix-orderings are
left to the team — several of these refactors are intertwined and the
right sequencing depends on which constraints the team prioritises
first.

Lesser items (per-fork test-file naming inconsistencies, the empty
`__init__.py` files across the tree, the missing `CONTRIBUTING.md`,
etc.) are catalogued in [`secondary-findings.md`](secondary-findings.md).
Those findings came from a more automated process than the
deep-dives: multi-agent sweeps over the codebase produced the
raw findings, manual deduplication trimmed overlaps, and a quick
human review pass refined wording and caught the most obvious
errors. They are *not* purely automated output — but the human
curation was lighter than the line-by-line authoring that went
into the deep-dives, which were hand-written end-to-end.
Confidence in any individual secondary entry is roughly **95%**:
the named file path, the named anti-pattern, and the cited line
are trustworthy enough to act on, but spot-checking before a fix
lands is recommended; if a finding looks wrong, it probably is,
and should be raised rather than implemented.

Unfamiliar with the engineering vocabulary the deep-dives lean on —
*Shotgun Surgery*, *load-bearing*, *Inappropriate Intimacy*,
*tautological oracle*, `importmode`, PEP 735, and the rest? See
[`glossary.md`](glossary.md) for plain-English definitions of every
term used.

---

## Theme 1: Foundational structure

These four are the base. They touch every other concern in the
codebase. Several of the topics in later themes either dissolve or
become much easier once these are addressed.

### Self-referential package layout

`setup.py` declares an `eth_consensus_specs` Python package whose
source path is `tests/core/pyspec/eth_consensus_specs/` — *inside*
the test tree. Combined with `pyproject.toml`'s `pythonpath = ["."]`,
the same files are reachable under two distinct dotted names, which
Python caches as two separate module objects with two independent
copies of every module-level global. The dual-mutation conftest
workaround, broken `pip install .`, per-fork `.gitignore`
enumeration, and `VERSION.txt` bootstrapping fragility are all
downstream of this one structural decision.

→ [deep-dives/self-referential-package-layout.md](deep-dives/self-referential-package-layout.md)

### Package export boundary — five top-level names, no public API

Installing the wheel adds five top-level Python names to the
environment: `eth_consensus_specs`, `configs`, `presets`, `specs`,
`sync`. Four of them are generic and unnamespaced — any other PyPI
package can collide on `configs` or `specs`. The `eth_consensus_specs`
package itself ships the runtime spec, the entire test suite, the
~10 000-line helper layer, the SSZ debug toolkit, and miscellaneous
utilities under one roof, with an empty `__init__.py` (it only reads
`VERSION.txt`) and no `__all__`. There is no curated public API: a
downstream user importing `eth_consensus_specs` gets the kitchen
sink, can reach into private internals without warning, and cannot
tell which symbols are intended-for-them versus
intended-for-the-tests. Both comparable repos ship two distributions
(runtime + testing) with namespaced top-levels.

→ [deep-dives/package-export-boundary.md](deep-dives/package-export-boundary.md)

### Directory structure

The actual spec test files sit nine path components deep, in a tree
that mixes the package being tested, the test framework, the
test-vector format definitions, the test infrastructure tests, and
the per-fork test files. The comparable repos use a clean
three-directory model (`src/`, `packages/testing/`, `tests/`); this
guide proposes a four-bucket target (spec markdown, generated
runtime, framework, tests) with concrete depths halved or better.

→ [deep-dives/directory-structure.md](deep-dives/directory-structure.md)

### Markdown as the source of truth

The canonical spec is authored as Python embedded in markdown
(`specs/<fork>/*.md`), not as Python in `.py` files. `pysetup/`
extracts the code at build time into gitignored `.py` files.
Listed last in this theme because it is the only Theme 1 item that
is *contested on its merits*, not just on its execution: the
markdown-as-source choice has genuine pedagogical and readability
advantages — readers and reviewers can read the spec as prose
interleaved with code, and the `.md` files render naturally on
GitHub and in the docs site. The cost is that default
static-analysis tools (Pyright, mypy, IDE jump-to-definition)
cannot see the spec — they see only what the build leaves
behind, when it has been run, in a location the project
ignores. The deep-dive frames the trade-off honestly: the readability
argument is real, but the tooling-blindness costs cascade into
several of the other topics in this guide, and there are
intermediate choices (e.g. authoring as `.py` and generating the
narrative `.md`) that capture most of the benefit at a fraction of
the cost.

→ [deep-dives/markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md)

---

## Theme 2: Daily friction for spec & test authors

These are the surfaces a test author hits every day. Fixing them is
the highest ergonomic return on engineering effort.

### Decorator stack on every spec test

Every routine spec test is wrapped by three to five stacked
decorators (`@with_phases`, `@spec_state_test`, `@with_state`,
`@with_meta_tags`, `@with_presets`, `@with_config_overrides`,
`@always_bls`). The order is load-bearing — get it wrong and BLS
state silently corrupts across tests; forget the outer `@spec_test`
and config overrides become a no-op without an error. Order rules
exist only as code comments. A proper pytest plugin
(markers + fixtures + a `pytest_collection_modifyitems` hook)
collapses the entire stack.

→ [deep-dives/decorator-stack.md](deep-dives/decorator-stack.md)

### The 10 000-line helper layer

`tests/core/pyspec/eth_consensus_specs/test/helpers/` is ~10 000
lines of god modules threaded with `is_post_<fork>(spec)` cascades.
Six files exceed 500 lines. Functions accept untyped `spec` and
`state` positionally; mix data-model definitions, mutation, and
assertion in one body; and impose a fork-addition cost that scales
with the helper-layer size. State-builders that *should* be pytest
fixtures are hand-rolled as decorators with module-global LRU
caches.

→ [deep-dives/helper-layer.md](deep-dives/helper-layer.md)

### Static-analysis config has no teeth

`pyproject.toml`'s `[tool.mypy]` block declares strict directives,
then on the next line sets `ignore_missing_imports = true`, which
silently disables most of them — every untyped third-party import
is a wildcard escape hatch. The ruff selection covers only five rule
families, with the `PLR09xx` complexity rules explicitly silenced.
Pytest markers are undeclared and unenforced. PEP 735 dependency
groups are absent; `[tool.uv]` is absent despite a committed
`uv.lock`. Fixing this is a force multiplier — most of the
helper-layer's primitive-obsession smells, several of the
decorator-stack's typing failures, and the dual-mode flag confusion
would be partly caught by a stricter config alone.

→ [deep-dives/static-analysis-config.md](deep-dives/static-analysis-config.md)

---

## Theme 3: Friction for the maintainer adding a fork

### N-place fork registration

Adding one new fork is not "edit one place" but rather "edit a dozen
places, plus write a new builder class that copy-pastes most of its
peers". The codebase models a fork as nine to twelve separate
registrations spread across `pysetup/`, the build system
(`Makefile`, `setup.py`), version control hygiene (`.gitignore`),
and CI configuration (four workflow files plus a labeler config).
None of these registrations is derived from any of the others. A
single fork manifest plus generated registries collapses the
footprint.

→ [deep-dives/fork-registration.md](deep-dives/fork-registration.md)

---

## Theme 4: Test infrastructure quality

These are smaller-surface issues but each affects an important part
of the test pipeline.

### Ad-hoc caching: eight separate mechanisms

The codebase has eight distinct caching mechanisms spread across the
test framework, the build tooling, and the executable spec itself.
Three are near-clone hand-rolled `LRU(size=10)` wrappers in different
files. The most consequential is mechanism #8: a runtime memoisation
layer baked into every fork's generated `minimal.py`/`mainnet.py`
from a Python string template, which means the spec a reader sees in
markdown is not the same code that runs at test time. Most of the
mechanisms collapse into pytest fixture scopes; one is structural
and tracks back to the markdown-as-source decision.

→ [deep-dives/ad-hoc-caching.md](deep-dives/ad-hoc-caching.md)

### Compliance runners — constraint-solver test synthesis

`tests/generators/compliance_runners/` is one of the more interesting
pieces of test engineering in the project — the only place where
test cases are *synthesised by constraint solving* (MiniZinc) rather
than hand-authored. **Adding this style of test is a good idea and
the audit's recommended direction; the deep-dive critiques only the
integration with the rest of the test framework, not the technique.**
The integration smells are: three sources of truth (markdown format
spec, MiniZinc constraint models, Python instantiators), two
conftests with deliberately opposite BLS state, an import-order
side-effect protected by `# noqa: E402`, and Stringly-Typed mutation
dispatch. The directory structure (`compliance_runners/` plural,
`gen_base/` framework) commits to a generic pattern but only one
runner exists.

→ [deep-dives/compliance-runners.md](deep-dives/compliance-runners.md)

### SSZ generic vectors — the library is its own oracle

The published SSZ generic test vectors at
`tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_generic/` use
the SSZ library *as their own oracle for validity*. The `valid` test
asserts only round-trip equality (`deserialize(serialize(x)) == x`);
the `invalid` test publishes bytes as "invalid" iff the library
raises on them. Neither has an external definition of validity. The
published vectors form the inter-client SSZ conformance suite, so
library bugs propagate into the spec other clients implement
against. Plus a seven-decorator chain on every generated test,
frame-inspection-driven registration, and a `safe_lambda` runtime
check for a closure-capture bug a linter rule would catch.

→ [deep-dives/ssz-generic-vectors.md](deep-dives/ssz-generic-vectors.md)

### Vector formats — thirty-five READMEs, two underlying patterns

`tests/formats/` has forty markdown format-spec READMEs. Beneath the
naming differences, ~10 of them are parameterisations of one shape
(`pre.ssz_snappy + input + post.ssz_snappy` — the state-transition
family) and ~25 are parameterisations of another (`data.yaml { input,
output }` — the pure-function family). Only six or seven are
genuinely multi-step protocols (fork_choice, light_client/sync,
gossip_validation, fast_confirmation) that need their own format.
The fragmentation imposes a real cost: format evolution is a
many-place edit, runners across five-plus client implementations
must each parse their own README's edge cases, and new formats
arrive by copy-paste. A pair of typed Pydantic base classes
(`StateTransitionCase`, `PureFunctionCase`) replaces ~35 of the
markdown documents while preserving the on-disk vector layout
clients already consume.

→ [deep-dives/vector-formats.md](deep-dives/vector-formats.md)

---

## Build orchestration: an evolution sketch

Not strictly code-level tech debt — a question of tooling maturity
and how the team's build / CI infrastructure could evolve. Treated
in its own section because the *recommendation shape* is different
from the themes above: the deep-dive doesn't say "this is broken,
fix it"; it says "here are two tracks of evolution, pick the level
of ambition that fits".

### Build orchestration is procedural and fragmented

The project runs its developer pipelines through a 332-line
hand-written `Makefile` wrapping standalone Python scripts under
`scripts/`, the `pysetup` markdown extractor, and seven GitHub
Actions workflows. `uv` is the runtime underneath most Make
recipes; its version is pinned for CI via a `vars.UV_VERSION`
GitHub repo variable, but `pyproject.toml` has no `[tool.uv]`
section — no `required-version` for a contributor's local
install to be checked against, no workspace declaration, no
`[dependency-groups]` (PEP 735). The `setup-python` + `setup-uv`
bootstrap pair is repeated across five workflow files (kept in
SHA-sync by Dependabot/Renovate today); two entry points into
the spec generator coexist by design (the contributor path runs
`make _pyspec` which installs dev dependencies; the release path
skips that for a clean build). Adding a check, changing a tool, upgrading a dependency,
or wiring a new fork into CI touches some combination of
several layers with no shared convention for which layer owns
which concern. The deep-dive frames the fix as a two-track
choice: **Track A** tightens what already exists (no
orchestrator change); **Track B** replaces the Makefile with a
Justfile in the shape `execution-specs`
migrated to. Either is a legitimate stopping point.

→ [deep-dives/build-orchestration.md](deep-dives/build-orchestration.md)

---

## Cross-cutting concerns

Some weaknesses don't sit inside one theme; they show up in many
of the deep-dives at once and only become visible once the reader
assembles them. Three are catalogued below: **the absence of
typing**, **the absence of a common structure for the spec's
tests**, and **the absence of unit tests for the test-support
code itself**.

### The typing deficit

Strict typing is named in the principles above as a force
multiplier, but the typing critique itself is distributed across
five deep-dives and many secondary findings. The audit finds
typing-shaped failure modes:

- **In the config:**
  [static-analysis-config.md](deep-dives/static-analysis-config.md)
  — `ignore_missing_imports = true` poisons the four strict
  directives above it; the directives still fire, but on a typing
  surface that has been mostly redacted to `Any` upstream by
  every untyped third-party import. Plus a minimal ruff selection
  and absent stubs.

- **In the helper layer:**
  [helper-layer.md](deep-dives/helper-layer.md) — `SpecForkName =
  str`, the `(spec, state)` Data Clumps threaded through every
  helper, the empty two-attribute `Spec` Protocol with no
  behavioural contract, and untyped helper signatures end-to-end.
  Primitive Obsession at module scale.

- **In dispatch:**
  [compliance-runners.md](deep-dives/compliance-runners.md) and
  [decorator-stack.md](deep-dives/decorator-stack.md) — Stringly
  Typed mutation operators, behaviour-flag YAML keys, and the
  `(name, kind, value)` yield protocol whose discriminators are
  strings parsed by `isinstance` cascades.
  [secondary-findings.md](secondary-findings.md) catalogues
  several siblings (BLS-backend selection, runner-to-handler
  dispatch, fork ordering as `int`).

- **At the package boundary:**
  [package-export-boundary.md](deep-dives/package-export-boundary.md)
  — the wheel ships no `py.typed` marker, so a downstream consumer
  who installs `eth_consensus_specs` imports every symbol as
  `Any`. The outbound typing deficit mirrors the inbound one
  (third-party libraries lack `py.typed`; this library doesn't
  ship it either).

- **In the spec itself:**
  [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md)
  — even if the helpers were typed, the boundary into the spec is
  `Any` because the spec lives in `.md` files; static analysis
  cannot see the spec at all. The two issues compound: the
  helper-layer typing fix has limited reach until the spec is
  authored as code.

The fixes converge. The leanSpec proposal that anchors
[helper-layer.md](deep-dives/helper-layer.md) and
[fork-registration.md](deep-dives/fork-registration.md) is
fundamentally a typing fix: a `ForkProtocol` ABC, concrete fork
classes that inherit incrementally, capability `Protocol`s
(`PQCapable`, `ForkChoiceCapable`, `NetworkCapable`), and
Pydantic-modelled state. The config-track in
[static-analysis-config.md](deep-dives/static-analysis-config.md)
(drop `ignore_missing_imports`, add `stubs/`, ship `.pyi` files
for the half-dozen libraries that lack typing) is the counterpart.
Neither track delivers without the other — strict directives
without typed code produce phantom signal; typed code without a
strict checker is uneconomic to maintain.

### The absence of a common test structure

A spec test in `execution-specs` looks the same wherever you open
it: a docstring naming the EIP, a `REFERENCE_SPEC_GIT_PATH` and
`REFERENCE_SPEC_VERSION` (a git hash that detects spec drift), a
`pytestmark = [...]` list of declarative markers
(`pytest.mark.valid_from("Paris")`, `pytest.mark.parametrize(...)`,
`pytest.mark.ported_from(...)`), and a test function whose
parameters are typed framework fixtures —
`state_test: StateTestFiller`, `pre: Alloc`, `fork: Fork`. The
framework — imported as one name, `execution_testing` — provides
the *fillers*: typed objects that take the test's inputs and emit
the on-disk vector. The test author writes "given this
pre-allocation and this transaction, fill"; the filler does the
rest.

A spec test in `consensus-specs` looks however its author left it:

```python
from eth_consensus_specs.test.context import always_bls, spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import ALTAIR, BELLATRIX, CAPELLA, PHASE0
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import next_epoch_via_block
from eth_consensus_specs.test.helpers.voluntary_exits import sign_voluntary_exit

@with_phases([PHASE0, ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
def test_gossip_voluntary_exit__valid(spec, state):
    yield "topic", "meta", "voluntary_exit"
    seen = get_seen(spec)
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    yield "state", state
    ...
```

What is missing from this shape, compared to the
`execution-specs` filler:

- **No `REFERENCE_SPEC_GIT_PATH` / `REFERENCE_SPEC_VERSION`**.
  The test does not name which markdown spec it is testing, and
  there is no version pin to detect spec drift between when the
  test was written and now. A reviewer who wants to verify that
  the test still tests what the spec says has to find the spec
  by hand.
- **No declarative marker list.** Fork applicability is one
  decorator (`@with_phases([...])`); BLS / preset / config-
  override choice is the rest of the decorator stack
  ([decorator-stack.md](deep-dives/decorator-stack.md)). Markers
  are an order-sensitive imperative chain, not a `pytestmark`
  list pytest hooks can introspect.
- **No typed framework imports.** The five-line import block
  reaches into five different internal paths
  (`eth_consensus_specs.test.context`,
  `.test.helpers.constants`, `.test.helpers.gossip`,
  `.test.helpers.keys`, `.test.helpers.state`,
  `.test.helpers.voluntary_exits`). There is no public
  `consensus_testing` package corresponding to `execution_testing`.
- **No filler.** The test signature is `def
  test_…(spec, state):` — two untyped positional parameters
  threaded with `yield "name", "kind", value` tuples. The
  yield-protocol is the audit's recurring Stringly Typed smell
  ([decorator-stack.md](deep-dives/decorator-stack.md),
  [vector-formats.md](deep-dives/vector-formats.md)). The fork-
  versions of every helper get reached through the `spec` god
  object ([helper-layer.md](deep-dives/helper-layer.md)).
- **No common base for vector layout.** The 35+ markdown format
  documents in `tests/formats/`
  ([vector-formats.md](deep-dives/vector-formats.md)) are the
  symptom: each test category has its own README describing its
  on-disk shape because there is no typed `*Filler` base class
  the schemas could derive from.

Where the symptoms surface:

- [decorator-stack.md](deep-dives/decorator-stack.md) — the
  seven-decorator chain is what a filler-plus-markers would
  collapse into.
- [vector-formats.md](deep-dives/vector-formats.md) — the 35-
  README format proliferation is what `StateTestFiller` /
  `BlockchainTestFiller` (one Pydantic class per test family)
  would replace.
- [helper-layer.md](deep-dives/helper-layer.md) — the 10 000-line
  helper layer exists because tests can't call into a typed
  framework; they reach into helpers instead.
- [package-export-boundary.md](deep-dives/package-export-boundary.md)
  — the absence of a `consensus_testing` distribution mirrors
  the absence of an `execution_testing`-style public testing
  surface.
- [secondary-findings.md](secondary-findings.md) — many in-test
  anti-patterns (asserts without messages, loop-as-parametrize,
  hardcoded test data) are downstream of the missing framework.

The fix converges with the others. The pytest-plugin solution
sketched in [decorator-stack.md](deep-dives/decorator-stack.md)
is half of it — markers, fixtures, a single import from a
plugin-shaped package. The leanSpec proposal in
[helper-layer.md](deep-dives/helper-layer.md) is the typed
framework half — `ForkProtocol`-shaped fork classes that the
fillers compose with. The vector-format Pydantic schemas in
[vector-formats.md](deep-dives/vector-formats.md) are the
*output* shape the fillers emit. Once those three exist, a
consensus-specs test looks like an execution-specs test — same
preamble, same markers, same filler-plus-fixtures signature —
and the team's reviewer load on each new test drops to "is
this consistent with the rest?" rather than "what shape did
this author choose?".

### Unit tests for the test-support code

Most of the code that *supports* the spec tests has no unit
tests of its own. The numbers across the major test-support
trees:

| Tree | Modules | With sibling `test_*.py` |
|---|---:|---:|
| `tests/core/pyspec/.../test/helpers/` (legacy helper layer, 10 000+ LoC) | 43 | **0** |
| `pysetup/` (markdown-to-Python extractor, build prerequisite for *everything*) | 7 | **0** |
| `scripts/` (validation and generation scripts) | 6 | **0** |
| `tests/infra/` (the in-progress framework migration) | 12 | 6 |
| `tests/infra/helpers/` (the unit-tested helper migration) | 5 | 4 |

Two of the three largest trees have **no unit tests at all**.
The 43-module helper layer (the most-edited test-support code
in the project) has zero. `pysetup/` — the build-time markdown→
Python extractor that produces the executable spec every other
test imports — has zero. `scripts/` (six standalone validation
and generator tools) has zero. The only trees with unit-test
discipline are `tests/infra/` and its `helpers/` sub-tree,
which the project's own remediation effort has been adding
piecemeal.

The consequences are catalogued across the deep-dives:

- **No safety net for refactoring the helper layer.**
  [helper-layer.md](deep-dives/helper-layer.md) — refactoring
  10 000 lines of `is_post_<fork>` cascades, untyped `(spec,
  state)` helpers, and god-modules requires characterisation
  tests (Feathers, *Working Effectively with Legacy Code*,
  2004) before any behaviour-preserving change is safe. Today
  the only validation is the downstream spec-test suite,
  which runs *through* the helpers rather than *against* them
  — a regression in a helper that the spec tests happen not
  to exercise is invisible.

- **The build-time extractor has no characterisation tests.**
  [markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md)
  flags this explicitly: there is no `pysetup/test_md_to_spec.py`,
  even though `pysetup/md_to_spec.py` is the parser that
  produces the entire executable spec. The parser's only
  validation is "the downstream tests pass", which means a
  class of bugs (the parser silently produced wrong code that
  the spec tests happen not to exercise) is structurally
  invisible. This is the most consequential single
  unit-testing gap in the project.

- **The decorator stack and the yield protocol are untested
  framework code.** [decorator-stack.md](deep-dives/decorator-stack.md)
  — the eleven `with_*` decorators, the autouse fixtures
  rebinding module globals, the `(name, kind, value)`
  yield-collection machinery: none of it has direct unit
  tests. Behaviour is exercised end-to-end through actual
  spec tests, so a regression in (say) marker-ordering only
  fails when *some* spec test happens to depend on the order
  that broke.

- **The compliance-runner framework has no tests for its
  framework parts.** [compliance-runners.md](deep-dives/compliance-runners.md)
  — the `gen_base/` infrastructure, `mutation_operators.py`'s
  Stringly Typed dispatch, the YAML `test_gen.yaml` loader.

The direction of travel is right: `tests/infra/` is the
project's own pattern for "test-support module + sibling
unit tests", and PR 4440 (referenced in
[ad-hoc-caching.md](deep-dives/ad-hoc-caching.md)) shipped
1 895 lines of unit tests for a 247-line spec-cache module —
a healthy ratio. The remaining work is to apply the same
pattern to the legacy helpers (~43 modules), to `pysetup/`
(7 modules, starting with the markdown extractor), and to
`scripts/` (6 modules).

The fix composes with the others. The leanSpec proposal in
[helper-layer.md](deep-dives/helper-layer.md) makes the
helpers easier to test (typed fork classes have well-defined
signatures, no more `(spec, state)` god-clumps). The
markdown-to-Python authoring fix in
[markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md)
either makes `pysetup/` unnecessary (option a — author Python
directly) or makes its surface small enough to characterise
(option c — generate markdown from Python). And the typed
filler shape from "absence of common test structure" above
gives the framework code a stable surface for unit tests to
target. The unit-test gap doesn't dissolve on its own — the
team has to write the tests — but each of the other refactors
makes the writing easier.

---

## Suggested reading order

For someone new to the audit:

1. **Read this guide top to bottom.** It's the index.
2. **Pick a theme and read the deep-dives in that theme.** Each is
   self-contained; the cross-references between deep-dives connect
   topics that share a root cause.
3. **Read [`secondary-findings.md`](secondary-findings.md)** for the
   smaller items.

For a fix-roadmap conversation:

- Theme 1 is foundational; addressing those four unblocks several
  others. The self-referential package layout, the package export
  boundary, and the directory structure can all be tackled without
  taking a position on markdown-as-source-of-truth — and doing so
  resolves most of the structural friction even if the spec stays
  in markdown. Markdown-as-source is the more contested choice; the
  other three are not.
- Theme 2's static-analysis config is a near-pure win — small
  config changes, broad behavioural impact. Doing it before the
  helper-layer refactor catches issues during the refactor.
- The decorator-stack rework is the path to a proper pytest plugin
  layer; doing it makes the compliance-runners and SSZ-generic-vector
  refactors mechanically tractable.

The deep-dives' "What fixing it would entail" sections are sketches,
not designs. Each describes the shape of the work; the team owns the
sequencing and the trade-offs.
