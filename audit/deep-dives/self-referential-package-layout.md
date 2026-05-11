# consensus-specs — self-referential package layout (deep-dive)

`consensus-specs` declares a Python package whose source lives inside
its own test tree, depends on that package as if it were external, and
consequently makes the same code reachable under two import names.
Several other findings turn out to be downstream consequences of this
single structural decision: the dual-mutation conftest workaround, the
broken `pip install .`, the per-fork `.gitignore` enumeration, and the
bootstrapping fragility of `VERSION.txt`.

Adjacent guides:
[directory-structure.md](directory-structure.md) (proposes the target
layout that resolves this),
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md) (why
the package source ended up inside the tests directory in the first
place).

## The shape of the problem

`setup.py` declares a package called `eth_consensus_specs`. The package
source lives at `consensus-specs/tests/core/pyspec/eth_consensus_specs/`
— *inside the test tree*. The repo then treats that package as if it
were an external dependency: every test file under
`tests/core/pyspec/eth_consensus_specs/test/<fork>/...` and every file
under `tests/infra/` imports its own siblings via the installed-package
name (`from eth_consensus_specs.test.helpers.state import ...`).
The repo depends on itself, and the package it defines lives inside the
test directory of the project that defines it.

This is compounded by `pyproject.toml` adding the repo root to
`sys.path` (`pythonpath = ["."]`). The same files are now reachable
under two distinct dotted names. Python caches modules by full dotted
name, so they become *two distinct module objects with two independent
copies of every module-level global*.

## The proof, by line

- `setup.py:19–25` — `package_dir = {"eth_consensus_specs":
  "tests/core/pyspec/eth_consensus_specs", ...}`. The package's source
  path is explicitly mapped to a subdirectory of `tests/`.
- `pyproject.toml:60–61` — `[tool.pytest.ini_options]` declares
  `pythonpath = ["."]`. This adds the repo root to `sys.path` and is
  the second route by which the package source becomes importable.
- The editable-install finder at
  `consensus-specs/.venv/lib/python3.13/site-packages/__editable___eth_consensus_specs_*_finder.py`
  has `MAPPING["eth_consensus_specs"] =
  "/.../tests/core/pyspec/eth_consensus_specs"`. So the same files are
  reachable as both `eth_consensus_specs.X` (via the editable finder)
  and `tests.core.pyspec.eth_consensus_specs.X` (via the
  pytest-injected sys.path entry).
- `tests/core/pyspec/eth_consensus_specs/test/conftest.py:113–120` is
  the workaround. It mutates `context.DEFAULT_TEST_PRESET` and *also*
  mutates
  `sys.modules.get("tests.core.pyspec.eth_consensus_specs.test.context").DEFAULT_TEST_PRESET`
  if that second module object happens to exist. The fixture has to
  patch both because they are two distinct module objects.
- The comment in that fixture (`conftest.py:114–116`) still calls the
  package `eth2spec` — the pre-rename name. The workaround predates the
  rename to `eth_consensus_specs`; the rename did not catch the
  surrounding prose, suggesting the dual-mutation pattern is obscure
  enough that the renamer didn't see it.
- `.gitignore:18–27` enumerates ten generated fork directories under
  `tests/core/pyspec/eth_consensus_specs/{phase0,altair,...,eip*}/`,
  because `pysetup` *generates* spec modules into those folders. The
  test directory both *is* the package and *contains the build output
  of the package*.

## Downstream consequences

Several of the points below show up across other guides as separate symptoms. They share a single root cause.

- **The dual-mutation conftest workaround.** Touching
  `context.DEFAULT_TEST_PRESET` requires touching both module objects.
  Anything else mutated on `context` (BLS toggle, fork list, generator-
  mode flag) is a latent bug waiting for the same workaround, or a
  silent failure if the second copy isn't reached. (See
  report §1, "Preset swapping with dual-module imports is fragile".)
- **`.gitignore` Shotgun Surgery.** Each new fork generates a new
  directory *inside the package*, requiring a new line in `.gitignore`
  — see §9 "`.gitignore` exhibits Shotgun Surgery for
  generated pyspec phases".
- **Install requires Make.** `setup.py` defers all spec generation to
  `make _pyspec`, because the fork submodules don't exist on disk until
  `pysetup` writes them into the package source directory. Standard
  `pip install .` does not run Make, so it produces a half-installed
  package. (See §6, "`setup.py` defers all spec
  generation to `make _pyspec`".)
- **Bootstrapping fragility for the version string.** `pyproject.toml:103`
  reads `VERSION.txt` from
  `tests/core/pyspec/eth_consensus_specs/VERSION.txt` — the file lives
  *inside* the dual-named package, so it inherits the same loading
  surprise (which copy of the package is read?). (See §9,
  "Dynamic version sourced from a generated file".)
- **`pythonpath = ["."]` is load-bearing for a wrong reason.** The
  setting is necessary because some test code (and `tests/infra/`
  modules) reach the package via the long path. Removing it would
  break those import paths *and* tools that depend on resolving the
  same module under both names.
- **`tests/infra/` imports `eth_consensus_specs.test.helpers.*`.** The
  "test infrastructure" lives at a different level of the tree than the
  pyspec test layer, but reaches its sibling via the *installed*
  package name — `tests/infra/yield_generator.py`, `tests/infra/dumper.py`,
  `tests/infra/block_randomized.py` all do this. The infra/test
  boundary is not a directory boundary; it's an import-path convention.
- **Static analysis confusion.** Pyright, "find all references",
  "go to definition", and coverage tools key on the full dotted
  name. The same source file becomes two nodes in any such graph;
  cross-references resolve under one name and miss under the other.
  Symbols queried under one dotted name appear to have no callers
  even when callers exist under the other.
- **Refactoring is doubled.** Renaming a helper requires updating
  callers under both import paths, or accepting that one breaks. The
  conftest dual-mutation is itself a small, ongoing example.
- **Stale comment, real signal.** The `eth2spec` reference at
  `conftest.py:114–116` survives a rename because the dual-mutation
  pattern is obscure enough that reviewers don't read the comment when
  changing the name. The bug rot is slow but constant.

## The proper names for what's happening

This is a stack of three reinforcing anti-patterns, not one:

1. **Self-referential package layering** (Lakos,
   *Large-Scale C++ Software Design*, 1996, ch. 4 — physical hierarchy
   violations). The build product (`eth_consensus_specs` Python
   package) lives in a directory whose name says it is *test material
   of* the package being built. Build outputs are siblings of test
   inputs. There is no clean physical hierarchy.

2. **Module identity via path, not name** (a Python import-system
   pitfall every guide warns against — see Brett Cannon's
   "How importing works", Aahz's posts on `sys.modules`). Once two
   paths reach the same files, you have two modules. The
   `pythonpath = ["."]` setting plus the editable install create the
   dual-path condition.

3. **Inappropriate Intimacy at the conftest layer** (Fowler,
   *Refactoring*, 1999, p. 85). The conftest knows that
   `eth_consensus_specs` and `tests.core.pyspec.eth_consensus_specs`
   are the same physical thing and patches both. A fixture should not
   need to know how Python is loading the source.

The umbrella label is **"build-test-source physical conflation"**
(Spolsky's Law of Leaky Abstractions applies — the "package"
abstraction leaks because the package source and the test data live
in the same directory under the same package name, and the build
output also lives there).

## Comparable contrast

Both comparable repos use the canonical `src/` layout:

- `execution-specs/src/ethereum/forks/<fork>/` is the spec;
  `execution-specs/tests/<fork>/` is the test code;
  `execution-specs/packages/testing/src/execution_testing/` is the test
  framework. Three separate Python packages, each installed once, each
  reachable by *one* import name. There is no `pythonpath = ["."]`
  workaround.
- `leanSpec/src/lean_spec/` is the spec; `leanSpec/tests/` is the test
  code; `leanSpec/packages/testing/src/{framework,consensus_testing}/`
  is the test framework. Same shape.

In neither comparable can a test file reach its own siblings through
an installed-package name. The dual-import pathology cannot occur
because the test directory and the package source directory are
different directories.

## Why this is load-bearing wrong

Most of the audit findings are local — fixable in one PR. This
one is foundational. Several findings stop existing as soon as it is
addressed:

- The conftest dual-mutation goes away (only one module object exists).
- `.gitignore` collapses from ten lines to one (or zero, if generated
  output lives outside the package source).
- `setup.py` becomes a normal Python package definition; `pip install .`
  is enough.
- `pythonpath = ["."]` is no longer load-bearing; pytest can rely on
  the installed package alone.
- The infra/test boundary becomes a real boundary instead of an
  import-path convention.
- Static analysis tools (Pyright, IDE jump-to-definition) see the
  package as one thing.

## What fixing it would entail

1. **Move the package out of the test tree** to `src/eth_consensus_specs/`
   (or `src/ethereum_consensus/` if there's appetite for renaming).
2. **Stop installing `tests/core/pyspec/eth_consensus_specs/` as a
   package.** The code under
   `tests/core/pyspec/eth_consensus_specs/test/` becomes a regular
   pytest test directory that imports `eth_consensus_specs` only by its
   canonical name.
3. **Drop `pythonpath = ["."]` from pytest config.** Tests reach the
   package via the editable install only.
4. **Rewrite `pysetup/` to generate fork modules into the new src
   location.** Or — more ambitious — refactor away from generation
   entirely (mirror what `execution-specs` does with WET fork
   directories or what `leanSpec` does with Pydantic-modelled forks).
   See §6 for the full scope of `pysetup/` debt that
   would be touched.
5. **Delete the conftest dual-mutation workaround** (`conftest.py:113–120`)
   and the now-redundant per-fork lines in `.gitignore`.
6. **Update every import in `tests/infra/` and `tests/core/pyspec/.../test/`
   to use the canonical package name** — most already do (most files
   already use `eth_consensus_specs.X` rather than the long path), so
   the import churn is small. The big work is the directory move and
   the `pysetup` retargeting.

That is a major refactor — touching `setup.py`, `pyproject.toml`,
`pysetup/`, every test file's resolution path, the editable-install
machinery, `.gitignore`, and CI. It's the kind of cleanup that
justifies a "v2.0" release. It is also the cleanup that fixes a dozen
smaller findings as side-effects, which is the test of a good
foundational refactor.

## Related guides

- [package-export-boundary.md](package-export-boundary.md) — the
  *outward* face of the same `setup.py`: even after the package
  source moves out of the test tree, the wheel still installs five
  top-level names with no curated public API. Independent in scope
  from this finding but shares a `setup.py` rewrite.
- [directory-structure.md](directory-structure.md) — the layout
  refactor that this structural fix unlocks.
- [markdown-as-source-of-truth.md](markdown-as-source-of-truth.md)
  — the upstream cause of why the package source is generated, not
  authored.

