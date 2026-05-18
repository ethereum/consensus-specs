# consensus-specs — helper layer (deep-dive)

The helper layer at
`tests/core/pyspec/eth_consensus_specs/test/helpers/` is a 10 000-
line set of god modules threaded with `is_post_<fork>(spec)`
cascades. Six files exceed 500 lines. They mix data-model definitions,
mutation, and assertion in single functions; accept untyped `spec` and
`state` positionally; and impose a fork-addition cost that scales with
the helper-layer size. This is where Shotgun Surgery and Primitive
Obsession compound into ongoing fork-addition cost.

Adjacent guides:
[directory-structure.md](directory-structure.md) (proposes
`framework/helpers/` as the single home; precondition for splitting
these god modules cleanly),
[ad-hoc-caching.md](ad-hoc-caching.md) (the `_prep_state_cache_dict`
LRU at `attestations.py:478` is a state-prep cache that should be a
pytest fixture),
[self-referential-package-layout.md](self-referential-package-layout.md)
(the helpers live inside the package being tested, structurally
preventing clean typing).

## The shape of the problem

Every test is parameterised over `(fork, preset)` and receives two
positional arguments — `spec` and `state` — that fully encode the
runtime context. Tests delegate almost all real work to helpers in
`test/helpers/`. So the helpers carry the cost of a new fork, of a
renamed spec function, of any change to state shape. In a project
where forks ship every 12–18 months, that layer is the load-bearing
part of the test infrastructure.

What's there: 49 top-level modules in `test/helpers/`, 9 454 lines
of Python, plus four per-fork subdirs (`altair/`, `electra/`,
`fulu/`, `gloas/`) with another ~200 lines of near-identical
`run_fork_test()` shims. Six top-level modules cross 500 lines; the
largest is 996. Functions accept `spec` and `state` positionally
with no type annotations, branch at runtime via `is_post_altair /
is_post_bellatrix / …` predicates, mix data construction, mutation
and assertion in one function body, and yield, return, and mutate
in place — often all three at once.

A new fork edits dozens of functions across several of those files.
A renamed `spec.process_slots` does not break at import time — it
breaks at runtime, in whichever helper executes first. The compiler
has nothing to say, because nothing is typed.

## Proof, by line

The largest helpers, by `wc -l`:

| File | Lines | Role |
|---|---:|---|
| `helpers/light_client_data_collection.py` | 996 | Light-client data store + collection harness |
| `helpers/fast_confirmation.py` | 744 | Fast-confirmation test driver |
| `helpers/fork_choice.py` | 691 | Fork-choice store + step harness |
| `helpers/rewards.py` | 559 | Rewards/penalties delta harness |
| `helpers/deposits.py` | 553 | Deposit construction & assertions |
| `helpers/fork_transition.py` | 544 | Cross-fork transition driver |
| `helpers/attestations.py` | 531 | Attestation construction & inclusion |
| `helpers/execution_payload.py` | 490 | Execution payload construction |
| `helpers/multi_operations.py` | 382 | Random-operations bundles |
| `helpers/state.py` | 279 | Slot/epoch/state transitions |

Fork predicates per file (top of the table — these are
`grep -c is_post_…`):

| File | `is_post_*` calls |
|---|---:|
| `helpers/execution_payload.py` | 28 |
| `helpers/rewards.py` | 25 |
| `helpers/genesis.py` | 20 |
| `helpers/attestations.py` | 15 |
| `helpers/fork_choice.py` | 13 |

`forks.py` defines nine `is_post_<fork>(spec)` predicates
(`is_post_altair`, `is_post_bellatrix`, `is_post_capella`,
`is_post_deneb`, `is_post_electra`, `is_post_fulu`, `is_post_gloas`,
`is_post_heze`, `is_post_eip8025`). Each is a trivial wrapper around
`is_post_fork(spec.fork, FORK)`. Callers do not navigate a registry;
they import the predicate they need and key behaviour off it inline.

## Critique / inventory / detailed breakdown

### God modules

`light_client_data_collection.py` (996 L) is the canonical example.
Its first 200 lines define nine `@dataclass` "Forked*" wrappers
(`ForkedBeaconState`, `ForkedSignedBeaconBlock`,
`ForkedLightClientHeader`, `ForkedLightClientBootstrap`,
`ForkedLightClientUpdate`, `ForkedLightClientFinalityUpdate`,
`ForkedLightClientOptimisticUpdate`) plus `BlockID`,
`CachedLightClientData`, `LightClientDataCache`,
`LightClientDataDB`, `LightClientDataStore`,
`LightClientDataCollectionTest` — every field typed `Any`. The
rest of the file does ancestor lookup, finalised-slot lookup,
period→sync-committee resolution, the data-collection test,
branch normalisation, header upgrade, and fork-transition glue.
Twelve concerns, one file.

`fork_choice.py` (691 L) merges fork-choice store construction,
step-by-step protocol simulation, attestation-pool management,
attester-slashing addition, and YAML-step generation.
`fast_confirmation.py` (744 L) uses it directly and adds an
`FCRTest` class that holds `spec`, `seed`, `store`, `fcr_store`,
`test_steps`, `attestation_pool`, `recent_attestations`,
`blockchain_artefacts` as bare attributes.

The pattern: each new test family (light-client data, fast
confirmation, fork-choice generators, fork-transition tests)
landed its entire framework — data model, mutation, persistence,
assertion, yield protocol — in one file. Long Module (Fowler,
*Refactoring*, 1999, p. 76): the unit of change is "edit this
1000-line file" rather than "edit one class".

### Fork switch chains

`rewards.py` is densest: 25 `is_post_*` calls in 559 lines.
`run_get_inactivity_penalty_deltas` (lines 232–298) branches on
`is_post_altair(spec)` six times in 67 lines, interleaving
pre-Altair and post-Altair assertion logic — two algorithms
stitched together by runtime fork checks:

```python
if not is_post_altair(spec):
    matching_attesting_indices = spec.get_unslashed_attesting_indices(...)
else:
    matching_attesting_indices = spec.get_unslashed_participating_indices(...)
...
if is_post_altair(spec):
    assert penalties[index] == 0
else:
    assert penalties[index] == base_penalty
elif is_post_altair(spec):
    assert penalties[index] > 0
```

`get_inactivity_penalty_quotient` (line 29) is a three-arm chain
on `is_post_bellatrix → is_post_altair → pre-Altair`.

`fork_transition.py:67–82` — same shape for execution payloads
(`is_post_gloas → is_post_bellatrix → pre`).
`attestations.py:40–55` — pre/post-Altair accounting inside
`run_attestation_processing`, the central helper for *all*
attestation tests. Lines 86–88 mutate `index = 0` for post-Electra
inside `build_attestation_data`. Line 124 reaches for
`payload_index` only post-Gloas.

These are Switch Statements (Fowler, p. 82); the cure is Replace
Conditional with Polymorphism (p. 255). Strategy / Template Method
(Gamma et al., *Design Patterns*, 1994, pp. 315, 325) are the
textbook alternatives; neither is used.

### Primitive obsession & god-object spec

Every helper takes `spec` and `state` positionally with no type
information. `helpers/typing.py` defines a `Spec` Protocol with
two attributes — `fork: str`, `config: Configuration` — and
`Configuration` declares one, `PRESET_BASE: str`. That Protocol
is imported in *one* place (`specs.py`); no helper annotates its
`spec` parameter against it.

In practice, `spec` is a god object. Helpers reach into it for
SSZ types (`spec.AttestationData`, `spec.Checkpoint`,
`spec.Attestation`, `spec.Bitlist`, `spec.Vector[...]`), constants
(`spec.MAX_ATTESTATIONS`, `spec.MAX_ATTESTATIONS_ELECTRA`,
`spec.SLOTS_PER_EPOCH`, `spec.MIN_ATTESTATION_INCLUSION_DELAY`,
`spec.GENESIS_EPOCH`, `spec.PTC_SIZE`, `spec.MIN_SEED_LOOKAHEAD`),
runtime config (`spec.config.ALTAIR_FORK_EPOCH`), mutating
functions (`spec.process_attestation`, `spec.process_slots`,
`spec.process_block`, `spec.upgrade_to_altair`,
`spec.upgrade_to_fulu`, `spec.upgrade_to_electra`), and pure
queries (`spec.get_current_epoch`, `spec.get_block_root_at_slot`,
`spec.compute_start_slot_at_epoch`).

This is Inappropriate Intimacy (Fowler, p. 85) at the package
level. It's also Primitive Obsession (Fowler, p. 80): fork
identity is `SpecForkName = NewType("SpecForkName", str)`
(`typing.py:7`), string-compared through a recursive
`PREVIOUS_FORK_OF` map (`forks.py:16–29`). A typo `"altair"` vs
`"Altair"` is a silent fall-through.

`state` is the same. `next_slot(spec, state)` mutates `state` in
place via `spec.process_slots(state, state.slot + 1)`
(`state.py:22–26`). Nothing in the signature says so.

### Per-fork helper duplication

`helpers/{altair,electra,fulu,gloas}/fork.py` each define a
`run_fork_test(post_spec, pre_state)` generator with the same
skeleton:

```python
yield "pre", pre_state
post_state = post_spec.upgrade_to_<fork>(pre_state)
stable_fields = [...]                       # ← only this list differs
for field in stable_fields:
    assert getattr(pre_state, field) == getattr(post_state, field)
assert pre_state.fork.current_version == post_state.fork.previous_version
assert post_state.fork.current_version == post_spec.config.<FORK>_FORK_VERSION
yield "post", post_state
```

What differs: the `stable_fields` list (Altair 17, Fulu 33), the
`upgrade_to_<fork>` symbol, and `<FORK>_FORK_VERSION`. Two of
those vary mechanically with the fork name. `stable_fields` is
"fields the previous fork had that didn't change shape" — an
introspection check could compute it, not hardcode it.

`helpers/fulu/state.py` is 6 lines (`initialize_proposer_lookahead`);
`helpers/gloas/state.py` is 16 (`initialize_ptc_window`). Bare
functions with no abstraction. They live in per-fork directories
because there was nowhere else for per-fork logic; no shared
parent type, interface, or registry.

DRY violation (Hunt & Thomas, Tip 11) compounded by Open/Closed
inversion (Meyer, *OOSC*).

### Mixed abstraction levels in one function

`get_valid_attestation` (`attestations.py:100–139`) does, in
order: argument defaulting, attestation-data construction
(delegated), post-Gloas index override (inline),
`spec.Attestation` construction, and aggregate filling with
optional signing (delegated). High-level orchestration, low-level
fork-specific mutation
(`if is_post_gloas(spec) and payload_index is not None: …`), and
SSZ object construction sit at the same indentation depth.

`build_attestation_data` (`attestations.py:61–97`) computes
beacon-block root, epoch-boundary root, source/root, and the
post-Electra `index = 0` clamp inline in 37 lines. There is
nowhere to attach a comment or a test for "what does post-Electra
mean for `index`" because the answer is one `if` deep inside a
constructor.

Violates Clean Code's "one level of abstraction per function"
(Martin, ch. 3).

### Visible test oracle: yield, return, and mutate

`run_attestation_processing` (`attestations.py:21–58`) yields
three named entries (`pre`, `attestation`, `post`) and also calls
`spec.process_attestation(state, attestation)` which mutates
`state` in place; it then yields the same object as `post`. The
caller cannot tell from the signature that `state` will be
mutated, that `pre` is identity-shared (so capturing it pre-call
doesn't snapshot), or that the generator must be consumed for any
of it to happen.

`prepare_state_with_attestations` returns nothing meaningful but
mutates `state`. Its cached cousin
`cached_prepare_state_with_attestations` (`attestations.py:481–
497`) is documented as "does not return anything" — yet at
line 497 calls `state.set_backing(...)`, swapping the underlying
SSZ tree under the caller. Two helpers with the same prefix
disagree on whether they mutate, replace, or compute.

`next_slot`, `next_slots`, `transition_to`,
`transition_to_slot_via_block` (`state.py:22–53`) mutate in place.
`next_epoch_via_block` returns the block (mutating state).
`state_transition_and_sign_block` returns the signed block
(mutating state). No shared signature contract — every helper
must be read in full to know whether to expect a return value, a
yielded sequence, or a side effect.

Side-Effect smell in the context of Separate Query from Modifier
(Fowler, p. 279); "functions should do one thing" (Martin, ch. 3).

### Cross-tree state: an in-progress migration to unit-tested helpers

`tests/infra/helpers/` is a parallel ~1 500-line helper tree —
and unlike the legacy `test/helpers/` tree, every helper module
in it has a sibling `test_*.py` of unit tests:

| Module | Helper LoC | Test LoC |
|---|---:|---:|
| `infra/helpers/withdrawals.py` | 709 | 659 |
| `infra/helpers/deposit_requests.py` | 506 | 321 |
| `infra/helpers/proposer_slashings.py` | 253 | 169 |
| `infra/helpers/builders.py` | 57 | 134 |

That is a deliberate in-progress effort to bring testing
discipline to the test-support layer: the helpers in this tree
have a unit-test contract that the legacy helpers do not. The
broader `tests/infra/` directory continues the same pattern at
the framework level — `test_block_randomized.py` (221 L),
`test_context.py` (257 L), `test_manifest.py` (51 L),
`test_md_to_spec.py` (345 L), `test_template_test.py` (562 L),
and `test_yield_generator.py` (309 L) are unit tests of the
framework's own machinery, and `tests/infra/pytest_plugins/` is
a proper plugin home. None of this exists in `helpers/` or
`tests/core/pyspec/.../test/helpers/`. The direction of travel is
the right one; the smell is not the new tree's existence but its
incompleteness.

The transitional state is what the audit is flagging. The same
domain also lives at `test/helpers/withdrawals.py` (290 L),
`test/helpers/deposits.py` (553 L),
`test/helpers/proposer_slashings.py` (196 L), with no unit tests
of their own. The trees cross-reference each other:
`test/helpers/withdrawals.py:4` imports `from
tests.infra.helpers.withdrawals import
assert_process_withdrawals_pre_gloas, get_expected_withdrawals`,
so one domain lives in two files in two trees with a one-way
dependency. Editing withdrawals logic today requires triangulating
between `test/helpers/withdrawals.py` (legacy),
`infra/helpers/withdrawals.py` (new home with tests), and
`infra/helpers/test_withdrawals.py` (those tests).

The right resolution is to *complete the migration* — move what
remains in the legacy helpers into the infra tree (or whatever
new home the directory-structure refactor settles on), write unit
tests for each as part of the move, and delete the legacy file —
not to undo the new tree. Divergent Change (Fowler, p. 79) at
directory level for the duration of the in-flight migration;
Misplaced Class (p. 86) at module level for what stays in the
legacy tree until migrated.

### Caching scattered in helpers

`attestations.py:478` declares
`_prep_state_cache_dict = LRU(size=10)` at module scope, keyed
by `(spec.fork, state.hash_tree_root())`. This is the helper-layer
instance of the broader caching problem catalogued in
[ad-hoc-caching.md](ad-hoc-caching.md): a helper reaches out of
band for its own LRU, its own keying scheme, its own size tuning,
with no shared infrastructure. There are seven other such
mechanisms; this one is mechanism #1.

## Named anti-patterns

- **Long Module / Long Method** (Fowler, *Refactoring*, 1999,
  pp. 76, 77) — six helpers >500 L;
  `run_get_inactivity_penalty_deltas` is 67 L of fork-conditional
  arithmetic.
- **Long Parameter List** (Fowler, p. 78) —
  `prepare_process_withdrawals` (parallel tree) takes 27 keyword
  parameters; `get_valid_attestation` threads 8.
- **Switch Statements** (Fowler, p. 82) — the `is_post_<fork>`
  cascade. Cure: Replace Conditional with Polymorphism (p. 255).
- **Primitive Obsession** (Fowler, p. 80) — `SpecForkName =
  NewType("SpecForkName", str)`; fork identity is a string
  compared against module-level constants.
- **Shotgun Surgery** (Fowler, p. 79) — a fork edits `forks.py`,
  `constants.py`, `attestations.py`, `rewards.py`,
  `execution_payload.py`, `fork_transition.py`, `withdrawals.py`,
  plus a new `helpers/<fork>/fork.py` shim, plus
  `helpers/<fork>/state.py` if the fork has state changes.
- **Divergent Change** (Fowler, p. 79) — at function level
  (`run_get_inactivity_penalty_deltas` changes for any rule
  change). The directory-level instance (withdrawals logic split
  across `test/helpers/` and `infra/helpers/`) is transitional:
  `tests/infra/` is the project's own in-progress migration
  toward a unit-tested helper layer, not an accidental split.
  See the cross-tree section above.
- **Inappropriate Intimacy** (Fowler, p. 85) — every helper
  reaches into `spec.<anything>`.
- **God Object** (Riel, *Object-Oriented Design Heuristics*,
  1996, ch. 3) — `spec` is a single namespace exposing ~200
  attributes mixing types, constants, and methods.
- **Data Clumps** (Fowler, p. 81) — `(spec, state)` is passed
  positionally to nearly every helper, never bundled into a
  context object.
- **Speculative Generality** (Fowler, p. 109) — the `Spec`
  Protocol declares two fields and is used in one place. No
  actual typing work.
- **Side Effect / Command-Query Separation** (Fowler, p. 279;
  Meyer, *OOSC*, ch. 23) — helpers are simultaneously command
  and query; some yield, return, and mutate at once.
- **Open/Closed inversion** (Meyer, *OOSC*) — every new fork
  modifies existing helpers rather than adding a fork-conformant
  module.

## Comparable contrast

`leanSpec/src/lean_spec/types/` defines narrow, Pydantic-validated
domain types — `ValidatorIndex`, `Slot`, `Epoch`, `Bytes32` — each
with its own validation, arithmetic, and identity. A function that
takes a `Slot` cannot accidentally be called with an `Epoch`. No
`is_post_*` cascade because there is no untyped `spec` god object.
The opposite of Primitive Obsession, by design.

`leanSpec/packages/testing/src/consensus_testing/forks/forks.py`
implements a fork registry: forks are objects with behaviour,
looked up by enum, selected polymorphically. The harness asks
"give me the fork for this scenario", not "is this spec post-X?".
The architectural shape this is being generalised into — a
`ForkProtocol` ABC, concrete per-fork classes that inherit
incrementally, and capability Protocols (`PQCapable`,
`ForkChoiceCapable`, `NetworkCapable`) for sub-spec conformance —
is documented in [*Proposal: Multi-Fork Architecture for
leanSpec*](https://hackmd.io/1iYMp6k_RXu0g9vGloV2ag) and is the
reference design for the fix sketch below.

`execution-specs/src/ethereum/forks/<fork>/` is the structural
counterpart: each fork is its own module, with its own state-
transition functions, block layout, and helpers. A test for Osaka
imports `ethereum.forks.osaka` and gets exactly Osaka's behaviour.
No `is_post_<fork>` chains because cross-fork conditional logic
doesn't live in shared helpers — fork knowledge stays local.
Adding a fork is a new directory, not edits across a 10 000-line
shared helper layer.

Structural difference: the comparables locate fork-specific
behaviour with the fork. consensus-specs centralises it in shared
helpers and gates it with predicates at runtime. The comparables
get type-checking and Open/Closed compliance for free.

## Why this is load-bearing

- **Every test depends on this layer.** Tests in
  `test/<fork>/<category>/test_*.py` are short (20–80 lines) and
  all reach into `helpers/`. A regression in
  `state_transition_and_sign_block` is felt by every block-
  producing test; a regression in `get_valid_attestation` by
  every attestation-signing test. Blast radius = whole corpus.
- **Fork addition is paid in this layer.** Each new fork adds an
  `is_post_<fork>` predicate, a `helpers/<fork>/fork.py` shim,
  and edits to ~6–10 of the largest existing helpers. The work
  is repetitive, distributed, and unguided by the type system —
  it scales linearly in forks and quadratically in
  (fork × helper responsibility).
- **Spec rename is silent until runtime.** Helpers reach into
  `spec.<symbol>` by attribute access. If `process_slots` is
  renamed `process_slot`, no helper fails at import time; the
  first test to exercise that path fails at runtime. Because
  helpers are the only callers (tests delegate everything), the
  failure is far from the change.
- **Compounding with directory structure.** Helpers live inside
  the test package they support; extracting them to a real
  framework module
  ([directory-structure.md](directory-structure.md)) requires
  rewriting consumer imports too. The refactors are coupled.
- **Compounding with caching.** `_prep_state_cache_dict` is one
  of eight ad-hoc caches
  ([ad-hoc-caching.md](ad-hoc-caching.md)). It lives in
  `attestations.py` because there is no shared
  framework-fixtures-and-caching layer. Same lift.

## What fixing it would entail

The shape of the solution is not speculative. leanSpec has a
concrete design proposal currently being adopted that captures
exactly the polymorphism / fork-as-class approach this deep-dive
points toward — and the steps below frame each helper-layer smell
as a piece of that proposal rather than as an independent cleanup.
Reference: [*Proposal: Multi-Fork Architecture for
leanSpec*](https://hackmd.io/1iYMp6k_RXu0g9vGloV2ag).

### The reference design (leanSpec proposal)

Three layers, each replacing a category of helper-layer smell.

1. **A `ForkProtocol` ABC.** One abstract interface declares the
   operations every fork must implement — `process_block`,
   `state_transition`, `process_attestations`, `upgrade_state` —
   plus class-level type pointers (`StateType`, `BlockType`) for
   the fork's state and block shapes. This replaces the
   two-attribute `Spec` Protocol at
   `tests/core/pyspec/.../helpers/specs.py:5–7`, which today
   carries no behavioural contract at all.

2. **Concrete fork classes that inherit incrementally.** Each
   fork is a class (`Devnet0(ForkProtocol)`,
   `Devnet1(Devnet0, PQCapable)`, …) that overrides only the
   methods that genuinely changed; everything unchanged is
   inherited. Adding a new fork becomes one new class file with
   one or two overridden methods, not a Shotgun Surgery edit
   across the helper layer. The `is_post_<fork>(spec)` cascades
   disappear because fork-typed dispatch *is* the class hierarchy.

3. **Capability `Protocol`s for sub-spec conformance.**
   Runtime-checkable Protocols (`PQCapable`, `ForkChoiceCapable`,
   `NetworkCapable`) mark which optional features a fork
   supports. Tests ask `isinstance(fork, PQCapable)` rather than
   chaining `is_post_electra(spec) and is_post_fulu(spec)`
   predicates; sub-spec conformance becomes a typed contract
   checkable at CI time.

State follows the same pattern via Pydantic model inheritance:
`Devnet1State(Devnet0State)` adds fields; type checkers verify
the addition; unchanged fields are shared by inheritance rather
than re-declared. This solves the *primitive-obsession-and-god-
object-spec* smell at the data-model layer the same way the fork
classes solve it at the behaviour layer.

A small `SpecRunner` era-aware dispatcher (`dict[str,
ForkProtocol]`) replaces the implicit fork-name → behaviour
dispatch threaded through the helper layer today. The proposal's
migration plan is phased and non-disruptive — Phase 1 is "wrap
the current code as `Devnet0`, all tests pass unchanged" — so the
transition can begin without touching test behaviour, and each
later phase lands independently.

### How the helper-layer smells map onto the design

1. **Fork-switch chains → fork-class polymorphism (Replace
   Conditional with Polymorphism).** The seven `is_post_<fork>`
   predicates and the helper bodies that branch on them collapse
   into method dispatch on the active fork class. The proposal's
   `Devnet1._check_attestation_signatures` example shows the
   shape — only the changed method is overridden; the rest is
   inherited.
2. **Primitive Obsession → typed state and typed forks.** The
   `SpecForkName = str` alias and the `(spec, state)` Data Clumps
   go away when the fork is a class instance and the state is a
   typed Pydantic model. Renames are caught by the type checker
   rather than producing silent runtime fallthroughs.
3. **God modules → behaviour on fork classes (or composed
   helpers).** The 996-line `light_client_data_collection.py`
   becomes methods on the fork class (or helper classes the fork
   class delegates to). Splitting it into
   `light_client/{data_model,store,collection,branch}.py` is the
   directory-level expression of the same split; each piece is
   testable on its own.
4. **Per-fork helper duplication → inheritance.** The five
   near-identical `helpers/<fork>/fork.py` files at ~40 lines each
   become subclass overrides; the parts that genuinely differ
   between forks are the only code that gets written twice.
5. **Complete the in-progress migration to unit-tested helpers.**
   `tests/infra/` is the project's own remediation effort: every
   helper in `tests/infra/helpers/` has a sibling `test_*.py`,
   the broader `tests/infra/test_*.py` files unit-test the
   framework's own machinery, and `tests/infra/pytest_plugins/`
   is a proper plugin home. The remaining work is to migrate the
   legacy `test/helpers/{withdrawals,deposits,proposer_slashings,
   …}.py` modules into the same pattern — adding sibling unit
   tests as part of the move and deleting the legacy file once
   the new home compiles. With the fork classes from steps 1–2 in
   place, the natural new home is "method on the fork class" or
   "module under the fork's package"; whichever home the
   directory-structure refactor settles on, the unit-test
   discipline that `tests/infra/` already practises stays. The
   *direction* of the move is set; the work is to finish it. See
   [directory-structure.md](directory-structure.md).
6. **Visible test oracle (yield/return/mutate) → Separate Query
   from Modifier.** Helpers either return or mutate, not both.
   Pytest fixtures carry mutated state across tests
   declaratively; the polymorphic fork methods stay query-shaped.
7. **Caching scattered in helpers → fixture scope.** The
   per-helper LRU wrappers in
   [ad-hoc-caching.md](ad-hoc-caching.md) collapse into pytest's
   fixture-scope caching once state-builders are fixtures rather
   than helper functions.

### Pytest integration

The leanSpec proposal shows the testing pattern explicitly, and
it composes cleanly with the pytest-plugin solution in
[decorator-stack.md](decorator-stack.md):

- **Parametrise over fork classes.**
  `@pytest.mark.parametrize("fork_cls", [Devnet0, Devnet1])`
  runs the same conformance test against every fork — replacing
  the eleven `with_*_and_later` decorators with one
  `parametrize` per test (combined with the
  `pytest_collection_modifyitems` hook from the decorator-stack
  fix for fork-range filtering).
- **Conformance tests via Protocol membership.**
  `assert isinstance(Devnet1(), PQCapable)` is a single-line
  type-checked assertion that replaces scattered "does this
  fork's helpers handle PQ signatures?" prose checks across the
  test layer.
- **State-builder helpers become fixtures.** Helpers like
  `prepare_state_with_attestations`, `transition_to`,
  `next_epoch_via_block`, `set_full_participation` become
  session- or module-scoped `@pytest.fixture` returning the fork
  class's `StateType` instance. Per-fork variants override the
  base fixture in a fork-specific `conftest.py`. The hand-rolled
  LRU wrappers in [ad-hoc-caching.md](ad-hoc-caching.md) collapse
  into pytest scope (the runtime gives scope-appropriate caching
  for free); the "query or mutation?" smell goes away because
  fixtures have a clear contract; tests gain a clear parameter
  list instead of an opaque positional `(spec, state, ...)`
  contract.
- **Test-data factories return callables.** Builders like
  `get_valid_attestation`, `build_attestation_data`,
  `get_random_attester_slashings` return callables from a
  factory fixture — the standard pytest pattern for builder-
  style APIs.

### Effort and sequencing

The directory-structure refactor in
[directory-structure.md](directory-structure.md) is a
precondition: until the fork classes have a home outside the
test package, splitting the helper layer only multiplies the
path-depth problem. The leanSpec proposal's Phase 1 — wrap the
current code as `Devnet0` and let all tests pass unchanged —
addresses the scope concern: the transition is phased, each
phase lands independently, and the first phase is mechanical
and non-disruptive. Phases 2 onward (per-fork subclasses,
capability Protocols, the SpecRunner dispatcher) land as new
forks arrive rather than as a single big-bang refactor.

## References


Related guides:
- [directory-structure.md](directory-structure.md) — proposes
  `framework/helpers/` as the single home; precondition for
  splitting these god modules cleanly.
- [ad-hoc-caching.md](ad-hoc-caching.md) — the
  `_prep_state_cache_dict` LRU at `attestations.py:478` is
  mechanism #1 of eight; the helper layer is its host.
- [self-referential-package-layout.md](self-referential-package-layout.md)
  — the helpers live inside the package being tested, which is
  the structural reason they can't be cleanly typed today.
- [package-export-boundary.md](package-export-boundary.md) — the
  ~10 000-line helper layer ships inside the installed wheel
  alongside the runtime spec, so a downstream user pulling
  `eth_consensus_specs` for the spec also installs the helpers as
  part of the public surface.

Literature:

- Fowler, *Refactoring* (1999) — Long Method (p. 76), Long
  Parameter List (p. 78), Switch Statements (p. 82),
  Primitive Obsession (p. 80), Shotgun Surgery (p. 79),
  Divergent Change (p. 79), Feature Envy (p. 80), Data Clumps
  (p. 81), Inappropriate Intimacy (p. 85), Misplaced Class
  (p. 86), Speculative Generality (p. 109), Replace
  Conditional with Polymorphism (p. 255), Separate Query from
  Modifier (p. 279).
- Martin, *Clean Code* — SRP (ch. 10); functions should do one
  thing (ch. 3); one level of abstraction per function (ch. 3);
  expressive names (ch. 2); DIP (ch. 11).
- Gamma, Helm, Johnson, Vlissides, *Design Patterns* (1994) —
  Strategy (p. 315) and Template Method (p. 325) as the
  structural alternatives to `is_post_X` cascades.
- Meyer, *Object-Oriented Software Construction* — Open/Closed
  Principle; Command-Query Separation (ch. 23).
- Hunt & Thomas, *The Pragmatic Programmer* — Tip 11 (DRY).
- Riel, *Object-Oriented Design Heuristics* (1996) — God Object
  / large-class heuristics.
