from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey
from eth_consensus_specs.test.helpers.state import next_slots
from eth_consensus_specs.test.helpers.voluntary_exits import sign_voluntary_exit


@with_gloas_and_later
@spec_state_test
def test_voluntary_exit__invalid__builder_index(spec, state):
    """
    Test that a voluntary exit targeting a builder index is invalid.

    The voluntary exit operation is validator-only. Builders exit via
    builder exit requests.
    """
    builder_index = 0
    pubkey = state.builders[builder_index].pubkey
    privkey = builder_pubkey_to_privkey[pubkey]

    # Advance slots and finalize so that genesis-epoch builders become active
    epoch = spec.get_current_epoch(state)
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 3)
    state.finalized_checkpoint.epoch = epoch + 1
    assert spec.is_active_builder(state, builder_index)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None
