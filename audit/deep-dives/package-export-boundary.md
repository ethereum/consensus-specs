# consensus-specs — package export boundary (deep-dive)

When someone runs `pip install eth-consensus-specs`, they install a
single distribution that drops **five top-level names** into their
Python environment — `eth_consensus_specs`, `configs`, `presets`,
`specs`, `sync` — and the main package mixes the runtime spec, the
test suite, the test helpers, the debug toolkit, and the spec
utilities behind a single empty `__init__.py`. There is no
`__all__`, no public-API declaration, no documented stable
surface; downstream consumers cannot tell what is "the spec they're
allowed to depend on" versus "the test framework they shouldn't
touch". The four data-only packages collide with generic top-level
names that any other PyPI distribution might claim.

The alternative repos solve this by splitting the runtime from the
test framework into separate distributions. consensus-specs ships
everything as one.

Adjacent guides:
[self-referential-package-layout.md](self-referential-package-layout.md)
(why the package source lives inside the test tree),
[directory-structure.md](directory-structure.md) (the broader layout
that the export boundary inherits from),
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md)
(why the `eth_consensus_specs` runtime is *generated* before
distribution).

## The shape of the problem

`setup.py` declares the wheel; the produced `top_level.txt` (visible
at `consensus-specs/.venv/lib/python3.13/site-packages/eth_consensus_specs-1.7.0a7.dist-info/top_level.txt`)
records exactly what the install lands as Python-importable names:

```
configs
eth_consensus_specs
presets
specs
sync
```

The first four lines are not Python packages in any meaningful
sense — they're directories of YAML or markdown files. setuptools
is being told to *treat* them as packages so `package_data` can
attach files to them, but the result is that anyone who imports any
generic name like `import specs` after installing `eth-consensus-specs`
will resolve it to consensus-specs's bundled YAML directory rather
than to whatever else they expected. The collision surface is real
and not project-namespaced.

The fifth line — `eth_consensus_specs` — is a Python package, but it
is a *very* full package. Its top-level layout is:

```
eth_consensus_specs/
├── __init__.py            ← empty except for VERSION.txt read
├── py.typed               ← PEP 561 marker
├── VERSION.txt
├── phase0/                ← generated runtime spec (per fork)
├── altair/, bellatrix/, capella/, deneb/, electra/, fulu/,
│   gloas/, heze/, eip8025/  (10 forks total)
├── config/                ← config loader (config_util.py)
├── debug/                 ← test-vector helpers (encode/decode/random_value/tools)
├── test/                  ← THE ENTIRE TEST SUITE
│   ├── conftest.py
│   ├── context.py         ← decorator zoo
│   ├── exceptions.py
│   ├── helpers/           ← ~10 000 lines of test helpers
│   ├── utils/
│   ├── phase0/, altair/, …  ← per-fork test_*.py files
│   └── …
└── utils/                 ← bls.py, kzg.py, hash_function.py, ssz/
```

A downstream user installing this package has no way to reach the
runtime spec without also pulling in 10 000 lines of test helpers,
the entire `test/<fork>/` test tree, the test-context decorator
machinery, and the test-vector debug tools. The empty
`__init__.py` exposes everything reachable; the only signal of
intent is the directory naming itself.

The alternative repos make different choices. `execution-specs`
ships **two** distributions (`ethereum-execution` for the runtime,
`ethereum-execution-testing` for the framework). `leanSpec` does
the same (`lean-spec`, `lean-ethereum-testing`). A consumer there
can install just what they need.

## Proof, by line

### `consensus-specs/setup.py` — the kitchen-sink wheel

The whole file is short enough to quote (with comment trimmed):

```python
from setuptools import find_packages, setup

setup(
    include_package_data=False,
    package_data={
        "configs": ["*.yaml"],
        "eth_consensus_specs": ["VERSION.txt"],
        "presets": ["**/*.yaml", "**/*.json"],
        "specs": ["**/*.md"],
        "sync": ["optimistic.md"],
    },
    package_dir={
        "configs": "configs",
        "eth_consensus_specs": "tests/core/pyspec/eth_consensus_specs",
        "presets": "presets",
        "specs": "specs",
        "sync": "sync",
    },
    packages=find_packages(where="tests/core/pyspec") + ["configs", "presets", "specs", "sync"],
    py_modules=["eth_consensus_specs"],
)
```

Three things are unusual:

1. **`packages=find_packages(where="tests/core/pyspec")`** — the
   recursive package discovery walks `tests/core/pyspec/` and
   captures `eth_consensus_specs` plus every subpackage (each fork,
   `test/`, `test/helpers/`, `test/<fork>/<category>/`,
   `debug/`, `config/`, `utils/`, `utils/ssz/`, …). There is no
   `exclude=` filter. The test tree is part of the wheel.

2. **`+ ["configs", "presets", "specs", "sync"]`** — four extra
   "packages" that are *not* Python packages (they have no
   `__init__.py`). They're listed here purely so `package_data` can
   attach their YAML/Markdown files to the wheel. The cost is that
   each becomes an importable top-level name.

3. **`py_modules=["eth_consensus_specs"]`** — declares
   `eth_consensus_specs` as a single-file module *and* as a package
   (it's already in `packages=`). This is a leftover; setuptools
   accepts both but the `py_modules` line is redundant at best,
   actively confusing at worst.

### `consensus-specs/pyproject.toml:11–58` — runtime + test deps mixed

The `[project]` table lists the runtime dependencies:

```
"eth-remerkleable==0.1.30",
"eth-utils==6.0.0",
"frozendict==2.4.7",
"lru-dict==1.4.1",
"marko==2.2.2",
"milagro_bls_binding==1.9.0",
"py_arkworks_bls12381==0.4.1",
"py_ecc==8.0.0",
"ruamel.yaml==0.19.1",
"setuptools==82.0.1",
```

`marko==2.2.2` is the markdown-to-AST library used by `pysetup/`
to build the runtime spec — it is a *build-time* dependency, not a
runtime dependency, but installing the wheel installs it because
the package boundary doesn't separate the two. `setuptools==82.0.1`
is also a build-time dependency that sneaks into the runtime
closure because of the spec-generation pipeline.

`[project.optional-dependencies]` `test`, `lint`, `docs` add the
test framework's deps (pytest, pytest-cov, pytest-html, ckzg,
deepdiff, minizinc, psutil, …). These attach via the *same*
distribution as `pip install eth-consensus-specs[test]` — which is
the canonical way to install a *test framework* whose code is part
of the same package. There's no separate `eth-consensus-specs-testing`
distribution to install instead.

### The wheel's `top_level.txt` records the import collision surface

`consensus-specs/.venv/lib/python3.13/site-packages/eth_consensus_specs-1.7.0a7.dist-info/top_level.txt`:

```
configs
eth_consensus_specs
presets
specs
sync
```

Each line is a top-level Python identifier the install creates. Try
this in a Python session after installing the wheel:

```python
import specs    # consensus-specs's markdown directory
import configs  # consensus-specs's YAML config directory
import presets  # consensus-specs's YAML preset directory
import sync     # consensus-specs's markdown file
```

The names `specs`, `configs`, `presets`, and `sync` are generic to
the point of being *aspirationally common*. Any other distribution
publishing a `specs` package — say, an OpenAPI helper, a
specification-reading library — collides at install time. There is
no namespace prefix; an unsuspecting `from specs import …` lands in
consensus-specs's territory whether the user wanted that or not.

### The `eth_consensus_specs` package has no public-API declaration

`consensus-specs/tests/core/pyspec/eth_consensus_specs/__init__.py`
in full:

```python
# See setup.py about usage of VERSION.txt
import os

with open(os.path.join(os.path.dirname(__file__), "VERSION.txt")) as f:
    __version__ = f.read().strip()
```

That's it. No `__all__`. No re-exports. No docstring describing
what the package is or how to use it. No deprecation markers on
internal-vs-external surfaces. A consumer who wants to import "the
phase0 mainnet spec" has to know that the path is
`eth_consensus_specs.phase0.mainnet` — there is no curated
top-level helper like `from eth_consensus_specs import get_spec("phase0",
"mainnet")`.

The same applies to every sub-package: `eth_consensus_specs.utils.bls`,
`eth_consensus_specs.test.helpers.state`,
`eth_consensus_specs.debug.encode`, etc., are all part of the
public namespace because nothing has been declared internal. The
`test/` subtree — including the entire test infrastructure — is
reachable as `eth_consensus_specs.test.<…>` from any external
consumer.

## Critique

### One distribution mixing five concerns

The `eth_consensus_specs` package contains five things a downstream
consumer could plausibly want, mixed without separation:

1. **The runtime spec** (`phase0/`, `altair/`, …, `eip8025/`) — what
   a reader of `specs/<fork>/beacon-chain.md` actually needs to
   execute. *Possibly* what a client implementer cross-checks
   against. (10 fork-specific subpackages, each with `mainnet.py`
   and `minimal.py`.)
2. **The test suite** (`test/<fork>/<category>/test_*.py`) — the
   pytest test files. ~10 000+ lines. Mostly internal; only
   meaningful in the project's own pytest invocation.
3. **The test helpers** (`test/helpers/`) — ~10 000 lines of
   state-builder, transition-driver, and assertion helpers used
   *exclusively* by the test suite.
4. **The test-vector debug toolkit** (`debug/`) — encode/decode/
   random-value generation used by `@vector_test`. Only useful
   when generating reference test vectors.
5. **Spec-side utilities** (`utils/`) — `bls`, `kzg`,
   `hash_function`, `ssz/` re-exports of `remerkleable`. Possibly
   useful to external consumers who want primitives the spec uses.

A consumer who only wants (1) — the runtime spec — installs all
five. They cannot opt out: no `[runtime-only]` extra,
no separate distribution. They also cannot tell which is which from
the package layout: every concern shares the same empty
`__init__.py`.

This is the textbook **God Package** smell at the distribution
level (Fowler, *Refactoring*, 1999, p. 78, "Large Class" extended
to packages). Hunt & Thomas Tip 17 ("Eliminate effects between
unrelated things") applies — the runtime spec, the test framework,
and the debug toolkit have unrelated lifetimes and should not share
a release cadence or a dependency closure.

### Generic top-level package names with no namespace

`configs`, `presets`, `specs`, and `sync` are not Python packages —
they are directories of YAML and Markdown files that setuptools
treats as packages so `package_data` can attach files to them. The
resulting wheel claims four common nouns as top-level Python
names. Some specific consequences:

- **PyPI-level collision.** Any other distribution publishing a
  `specs` or `configs` package can't be installed alongside
  `eth-consensus-specs` without conflict.
- **Implicit shadowing.** A user's own `specs/` directory in their
  project — a perfectly normal name for application configuration
  or tests — gets shadowed by the installed-package directory in
  search order, depending on `sys.path` order.
- **No prefix.** `eth_consensus_specs.configs.mainnet` would be
  the namespaced form; instead the wheel ships `configs.mainnet`
  with no prefix. Any project that wants to namespace its own
  configs collides.
- **Pretend-packages.** They are listed in `packages=…` solely to
  attach data files. setuptools has a more honest mechanism for
  this (`package_data` on the actual package, or `data_files=`),
  but the chosen approach pollutes the top-level namespace.

This is **Inappropriate Intimacy** between the package and the
global Python namespace (Fowler, p. 85), plus a violation of the
universal convention that distributed Python packages should
carry a project-specific prefix.

### `py_modules` declaration alongside `packages` is redundant

`setup.py:28` has `py_modules=["eth_consensus_specs"]` which
declares `eth_consensus_specs` as a single-file module on top of
its existing declaration as a package via `packages=…`. setuptools
tolerates this (it picks the package over the module), but the
line is dead config — Comments-as-Deodorant (Fowler) for whatever
historical reason once needed it. New maintainers reading the
setup.py have to puzzle out why the line is there.

### Build-time dependencies leak into the runtime closure

`marko==2.2.2` and `setuptools==82.0.1` are listed as runtime deps
in `pyproject.toml:13–24`. `marko` is the markdown parser used by
`pysetup/md_to_spec.py`; `setuptools` is the build backend itself.
Neither is needed to *use* the runtime spec — they are needed to
*generate* it. But because the package boundary doesn't separate
build from runtime, every consumer of `eth-consensus-specs` pulls
both into their site-packages.

The `[project.optional-dependencies]` `test` group adds pytest +
pytest-xdist + ckzg + minizinc + psutil + deepdiff. `minizinc`
specifically is a heavy dependency: it requires a separate
*system* binary (the `gecode` solver) and a Python wrapper. It's
needed only by the fork-choice compliance-runners — a single
sub-feature. Bundling it into the test extras of the main
distribution means anyone who runs `pip install
eth-consensus-specs[test]` to use the test framework also has to
install MiniZinc system-wide.

### Optional-extras as a poor substitute for sub-packages

The `pyproject.toml` `[project.optional-dependencies]` mechanism
declares `test`, `lint`, `docs` extras. This is the right
mechanism for "additional deps for a feature within one
distribution" — but consensus-specs uses it where alternative
repos use *separate distributions*. The semantic difference:

- With `[test]` extra: `eth-consensus-specs[test]` is the same
  distribution; the test framework code ships in the wheel
  unconditionally, the extra just installs more dependencies.
- With separate `eth-consensus-specs-testing` distribution: the
  test framework is its own wheel that depends on
  `eth-consensus-specs`. A user can install just the runtime, just
  the framework (which transitively installs the runtime), or
  neither.

Using extras for what should be a separate distribution conflates
"these dependencies are optional" with "this code is optional".
The code itself isn't optional — it's always shipped — but it
shouldn't be there for runtime users.

### No deprecation markers, no `_internal` convention

Python's convention for "this is internal, don't import it" is the
underscore prefix (`_helpers`, `_internal`). `eth_consensus_specs`
uses no such convention. `eth_consensus_specs.test.helpers.state`
is reachable from outside; nothing in the namespace says "this is
internal-to-the-test-framework, don't depend on it". An external
consumer who imports a test helper for some clever purpose has just
acquired a coupling the consensus-specs maintainers don't know
about.

By Hyrum's Law — "with a sufficient number of users, every
observable behavior of your system becomes a contract" — the lack
of a curated public API surface means every reachable name is a
de-facto contract. Refactoring the test helpers risks breaking
unknown downstream code.

## Named anti-patterns

- **God Package** (Fowler, *Refactoring*, 1999, p. 78, "Large
  Class" generalised) — one distribution mixing runtime, test,
  helpers, debug, and utilities. Five concerns, one boundary.
- **Generic Top-Level Names** — `configs`, `presets`, `specs`,
  `sync` are claimed as top-level identifiers without project
  namespacing. Every Python project that uses one of these names
  conflicts.
- **Inappropriate Intimacy** (Fowler, p. 85) at the package layer
  — the package boundary knows that `configs/`, `presets/`, etc.
  are data directories needing file attachment, and re-uses
  setuptools' package mechanism for it.
- **Comments-as-Deodorant** (Fowler) — `py_modules=["eth_consensus_specs"]`
  is a leftover line that has no documented role; reviewers have
  to guess.
- **DIP violation** (Martin, *Clean Architecture*) — runtime spec,
  test framework, debug toolkit, and utilities all share a
  versioned distribution; their lifetimes are coupled by the
  release cycle even though their concerns aren't.
- **Pragmatic Programmer Tip 17** — "Eliminate effects between
  unrelated things". Build-time deps (marko, setuptools), test
  deps (pytest, minizinc), and runtime deps (eth-remerkleable,
  py-ecc) all share the same install-time closure.
- **Missing API curation** — no `__all__`, no `_internal_`
  convention, no documented public surface; Hyrum's Law means
  every reachable name becomes contract.
- **Pretend-packages** — `configs/`, `presets/`, `specs/`, `sync/`
  are listed as Python packages so `package_data` can attach files
  to them, distorting the top-level namespace.

## Comparable contrast

### `execution-specs` — two distributions

`execution-specs/pyproject.toml` declares `ethereum-execution` (the
runtime) with five top-level names that are all narrowly
project-prefixed:

- `ethereum/` — the spec (per-fork in `forks/<fork>/`)
- `ethereum_optimized/` — optimised crypto helpers
- `ethereum_spec_tools/` — CLI tools (`ethereum-spec-evm`, etc.)

Plus `py.typed` markers on each. The dependencies are runtime-only:
`pycryptodome`, `coincurve`, `ethereum-types`, `ethereum-rlp`,
`cryptography`, `platformdirs`, `libcst`. No pytest, no minizinc,
no markdown parser.

The test framework lives in a *separate* distribution at
`execution-specs/packages/testing/pyproject.toml`:

```
[project]
name = "ethereum-execution-testing"
version = "1.0.0"
description = "Ethereum execution layer client test generation and runner framework"
dependencies = [
    "click>=8.1.0,<9",
    "ethereum-hive>=0.1.0a5,<1.0.0",
    "ethereum-execution",   ← depends on the runtime
    "gitpython>=3.1.31,<4",
    "PyJWT>=2.3.0,<3",
    …
    "pytest>=8,<9",
    "pytest-custom-report>=1.0.1,<2",
    "pytest-html>=4.1.0,<5",
    "pytest-metadata>=3,<4",
    "pytest-xdist>=3.3.1,<4",
    …
]
```

A client implementer installs `ethereum-execution` and gets only
the spec. A test-vector generator installs
`ethereum-execution-testing` and transitively gets the spec plus
the framework. The two are released independently.

### `leanSpec` — same two-distribution pattern

`leanSpec/pyproject.toml` declares `lean-spec` (the runtime).
`leanSpec/packages/testing/pyproject.toml` declares
`lean-ethereum-testing` separately:

```
[project]
name = "lean-ethereum-testing"
dependencies = [
    "lean-spec",   ← depends on the runtime
    "pydantic>=2.12.0,<3",
    "pytest>=8.3.3,<9",
    "click>=8.1.0,<9",
]
```

Same shape. The test framework is a separate, declarative
distribution; the runtime is its own thing.

### What both alternatives share

- **Two distributions**, one for the runtime and one for the test
  framework.
- **Project-prefixed top-level names** — `ethereum`,
  `ethereum_optimized`, `ethereum_spec_tools`, `execution_testing`,
  `lean_spec`, `framework`, `consensus_testing`. No bare `specs`
  or `configs`.
- **Runtime deps stay narrow**; build/test/lint deps live in the
  testing distribution or in a uv `[dependency-groups]` for
  development.
- **The framework's CLIs and pytest plugins are exposed by the
  testing distribution**, not by the runtime — `fill`, `apitest`
  in leanSpec; `evm-tools`, `consume`, `execute` in execution-specs.

A user can install one without the other. consensus-specs cannot
offer that.

## Why this is load-bearing

Three properties make this worth fixing rather than living with:

1. **Every external consumer pays the framework tax.** The five
   client implementations that consume consensus-specs's vectors
   (Lighthouse, Lodestar, Prysm, Teku, Nimbus, Grandine) probably
   don't `pip install eth-consensus-specs` at all — they consume
   the published vectors directly. But anyone who *does* want the
   runtime spec for tooling (researchers, downstream Python
   projects, fork-validation tools) installs the entire test
   framework whether they want it or not.
2. **The release cadence is coupled.** A fix to a test helper
   bumps the same distribution as a runtime spec change. There is
   no way to release a new runtime spec without also implicitly
   re-releasing the test framework, and vice versa.
3. **Future external API stability is impossible to reason about.**
   Without `__all__` or an internal-naming convention, every
   reachable name is a de-facto public API. Refactoring the test
   helpers risks breaking unknown downstream code (Hyrum's Law).
   The team cannot safely move helpers around or rename them
   without semver coordination they have no path to negotiate.

This is also why the issue is *foundational* to several other
findings:

- The
  [self-referential-package-layout.md](self-referential-package-layout.md)
  issue (the package source lives inside the test tree) is what
  makes it natural to ship the test tree inside the runtime
  distribution — the boundary follows the directory, and the
  directory mixes both. Splitting the package boundary forces
  splitting the directory.
- The [helper-layer.md](helper-layer.md) god-modules issue is partly
  enabled by the absence of an external API contract — there's
  nothing telling a contributor "this helper is internal to the
  test framework", because no boundary exists at the distribution
  layer.
- The [build-orchestration.md](build-orchestration.md)
  install-requires-Make problem (`pip install .` doesn't work
  because the spec hasn't been generated) is partly a
  package-boundary issue — if the runtime and the test framework
  were separate distributions, the runtime distribution could ship
  the *output* of the build (the generated `.py` files) without
  needing the markdown extractor at all.

## What fixing it would entail

A sketch (not a design):

1. **Split into two distributions.** `eth-consensus-specs` (the
   runtime: `phase0`, `altair`, …, `eip8025`, plus narrow `utils/`
   spec primitives) and `eth-consensus-specs-testing` (the test
   framework: `test/helpers/`, `test/context.py`, `debug/`, the
   pytest plugin layer in `tests/infra/pytest_plugins/`). The
   testing distribution depends on the runtime; users install only
   what they need.
2. **Drop the four pretend-packages from the runtime distribution.**
   `configs/`, `presets/`, `specs/`, `sync/` are *data* — ship
   them as `package_data` on the actual runtime package
   (`eth_consensus_specs`) under a sub-directory like
   `eth_consensus_specs/_data/configs/`, or via `data_files=`, or
   distribute the YAML/Markdown as a separate non-Python release
   (a tarball release on GitHub) for the cross-client consumers
   who don't need a Python install. Either route, the top-level
   namespace stops claiming `configs`, `presets`, `specs`, `sync`.
3. **Curate `__init__.py`.** Add `__all__` listing the public
   surface; add a docstring describing what the package is and
   isn't. Internal helpers gain underscore prefixes
   (`_internal_state_caching`) or move into private subpackages
   (`eth_consensus_specs._internal/`).
4. **Move build-time deps out of runtime.** `marko`, `setuptools`,
   and the markdown extractor itself belong in a build-time
   environment, not in the runtime distribution's deps. PEP 517
   build-system requires (`[build-system].requires`) is the right
   home for them.
5. **Move test-extras to the testing distribution.** `pytest`,
   `pytest-cov`, `pytest-xdist`, `ckzg`, `deepdiff`, `minizinc`,
   `psutil`, `pytest-html`, `pytest-sugar` all migrate to the
   `eth-consensus-specs-testing` distribution's deps. The runtime
   distribution loses the `[test]` extra entirely.
6. **Remove the redundant `py_modules` line from `setup.py`.**
   Migrate to `pyproject.toml`-only configuration (`[tool.setuptools]`)
   if possible, deprecating `setup.py`.
7. **Document the public surface.** A `eth_consensus_specs/README.md`
   or a top-level docstring describes what is stable, what is
   internal, and what the team's compatibility commitment is. The
   testing distribution gets the same treatment for its own
   surface.
8. **Coordinate with downstream consumers.** The 0.1.x version
   number of `eth-consensus-specs` is pre-1.0; the team has
   latitude to make breaking changes. A coordinated release
   announces the split, the new install commands (`pip install
   eth-consensus-specs` → runtime only;
   `pip install eth-consensus-specs-testing` → framework + runtime),
   and the deprecation timeline for the kitchen-sink layout.

The full migration is a significant cross-cutting refactor —
intertwined with the
[self-referential-package-layout.md](self-referential-package-layout.md)
fix (the directory move) and the
[directory-structure.md](directory-structure.md) target layout (the
four-bucket reorganisation). Doing them as one v2 release is the
natural shape; doing them piecemeal is harder because each fix
requires the others to be coherent.

## References

Adjacent guides:

- [self-referential-package-layout.md](self-referential-package-layout.md)
  — the package source inside the test tree is the *physical* shape
  that makes the kitchen-sink distribution a natural outcome;
  fixing one without the other is harder than fixing both at
  once.
- [directory-structure.md](directory-structure.md) — the four-
  bucket target layout (spec markdown / generated runtime /
  framework / tests) is the directory shape that lets the export
  boundary cleanly split into two distributions.
- [build-orchestration.md](build-orchestration.md) — the
  install-requires-Make problem is partly a packaging issue; if
  the runtime distribution shipped the generated `.py` files
  rather than relying on `make _pyspec`, `pip install
  eth-consensus-specs` would just work.
- [helper-layer.md](helper-layer.md) — the helpers being part of
  the same distribution as the runtime is what enables the
  10 000-line growth without a public-API objection from
  downstream consumers; a separate testing distribution would
  give the helpers a contract layer.
- [markdown-as-source-of-truth.md](markdown-as-source-of-truth.md)
  — the runtime is *generated*, which is why bundling the
  markdown extractor (`marko`) as a runtime dep made sense at the
  time; fixing this lets the runtime ship without that build-side
  dependency.

External references:

- Fowler, M. *Refactoring: Improving the Design of Existing Code*
  (1999) — Large Class (p. 78) generalised to packages,
  Inappropriate Intimacy (p. 85), Comments-as-Deodorant (p. 87).
- Martin, R. *Clean Architecture* — module-level Dependency
  Inversion; missing-boundary-check at a system seam (the
  runtime/framework boundary).
- Hunt, A. & Thomas, D. *The Pragmatic Programmer* — Tip 11 (DRY)
  for the per-fork data files; Tip 17 (Eliminate effects between
  unrelated things) for runtime-vs-build-vs-test dependency
  coupling; Tip 38 ("Configure, don't integrate") on schema-driven
  package metadata.
- Lakos, J. *Large-Scale C++ Software Design* (1996, ch. 4) —
  physical hierarchy and component-vs-package distinction;
  applies to Python distributions just as well.
- Hyrum's Law — "with a sufficient number of users, every
  observable behavior of your system becomes a contract" — the
  absence of `__all__` makes every reachable name a de-facto
  public API.
- PEP 561 — `py.typed` marker; relevant because the marker exists
  at the package level but the public-API surface it implies
  isn't documented.
- PEP 517 — `[build-system].requires` is the right home for
  `marko` and `setuptools`, separating build-time from runtime
  deps.
