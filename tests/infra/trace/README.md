## Spec trace framework

This is an implementation of #4603 a new testing framework for the Ethereum
consensus spec tests, based on tracing spec method calls and recording them in a
structured trace file.

The basic idea for new tests is to use pytest more properly, to use fixture
parametrization for forks and presets, and to use a spec trace file to generate
vectors (the actual vector generation is another task in progress).

### Usage and example test

```python
from tests.infra.trace import spec_trace


@with_all_phases
@spec_state_test  # keep these like before
@spec_trace  # this is the thing that makes the magic happen
def test_linear_sanity_slots(spec, state):  # spec and state can be positional but the name matters
    # just use spec methods, they are traced automagically, and state is dumped
    spec.process_slot(state)
```

### Spec trace file example

```yaml
metadata:
  fork: electra
  preset: minimal
context:
  fixtures: []
  parameters: {}
  objects:
    states:
      a5c63f50136afb2ac758cc8c7fc11d3c0ff418f411522eba1cf4b7ac815523ab: states_a5c63f50136afb2ac758cc8c7fc11d3c0ff418f411522eba1cf4b7ac815523ab.ssz
      90d959fafeb0ce724111cf6fe3900a6a6e464a3dbd3b637002aaf85d6585072e: states_90d959fafeb0ce724111cf6fe3900a6a6e464a3dbd3b637002aaf85d6585072e.ssz
    blocks: {}
    attestations: {}
trace:
- op: load_state
  params: {}
  result: $context.states.a5c63f50136afb2ac758cc8c7fc11d3c0ff418f411522eba1cf4b7ac815523ab
- op: process_slot
  params:
    state: $context.states.a5c63f50136afb2ac758cc8c7fc11d3c0ff418f411522eba1cf4b7ac815523ab
```

In this example, `process_slot` does not return anything but we can see the
final state being dumped automatically anmd it's different from the initial one.

### Implementation details

wrapt is used to wrap spec methods and record their calls, parameters and
results. A decorator is used to set things up. Some simple pydantic models are
used for the trace file structure and some sanitation/formatting.

### TODO

This is still work in progress.

I'm not sure about how some of the finer trace details map to vectors yet, so
this is a WIP. Once we have vectors generated from traces, we can refine the
trace format as needed.

I tried my best to separate core logic from the boilerplate needed but it could
be improved upon.

I didn't implelement some things we have with yield-based tests, Leo told me to
not worry about that because the new framework is for new tests and we can keep
the old ones as is for now and don't need feature parity.

Types are perhaps not as strict as they could be (partially because we had some
flexibility in mind), but it's a start and in many cases we don't have enough
typing in the tests to be sure about that. There's an issue open to improve
typing in the tests in general.

### Credits

Thanks to Leo for the initial idea and guidance, and to all the reviewers who
helped refine this.

Thanks to Cristobal for the first prototype of this framework, it's not used
here but I reviewed 4724 and got some inspiration from that.

Thanks to IG organizers, mentors, sponsors and fellow builders for making this
possible!
