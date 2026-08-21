# `process_payload_attestation` compliance tests (aspect-based)

This Gloas runner covers the handler's ordered parent-root and previous-slot
checks, followed by indexed-attestation validity. Participant coverage keeps an
empty indexed attestation separate from an invalid aggregate signature: the
signature dimension is `NA` for an empty set because signature verification is
unreachable.

The handler does not mutate state. Rejected vectors omit `post`; accepted
vectors retain a byte-identical state and are independently replayed.

```bash
uv run python -m tests.generators.compliance_runners.state_transition.run payload_attestation
uv run python -m tests.generators.compliance_runners.state_transition.payload_attestation.coverage
```
