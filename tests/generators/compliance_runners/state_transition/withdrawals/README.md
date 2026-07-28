# `process_withdrawals` compliance tests (aspect-based)

This Gloas generator models the parent-payload guard, the four ordered
withdrawal sources (builder pending, pending partial, builder sweep, validator
sweep), and the `MAX_WITHDRAWALS_PER_PAYLOAD` boundary.

```bash
uv run python -m tests.generators.compliance_runners.state_transition.withdrawals.run
uv run python -m tests.generators.compliance_runners.state_transition.withdrawals.coverage
```

The standard profile uses pairwise source/capacity coverage for full-parent
states and includes the parent-empty no-op. `validation.py` independently
recovers every serialized dimension and re-executes the specification.
