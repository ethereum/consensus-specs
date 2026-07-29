# `process_pending_deposits` compliance tests (aspect-based)

This Gloas generator uses a bounded relational queue model: a primary entry, an
optional secondary entry, or a processed-count-limit prefix. The independent
coverage dimensions include queue layout, finalization/limit reachability,
validator membership and lifecycle, the strict `withdrawable_epoch < next_epoch`
boundary, carried deposit churn, and the `LT`/`EQ`/`GT` comparison of a deposit
amount to available **activation** churn. New-validator deposits also expose an
applicable signature-validity dimension, so invalid signatures for new-validator
deposits remain coverage obligations.

The base state uses enough minimal-preset validators for activation churn to be
capped while exit churn remains larger. Therefore every `GT` amount case is
still within exit churn, demonstrating that this handler correctly uses the
Gloas activation-only budget.

The bounded layouts make ordering effects explicit: an exiting deposit may be
postponed before a later active deposit is applied; an active entry may be
followed by an unfinalized one; and withdrawn entries can consume the per-epoch
processed-count budget without consuming churn. The materializer also creates an
unfinalized entry only after advancing the state slot beyond that entry while
retaining genesis finality.

Two processable layouts compare the second deposit against the budget remaining
after the first deposit's churn consumption. They cover `LT`, `EQ`, and `GT`,
including an invalid new-validator first deposit: it is discarded for registry
purposes but still consumes activation churn.

Validation independently replays the complete queue loop to recover the decisive
stop gate, consumed count, processed churn, postponed entries, and applied
entries. It then checks queue reconstruction, carried churn, balance effects,
aggregate per-validator balance changes, and new-validator creation fields
directly; it does not use `process_pending_deposits` as a post-state oracle.

`onewise` covers individual aspect values, `pairwise` covers two-aspect
interactions, and the default `standard` profile uses three-way interactions.

Unlike the other state-transition compliance handlers, this is an **epoch
processing** handler. Its vectors therefore use `runner: epoch_processing`,
`handler: pending_deposits`, and contain only `pre` and `post` states: there is
no block-operation input. The shared runner dispatches this pair to
`spec.process_pending_deposits(state)`.

Gloas omits Electra's Eth1 bridge transition gate. The model consequently starts
with finalization, then the per-epoch limit, matching the current Gloas
specification.

Run it with:

```bash
uv run python -m tests.generators.compliance_runners.state_transition.pending_deposits.run
uv run python -m tests.generators.compliance_runners.state_transition.pending_deposits.coverage
```
