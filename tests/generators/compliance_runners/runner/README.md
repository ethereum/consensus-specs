# Compliance vector replay

Replay validates serialized vectors independently of generation and coverage
evaluation. Run either format, or omit `--kind` to replay both from a mixed
root:

```sh
pytest tests/generators/compliance_runners/runner/test_run.py \
  --test-dir=out/compliance --kind=state_transition

pytest tests/generators/compliance_runners/runner/test_run.py \
  --test-dir=out/compliance --kind=fork_choice
```

`--test-dir` accepts a root containing preset directories or a batch directory
containing `*/reftests`. Repeat it to combine roots. `--start` and `--limit`
slice the discovered cases after format filtering. An empty selection is an
error.

- `discovery.py` identifies cases by preset, fork, runner, handler, and suite.
- `io.py` reads YAML and compressed SSZ files.
- `state_transition.py` replays operations, epoch processing, and sanity
  vectors.
- `fork_choice.py` replays fork-choice events and initializes its trusted setup.
- `test_run.py` provides the shared pytest entry point.

The reusable replay modules do not import generator implementations or pytest
entry points. Generators share the operation schema in `formats.py` and the
payload-attestation conversion in `payload_attestation.py` with replay.

Run the runner's regression tests without supplying vector directories:

```sh
pytest tests/generators/compliance_runners/runner/test_discovery.py \
  tests/generators/compliance_runners/runner/test_replay.py
```
