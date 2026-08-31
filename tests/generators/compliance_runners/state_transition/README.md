# State-transition compliance test generator

State-transition compliance test generator intended to produce reference tests
for individual state-transition handlers. Each handler models semantic coverage
conditions, materializes concrete SSZ test vectors, and validates the generated
vectors against the executable specification.

The generator currently targets the `gloas` fork with the `minimal` preset. Its
test cases follow the standard
[operations test format](../../../formats/operations/README.md) or
[epoch processing test format](../../../formats/epoch_processing/README.md),
depending on the handler.

## Handlers

Operation handlers:

- `attestation`
- `builder_deposit_request`
- `builder_exit_request`
- `consolidation_request`
- `deposit_request`
- `execution_payload_bid`
- `parent_execution_payload`
- `payload_attestation`
- `proposer_slashing`
- `withdrawal_request`
- `withdrawals`

Epoch-processing handlers:

- `builder_pending_payments`
- `pending_deposits`
- `ptc_window`

## Generating tests

From the repository root:

```bash
make comptests kind=state_transition
```

The default profile is `standard`, and all handlers are generated. Select a
handler, profile, or output directory with Make variables:

```bash
make comptests kind=state_transition handler=withdrawals profile=smoke
make comptests kind=state_transition profile=all
make comptests kind=state_transition comptests_dir=../compliance-spec-tests/tests
```

The supported profiles are:

- `smoke` — one representative per terminal outcome
- `normal` — cases with no independently failed conditions
- `exceptional` — single-fault cases
- `standard` — `normal` plus `exceptional`
- `all` — every distinct model coverage signature

`make comptests` is the supported generation path. The underlying module can
also be run directly:

```bash
uv run python -m tests.generators.compliance_runners.state_transition.run
uv run python -m tests.generators.compliance_runners.state_transition.run \
  --handler withdrawals --profile smoke
uv run python -m tests.generators.compliance_runners.state_transition.run \
  --comptests-output /path/to/output
```

The direct command writes to each handler's local `reftests/` directory unless
`--comptests-output` is provided. It validates each handler immediately after
materialization. Handler-specific MiniZinc models, coverage definitions,
materializers, and validators are located in the corresponding provider
directory.

A handler may have multiple provider directories. Their cases are appended to
the same handler output with distinct case numbers and validated independently;
the provider directory is an implementation detail, while the generated manifest
continues to use the protocol handler name.

## Running generated tests

From the repository root, run the compliance runner against a directory
containing generated `reftests`:

```bash
uv run pytest \
  tests/generators/compliance_runners/state_transition/runner/test_run.py \
  --test-dir ${test_dir}
```

The `--test-dir` option can be repeated to run multiple test roots. Optional
`--start` and `--limit` arguments select a slice of the discovered cases.

## Output

Generated cases use this layout:

```text
<output>/minimal/gloas/
  operations/<handler>/main/case_XXXX/
  epoch_processing/<handler>/main/case_XXXX/
```

Each case contains `pre.ssz_snappy`, the operation input when applicable,
`post.ssz_snappy` when the handler accepts the input, `meta.yaml`,
`manifest.yaml`, and `dimensions.yaml` with the claimed coverage dimensions.

The modelling approach and the distinction between coverage dimensions,
materialization, and validation are documented in
[`TEST_METHODOLOGY.md`](TEST_METHODOLOGY.md).
