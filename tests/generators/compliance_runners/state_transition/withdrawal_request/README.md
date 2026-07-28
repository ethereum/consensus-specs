# `process_withdrawal_request` compliance tests (aspect-based)

Aspect-based coverage for the `process_withdrawal_request` handler (defined in
Electra, inherited by gloas). The first **validator-side** runner: it establishes
the reusable validator aspect family and reuses `source_authorization` from the
builder side.

## Aspects

| aspect | dims | source |
|---|---|---|
| `withdrawal_amount` | `is_full_exit_request` | new (`../aspects/`) |
| `partial_queue_capacity` | `partial_queue_full` | new (`../aspects/`) |
| `validator_membership` | `validator_pubkey_found` | validator family (new) |
| `validator_credential` | `validator_credential` (BLS/ETH1/COMPOUNDING) | validator family (new) |
| `source_authorization` | `source_address_matches` | **shared with builder_exit_request** |
| `validator_lifecycle` | `validator_active`, `validator_exiting`, `validator_old_enough` | validator family (new) |
| `validator_pending_withdrawal` | `has_pending_partial_withdrawal` | validator family (new) |
| `validator_balance` | `sufficient_effective_balance`, `has_excess_balance` | validator family (new) |
| `outcome` | `outcome` | handler outcome |

The validator family (`validator_membership`, `validator_credential`,
`validator_lifecycle`, `validator_balance`, `validator_pending_withdrawal`) is
built to be reused by `consolidation_request` and `voluntary_exit`.
`source_authorization` is the *same file* `builder_exit_request` binds — proving
aspects are not entity-specific (bid/exit bind it to a builder's
`execution_address`; here to a validator's `withdrawal_credentials[12:]`).

## Outcomes (12)

`REJECTED_{QUEUE_FULL, NOT_FOUND, CREDENTIALS, INACTIVE, EXITING, TOO_YOUNG}`,
then a branch on `amount == 0`: full-exit → `FULL_EXIT_INITIATED` /
`FULL_EXIT_NOOP_PENDING`; partial → `PARTIAL_QUEUED` /
`PARTIAL_NOOP_{NOT_COMPOUNDING, INSUFFICIENT_EFFECTIVE_BALANCE, NO_EXCESS_BALANCE}`.
Never raises — `post` is always present. No BLS, no churn gate.

## Coverage profiles (`coverage.py`)

| profile | cases |
|---|---|
| `onewise` | 13 |
| `normal` (2-wise inputs, effected outcomes) | 9 |
| `exceptional` (1-wise outcome, rejections/no-ops) | 10 |
| `standard` (`normal ∪ exceptional`) | 19 |

## Usage

```bash
uv run python -m ...withdrawal_request.run                    # standard + validate
uv run python -m ...withdrawal_request.coverage               # profile summary
uv run python -m ...withdrawal_request.coverage onewise --materialize
```

## Notes

- Materialization advances the state to epoch 70 (> `SHARD_COMMITTEE_PERIOD`) so
  `old_enough` is reachable, and sets the target validator's credentials /
  activation & exit epochs / effective balance / balance to realize each
  dimension. The pending-partial-withdrawals queue is filled to exactly the
  limit for `partial_queue_full`, with the target's own entry included when
  `has_pending_partial_withdrawal`.
- The `validator_lifecycle` aspect carries one coherence constraint
  (`old_enough ∧ ¬exiting → active`) to exclude the one infeasible
  active/exiting/old-enough combination.
