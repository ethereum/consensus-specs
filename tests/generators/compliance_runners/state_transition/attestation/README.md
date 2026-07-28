# `process_attestation` compliance tests (aspect-based)

This Gloas runner follows the handler's ordered validation gates: target epoch,
slot/inclusion timing, Gloas payload index, committee bits and participants,
aggregation-bit length, and aggregate signature. Successful cases cover both
current- and previous-epoch targets, exercising their distinct participation and
pending-payment queue locations.

```bash
uv run python -m tests.generators.compliance_runners.state_transition.attestation.run
uv run python -m tests.generators.compliance_runners.state_transition.attestation.coverage
```
