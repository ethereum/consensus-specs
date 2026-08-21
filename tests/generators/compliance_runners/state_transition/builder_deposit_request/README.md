# `process_builder_deposit_request` compliance tests (aspect-based)

Aspect-based coverage for the `gloas` `process_builder_deposit_request` handler.
A third instance of the shared pipeline
([`../aspects/`](../aspects), [`../aspect_coverage.py`](../aspect_coverage.py)),
reusing two aspects from the other handlers.

## Aspects

| aspect | dims | source |
|---|---|---|
| `withdrawal_credential` | `wc_is_builder_prefix` | shared (`../aspects/`) |
| `builder_membership` | `builder_pubkey_found` | **shared with builder_exit_request** |
| `signed_message` | `builder_signature_valid` | **shared with execution_payload_bid** (bound to `is_valid_builder_deposit_signature`) |
| `deposit_amount` | `amount_nonzero` | shared (`../aspects/`) |
| `builder_reset` | `builder_withdrawable_epoch_set`, `builder_balance_zero` | swept-index reset (`../aspects/`) |
| `outcome` | `outcome` | handler outcome |

The `signed_message` aspect is the *same file* the bid handler binds — each
handler binds a different signature predicate and applicability: bid uses
`verify_execution_payload_bid_signature`, applicable only for an existing
builder; deposit uses `is_valid_builder_deposit_signature`, applicable always
(the signature is a pure function of the request).

## Outcomes

`IGNORED_BAD_PREFIX`, `IGNORED_BAD_SIGNATURE`, `ADDED_NEW_BUILDER`, `TOPPED_UP`,
`TOPPED_UP_AFTER_RESET` (spec branch order). Never raises — a rejection is a
no-op; `post` is always present.

## Coverage profiles (`coverage.py`)

| profile | cases |
|---|---|
| `onewise` | 6 |
| `normal` (2-wise inputs, credited outcomes) | 10 |
| `exceptional` (1-wise outcome, rejections) | 2 |
| `standard` (`normal ∪ exceptional`) | 12 |

`normal` treats all three crediting outcomes (`ADDED_NEW_BUILDER`, `TOPPED_UP`,
`TOPPED_UP_AFTER_RESET`) as "accepted" — the coverage engine's `accept` filter
takes a set.

## Usage

```bash
uv run python -m tests.generators.compliance_runners.state_transition.run builder_deposit_request  # standard + validate
uv run python -m ...builder_deposit_request.coverage               # profile summary
uv run python -m ...builder_deposit_request.coverage onewise --materialize
```

## Notes

- **Real BLS** deposit signatures (valid / wrong-key), so `IGNORED_BAD_SIGNATURE`
  depends on genuine verification.
- **Scope.** The `get_index_for_new_builder` slot-reuse dimension (append vs
  reuse a swept slot) is deferred; it needs a distinct swept builder in the
  pre-state. A prior single-model smoke version is archived at
  [`../old2/builder_deposit_request/`](../old2/builder_deposit_request).
- `builder_credited` is a processing-outcome label (credit branch reached), not
  a state-change predicate — a zero-amount top-up credits nothing.
