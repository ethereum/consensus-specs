# `process_withdrawals` compliance tests — withdrawal-processing aspects

A single materializer (`materializer.py`) materializes solutions of two
complementary aspect models of `process_withdrawals`:

## withdrawal-processing

Models the pending builder/validator queue lengths (existence and hit-limit)
together with the builder sweep (builder count, eligibility, swept count,
next-index bookkeeping, and whether the sweep hits the withdrawals limit) and
the validator sweep.

## builder-pending-withdrawal

Models a single pending-withdrawal entry for `get_builder_withdrawals` (the
referenced builder's lifecycle and its pending-amount vs balance comparisons).

## Layout

```bash
uv run python -m tests.generators.compliance_runners.state_transition.withdrawal_processing.run
uv run python -m tests.generators.compliance_runners.state_transition.withdrawal_processing.coverage
```

- `coverage.py` enumerates both aspect models and selects a coverage profile
  (`standard` uses pairwise coverage; `exhaustive` keeps every distinct
  signature).
- `materializer.py` materializes each selected solution of both models into a
  concrete pre/post vector and verifies it with the corresponding aspect
  validator.
- `validation.py` independently recovers every dimension from the serialized
  vectors and re-executes `process_withdrawals` to confirm the emitted `post`.
- `run.py` runs the `standard` profile generation followed by validation.
