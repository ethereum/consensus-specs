# consensus-specs — static analysis config (deep-dive)

`consensus-specs/pyproject.toml` reads, on first scan, like a serious
commitment to static analysis: strict mypy directives, a Pylint family
selected in ruff, a pinned toolchain. On second reading it is the
opposite — every strict knob has a release valve next to it, and the
release valves are the things that are actually in force. The
combination of `ignore_missing_imports = true`, the minimal ruff
selection, and the silenced `PLR09xx` complexity rules makes the
typing/lint surface largely ceremonial. Most of the failure modes
catalogued in the adjacent guides — primitive-obsession in helpers,
decorator stacks, dual-mode context flags — would be partly caught
by stricter typing. Fixing the config is a force multiplier on every
other finding.

Adjacent guides:
[helper-layer.md](helper-layer.md) (most of the helper-layer's
primitive-obsession smells would be partly caught by stricter
typing),
[decorator-stack.md](decorator-stack.md) (pytest markers, currently
undeclared, would replace some of the decorator ordering rules),
[directory-structure.md](directory-structure.md) (`pythonpath =
["."]` is in this same `pyproject.toml` block).

## The shape of the problem

`pyproject.toml` declares strict mypy on lines 65–69 and then on line
70 turns the strictness off for any code that touches an untyped
third-party import — which, given that `eth-remerkleable`, `lru-dict`,
`milagro_bls_binding`, `py_arkworks_bls12381`, `marko`, `ruamel.yaml`,
and most of the `pytest-*` plugins ship without `py.typed`, is most
of the codebase. It then declares a ruff selection that *omits* the
rule families that would have caught the helper-layer's ergonomic
defects (`E`, `W`, `B`, `A`, `N`, `D`, `C4`, `ARG`, `SIM`, `RET`,
`TRY`, `RUF`, `PT`) and *includes* the Pylint family — and then
silences the four `PLR09xx` complexity rules whose firing is the
loudest signal that helpers like `is_post_*`, `with_state_list`, and
the test_run runners need redesign. The pytest config has no
`markers`, no `--strict-markers`, no `addopts`. The dependencies are
pinned to exact versions in three flat extras groups; there is no
`[dependency-groups]` (PEP 735) and no `[tool.uv]` block despite the
project shipping `uv.lock`. Renovate, finally, explicitly disables
Python upgrades on a Python project (`renovate.json:8–11`).

The effect is a configuration file whose stated discipline and
actual discipline disagree by two orders of magnitude. Fowler calls
configuration that contradicts itself a Comments-as-Deodorant smell
(*Refactoring*, 1999): the strict directives serve as decoration,
not enforcement.

## Proof, by line

The whole `pyproject.toml` static-analysis surface is reproducible
in 40 lines:

```toml
# pyproject.toml:60–70 (pytest + mypy)
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.mypy]
disallow_incomplete_defs = true
disallow_untyped_defs = true
warn_unused_ignores = true
warn_unused_configs = true
warn_redundant_casts = true
ignore_missing_imports = true        # <-- defeats every line above

# pyproject.toml:72–95 (ruff)
[tool.ruff]
line-length = 100
namespace-packages = ["scripts"]
src = ["."]

[tool.ruff.lint]
select = ["F", "I", "INP", "PL", "UP"]
ignore = [
  "PLR0911",  # too-many-return-statements
  "PLR0912",  # too-many-branches
  "PLR0913",  # too-many-arguments
  "PLR0915",  # too-many-statements
  "PLR1714",  # repeated-equality-comparison
  "PLR2004",  # magic-value-comparison
  "PLW0128",  # redeclared-assigned-name
  "PLW0603",  # global-statement
  "PLW2901",  # redefined-loop-name
]

[tool.ruff.lint.isort]
combine-as-imports = true
known-first-party = ["eth_consensus_specs"]
order-by-type = false
```

That is the static-analysis policy declared in `pyproject.toml`.
`codespell` is also invoked from `make lint` (`Makefile:280`) but
runs with defaults — no `[tool.codespell]` block exists. The ruff
formatter inherits `line-length = 100` from the parent `[tool.ruff]`
block; no explicit `[tool.ruff.format]` options are set.

Two configurations are absent that would catch existing
audit-cited findings on their own merit:

- **An `[tool.ruff.lint.mccabe]` cyclomatic-complexity cap** —
  overlaps with the silenced `PLR0912` (too-many-branches) rule
  and surfaces the helper-layer's `is_post_<fork>` cascades and
  `with_state_list` / test-run runner branching that
  [helper-layer.md](helper-layer.md) enumerates by hand. The
  mccabe cap automates that detection without the noise of the
  other PLR09xx rules the team has explicitly silenced.
- **`vulture` dead-code detection** — surfaces unused functions
  and classes in files like `helpers/shard_block.py` (91 lines of
  orphaned phase-1 implementation), which the audit catalogues by
  hand in [secondary-findings.md](../secondary-findings.md).
  Configuring vulture moves this class of finding from review-time
  discovery to automated enforcement.

Three further configurations are conditional or lower-priority: a
`[tool.codespell]` block would let the project customize `skip`
patterns and an `ignore-words-list` if the project vocabulary
clashes with codespell's typo dictionary as it grows;
`[tool.ruff.format]` options matter mainly for stable formatter
behaviour across ruff version bumps (lower priority since
`uv.lock` pins ruff); a pydocstyle convention is lower priority
for a project whose canonical spec is markdown rather than
docstrings.

Compare with `execution-specs/pyproject.toml:372–500` (Comparable
contrast section below) to see how a spec-comparable repo
configures these same surfaces.

## Critique / inventory

### Type checking — `[tool.mypy]:64–70`

`pyproject.toml` declares `disallow_untyped_defs = true` and
`disallow_incomplete_defs = true` on lines 65–66. Taken at face
value, the project's own standard is that every function in the
codebase must have annotations on every parameter and return.
`warn_unused_ignores` (line 67) and `warn_redundant_casts` (line
69) add: dead `# type: ignore` comments and pointless `cast()`
calls are errors. These together are the canonical "strict mypy"
posture; they match `execution-specs/pyproject.toml:477–478,
:480` and the intent of leanSpec's `error-on-warning = true`
(`leanSpec/pyproject.toml:85`).

#### What mypy actually checks

The Makefile (`Makefile:272–288`) builds the mypy invocation as:

```makefile
MYPY_PACKAGE_BASE := $(subst /,.,$(PYSPEC_DIR:$(CURDIR)/%=%))
MYPY_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), -p $(MYPY_PACKAGE_BASE).eth_consensus_specs.$S)
...
@output="$$($(UV_RUN) mypy $(MYPY_SCOPE) 2>&1)" || { echo "$$output"; exit 1; }
```

`MYPY_SCOPE` expands to one `-p` flag per executable spec name —
`-p tests.core.pyspec.eth_consensus_specs.phase0`,
`-p ...altair`, and so on. Running `make lint` therefore invokes
mypy on **six source files**: `minimal.py` and `mainnet.py` for
each of the three forks currently in `ALL_EXECUTABLE_SPEC_NAMES`.
Result: "Success: no issues found in 6 source files".

Running mypy on the rest of the Python tree with
`--explicit-package-bases` (necessary to bypass the
self-referential-package-layout discovery issue — see below)
surfaces the gap between the declared standard and the code:

| Tree | Errors today | In `MYPY_SCOPE`? |
|---|---:|---|
| `tests/core/pyspec/.../test/helpers/` (legacy helper layer) | 503 errors in 47 files | no |
| `tests/infra/` (in-progress framework migration) | 302 errors in 33 files | no |
| `pysetup/` (markdown→Python extractor) | 59 errors in 14 of 19 files | no |
| `scripts/` (standalone utilities) | 13 errors in 4 of 6 files | no |
| Generated per-fork spec packages | 0 errors in 6 files | **yes** |
| **Total** | **~877 errors across ~98 files** | |

**By the project's own `disallow_untyped_defs = true` standard,
those ~877 are tech debt.** They don't surface because
`MYPY_SCOPE` exempts them.

#### The self-referential-package-layout blocks mypy traversal

Expanding `MYPY_SCOPE` to include the helpers isn't a simple
edit. The package source lives inside the test tree
(see [self-referential-package-layout.md](self-referential-package-layout.md)),
so the same files are reachable under two dotted names. mypy
refuses to proceed:

```
$ uv run mypy tests/core/pyspec/eth_consensus_specs/test/helpers/
tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_impl.py: error: Source file found twice under different module names: "eth_consensus_specs.test.helpers.churn" and "tests.core.pyspec.eth_consensus_specs.test.helpers.churn"
tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_impl.py: note: See https://mypy.readthedocs.io/en/stable/running_mypy.html#mapping-file-paths-to-modules for more info
tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_impl.py: note: Common resolutions include:
tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_impl.py: note:     a) adding `__init__.py` somewhere,
tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_impl.py: note:     b) using `--explicit-package-bases` or adjusting `MYPYPATH`
Found 1 error in 1 file (errors prevented further checking)
```

`--explicit-package-bases` is the documented workaround, but the
underlying issue is structural: the package layout makes the type
checker's discovery ambiguous before any annotation work begins.
The typing gap and the package-layout gap reinforce each other —
even if a maintainer wanted to start annotating the helpers, mypy
can't traverse them under the current setup.

#### Why the six-file slice passes — the `Any`-propagation interaction

Within the six files that *are* checked, the strict directives
pass cleanly only because `ignore_missing_imports = true` (line
70) silences most of the third-party surface. The mechanism is
worth understanding because removing the scope restriction
without addressing this would still leave the directives weakened
on the broader surface.

When mypy imports a module that ships *without a `py.typed` marker*
(the file in a package's root that says "this library has type
stubs the checker should trust") it normally errors:

```
Skipping analyzing 'foo': module is installed, but missing library
stubs or py.typed marker.
```

With `ignore_missing_imports = true`, mypy silently treats the
import as `Any` and proceeds. In this codebase, "untyped
third-party imports" covers most of what tests touch:
`eth-remerkleable` (the SSZ container library), `lru-dict`,
`milagro_bls_binding`, `py_arkworks_bls12381`, `marko`,
`ruamel.yaml`, and most `pytest-*` plugins. None ship
`py.typed`. Once one of them is imported, `Any` is in the file —
and `Any` propagates: every expression that touches it returns
`Any`, every parameter that comes from one is `Any`, every
return type that traces back to one is `Any`.

A worked example shows the mechanism:

```python
from eth_remerkleable import Container   # untyped → Container is Any

def build_state(spec: Spec, validators: list) -> BeaconState:
    # `spec` and `BeaconState` both originate from untyped imports;
    # both are Any to mypy, regardless of how they're spelled here.
    s = spec.BeaconState(validators=validators)   # s: Any
    return s.do_anything().you.want()             # also Any
```

`disallow_untyped_defs` looks at this signature and is satisfied —
every parameter and the return are annotated. The body operates on
`Any` end-to-end; the type checker has nothing concrete to reason
about. The rule fires green; the rule's intent is unmet.

Each of the four strict directives above line 70 reaches the same
outcome, slightly differently:

- **`disallow_untyped_defs` (line 66)** still fires on functions
  with no annotations at all. Vacuous on functions whose
  annotations are `Any` (or transit through untyped imports
  to `Any`) — which is most of the helper layer.
- **`disallow_incomplete_defs` (line 65)** still fires when some
  parameters are annotated and others aren't. Vacuous on the same
  surface for the same reason.
- **`warn_unused_ignores` (line 67)** fires when a `# type: ignore`
  covers a line that would type-check anyway. When the line's
  expressions are `Any`, mypy cannot reliably tell whether the
  line is correct on its own or whether `Any` is masking an
  error; the warning becomes a flapping signal — see the second
  consequence below.
- **`warn_redundant_casts` (line 69)** fires on `cast(T, x)` where
  `x` is already known to be `T`. When `x` is `Any`, mypy cannot
  tell whether the cast does anything (`Any` is compatible with
  every target type), so the warning never triggers, and casts
  that would be redundant *in a typed world* sit invisible.

The directives are still on. They fire on the vanishing minority
of code where every type is concrete and never transits an
untyped import — which, in practice, is the small surface where
the codebase needs them least.

Two consequences worth naming:

- **`disallow_untyped_defs` is enforced against a frontier that doesn't
  exist.** In practice every helper in `tests/core/pyspec/eth_consensus_specs/test/helpers/`
  takes a `spec` argument and a `state` argument — both untyped at the
  module boundary because the generated spec module has no public
  stubs and `eth-remerkleable` has no stubs. So every helper's
  signature is `def foo(spec, state, ...) -> None` and mypy is happy
  with that because both `spec` and `state` are `Any`. The whole
  helper-layer Primitive Obsession surface
  ([helper-layer.md](helper-layer.md)) is invisible to the type
  checker by configuration.
- **`warn_unused_ignores` on a codebase with no real type errors
  produces phantom signal.** When `Any` propagates everywhere, almost
  no `# type: ignore` is needed, so this rule fires on the few legacy
  ignores left over and creates a flapping signal that maintainers
  quickly route around. Hunt & Thomas, *The Pragmatic Programmer*,
  Tip 50 ("Don't use wizard code you don't understand"): a config
  block whose rules contradict each other trains readers to ignore
  the file.

`pyproject.toml` has no `mypy_path`, `files`, or `plugins` keys.
The check's scope is whatever the Makefile passes — currently the
six-file `-p phase0 -p altair -p ...` invocation analysed above.
Compare to execution-specs lines 484–485:

```toml
mypy_path = ["src", "packages/testing/src", "packages/testing/stubs"]
files = ["src", "tests", "packages"]
```

…which both *targets* the check and *makes shadow stubs available*.
consensus-specs has neither: no `stubs/` directory, and no
`pyproject.toml`-declared scope that would survive a change of
caller. Closing the ~877-error gap means three coordinated moves:
expand `MYPY_SCOPE` (or declare `files` directly in
`pyproject.toml`), unblock mypy's traversal by addressing the
self-referential-package-layout issue, and replace
`ignore_missing_imports = true` with selective per-module overrides
plus locally-shipped stubs for the half-dozen libraries that ship
without `py.typed`.

### Lint — `[tool.ruff.lint]:78–95`

The selection is `F`, `I`, `INP`, `PL`, `UP`. Spelled out:

- `F` — pyflakes (real errors: undefined name, unused import).
- `I` — isort (import sorting).
- `INP` — flake8-no-pep420 (`__init__.py` presence; weakly relevant
  because the project's package layout is non-standard, see
  [self-referential-package-layout.md](self-referential-package-layout.md)).
- `PL` — Pylint (a wide family) — partly silenced again on lines 85–95.
- `UP` — pyupgrade (modernise syntax).

The families *not* selected, with their cost:

| Family | What it catches | Where it would have fired |
|---|---|---|
| `E`, `W` | pycodestyle errors / warnings | Style and indentation in helpers |
| `B` | flake8-bugbear | Common bug patterns: mutable default args, function calls in default args, useless expressions |
| `A` | flake8-builtins | Shadowing `id`, `type`, `list` — a common pattern in spec helpers |
| `N` | pep8-naming | Helper names that don't match Python convention (relevant given the spec uses Python and the markdown both) |
| `D` | pydocstyle | Docstring presence and shape — the helpers have almost no docstrings |
| `C4` | flake8-comprehensions | Unnecessary generators, list-of-set comprehensions |
| `ARG` | flake8-unused-arguments | Pytest fixtures left in helper signatures |
| `SIM` | flake8-simplify | `if x: return True else: return False` patterns the helpers contain |
| `RET` | flake8-return | Inconsistent `return` shapes — a recurring helper smell |
| `TRY` | tryceratops | Exception-handling errors |
| `RUF` | ruff-native | Various; `RUF005` (concat) is common |
| `PT` | flake8-pytest-style | Pytest idioms: marker shape, fixture scope, parametrize style — directly relevant |

In particular, `PT` would have caught the unregistered custom markers
flagged in §9 — `@pytest.mark.<something>`
firings against an empty `markers` list.

execution-specs selects ten families (`E`, `F`, `B`, `W`, `I`, `A`,
`N`, `D`, `C4`, `ARG` — `execution-specs/pyproject.toml:377–388`) and
adds an mccabe cap of 7 (line 436). leanSpec selects nine (`E`, `F`,
`B`, `W`, `I`, `A`, `N`, `D`, `C` — `leanSpec/pyproject.toml:67`) and
configures the formatter (lines 63–64) and pydocstyle convention (lines
71–72). consensus-specs selects five families and configures neither.

### Complexity-silencing — `[tool.ruff.lint]:85–95`

The `ignore` list is the single most diagnostic-rich block in the
file. Each entry maps to a specific design problem the project has
chosen not to surface:

- `PLR0911` — too-many-return-statements. Fires on the multi-branch
  `is_post_*` ladders and the `with_state_list` filter chain.
- `PLR0912` — too-many-branches. Fires on the long `if spec.fork
  == ...:` chains throughout helpers.
- `PLR0913` — too-many-arguments. Fires on every test-builder helper
  with more than five parameters (every helper in
  `tests/core/pyspec/eth_consensus_specs/test/helpers/attestations.py`).
- `PLR0915` — too-many-statements. Fires on the long state-prep
  helpers in `helpers/genesis.py` and `helpers/rewards.py`.
- `PLR1714` — repeated-equality-comparison. Fires when code writes
  `x == "minimal" or x == "mainnet"` rather than a set check.
- `PLR2004` — magic-value-comparison. Fires on the spec-constants in
  helpers (debatable — this one is reasonably silenced for spec code).
- `PLW0128` — redeclared-assigned-name. Fires on the `_orig = orig;
  orig = cache_this(...)` shadow pattern documented in
  [ad-hoc-caching.md](ad-hoc-caching.md). The shadow is the smell;
  silencing the rule hides it.
- `PLW0603` — global-statement. Fires on the eight module-global
  caches catalogued in [ad-hoc-caching.md](ad-hoc-caching.md).
- `PLW2901` — redefined-loop-name. Fires on `for x in xs: x = ...`
  shadowing inside the helpers' state-preparation loops.

Six of the nine ignores correspond directly to findings in
[ad-hoc-caching.md](ad-hoc-caching.md), [helper-layer.md](helper-layer.md),
or [decorator-stack.md](decorator-stack.md). The lint config is
documenting where the design problems are by enumerating the noise
they produce — Fowler, *Refactoring* (1999), p. 87: "Comments are
often used as a deodorant" — and then turning the alarm off rather
than addressing the smell. Hunt & Thomas, *The Pragmatic Programmer*,
Tip 17 ("Eliminate effects between unrelated things"): silencing a
rule because *one* helper trips it makes the rule unable to flag
*new* helpers that trip it for the same design reason.

### Pytest — `[tool.pytest.ini_options]:60–62`

Three lines:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

What is missing:

- **No `markers`.** Every `@pytest.mark.<name>` in the test suite is
  unregistered. Pytest emits `PytestUnknownMarkWarning` at collection,
  which is silently swallowed because `filterwarnings` is also unset.
  The decorator-stack deep-dive ([decorator-stack.md](decorator-stack.md))
  catalogues the markers used (`with_all_phases`, `spec_state_test`,
  …) — none of them is declared here, none of them is validated, and
  a typo in any of them is silently a no-op.
- **No `--strict-markers`.** Without this, the warning above doesn't
  even fail CI. The unregistered-marker problem is invisible by
  construction.
- **No `addopts`.** No `-ra`, no `--cov`, no `--cov-branch`, no
  `--strict-markers`, no `--strict-config`, no timeout. Coverage is
  only on if a developer remembers to type the flag.
- **No `filterwarnings`.** Deprecation warnings from third-party
  packages — and there are many, given the pinned-everything
  dependencies — appear in test output as noise rather than as
  errors. Real deprecations from the spec's own code (like the
  `datetime.utcnow()` usages catalogued in §8 of the broader audit
  report) hide in the same noise.
- **No `minversion`.** The pinned `pytest==9.0.3` (line 37) covers
  this in practice, but a fresh checkout that pins-relax (e.g. via
  CI override) loses the minimum.

execution-specs registers nine markers (`pyproject.toml:287–297`).
leanSpec registers four markers, sets `--strict-markers`, sets
`--cov=src --cov-branch`, sets `asyncio_mode = "auto"`, sets `timeout
= 300` (`pyproject.toml:92–115`). consensus-specs sets two keys.

### Dependency management — `[project]:13–24`, `[project.optional-dependencies]:26–58`

Every direct dependency is pinned with `==` to an exact version. That
pattern continues in the three flat optional-dependencies groups
(`test`, `lint`, `docs`) — `ckzg==2.1.7`, `mypy==1.20.2`,
`ruff==0.15.12`, etc.

Specific issues:

- **`==`-pinning at the library level is wrong-shaped for a library
  that other projects depend on.** A consumer that uses
  `eth-consensus-specs` and also uses `pytest>=9.1` cannot resolve.
  The execution-specs equivalent uses ranges (`pytest>=8,<9`,
  `pycryptodome>=3.22,<4` — `execution-specs/pyproject.toml:23, :205`),
  and leanSpec does the same (`pytest>=8.3.3,<9` —
  `leanSpec/pyproject.toml:140`). consensus-specs is shipped as a
  PyPI package (`name = "eth-consensus-specs"`, line 5), which makes
  the `==` pinning a downstream-resolution hazard rather than just an
  internal-build choice.
- **The three groups are flat.** `lint` includes `mypy` and `ruff`;
  `test` includes `pytest` and friends; `docs` includes
  `mkdocs-material` and friends. There is no `dev` aggregation.
  Anyone wanting "everything for development" runs three installs.
  execution-specs uses PEP 735 `[dependency-groups]` with explicit
  `include-group` aggregation (`execution-specs/pyproject.toml:203–260`)
  and a single `dev` group that pulls in `test`, `lint`, `actionlint`,
  `doc`, and `mkdocs`. leanSpec does the same
  (`leanSpec/pyproject.toml:138–170`).
- **`[project.optional-dependencies]` rather than `[dependency-groups]`.**
  PEP 735 (accepted October 2024) adds `[dependency-groups]` for
  exactly this case — install-time-only groups that are not part of
  the published distribution metadata. consensus-specs uses the
  pre-PEP-735 shape; both comparables use the modern shape. The
  pre-PEP-735 shape leaks lint and test deps into the published
  package's metadata.
- **Pinned setuptools in dependencies.** `setuptools==82.0.1` at line
  23 — a *runtime* dependency. setuptools is not a runtime dependency
  for any code in `tests/`; this is a build-time tool that has been
  miscategorised. (It also appears in `[build-system]` requires at
  line 2, which is correct.)

### `[tool.uv]` and Renovate — absence and contradiction

- **No `[tool.uv]` block.** The repo ships `uv.lock` (visible at the
  repo root in directory listings) but the toml has no `[tool.uv]`,
  no `[tool.uv.workspace]`, no `[tool.uv.sources]`. Both comparables
  configure uv: `execution-specs/pyproject.toml:502–510` (`required-version`,
  `extra-build-dependencies`, `[tool.uv.workspace]`, `[tool.uv.sources]`)
  and `leanSpec/pyproject.toml:128–136` (`required-version`,
  workspace, git source). consensus-specs has the lockfile but not
  the policy that produces it. A maintainer running a fresh `uv sync`
  has no `required-version` floor and no documented workspace shape.
- **Renovate disables Python upgrades — `renovate.json:7–10`.**

  ```json
  {
    "matchDepNames": ["python"],
    "enabled": false
  }
  ```

  …on a project where `[project.requires-python]` is `>=3.11, <3.15`
  (line 11) and the dependencies are all `==`-pinned. The two
  decisions multiply: the toolchain version range is wide, the
  upgrade machinery for that range is off, and the dependency
  versions never move because Renovate is the only thing that would
  move them and it's been told to leave Python alone. Hunt & Thomas
  Tip 11 (DRY): the policy is split between two files that disagree.
- **`.gitignore` per-fork ignores —
  `consensus-specs/.gitignore:18–27`.** Tangential to static analysis
  but worth a mention in the same survey: every fork directory is
  enumerated by hand (`phase0/`, `altair/`, `bellatrix/`, …,
  `eip*/`). When a new fork is added, this file is one of *seven*
  places the maintainer must remember to edit (the others are
  catalogued in [self-referential-package-layout.md](self-referential-package-layout.md)).
  Enumeration-where-a-pattern-would-do is a Speculative Generality
  inverse: too-specific configuration that ages with the project.

## Named anti-patterns

- **Comments-as-Deodorant** (Fowler, *Refactoring*, 1999, p. 87) —
  the strict mypy directives on lines 65–69 read as a comment that
  documents intent without enforcing it. The next line (70) negates
  them.
- **Speculative Generality** (Fowler, p. 109) — the wide
  `requires-python = ">=3.11, <3.15"` range covers four Python
  minor versions while the project is `==`-pinned and CI runs one
  version. Three of the four versions are theoretical.
- **Dead Code** (Fowler, p. 95) — `disallow_untyped_defs = true` is
  dead by construction when `ignore_missing_imports = true` makes
  most function boundaries `Any`. `warn_unused_ignores = true` is
  dead because there are few real ignores.
- **Magic Suppression** — the nine entries on lines 85–95 silence
  rules without explaining *which* legacy code requires the
  suppression. A `per-file-ignores` block (which execution-specs uses
  at lines 409–432) at least scopes the suppression to identifiable
  legacy. consensus-specs suppresses globally.
- **Configure-don't-integrate** (Hunt & Thomas, *The Pragmatic
  Programmer*, Tip 38) — the contract that "this codebase has type
  checking" is announced in `pyproject.toml` but not integrated with
  reality (no stubs path, no `files` scope, no per-file overrides for
  the genuinely-untyped surface). The announcement and the integration
  are different things.
- **Don't write a comment when you can express it in code** (Martin,
  *Clean Code*) — the silenced `PLR09xx` rules are comments that say
  "we know our helpers are too long". Expressing it in code would be
  reducing the helpers; suppressing the rules merely comments on the
  problem.
- **Wizard-Code-You-Don't-Understand** (Hunt & Thomas, Tip 50) — the
  `disallow_*` directives next to `ignore_missing_imports` look like
  a copy-paste from a "strict mypy" recipe; the contradiction
  suggests the recipe was applied without reading what each line does.

## Comparable contrast

Side-by-side; consensus-specs (left), execution-specs (centre),
leanSpec (right). Lines are quoted from the actual files.

### Mypy

```
# consensus-specs/pyproject.toml:64–70
[tool.mypy]
disallow_incomplete_defs = true
disallow_untyped_defs = true
warn_unused_ignores = true
warn_unused_configs = true
warn_redundant_casts = true
ignore_missing_imports = true     # negates the four lines above
```

```
# execution-specs/pyproject.toml:474–500
[tool.mypy]
namespace_packages = true
strict_optional = true
disallow_incomplete_defs = true
disallow_untyped_defs = true
strict_bytes = true
warn_unused_ignores = true
warn_unused_configs = true
warn_redundant_casts = true
ignore_missing_imports = false    # opposite stance
mypy_path = ["src", "packages/testing/src", "packages/testing/stubs"]
files = ["src", "tests", "packages"]
exclude = [...]
plugins = ["pydantic.mypy"]
```

```
# leanSpec/pyproject.toml:81–85 (uses ty rather than mypy)
[tool.ty.environment]
python-version = "3.12"
[tool.ty.terminal]
error-on-warning = true
```

execution-specs explicitly *disables* `ignore_missing_imports` and
provides a stubs path for the surface that needs it. leanSpec uses
ty with `error-on-warning`, which is a single-knob equivalent of the
strictness that execution-specs assembles by hand.

### Ruff

```
# consensus-specs/pyproject.toml:78–95
select = ["F", "I", "INP", "PL", "UP"]
ignore = [
  "PLR0911", "PLR0912", "PLR0913", "PLR0915",
  "PLR1714", "PLR2004", "PLW0128", "PLW0603", "PLW2901",
]
# (no [tool.ruff.format], no per-file-ignores, no mccabe cap)
```

```
# execution-specs/pyproject.toml:377–388, :434–436
select = ["E", "F", "B", "W", "I", "A", "N", "D", "C4", "ARG"]
fixable = ["E", "F", "B", "W", "I", "D"]
ignore = [
  "C401", "C408", "D107", "D200", "D203", "D205", "D212", "D401",
]
[tool.ruff.lint.mccabe]
max-complexity = 7
# plus per-file-ignores at lines 409–432
```

```
# leanSpec/pyproject.toml:60–69
[tool.ruff]
line-length = 100
[tool.ruff.format]
docstring-code-format = true
[tool.ruff.lint]
select = ["E", "F", "B", "W", "I", "A", "N", "D", "C"]
fixable = ["I", "B", "E", "F", "W", "D", "C"]
ignore = ["D205", "D203", "D212", "D415", "C901", "A005", "C420"]
```

Both comparables select the `B` (bugbear), `N` (naming), `D`
(pydocstyle), `A` (builtins), and `C/C4` (comprehensions /
complexity) families. consensus-specs selects none of them.
execution-specs caps mccabe at 7; consensus-specs has no mccabe
configuration but silences four PLR complexity rules instead — the
opposite stance.

### Pytest

```
# consensus-specs/pyproject.toml:60–62
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```
# execution-specs/pyproject.toml:286–297
[tool.pytest.ini_options]
markers = [
    "slow: ...",
    "bigmem: ...",
    "evm_tools: ...",
    "json_blockchain_tests: ...",
    "json_state_tests: ...",
    "vm_test: ...",
    "eels_base_coverage: ...",
    "repricing: ...",
    "stub_parametrize: ...",
]
```

```
# leanSpec/pyproject.toml:87–115
[tool.pytest.ini_options]
minversion = "8.3.3"
testpaths = ["tests"]
python_files = "test_*.py"
pythonpath = ["."]
addopts = [
    "-ra", "--strict-markers",
    "--cov=src", "--cov-report=term-missing", "--cov-report=html",
    "--cov-branch",
    "--ignore=tests/consensus", "--ignore=tests/execution",
    "--ignore=tests/interop",
]
markers = [
    "slow: ...", "valid_until: ...", "interop: ...", "num_validators: ...",
]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
timeout = 300
```

leanSpec's pytest block is twenty lines that *enforce* a contract.
consensus-specs has three lines that announce file locations and
nothing else. The decorator-stack deep-dive
([decorator-stack.md](decorator-stack.md)) shows the project has a
substantial set of custom pytest markers — none of them registered
here, none of them validated.

### Dependency groups

```
# consensus-specs/pyproject.toml:26–58
[project.optional-dependencies]
test = [ "ckzg==2.1.7", "deepdiff==9.0.0", ..., "pytest==9.0.3", ... ]
lint = [ "codespell==2.4.2", ..., "mypy==1.20.2", "ruff==0.15.12" ]
docs = [ "mdx-truly-sane-lists==1.3", ..., "mkdocs==1.6.1" ]
```

```
# execution-specs/pyproject.toml:203–260
[dependency-groups]
test    = [ ... ranges, e.g. "pytest>=8,<9" ... ]
lint    = [ ... ]
actionlint = [ ... ]
doc     = [ ... ]
mkdocs  = [ ... ]
dev = [
    { include-group = "test" },
    { include-group = "lint" },
    { include-group = "actionlint" },
    { include-group = "doc" },
    { include-group = "mkdocs" },
    "ethereum-execution[optimized]",
    "psutil>=7.2.2",
]
```

PEP 735 is the modern shape; both comparables use it; consensus-specs
uses the pre-PEP-735 shape with `==` pinning, which leaks dev deps
into the published distribution and makes the project resolution-hostile
for downstream consumers.

### uv

```
# consensus-specs/pyproject.toml — no [tool.uv]
```

```
# execution-specs/pyproject.toml:502–510
[tool.uv]
required-version = ">=0.7.0"
extra-build-dependencies = { ethash = ["setuptools", "cmake>=4.2.1,<5"] }
[tool.uv.workspace]
members = ["packages/*"]
[tool.uv.sources]
ethereum-execution-testing = { workspace = true }
```

```
# leanSpec/pyproject.toml:128–136
[tool.uv]
required-version = ">=0.7.0"
[tool.uv.workspace]
members = ["packages/*"]
[tool.uv.sources]
lean-ethereum-testing = { workspace = true }
lean-multisig-py = { git = "https://github.com/anshalshukla/leanMultisig-py", branch = "devnet4" }
```

consensus-specs ships the lockfile that these blocks produce but
none of the policy that produces it. Hunt & Thomas Tip 11 (DRY)
applies in the negative: the truth about the toolchain lives in
`uv.lock` only, not in any file a human reads first.

## Why this is load-bearing

Most of the design defects catalogued in adjacent deep-dives are
*detectable* by stricter typing or fuller lint, and the catalogued
defects fall into three buckets:

1. **Caught by stricter typing.** The dual-mode context flags (§1 of
   the broader audit catalogue — flags whose meaning depends on which
   call site they reach) would surface as type confusion if helper
   signatures had real types rather than `Any`. The helper-layer's
   primitive-obsession problems
   ([helper-layer.md](helper-layer.md)) — passing raw `int` for slot,
   epoch, validator-index, attestation-index — would surface as
   `NewType` violations the moment the spec module exposed real
   types.
2. **Caught by stricter lint.** The decorator stacks
   ([decorator-stack.md](decorator-stack.md)) would surface as `B`
   and `PT` family findings. The unregistered markers would surface
   as `PT020`. The Primitive Obsession on integer indices would
   surface as `A` (builtin shadowing) and `N` (naming). The eight
   caching mechanisms ([ad-hoc-caching.md](ad-hoc-caching.md)) would
   surface as nine `PLW0603` and `PLW0128` findings — and those
   exact rules are the ones explicitly silenced on lines 92–93.
3. **Caught by stricter pytest config.** The `with_state_list` /
   `with_phases` matrix would emit collection warnings (custom marks)
   that `--strict-markers` would convert into errors. Test pollution
   from the cache layer would surface as `pytest.warns` from
   `filterwarnings`-flagged deprecations.

So fixing this one config defect is a force multiplier: every
adjacent deep-dive's failure mode becomes either machine-detectable
(under stricter lint/type) or test-time-detectable (under stricter
pytest) instead of human-archaeology. The current configuration is a
unique kind of debt because it is *itself* small and contained — 40
lines — but it makes everything else's debt invisible.

## What fixing it would entail

The configuration is quotable in 40 lines and replaceable in roughly
the same number. The work splits into orthogonal tracks:

- **Mypy track.** Flip `ignore_missing_imports` to `false`. Add a
  `stubs/` directory and a `mypy_path` entry. Stub the half-dozen
  third-party packages that lack `py.typed` (small `.pyi` files,
  one per package). Add `files = ["tests/core/pyspec/eth_consensus_specs"]`
  to scope the check. Expect the first run to produce hundreds of
  errors; address them by typing helper signatures.
- **Ruff track.** Add the missing rule families (`E`, `W`, `B`, `A`,
  `N`, `C4`, `ARG`, `SIM`, `RET`, `PT`, `RUF`). Expect the first run
  to produce thousands of findings, most of them autofixable. The
  silenced `PLR09xx` rules can be replaced by an `mccabe.max-complexity`
  cap and a `per-file-ignores` block that scopes the legacy
  helpers — letting the rule fire for *new* code while
  grandfathering existing helpers.
- **Pytest track.** Register every marker the codebase uses. Add
  `--strict-markers`, `--strict-config`, `--cov=tests/core/pyspec/eth_consensus_specs`,
  `--cov-branch`, `-ra`, `filterwarnings = ["error"]`, `timeout = 300`.
  Expect collection-time errors for typo'd markers; fix each.
- **Dependency track.** Migrate `[project.optional-dependencies]` to
  `[dependency-groups]` with `include-group` aggregation. Move
  `setuptools` out of `dependencies`. Replace `==` pinning with
  ranges for runtime dependencies; keep pinning in `lint`/`test`
  groups if developers want it (acceptable there).
- **uv + Renovate track.** Add `[tool.uv]` with `required-version`.
  Re-enable Renovate's Python rule and let it propose minor-version
  bumps; review and accept.

These tracks are independent. The Mypy track is the largest in
absolute work; the Ruff track delivers the highest signal density;
the Pytest track is the smallest and most immediately actionable
(less than a day's work to register markers and add `--strict-markers`).

## References

- Beck, K. *Test-Driven Development by Example*. Addison-Wesley,
  2002. (FIRST tests; pytest configuration is the place that
  enforces Fast / Isolated / Repeatable.)
- Feathers, M. *Working Effectively with Legacy Code*. Prentice Hall,
  2004. (Configuration-as-test-seam: a strict mypy block that
  lies makes the whole codebase a legacy codebase by the book's
  definition — code without effective tests.)
- Fowler, M. *Refactoring: Improving the Design of Existing Code*.
  Addison-Wesley, 1999. Comments-as-Deodorant (p. 87), Speculative
  Generality (p. 109), Dead Code (p. 95).
- Hunt, A.; Thomas, D. *The Pragmatic Programmer*. Addison-Wesley,
  1999. Tip 11 (DRY); Tip 17 (Eliminate effects between unrelated
  things); Tip 38 (Configure, don't integrate); Tip 50 (Don't use
  wizard code you don't understand).
- Martin, R. *Clean Code*. Prentice Hall, 2008. ("Don't write a
  comment when you can express it in code"; SRP applied to config —
  one config block, one purpose.)
- PEP 735 — Dependency Groups in pyproject.toml. Accepted October
  2024. (The shape execution-specs and leanSpec use; the shape
  consensus-specs predates.)

