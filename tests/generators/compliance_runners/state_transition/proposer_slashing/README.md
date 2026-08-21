# `process_proposer_slashing` compliance tests (aspect-based)

This Gloas compliance runner covers the assertion-order gates for conflicting
proposer headers, validator slashability, and both proposer signatures. Its
successful cases additionally cover the EIP-7732 pending-payment branches:
current epoch, previous epoch, and outside the two-epoch window; for each
in-window case it covers both matching and foreign payment proposers.

Slashability is modeled as the specification defines it: unslashed, activated,
and not yet withdrawable. `exit_epoch` is tracked independently so the suite
includes an exited-but-not-yet-withdrawable proposer that is still slashable.

Rejected operations omit `post`; accepted operations must slash the proposer.
When a pending payment belongs to the slashed proposer, the runner verifies
that Gloas clears it only in the current/previous-epoch window.

```bash
uv run python -m tests.generators.compliance_runners.state_transition.run proposer_slashing
uv run python -m tests.generators.compliance_runners.state_transition.proposer_slashing.coverage
```
