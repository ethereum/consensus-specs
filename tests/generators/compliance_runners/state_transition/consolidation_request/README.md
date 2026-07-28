# `process_consolidation_request` compliance tests (aspect-based)

Aspect-based coverage for `process_consolidation_request` (Electra, inherited by
gloas) — the largest handler: two mutually-exclusive paths and 19 outcomes.

## Two paths

Selected by `same_source_target` (`source_pubkey == target_pubkey`):
- **switch-to-compounding** (same): `is_valid_switch_to_compounding_request` →
  `SWITCHED_TO_COMPOUNDING`, else the first failing switch gate
  (`SWITCH_REJECTED_{SOURCE_NOT_FOUND, NOT_AUTHORIZED, NOT_ETH1, INACTIVE, EXITING}`).
- **consolidation** (different): a 12-gate chain →
  `REJECTED_{QUEUE_FULL, INSUFFICIENT_CHURN, SOURCE_NOT_FOUND, TARGET_NOT_FOUND,
  SOURCE_CREDENTIALS, TARGET_NOT_COMPOUNDING, SOURCE_INACTIVE, TARGET_INACTIVE,
  SOURCE_EXITING, TARGET_EXITING, SOURCE_TOO_YOUNG, SOURCE_PENDING_WITHDRAWAL}` or
  `CONSOLIDATED`. Never raises — `post` always present.

## Aspects

Reuses the **validator family** for the SOURCE validator (`validator_membership`,
`validator_credential`, `validator_lifecycle`, `validator_pending_withdrawal`) and
`source_authorization` (shared with `builder_exit_request` / `withdrawal_request`).
The consolidation-specific aspects are `consolidation_pair`,
`pending_consolidations_capacity`, `consolidation_churn`, and a compact
`target_validator`.

### Two-role limitation (worth noting)
Consolidation has *two* validators (source + target), but the flat-var aspects
bind each dimension to one global name — so the full family binds to the SOURCE
only, and the target uses a compact single-instance `target_validator` aspect.
Letting both roles reuse the same family would require **parameterized aspects**
(MiniZinc predicates over a validator record), instantiable as `source` and
`target`. That is the natural next refactor for the aspect layer.

## Materialization notes

- **Churn** (`sufficient_consolidation_churn`) is realized by sizing the active
  validator set: **64 validators → churn > MIN (sufficient); 32 → churn == MIN
  (insufficient)** — robust to the one or two validators the case marks inactive.
- Source and target validators (indices 0 and 1) get credentials / activation &
  exit epochs set to realize their lifecycle and credential dimensions; the state
  is advanced to epoch 70 for `old_enough` headroom.
- Both queues are filled to their limits for `pending_consolidations_full` /
  `has_pending_partial_withdrawal`. No BLS.

## Coverage profiles (`coverage.py`)

| profile | cases |
|---|---|
| `onewise` | 19 |
| `normal` (2-wise inputs, effected outcomes) | 7 |
| `exceptional` (1-wise outcome, rejections) | 17 |
| `standard` (`normal ∪ exceptional`) | 24 |

## Usage

```bash
uv run python -m ...consolidation_request.run                 # standard + validate
uv run python -m ...consolidation_request.coverage            # profile summary
uv run python -m ...consolidation_request.coverage onewise --materialize
```
