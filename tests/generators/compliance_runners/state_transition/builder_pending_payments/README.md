# `process_builder_pending_payments` compliance tests

Epoch-processing vectors cover the quorum `LT`/`EQ`/`GT` boundary, zero-value
withdrawals, mixed payment ordering, preserved output prefixes, and rotation of
both payment sections. Validation reconstructs the two changed state fields
without calling the handler.

This is an `epoch_processing` sub-transition. Cases contain only `pre` and
`post`, written under
`minimal/gloas/epoch_processing/builder_pending_payments/main/case_XXXX/`.

Profiles are `onewise`, `pairwise`, and `standard` (pairwise). Coverage records
occupancy, the target weight-to-quorum boundary, target withdrawal amount,
qualifying-count class, mixed LT/EQ/GT ordering, retained-section occupancy,
existing withdrawal prefix, rotation effects, outcome, and state effect.
Qualifying zero-amount withdrawals are deliberately retained in the expected
output, and payment/withdrawal markers make ordering and copied fields visible.

Run and validate the standard profile:

```bash
UV_CACHE_DIR=.uv-cache uv run python -m \
  tests.generators.compliance_runners.state_transition.run builder_pending_payments
```

Inspect coverage profiles or materialize a specific profile:

```bash
UV_CACHE_DIR=.uv-cache uv run python -m \
  tests.generators.compliance_runners.state_transition.builder_pending_payments.coverage
UV_CACHE_DIR=.uv-cache uv run python -m \
  tests.generators.compliance_runners.state_transition.builder_pending_payments.coverage \
  standard --materialize
```
