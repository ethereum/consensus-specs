# State-transition suite quality evaluation

This package measures the generated Gloas state-transition compliance suite
against materialized Python-spec slices.  It is a generator-quality metric:
the normal compliance runner remains the oracle for SSZ decoding, expected
post-states, and rejection cases.

Outputs are deliberately local.  They contain generated test suites, copied
slice source, coverage databases, and JSON reports and must not be committed.

## Groups and exclusions

[`groups.yaml`](groups.yaml) defines composable vector/code scopes.  The
standard groups are `all`, `operations`, `epoch_processing`, and
`parent_execution_payload_plus_invoked`.  A handler name is also a valid
single-handler group.

[`exclusions.yaml`](exclusions.yaml) defines shared helpers excluded from the
generator-quality denominator.  Every report retains both raw and in-scope
metrics and lists the applied exclusions.  Add an exclusion only with a
specific rationale and independent coverage owner.

The parent-plus-invoked group is intentionally an aggregate: parent-payload
vectors run against the parent slice; vectors for dispatched requests run
against their own matching slices.  Vectors are never applied to a processor
with an incompatible input type.  Function bodies are de-duplicated by source
hash before aggregate metrics are calculated.

## Workflow

The repository-owned slicer accepts one or more root methods, expands their
combined call graph once, and imports excluded helpers from PySpec.  This makes
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
group. `evaluate` dispatches every vector to its matching root function in
that same slice, writes `<work-dir>/results/<preset>/<group>.json`, and prints
raw and in-scope coverage percentages. `--group` may be repeated. Omitting
`--group` from `collect` creates all individual-handler slices.

After evaluation, the group slice directory contains a `coverage/` directory
with Coverage.py's native `,cover` annotation report. It prefixes covered
lines with `>` and missed executable lines with `!`. The canonical
`code_to_test.py` remains unmodified so `collect_slice --check` continues to
verify it byte-for-byte.
