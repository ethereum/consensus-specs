# consensus-specs — compliance runners (deep-dive)

`tests/generators/compliance_runners/` is one of the more interesting
pieces of test engineering in `consensus-specs`: the only place in
the project where test cases are **synthesised by constraint solving**
rather than hand-authored. A MiniZinc-backed generator enumerates
valid block-tree topologies; a runner replays the resulting YAML/SSZ
event vectors through the spec; a YAML config layer drives instance
variation. Synthetic test-case generation catches a class of bugs
authored tests miss, and using a constraint solver to enumerate valid
topologies is exactly the right tool for the job — adding these
tests is straightforwardly a good idea, and the audit's recommended
direction is *more* of this style of testing, not less.

**What this deep-dive catalogues is the *integration* with the rest
of the test framework, not the technique itself.** How the runner
finds tests, how the scenario format is described, how BLS state is
toggled, how mutations are dispatched, where the YAML config lives —
those are operational choices the constraint-solver approach does
not require, and most of them collide with patterns the rest of the
project uses. The fix preserves the generator and the runner; it
fixes the seams between them and the surrounding code.

Adjacent guides:
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md) (the
test-vector format problem),
[build-orchestration.md](build-orchestration.md) (the `make comptests`
recipe),
[directory-structure.md](directory-structure.md) (where this would
land in a refactored layout),
[ssz-generic-vectors.md](ssz-generic-vectors.md) (sibling ad-hoc
vector-generation system, with a different shape).

## The shape of the problem

The technique here is something the rest of the project doesn't
have and would benefit from more of. Adding constraint-solver-
synthesised tests is the audit's *recommended* direction, not its
target. What's strange — and what this section catalogues — is
purely the integration: three properties make this particular
subdirectory stand apart from the rest of `tests/` in ways that
look more like accidental divergence than intentional design.

1. **Only one runner exists.** The directory is named
   `compliance_runners/` (plural) and has a `gen_base/` shared-
   infrastructure subdirectory, suggesting a generic framework. In
   practice only `fork_choice/` exists. Speculative Generality
   (Fowler) embedded in the directory structure.
2. **Three sources of truth.** The fork-choice scenario format is
   defined in *three* places: (a) the markdown format spec at
   `tests/formats/fork_choice/README.md`; (b) the MiniZinc constraint
   models at `tests/generators/compliance_runners/fork_choice/model/*.mzn`;
   (c) the Python instantiators that consume MiniZinc output at
   `tests/generators/compliance_runners/fork_choice/instantiators/`.
   Keeping these aligned is enforced only by code review.
3. **Two conftests with deliberately opposite BLS state.** The
   generator (`compliance_runners/fork_choice/conftest.py:42–43`)
   has `bls.bls_active = True` (via `prepare_bls()`); the runner
   (`compliance_runners/fork_choice/runner/conftest.py:30–31`) has
   `bls.bls_active = False`. The same pipeline produces vectors with
   BLS active and validates them with BLS inactive. This is a
   deliberate testing decision but lives only as two separate autouse
   fixtures that a reader has to find and connect manually.

None of these three properties is about the constraint-solving
technique itself, the MiniZinc choice, or the decision to synthesise
vectors. The generator and the runner are the work to *preserve*;
the surface to fix is how they connect to the rest of the test
framework.

## Proof, by line

### Layout (43 files)

```
tests/generators/compliance_runners/
├── __init__.py
├── gen_base/                            ← shared "framework" (3 files)
│   ├── __init__.py
│   ├── gen_typing.py
│   ├── output.py
│   └── pytest_support.py
└── fork_choice/                         ← only concrete runner
    ├── __init__.py
    ├── conftest.py                      ← generator-mode pytest config
    ├── README.md
    ├── generate_comptests.py            ← pytest test that emits vectors
    ├── generate_test_instances.py       ← MiniZinc solver wrappers
    ├── instantiators/                   ← scenario builders (7 files)
    │   ├── block_cover.py, block_tree.py, debug_helpers.py,
    │   ├── helpers.py, mutation_operators.py, scheduler.py,
    │   └── test_case.py
    ├── model/                           ← MiniZinc constraint models
    │   ├── Block_cover.mzn
    │   ├── Block_tree.mzn
    │   └── SM_links.mzn
    ├── runner/                          ← validates generated vectors
    │   ├── __init__.py
    │   ├── conftest.py                  ← runner-mode pytest config
    │   └── test_run.py
    ├── tiny/, small/, standard/         ← per-size YAML configs
    │   ├── test_gen.yaml
    │   ├── block_tree_tree.yaml, block_tree_other.yaml,
    │   ├── block_cover.yaml,
    │   └── (plus block_tree_tree_2.yaml in small/ and standard/)
    └── sample_*.yaml                    ← 4 hand-rolled exemplars
        ├── sample_attester_slashings.yaml
        ├── sample_block_cover.yaml
        ├── sample_block_tree.yaml
        └── sample_invalid_messages.yaml
```

### Key citations

- **`compliance_runners/fork_choice/conftest.py:14–18`** — the comment
  is unusually candid about the smell:

  ```python
  # The compliance generator relies on generator-mode decorators
  # being resolved at import time, so set the context before
  # importing the generator module.
  configure_generator_context()

  from .instantiators.test_case import enumerate_test_groups, prepare_bls  # noqa: E402
  ```

  The `noqa: E402` (module-level import not at top of file) is the
  giveaway: the import order is constrained by hidden global state.

- **`compliance_runners/fork_choice/conftest.py:42–43`** — autouse
  fixture turning BLS *on*:

  ```python
  @pytest.fixture(scope="session", autouse=True)
  def _prepare_bls():
      prepare_bls()
  ```

- **`compliance_runners/fork_choice/runner/conftest.py:30–32`** —
  autouse fixture turning BLS *off* in the same package tree:

  ```python
  @pytest.fixture(scope="session", autouse=True)
  def _disable_bls():
      bls.bls_active = False
  ```

- **`compliance_runners/fork_choice/generate_test_instances.py:6`** —
  the entire generator depends on MiniZinc:

  ```python
  from minizinc import Instance, Model, Solver, Status
  ```

  `minizinc==0.10.0` is pinned in `consensus-specs/pyproject.toml:31`
  as a *test-extras* dependency. A contributor who runs `pip install
  -e .[test]` gets it; a contributor running `pip install -e .` does
  not. The dependency is heavyweight: MiniZinc requires a separate
  binary install (`gecode` solver, see `:43` `Solver.lookup("gecode")`),
  not just a Python package.

- **`compliance_runners/fork_choice/generate_test_instances.py:36–66`**
  — `solve_sm_links`, `solve_block_tree`, `solve_block_cover` directly
  instantiate the solver synchronously and yield solutions. No
  parallelism, no caching, no cancellation hook. The constraint
  problem is small enough that this is fine in practice but fragile
  if the bounds grow.

- **`compliance_runners/fork_choice/instantiators/mutation_operators.py:55–63`**
  — Stringly-Typed dispatch:

  ```python
  def apply_mutation(self, tv, op_kind, *params):
      if op_kind == "shift":
          return self.apply_shift(tv, *params)
      elif op_kind == "late_arrival":
          return self.apply_late_arrival(tv, *params)
      elif op_kind == "multi_route":
          return self.apply_multi_route(tv, *params)
      else:
          assert False
  ```

  An enum or a registry would let new mutations register themselves;
  the `assert False` fall-through is silent failure dressed as a
  guarantee. Compounded by the fact that the *kind strings* are
  embedded in test-case metadata that consumers of the generated
  vectors might want to inspect — they have no protocol for doing
  so.

- **`compliance_runners/fork_choice/runner/test_run.py:31`** —
  filename-pattern surgery to extract the test-case prefix:

  ```python
  def get_prefix(p):
      return p[p.rindex("/") + 1 : p.rindex(".")]
  ```

  This reimplements path parsing the slow way. Combined with
  `glob(f"{td}/block_*.ssz_snappy")` at lines 38–58, the runner
  re-discovers vectors by filename convention rather than reading
  the `meta.yaml` manifest the generator already writes.

- **`compliance_runners/fork_choice/standard/test_gen.yaml`** — six
  test groups (`block_tree_test`, `block_weight_test`,
  `shuffling_test`, `attester_slashing_test`, `invalid_message_test`,
  `block_cover_test`), each with `test_type`, `instances`, `seed`,
  `nr_variations`, `nr_mutations`, plus optional boolean flags
  (`with_attester_slashings`, `with_invalid_messages`). No schema —
  a misnamed key silently produces zero tests. The `instances` field
  is a *filename* (e.g. `block_tree_tree.yaml`) that points to
  another YAML file in the same directory. Two-level YAML indirection
  with no validation.

- **`Makefile:301–324`** — the `comptests:` target chains seven
  conditional variables (`FC_GEN_CONFIG`, `MAYBE_TEST`,
  `MAYBE_PARALLEL`, `MAYBE_FORKS`, `MAYBE_PRESETS`, `MAYBE_SEED`,
  `MAYBE_GROUP_SLICE_INDEX`, `MAYBE_GROUP_SLICE_COUNT`) before
  invoking `pytest` against
  `tests/generators/compliance_runners/fork_choice/generate_comptests.py`.
  Same pattern as the main `test:` target — see
  [build-orchestration.md](build-orchestration.md).

- **`tests/infra/dumper.py`** is imported by `generate_comptests.py`
  to write vectors. So the compliance-runners' output path goes
  through the same `Dumper` infrastructure as the main pyspec test
  vectors, but via a different code path (`gen_base/output.py`'s
  `dump_test_case_result(result, dumper)` rather than the
  `yield_generator` plugin's vector emission).

## Critique / inventory

### A "framework" with one user

`gen_base/` holds three files (`gen_typing.py`, `output.py`,
`pytest_support.py`) that together count ~150 lines of
"framework". Only `fork_choice/` uses them. Either there are *other*
compliance runners that haven't been written yet (Speculative
Generality — Fowler, *Refactoring*, 1999, p. 109), or `gen_base/`
is over-abstracted for its single consumer (Hunt & Thomas, *The
Pragmatic Programmer*, Tip 12 — "Don't gold-plate"). The directory
name `compliance_runners/` (plural) commits to the former
interpretation; the actual code commits to the latter. Without a
roadmap entry naming the second runner, a maintainer can't tell
which.

### Three sources of truth for the same scenario format

The fork-choice scenario shape — what counts as a valid sequence of
blocks, attestations, ticks, and checks — is defined in three
artefacts that must stay aligned:

- `tests/formats/fork_choice/README.md` — markdown prose, the
  "spec" of the YAML format consumers should expect.
- `tests/generators/compliance_runners/fork_choice/model/*.mzn` —
  three MiniZinc files encoding *valid* block-tree, block-cover, and
  super-majority-link topologies as constraints over integer
  variables.
- `tests/generators/compliance_runners/fork_choice/instantiators/*.py` —
  Python that consumes MiniZinc output and emits Python objects
  matching the markdown spec.

Adding a new check type requires synchronised edits to all three;
the only enforcement is code review. Hunt & Thomas Tip 11 (DRY)
applies at the meta level — the format is not the same DRY violation
as a duplicated function, but *its specification* is duplicated
across three formalisms with no validator translating between them.
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md)
covers (a) and partly (c); the MiniZinc layer is unique to
compliance-runners.

### Two conftests with opposite autouse semantics

The split between
`compliance_runners/fork_choice/conftest.py` (BLS *on*) and
`compliance_runners/fork_choice/runner/conftest.py` (BLS *off*) is a
deliberate decision: vectors are generated with valid signatures and
*replayed* without re-verifying signatures (because validation under
runner mode is about fork-choice logic, not signature correctness).
But the two autouse fixtures sit ~80 lines apart in the file tree
and don't reference each other; a reader has to deduce the design
from the symmetry. Beck's FIRST tests
(*Test-Driven Development*, 2002, "Self-validating") would prefer
the BLS-state contract to live in a single named fixture or marker
that both modes opt into explicitly, with a docstring explaining
the asymmetry.

### Generator-mode side-effect at import time

`compliance_runners/fork_choice/conftest.py:14–18` requires
`configure_generator_context()` to run *before* the import of
`enumerate_test_groups`. The context flag (`is_generator = True`)
is read by spec-test decorators at module-import time —
`tests/core/pyspec/eth_consensus_specs/test/context.py:321–322`
(the same dual-mode flags covered in
[decorator-stack.md](decorator-stack.md)) — to decide whether the
yielded values become test-vector output or pytest assertions. The
order dependency is acknowledged in the comment, papered over with
a `noqa: E402`. Configuration as Global Mutable State (Hunt &
Thomas, Tip 17) — the import statement order is load-bearing for a
side-effect that lives in a different module.

### Stringly-typed mutation dispatch with silent fall-through

`mutation_operators.py:55–63`'s `if/elif/else: assert False` is
classic Stringly Typed (Fowler) plus a silent failure mode. Adding
a new mutation operator means editing this dispatch. An enum
(`class MutationKind(Enum): SHIFT = "shift"; LATE_ARRIVAL =
"late_arrival"; MULTI_ROUTE = "multi_route"`) plus a registry-
backed dispatch would catch unknown operators at construction time.
`assert False` also disappears under `python -O`, leaving an
implicit fall-through.

### Filename-pattern discovery in the runner

`runner/test_run.py:38–58` rediscovers test-case files via glob
(`block_*.ssz_snappy`, `attestation_*.ssz_snappy`, etc.) and a
hand-rolled `get_prefix` (line 31) that does string slicing on path
separators rather than using `pathlib.Path.stem`. Brittle
(filename rename = silent test miss) and not documented
anywhere. The `meta.yaml` the generator writes already lists the
files in the test case; the runner could read it and skip the glob
entirely.

### YAML config indirection without validation

`standard/test_gen.yaml` references `instances: block_tree_tree.yaml`
which is a separate file in the same directory. Two levels of YAML
indirection, no schema, no Pydantic, no validation that the
referenced file exists or matches the expected schema. A typo in
`instances:` produces a `FileNotFoundError` at solver time, not at
config-load time. Hunt & Thomas Tip 38 ("Configure, don't
integrate") — the config layer is integration-shaped, not
config-shaped.

### Sample YAML files alongside size-graded configs

The four `sample_*.yaml` files at `compliance_runners/fork_choice/`'s
root (`sample_attester_slashings.yaml`, `sample_block_cover.yaml`,
`sample_block_tree.yaml`, `sample_invalid_messages.yaml`) are
hand-rolled exemplars sitting next to but distinct from the
`tiny/`, `small/`, `standard/` size-graded configs. Their
relationship to the size-graded set is undocumented — are they
testing the generator? Reference inputs? Examples for
documentation? A maintainer can't tell.

### Stringly-typed YAML keys for behaviour flags

`with_attester_slashings: true`, `with_invalid_messages: true` —
boolean flags in YAML that toggle code paths in the generator.
Adding a new flag means edits in three places (the YAML schema-
that-isn't, the `test_case.py` reader, and the instantiator that
implements the flag). The pattern is reasonable in isolation but
joins the project-wide N-place pattern documented in
[fork-registration.md](fork-registration.md).

## Named anti-patterns

- **Speculative Generality** (Fowler, *Refactoring*, 1999, p. 109)
  — `compliance_runners/` and `gen_base/` are scaffolding for
  runners that don't exist; only `fork_choice/` populates them.
- **Stringly Typed** (Fowler) — `mutation_operators.py:55–63`
  dispatches on `op_kind` strings; YAML configs use string keys
  for behaviour flags; `runner/test_run.py:31` extracts test-case
  prefixes via string slicing.
- **Configuration as Global Mutable State** (Hunt & Thomas, *The
  Pragmatic Programmer*, Tip 17) — the `configure_generator_context()`
  call must precede the `enumerate_test_groups` import; the import
  order encodes a side-effect.
- **Comments-as-Deodorant** (Fowler) — the `noqa: E402` comment at
  `conftest.py:18` and the surrounding 3-line explanation are doing
  the documentation work that the type system or fixture protocol
  should do.
- **Multi-source-of-truth / DRY violation** (Hunt & Thomas, Tip 11)
  — three artefacts (markdown spec, MiniZinc model, Python
  instantiator) describe the same scenario format.
- **Inappropriate Intimacy** (Fowler, p. 85) — the runner's
  filename-pattern discovery knows the dump-side filename conventions
  in detail and breaks on rename.
- **Beck FIRST violation — Self-validating** (Beck, *Test-Driven
  Development*, 2002) — the BLS-on / BLS-off split between the two
  conftests is a contract communicated by symmetry rather than by
  declaration.
- **Silent-failure smell** — `mutation_operators.py:62`'s
  `else: assert False` becomes a no-op under `python -O`.

## Comparable contrast — caveat

Neither `execution-specs` nor `leanSpec` has an exact equivalent of
the constraint-solving compliance generator, so a direct contrast
isn't available. What both comparables *do* have is a unified
test-vector framework where the synthesis path and the validation
path share a single typed model:

- `execution-specs/packages/testing/src/execution_testing/test_fixtures/`
  defines fixture base classes that both the generator and the
  consumer derive from, with `@field_serializer` annotations
  declaring the serialisation shape.
- `leanSpec/packages/testing/src/consensus_testing/test_fixtures/`
  uses Pydantic models for the same role, with the same shared-
  model property.

In both, "the format" is a Python type, not a markdown README plus
a constraint model plus an instantiator. New scenarios are subclasses
or new instances of the existing model, not new YAML files plus new
MiniZinc constraints plus new instantiators.

If consensus-specs adopted a similar shape, the constraint-solving
technique would still have a place — it would generate values for a
typed `BlockTreeScenario` model rather than emit YAML that a runner
re-parses. The model would be the bridge between (a) hand-authored
exemplars, (b) constraint-solver-synthesised cases, and (c) the
runner that validates them. The three-source-of-truth problem
collapses into one.

## Why this is load-bearing

This is *not* a "Most consequential finding" — the compliance
runners affect a focused part of the test surface (fork-choice
scenario testing) and most contributors don't touch them. But two
properties make this deep-dive worth its own report:

1. **It's the only place in the project where this pattern exists.**
   A future contributor adding a second compliance runner (e.g. for
   light-client sync, attestation pool, gossipsub) inherits all of
   the above smells *and* implicitly commits the project to the
   "synthesised vectors via MiniZinc" architecture. Documenting the
   smells now prevents the "second runner copies the first" failure
   mode.

2. **It's the most sophisticated test-generation technique in the
   project, and the smells are about its integration, not its
   technique.** The MiniZinc-driven synthesis is a strength to
   preserve and extend — constraint solving for valid graph
   topologies is the *right* tool, and the audit's recommendation
   is for *more* of this style of testing in the project, not less.
   The Stringly-Typed dispatch, the global-mode toggle, the
   filename-pattern discovery, the multi-source-of-truth between
   `.mzn` / `.md` / `.py`, and the dual-conftest BLS state are all
   integration choices that the technique itself doesn't require —
   they are how this directory wires into the rest of `tests/`,
   not how it does its work.

The rest of the project's testing surface is heavy on
`tests/core/pyspec/...` per-fork pyspec tests and the markdown→
yield→YAML pipeline that consumes them. The compliance runners are
the one branch that takes a different path, and that branch's debt
is mostly orthogonal to the rest of the audit.

## What fixing it would entail

The mission is to **preserve the constraint-solver test synthesis —
the generator, the MiniZinc models, the runner, the YAML
event-vector format — and fix only the integration surface around
them.** None of the steps below replaces the technique; each one
brings the seams between the technique and the rest of the test
framework into line with how the rest of the project is structured.

A sketch (not a design):

1. **Decide on the directory's promise.** Either rename
   `compliance_runners/` to `fork_choice_compliance/` (admit there's
   one runner) and inline `gen_base/` into it, *or* commit to
   building the second runner that justifies the plural and the
   `gen_base/` framework. Speculative Generality dies either way.
2. **Make the scenario format a typed Python model.** A Pydantic
   `BlockTreeScenario`, `BlockCoverScenario`, `SMLinksScenario`
   that the MiniZinc layer populates and the runner consumes.
   `tests/formats/fork_choice/README.md` becomes a generated
   document or a thin pointer to the model. The MiniZinc constraint
   models stay (they're the *valid topology* spec) but emit values
   typed against the model rather than untyped dicts.
3. **Replace `mutation_operators.py:55–63`'s string dispatch with
   an enum or a registry.** New mutations register; unknown kinds
   fail at construction.
4. **Read the manifest.** `runner/test_run.py` should consume the
   `meta.yaml` the generator already writes, eliminating the glob
   patterns and the `get_prefix` hack.
5. **Validate `test_gen.yaml`.** A Pydantic model for
   `TestGenConfig` with field validators for `test_type`,
   `instances`, `nr_variations`, etc. Misnamed keys fail at load
   time, not at solve time.
6. **Document the BLS asymmetry explicitly.** A single named fixture
   (`bls_for_generator` / `bls_for_runner`) that both modes opt into,
   with a docstring stating the design intent. Or a marker
   (`@pytest.mark.bls_mode("on" | "off")`) that the conftest
   inspects.
7. **Sort out the `sample_*.yaml` files.** Either move them to
   `examples/` (intent: documentation), to `tests/test_generator/`
   (intent: tests of the generator), or delete them.
8. **Drop the `noqa: E402` import-order constraint.** If
   `enumerate_test_groups`' generator-mode dependency is real, push
   it down to the function level (`from .instantiators.test_case
   import enumerate_test_groups` inside `pytest_generate_tests`)
   rather than at module top-level.

The full fix is small relative to the rest of the audit — most of
it is local to `compliance_runners/`. Steps 2 and 6 cross-reference
[decorator-stack.md](decorator-stack.md)'s pytest-plugin rework
because the dual-mode flag in `context.py` is what makes
`configure_generator_context()` necessary in the first place.

**Pytest-plugin / fixture angle.** Several of the smells are
fixture-shaped:

- The BLS-on / BLS-off split (step 6) is a parameterised fixture
  with two values. Tests opt in via `@pytest.mark.parametrize`
  (indirect) or via a session-scoped fixture in each conftest.
- The `prepare_bls()` autouse fixture and its mirror disable are
  what pytest's fixture system models natively.
- The runner's `--test-dir` / `--start` / `--limit` CLI options
  (`runner/conftest.py:8–28`) are an ad-hoc parametrisation that a
  pytest fixture parameterising over `test_info` tuples (already
  declared at `runner/test_run.py:60–66`) makes more discoverable.
- The Stringly-Typed mutation dispatch at
  `mutation_operators.py:55–63` is not pytest-shaped — that's
  application code. But once mutations are typed, a fixture that
  parametrises over `MutationKind` can drive both unit tests of the
  mutation operators and the generator's variation loop, removing
  the duplication between the test layer and the generator layer.

Most of the integration smells dissolve if the
[decorator-stack.md](decorator-stack.md) plugin rework lands first
— the `is_generator` flag goes away, the import-order side-effect
goes away, and `configure_generator_context()` becomes
unnecessary.

## References

Related guides:
- [markdown-as-source-of-truth.md](markdown-as-source-of-truth.md)
  — covers the markdown half of the three-source-of-truth problem;
  this report covers the MiniZinc half.
- [build-orchestration.md](build-orchestration.md) — the `make
  comptests` recipe is a sibling of the main `make test` recipe;
  same Long Method pattern.
- [decorator-stack.md](decorator-stack.md) — the
  `is_pytest`/`is_generator` flags that `configure_generator_context()`
  manipulates live in `tests/core/pyspec/.../test/context.py`;
  fixing them there fixes the import-order fragility here.
- [fork-registration.md](fork-registration.md) — the YAML
  behaviour flags (`with_attester_slashings`, `with_invalid_messages`)
  are part of the project's broader N-place pattern.

External references:

- Fowler, *Refactoring* (1999) — Speculative Generality (p. 109),
  Stringly Typed (sub-form), Inappropriate Intimacy (p. 85),
  Comments-as-Deodorant (p. 87).
- Hunt & Thomas, *The Pragmatic Programmer* — Tip 11 (DRY), Tip 12
  ("Don't gold-plate"), Tip 17 (Eliminate effects between unrelated
  things), Tip 38 ("Configure, don't integrate").
- Beck, *Test-Driven Development* (2002) — FIRST tests, especially
  Self-validating.
- de Kleer & Williams, "Diagnosing multiple faults" (1987) —
  background on constraint-based reasoning that motivates
  MiniZinc-style approaches; cited because the *technique* used
  here is sound and the deep-dive should not dismiss it.
