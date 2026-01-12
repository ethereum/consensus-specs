# Spec trace framework

This is an implementation of ethereum/consensus-specs#4603, a new testing
framework for the Ethereum consensus spec tests, based on tracing spec method
calls and recording them in a structured trace file.

The basic idea is to make tests simpler and more linear and hide the minutiae of
dumping data into the test harness (`@spec_trace` decorator) and automate
everything that doesn't have to be manual.

The spec is wrapped into a transparent proxy object and all method calls are
being tracked including any state mutations before and after. Final state is
recorded and all relevant artifacts, including all states, are being saved into
SSZ artifacts (hash-addressed to avoid duplication).

## Usage and example test

You can find this example in `tests/infra/trace/test_example_slots_2.py`:

```python
from tests.infra.trace.decorator import spec_trace


@with_all_phases
@spec_state_test  # keep these like before
@spec_trace  # this is the thing that makes the magic happen
def test_linear_sanity_slots_222(
    spec, state
):  # spec and state can be positional but the name matters
    # just use spec methods, they are traced automagically, and state is dumped
    spec.process_slot(state)
```

Example of using example test with reftests:

```bash
cp -v tests/infra/trace/test_example_slots_2.py tests/core/pyspec/eth2spec/test/gloas/sanity/test_slots_2.py
make reftests fork=gloas runner=sanity k=linear_sanity_slots_222 verbose=true
```

that produces a trace in
`../consensus-spec-tests/tests/minimal/gloas/sanity/slots_2/pyspec_tests/linear_sanity_slots_222/trace.yaml`

## Spec trace file example

```yaml
default_fork: gloas
trace:
- {op: load_state, state_root:
    95d19311d30804985b06c40cc437bdfbb126209ad9ea8253ba33e0ff0af74c40.ssz_snappy}
- op: spec_call
  method: process_slot
  input: {state:
      95d19311d30804985b06c40cc437bdfbb126209ad9ea8253ba33e0ff0af74c40.ssz_snappy}
- {op: assert_state, state_root:
    41f562b491baaa9fdd981973c8aef64bb7c663c4b07f35141c16afc9e11184c1.ssz_snappy}
```

In this example, `process_slot` does not return anything but we can see the
initial state and the final state being dumped automatically and they are
different. In the other more complex example test (omitted here for brevity) we
can examine how complex inputs and outputs being dumped and how out-of-band
state mutations are being tracked with assert and load steps.

A non-normative example of a little more complex inputs and outputs:

```yaml
- op: spec_call
  method: get_current_epoch
  input: {state:
      0740b3ecc6fb1bdc20c4f2d792da51dc7aaaa506e445ee7ba7ef1dd7ed900443.ssz_snappy}
  assert_output: 2
- op: spec_call
  method: get_seed
  input:
    state:
      0740b3ecc6fb1bdc20c4f2d792da51dc7aaaa506e445ee7ba7ef1dd7ed900443.ssz_snappy
    epoch: 2
    domain_type: '0x00000000'
  assert_output: '0x79edc6cbb9ffac34477afe87d8569b7afab320241ce69d70c6d0c0a1839379df'
```

simple primitive types here (e.g. int or bytes, not containers) are serialized
directly into yaml (even in cases where they subclass SSZ `View` and can
technically be dumped as ssz artifacts), bytes are dumped as 0x-prefixed hex
strings which seems appropriate. SSZ artifacts are always referred to by root
hash-based filename so that there's no need to maintain any mappings or
filename-generating logic.

### Implementation details

wrapt is used to wrap spec methods and record their calls, parameters and
results. A decorator is used to set things up. Some simple pydantic models are
used for the trace file structure and some sanitation/formatting.

From a consumer standpoint (i.e. test runner) new tests using this decorator
behave differently and are being detected by a new data type yielded (a pydantic
model instance). Some logic was added to `execute_test` in
`tests/core/pyspec/eth2spec/gen_helpers/gen_base/gen_runner.py` to catch that
new case and apply new serialization method.

The way `wrapt.ObjectProxy` operates is that it allows you to create a proxy
object for e.g. consensus spec module and override things on it without
affecting any of the underlying logic (unlike monkey-patching). In our case here
we override all lowercase methods in the spec object by wrapping them in a
`wrapt` decorator with tracer function. Whenever a state is detected in any of
the method calls it gets automatically tracked and then it's checked again after
each method call to check for mutations. Everything is saved in a pydantic model
object for further dumping using existing reftest tooling.

## TODO

This is still being cooked.

I tried my best to separate core logic from the boilerplate needed but it could
be improved upon.

Some cleanup and polishing is still required.

Typing could be improved.

More example tests showcasing new features (or potentially some actually needed
tests that were waiting for this) could be added.

## Credits

Thanks to Leo for the initial idea and guidance, and to all the reviewers who
helped refine this.

Thanks to Cristobal for the first prototype of this framework, it's not used
here but I reviewed 4724 and got some inspiration from that.

Thanks to IG organizers, mentors, sponsors and fellow builders for making this
possible!
