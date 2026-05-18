# consensus-specs — decorator stack (deep-dive)

Every routine spec test in `consensus-specs` is wrapped by at least
three stacked decorators, and many use four or five. That short stack
hides a four-deep expansion in
`tests/core/pyspec/eth_consensus_specs/test/context.py`, with order
rules existing only as code comments. Get the order wrong and BLS
state silently corrupts across tests; forget the outer `@spec_test`
and config overrides become a no-op without an error. This is the
surface every test author touches every day.

Adjacent guides:
[ad-hoc-caching.md](ad-hoc-caching.md) (the LRU cache and
function-identity hash key inside `context.py` share its mutable-
global problem),
[directory-structure.md](directory-structure.md) (the package layout
that the `is_pytest`/`is_generator` flags compensate for).

## The shape of the problem

Every routine spec test in `consensus-specs` is decorated with at
least three stacked decorators, and many use four or five:

```python
@with_altair_and_later
@spec_state_test
def test_sync_committee_committee__full(spec, state):
    ...
```

That two-line stack hides a four-deep expansion. `@spec_state_test`
is `spec_test(with_state(single_phase(...)))`
(`context.py:351`); `@spec_test` is itself
`vector_test(bls_switch(...))` (`context.py:346`); `@with_state` is a
preconfigured call to `with_custom_state(default_balances,
default_activation_threshold)` (`context.py:217`); `@vector_test`
lives in `tests/infra/yield_generator.py` and orchestrates the
yield-driven test-vector emission. The user-facing test sees four
keyword arguments injected (`spec`, `state`, `phases` removed by
`single_phase`, `bls_active` consumed by `bls_switch`) and yields a
mix of `(name, kind, value)` tuples that the framework interprets
positionally. None of this is visible at the call site.

A senior reader scanning a file of `test_*.py` functions sees only
the outer wrappers (`@with_altair_and_later`, `@spec_state_test`,
sometimes `@always_bls`, `@with_presets(...)`,
`@with_config_overrides(...)`). To reason about what those wrappers
do — and crucially, in what order they must appear — the reader has
to open `context.py` and read past the prose comments at lines
342–345, 419–421, 433–436, 449–452, 766–767, and 794–798. Order
mistakes do not produce errors; they produce silent corruption (BLS
state leaks across tests; config overrides silently no-op; fork-meta
yields are dropped).

This matters for the project's stated purpose because consensus-specs
is a specification — it is read more than it is written, and its
tests are the canonical reference for client implementers. A test
author working on a new EIP must internalise five layers of decorator
machinery, two module-level globals (`DEFAULT_TEST_PRESET`,
`DEFAULT_PYTEST_FORKS`), two dual-mode flags (`is_pytest`,
`is_generator`), four autouse fixtures that mutate those globals, and
a string-keyed yield protocol — all before writing the first
assertion. Every one of those is a hidden dependency in Feathers'
sense (*Working Effectively with Legacy Code*, 2004) and a
test-seam-by-side-effect.

## Proof, by line

- `context.py:340–351` — `spec_test = vector_test ∘ bls_switch`;
  `spec_state_test = spec_test ∘ with_state ∘ single_phase`. The
  comment at 342–345 spells out an ordering rule ("Bls switch must
  be wrapped by vector_test … before setting back the BLS setting")
  that exists nowhere else and is not enforced by code.
- `context.py:217` — `with_state = with_custom_state(default_balances,
  default_activation_threshold)`. A module-level partial application
  hidden behind a name that looks like a fresh decorator.
- `context.py:74,83` — `_custom_state_cache_dict = LRU(size=10)`,
  keyed on `(spec.fork, spec.config.__hash__(), spec.__file__,
  balances_fn, threshold_fn)` — a tuple that includes the *identity*
  of the balances function (see
  [ad-hoc-caching.md](ad-hoc-caching.md)).
- `context.py:47–50` — `DEFAULT_TEST_PRESET = MINIMAL`,
  `DEFAULT_PYTEST_FORKS = ALL_PHASES`. Module-level mutable globals
  that the autouse fixtures reach into and rebind.
- `context.py:321–322, 327, 610, 647, 662, 840` — `is_pytest`/
  `is_generator` booleans branch the skip path
  (`pytest.skip` vs. `raise SkippedTest`), the dispatcher (collect
  `MultiPhaseResult` vs. discard), the fork-meta accumulator, and
  the `only_generator` gate. Two booleans, three execution modes,
  six branches.
- `context.py:416–443` — `@never_bls` and `@always_bls` each carry
  their own copy of the `bls_switch` body and an extra
  `@with_meta_tags({"bls_setting": ...})`. The comments at 419–421/
  433–436 say these "may only be applied to yielding spec test
  functions, and should be wrapped by vector_test" — enforced only
  by docstring.
- `context.py:446–462` — `bls_switch` mutates `bls.bls_active`
  before the call and restores it after. If the wrapped function
  raises before `yield from`, the restore is skipped. The
  order-comment at line 342 exists for this exact failure mode.
- `context.py:556–587` — `_get_run_phases` reads
  `DEFAULT_PYTEST_FORKS` directly (line 569). The fork list is not
  passed in; it is grabbed from module state set by the autouse
  fixture at `conftest.py:124–131`.
- `context.py:590–622` — `_run_test_case_with_phases` branches on
  `is_pytest and is_generator` (line 610). Pytest mode silently
  drops every phase's return except the last (lines 620–622).
- `context.py:625–678` — `with_phases` carries a four-way branch
  (`"phase" in kw`; `is_pytest and is_generator`; `is_pytest` only;
  default) on the `fork_metas` path. What this decorator *does*
  depends on which mode the module is in.
- `context.py:700–712` — eleven pre-applied phase decorators
  (`with_light_client`, `with_altair_and_later` …
  `with_eip8025_and_later`, `with_bellatrix_only`) materialised at
  import time. Adding a fork edits this file plus
  `helpers/constants.py` plus `helpers/forks.py` — Shotgun Surgery
  (Fowler, *Refactoring*, 1999, p. 79).
- `context.py:735–763` — `get_copy_of_spec` re-imports the per-fork
  preset module by literal-string path
  (`f"eth_consensus_specs.{fork}.{preset}"`), runs `exec_module`,
  and `module.config = deepcopy(spec.config)` — manually replicating
  pieces of Python's import machinery to give the inner test a copy.
  `spec_with_config_overrides` then rebuilds the `Configuration`
  namedtuple in place via `Configuration.__annotations__`.
- `context.py:765–798` — `with_config_overrides` (line 765) and
  `_with_config_overrides_emit` (line 794) both warn in prose that
  the `spec_test` decorator must wrap them. The latter notes that
  pytest "doesn't run generator tests, and instead silently passes
  it" — a known failure mode the codebase documents rather than
  detects.
- `context.py:837–847` — `only_generator` gates a test on the
  `is_generator`/`is_pytest` pair. In modern pytest this is a
  marker plus a `pytest_collection_modifyitems` hook; here it is a
  closure over module globals.
- `context.py:873–903` — `with_fork_metas` composes
  `set_fork_metas ∘ with_phases(ALL_PHASES) ∘ spec_test ∘ with_state ∘
  yield_fork_meta` in one nested call (line 901). Five decorators
  in one factory.
- `context.py:906–960` — `yield_fork_meta` yields stringly-typed
  meta tuples: `("post_fork", "meta", ...)`, `("fork_epoch",
  "meta", ...)`, `("fork_block", "meta", ...)`. The protocol is a
  `(name, kind, value)` triple where `kind` is a string
  discriminator. Stringly Typed (Fowler, *Refactoring*, 1999).
- `conftest.py:99–121` — autouse `preset(request)` rebinds
  `context.DEFAULT_TEST_PRESET` (line 113) and *also* the same
  attribute on a second module string-looked-up at line 118
  (`sys.modules.get("tests.core.pyspec.eth_consensus_specs.test.context")`).
  The comment at 114–117 still references `eth2spec` — a name the
  package no longer has.
- `conftest.py:104–112` — the "general" preset is a string compare
  that swaps `spec_preset = "minimal"` while keeping the callspec
  as `"general"`. A pytest skip at 105/108 substitutes for
  parametrize-level filtering.
- `conftest.py:123–146, 167–171` — autouse `run_phases` rebinds
  `DEFAULT_PYTEST_FORKS` (line 129/131; the reset is gated on
  `not context.is_generator`). Autouse `bls_type` calls one of four
  module-level setter functions
  (`bls_utils.use_py_ecc/milagro/arkworks/fastest()`). Session-
  autouse `kzg_type` reaches across `spec_targets.values()` to patch
  every spec module's KZG.
- `conftest.py:174` — `pytest_plugins = ["tests.infra.pytest_plugins.yield_generator"]`.
  The yield-driven vector-emission plugin is loaded from a
  `tests.`-prefixed path the conftest itself depends on resolving
  under both import paths.
- `tests/.../altair/sanity/test_blocks.py:52–53` — a representative
  test: `@with_altair_and_later` over `@spec_state_test` over a
  function yielding `("pre", state)`, `("blocks", [signed_block])`,
  `("post", state)` tuples. The author must know that
  `with_altair_and_later` must be outermost, that `spec_state_test`
  injects `state` and removes `phases`, and that the yields must
  come after `pre` mutation but before `post` mutation. None of
  this is checked.
- `utils/utils.py:4–26` — `with_meta_tags` uses a `yielded_any`
  flag to decide whether to append meta tuples; if the wrapped
  function raises before its first yield, the meta tags are
  silently dropped.

## Critique / inventory / detailed breakdown

### The decorator zoo

`context.py` exports, by my count, twenty-three test-author-facing
decorators in one 960-line module:

```
single_phase, spec_test, spec_state_test,
spec_configured_state_test, spec_state_test_with_matching_config,
with_matching_spec_config, never_bls, always_bls, bls_switch,
with_all_phases, with_all_phases_from, with_all_phases_from_except,
with_all_phases_from_to, with_all_phases_from_to_except,
with_all_phases_except, with_phases, with_presets,
with_config_overrides, with_state (= with_custom_state(...)),
with_custom_state, with_test_suite_name, only_generator,
with_fork_metas, set_fork_metas, yield_fork_meta, description,
with_meta_tags
```

Plus eleven precomputed phase decorators
(`with_light_client`, `with_altair_and_later` … `with_eip8025_and_later`,
`with_bellatrix_only`) created at module load time at lines 700–712.
This is Divergent Change (Fowler, *Refactoring*, 1999, p. 77) — a
single module changes for one reason and only one (test-runtime
configuration), but every test author has to understand all of it.
It is also Long Method at the module level: thirty-plus closures and
factories, all sharing four module-level mutable variables and two
dual-mode flags.

### The order-significance rules in comments

Six prose comments at `context.py:342–345`, `419–421`, `433–436`,
`449–452`, `766–767`, and `794–798` encode invariants with no other
enforcement: `bls_switch`/`@never_bls`/`@always_bls` must be wrapped
by `vector_test` (else BLS flag leaks across tests);
`with_config_overrides` and `_with_config_overrides_emit` must be
wrapped by `spec_test` (else the test silently passes without
applying overrides — pytest does not run generator functions absent
a consumer). This is *Inappropriate Comment* (Martin, *Clean Code*,
ch. 4) and Comments-as-Deodorant (Fowler, *Refactoring*, 1999,
p. 87) — prose used because the structure cannot express its own
constraints. A type-checker, marker, or single composed entry point
would catch all of these statically.

### The mutable global preset

`DEFAULT_TEST_PRESET` (`context.py:47`) and `DEFAULT_PYTEST_FORKS`
(`context.py:50`) are read by `_get_preset_targets` (line 550),
`_get_run_phases` (line 569), and the fork-transition branch of
`with_phases` (lines 652, 665); written by the autouse fixtures
`preset` (`conftest.py:113`) and `run_phases` (`conftest.py:129,
131`); written *twice* at `conftest.py:118–120` to patch the
dual-import-path shadow; and indirectly fed into the LRU cache key
via `spec.config.__hash__()` at `context.py:83`. Hunt & Thomas's
Tip 17 ("Eliminate effects between unrelated things") names this
exactly; Beck's "Isolated" criterion (*Test-Driven Development*,
2002) is violated. Tests share `bls.bls_active`,
`DEFAULT_TEST_PRESET`, `DEFAULT_PYTEST_FORKS`, the LRU cache, and
the spec module's mutated `.config`.

### Dual-mode flags as implicit semantics

`is_pytest`/`is_generator` carry meaning at six locations:
`context.py:327` (skip-or-raise), `:610` (collect MultiPhaseResult
vs. discard), `:647` (fork-meta accumulation), `:662` (no-op when
pytest-only-and-not-generator), `:840` (`only_generator` gate),
`conftest.py:130` (DEFAULT_PYTEST_FORKS reset gated). Two booleans
encoding three execution modes (test runner; vector generator;
vector generator under pytest) — Primitive Obsession with a control
flag (Fowler, *Refactoring*, 1999, p. 89). The same code path means
two different things depending on which module-level flag was set
by some other entry point: Strategy (Gamma et al., *Design Patterns*,
1994) inverted into branching inside one module.

### Autouse fixtures as a side-effect channel

Four `@fixture(autouse=True)` blocks at `conftest.py:99–146` and
one session-autouse at `:167–171` mutate `context.DEFAULT_TEST_PRESET`
plus its string-looked-up shadow (lines 113, 118–120), mutate
`context.DEFAULT_PYTEST_FORKS` (129, 131), set `bls_utils.bls_active`
via setter functions (137–144), and patch every spec module's KZG
across `spec_targets.values()` (149–164). Pytest's design intent —
explicit dependency injection (Beck, *Test-Driven Development*,
2002, "make dependencies obvious") — is inverted: the fixtures take
`request`, but their effect is on globals the test never names.

### Config override yields require an outer wrapper

`with_config_overrides` (line 765) and `_with_config_overrides_emit`
(line 794) both warn in prose that they require a `spec_test` outer
wrapper because they yield. Pytest, on encountering a bare generator
test with no consumer, reports it as passing. The codebase offers
`spec_configured_state_test` (line 354) as a safer named composite —
but `with_config_overrides` is still exported, and any user who
applies it without the matching outer wrapper gets a green test that
did nothing. *Speculative Generality* (Fowler, *Refactoring*, 1999,
p. 109): two ways to apply overrides, one of them silently broken,
with prose as the only safety rail.

### Fork-transition tests use stringly-typed yield metadata

`yield_fork_meta` (line 906) yields `("post_fork", "meta", ...)`,
`("fork_epoch", "meta", ...)`, `("fork_block", "meta", ...)`. The
first element names the field, the second is a literal `"meta"`
discriminator consumed by `tests/infra/yield_generator.py`, the
third is the value. Typo any constant and the field is dropped
without an error. There is no `Meta`/`Pre`/`Post`/`Block` value
class; everything moves through tuples of strings.
`utils/utils.py:13–24`'s `yielded_any` flag is a downstream
consequence: the framework cannot distinguish "test produced no
yields" from "test mode is non-yield" without that sentinel.

### Inappropriate Intimacy with the spec module object

`get_copy_of_spec` (line 735–746) re-imports the per-fork preset
module by literal-string path, runs `exec_module`, and assigns
`module.config = deepcopy(spec.config)` to preserve overrides — a
hand-rolled replay of Python's import machinery so
`with_config_overrides` can mutate `module.config` on the resulting
copy. Test infrastructure reaches into spec module internals to
rebind attributes — Inappropriate Intimacy (Fowler, *Refactoring*,
1999, p. 85).

## Named anti-patterns

- **Long Method / Long Module** (Fowler, *Refactoring*, 1999, p. 76)
  — `context.py` is 960 lines, all of it test-runtime configuration.
- **Comments-as-Deodorant** (Fowler, *Refactoring*, 1999, p. 87) —
  six order/wrapping invariants live in prose comments at
  `context.py:342–345, 419–421, 433–436, 449–452, 766–767, 794–798`.
- **Stringly Typed** (Fowler, *Refactoring*, 1999) — the `(name,
  kind, value)` yield protocol; `kind ∈ {"meta", "cfg", ...}`;
  `name ∈ {"pre", "post", "blocks", "post_fork", "fork_epoch",
  "fork_block", "config", ...}`. No types.
- **Primitive Obsession with a control flag** (Fowler,
  *Refactoring*, 1999, p. 89) — `is_pytest`/`is_generator` encode an
  enum-of-three as two booleans across seven branches.
- **Inappropriate Intimacy** (Fowler, *Refactoring*, 1999, p. 85) —
  `get_copy_of_spec` reaches into the spec module's internals to
  rebind `module.config`; autouse fixtures rebind module-level
  variables on `context`.
- **Shotgun Surgery** (Fowler, *Refactoring*, 1999, p. 79) — adding
  a fork touches `with_phases` constants (lines 700–712),
  `helpers/constants.py`, `helpers/forks.py`, the autouse fixtures,
  and the `with_fork_metas` chain.
- **Hidden Dependencies / Test Seam Misuse** (Feathers, *Working
  Effectively with Legacy Code*, 2004) — every test depends on
  `bls.bls_active`, `DEFAULT_TEST_PRESET`, `DEFAULT_PYTEST_FORKS`,
  the LRU cache, and the spec module's mutated `.config`, none of
  which are named in the test signature.
- **Decorator overuse** (Gamma et al., *Design Patterns*, 1994 — the
  pattern when properly applied is a single-axis behavioural
  extension; here it is misused as a Strategy / Template-Method
  selector with five axes stacked).
- **FIRST violation: not Isolated** (Beck, *Test-Driven Development*,
  2002) — tests share mutable globals via fixtures and decorators;
  the order of test execution affects the values those globals carry.
- **Inappropriate Comment** (Martin, *Clean Code*, ch. 4) — the
  `# eth2spec` comment at `conftest.py:114–117` references a name
  the package no longer has.

## Comparable contrast

`leanSpec` and `execution-specs` solve the same set of concerns —
"run a test under different forks", "produce a YAML/JSON test
vector", "skip on the wrong preset", "configure cryptography" — with
no decorator stack at all. The pattern in both repos is **fixture
classes injected by name**, augmented by **pytest markers**.

In `leanSpec/packages/testing/src/framework/pytest_plugins/filler.py`,
a test signature looks like
`def test_block(state_transition_test: StateTransitionTestFiller)`
(per `leanSpec/.claude/rules/test-framework.md`). The fixture is a
class; calling it produces a `FixtureWrapper`; the wrapper runs the
state transition, validates against `StateExpectation`, serializes
via Pydantic, and emits the JSON at session end. The framework
collects fixtures via the `FixtureCollector` class
(`filler.py:15–80`), keeps no module-level mutable state, and
discriminates fixture types by class rather than by string. Fork
selection is a marker (`@pytest.mark.valid_until`) declared at
`leanSpec/pyproject.toml:107–112`.

In `execution-specs/pyproject.toml:286–297`, the entire fork/feature
selection vocabulary is nine pytest markers — `slow`, `bigmem`,
`evm_tools`, `json_blockchain_tests`, `vm_test`, etc. The
filler-plugin path
(`execution-specs/packages/testing/src/execution_testing/cli/pytest_commands/plugins/filler/filler.py`)
uses fixtures for state setup and markers for selection. Fork
chaining ("from amsterdam onward") is handled by deselecting markers
on the CLI, not by stacking eleven decorator factories. The "WET
across forks" architecture (`execution-specs/CLAUDE.md`: "Each fork
under `src/ethereum/forks/` is a complete copy of its predecessor")
means each fork's test layer is concrete code, not parametrised
over a phase variable.

The contrast is not just stylistic. Markers integrate with pytest's
collection, reporting, and `-m` deselect machinery; decorator
factories do not. Fixtures are explicit dependencies named in the
test signature; module-level mutable state is not. Markers can be
declared once in `pyproject.toml` (the comparable repos do this in
8–11 lines total); consensus-specs has eleven fork wrappers built at
import time of `context.py`.

## Why this is load-bearing

Most of the §1 findings in the broader audit catalogue collapse into
this single one. Specifically:

- "Module-level mutable state (DEFAULT_TEST_PRESET, DEFAULT_PYTEST_FORKS)"
  exists *because* the autouse fixtures need a place to drop
  per-pytest-CLI configuration, and the decorators need a place to
  read it that is free of the explicit-parameter problem the
  architecture has chosen to avoid. Replace the decorator stack with
  pytest fixtures and these globals stop having a job.
- "Dual-mode context flags (is_pytest, is_generator)" exists because
  `context.py` is loaded both by pytest and by the generator script
  in `tests/generators/`, and the same `with_phases`/`vector_test`
  decorators need to behave differently in each mode. With explicit
  per-mode entry points (a pytest plugin and a generator CLI, as in
  the comparables), the flags disappear.
- "Decorator ordering is load-bearing but undocumented in code"
  exists because BLS state, config overrides, and yield collection
  share a single composition path with no checks. A typed
  fixture-and-marker model has no ordering to forget.
- "Autouse fixtures as a side-effect channel" exists because the
  decorators read globals and the fixtures are the only place to
  seed those globals. Cut the decorators' dependency on globals and
  the fixtures stop being side-effect channels.
- "Config override yields require an outer wrapper" exists because
  `_with_config_overrides_emit` is a generator and pytest silently
  passes generator tests with no consumer. With overrides expressed
  as a fixture parameter or a marker, no generator dance is needed.
- "Fork-transition tests use stringly-typed yield metadata" exists
  because `with_fork_metas` has chosen the same `(name, kind,
  value)` protocol the rest of the framework uses. Replace the
  protocol with a typed result object and the strings disappear.

This deep-dive is intertwined with
[ad-hoc-caching.md](ad-hoc-caching.md) (`_custom_state_cache_dict` is
keyed on a tuple containing `spec.config.__hash__()`, where
`spec.config` is the very namedtuple the autouse fixtures and
`with_config_overrides` mutate) and with
[directory-structure.md](directory-structure.md) (the
`tests.core.pyspec.eth_consensus_specs.test.context` shadow at
`conftest.py:114–120` exists only because the package lives inside
`tests/`).

## What fixing it would entail

The solution is a single comprehensive pytest plugin — provisionally
`framework/plugins/pyspec.py` — that absorbs every concern the
decorator stack today expresses ad-hoc, with a thin generator CLI
sharing the plugin's collection and serialisation primitives. Every
problem catalogued in the critique section above maps onto a specific
plugin facet; the framing below is the plugin's surface, not a list
of unrelated cleanups.

The existing `tests/infra/pytest_plugins/yield_generator.py` (~400
lines) is already a partial plugin missing only its `pytest_plugins`
declaration and a typed yield protocol — extending it into the
facets below is the path of least resistance. Both comparables ship
working models with the same shape this plugin would take:
`execution-specs/packages/testing/src/framework/pytest_plugins/filler.py`
and `leanSpec/packages/testing/src/framework/pytest_plugins/filler.py`.

### The plugin's surface, in seven facets

1. **Two entry points sharing one plugin.** The plugin registers via
   `pytest_plugins` for the test-runner path; a thin generator CLI
   imports the same plugin's collection and serialisation primitives
   but skips the assertion path. The dual-mode `is_pytest` /
   `is_generator` flags disappear because the two callers no longer
   share a single function body that has to branch on which one is
   active. This dissolves the autouse `is_pytest_active` fixture
   (`context.py:42`), the `is_pytest`/`is_generator` mutation at
   `context.py:38`, and every conditional that reads them.

2. **Fork selection as a marker, filtered at collection time.** The
   plugin declares `@pytest.mark.fork(<name>)` in `pyproject.toml`'s
   `[tool.pytest.ini_options].markers` and registers a
   `pytest_collection_modifyitems` hook that drops tests whose fork
   marker falls outside the run's `--fork=<range>` predicate. The
   eleven `with_*_and_later` decorators, the `with_phases` /
   `with_fork_metas` factories, and the prose-only "must come first"
   ordering rules all collapse into one marker plus one filter hook.
   Fork chaining (`with_altair_and_later`) becomes a marker
   predicate evaluated against a fork enum, not a wrapper hierarchy.

3. **BLS, preset, and config-overrides as fixtures.** The plugin
   provides a `bls_active` fixture (parametrisable per test), a
   `preset` fixture that selects between `minimal.py` and
   `mainnet.py` and yields the chosen spec module, and a
   `config_overrides` fixture that returns a fresh configured spec
   rather than rebinding a shared one in place. The `bls_switch`
   autouse fixture, the `spec_with_config_overrides` outer wrapper,
   and the `DEFAULT_TEST_PRESET` global all dissolve — each is
   replaced by a fixture the test signature names explicitly. The
   "always_bls last, with_phases first" ordering rule disappears
   because fixture composition is by name, not by stack position.

4. **A typed result protocol replacing `(name, kind, value)`
   tuples.** The plugin defines a `SpecTestResult` dataclass with
   `pre`, `post`, `blocks`, `meta`, `config` fields, plus a
   `ForkTransitionResult` with `pre_fork`, `post_fork`,
   `fork_epoch`, `fork_block`. Both the pytest path and the
   generator CLI serialise the same dataclass; the string
   discriminators (`"data"` vs `"meta"`, `"ssz"` vs `"yaml"`) and
   the duck-typed `isinstance` inference at
   `tests/infra/yield_generator.py:26–45` go away. The Stringly
   Typed yield protocol becomes a Python type the plugin can
   validate at the boundary.

5. **Cache lifetime governed by fixture scope.** The plugin exposes
   a `prepared_state` fixture whose scope (`function`, `module`,
   `session`) determines lifetime; pytest's own scope rules govern
   when a state is rebuilt. The hand-rolled module-global LRU at
   `context.py:74`, with its function-identity hash key, is
   replaced by `@pytest.fixture(scope="session")` — the cache
   becomes a first-class part of the test framework rather than a
   side channel. See [ad-hoc-caching.md](ad-hoc-caching.md) for the
   broader frame; the `_prep_state_cache_dict` LRU is mechanism #1
   of eight.

6. **One canonical import path; no shadow workaround.** The plugin
   imports the spec under one name only. The conftest dual-module
   patch at `conftest.py:118–120` becomes unnecessary once the
   package layout is fixed
   (see [self-referential-package-layout.md](self-referential-package-layout.md)
   and [directory-structure.md](directory-structure.md)). The
   plugin doesn't need to know about both names because there is
   only one.

7. **Prose-only ordering rules compile into the plugin's structure
   or disappear.** Each of the comments at `decorators.py:42`,
   `:91`, `:158` either becomes a fixture-composition constraint
   that the framework enforces (fixtures don't have an ordering
   problem — the test signature names what it needs and pytest
   resolves it), or describes a side effect that no longer happens.
   The comments that survive document genuine spec-level
   invariants, not framework wiring.

### Effort and sequencing

This is a substantial refactor — every test file imports from
`context.py` — but each facet is mechanical, lands independently,
and several fix multiple findings at once. The sequence below is
the transition plan; nothing has to land all at once. A practical
order:
facet 4 (typed yield protocol) and facet 1 (single entry point) are
upstream of the others and the right place to start; facets 2 and 3
(markers and fixtures replacing decorators) are the bulk of the
test-file churn but mechanically uniform; facets 5 and 6 are
unblocked by the corresponding ad-hoc-caching and
self-referential-package-layout deep-dives respectively; facet 7 is
clean-up that follows the others.

## References

Related guides:
- [ad-hoc-caching.md](ad-hoc-caching.md) — the LRU cache at
  `context.py:74` and the function-identity hash key at
  `context.py:83` are inside the same module and key on
  `spec.config.__hash__()`, which the decorator stack mutates.
- [directory-structure.md](directory-structure.md) — the dual-module
  patch at `conftest.py:114–120` is a direct symptom of the package
  living inside `tests/`; both deep-dives need the same lift to
  fully resolve.
- [self-referential-package-layout.md](self-referential-package-layout.md)
  — the `eth2spec` comment at `conftest.py:114–117` and the
  string-keyed `sys.modules` shadow are dual-import-path artefacts.
