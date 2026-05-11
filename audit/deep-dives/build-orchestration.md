# consensus-specs — build orchestration (deep-dive)

`consensus-specs` glues its developer pipelines together with a 332-
line hand-written `Makefile`, six standalone Python scripts, the
`pysetup` markdown extractor, and seven duplicative GitHub Actions
workflows — with `uv` underneath all of it but no `[tool.uv]`
section in `pyproject.toml`. There is no `Justfile`, no functioning
`tox.ini`, no composite GitHub Action, and no declarative recipe
layer. The build is procedural where it could be declarative and
split across multiple tooling ecosystems where the alternative repos
use one or two.

Adjacent guides:
[static-analysis-config.md](static-analysis-config.md) (the *declared*
config that this orchestration layer invokes),
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md) (the
spec build pipeline that drives the install-requires-Make problem),
[fork-registration.md](fork-registration.md) (the per-fork
orchestration footprint).

## The shape of the problem

`consensus-specs` glues its developer pipelines together with a 332-line
hand-written `Makefile` plus six standalone Python scripts plus the
`pysetup` markdown extractor plus seven duplicative GitHub Actions
workflows, with `uv` underneath all of it but no `[tool.uv]` section
in `pyproject.toml`. There is no `Justfile`, no working `tox.ini`, no
composite GitHub Action, and no declarative recipe layer. The build
is procedural where it could be declarative and split across multiple
tooling ecosystems where the
comparables use one or two.

A new contributor's question "how do I run the full lint pipeline?"
resolves to `make lint`, which under the hood runs `_pyspec` →
`uv run mypy <bash-built-package-scope>` → `mdformat` → `ruff check
--fix` → `ruff format`, all chained imperatively in a single Make
recipe that mixes validation with auto-fix and silently mutates
tracked files (`Makefile:276–293`). The same question on
`execution-specs` resolves to `just lint` (declarative recipe in a
grouped Justfile); on `leanSpec` to `uvx tox -e all-checks` (a tox env
that composes four sub-envs by reference). All three projects do
roughly the same work; only one expresses it in a form a contributor
can read top-to-bottom.

The orchestration debt is observable but quiet — none of its
individual smells are large enough to break anything, but together
they're the surface a maintainer touches every time they want to add
a check, change a tool, upgrade a dependency, or wire a new fork into
CI. Sixteen audit findings (eight in §7, eight or nine in §8)
live here and share one root cause: there is no declarative
orchestration layer.

## Proof, by line

- **`consensus-specs/Makefile`** (332 lines total) is the primary
  developer entry point. Notable areas:
  - `:1–13` — `ALL_EXECUTABLE_SPEC_NAMES` is a hardcoded fork list at
    the top of the file; every fork addition edits this line. Same
    list appears redundantly at `pysetup/constants.py`,
    `md_doc_paths.py:PREVIOUS_FORK_OF`, `.gitignore:18–27`, and four
    GitHub workflow matrices (cross-cuts with
    [fork-registration.md](fork-registration.md)).
  - `:201–220` — the `test:` target sets *fifteen* `MAYBE_*`/conditional
    variables (`MAYBE_TEST`, `MAYBE_FORK`, `PRESET`, `MAYBE_PARALLEL`,
    `MAYBE_INFRA`, `MAYBE_SPEC`, `BLS`, `KZG`, `MAYBE_VERBOSE`,
    `MAYBE_REFTESTS`, `COVERAGE_PRESETS`, `COV_SCOPE_SINGLE`,
    `COV_SCOPE_ALL`, `COV_SCOPE`, `COVERAGE`) before the recipe runs.
    Tracing `make test fork=electra preset=minimal k=test_blocks`
    requires mentally unfolding all fifteen.
  - `:166` — `UV_RUN := uv run`, hardcoded with no fallback. Every
    invocation downstream (`:176`, `:188`, `:223`, `:262`, `:280–289`,
    `:313`) breaks at runtime if `uv` is not on `PATH`; only `_sync`
    (`:171–175`) has the safety check.
  - `:272–273` — `MYPY_PACKAGE_BASE := $(subst /,.,$(PYSPEC_DIR:$(CURDIR)/%=%))`
    constructs a Python dotted package name with `$(subst)` and
    `$(foreach)`, then passes it to mypy via `-p <name>`. Brittle
    string substitution where mypy's own `pyproject.toml`-driven
    discovery would do the job.
  - `:276–293` — the `lint:` target chains validation (`mypy`,
    `mdformat --check`) with auto-fix (`ruff check --fix`,
    `ruff format`, `mdformat` auto-fix) in one recipe. After the
    chain, it diffs git and prints a warning if files were modified,
    but the exit code stays `0`, so CI cannot distinguish "passed
    clean" from "passed and reformatted" (§7 finding "Lint target
    both validates and mutates").
  - `:331–332` — `clean: git clean -fdx`, unconditionally
    destructive. No dry-run, no confirmation. Pragmatic Programmer
    Tip 26 (Reversibility).

- **`consensus-specs/setup.py`** (~28 lines) is a near-empty wrapper
  delegating spec generation to `make _pyspec` via the Makefile. `pip
  install .` does not run that step. This is covered as a structural
  fact in [self-referential-package-layout.md](self-referential-package-layout.md)
  and [markdown-as-source-of-truth.md](markdown-as-source-of-truth.md);
  the orchestration angle is that **install reproducibility depends
  on Make**, which is a tool consensus-specs *also* uses for tests
  and lint.

- **`consensus-specs/scripts/`** — six standalone Python files:
  `check_fork_comments.py`, `check_markdown_headings.py`,
  `check_value_annotations.py`, `fix_trailing_whitespace.py`,
  `gen_kzg_trusted_setups.py`, `gen_spec_indices.py`. Each
  re-implements its own `argparse` and file-discovery loop. None are
  registered as `[project.scripts]` entry points in `pyproject.toml`;
  none are pytest plugins or pre-commit hooks. The first four are
  invoked from `make lint`; the last two are **not invoked anywhere**
  — dead code (§7 finding "Dead code: unreachable generator scripts").

- **`consensus-specs/pyproject.toml`** has `uv.lock` committed
  (343 KB) but no `[tool.uv]` section, no workspace, no
  `[dependency-groups]` (PEP 735). `uv` is used implicitly by every
  `make` target via `UV_RUN`, but the project's expectations of `uv`
  (version, workspace shape, group composition) are unstated.
  Cross-cuts with [static-analysis-config.md](static-analysis-config.md).

- **`consensus-specs/.github/workflows/`** — seven workflows. Every
  workflow that runs Python repeats the same three-step setup
  (`actions/checkout` → `setup-python` with `pyproject.toml` →
  `astral-sh/setup-uv` with `enable-cache: true`). The block appears
  ~10 times across `checks.yml`, `comptests.yml`, `tests.yml`,
  `release.yml`, `website.yml`. Every action SHA pin is repeated
  identically across the files, with the version tag in an inline
  comment that can drift from the SHA.
  - `comptests.yml:60–170` — the `config` job builds a CI matrix
    dynamically with bash + jq from three orthogonal inputs (preset,
    fork, config). The expression is dense, has no dry-run/preview
    surface, and produces opaque "matrix expansion failed" errors
    when something is wrong.
  - All jobs use `runs-on: ubuntu-latest` with no resource specs.
  - `tests.yml` — full-matrix tests run only on `workflow_dispatch`
    (manual) and a daily cron, not on `pull_request` or `push`.
    Preset-specific bugs surface only the next morning rather than on
    the PR that introduced them.
  - `stale.yml` — 365-day inactivity threshold. Daily cron incurs CI
    cost for a task that catches almost nothing; "maintenance
    theatre".
  - `checks.yml:59–112` — PR title validation in inline bash, with
    fragile regex (e.g. `[^e]ed$` to detect past tense, special-cased
    against "Embed"/"Shed").

- **No `Justfile`, no functioning `tox.ini`, no composite GitHub
  Action, no `pre-commit` config.** The orchestration *gaps* are
  themselves evidence of the fragmentation: there is no place to
  declare a check or recipe in a way that any tool other than Make
  can consume.

## Critique / inventory

### The Makefile as a procedural cascade

The `test:` target's fifteen-variable cascade and the `lint:` target's
validation-mutation conflation are the two clearest examples. Both
are forms of Long Method (Fowler, *Refactoring*, 1999) at the recipe
layer: a single Make rule mixes argument parsing, environment
construction, tool dispatch, and post-hoc git-diff-checking. The
declarative alternative — one recipe per concern, parameterised by
inputs, composed by reference — exists in `Justfile`, `tox.ini`, or
even Make itself with a different style; the choice here was
procedural and the cost compounds.

The recipe layer is also coupled to the *physical* layout of the
repo. `MYPY_PACKAGE_BASE := $(subst /,.,$(PYSPEC_DIR:$(CURDIR)/%=%))`
encodes the dotted-name mapping for `tests/core/pyspec/eth_consensus_specs/`
in a substitution rule; it would break if the package were moved out
of `tests/`. Inappropriate Intimacy (Fowler) between the build
system and the source layout (cross-cuts with
[directory-structure.md](directory-structure.md) and
[self-referential-package-layout.md](self-referential-package-layout.md)).

### The five-tool fragmentation

Adding a new check requires deciding which of these layers owns it:
`Makefile` recipes, `pysetup/` build-time generation,
`scripts/<name>.py` standalone scripts, `pyproject.toml` `[tool.*]`
config, or `.github/workflows/` CI steps. The decision is
undocumented; the answer in practice is "wherever the contributor
with the change is most comfortable", which is how the codebase
ended up with `check_*` Python scripts implementing what `ruff` and
`mdformat` plugins could provide, two `gen_*` scripts that are never
run, and `pysetup` which exists only because the spec lives in
markdown
([markdown-as-source-of-truth.md](markdown-as-source-of-truth.md)).

Hunt & Thomas (*The Pragmatic Programmer*, Tip 11 "DRY") captures
this at the project level: the same orchestration concept ("run a
Python script with these arguments") is implemented six different
ways across the scripts, with six independent `argparse`
declarations. A single `[project.scripts]` block plus pre-commit
hooks would replace most of `scripts/` with declarative entry points.

### CI workflow duplication

Every Python-running workflow repeats the same three-step bootstrap;
upgrading a pinned action SHA is a 10+-file find-and-replace. The
same ecosystem hosts a clean alternative: composite actions
(`.github/actions/<name>/action.yaml`), used as
`uses: ./.github/actions/setup-uv` from any workflow that needs the
bootstrap. `execution-specs` does this; `consensus-specs` does not.
Shotgun Surgery (Fowler) for any CI bootstrap change.

The dynamic matrix in `comptests.yml:60–170` is its own sub-smell.
Building a CI matrix with bash + jq is a working pattern but it has
no debug surface — when the expansion fails, the job output is the
post-expansion errors, not the expression that produced them. A
matrix `include`-list (verbose but transparent) or a small Python
script that emits JSON with prints on failure would both expose what
the expansion built. This is "Stringly-Built Code" (a structural
sibling of Stringly Typed) at the CI configuration layer.

### Lint conflates validation with mutation

`Makefile:276–293`'s `lint:` chains `ruff check --fix`, `ruff format`,
and `mdformat` (auto-fix mode), which mutate tracked files, with
`mypy` and `mdformat --check`, which only validate. The post-hoc
`git diff` check warns but doesn't fail. In CI, a clean run is
indistinguishable from "passed and silently reformatted"; in local
development, `make lint` becomes "fix everything you can and tell me
about the rest", which is a reasonable verb but a misnamed target —
"lint" connotes validation, not transformation. Both `execution-specs`
(`just lint` vs `just fix`) and `leanSpec` (`tox -e lint` vs
`tox -e fix`) split the two.

### Dead, manual, and not-pre-commit-able scripts

`scripts/gen_kzg_trusted_setups.py` and `scripts/gen_spec_indices.py`
are never invoked. Either they're dead (Fowler's "Dead Code") or they
have an undocumented contract that they're run manually for some
operational task. Neither is wired into `pre-commit-config.yaml`
(absent), `pyproject.toml [project.scripts]` (absent), or any CI
job. Future maintainers cannot tell from the file whether to keep,
delete, or document.

The four `check_*.py` scripts that *are* used are also outside any
standard tool: they're invoked from `make lint` via `python script.py`
calls, not as `pre-commit` hooks, not as `pytest` plugins, not as
ruff custom rules. Each script reimplements file discovery
(`pathlib.Path.rglob` with custom patterns) and argument parsing
(`argparse`) — work that a pre-commit hook gets for free. Hunt &
Thomas (Tip 38, "Configure, don't integrate") apply.

### "Maintenance theatre" workflows

`stale.yml` runs daily with a 365-day inactivity threshold. Issues
that go an entire year without a comment get marked stale and closed
30 days later. The threshold is high enough that the workflow
catches almost nothing. The cron incurs negligible CI cost but the
workflow exists in the repo as "we have stale-issue management",
which is a form of Comments-as-Deodorant (Fowler) applied to CI:
the workflow's existence asserts a hygiene property that the
configured behaviour does not actually deliver.

### `runs-on: ubuntu-latest` with no resource declaration

Every job pins `ubuntu-latest`. No memory, CPU, or timeout
declarations. The `comptests` matrix produces large generated
artefacts (one per fork × preset × slice) that can exhaust runner
storage silently; the workflow has `continue-on-error: true` on the
artifact-cleanup steps, hiding cleanup failures. A single per-runner
spec at the top of the workflow file (or, better, in a composite
action) would make resource expectations explicit.

## Named anti-patterns

- **Long Method** (Fowler, *Refactoring*, 1999, p. 76) at the recipe
  layer — `Makefile:201–220`'s 15-variable test target.
- **Shotgun Surgery** (Fowler, p. 79) — every CI bootstrap upgrade
  edits 10+ workflow files; every fork addition edits the
  `ALL_EXECUTABLE_SPEC_NAMES` list, the per-fork CI matrices, and the
  Makefile in tandem.
- **Inappropriate Intimacy** (Fowler, p. 85) — the Makefile knows the
  physical path of the package source (`PYSPEC_DIR`) and constructs
  Python dotted names from it via string substitution.
- **Comments-as-Deodorant** (Fowler) — `stale.yml` configured at
  365 days; the lint target's git-diff warning that doesn't fail.
- **Dead Code** (Fowler) — `gen_kzg_trusted_setups.py`,
  `gen_spec_indices.py`.
- **Stringly-Built Code** — `comptests.yml`'s bash+jq dynamic matrix;
  the Makefile's `$(subst)`-built mypy package name.
- **Configuration as Global Mutable State** (Hunt & Thomas, *The
  Pragmatic Programmer*, Tip 17) — `UV_RUN := uv run` as a global
  Make variable used by every recipe; no per-recipe override path.
- **DRY violation** (Hunt & Thomas, Tip 11) — five-place fork list,
  10×-repeated CI bootstrap, six independent argparse declarations
  across `scripts/`.
- **Reversibility violation** (Hunt & Thomas, Tip 26) — `make clean`
  unconditionally runs `git clean -fdx`.
- **Single Responsibility violation** (Martin, *Clean Code*) at the
  recipe level — `lint` mixes validation and mutation.
- **Open/Closed violation** (Martin) at the orchestration level —
  adding a new check, a new fork, or a new tool ecosystem requires
  editing existing recipes rather than registering against a stable
  interface.

## Comparable contrast

### `execution-specs` — declarative `Justfile` + composite action

`execution-specs/Justfile` (~365 lines, similar size to consensus-specs's
Makefile) is structured around grouped, named recipes:

```just
# Run all static checks (spellcheck, lint, format, mypy, ...)
[group('static analysis'), parallel]
static: typecheck lint-spec spellcheck deadcode lint-actions lock-check format-check lint
```

The `static` recipe declares its dependencies inline; `[parallel]`
opts into parallel execution; `[group('static analysis')]` makes
`just --list` self-document. There is no equivalent of the 15-variable
cascade — recipes either take positional arguments (`set
positional-arguments := true` at the top) or are split into smaller
recipes that compose by reference.

CI uses one composite action,
`execution-specs/.github/actions/setup-uv/action.yaml`:

```yaml
name: Setup uv and just
description: Install uv, Python, and just for CI jobs
inputs:
  python-version:
    default: "3.13"
  enable-cache:
    default: "true"
runs:
  using: "composite"
  steps:
    - uses: astral-sh/setup-uv@<sha> ...
    - uses: taiki-e/install-action@<sha> ...  # installs `just`
```

Every workflow in `execution-specs/.github/workflows/` calls
`uses: ./.github/actions/setup-uv` with at most a `python-version`
override. SHA upgrades happen in one file. Fifteen other composite
actions exist in the same `.github/actions/` directory for related
concerns (`build-fixtures`, `setup-geth`, `cache-docker-images`).
This is the same DRY discipline `execution-specs` applies elsewhere
applied to CI.

`tox.ini` in `execution-specs` is now a migration stub that prints
"execution-specs has migrated from tox to just" and exits non-zero —
a deliberate decision to centralise on one orchestrator and break
cleanly with the legacy tool.

### `leanSpec` — `tox.ini` with `tox-uv` runner

`leanSpec/tox.ini` uses tox 4 with `runner = uv-venv-lock-runner`,
declaring environments for each concern:

```ini
[testenv:all-checks]
description = Run all quality checks (lint, typecheck, spellcheck, mdformat)
commands =
    {[testenv:lint]commands}
    {[testenv:typecheck]commands}
    {[testenv:spellcheck]commands}
    {[testenv:mdformat]commands}

[testenv:lint]
commands =
    ruff check --no-fix --show-fixes
    ruff format --check

[testenv:fix]
commands =
    ruff check --fix
    ruff format
```

`lint` and `fix` are separate envs; `all-checks` composes by
reference using tox's `{[testenv:other]commands}` syntax. A
contributor runs `uvx tox -e all-checks` for validation,
`uvx tox -e fix` to mutate. There is no Makefile, no Justfile, no
`scripts/` directory. The orchestration layer is one file, ~80
lines, fully declarative.

### Common shape

Both comparables converge on three properties consensus-specs lacks:

1. **One declarative orchestrator** — `Justfile` or `tox.ini`, with
   recipes/envs that compose by reference.
2. **A composite action or runner discipline for CI** — bootstrap
   logic deduplicated.
3. **Validation and mutation as separate verbs** — `lint` vs `fix`,
   not "lint that auto-fixes".

The split is independent of language, framework, or domain — both
projects are the same shape (Python, uv-managed, Ethereum-spec
codebases) and both made the same orchestration choices that
consensus-specs has not.

## Why this is load-bearing

The orchestration layer is the surface every contributor touches
every day, and the surface every fork addition modifies. Concretely:

- A typo in `make test fork=electra` has to navigate the 15-variable
  cascade. A typo in `just test electra` is a recipe-not-found error
  with a one-line fix.
- An action SHA upgrade in CI is a 10-file change in consensus-specs;
  one file in execution-specs.
- Adding a new lint check is "edit `Makefile:276–293` and figure out
  whether to add it before or after the auto-fix block" in
  consensus-specs; "add a `[testenv:newcheck]` block" in leanSpec.
- The fork list lives in five places (cross-cuts with
  [fork-registration.md](fork-registration.md)) because the
  orchestration layer doesn't surface a single place to register
  per-fork concerns.

This deep-dive does not introduce a new "Most consequential finding";
the orchestration debt is the *aggregate* cost of decisions covered by
others ([fork-registration.md](fork-registration.md),
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md),
[directory-structure.md](directory-structure.md),
[self-referential-package-layout.md](self-referential-package-layout.md),
[static-analysis-config.md](static-analysis-config.md)). What's
specific to this layer is that it's the place where those decisions
are *manifested* for the contributor — the 15-variable test target is
where the user feels the markdown source-of-truth, the package layout,
the absent `[tool.uv]`, and the per-fork CI matrices all at once.

## What fixing it would entail

A practical staging:

1. **Adopt `Justfile` or `tox.ini` as the orchestration layer.**
   Either choice resolves most of §7. `Justfile` matches
   `execution-specs`; `tox.ini` matches `leanSpec`. The decision is
   a matter of team taste; either is dramatically better than the
   current Makefile.
2. **Split `lint` from `fix`.** Two recipes, two verbs. CI runs
   `lint`; local development runs `fix` when needed.
3. **Replace `scripts/check_*.py` with `pre-commit-hooks` or `ruff`
   custom plugins.** The four checks are the kind of thing pre-commit
   was built for. Drop the dead `gen_kzg_trusted_setups.py` and
   `gen_spec_indices.py` (or document them as one-off operational
   tools and move them to a clearly-labelled location).
4. **Introduce a composite GitHub Action** at
   `.github/actions/setup-python-uv/action.yaml`. Use it from every
   workflow. SHA upgrades become one-file changes. Mirror
   `execution-specs/.github/actions/setup-uv/action.yaml`.
5. **Replace the `comptests.yml` dynamic matrix** with either an
   explicit `matrix.include` list (verbose but transparent) or a
   small `scripts/build_comptests_matrix.py` invoked with a `--dry-run`
   flag that prints the matrix it would emit.
6. **Add `[tool.uv]` and PEP 735 `[dependency-groups]` to
   `pyproject.toml`.** Matches `execution-specs`/`leanSpec` and lets
   `uv` discover groups without Make doing the dispatch.
7. **Make `test`, `lint`, `fix`, etc. all single-tool invocations.**
   `just test` or `tox -e test`. The 15-variable Makefile cascade
   moves into either Justfile parameters (positional + `set
   positional-arguments`) or tox `factor` envs.
8. **Drop the `make clean` `git clean -fdx`** in favour of either a
   targeted cleanup (caches only) or a confirmation prompt.
9. **Reconsider `stale.yml`.** Either tighten the threshold to a
   value that catches actual stale issues (30–60 days), or remove
   the workflow.

The full migration is not small but each step is independent and
reversible. Step 1 (the Justfile or tox.ini choice) is the load-bearing
one — once it exists, steps 2, 3, 6, 7, 8, 9 collapse into recipe
moves; steps 4 and 5 are independent CI/tooling cleanups that can
happen in any order.

## References

Related guides:
- [static-analysis-config.md](static-analysis-config.md) — declared
  config (mypy/ruff/pytest/uv/dependency groups) lives in
  `pyproject.toml`; this deep-dive covers how the orchestration layer
  invokes that config and what the comparables do differently at the
  invocation layer.
- [markdown-as-source-of-truth.md](markdown-as-source-of-truth.md) —
  the orchestration layer must run `pysetup` before tests; the
  `_pyspec` Make target chain and the `setup.py` deferral both stem
  from the markdown source-of-truth choice.
- [fork-registration.md](fork-registration.md) — the
  `ALL_EXECUTABLE_SPEC_NAMES` list, the per-fork CI matrices, and the
  Makefile fork plumbing are all symptoms of the N-place fork
  registration pattern.
- [directory-structure.md](directory-structure.md) — the Makefile
  knows the physical path of the package source (`PYSPEC_DIR`); a
  layout fix simplifies the recipe.
- [self-referential-package-layout.md](self-referential-package-layout.md)
  — `pip install .` not running `make _pyspec` is a downstream
  symptom of the package-in-tests-tree layout.
