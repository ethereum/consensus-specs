# `process_builder_exit_request` compliance tests (aspect-based)

Aspect-based coverage for the `gloas` `process_builder_exit_request` handler,
built to demonstrate **horizontal scaling**: it reuses the shared realization
aspects in [`../aspects/`](../aspects) and the shared coverage engine
[`../aspect_coverage.py`](../aspect_coverage.py) that
[`../execution_payload_bid/`](../execution_payload_bid) also uses.

## Aspects

| aspect | dims | source |
|---|---|---|
| `builder_membership` | `builder_pubkey_found` | shared (`../aspects/`) |
| `builder_lifecycle` | `deposit_to_finalized_epoch`, `withdrawable_epoch_set` | **shared with execution_payload_bid** (`is_active_builder`) |
| `builder_pending_balance` | `has_pending_withdrawal`, `has_pending_payment` | **shared with execution_payload_bid** (`get_pending_balance_to_withdraw_for_builder`) |
| `source_authorization` | `source_address_matches` | shared (`../aspects/`) |
| `outcome` | `outcome` | handler outcome |

`builder_lifecycle.mzn` and `builder_pending_balance.mzn` are the *same files*
the bid handler includes — each handler only binds their applicability to its own
membership notion (bid: `builder_ref == EXISTING`; exit: `builder_pubkey_found`).
Improving one aspect (or its recovery procedure) benefits both handlers.

## Outcomes

`EXIT_INITIATED`, `IGNORED_PUBKEY_NOT_FOUND`, `IGNORED_NOT_ACTIVE`,
`IGNORED_ADDRESS_MISMATCH`, `IGNORED_PENDING_NONZERO` (first-failing gate). The
operation never raises — a rejection is a no-op, so `post` is always present.

## Coverage profiles (`coverage.py`)

| profile | cases |
|---|---|
| `onewise` | 10 |
| `normal` (2-wise inputs, `EXIT_INITIATED`) | 1 |
| `exceptional` (1-wise outcome, rejections) | 4 |
| `standard` (`normal ∪ exceptional`) | 5 |

## Usage

```bash
uv run python -m tests.generators.compliance_runners.state_transition.run builder_exit_request                       # standard profile + validate
uv run python -m ...builder_exit_request.coverage                  # profile summary
uv run python -m ...builder_exit_request.coverage onewise --materialize
```

Output: standard [operations format](../../../../formats/operations/README.md)
under `reftests/minimal/gloas/operations/builder_exit_request/main/case_XXXX/`
(`pre` / `builder_exit_request` / `post` / `meta` / `manifest` / `dimensions`).
`validation.py` independently recovers each dimension via the spec and runs the
handler as an oracle.

> A prior, single-model smoke-profile version lives under
> [`../old2/builder_exit_request/`](../old2/builder_exit_request); this is its
> aspect-based successor.
