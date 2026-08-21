# `process_parent_execution_payload` compliance tests

Aspect-based compliance generation for the Gloas
`process_parent_execution_payload` handler. The model covers parent delivery,
the execution-requests commitment and four request-list caps, non-empty request
dispatch, current/previous/evicted builder-payment settlement, ordered gate
reachability, outcomes, and state effects.

The materializer writes standard `operations/parent_execution_payload` vectors
with `pre`, `block`, and (for successful cases) `post` parts. Rejected cases
omit `post`. Each case also records its model assignment in `dimensions.yaml`;
the independent validator recovers every dimension from the encoded vector and
re-executes the specification as an oracle.

```bash
# Generate and validate the standard profile.
uv run python -m \
  tests.generators.compliance_runners.state_transition.run parent_execution_payload

# Inspect profile sizes, or materialize another profile.
uv run python -m \
  tests.generators.compliance_runners.state_transition.parent_execution_payload.coverage
uv run python -m \
  tests.generators.compliance_runners.state_transition.parent_execution_payload.coverage \
  pairwise --materialize
```

The standard profile combines pairwise coverage of successful input aspects, one
representative for each successful outcome/effect state, and every exceptional
outcome/trace state. The `onewise` and `pairwise` profiles cover all aspects at
the indicated strength.
