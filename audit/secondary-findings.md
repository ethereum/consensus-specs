# consensus-specs — secondary findings

This document catalogues the smaller-surface tech-debt items that
don't warrant their own deep-dive but are still worth fixing as the
team works through the items in [`README.md`](README.md). Each
finding is a single paragraph: what's wrong, where to find it in the
code, and the named anti-pattern. None of these is foundational; they
are mostly local cleanups that can land in single PRs.

The items are grouped by the area of the codebase they touch.

---

## Standalone scripts (`scripts/`)

Six free-standing Python scripts live under `scripts/`. The
build-orchestration deep-dive notes that each re-implements its own
argparse and that two are dead. Beyond the per-file smells listed
below, most of these scripts could be replaced wholesale by
existing tooling — pre-commit hooks, AST-based validators, or an
mkdocs plugin entry point. Per-script substitution analysis:

| Script | Replaceable by | Notes |
|---|---|---|
| `check_fork_comments.py` | `pre-commit` hook + `markdown-it-py` AST | The regex-against-lines approach with no code-fence awareness is a textbook case for a markdown-AST-based lint rule. |
| `check_markdown_headings.py` | Same as above | Already shares the heading-parser issue with `pysetup/md_to_spec.py`; both could share an AST walker. |
| `check_value_annotations.py` | `ast.parse(...)`-based validator | The `eval()` sandbox attempt is well-known not-actually-sandbox; `ast.parse(mode="eval")` plus a `NodeVisitor` is the correct shape. |
| `fix_trailing_whitespace.py` | `pre-commit` hook (`trailing-whitespace`) | Already noted below — the pre-commit hook handles CRLF correctly, the script doesn't. |
| `gen_kzg_trusted_setups.py` | Dead per build-orchestration | Just delete. KZG library distributions ship trusted setups directly. |
| `gen_spec_indices.py` | `mkdocs-gen-files` plugin entry-point | Already uses `mkdocs_gen_files`; could be an `mkdocs.yml` plugin entry rather than a separately-invoked script. |

The file-specific smells inside the scripts themselves follow.

### `check_fork_comments.py` walks the entire repo on no-args invocation

`scripts/check_fork_comments.py:111–115` defaults to
`Path(".").rglob("*.md") | "*.yaml" | "*.yml"` when called with no
arguments, with no exclusion list — `node_modules/`, `.venv/`,
generated pyspec output, or any vendored YAML the project later
acquires get scanned. The script also catches `UnicodeDecodeError`
and silently returns an empty violation list (line 18), so a binary
YAML that happens to match the extension fails open. Hunt & Thomas
Tip 38 (Configure, don't integrate) violation.

### `check_fork_comments.py` regex matches inside Python string literals

`scripts/check_fork_comments.py:23` uses
`r"\[(\w+)\s+in\s+(\w[\w:_-]*)\]"` against entire lines, then
post-hoc tries to detect "this is in a Python comment" by searching
for a `#` before the match (line 69). A string literal `"[New in
Phase0]"` inside spec markdown's Python code blocks, or an
inline-mathematical bracket, would fire a false positive — the
parser doesn't know about code fences. A markdown AST walk like
`md_to_spec.py` already uses would be cheap to share.

### `check_markdown_headings.py` toggles `in_code_block` on every triple-backtick

`scripts/check_markdown_headings.py:33–34` flips `in_code_block`
whenever a line starts with ` ``` `, with no language detection and
no handling of fence-length variation (`~~~` or four backticks for
nested blocks). A heading inside a four-backtick block is processed
as a real heading; a closing fence with trailing text is ignored.
Same shape as `md_to_spec.py`'s heading parser, but here in a
separate script that doesn't share infrastructure.

### `check_value_annotations.py` uses `eval()` with a stripped-down builtins dict

`scripts/check_value_annotations.py:48` runs `eval(expr,
{"__builtins__": {}}, {})` on values extracted from spec markdown.
The intent is sandboxing, but `__builtins__: {}` does not block
dunder-attribute access on literal types, and a malformed expression
silently returns `None` and the violation is missed. The deeper
smell is that "is this expression valid?" is decided by `eval`
instead of by AST traversal; `ast.parse(expr, mode="eval")` followed
by a `NodeVisitor` would be both safer and checkable.

### `fix_trailing_whitespace.py` shells out to `git ls-files` instead of using a library

`scripts/fix_trailing_whitespace.py:10–15` invokes
`subprocess.run(["git", "ls-files", "--cached", "--others",
"--exclude-standard"])` to enumerate files. The script implicitly
assumes `git` is on `PATH`, that the CWD is a git checkout, and that
the user wants every tracked file rewritten in place — a silent
in-place edit on a developer machine with un-committed generated
files. There is no `--dry-run`. `pre-commit` already provides a
vetted trailing-whitespace hook.

### `fix_trailing_whitespace.py` silently strips CRLF line endings

`scripts/fix_trailing_whitespace.py:27` does `lines =
original.split('\n')` then `'\n'.join(...)` — Windows-style `\r\n`
survives the split as a `\r` at the end of each "line" and gets
stripped, silently converting CRLF files to LF on disk. A
contributor on Windows would see every CRLF file rewritten.
`splitlines(keepends=True)` plus per-line `rstrip(' \t')` preserves
line endings.

### `gen_kzg_trusted_setups.py` argparse lives inside `if __name__ == "__main__":`

`scripts/gen_kzg_trusted_setups.py:9–43` puts the argparse
construction inside the `if __name__ == "__main__":` guard, so the
script offers no `main()` entry point that other code (or tests)
could call. The script is dead per build-orchestration but the
structure itself is the smell: argparse-in-main precludes
unit-testing the CLI parser, and the absence of a return-code
contract means a CI invocation can't distinguish "secret was
invalid" from "I/O failed".

### `gen_spec_indices.py` has top-level executable code outside any function

`scripts/gen_spec_indices.py:109–139` runs `print(...)`, populates
`spec_forks`, and calls `generate_pages_recursively` at module
import time. There is no `if __name__ == "__main__":` guard and no
`main()`. Importing this module for any reason (linting, IDE
indexing) executes the full generation pipeline and writes files
via `mkdocs_gen_files.open`. The import-time side-effect is a
secondary smell that compounds the "is this still used?" question
because static analysers can't tell whether the side effect is
intentional.

### `gen_spec_indices.py` hardcodes `_deprecated` as the only excluded fork directory

`scripts/gen_spec_indices.py:115` skips `specs/_deprecated/` via a
literal `{"_deprecated"}` set; `_features/` is *not* skipped, so
the script will happily index experimental fork directories
alongside mainline ones with no visual distinction. Adding another
excluded directory is Shotgun Surgery on a literal set deep inside
a recursive helper — same shape as `IGNORE_SPEC_FILES` in
`md_doc_paths.py:31`: two ignore-lists, two formats, no shared
truth.

### Three `check_*.py` scripts share a copy-pasted output template

`scripts/check_fork_comments.py:127–131`,
`scripts/check_markdown_headings.py:82–87`, and
`scripts/check_value_annotations.py:172–176` each end with the same
loop printing `f"File: {v['file']}:{v['line']}\nContent:
{v['content']}\nMessage: {v['message']}\n"` and then `sys.exit(1)`.
The "violation" dict shape is duplicated three times with no shared
dataclass; adding a `severity` or `column` field requires editing
all three scripts. Duplicated Code at the "linter framework" level.

### `check_*.py` exit on first batch instead of returning structured results

All three checkers (`check_fork_comments.py:133`,
`check_markdown_headings.py:88`, `check_value_annotations.py:178`)
call `sys.exit(1)` inside `main()` rather than returning an int and
letting the entry point exit. Tests cannot import-and-call `main`
without trapping `SystemExit`, and a future "check all three at
once" runner has to spawn subprocesses to recover the violation
list. Inappropriate Intimacy with the process-exit mechanism.

---

## Per-fork test layout (`tests/core/pyspec/.../test/<fork>/`)

### Same-file-name-across-forks with inconsistent decorators

`phase0/sanity/test_blocks.py` (~43 KB, ~44 `@with_all_phases`
decorators) runs against all forks; `altair/sanity/test_blocks.py`
(~4.6 KB) uses `@with_altair_and_later`; `electra/sanity/` has no
top-level `test_blocks.py` (moved to `blocks/test_blocks.py`);
`gloas/sanity/test_blocks.py` (~16 KB) uses `@with_gloas_and_later`.
The same logical file name lives in multiple forks with different
decorators and import sets — unintentional WET.

### Decorator-parameterisation obfuscates fork applicability

Tests in different fork directories use different decorator forms:
`@with_all_phases`, `@with_altair_and_later`, `@with_electra_and_later`.
Fork scope is scattered across three layers — decorator choice,
module location (fork name in path), and inline conditionals (`if
is_post_electra(spec)`). A test reader can't immediately know
whether a fork-named test runs *only* for that fork or for that
fork onward, and the operational costs compound: (a) reviewer
cognitive load — a test in `electra/` decorated `@with_all_phases`
will run for phase0, altair, etc., surprising if the path implies
"electra-only"; (b) skip-detection failure — when CI runs only one
fork (`make test-electra`), the reader can't tell from the test
source whether their change is being exercised; (c) fork-addition
tax — adding a new fork forces an audit of every
`@with_X_and_later`-decorated test to decide whether the new fork
should be in scope, and the path layout doesn't help locate them;
(d) refactor risk — moving a test from `phase0/` to `altair/`
because "altair changed it" doesn't change the decorator, so the
test silently keeps running for phase0 unless the maintainer
remembers the second edit.

### `unittests/` as informal subcategory with semantic confusion

`phase0/unittests/` contains spec unit tests
(`test_config_invariants.py`, `fork_choice/`, `math/`, `validator/`);
the rest of `phase0/` (`sanity/`, `block_processing/`, …) is *also*
testing spec logic. The boundary is loose. Per-fork `unittests/`
directories shrink (`electra/unittests/` only has three files) and
drift in scope. Speculative Generality (Fowler).

### `transition/` vs. `fork/` directory split: undocumented cross-reference

`fork/` (test directory, singular) corresponds to
`tests/formats/forks/` (format spec, plural) — tests that exercise
the `upgrade_<fork>` function in isolation: one pre-state, one
upgrade call, one post-state, with `meta.yaml` carrying just
`fork: str`. `transition/` (test directory, matching
`tests/formats/transition/`) is a different vector format
entirely: tests that exercise *chain processing across* a fork
boundary, with `meta.yaml` carrying `post_fork`, `fork_epoch`,
`fork_block`, `blocks_count` and multiple blocks processed under
two specs. Phase0 has neither; later forks have both. The two
formats are documented in `tests/formats/{forks,transition}/README.md`,
but the test tree itself contains no pointer to those format
specs, and the singular/plural naming inconsistency
(`fork/`-test ↔ `forks/`-format) makes the relationship harder
to discover. Divergent Change (Fowler) at the *naming* layer
rather than the format layer.

### Block-processing tests reflect fork divergence with no inheritance rule

`phase0/block_processing/` has 7 files (`test_process_attestation.py`
~598 lines, `test_process_deposit.py`, …); `altair/block_processing/`
has 2 (one is `test_process_deposit.py` ~26 lines delegating to
phase0 helper); `electra/block_processing/` has 6 much shorter files
focusing on consolidation/withdrawal-request deltas. This is
intentional WET, but no clear inheritance rule exists; refactoring
to composition would reduce the duplication mass.

### Phase0 as monolithic baseline; other forks override by copy

`phase0/` (~85 files) is a monolithic baseline; later forks
selectively re-implement. There is no Python inheritance mechanism
— forks copy. Example: `phase0/sanity/test_blocks.py` (~44 tests
with `@with_all_phases`) implicitly applies to altair+;
`altair/sanity/test_blocks.py` redefines with `@with_altair_and_later`.
A `git diff` shows two largely different files that semantically
encode a fork-aware subset — Duplicated Code at scale.

### 119 `__init__.py` files load-bearing because of `importmode=prepend`

The test tree has 119 empty `__init__.py` files. They are *not*
vestigial: `pyproject.toml:60–62` does not set
`importmode = "importlib"`, so pytest runs on the default `prepend`
mode and registers each `test_*.py` under its short module name in
`sys.modules`. The codebase has many duplicate filenames across
forks (`test_blocks.py` in every fork's `sanity/`,
`test_process_deposit.py` in every fork's `block_processing/`,
etc.), so the `__init__.py` files are what turn each directory into
a regular package and let the *full* dotted path
(`tests.core.pyspec.…test.altair.sanity.test_blocks`) disambiguate
the modules. Switching to `importmode = "importlib"` is the modern
recommendation and would let the 119 boilerplate files be removed
in a single follow-up pass — the cleanup is a config change first,
not a file-deletion. `importlib` is better than `prepend` for two
load-bearing reasons: (a) it loads each test under a unique
synthetic module name derived from its full path, so duplicate
file names across forks need no `__init__.py` to disambiguate; and
(b) it doesn't manipulate `sys.path`, whereas `prepend` actually
prepends each test directory to `sys.path` and lets stray helper
modules in one directory be reached from elsewhere with surprising
results. It's the pytest-recommended setting for new projects;
`prepend` is the global default only for backwards compatibility
with projects that depended on the `sys.path` side effect.

### Fork drift and incomplete fork-scoped coverage

`phase0` has 15 subdirs; `heze` has only `unittests/`; `eip7732` has
only `block_processing/`. These incomplete forks may be experimental
or deferred upgrades, yet they occupy slots in the fork tree without
status markers (draft / experimental / stable / deprecated). If a
fork is later completed, adding missing test directories is Shotgun
Surgery; if abandoned, the empty directories are dead code.

### Naming collision: `test_blocks.py` in two paths under Electra

`tests/core/pyspec/.../sanity/test_blocks.py` exists for phase0,
altair, bellatrix, deneb, gloas; `tests/core/pyspec/.../electra/sanity/blocks/test_blocks.py`
is one level deeper. Same logical category, different path
structure. Principle of least surprise violated.

---

## Per-fork test bodies — in-test patterns

These are anti-patterns inside individual `test_*.py` files (rather
than the directory layout above). They are mostly small, mechanical
fixes that can land in dedicated PRs.

### Bare `assert` without messages throughout block-processing tests

Every assertion in `phase0/sanity/test_blocks.py` is a naked `assert`
with no failure message — examples include `assert state.slot ==
block.slot` (line 101), `assert state.eth1_data.block_hash == a`
(line 1198), and the loop-body `assert state.balances[index] <
pre_balances[index]` (line 444). When a vector-generation run fails
on the mainnet preset, pytest reports only the source line — the
reader cannot tell *which* invariant tripped without re-reading the
surrounding code. `pytest`'s `assert msg` form, or `pytest.approx` /
`pytest.raises(... match=...)`, would self-document the same checks.

### Magic byte literals as test sentinels

`phase0/sanity/test_blocks.py:272` (`block.state_root = b"\xaa" *
32`), `:522–530` (`random_root=b"\xaa"*32`, `b"\xbb"*32`), `:1184–1186`
(three sentinels `a/b/c = b"\xaa"*32`/`b"\xbb"*32`/`b"\xcc"*32`),
`fork_choice/test_on_block.py:176` (`b"\x45" * 32`), `:217`
(`b"\x12" * 32`), and `gloas/sanity/test_blocks.py:289`
(`spec.Hash32(b"\x42" * 32)`) all use ad-hoc byte-pattern sentinels
with no shared definition. The patterns drift across files. Primitive
Obsession (Fowler) plus DRY violation. A `helpers/sentinels.py` with
named factories would centralise the convention.

### Hidden coupling on a module-global non-deterministic RNG

`phase0/fork_choice/test_on_block.py:48` instantiates a *module-level*
`rng = random.Random(2020)` and the helper `_drop_random_one_third`
(line 51) closes over it. Every test in the file that triggers
`_drop_random_one_third` *consumes* RNG state, so the sequence each
test sees depends on the order in which earlier tests ran. Beck's
FIRST violated twice — Self-validating (a flake here is invisible)
and Isolated (test order changes outcomes). Each test that needs
randomness should own its `Random(seed)`.

### Manual try/except instead of `pytest.raises`

`phase0/unittests/math/test_integer_squareroot.py:26–32` uses the
`bad = False; try: ...; bad = True; except ValueError: pass; assert
not bad` idiom to assert a function raises `ValueError`. This is a
hand-rolled negation of `pytest.raises(ValueError)`, requires four
extra lines, and silently absorbs *any* exception other than
`ValueError` (it never re-raises). The same anti-pattern appears
implicitly across the `expect_assertion_error(lambda: ...)` calls
in `phase0/sanity/test_blocks.py` (lines 84, 209, 275, 289, 309).

### Loop-as-parametrize: four `test_full_random_operations_N`

`phase0/sanity/test_blocks.py:1247–1267` defines four near-identical
test functions that differ only in the `Random(2020 / 2021 / 2022 /
2023)` seed argument to a shared helper. This is a textbook
`@pytest.mark.parametrize("seed", [2020, 2021, 2022, 2023])` —
duplicated four times, with the only signal of the duplication being
the `_0`/`_1`/`_2`/`_3` suffix. The same shape recurs as
`test_missed_payload_next_block_*` in `gloas/sanity/test_blocks.py:131–246`.

### Long Method test functions exceed 100 lines and test multiple things

`altair/light_client/test_sync.py:49–289` is a single 240-line
`test_light_client_sync` that walks through *seven* labelled
scenarios separated only by ASCII-art comments. A failure on
scenario 5 reports `test_light_client_sync` failed — the operator
must read 200 lines of preceding state-mutation to localise the
regression. Long Method (Fowler) + SRP violation; each ASCII-art
comment block is begging to be a parametrised case or a separate
test.

### `dump_skipping_message` as a prose-conditional skip

`phase0/sanity/test_blocks.py:424–428`, `:625–628`, `:653–656`,
`:701–704` perform `if <condition>: return dump_skipping_message("...")`
inside the test body, returning *before* any `yield "pre"`. The test
*passes* in pytest's eyes but emits no vector — the skip is
invisible to `pytest -ra` and to CI dashboards, and the skip reason
isn't attached to the test as a marker. `pytest.mark.skipif` (or
the existing `@with_presets` decorator) would surface the skip
properly.

### `state.copy()` boilerplate as missing fixture

`phase0/sanity/test_blocks.py:474, 599, 659, 707, 878` repeat
`pre_state = state.copy()` to capture pre-conditions for a
post-block-processing assertion (variants: `pre_balances =
list(state.balances)` at 431; `pre_historical_roots =
state.historical_roots.copy()` at 1146). The pattern is duplicated
in ~10 tests because there is no `pre_state` fixture. A
`@pytest.fixture def pre_state(state)` or a helper context manager
would replace ~20 lines of boilerplate.

---

## Helper modules — smaller files

The helper-layer deep-dive covers the largest files. The items below
are smaller files in the same tree that have their own concentrated
issues.

### Empty `helpers/das.py` shipped as a placeholder

`tests/core/pyspec/eth_consensus_specs/test/helpers/das.py` is zero
bytes. Nothing imports it, no `# TODO` comment explains its
purpose, and no other helper references the module name — yet a
sibling test tree at `test/fulu/unittests/das/test_das.py` exists
that one might reasonably expect to be supported by it. An empty
module that the package layout treats as live is either
Speculative Generality (Fowler, *Refactoring*, 1999, p. 109) or a
forgotten scaffold. Delete it, or make the placeholder intent
explicit.

### `helpers/shard_block.py` is dead code from an abandoned phase

`helpers/shard_block.py:1–91` defines `PowChain`, `sign_shard_block`,
`build_shard_block`, `get_shard_transitions`, and friends against
`spec.ShardBlock`, `spec.MAX_SHARDS`, `spec.get_shard_proposer_index`
— spec symbols that don't exist in any current fork. A recursive
grep across `tests/` finds zero importers. Dead Code (Fowler, p. 87)
carried forward from an abandoned sharding proposal (Phase 1).

### `helpers/block_processing.py` dispatch table references nonexistent spec functions

`helpers/block_processing.py:18–19` registers
`"process_shard_header" → spec.process_shard_header` and `:35–37`
registers `"process_application_payload" → spec.process_application_payload`.
Neither symbol exists on any current fork's spec. The hidden
contract at line 61 (`if hasattr(spec, name): call(state, block)`)
silently skips them, deferring `AttributeError` to a code path
nothing reaches. Stringly-typed dispatch plus "hasattr-as-error-
suppression" (Inappropriate Comment, Martin, *Clean Code*, ch. 4).

### `helpers/payload_attestation.py` imports from a *test* module

`helpers/payload_attestation.py:1–3` does
`from eth_consensus_specs.test.gloas.block_processing.test_process_payload_attestation import prepare_signed_payload_attestation`.
The dependency direction is inverted: the helper layer (the
*substrate* of all tests) reaches into a single fork's test suite for
a construction routine. If the test file is renamed, deleted, or
moved, every consumer of `get_random_payload_attestations` breaks.
Inappropriate Intimacy at module level + DIP violation.

### `helpers/specs.py` builds the spec registry via `exec`/`eval`

`helpers/specs.py:14–24` does
`exec(f"from eth_consensus_specs.{fork} import …")` in a loop, then
`eval(f"spec_{fork}_minimal")` to populate `spec_targets`. This is
the canonical "metaprogramming used to avoid writing 16 imports"
smell — Pyright cannot type the resulting dict, "go to definition"
lands nowhere, and a typo in `ALL_PHASES` surfaces only at runtime
as `NameError`. Stringly Typed (Fowler). A literal
`importlib.import_module` table would be both safer and shorter.

### `helpers/keys.py` allocates 8 192 BLS keypairs at import time

`helpers/keys.py:11–13` computes `pubkeys = [bls.SkToPk(privkey) for
privkey in privkeys]` for `privkeys = [i + 1 for i in range(32 *
256)]` — 8 192 BLS public-key derivations executed unconditionally
during `import …helpers.keys`. Forty-three modules import this file;
pytest collection therefore pays the key-derivation cost even for
runs that never need a signature. Pragmatic Programmer Tip 17 —
"Eliminate effects between unrelated things". A lazy `pubkey(i)`
accessor would make the cost pay-as-you-use.

### `helpers/typing.py` declares a `Spec` Protocol used in one place

`helpers/typing.py:12–18` declares `Configuration` and `Spec`
Protocols. The only consumer is the `dict[…, Spec]` annotation on
`spec_targets` in `helpers/specs.py:21`. Forty-nine top-level helper
modules accept a `spec` parameter and *none* of them annotate it as
`Spec`. The Protocol is structurally too narrow to be useful (it
asserts only `spec.fork: str` and `spec.config.PRESET_BASE: str`)
and broadly unused — Speculative Generality at the type level.

### `helpers/forks.py` is a `is_post_<fork>` constant ladder rebuilt by hand

`helpers/forks.py:32–65` defines nine separate `is_post_<fork>(spec)`
predicates, each a one-line wrapper around `is_post_fork(spec.fork,
FORK_CONSTANT)`. Adding a fork requires adding one constant in
`constants.py`, one entry in `PREVIOUS_FORK_OF`, *and* one new
predicate function here, then importing it across ~15 helpers. A
`make_is_post(fork)` factory or a single `is_post(spec, fork)` call
site would eliminate them.

### `helpers/forks.py` recursive `is_post_fork` is fork-count-quadratic

`helpers/forks.py:16–29`'s `is_post_fork(a, b)` walks
`PREVIOUS_FORK_OF` recursively to determine ordering. Each
`is_post_<fork>(spec)` call therefore runs a chain walk in the worst
case (e.g. `is_post_altair` on a heze spec walks 8 dict lookups).
With 25+ `is_post_*` calls in `rewards.py` alone, the per-test
overhead is non-zero. Primitive Obsession — fork ordering is encoded
as a linked-list of strings, not as a total-order over a small enum;
a precomputed rank table would make comparison O(1).

### `helpers/inactivity_scores.py` ignores its parameters

`helpers/inactivity_scores.py:4–11` defines
`randomize_inactivity_scores(spec, state, …)` and
`zero_inactivity_scores(spec, state, rng=None)`; neither uses
`spec`, and `zero_inactivity_scores` accepts `rng=None` it never
references. Long Parameter List (Fowler, p. 78) at micro-scale —
parameters that exist only to satisfy "all helpers take
`(spec, state)`" convention. The signature lies.

### `helpers/block.py` uses a `proposer_index` parameter that the indirection ignores

`helpers/block.py:132–133` defines
`get_beacon_proposer_to_build(spec, state, proposer_index=None):
return spec.get_beacon_proposer_index(state)`. The function takes a
`proposer_index` argument and discards it — every caller's override
is silently dropped. The single call site at line 100 supplies a
proposer index that gets thrown away. Either Dead Parameter or a
latent bug; the indirection adds nothing beyond the bare
`spec.get_beacon_proposer_index(state)` call.

### `helpers/inclusion_list.py` monkey-patches the spec module to install a cache

`helpers/inclusion_list.py:131–149`'s `run_with_inclusion_list_store`
saves `spec.cached_or_new_inclusion_list_store`, replaces it with an
`@lru_cache(maxsize=1)` wrapper, runs `func()`, and restores the
original in a `try/finally`. The spec module is global state; if
`func()` spawns a thread that calls the spec function, the patched
cache leaks. A pytest fixture that *injects* a fresh store per test
would eliminate the global mutation.

### `helpers/{altair,bellatrix,...}/fork.py` are seven near-clones

The seven `helpers/<fork>/fork.py` files all define
`run_fork_test(post_spec, pre_state)` with the same skeleton: yield
`pre`, call `post_spec.upgrade_to_<fork>(pre_state)`, assert each
field in `stable_fields` is unchanged, assert `fork` changed,
assert version constants match, yield `post` (`altair/fork.py:6–47`,
`gloas/fork.py:10–86`). Only `stable_fields`, the `upgrade_to_X`
symbol, and the version constant differ. Duplicated Code (Fowler,
p. 76) at the file level; a parametrised
`run_fork_test(post_spec, pre_state, fork_name)` would replace all
seven.

### Per-fork helper subdirs hold one or two tiny files each

`helpers/altair/`, `bellatrix/`, `capella/`, `deneb/`, `electra/`
each contain a single `fork.py` plus an empty `__init__.py`;
`helpers/fulu/` and `helpers/gloas/` add one `state.py` (6 and 16
lines respectively). Seven directories created so 7×~50 LOC of
fork-specific glue can hide behind a `helpers.<fork>` namespace.
Speculative Generality at the directory level. A flat
`helpers/per_fork.py` parametrised on fork-name would carry the
same content with none of the directory-tree overhead.

### `helpers/fulu/state.py:initialize_proposer_lookahead` duplicates spec logic

`helpers/fulu/state.py:1–6` defines `initialize_proposer_lookahead`
whose body is a hand-written translation of the spec function of the
same name — `eth_consensus_specs/eip8025/minimal.py:8021` defines
the actual `initialize_proposer_lookahead(...)`. Two Sources of
Truth — a bug fix in one silently desynchronises the other. The
deeper question is *why* a test helper hand-writes a spec routine;
"the function doesn't exist on fulu yet, only on eip8025" is the
answer, but no comment says so.

### `helpers/constants.py` mixes fork identifiers, presets, and `UINT64_MAX`

`helpers/constants.py` declares fork-name string constants (lines
8–19); fork groupings (`MAINNET_FORKS`, `ALL_PHASES`,
`LIGHT_CLIENT_TESTING_FORKS`, `TESTGEN_FORKS`,
`ALLOWED_TEST_RUNNER_FORKS` — six overlapping subsets, lines 26–44);
two more dicts (`PREVIOUS_FORK_OF`, `POST_FORK_OF`, lines 47–85);
and `UINT64_MAX` (line 99, used by a single test). Three unrelated
domains in one file — Divergent Change (Fowler).

### `helpers/epoch_processing.py` dispatch order encodes fork ordering as conditional list elements

`helpers/epoch_processing.py:7–38`'s `get_process_calls(spec)` is a
list whose entries are sometimes plain strings and sometimes
`(post_fork_name if is_post_<fork>(spec) else pre_fork_name)`
ternary expressions (lines 25–35). The list is consumed by
`hasattr(spec, name)` filtering downstream (line 53), so unknown
items silently disappear. Switch Statements (Fowler) embedded in a
data structure — the comments at lines 24, 30, 36, 37 are
Inappropriate-Comment-as-Deodorant for what the code can't say.

### `helpers/voluntary_exits.py` hard-codes `CAPELLA_FORK_VERSION` for post-Deneb domains

`helpers/voluntary_exits.py:24–29` reads
`spec.config.CAPELLA_FORK_VERSION` when `is_post_deneb(spec)` — the
"voluntary-exit domain stays pinned to Capella in Deneb+" rule
expressed as a literal config-attribute lookup. The rule is correct
on Deneb through Heze; if a future fork changes the domain pinning,
the silent fall-through here will produce invalid signatures with
no test failure at the helper layer. A
`get_voluntary_exit_fork_version(spec)` keyed off the
`PREVIOUS_FORK_OF` graph would localise the rule.

### `helpers/gossip.py:get_filename` is a string-substring switch statement

`helpers/gossip.py:34–62` derives a filename prefix by chained
`if "BeaconBlock" in class_name … elif class_name == "Attestation"
… elif "AggregateAndProof" in class_name …` — eight branches,
mixing substring containment and equality. Adding a new SSZ-typed
gossip object requires adding a branch *and* keeping the comment
grouping correct. Switch Statements (Fowler, p. 82); a registry
keyed on the SSZ type itself would let each gossip module register
its filename when it loads.

### `helpers/block_header.py` is an 11-line file for one stand-alone signing helper

`helpers/block_header.py:1–11` contains only `sign_block_header`,
which constructs a domain, signs, and returns a
`SignedBeaconBlockHeader`. It does not coordinate with `block.py`,
share a domain helper, or fit a `signers/` interface — it's a
dedicated module for one short function. Speculative Generality at
the file level; would naturally live beside `sign_block` in
`block.py` or a future `helpers/signing.py`.

---

## Spec utilities (`utils/`, `debug/`, `config/`)

The helper-layer deep-dive covers `tests/core/pyspec/.../test/helpers/`.
The sibling subtrees `utils/`, `debug/`, and `config/` were not
deep-dived.

### Sub-package `__init__.py` files expose no public API

`tests/core/pyspec/eth_consensus_specs/utils/__init__.py`,
`debug/__init__.py`, `utils/ssz/__init__.py`, and
`config/__init__.py` are all empty regular-package markers. They
need to exist (setuptools' `find_packages()` discovers regular
packages by walking for `__init__.py`, and the file gives mypy /
sphinx / IDE jump-to-definition the path of least surprise), but
they could host a curated `__all__` plus re-exports so callers
could write `from eth_consensus_specs.debug import encode, decode`
instead of `from eth_consensus_specs.debug.encode import encode`.
Missed ergonomics opportunity rather than dead weight — the file
isn't the smell, the empty body is.

### Stringly-typed BLS-backend selection via four global toggles

`utils/bls.py:84–121` exposes `use_milagro()`, `use_arkworks()`,
`use_py_ecc()`, and `use_fastest()` — each mutates two module-level
`global` variables (`bls`, `Scalar`). Every BLS call site then
branches on `if bls == arkworks_bls or bls == fastest_bls` (lines
144, 222, 241, 252, 270, 348, 359, 373, 387) — Switch Statement
(Fowler) repeated across ~12 functions. Adding a fifth backend is
Shotgun Surgery; mutating globals from test setup is exactly Hunt &
Thomas Tip 17 ("Eliminate effects between unrelated things"). A
`BLSBackend` Strategy would replace the toggle-and-branch idiom.

### `except Exception: result = False` swallows all BLS failures

`utils/bls.py:148–149`, `:160–161`, and `:172–173` each wrap the
verifier call in a bare `except Exception:` that converts *any*
failure (including `ImportError`, `AttributeError`, malformed
inputs, or a backend panic) into `result = False`. A test that
should distinguish "signature is invalid" from "the BLS library blew
up" cannot — both surface as `False`. Catching `BLSError` (or
backend-specific exceptions) would distinguish negative results from
genuine failures.

### `only_with_bls` decorator hides a runtime global toggle

`utils/bls.py:124–138` defines a decorator that wraps each of
`Verify`, `Aggregate`, `Sign`, `SkToPk`, `KeyValidate` in a closure
that reads the module-global `bls_active` flag at call time. Whether
a BLS function runs depends on a global set by direct attribute
assignment (`bls_active = ...`). The decorator name suggests guard
behaviour but its semantics is "silently return a stub if BLS is
off". Inappropriate Intimacy with `bls_active`; a context manager
(`with bls_disabled(): ...`) would scope the off state explicitly.

### Hardcoded `STUB_*` constants couple BLS stub mode to spec wire shapes

`utils/bls.py:78–81` defines `STUB_SIGNATURE = b"\x11" * 96`,
`STUB_PUBKEY = b"\x22" * 48`, and `G2_POINT_AT_INFINITY` as literal
byte patterns. The values 96 and 48 are Magic Numbers (Fowler); the
filler bytes and the infinity-point encoding are domain knowledge
that belongs in the spec, not in a test util. A spec-imported
constant plus a named factory `make_stub_signature(spec)` would
remove the duplication and prevent silent drift if a fork ever
changed BLS output sizes.

### `dump_kzg_trusted_setup_files` mixes filesystem I/O, side effects, and crypto

`utils/kzg.py:92–125` is a single 33-line procedure that mutates a
global by calling `bls.use_fastest()`, generates two trusted setups,
computes Lagrange basis and roots of unity, hex-encodes everything,
creates a directory, `print()`s to stdout (lines 110, 125), and
writes a JSON file. SRP violation; `print` for status reporting in a
library function is awkward whenever called from a test. Splitting
into `generate_setup_payload(...)` + `write_setup(payload, path)`
would make each piece testable.

### `hash` shadows the builtin in a one-liner module

`utils/hash_function.py:8` defines `def hash(x: bytes | bytearray |
memoryview) -> Bytes32:` which shadows Python's builtin `hash()`.
Anyone doing `from eth_consensus_specs.utils.hash_function import *`
ends up with a name ambiguous at every call site — is this
`builtins.hash` or the SSZ sha256 wrapper? The 10-line module exists
solely to wrap one `sha256(x).digest()` call; rename to
`sha256_bytes32` or inline at call sites.

### `merkle_minimal.py` precomputes 100 zerohashes at import time

`utils/merkle_minimal.py:7–9` runs a 99-iteration `for layer in
range(1, 100)` loop unconditionally at import, materialising 100
hashes worth of `sha256` calls every time the module is loaded. The
depth `100` is a Magic Number with no comment; the SSZ tree depth
needed for any current fork is much smaller. A lazy
`@functools.cache`-d `zerohash(depth)` would defer the work and
eliminate the magic number.

### `ssz_impl.py` defines four-name aliases for two SSZ operations

`utils/ssz/ssz_impl.py:8–21` defines `ssz_serialize`, `serialize`,
`ssz_deserialize`, and `deserialize` — two pairs where each member
is a one-line call to the other. There is no docstring explaining
when a caller should use the prefixed vs. the unprefixed name; both
forms are in active use across the repo. Two Sources of Truth (Hunt
& Thomas) for one operation, with no deprecation marker. Pick one
name, alias the other with a `DeprecationWarning`.

### `ssz_typing.py` is a re-export shim with `# ruff: noqa: F401`

`utils/ssz/ssz_typing.py:1` opens with `# ruff: noqa: F401`,
silencing unused-import lint, then 36 lines of pure re-exports from
`remerkleable.*` plus two local aliases (`Bytes20`, `Bytes31`). The
module exists solely to centralise SSZ-type imports but offers no
abstraction over `remerkleable` — Speculative Generality (Fowler).
The `# type: ignore` comments on the local aliases hint that even
they fight the type system.

### Two-source-of-truth `RandomizationMode` enum with parallel name table

`debug/random_value.py:27` defines `random_mode_names = ("random",
"zero", "max", "nil", "one", "lengthy")`, then `RandomizationMode`
(lines 30–48) enumerates six members with values 0–5 and a
`to_name()` method that indexes into the parallel tuple. Re-ordering
either silently breaks the mapping. `is_changing()` (line 47) tests
`self.value in [0, 4, 5]` — three Magic Numbers. DRY violation; a
single `(Enum, str-name, is_changing)` declaration would collapse
the duplication.

### `get_random_ssz_object` is a 125-line dispatch chain

`debug/random_value.py:51–176` is one function with seven `elif
issubclass(typ, ...)` branches covering ByteList, ByteVector,
boolean/uint, Vector/Bitvector, List variants, Container variants,
Union, CompatibleUnion. Each branch re-checks the `mode` against
the same enum members — Switch-on-Type and Switch-on-Mode
interleaved. New SSZ types require a new branch; new randomisation
modes require touching every branch. Polymorphism on the type plus
a per-mode policy object would split the two concerns.

### Mode-dependent control flow obscured by load-bearing bit math

`debug/random_value.py:125` reads `max_list_length = 1 <<
(max_list_length.bit_length() >> 1)` inside the recursion for
`List`-like types — silently halving the length budget at every
level. There is no comment, no name for the operation, no test
pinning the intended depth scaling. Extracting
`_decay_list_budget(n)` would make the policy explicit.

### Twin `decode`/`encode` modules are isomorphic Switch-on-Type chains

`debug/encode.py:18–56` and `debug/decode.py:18–52` are mirror
images of each other: each is one function with eight isinstance/
issubclass branches over the same set of SSZ shapes. Every new SSZ
kind — and the codebase has already added `ProgressiveContainer`,
`ProgressiveList`, `ProgressiveBitlist`, `CompatibleUnion` —
requires editing both files in lockstep. Divergent Change vs.
Shotgun Surgery (Fowler). A visitor on the SSZ types (with
`to_json` / `from_json` methods on the view classes) would localise
the change.

### `decode.py` silently does not handle `CompatibleUnion`

`debug/encode.py:50–54` handles `CompatibleUnion`; `debug/decode.py`
(lines 40–50, the Union branch) handles plain `Union` but never
matches `CompatibleUnion`, so a round-trip through YAML for a
CompatibleUnion-bearing type falls through to the final `raise
Exception(f"Type not recognized…")` at `decode.py:52`. Asymmetry
between encode and decode is a classic latent bug. Beck FIRST
(Self-validating) — there is no property test asserting
`decode(encode(x)) == x` for the SSZ catalogue.

### `tools.py` extension-string dispatch with no enum or registry

`debug/tools.py:39–46` decides whether to snappy-decompress by
matching `file_path.suffix == ".ssz_snappy"` or `== ".ssz"` and
raising on anything else. The two extensions are bare strings, not
constants; a typo would silently fall into the `else`. Stringly
Typed (Fowler) — an `SSZFileFormat` enum or a small registry would
make the supported set machine-readable.

### `parse_config_vars` — primitive obsession and inverted special-cases

`config/config_util.py:8–23` takes a `dict[str, Any]` of YAML
strings and converts every entry to `int`, except: lists, `0x`-prefixed
strings (which become `bytes.fromhex`), and the two keys
`PRESET_BASE` and `CONFIG_NAME` (lines 19–22, hard-coded to remain
strings). The keep-as-string list is a denylist; new string-typed
config keys silently get `int()`-coerced and crash the YAML loader.
Primitive Obsession over a `Config` dataclass with typed fields,
plus the special-case keys are Magic Strings.

### Module-level globals declared without initialiser, mutated through `global`

`config/config_util.py:53–65` declares `mainnet_config_data` and
`minimal_config_data` as type-annotated globals with no value, plus
a `loaded_defaults = False` flag. `load_defaults(...)` mutates all
three via `global` (Hunt & Thomas Tip 17 violation). Reading
`mainnet_config_data` before `load_defaults()` raises `NameError`
rather than a clear error; nothing prevents partial initialisation
if the second `load_config_file` raises. A `ConfigDefaults`
dataclass returned from a factory would be both safer and statically
checkable.

### `load_preset` validation order: `assert preset != {}` after key-disjoint check

`config/config_util.py:26–41`'s loop merges fork-preset YAML files;
it checks key-disjointness on every iteration but only verifies
`preset != {}` after the loop. The assertion has no message — a
contributor passing zero preset files gets a bare `AssertionError`
with no context. The `Exception(...)` raised on duplicate keys
(line 38) is generic, not a typed `PresetMergeError`. Beck FIRST
(Self-validating) is half-implemented. A Pydantic model for the
preset schema (with field validators replacing the post-hoc
assertion, and Pydantic's own `ValidationError` carrying the
failing field path) is both safer and statically checkable; the
schema doubles as documentation for what shape a preset YAML must
have.

### Tests-alongside-source: `test_*.py` files inside the runtime `utils/` package

`utils/test_merkle_minimal.py` and `utils/test_merkle_proof_util.py`
live inside the importable `eth_consensus_specs.utils` package
rather than in `tests/`. The second file's docstring at lines 3–4
admits its purpose: "these functions are extract from
merkle-proofs.md (deprecated), the tests are temporary to show
correctness while the document is still there" — a TODO-as-comment
that has outlived its writer. They get collected by pytest as part
of the spec test run, mixing infra unit tests with spec
behavioural tests.

### `test_merkle_proof_util.py` defines its own `get_power_of_two_ceil`

`utils/test_merkle_proof_util.py:7–13` defines a recursive
`get_power_of_two_ceil` *inside* the test module — the function is
not imported from anywhere in the package; it exists only to be
asserted-against by a parametrised test on lines 30–35. The comment
at line 3 says the function was extracted from a deprecated
markdown doc to "show correctness". The test now verifies a
function with no production callers — Dead Code (Fowler).

---

## Build extraction (`pysetup/`)

The markdown-as-source-of-truth and fork-registration deep-dives
cover the major themes. The items below are file-specific smells
inside `pysetup/` itself.

### `pysetup/__init__.py` exposes no public API

`pysetup/__init__.py` is a zero-byte file. The file itself is needed
(it's how setuptools and Python recognise the directory as a
regular package), but for a module that is the build orchestrator
of the entire spec, leaving `__all__`, a version, and a one-line
docstring off the surface means every consumer reaches in via
`from pysetup.helpers import …`. The package boundary is
load-bearing only by convention; the same shape recurs at the
sub-package level (see "Sub-package `__init__.py` files expose no
public API" above).

### Recursive O(depth) fork ancestry test in `is_post_fork`

`pysetup/md_doc_paths.py:41–54` implements `is_post_fork(a, b)` as a
recursive lookup that walks the `PREVIOUS_FORK_OF` chain one step at
a time and re-traverses on every call. There is no memoisation
even though the relation is static, the recursion can hit Python's
stack limit on long chains, and the same data is also re-enumerated
by `collect_prev_forks` in `helpers.py:16–22`. A precomputed
`IS_POST_FORK: dict[tuple[str, str], bool]` would make both lookups
O(1).

### Fork genealogy is a flat `dict[str, str | None]`

`pysetup/md_doc_paths.py:16–27` declares the fork lineage as a bare
mapping from fork string to predecessor string, with `EIP8025: FULU`
sitting alongside the linear mainline as a sibling whose semantics
("is this an experimental branch?") are nowhere expressed. Adding a
deprecation, a "draft" status, or a non-linear branch would require
ad-hoc string conventions. A `Fork` dataclass with explicit
`predecessor`, `status`, `directory` fields plus a `ForkGraph` that
owned `is_descendant`/`ancestors` would replace four string-keyed
dicts with one typed structure.

### `get_fork_directory` does filesystem probing instead of declaring location

`pysetup/md_doc_paths.py:57–64` searches for a fork's specs by
trying `specs/{fork}` then `specs/_features/{fork}` and raising if
neither exists — the directory location is implicit data hidden in
two fallback `os.path.exists` calls (relative to CWD). Inappropriate
Intimacy with the filesystem layout — the location should be a
declared field on the fork object, not a probe.

### `get_md_doc_paths` returns a newline-joined string instead of a list

`pysetup/md_doc_paths.py:74–92` builds `md_doc_paths` as a single
string by repeated concatenation, returns it, and the caller in
`generate_specs.py:209` immediately splits it back via `.split()`.
Two issues: a Stringly Typed return type (Fowler — a smell, not a
bug today, since paths in this project don't contain whitespace),
and a latent bug — the `.split()` round-trip would silently break
the day someone introduces a path containing a space. Returning
`list[Path]` directly fixes the smell and forecloses the bug.

### `objects_to_spec` assembles a Python module by string concatenation

`pysetup/helpers.py:47–258` builds the entire generated spec module
by appending strings into `spec_strs` (lines 232–257), with eight
`reduce(lambda txt, builder: txt + "\n\n" + builder.<part>())`
chains (lines 174–189) for imports, classes, preparations, sundry
functions. The `reduce` hides ordering assumptions, and
`execution_engine_cls`'s fold (`builder.execution_engine_cls() or
txt`) silently treats empty strings as "no override" — coupling
builder return-value semantics to truthiness. A `SpecAssembly`
dataclass collecting typed sections, with a single `render()`
method, would replace both the string-glue and the ordering quirks.

### `dependency_order_class_objects` runs to a fixed point with no progress proof

`pysetup/generate_specs.py:127–133` calls
`dependency_order_class_objects` in a `while OrderedDict(new_objects)
!= OrderedDict(class_objects)` loop, copying the entire dict on
each iteration via `copy.deepcopy`, with no termination guarantee
and no iteration cap. The ordering function itself
(`pysetup/helpers.py:323–351`) parses class source with two regexes
to extract dependencies. If the loop fails to converge (a circular
dependency in spec markdown), the build hangs silently.

### Config-name substitution by per-variable regex

`pysetup/helpers.py:104–110` rewrites every config variable name
into `config.<name>` by running a separate `re.sub(rf"(?<!['\"])\b{name}\b(?!['\"])"
…)` for each name in `spec_object.config_vars` against the joined
function source and the joined class source. This is O(N_vars *
len(source)) for what is fundamentally an AST rewrite; the
quote-detection lookbehind is approximate (it doesn't understand
triple-quoted strings or comments). A proper `ast.NodeTransformer`
would be both faster and less wrong.

### `requires_mypy_type_ignore` encodes mypy bugs as a string-prefix table

`pysetup/helpers.py:25–31` decides whether to emit a `# type:
ignore` comment in a generated class by string-matching the type
expression: `startswith("Bitlist")`, `startswith("ByteVector")`, a
partial regex guard for `List`, and a `"ceillog2"`/`"floorlog2"`
substring check on `Vector`. Each rule encodes an underlying mypy or
`remerkleable` limitation that someone debugged once; none cite the
upstream issue. A `KNOWN_MYPY_WORKAROUNDS: dict[str, str]` mapping
pattern to issue URL would at least make the workarounds
discoverable.

### `OPTIMIZED_BLS_AGGREGATE_PUBKEYS` lives in `constants.py` as triple-quoted Python source

`pysetup/constants.py:29–32` defines `OPTIMIZED_BLS_AGGREGATE_PUBKEYS`
as a string holding a Python function body that overrides the
spec's default implementation when a builder asks for it. A
constants module holds executable source as data; no test verifies
the override matches the spec's `eth_aggregate_pubkeys` signature,
and a typo in the string surfaces only at import time of the
generated module. Same shape as the deep-dive's `cache_this`
finding, smaller surface — Stringly Typed source code in a
constants file.

### `eval()` of arbitrary spec values inside `check_yaml_matches_spec`

`pysetup/md_to_spec.py:602–608` calls `eval(updated_value)` on a
string assembled by substituting other spec values into the
variable definition, wraps it in a `try/except NameError: pass`
("Okay it's probably something more serious, let's ignore"), and
otherwise asserts equality against the YAML. Three issues at once:
`eval` runs arbitrary expressions from markdown; the bare comment
"let's ignore" swallows real mismatches; and any non-`NameError`
exception crashes the build with no location info. Inappropriate
Comment (Martin) over a security-relevant shortcut.

### `_get_class_info_from_ast` silently returns `None` on unrecognised bases

`pysetup/md_to_spec.py:488–501` returns `parent_class = None` for any
base expression it doesn't match (Name, Subscript, Call), with a
TODO comment "check for consistency with other phases". A cross-fork
SSZ class that derives from `phase0.SignedBeaconBlock` falls into
this branch and gets accepted by the assertion `parent_class is
None or parent_class == "Container"` at line 186 — inheritance-chain
bugs would surface only as runtime errors much later. Dead-letter
TODO + assertion-as-validation. The right shape is a Pydantic
discriminated union over `ParentClass` variants (`NamedBase`,
`GenericBase`, `ContainerBase`, `UnknownBase`) — the AST walker is
forced to enumerate every base type it handles, and a `match` on
the discriminator gives compile-time exhaustiveness checking
instead of a silent `None` fall-through.

### `_load_kzg_trusted_setups` builds paths via string concatenation

`pysetup/md_to_spec.py:514–521` constructs the trusted-setup path as
`str(Path(__file__).parent.parent) + "/presets/" + preset_name +
"/trusted_setups/trusted_setup_4096.json"`, mixing `Path` semantics
with raw `/` concatenation and hardcoding the `4096` filename. A new
trusted-setup file size requires editing this string; a Windows
path would break the `/`. Primitive Obsession on `Path`.

### `ALL_KZG_SETUPS` is loaded at module import time

`pysetup/md_to_spec.py:532–535` populates `ALL_KZG_SETUPS` by
calling `_load_kzg_trusted_setups("minimal")` and `…("mainnet")` at
import time, which means importing `md_to_spec` reads two
multi-MB JSON files unconditionally — even for callers that never
produce a KZG-bearing fork. Side effects in module scope (Hunt &
Thomas, Tip 17) couple import latency to disk I/O and make
`md_to_spec` un-importable on a checkout where the trusted-setup
files are absent.

### `BuildTarget` carries a `list[Path]` instead of `Sequence[Path]` or `tuple`

`pysetup/typing.py:31–34`'s `BuildTarget` declares
`preset_paths: list[Path]`, then `generate_specs.py:115` calls
`load_preset(tuple(preset_files))` to make the value hashable for
`@cache`. The same value is converted between three representations
(list at construction, tuple at cache lookup, sequence in
`build_spec`'s signature). `tuple[Path, ...]` on the NamedTuple
field would remove the conversion and document immutability.

---

## Test-vector generators (`tests/generators/`, `tests/formats/`)

The compliance-runners deep-dive covers the fork-choice subsystem;
the items below cover smaller surfaces.

### Manual fork-coverage checklist with no machine enforcement

`tests/checklists/heze.md` is a hand-maintained markdown checklist
of test cases for the Heze fork, each with "Implemented ✅". Nothing
checks the list against actual test files — a renamed test leaves
the checklist stale; a missing test leaves a misleading ✅. Beck
FIRST (Self-validating). Other forks presumably need their own
checklists; only Heze has one. `execution-specs` is at the opposite
end of the automation spectrum: it ships an `EIPChecklist` Python
class with hierarchical attributes
(`EIPChecklist.TransactionType.Test.IntrinsicValidity.GasLimit.Exact()`),
tests mark themselves by decoration, the framework auto-generates
filled checklists from those markers (a renamed test moves its
checkbox automatically), per-EIP supplementary files
(`eip_checklist_external_coverage.txt`,
`eip_checklist_not_applicable.txt`) carry the items that aren't
covered by Python markers, and a CI workflow
(`.github/workflows/test-checklist.yaml`) asserts checklist-
template consistency on every PR. Same engineering goal,
markedly different execution.

### Format READMEs as the spec for test-vector shapes

`tests/formats/<category>/README.md` is the spec for the YAML/SSZ
shape of the corresponding category's test vectors. A markdown
document is the source of truth for a wire format consumed by code
in five languages. Three sources of truth (markdown spec, generator
code, runner code) must stay aligned by code review only. The
[vector-formats.md](deep-dives/vector-formats.md) deep-dive is the
direct fix: a pair of typed Pydantic base classes
(`StateTransitionCase`, `PureFunctionCase`) replace ~35 of the
markdown documents while preserving the on-disk vector layout
clients already consume. See also
[markdown-as-source-of-truth.md](deep-dives/markdown-as-source-of-truth.md)
for the broader frame.

### Output writer uses dynamic method dispatch without a clear interface

`tests/generators/compliance_runners/gen_base/output.py:8–29`
(`dump_test_case_result`) routes by string kind via `getattr(dumper,
f"dump_{kind}", None)`. A new kind requires a `Dumper.dump_<kind>`
method that the dispatch can't enforce — Stringly Typed and
Open/Closed violation. A `TestCasePartKind` enum with a single
polymorphic `dump_part(kind, ...)` would replace the
`getattr`-by-string idiom.

### Pyspec test vectors generated via yield with no type safety

`@vector_test` in `tests/infra/yield_generator.py` collects yielded
`(name, kind, data)` tuples and routes them through
`_yield_generator_post_processing()`. Implicit type inference (View
→ SSZ; dict → data); no schema check; coupling to spec types
(`eth_consensus_specs.utils.ssz.ssz_typing.View`); error messages
surface only in the writer, not at the test boundary. Fail-late +
DIP violation.

---

## Project metadata (`pyproject.toml` and friends)

These are smaller items not covered by the static-analysis-config
deep-dive — that deep-dive focuses on the typing/lint surface; the
items below are project-management concerns.

### Pinned-everything dependencies disable resolution

`pyproject.toml:13–58` pins every version with `==` (e.g.
`eth-remerkleable==0.1.30`, `setuptools==82.0.1`, `pytest==9.0.3`).
Combined with `renovate.json:9–10` (which disables Python updates),
the project has opted out of automated dependency management. Hunt
& Thomas Tip 38 — the pinning prevents `uv` or `pip` from resolving
upgrades that would otherwise be safe. Ranges (`>=8,<9`) would let
resolvers do their job while keeping major versions controlled.

### Renovate disables Python dependency updates for a Python project

`renovate.json:9–10` sets `"matchDepNames": ["python"], "enabled":
false`, opting out of automated Python dependency management. The
rationale isn't documented; combined with `==` pinning everywhere,
it leaves the project to hand-bump dependencies indefinitely.

### `.gitignore` Shotgun Surgery for generated phases

`.gitignore:18–27` enumerates per-phase generated directories
(`tests/core/pyspec/eth_consensus_specs/phase0/`, `…/altair/`, ...,
`…/eip*/`). Each new fork adds a line. A
`tests/core/pyspec/eth_consensus_specs/*/` glob would do the job
once. (This finding goes away entirely if the package source moves
out of `tests/` — see the directory-structure deep-dive.)

### Dynamic version sourced from a generated file

`pyproject.toml:103` reads the package version from
`tests/core/pyspec/eth_consensus_specs/VERSION.txt`, which is
generated by the test infrastructure, not checked in. If
`pyproject.toml` is evaluated before the test build runs, the
version reading fails or is stale. Bootstrapping fragility — the
package metadata depends on the test infra.

### `.gitattributes` only labels Solidity but no Solidity exists

`.gitattributes:1` is a single line: `*.sol linguist-language=Solidity`.
There are zero `.sol` files in `consensus-specs/` (`find -name
'*.sol'` returns nothing). The line is dead config — likely a
template leftover. Meanwhile actually-useful directives are missing:
`uv.lock linguist-generated=true` and `linguist-generated` markers
for `tests/core/pyspec/eth_consensus_specs/<fork>/` would prevent
GitHub's language stats from including the generated pyspec output
and the lockfile.

### No `.editorconfig`

`/home/dev/src/cs-tech-debt/consensus-specs/.editorconfig` is
absent. `execution-specs/.editorconfig` exists with `[*.py]
max_line_length = 79`. Without an editorconfig, IDE defaults (tabs
vs. spaces, line endings, final-newline) drift per contributor — and
the repo mixes Python, YAML, Markdown, Make, and Solidity-tagged
Python. The Ruff config in `pyproject.toml` covers Python only;
everything else has no shared formatting baseline.

---

## Repo governance and CI metadata (`.github/`)

Not covered by the build-orchestration deep-dive (which focuses on
workflows themselves). The items below are about the surrounding
governance and configuration layer.

### `release-drafter.yml` references EIP labels that the labeler doesn't emit

`.github/release-drafter.yml:18, 22–25, 29` lists categorisation
labels including `eip7594`, `eip7732`, `eip7843`, `eip7928`,
`eip8061`, `eip7805` — none of which are produced by
`.github/labeler.yml`, which only emits `eip6914` and `eip8025`
(lines 64–76). The release notes therefore *can never* sort PRs into
those categories under the auto-labeller; a human must hand-label
each PR. Two Sources of Truth (Hunt & Thomas, Tip 17) plus Dead Code
(Fowler).

### `labeler.yml` hard-codes per-fork rules in a ten-block copy-paste

`.github/labeler.yml:1–76` enumerates phase0, altair, bellatrix,
capella, deneb, electra, fulu, gloas, heze, eip6914, eip8025 — each
as a 5-line stanza referencing `specs/<fork>/**`,
`presets/*/<fork>.yaml`, `pysetup/spec_builders/<fork>.py`. Adding a
fork is Shotgun Surgery (Fowler); the fork list is also recorded in
`pysetup/md_doc_paths.py`, `release-drafter.yml`, `.gitignore:18–27`,
the test directories, and `AGENTS.md` — at least six places to keep
in sync.

### PR template fields validated by no workflow

`.github/pull_request_template.md` defines three free-text sections
(Description, Checklist, Relations — lines 1–19), all wrapped in
HTML comments so they render invisibly until the author replaces
them. No workflow under `.github/workflows/` parses them; no
required-status check enforces the checklist boxes; and the "Run
`make lint`" / "Run `make test`" items are already covered by
`tests.yml` and `checks.yml` — duplication without enforcement.
Speculative Generality.

### `mkdocs.yml` depends on `docs/` that doesn't exist in tree

`mkdocs.yml:1–42` declares the docs site, with `gen-files` configured
at line 35 to run `scripts/gen_spec_indices.py`. The implicit
`docs_dir` (mkdocs default) is `docs/`, which is *gitignored*
(`.gitignore:44`) and only materialised at build time by the
`_copy_docs` Make target (`Makefile:252–258`) which copies `specs/`,
`sync/`, `ssz/`, `fork_choice/`, and `README.md` into a transient
`docs/`. A contributor who clones the repo and runs `mkdocs serve`
directly will see an empty site and no helpful error. Hidden
Knowledge — the dependency is in the Make target, not in the mkdocs
config.

### No `.github/ISSUE_TEMPLATE/` directory

`.github/` contains only `labeler.yml`, `pull_request_template.md`,
`release-drafter.yml`, and `workflows/` — no `ISSUE_TEMPLATE/`
folder. `execution-specs/.github/ISSUE_TEMPLATE/` ships
`incorrect-specification.md`, `incorrect-documentation.md`,
`tooling-problem.md`, `eip-tracker.md`, and `blank-issue.md`; the
absence here means new spec-bug reports arrive as free-form prose
that triagers must re-classify by hand.

### `.github/` lacks the extension points comparable repos use

`execution-specs/.github/` has `actions/` (15+ composite actions —
`setup-uv`, `setup-env`, `cache-docker-images`, …), `configs/`
(`evm.yaml`, `feature.yaml`, `fork-ranges.yaml`, …),
`actionlint.yaml`, and `scripts/`. `consensus-specs/.github/`
contains only `workflows/`, `labeler.yml`, `pull_request_template.md`,
`release-drafter.yml`. The build-orchestration deep-dive flags the
workflow-level duplication; this finding is the adjacent observation
that the directory has no extension points (`actions/`, `configs/`,
`actionlint.yaml`) for that duplication to collapse into.

---

## Documentation and developer onboarding

These items affect the experience of a new contributor finding their
way into the codebase. They are small individually but compound.

### `AGENTS.md` conflates human and agent audiences in a 421-line monolith

`AGENTS.md` mixes contributor guidance ("Adding a new fork or
feature", "Modifying an existing function") with agent-only details
(decorator stack, preset behaviour, fork inheritance chains). A
developer looking up "how to run tests" navigates past 340 lines of
unrelated context. The file's "Fork inheritance" section restates
`pysetup/md_doc_paths.py` PREVIOUS_FORK_OF in prose — a Two Sources
of Truth violation.

### Three minimalist skills with no `agents/`, `rules/`, or `hooks/`

`consensus-specs/.claude/` contains only
`skills/{commit,prepare-release,run-tests}/SKILL.md` — no `agents/`,
`rules/`, `hooks/`, `hooks.json`, or `settings.json`. Every agent
task starts from generic defaults; project-specific patterns must be
inferred from `AGENTS.md` each time.

### `README.md` is user-centric; no contributor quick-start

`README.md:61–113` covers prerequisites (install `uv`), cloning,
`make help`. There's no "run the test suite", no "lint your changes",
no canonical workflow. A new contributor must either read
`AGENTS.md` in full or experiment.

### No `CONTRIBUTING.md`

Contributor workflow guidance is distributed across `README.md`,
`AGENTS.md`, and `.claude/skills/`. The alternatives provide a
single `CONTRIBUTING.md` that links to the canonical workflow.
Absent here.

### Test-pattern format documented only as prose

`AGENTS.md:322–337` documents the canonical "yield 'pre', 'blocks',
'post'" pattern for spec tests. There is no schema, no validator, no
linter check. A typo (`yield 'setup'` instead of `'pre'`) surfaces
only at vector-generation time, far from the test source.

### "general" / "minimal" preset behaviour hidden in `conftest.py` comments

`tests/core/pyspec/.../test/conftest.py:104–112` documents in code
that the "general" preset is preset-independent and internally uses
"minimal" for spec loading. This crucial fact is not surfaced in any
developer-facing doc beyond a passing mention in `AGENTS.md`. Hidden
Knowledge — agents and humans hit it as a surprise.

---

## Test infrastructure (`tests/infra/`)

A note on framing. `tests/infra/` is the project's own in-progress
effort to give the test-support layer a structured home with sibling
unit tests — every helper module in `tests/infra/helpers/` has a
`test_*.py` next to it, and `tests/infra/test_*.py` unit-tests the
framework's own machinery (block randomization, manifest, context,
markdown→spec extractor, template tests, yield generator). That
direction is right; the findings below are smells *inside* the new
tree, not arguments against the tree's existence. The
[helper-layer.md](deep-dives/helper-layer.md) deep-dive frames the
overall migration in more detail.

### Stringly-typed runner-to-handler dispatch

`tests/infra/pytest_plugins/yield_generator.py:27–85` defines a
hardcoded `RUNNERS` dictionary mapping directory names (e.g.
`"block_processing"`) to handler-name derivation rules using
regex-like prefixes and nested dictionaries (`handler_name_map`,
`handler_name_strip`). Adding a new runner or changing dispatch
logic requires editing the shared map. Open/Closed is violated and
the dispatch is "Stringly Typed" (Fowler, *Refactoring*, 1999). A
Strategy or Visitor (Gamma et al., *Design Patterns*, 1994) with
module-registered handler classes would eliminate the central table.

### Duck-typed SSZ inference in yield post-processing

`tests/infra/yield_generator.py:26–45` performs runtime type checks
(`isinstance(value, View)`, `isinstance(value, bytes)`) to infer
whether a yielded tuple is SSZ data, metadata, or plain Python. There
is no schema or serialisation hint; a new SSZ type not recognised by
the heuristic falls through to the `data` branch and silently
corrupts the test vector. The fix is a typed yield protocol — see
the SSZ generic vectors deep-dive for one shape it could take.

### Frame-inspection test registration

`tests/infra/template_test.py:37–55` uses `inspect.currentframe()`
and `inspect.getmodule()` to dynamically register test functions in
the caller's module namespace. While creative, this requires
frame-error handling, assumes a two-frame call stack, and obscures
control flow (the reader can't immediately see where a test is
registered). The SSZ generic system is its largest user; replacing
it with `pytest_generate_tests` and explicit parametrisation is the
right shape.

### `Manifest` dataclass with manual field-by-field merging

`tests/infra/manifest.py:8–40`'s `with_defaults()` method explicitly
lists all six fields. Adding a new field requires editing the
dataclass, the `__init__`, the `with_defaults()` method, and the
`is_complete()` check — DRY violation at the smallest scale.
`dataclasses.replace` or a `BaseModel.model_update`-style merge
would handle arbitrary fields generically.

### God object in `dumper.py`

The `Dumper` class at `tests/infra/dumper.py:48–84` handles YAML
formatting, SSZ compression, and manifest writing in one type, owns
two YAML encoder instances, and is dispatched on by string at
`tests/infra/pytest_plugins/yield_generator.py:368`
(`"meta"`/`"data"`/`"ssz"`). SRP violation; three smaller classes
(or a registry of handlers) would be more honest.

### Magic numbers and fork-specific branches in `block_randomized.py`

`tests/infra/block_randomized.py:298–339` contains a hardcoded
fork-config table mapping each fork to a pair of randomiser
functions (`randomize_state_<fork>`, `random_block_<fork>`); adding
Gloas required importing two new functions and editing the table —
Shotgun Surgery. Constants such as `BLOCK_TRANSITIONS_COUNT = 2`
(line 77) and `DEFAULT_SEED = 1447` (line 78) are unexplained magic
numbers, and scenario keys (`"epochs_to_skip"`, `"slots_to_skip"`,
etc.) are bare strings, not enums.

### Regex-driven metadata extraction with no static type checking

`tests/infra/pytest_plugins/yield_generator.py:119–144` uses
`path.stem`, `path.parents`, and `str.removeprefix()` to infer
`runner_name`, `handler_name`, and `suite_name` from file path and
module name. A test file whose path or name doesn't match the
(undocumented) convention silently writes its vectors to the wrong
directory. A plugin where each runner registers its handler
explicitly would replace the fragile path-based inference.

### Lazy import in `vector_test` decorator hides coupling

`tests/infra/yield_generator.py:71–72` performs a lazy import inside
the `vector_test` decorator to avoid a circular dependency with
`eth_consensus_specs.test.context`. The lazy import hides the
coupling from static analysis; nothing in the function signature
suggests the dependency. Inappropriate Intimacy (Fowler) — the
decorator knows that its caller is the spec test loader.

### Manifest completeness validated only at dump time

`Manifest.is_complete()` (`manifest.py:28–39`) is asserted at *dump*
time inside `tests/infra/pytest_plugins/yield_generator.py:347`. A
test that forgets to set `fork_name` will appear to pass and only
fail when the plugin tries to write vectors — a fail-late pattern
that violates Beck's FIRST principle (Self-validating). Earlier
validation (at test registration) would fail fast.

---

## Notes for the team

Most items above are local cleanups with single-PR scope:

- **Standalone scripts** items either retire the scripts in favour
  of `pre-commit` and existing libraries (per the substitution
  table at the top of the section), or fix them in place; the
  build-orchestration deep-dive recommends the former for most.
- **Per-fork test layout** items collapse into the
  directory-structure refactor (see [`README.md`](README.md) Theme
  1) — fixing them in isolation is possible but fixing them as part
  of the layout move is cheaper.
- **Per-fork test bodies** items are mechanical pytest hygiene
  (markers, parametrize, fixtures) — easy wins that improve every
  test author's life.
- **Helper modules** items are concentrated in `helpers/` and
  several are simple deletions (the empty `das.py`, the dead
  `shard_block.py`, the inverted `payload_attestation.py` import);
  a single cleanup PR could address most of them.
- **Spec utilities** items are the kind of thing that a strict
  static-analysis config (see the static-analysis-config deep-dive)
  would have caught earlier; addressing the config first makes
  fixing these easier.
- **Build extraction** items inside `pysetup/` are mostly
  defensive: replace `eval`/regex source rewrites with AST passes,
  bound the unbounded loops, type the genealogy. None of them
  require touching the markdown spec.
- **Test-vector generators** items mostly collapse into the
  vector-formats deep-dive's typed-schema proposal.
- **Project metadata** items (`renovate.json`, `==`-pinning,
  dynamic version, `.gitattributes`, `.editorconfig`,
  `.pre-commit-config.yaml`) are dependency-management and
  repo-hygiene decisions. The `==`-pinning + Renovate disable
  combination should probably be revisited together rather than
  separately.
- **Repo governance** items (`labeler.yml`, `release-drafter.yml`,
  `mkdocs.yml`, missing `ISSUE_TEMPLATE/`) are governance hygiene;
  the `labeler.yml` / `release-drafter.yml` mismatch is the most
  worth fixing (they are actively contradicting each other).
- **Documentation** items can be addressed at any time and
  independently of any code refactor.
- **Test infrastructure** items can be addressed independently;
  doing them as a sequence of small PRs gives the team practice
  with the patterns the larger refactors will need. The whole
  `tests/infra/` tree is the project's own remediation effort
  (see the framing note at the top of that section), so the
  smells listed there are *inside* the new tree, not arguments
  against it.
