# consensus-specs — ad-hoc caching (deep-dive)

The codebase has **eight distinct caching mechanisms** spread across
the test framework, the build tooling, and — most consequentially —
the executable spec itself. The headline issue is mechanism #8: a
runtime memoisation layer baked into every fork's generated
`minimal.py`/`mainnet.py` from a Python string template. The
consequence is a **contract divergence between the spec as defined
and the spec as tested**: spec readers see pure functions in markdown,
tests run impure functions with hidden module-level state, and the
Python reference implementation that generates the inter-client test
vectors is not the same function as the markdown spec that other
clients implement against. The functions share a name and a signature
but not a contract.

Adjacent guides:
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md) (why
the cache lives in a string template),
[decorator-stack.md](decorator-stack.md) (the LRU cache and
function-identity hash key inside `context.py` share the same
mutable-global problem).

## The headline: the executable spec silently memoises seven hot-path functions

`pysetup/spec_builders/phase0.py:47–104` defines a `sundry_functions()`
classmethod that returns a Python **string template**. That string is
concatenated into every fork's generated `minimal.py` and `mainnet.py`
via `pysetup/helpers.py:183–184` (`reduce(lambda txt, builder: ...,
builders, "")`). The template defines a factory:

```python
def cache_this(key_fn, value_fn, lru_size):
    cache_dict = LRU(size=lru_size)

    def wrapper(*args, **kw):
        key = key_fn(*args, **kw)
        if key not in cache_dict:
            cache_dict[key] = value_fn(*args, **kw)
        return cache_dict[key]
    return wrapper
```

…and then **shadows seven canonical spec functions** with cached
versions, using the assignment-shadow pattern (`_orig = orig; orig =
cache_this(...)`):

| Function | Cache key | `lru_size` |
|---|---|---|
| `compute_shuffled_permutation` | `(index_count, seed)` | 256 |
| `get_total_active_balance` | `(validators_root, epoch)` | 10 |
| `get_base_reward` | `(validators_root, slot, index)` | 2 048 |
| `get_committee_count_per_slot` | `(validators_root, epoch)` | `SLOTS_PER_EPOCH * 3` |
| `get_active_validator_indices` | `(validators_root, epoch)` | **3** |
| `get_beacon_committee` | `(validators_root, randao_root, slot, index)` | `SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3` |
| `get_attesting_indices` | `(randao_root, validators_root, attestation_root)` | `SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3` |

The originals remain reachable under `_compute_shuffled_permutation`,
`_get_active_validator_indices`, etc., but every test and every helper
that calls `get_beacon_committee(...)` is silently calling the cached
wrapper.

### Why this is the most consequential of the eight

**The spec-as-defined and the spec-as-tested diverge.**
`specs/phase0/beacon-chain.md` defines these seven functions as
pure: the markdown shows `def get_beacon_committee(state, slot,
index)` with no decorator, no annotation, no marker, no comment.
A reader reasons about it as a pure function — same arguments
yield the same return, no side effects, no module state. That
reasoning is *correct for the markdown* and *wrong for the
runtime*. The runtime is impure with module-level `LRU` state
keyed by SSZ `hash_tree_root()` values; results depend on call
history, on which other tests have run, and on cache eviction
under bounded sizes (some as small as 3). This isn't an
optimisation invisible to tooling — it is a contract divergence
between the canonical spec and the canonical reference
implementation, and the divergence has concrete consequences for
each of the spec's four audiences:

- **Spec authors and EIP authors** reason about a different
  function. A spec author who proposes "let's tighten
  `get_active_validator_indices` to also reject inactive
  validators" reads the markdown definition; the test layer
  runs a memoised wrapper whose key is
  `(validators.hash_tree_root(), epoch)`. Whether the change
  invalidates the cache key — whether memoisation still
  preserves correctness after the change — is reasoning the
  spec doesn't surface and the markdown doesn't prompt.

- **Client implementers in other languages** (Lighthouse,
  Prysm, Teku, Nimbus, Lodestar) read the markdown to write
  their implementation. Their `get_beacon_committee` is pure,
  matching what the spec says. The Python reference
  implementation — the one whose runs *generate the test
  vectors those clients conform against* — is impure with
  state. The spec the vectors are derived from is not the spec
  the clients are implementing. Conformance checking degrades
  to "does your pure implementation produce outputs equal to
  our memoised one's outputs", which is true only because the
  memoisation has been correctness-preserving so far.

- **Test authors** cannot reason locally about test
  determinism. "What happens when this is called twice with
  the same arguments?" depends on which tests ran first, what
  cache entries were evicted, and what `validators.hash_tree_root()`
  collisions occurred earlier. Beck's FIRST property of
  Isolated tests (*Test-Driven Development*, 2002) is silently
  violated; correctness-when-it-holds is luck rather than
  design. There is no `cache_clear()` hook between tests, no
  autouse fixture flushing the LRUs.

- **Code reviewers and fork authors** lose a signal. A new
  fork that introduces a hot-path function —
  `process_payload_attestation` in gloas, say — would benefit
  from being memoised, but nothing in the markdown spec
  prompts the reviewer to revisit the cache template. The
  decision lives in `pysetup/spec_builders/phase0.py:47–104`,
  the only place where one can see "this function gets cached
  with key X, size Y". New caches accrete by knowledge of the
  legacy template, not by spec-level guidance — and missing
  caches go unnoticed because the function still works, just
  slowly.

Feathers (*Working Effectively with Legacy Code*, 2004) calls
this kind of invisible-from-source test seam the worst kind to
debug: the source you read isn't the source that runs, the
behaviour you can reason about isn't the behaviour you observe,
and there is no compiler error or type error to catch the gap.

The divergence is the headline. The supporting concerns below
compound it.

1. **The cache lives inside a string literal.** Until `make _pyspec`
   runs, the `cache_this` source code does not exist in any tracked
   `.py` file. Ruff, mypy, and Pyright all see it as a string. Refactoring the cache means editing the string template at
   `pysetup/spec_builders/phase0.py:47–104`. Static analysis is
   structurally blind to it — and stays blind even after the build,
   because by then the code is in `tests/core/pyspec/eth_consensus_specs/<fork>/{minimal,mainnet}.py`,
   files that `.gitignore` excludes from the repo.

2. **The seven wrapped functions are the hottest path of the spec.**
   `compute_shuffled_permutation`, `get_active_validator_indices`,
   `get_beacon_committee`, and `get_attesting_indices` are called
   constantly during state transitions and attestation processing. The
   decision to memoise them is reasonable (the originals are
   expensive); the decision to do so by string-template plus
   module-level shadow rather than by an explicit reviewable
   decorator hides that the spec has performance-tuned non-pure
   callable points.

3. **`lru_size=3` for `get_active_validator_indices` is a startlingly
   small bound.** A test sequence that touches four states by
   `validators.hash_tree_root()` will evict the first; the next
   invocation is a cold miss. For long matrix runs the cache thrashes
   invisibly. There is no metric, no log, no warning when eviction
   pressure rises.

4. **The keys mix arguments and SSZ-container hashes inconsistently.**
   `compute_shuffled_permutation` uses pure arguments. `get_total_active_balance`
   composes `validators_root` with `epoch`. `get_beacon_committee`
   composes `validators_root` with `randao_root` plus arguments. The
   choice of what enters the key required someone to reason about
   which state mutations *actually* invalidate which lookups — and
   that reasoning lives only inside the string template, with no
   comments and no pointer to it from any spec doc. A fork that
   changes the validator-activation rule could quietly break
   correctness without any cache-policy review.

5. **Caches persist across tests.** They're populated at module-import
   time and live for the pytest process. There is no `cache_clear()`
   hook, no autouse fixture flushing them between tests. Beck's FIRST
   tests (*Test-Driven Development*, 2002) require Isolated; a
   pollution that didn't happen because no two tests share a
   `validators.hash_tree_root()` is correctness-by-luck, not by
   design.

6. **No fork-level override.** `sundry_functions()` is documented as a
   per-fork override hook in `pysetup/spec_builders/base.py:32`. Only
   `phase0.py` defines `cache_this` and its wrappers. Later forks
   inherit phase0's set unchanged. Adding a new hot-path function in
   gloas (e.g. `process_payload_attestation`) means extending
   `phase0`'s template. The override hook exists but the extension
   model doesn't.

## The full inventory: eight distinct caching mechanisms

| # | Mechanism | Locations | Key shape | Bounded? | Visible to static analysis? |
|---|---|---|---|---|---|
| 1 | `lru-dict.LRU(size=10)` global, hand-wrapped decorator | `tests/core/pyspec/eth_consensus_specs/test/context.py:74` (`_custom_state_cache_dict`); `tests/core/pyspec/eth_consensus_specs/test/helpers/rewards.py:312` (`_cache_dict`); `tests/core/pyspec/eth_consensus_specs/test/helpers/attestations.py:478` (`_prep_state_cache_dict`) | three different hand-built tuples | yes (10) | yes |
| 2 | `@functools.cache` (unbounded) | `pysetup/generate_specs.py:66, :85`; `pysetup/md_to_spec.py:462, :470, :475, :487, :504, :514, :538, :575`; `tests/core/pyspec/eth_consensus_specs/test/helpers/blob.py:191` | argument tuple via `__hash__` | **no** | yes |
| 3 | `@functools.lru_cache(maxsize=1)` nested inside a function | `tests/core/pyspec/eth_consensus_specs/test/helpers/inclusion_list.py:137` | no args (singleton per invocation), explicit `cache_clear()` after a monkey-patched scope | yes (1) | yes |
| 4 | Plain module-global `dict` | `tests/core/pyspec/eth_consensus_specs/utils/ckzg_utils.py:8` (`_trusted_setup_cache`) | `(abs_path, precompute)` | **no** | yes |
| 5 | Eagerly-populated `dict` at import time | `pysetup/md_to_spec.py:532–535` (`ALL_KZG_SETUPS`) | `"minimal"` / `"mainnet"` | n/a (fixed) | yes |
| 6 | Closure + `nonlocal` per-step | `tests/generators/compliance_runners/fork_choice/runner/test_run.py:154` (`cached_head`) | none — single slot | yes (1) | yes |
| 7 | Domain-embedded cache field on a model | `tests/core/pyspec/eth_consensus_specs/test/helpers/light_client_data_collection.py` (`LightClientDataCache.data`) | `BlockID` | **no** | yes |
| 8 | **`cache_this` factory + module-shadow, injected via string template into the executable spec** | `pysetup/spec_builders/phase0.py:47–104` (template); generated into `tests/core/pyspec/eth_consensus_specs/<fork>/{minimal,mainnet}.py` | per-function tuple, mostly composing SSZ-container `hash_tree_root()` with arguments | yes (varies, 3 to ~thousands) | **no** (string template; generated dirs are gitignored) |

## Critique by cluster

### The three LRU(10) state-prep wrappers (mechanism #1)

`_custom_state_cache_dict`, `_cache_dict`, and `_prep_state_cache_dict`
are near-clones of each other. Same library (`lru-dict`), same size
(10), same structure: build a key, look it up, on miss run a state
preparation function and store `state.get_backing()`, on hit re-wrap
with `spec.BeaconState(backing=...)`. The only differences are the
file location and the key composition:

- `context.py:74` keys on `(spec.fork, spec.config.__hash__(), spec.__file__, balances_fn, threshold_fn)` — function identity contributes to the key, which is brittle (Python `hash(fn)` is identity-based; the same logical builder imported from a different path collides differently).
- `rewards.py:312` keys on `(state.hash_tree_root(), spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY, spec.SLOTS_PER_EPOCH, epochs)`.
- `attestations.py:478` keys on `(spec.fork, state.hash_tree_root())`.

Three different answers to "is this the same input?". Each is *correct
enough* for its caller, but together they expose the absence of any
project-wide identity model for "prepared state". Changing a global
property (e.g. invalidate on preset change) is a Shotgun Surgery edit
across three files (Fowler, *Refactoring*, 1999, p. 79). Duplicated
Code (Fowler, p. 76) is the most direct textbook hit.

**Note: the pattern is downstream of `remerkleable`'s API.** The
`store_backing → re-wrap with BeaconState(backing=…)` idiom only works
because the SSZ library underlying `consensus-specs` (`eth-remerkleable
== 0.1.30`, distributed as `remerkleable`) exposes a *cached binary
tree backing* as a first-class concept — `view.get_backing()` returns
the immutable tree, and `Container(backing=t)` wraps the tree in a
new view without re-hashing the unchanged subtrees. The cached-tree
optimisation is real and load-bearing for state-transition tests
(thousands of `hash_tree_root` recomputations per run). The price is
that the cache mechanism is intimately coupled to remerkleable's
internal model: every cache that wants to be cheap reaches for
`get_backing()`. A future move to a Pydantic-style typed-SSZ approach
(as `leanSpec` uses) would express these caches differently — values
are immutable and content-hashable, so the cache key is the value
itself rather than a tree handle. That's a much larger change than
this deep-dive proposes; calling out the dependency here so the
shape's origin is explicit.

### The `@functools.cache` zoo in `pysetup/` (mechanism #2)

Eight `@cache` decorators on functions in `pysetup/md_to_spec.py` plus
two more in `pysetup/generate_specs.py`. Several specific issues:

- **Caching by AST identity.** `_get_name_from_heading(heading)`,
  `_get_class_info_from_ast(cls)` (`md_to_spec.py:462`, `:487`) take
  AST nodes whose `__hash__` is identity-based. Two AST nodes
  representing the same heading parsed in two separate calls hash
  differently — the cache rarely hits across parses. Within a single
  parse the same node is unlikely to be queried twice. The decorator
  is decorative.
- **Unbounded `@cache` on `parse_markdown(content: str)`** at
  `md_to_spec.py:575`. The key is the whole file content; the cache
  has no `maxsize`. Every markdown file ever parsed in the process is
  retained. For a build that touches dozens of large markdown files,
  this is not free.
- **Caching I/O.** `load_preset()`, `load_config()`,
  `_load_kzg_trusted_setups()` cache file-system reads forever. No
  `cache_clear()` is called by anything; tests that need a fresh load
  have no path to ask for one.
- **`Sequence[Path]` as cache key.** `load_preset(preset_files:
  Sequence[Path])` requires a hashable sequence; passing a list
  TypeErrors at hash time, passing a tuple is fine. The contract is
  enforced only by runtime error (Hunt & Thomas, *The Pragmatic
  Programmer*, Tip 38: "Configure, don't integrate" — the contract
  should be visible).

### The KZG trusted-setup duplicates (mechanisms #2, #4, #5)

KZG trusted setups are loaded from disk and cached in *three different
ways*:

- `pysetup/md_to_spec.py:514` — `@cache _load_kzg_trusted_setups(preset_name)`, used internally by spec generation.
- `pysetup/md_to_spec.py:532–535` — `ALL_KZG_SETUPS = {"minimal": ..., "mainnet": ...}`, eagerly populated at import time.
- `tests/core/pyspec/eth_consensus_specs/utils/ckzg_utils.py:8` — `_trusted_setup_cache: dict[tuple[str, int], object] = {}`, lazily populated when the test runner first asks for ckzg.

Same logical thing, three implementations, two of them in `pysetup/`
loading from the same files. None share a key shape. Duplicated Code
on a heavy-I/O entity.

### The lone clean pattern (mechanism #3)

`tests/core/pyspec/eth_consensus_specs/test/helpers/inclusion_list.py:137`
is the only piece of the caching surface with proper test isolation:

```python
def run_with_inclusion_list_store(spec, func):
    @lru_cache(maxsize=1)
    def cached_or_new_inclusion_list_store():
        return spec.InclusionListStore()

    cached_or_new_inclusion_list_store_backup = spec.cached_or_new_inclusion_list_store
    spec.cached_or_new_inclusion_list_store = cached_or_new_inclusion_list_store
    try:
        func()
    finally:
        spec.cached_or_new_inclusion_list_store = cached_or_new_inclusion_list_store_backup
        cached_or_new_inclusion_list_store.cache_clear()
```

A per-test cache, bounded, scoped to one `func()` call, monkey-patched
into the spec module, restored and explicitly cleared in `finally`.
This is the pattern the LRU(10) wrappers in mechanism #1 *should* use
but don't. It exists once, used in one place.

## The named anti-patterns

This is a stack:

- **Duplicated Code** (Fowler, *Refactoring*, 1999, p. 76) — the three
  LRU(10) state-prep wrappers; the three KZG trusted-setup loaders.
- **Shotgun Surgery** (Fowler, p. 79) — any project-wide cache policy
  change is an N-place edit.
- **Speculative Generality** (Fowler, p. 109) — eight mechanisms when
  two would suffice (one per-process for state preparation; one
  per-test for I/O fixtures).
- **Inappropriate Intimacy** (Fowler, p. 85) — every caller knows the
  dict is there, the size is 10, and how to compose a key.
- **Configuration as global mutable state** (Hunt & Thomas, *The
  Pragmatic Programmer*, Tip 17, "Eliminate effects between unrelated
  things") — module globals for caches mean tests cannot run in
  isolation by construction; only the inclusion-list pattern recovers
  isolation explicitly.
- **Decorator misuse** (Gamma et al., *Design Patterns*, 1994) —
  `@cache` is meant for "pure function of its arguments". AST-node
  identity isn't pure, file-system state isn't pure, and unbounded
  cache on whole-file string content isn't free.
- **Memoisation without invalidation** — Hunt & Thomas Tip 38
  ("Configure, don't integrate") — the caches' invalidation logic is
  fully implicit (process lifetime, decorator scope, monkey-patch
  teardown).
- **Implementation Shadow** (Feathers, *Working Effectively with
  Legacy Code*, 2004, on hidden test seams) — `cache_this` shadows the
  canonical spec function names. The spec a reader sees in markdown is
  not the spec the runtime executes.
- **Stringly-Built Code** (a sub-form of Stringly Typed, Fowler) —
  generating Python by string concatenation hides the result from
  every static analysis tool the project otherwise relies on.

## What the comparables do — caveat

I have not deep-dived caching in `execution-specs` or `leanSpec` for
this report. The structural shape of the comparables suggests the
cache pressure is different rather than handled differently:

- `leanSpec/src/lean_spec/types/` builds Pydantic state models with
  hash-tree-root computation already memoised on the model side, so
  the `state.hash_tree_root()`-as-key trick that drives the LRU(10)
  wrappers is not needed at the test layer.
- `execution-specs` keeps each fork as a complete Python module;
  cross-fork state-preparation reuse — the thing the LRU(10) caches
  exist to amortise — does not arise.

Verifying that with reads of their helper modules is a follow-on
task; treat the contrast above as a hypothesis, not a finding.

## Why this is load-bearing

Mechanism #8 — `cache_this` shadowing in the executable spec — is
the only one that affects spec correctness reasoning rather than
test ergonomics. A reviewer reading
`specs/phase0/beacon-chain.md` and reasoning about `get_beacon_committee`
as a pure function is reasoning about a different function than the
one tests actually call. Any audit of those seven functions has to
treat the shadow layer as part of the surface, and the shadow layer
is only legible after running `make _pyspec` and reading a gitignored
file.

The other seven mechanisms are local nuisances — Duplicated Code,
small isolation hazards. Mechanism #8 is foundational.

## What fixing it would entail

- **Move `cache_this` out of the spec generation entirely, into the
  test layer.** The cleanest fix for the divergence is for the
  markdown spec to revert to defining pure functions, and for the
  caching to live at the test layer where each test opts in to
  exactly the wrappers it needs. The text at
  `pysetup/spec_builders/phase0.py:59–104` is deleted from the
  builder; the cache module lives at e.g. `tests/infra/spec_cache.py`
  as a tracked Python file (visible to ruff, mypy, and Pyright);
  tests that benefit from caching opt in via marker or
  fixture. This is the shape of [PR 4440](https://github.com/ethereum/consensus-specs/pull/4440)
  — see the "Prior art" subsection below for what was proposed, what
  closed it, and the pytest-fixture version that finishes the design.
- **(Alternative) keep the cache in the spec, but make the shadow
  explicit.** If the team prefers the cache to remain part of the
  reference implementation, replace the assignment-shadow pattern
  with an annotation the markdown spec can carry — e.g. `<!--
  @cache(lru_size=256, key=(index_count, seed)) -->` immediately
  above the function — that `pysetup` reads and turns into cache
  wiring alongside the definition. Spec readers then know from the
  markdown that the function is memoised. This restores the
  divergence to "spec defines a memoised function, test runs the
  same memoised function" rather than the current "spec defines a
  pure function, test runs a memoised one". The test-layer approach
  above is preferable — caching is a *test-execution concern*, not
  a *spec-definition concern* — but this alternative survives if the
  team wants the cache to be a property of the published reference
  implementation.
- **Consolidate the three LRU(10) wrappers.** A single typed
  `StatePrepCache` class with a documented eviction policy and a
  `clear()` hook, used by all three state-prep helpers. Removes the
  Duplicated Code; gives a place for cache invalidation hooks.
- **Bound the `@cache` decorators in `pysetup/`.** Replace `@cache`
  with `@lru_cache(maxsize=N)` everywhere, especially `parse_markdown`.
- **Drop AST-keyed `@cache`.** `_get_name_from_heading`,
  `_get_class_info_from_ast`, and friends should either lose the
  decorator (the saving is illusory) or compute a content-derived key.
- **Provide `cache_clear_all()` for tests.** Either an autouse fixture
  that flushes module-globals or a single project-wide `clear()`
  function; sometimes-flaky timing tests will benefit.
- **Document the policy.** A short `tests/CACHING.md` (or a section
  in `AGENTS.md`) describing where caches live, who owns them, and
  when they're invalidated. Currently nothing in the docs surfaces
  the existence of any of the eight mechanisms.

This is a non-trivial cleanup but considerably smaller than the
self-referential package layout fix
([self-referential-package-layout.md](self-referential-package-layout.md)).
The hardest part is moving the `cache_this` template out of the
string and resolving the shadow naming question with the spec
maintainers.

### Prior art: PR 4440 and the pytest-shaped path for mechanism #8

A 2025 proposal — [consensus-specs PR 4440 ("Spec cache system based
on test decorators")](https://github.com/ethereum/consensus-specs/pull/4440),
opened by Leo Lara — moved the cache out of the spec generation
entirely and into the test layer. Closed without merge in September
2025 on a single objection ("doesn't help multi-threaded execution");
the design otherwise targets exactly the divergence catalogued in this
deep-dive. Reading what was proposed and what was missing is the
shortest path to the right fix.

**What PR 4440 proposed.**

- A `tests/infra/spec_cache.py` module — 247 lines, a real tracked
  Python file (visible to ruff, mypy, Pyright; no string template). 1 895 lines of accompanying unit tests under
  `tests/infra/test_spec_cache.py`.
- A `@spec_cache(["fn1", "fn2", ...])` decorator that each test opts
  into, declaring which spec functions to cache for the duration of
  the test. The decorator looks up a `SpecCache` keyed by
  `(spec.fork, spec.config)`, saves the originals via
  `getattr(spec, fn_name)`, replaces them with cached wrappers via
  `setattr(spec, fn_name, ...)`, and restores them in a `finally`
  block.
- A convenience wrapper `spec_cache_peerdas` for the three KZG/cell
  functions used in PeerDAS tests
  (`compute_cells_and_kzg_proofs`, `verify_data_column_sidecar_kzg_proofs`,
  `recover_cells_and_kzg_proofs`).
- A `--disable-spec-cache` CLI flag plus an autouse fixture for
  debugging; per-function hit/miss `SpecCacheStats` for
  observability.
- `pytest.mark.xdist_group(name="cache_<fns>")` composed with the
  decorator so cache-sharing tests run in the same xdist worker.

Reported result: a ~66% reduction in single-thread run time on the
PeerDAS tests it was applied to.

**Why it addresses the headline divergence.** The markdown spec
reverts to defining `get_beacon_committee` (and the other six
functions) as pure: no decorator on the definition, no annotation,
no marker. The spec object exposes them as pure. Only inside a
`@spec_cache(...)`-decorated test is the function temporarily
shadowed via `setattr`, and only for that test. The four-audience
consequences from earlier in this deep-dive flip:

- Spec authors and EIP authors reason about pure functions; the
  markdown they read is the function the runtime exposes.
- Client implementers in other languages have a pure reference
  implementation to conform against; the test vectors they consume
  are generated from the same shape they implement.
- Test authors see, in the test's own decorators, which functions
  are cached for that test — a local and reviewable choice instead
  of a global module-level shadow.
- Code reviewers and fork authors evaluating a new hot-path function
  decide caching at the test level when (and if) they need it; no
  hidden cache template to extend.

**What closed it.** Maintainer feedback was that per-process caching
gives little benefit when the slowest CI step (the Fulu matrix at
~30 minutes) runs under `pytest-xdist` with multiple workers — each
worker rebuilds its own cache, so the savings don't compound. The
PR's author noted that multi-process cache sharing is independent
work that can be added in a follow-up. The PR was closed on
2025-09-23.

**The pytest-fixture / marker version that finishes the design.**

The PR 4440 design as a pytest plugin instead of a free-standing
decorator — and with the multi-process gap closed:

- **Marker:** `@pytest.mark.spec_cache("fn1", "fn2", ...)`, declared
  in `pyproject.toml`'s `[tool.pytest.ini_options].markers`. Tests
  opt in by name; mistypes are caught by `--strict-markers`.
- **Plugin fixture:** `cached_spec` (function-scoped by default,
  configurable to module / session) reads the test's marker, wraps
  the named spec functions, yields the patched spec, and restores
  in teardown. Replaces the decorator's `setattr`/`finally` dance
  with `monkeypatch.setattr`, which pytest already manages on
  teardown — fewer bespoke moving parts.
- **Cross-process sharing.** A `--spec-cache-store` CLI flag plus
  a `diskcache`- or SQLite-backed `SpecCacheStore` shared across
  xdist workers via a session-scoped tmp path. The serialisation
  surface is small — the seven KZG / committee computations all
  return SSZ-serialisable values whose `hash_tree_root()` is
  already the cache key. This is the multi-process feature
  jtraglia's review asked for; it lands as a fixture-scoped
  store object, not as a re-architecture.
- **Convenience markers** for common bundles
  (`@pytest.mark.spec_cache_peerdas` for the three KZG functions),
  parallel to the `spec_cache_peerdas` helper PR 4440 already
  shipped.
- **xdist grouping** preserved via `@pytest.mark.xdist_group(...)`
  composition with the `spec_cache` marker — same shape PR 4440
  used, now with a real cross-worker store underneath rather than
  per-worker isolation.

This composes cleanly with the broader pytest-plugin solution in
[decorator-stack.md](decorator-stack.md): one plugin can absorb
fork selection, BLS toggle, presets, config overrides, the typed
yield protocol, *and* spec-function caching — each as a marker or
fixture, with shared state managed by pytest's scope rules and a
shared cross-process store.

### Pytest-plugin / fixture angle (the broader picture)

Five of the eight mechanisms are textbook pytest-fixture territory
and would dissolve into the runtime's own scope rules:

- Mechanism #1 (the three LRU(10) wrappers `_custom_state_cache_dict`,
  `_cache_dict`, `_prep_state_cache_dict`) — each becomes a
  `@pytest.fixture(scope="session")` (or `scope="module"` for finer
  invalidation) keyed on `(spec.fork, state.hash_tree_root())`. The
  hand-rolled `LRU(size=10)` + tuple-key + `state.get_backing()`
  re-wrap pattern is exactly what session-scoped fixtures provide
  declaratively.
- Mechanism #3 (`run_with_inclusion_list_store`'s nested
  `lru_cache(maxsize=1)` with `cache_clear()` in `finally`) is the
  right *pattern* expressed as the wrong *mechanism*. A
  `@pytest.fixture(scope="function")` with the spec patch in setup
  and the restore in teardown does the same job declaratively, and
  the test gets the cached store as a parameter rather than via
  monkey-patch.
- Mechanism #6 (the `cached_head` closure with `nonlocal` inside the
  fork-choice runner) is a function-scoped fixture in disguise.
- Mechanism #4 (`_trusted_setup_cache` plain dict) and mechanism #5
  (`ALL_KZG_SETUPS` eager dict) are session-scoped fixtures keyed
  on preset name.

Mechanism #2 (`@functools.cache` zoo in `pysetup/`) is the only one
that is *not* pytest-fixture shaped — it lives in build-time code
that runs before pytest collection. Mechanism #8 was previously
listed here as not fixture-shaped, on the reasoning that it lives
in the runtime spec itself; PR 4440 (above) demonstrated the
opposite by moving the cache out of the spec and into the test
layer via a per-test decorator. The pytest-fixture / marker version
sketched in the prior-art subsection is the right shape for #8 — it
restores the spec-as-defined / spec-as-tested correspondence and is
the most consequential single refactor in this deep-dive.

