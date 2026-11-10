from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.gloas.block_processing.test_process_builder_exit_request import (
    advance_past_finalization,
    run_builder_exit_request_processing,
)
from eth_consensus_specs.test.helpers.constants import PQ


def prepare_builder_exit_request(spec, state, builder_index, prefix=None):
    """
    A builder exit request naming the XMSS public key of the builder at
    ``builder_index``, after ``prefix``.
    """
    if prefix is None:
        prefix = spec.XMSS_DEPOSIT_PREFIX
    builder = state.builders[builder_index]
    return spec.BuilderExitRequest(
        source_address=builder.execution_address,
        pubkey=spec.Bytes48(prefix + builder.pubkey),
    )


@with_phases([PQ])
@spec_state_test
def test_builder_exit_request(spec, state):
    builder_index = 0
    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)
    current_epoch = spec.get_current_epoch(state)
    builder_exit_request = prepare_builder_exit_request(spec, state, builder_index)

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request)

    assert not spec.is_active_builder(state, builder_index)
    expected_withdrawable = current_epoch + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    assert state.builders[builder_index].withdrawable_epoch == expected_withdrawable


@with_phases([PQ])
@spec_state_test
def test_builder_exit_request_ignores_pubkey_prefix(spec, state):
    builder_index = 0
    advance_past_finalization(spec, state)
    builder_exit_request = prepare_builder_exit_request(
        spec, state, builder_index, prefix=b"\xff" * 16
    )

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request)

    assert not spec.is_active_builder(state, builder_index)
