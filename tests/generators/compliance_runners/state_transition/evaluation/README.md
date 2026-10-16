# State-transition suite quality evaluation

This package measures the generated Gloas state-transition compliance suite
against materialized Python-spec slices. It is a generator-quality metric: the
normal compliance runner remains the oracle for SSZ decoding, expected
post-states, and rejection cases.

Outputs are deliberately local. They contain generated test suites, copied slice
source, coverage databases, and JSON reports and must not be committed.

## Groups and exclusions

[`groups.yaml`](groups.yaml) defines composable vector/code scopes. The standard
groups are `all`, `all_operations`, `all_epoch_processing`, `all_sanity`, and
`parent_execution_payload_plus_invoked`. The `blocks` handler uses the sanity
test format. A handler name is also a valid single-handler group.

[`exclusions.yaml`](exclusions.yaml) defines shared helpers excluded from the
generator-quality denominator. Every report retains both raw and in-scope
metrics and lists the applied exclusions. Add an exclusion only with a specific
rationale and independent coverage owner.

The parent-plus-invoked group is intentionally an aggregate: parent-payload
vectors run against the parent slice; vectors for dispatched requests run
against their own matching slices. Vectors are never applied to a processor with
an incompatible input type. Function bodies are de-duplicated by source hash
before aggregate metrics are calculated.

## Workflow

The repository-owned slicer accepts one or more root methods, expands their
combined call graph once, and imports excluded helpers from PySpec. This makes
the emitted slice executable while keeping shared helpers out of the metric:

```bash
uv run python -m tests.generators.compliance_runners.state_transition.evaluation.cli \
  collect --work-dir /tmp/state-transition-evaluation \
  --group parent_execution_payload_plus_invoked

uv run python -m tests.generators.compliance_runners.state_transition.evaluation.cli \
  evaluate --tests comptests/tests --work-dir /tmp/state-transition-evaluation \
  --group parent_execution_payload_plus_invoked
```

The `collect` command materializes and freshness-checks one tailored slice per
group. `evaluate` dispatches every vector to its matching root function in that
same slice, writes `<work-dir>/results/<preset>/<group>.json`, and prints raw
and in-scope coverage percentages. `--group` may be repeated. Omitting `--group`
from `collect` creates all individual-handler slices.

After evaluation, the group slice directory contains a `coverage/` directory
with Coverage.py's native `,cover` annotation report. It prefixes covered lines
with `>` and missed executable lines with `!`. The canonical `code_to_test.py`
remains unmodified so `collect_slice --check` continues to verify it
byte-for-byte.

## Experimental mutation testing

`mut_cli.py` uses Cosmic Ray only to materialize an army of isolated mutant
files from one collected evaluation-group slice. It does not use Cosmic Ray's
executor or session database for test outcomes. The army manifest is the durable
record of mutations and attempts, so a later invocation can retry surviving
mutants with a different vector set.

```bash
uv run python -m tests.generators.compliance_runners.state_transition.evaluation.mut_cli \
  materialize --work-dir /tmp/state-transition-mutation \
  --group parent_execution_payload_plus_invoked

uv run python -m tests.generators.compliance_runners.state_transition.evaluation.mut_cli \
  run --work-dir /tmp/state-transition-mutation \
  --group parent_execution_payload_plus_invoked --tests comptests/tests
```

The experiment uses a conservative boolean/comparison operator set. `run` tries
at most 20 untried mutants by default; use `--max-mutants 0` to try all of them.
To attempt survivors again with a different vector corpus, pass
`--retry-survivors`. Every mutant is written below
`<work-dir>/mutants/<preset>/<group>/<mutation-id>/code_to_test.py`, with the
manifest at `.../manifest.json`.

Use `dump` to inspect the army and every test attempt:

```bash
uv run python -m tests.generators.compliance_runners.state_transition.evaluation.mut_cli \
  dump --work-dir /tmp/state-transition-mutation --group parent_execution_payload_plus_invoked
```

## TARGET backend defaults and benchmarks

The shared TARGET default is MiniZinc/Gecode, configured in
[`backend_config.py`](backend_config.py). Small targets explicitly opt into
Python with `bind(..., backend="python")` in `target.py`. Generation, direct
TARGET binding, and coverage scoring inherit that target default. Override it
with `TARGET.for_spec(spec, backend="python")` or the scoring CLI's
`--backend python`. There is no automatic size-based switch. Install the
MiniZinc executable with Gecode as well as the project's Python dependencies to
use MiniZinc. Pure observation and validation do not launch a solver.

The TARGET backend solves generated integer satisfaction models in one MiniZinc
CLI invocation. It streams JSON solutions directly, avoiding the separate
model-interface analysis that `minizinc.Instance` normally performs before
solving. Solver discovery/configuration and warning/error decoding still use the
MiniZinc library. Only `ALL_SOLUTIONS` or `UNSATISFIABLE` terminal statuses are
accepted; partial enumeration fails. Temporary model files and processes are
cleaned up on errors. This changes execution overhead, not feasibility or
coverage compilation, and introduces no cache shared across target bindings.

Run the comparison of the fourteen providers in the original migration cohort:

```bash
uv run python -m tests.generators.compliance_runners.state_transition.evaluation.benchmark_backends \
  --repeats 3 --output /tmp/state-transition-backend-baseline/results.json
```

The default run covers both presets, both backends, and every supported standard
profile. Use `--providers`, `--presets`, `--profiles`, or `--backends` to narrow
a run. Each provider/preset/backend runs in a separate worker process. Every
profile starts with a fresh target binding; scoring uses its generation caches.
Imports are excluded from timings, and module-level fixture caches may warm
across repeats. The JSON retains individual samples and min/median/max timings,
solver calls, parity fingerprints, and POSIX process memory peaks. Python and
child-process peak RSS are separate measurements, not a combined peak. The
Markdown report sums profile medians for a compact per-worker comparison.

The benchmark runs serially; avoid concurrent test or benchmark jobs while
collecting a baseline. Reports are written incrementally with `status: running`,
and marked complete only after all requested cells finish and fingerprints
agree. Keep generated JSON/Markdown reports local; do not commit them. Use a new
output directory for each revision so before/after measurements and canonical
parity fingerprints remain available for comparison.

### Explicit small-provider choices

The optimized three-repeat benchmark found Python faster on both presets for
thirteen providers. They have at most 31,104 raw configurations, and Python
generation summed across their supported profiles takes less than 1.6 seconds
per provider/preset. These targets explicitly select Python through `bind`;
attestation and the other TARGET providers inherit MiniZinc. The scoring CLI
uses the target default unless `--backend` is supplied.

| Provider                              | Raw configurations | Generation backend |
| ------------------------------------- | -----------------: | ------------------ |
| attester_slashing                     |                768 | Python             |
| bls_to_execution_change               |                 80 | Python             |
| builder_deposit_request               |             14,400 | Python             |
| builder_exit_request                  |              1,960 | Python             |
| builder_pending_payments              |             10,944 | Python             |
| builder_pending_withdrawal_processing |             31,104 | Python             |
| deposit_request                       |                120 | Python             |
| effective_balance_updates             |              3,000 | Python             |
| process_operations_dispatch           |                 24 | Python             |
| pending_consolidations                |                 60 | Python             |
| ptc_window                            |                 24 | Python             |
| slashings                             |                108 | Python             |
| sync_aggregate                        |                 12 | Python             |
| attestation                           |            163,840 | MiniZinc           |

Counts are before target feasibility filtering and agree on minimal/mainnet.
These are measured provider choices, not a universal cutoff. Rebenchmark as
domains, constraints, or profiles grow. Python remains the explicit parity
reference even for MiniZinc providers; the benchmark forces each backend so
provider defaults cannot turn a comparison into the same backend on both sides.
