# consensus-specs — build orchestration (deep-dive)

`consensus-specs` runs its developer pipelines through a 332-line
hand-written `Makefile` that wraps standalone Python scripts under
`scripts/`, the `pysetup` markdown extractor, and seven GitHub
Actions workflows. `uv` is the runtime underneath most Make
recipes; its version is pinned for CI via a `vars.UV_VERSION`
GitHub repo variable, but `pyproject.toml` has no `[tool.uv]`
section — so a contributor running `uv` locally has no
`required-version` floor, no workspace declaration, and no
`[dependency-groups]` (PEP 735). Adding a check, changing a
tool, upgrading a dependency, or wiring a new fork into CI
typically edits across several layers — `Makefile` recipes,
scripts under `scripts/`, `pyproject.toml [tool.*]` config, the
`pysetup/` extractor, and `.github/workflows/` — with no shared
convention for which layer owns which concern.

Adjacent guides:
[static-analysis-config.md](static-analysis-config.md) (the *declared*
config that this orchestration layer invokes),
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md) (the
spec build pipeline that drives the install-requires-Make problem),
[fork-registration.md](fork-registration.md) (the per-fork
orchestration footprint).

## The shape of the problem

None of the individual items below is large enough to break the
build, but together they form the surface a maintainer touches
every time they want to add a check, change a tool, upgrade a
dependency, or wire a new fork into CI. Two structural instances
ground the shape:

**Instance one — `uv` is pinned for CI but not for contributors.**
Most Make recipes shell through `UV_RUN := uv run`
(`Makefile:166`). The `uv` version is pinned for CI via a
`vars.UV_VERSION` GitHub repo variable read by every workflow
that installs it (`release.yml:75,164`, `website.yml:27`,
`checks.yml:26,45,140`); bumping the CI version is a
repo-variable change with no code edit required. `pyproject.toml`,
however, has no `[tool.uv]` section — no `required-version`, no
workspace declaration, no `[dependency-groups]` (PEP 735). A
contributor with a much-older or much-newer `uv` on their `PATH`
may produce different resolution behaviour from CI without
warning. `execution-specs` pins on both sides: `version: "0.10.4"`
in the composite action *and*
`[tool.uv]\nrequired-version = ">=0.7.0"` in `pyproject.toml`
(plus a `[tool.uv.workspace]` block) — so the contributor's local
`uv` is constrained at install time. consensus-specs has the CI
half. Cross-cuts with
[static-analysis-config.md](static-analysis-config.md).

**Instance two — CI bootstrap repeats across workflows.**
Every Python-running workflow under `.github/workflows/` includes
the same `setup-python` + `astral-sh/setup-uv` bootstrap (after
the per-workflow `actions/checkout`). The block appears in
`checks.yml`, `comptests.yml`, `tests.yml`, `release.yml`, and
`website.yml`, with the same action SHA pins repeated in each.
Upgrading a pinned SHA today is a multi-file change kept in sync
by Dependabot/Renovate; a composite action at
`.github/actions/setup-uv/action.yaml` (the pattern
`execution-specs` uses) would consolidate the `setup-python` +
`setup-uv` pair into one referenced file, reducing the surface
where the SHAs live — at the cost of slower Dependabot cadence
for SHAs *inside* composite actions, which is a known
trade-off.

These instances are structural. They're compounded by recipe-level
items inside the Makefile itself — `make lint` chains read-only
checks with auto-fix steps that modify tracked files (the recipe
diffs `git` afterwards but exits 0 regardless); `make test`
exposes nine user-facing knobs documented in the Makefile help
block (lines 53–91) plus several derived variables before the
underlying `pytest` invocation runs; `make clean` runs `git clean
-fdx` with a bold warning in the help text. The Critique /
inventory section below catalogues both the structural and the
recipe-level items, grouped by category; the Comparable contrast
section near the end describes how the two reference repos
address the same engineering need.

## Proof, by line

- **`consensus-specs/Makefile`** (332 lines total) is the primary
  developer entry point. Notable areas:
  - `:1–13` — `ALL_EXECUTABLE_SPEC_NAMES` is a hardcoded fork list at
    the top of the file; every fork addition edits this line. Same
    list appears redundantly at `pysetup/constants.py`,
    `md_doc_paths.py:PREVIOUS_FORK_OF`, `.gitignore:18–27`, and four
    GitHub workflow matrices (cross-cuts with
    [fork-registration.md](fork-registration.md)).
  - `:201–220` — the `test:` target exposes nine user-facing knobs
    (`k=`, `fork=`, `preset=`, `component=`, `bls=`, `kzg=`,
    `verbose=`, `reftests=`, `coverage=`), documented in the help
    block at `Makefile:53–91`. These are realised inside the recipe
    as a set of `MAYBE_*` / `COV_SCOPE_*` derived variables that
    expand into the final `pytest` invocation. The user surface is
    documented; the derivation is dense but inspectable via
    `make -n test ...` (Make's dry-run flag).
  - `:166` — `UV_RUN := uv run`, hardcoded. Recipes that wrap
    Python invocations (`:176`, `:188`, `:223`, `:262`, `:280–289`,
    `:313`) use `UV_RUN`; recipes that bootstrap the environment
    or operate on the filesystem (`_sync` at `:171–175`, `clean`,
    `help*`, `_copy_docs`) do not. The `command -v uv` safety
    check at `_sync` is positioned correctly as a dependency of
    the downstream recipes (`_pyspec` depends on `_sync`, which
    depends on `uv` being on `PATH`); duplicating it in every
    downstream recipe would be redundant.
  - `:272–273` — `MYPY_PACKAGE_BASE := $(subst /,.,$(PYSPEC_DIR:$(CURDIR)/%=%))`
    constructs a Python dotted package name with `$(subst)`, then
    passes it to mypy via `-p <name>`. The substitution encodes
    the current `tests/core/pyspec/eth_consensus_specs/` layout;
    if the package moves out of `tests/`
    (per [self-referential-package-layout.md](self-referential-package-layout.md)),
    the rule needs updating. `mypy`'s own `pyproject.toml`-driven
    discovery is an alternative that avoids encoding the layout
    in the Makefile.
  - `:276–293` — the `lint:` target chains validation (`mypy`,
    `mdformat --check`) with auto-fix steps (`ruff check --fix`,
    `ruff format`, `mdformat` auto-fix) in one recipe. After the
    chain, it diffs `git` and prints a warning if files were
    modified, but the exit code stays `0`, so CI cannot
    distinguish "passed clean" from "passed and reformatted"
    without a follow-up diff check (§7 finding "Lint target both
    validates and mutates").
  - `:331–332` — `clean: git clean -fdx`. The help block
    (`:149–157`) bolds a warning that the recipe deletes all
    untracked files. `git clean -ndx` (the standard dry-run
    flag) previews the deletion before the user runs the
    recipe. The recipe is wholesale rather than targeted — a
    cache-only or generated-only cleanup is not separately
    exposed.

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
  re-implements its own `argparse` and file-discovery loop. None
  are registered as `[project.scripts]` entry points in
  `pyproject.toml`; none are pytest plugins or pre-commit hooks.
  The first four are invoked from `make lint`. `gen_spec_indices.py`
  is wired into `mkdocs.yml:35–37` under the `gen-files` plugin's
  `scripts:` list, so it runs as part of every mkdocs build.
  `gen_kzg_trusted_setups.py` is an operational utility (regenerates
  KZG trusted setups when ceremony parameters change) — it is not
  intended for routine invocation; whether it should remain in
  `scripts/` or move to a clearly-labelled operational directory
  is a curation choice.

- **`consensus-specs/pyproject.toml`** has `uv.lock` committed
  (343 KB) but no `[tool.uv]` section, no workspace declaration,
  and no `[dependency-groups]` (PEP 735). The `uv` version is
  pinned for CI via a `vars.UV_VERSION` GitHub repo variable
  consumed by every workflow that installs `uv` — so version
  drift across workflows is not a risk. The contributor side has
  no equivalent: there is no `required-version` for `uv` to
  enforce when a local invocation runs, no declared workspace
  shape, and no declared dependency-group structure. Compare to
  `execution-specs/pyproject.toml:502–509`, which declares
  `[tool.uv]\nrequired-version = ">=0.7.0"` plus
  `[tool.uv.workspace]` and `[tool.uv.sources]` blocks.
  Cross-cuts with [static-analysis-config.md](static-analysis-config.md).

- **`consensus-specs/.github/workflows/`** — seven workflows. Every
  workflow that runs Python repeats the same `setup-python` +
  `setup-uv` bootstrap (after the per-workflow `actions/checkout`).
  The block appears in `checks.yml`, `comptests.yml`, `tests.yml`,
  `release.yml`, and `website.yml`. Action SHA pins are repeated
  identically across the files; today the multi-file find-and-
  replace for upgrades is handled by Dependabot/Renovate in a
  single PR.
  - `comptests.yml:60–170` — the `config` job builds a CI matrix
    dynamically with bash + jq from three orthogonal inputs
    (preset, fork, config). The expression is dense and has no
    dry-run/preview surface; when expansion fails, the job output
    is the post-expansion error rather than the expression that
    produced it.
  - All jobs use `runs-on: ubuntu-latest` (the standard for
    GitHub-hosted runners; no resource-request mechanism exists
    for this runner class).
  - `tests.yml` — full-matrix tests run only on
    `workflow_dispatch` (manual) and a daily cron, not on
    `pull_request` or `push`. Preset-specific bugs surface in
    the next morning's cron rather than on the PR that
    introduced them.
  - `stale.yml` — 365-day inactivity threshold. The threshold is
    long; a protocol-spec repo where issues legitimately span
    multiple fork timelines (12–18 months each) needs a long
    threshold, so the long value may be deliberate. The daily
    cron's cost is negligible.
  - `checks.yml:59–112` — PR title validation in inline bash,
    with regex such as `[^e]ed$` for past-tense detection,
    special-cased against "Embed" / "Shed". The regex is
    inspectable but each rule is a one-off without a shared
    naming-rules grammar.

- **No `Justfile`, no functioning `tox.ini`, no composite GitHub
  Action, no `pre-commit` config.** These are absences relative
  to the comparable repos; the Comparable contrast section below
  details what each absence corresponds to in `execution-specs`
  and `leanSpec`.

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

### Spec generator has two invocations of record

There are two entry points into `pysetup.generate_specs`. The
contributor path is `make _pyspec`, which depends on `_sync`
(running `uv sync --all-extras`) — i.e. development dependencies
are installed before the generator runs. The PyPI release
workflow (`.github/workflows/release.yml:145`) invokes the
generator differently: `uv run python -m pysetup.generate_specs
--all-forks` directly, followed by `uv build`. The release path
intentionally skips `_sync` to keep the build environment clean
of dev/test dependencies before `uv build` produces the
distributable wheel.

The two paths are therefore not redundant — they encode
different environment requirements. The maintenance note is that
both call sites invoke the same generator function, so a change
to the generator's signature, flags, or fork list must be
mirrored in both. The divergence is not currently documented at
either site; a brief comment cross-referencing the two ("the
release path skips `_sync` deliberately; see `Makefile:171–175`")
is the minimum-friction fix.

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

### Scripts: invocation paths and substitution options

Six standalone Python files live under `scripts/`. Their
invocation paths are:

- The four `check_*.py` / `fix_trailing_whitespace.py` scripts
  are called from `make lint` via `python script.py`. They are
  not registered as `[project.scripts]` entry points, not
  `pre-commit` hooks, not pytest plugins, and not ruff custom
  rules. Each reimplements file discovery
  (`pathlib.Path.rglob` with custom patterns) and argument
  parsing (`argparse`).
- `gen_spec_indices.py` is invoked indirectly: `mkdocs.yml:35–37`
  lists it under the `gen-files` plugin's `scripts:` array, so
  it runs as part of every mkdocs build (already in the
  `mkdocs-gen-files` plugin shape).
- `gen_kzg_trusted_setups.py` is an operational utility,
  regenerated when KZG ceremony parameters change. It is not on
  any routine path; placement under `scripts/` alongside
  routine-invocation scripts blurs that distinction.

Per-script options if the team wants to consolidate on more
declarative tooling. Each row notes the substitution shape and a
trade-off the team should weigh before adopting it.

| Script | Substitution option | Trade-off to weigh |
|---|---|---|
| `check_fork_comments.py` | `pre-commit` hook + `markdown-it-py` AST | `pre-commit`'s default model runs on staged files only; whole-tree checks need explicit `--all-files` invocation. The regex-against-lines approach misses code-fence boundaries; an AST walk shared with `pysetup/md_to_spec.py` is more robust. |
| `check_markdown_headings.py` | Same as above | Same; this script shares a heading-parser issue with `pysetup/md_to_spec.py`. |
| `check_value_annotations.py` | `ast.parse(mode="eval")` + `NodeVisitor` | The current `eval(expr, {"__builtins__": {}})` isn't a real sandbox. An AST-based validator is safer and exposes the same checks declaratively. |
| `fix_trailing_whitespace.py` | `pre-commit` hook (`trailing-whitespace`) | The pre-commit hook handles CRLF correctly (the script splits on `\n` and strips `\r`, silently converting CRLF files to LF). |
| `gen_kzg_trusted_setups.py` | Keep as operational utility; relocate to a clearly-labelled directory (e.g. `scripts/operational/`) | The script regenerates trusted setups when ceremony parameters change — not a candidate for CI automation. Moving it makes the "routine vs operational" distinction visible. |
| `gen_spec_indices.py` | Keep as-is — already in the `mkdocs-gen-files` plugin shape | No change needed; this script is already wired declaratively via `mkdocs.yml`. |

A caveat on adopting `pre-commit` widely: `pre-commit` creates
its own virtualenv per hook outside `uv`'s control, with its
own resolver and cache. If the team wants to centralise on `uv`
(see the fix-sketch Track A item on `[tool.uv]` and PEP 735
dependency groups), running checks through `pre-commit` works
against that centralisation. `ruff` custom plugins or
`pyproject.toml`-defined entry points are alternatives that
stay in the `uv` ecosystem.

`secondary-findings.md` catalogues the per-file smells inside
the scripts themselves — the table above answers "what shape
could these scripts move toward?"; the per-file findings answer
"what's worth fixing in each script as it stands?".

### `stale.yml` threshold

`stale.yml` runs daily with a 365-day inactivity threshold; issues
that go an entire year without activity are marked stale and
closed 30 days later. The threshold is long, and a defensible
reading is that a protocol-spec repo where issues legitimately
span multiple fork timelines (each 12–18 months) needs a long
threshold to avoid closing live design discussions. The cron's
CI cost is negligible. The item to surface is whether the
threshold matches the team's intent — a 365-day rule catches
only the oldest dead-zombie issues, which may or may not be the
intended scope.

### Workflows don't declare `concurrency:` groups

None of the eight workflows under
`consensus-specs/.github/workflows/` declares a `concurrency:`
block. A PR that gets pushed twice in five minutes runs the full
Python matrix twice, even though only the latest push will be
reviewed. `execution-specs` declares

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref || github.run_id }}
  cancel-in-progress: ${{ github.ref_name != github.event.repository.default_branch }}
```

on essentially every workflow — the pattern cancels stale runs on
PRs while leaving runs on the default branch untouched, so
`master` stays consistent. The change is a small per-workflow
addition with CI-minute savings on active PR threads.

Adjacent observation: `timeout-minutes` is absent from every
consensus-specs workflow, so all jobs default to GitHub's 6-hour
upper bound. `execution-specs` declares explicit per-job
`timeout-minutes` on long-running jobs (`benchmark.yaml: 720`,
`release_fixture_feature.yaml: 1440`) — useful for catching hung
jobs faster than the default and for documenting expected
runtime. Lower priority than the concurrency point.

## Named anti-patterns

- **Long Method** (Fowler, *Refactoring*, 1999, p. 76) at the recipe
  layer — `Makefile:201–220`'s `test:` target, with nine user-facing
  knobs and several derived variables expanded into a single
  `pytest` invocation.
- **Shotgun Surgery** (Fowler, p. 79) — every fork addition edits the
  `ALL_EXECUTABLE_SPEC_NAMES` list, the per-fork CI matrices, and the
  Makefile in tandem (the CI-bootstrap SHA upgrades are also
  multi-file but kept in sync by Dependabot/Renovate, so the cost
  there is smaller).
- **Inappropriate Intimacy** (Fowler, p. 85) — the Makefile knows the
  physical path of the package source (`PYSPEC_DIR`) and constructs
  Python dotted names from it via string substitution.
- **Stringly-Built Code** — `comptests.yml`'s bash+jq dynamic matrix
  has no preview surface; the Makefile's `$(subst)`-built mypy
  package name encodes the source layout in a substitution rule.
- **DRY violation** (Hunt & Thomas, Tip 11) — five-place fork list
  (cross-cuts with [fork-registration.md](fork-registration.md));
  the CI bootstrap appears in five workflow files (mitigated by
  Dependabot SHA syncing); six independent `argparse` declarations
  across `scripts/`.
- **Single Responsibility violation** (Martin, *Clean Code*) at the
  recipe level — `lint` mixes read-only checks with auto-fix steps,
  and its exit code stays 0 regardless.
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

The fixes split into two tracks. **Track A** ("within the existing
toolchain") tightens what's already there — same Make, same
scripts, same workflows — without changing the orchestration layer.
**Track B** ("modern declarative orchestrator") replaces the
Makefile with a Justfile in the style of `execution-specs`; most
of Track A's recipe-level fixes happen naturally inside the new
Justfile, while the cross-cutting fixes (composite actions,
concurrency, dependency groups) apply to either track.

### Track A — within the existing toolchain

Pragmatic improvements that don't require choosing a new
orchestrator. Each is independent; each lands as a single PR.

1. **Make `make lint` exit non-zero when it modifies files, or
   split it into `lint` and `fix`.** The single-line fix
   (`git diff --quiet ... || exit 1` after the chain) is the
   minimum: CI can then distinguish "passed clean" from "passed
   and reformatted". Splitting into separate `lint` (read-only)
   and `fix` (mutating) targets is the cleaner shape used by both
   comparables, but the one-line exit-code fix captures the
   load-bearing improvement on its own.
2. **Consider whether to consolidate `scripts/check_*.py`.**
   Options: leave them in place (they work, and they reuse code
   with `pysetup/`); rewrite them as `ruff` custom plugins or
   `pyproject.toml`-defined entry points (stays in the `uv`
   ecosystem); or move them to `pre-commit` hooks (introduces a
   parallel tool with its own virtualenv-creation outside `uv`'s
   control, which works against the `[tool.uv]`-centralisation in
   item 6). The choice depends on the team's appetite for
   adopting `pre-commit`. Either way: relocate
   `gen_kzg_trusted_setups.py` to a clearly-labelled operational
   directory so its non-routine status is visible (and leave
   `gen_spec_indices.py` where it is — it's already wired
   declaratively via `mkdocs.yml`).
3. **Consider a composite GitHub Action** at
   `.github/actions/setup-python-uv/action.yaml`. The current
   `setup-python` + `setup-uv` pair (~2 steps × 5 workflows)
   would consolidate into one referenced file. Trade-offs to
   weigh: composite actions have less-expressive per-step `if:`
   syntax and `outputs:` plumbing than job-level steps, and
   Dependabot updates SHAs *inside* composite actions on a
   different cadence than SHAs in workflow files. The savings
   are real but modest; Dependabot already keeps the existing
   multi-file SHAs in sync.
4. **Replace `comptests.yml`'s dynamic matrix** with an explicit
   `matrix.include` list (verbose but transparent) or a small
   Python helper invoked with a `--dry-run` flag that prints what
   the matrix would expand to.
5. **Add `concurrency:` blocks to every workflow** so superseded
   PR pushes cancel themselves but `master` runs never cancel.
6. **Add `[tool.uv]` and `[dependency-groups]` (PEP 735) to
   `pyproject.toml`.** Declare a `required-version` so a
   contributor's local `uv` is constrained the same way CI's is
   (CI is already pinned via `vars.UV_VERSION`; the contributor
   gap is the open one — `uv` refuses to run if the local
   version is older than the declared minimum). Declare
   workspace shape and named groups (`lint`, `test`, `docs`)
   rather than relying on extras-as-groups.
   `execution-specs/pyproject.toml:502–509` is the reference
   shape.
7. **Soften `make clean`.** Either replace `git clean -fdx` with
   a targeted cleanup of known artefacts (caches and generated
   dirs only), add a confirmation prompt, or split into
   `make clean` (targeted) and `make clean-all` (the current
   wholesale behaviour). The current recipe's help block warns
   the user, but the targeted variant removes the warning's
   load-bearing role.
8. **Document the spec generator's two invocations.** The
   release path's direct `python -m pysetup.generate_specs`
   invocation deliberately skips `_sync` to keep the build
   environment clean of dev/test dependencies before `uv build`;
   the contributor path runs `make _pyspec` which depends on
   `_sync`. A one-line comment at each call site cross-referencing
   the other captures the design intent without forcing the two
   paths to converge.
9. **Reconsider `stale.yml` if the threshold doesn't match
   intent.** A 365-day threshold may be deliberate for a
   protocol-spec repo with multi-year fork timelines, in which
   case leave it; if the intent was tighter triage, tightening
   the threshold to 30–60 days catches a different population of
   issues.
10. **Consider reducing the derived-variable count in
    `make test`.** Nine user-facing knobs are documented; the
    derived `MAYBE_*` / `COV_SCOPE_*` variables exist to expand
    those knobs into the final `pytest` command. `make -n test
    fork=... preset=... k=...` is the existing inspection
    mechanism. Splitting the recipe into sub-targets is one
    option; the smaller win is annotating the derived variables
    with comments tying each back to the user-facing knob it
    serves.

### Track B — modern declarative orchestrator (execution-specs style)

Replace the 332-line Makefile with a Justfile in the same shape
as `execution-specs/Justfile`. `execution-specs` itself
deliberately migrated *off* tox onto just (its `tox.ini` survives
only as a deprecation stub redirecting users at the new recipes)
— a useful data point that the audit's recommendation isn't
speculative.

#### The Justfile shape

execution-specs's Justfile uses a small set of just features that
together solve most of the orchestration debt:

- **`set positional-arguments := true`** at the top — recipes
  accept CLI arguments naturally via `"$@"`.
- **A `list` default recipe** annotated `[default, private]`
  running `@just --list` — running `just` with no args prints
  every recipe grouped by category. This is the read-the-pipeline
  surface a contributor cannot get from a 332-line Makefile.
- **Project variables at the top** (`root`, `output_dir`,
  `xdist_workers`, `evm_bin`, `latest_fork`) — explicit
  configuration in one block; environment variables read via
  `env("VAR", "default")`, no hidden Make conditionals.
- **`[group('...')]` annotations** on recipes — `[group('static
  analysis')]`, `[group('consensus tests')]`. `just --list`
  prints recipes grouped under their category headings, so a new
  contributor sees the taxonomy without reading recipe bodies.
- **A `[parallel]` composite recipe** for the common "run all
  checks" path:
  ```just
  [group('static analysis'), parallel]
  static: typecheck lint-spec spellcheck deadcode lint-actions \
          lock-check format-check lint
  ```
  Calling `just static` runs all eight checks in parallel; CI
  invokes this single recipe rather than chaining eight `run:`
  steps. The composite is read-only — `fix` is deliberately not
  in the list.
- **Read-only / mutating split made structural.** `lint` and
  `format-check` call `ruff check` / `ruff format --check`
  (no `--fix`); `fix` calls `ruff format` + `ruff check --fix`.
  The `static` composite depends only on the read-only recipes.
  CI runs `just static`; contributors run `just fix` when they
  want mutation. Track A item 1 ("split `lint` from `fix`")
  becomes structural here, not just a Make-recipe split.
- **Multi-line shell recipes** for cases where shell logic
  matters — `#!/usr/bin/env bash` shebang at the top of the
  recipe body, e.g. `spellcheck` prints a helpful "add to
  whitelist" message on failure rather than just exiting
  non-zero. Make can do this too, but the just syntax keeps the
  shell code visibly framed inside the recipe.

#### The composite GitHub Action

`execution-specs/.github/actions/setup-uv/action.yaml` is a
single composite action that installs `uv`, sets up Python via
`UV_PYTHON_PREFERENCE=only-managed`, and installs `just` via
`taiki-e/install-action`. Every workflow's `setup-python` +
`setup-uv` bootstrap pair collapses to one referenced step:

```yaml
- uses: ./.github/actions/setup-uv
```

The SHA pins for the underlying actions live in one file rather
than across multiple workflows. The trade-offs noted in Track A
item 3 (composite-action `if:` syntax limitations, slower
Dependabot cadence for SHAs inside composite actions) apply
here too; the benefit is the *contributor-facing* clarity of one
shared bootstrap, not raw upgrade-edit count.

#### Workflow invocations

Workflows call `just <recipe>` directly. The `static` job in
`execution-specs/.github/workflows/test.yaml`, for example, is
literally:

```yaml
- name: Run static checks
  run: just static
```

No `MAYBE_*` variable cascade, no shell-built mypy package
scope, no chained `python -m` invocations in the workflow YAML —
the workflow says *what* to run, the Justfile says *how*.
Workflows also gain `concurrency:` blocks
(`cancel-in-progress: ${{ github.ref_name !=
github.event.repository.default_branch }}`) and `paths-ignore`
filters for docs-only changes, both of which Track A also
recommends but which the execution-specs example exercises
inline.

#### Migration shape

The transition can be staged so Make and just coexist during the
move:

1. **Phase 0** — Introduce a `Justfile` with recipes that *call
   the existing Make targets*. `just test` becomes `make test
   "$@"`; `just lint` becomes `make lint`. Nothing breaks; the
   Justfile is a thin façade. Contributors can use either.
2. **Phase 1** — Introduce the composite GitHub Action; migrate
   one workflow at a time to call `just <recipe>` instead of
   `make <recipe>`. Each migration is one PR.
3. **Phase 2** — Move recipe bodies *into* the Justfile,
   inlining the underlying commands. The Makefile recipes
   become thin wrappers that call `just <recipe>`. At this
   point `just` is canonical; Make survives only for muscle
   memory.
4. **Phase 3** — Replace the Makefile with a deprecation stub
   (one-line message redirecting at `just`), or remove it.
   Update README to direct contributors at `just` and
   `just --list`. Same shape execution-specs used to migrate
   away from tox.

#### What Track B subsumes mechanically

- **A1 lint/fix split** — two named recipes, deliberately
  excluded from the `static` composite.
- **A10 derived-variable count in `make test`** — `just test
  fork=<f> preset=<p> k=<filter>` with positional arguments;
  no conditional-variable cascade. The same user-facing knobs
  remain; their expansion is in a single recipe body rather
  than spread across multiple Make variables.
- **A7 `make clean`** — a default-safe `just clean` (targeted)
  plus `just clean-all` (the wholesale variant) gives the
  user the choice the current single recipe doesn't.

#### What Track B does *not* subsume

A2 (`scripts/`), A3 (composite Action — already exists in
Track B but as a precondition), A4 (`comptests` matrix), A5
(`concurrency:` blocks), A6 (`[tool.uv]` and
`[dependency-groups]`), A8 (spec-generator invocation
documentation), and A9 (`stale.yml`) are orthogonal to the
orchestrator choice. Track B benefits from each as much as
Track A does, and they remain worth doing under either path.
A8 specifically: the deliberate environment difference between
the contributor and release paths persists regardless of
whether the orchestrator is Make or Just; Track B doesn't
"collapse" them, it just renames the contributor side from
`make _pyspec` to `just pyspec`.

#### The honest costs

- **`just` becomes a required tool** for contributors and CI
  runners. A single Rust binary, installable via brew, cargo,
  curl, or `taiki-e/install-action` in CI. The cost is real
  but small — comparable to the existing requirement of `uv`.
- **The Justfile takes effort to write.** Migrating 332 lines
  of Make to a Justfile is real work, even with the existing
  recipe surface as a template.
- **Two orchestration files during migration.** The Phase 0–2
  staging means contributors briefly see both Makefile and
  Justfile. Documentation should be clear about which is
  canonical when.
- **`just` is one more tool on top of an already-long stack.**
  Contributors to consensus-specs already work with `uv`,
  `mdformat`, `mypy`, `ruff`, `pytest`, `pysetup`, and
  `mkdocs`. Adding `just` to that stack is small in absolute
  terms but non-zero in onboarding terms; the team should
  weigh whether the orchestration-layer payoff justifies one
  more required tool.

The payoff is that the orchestration layer becomes readable,
parameterised, declarative, groupable, and parallelisable; a
contributor can run `just --list` to see every recipe rather
than reading 332 lines of Make.

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
