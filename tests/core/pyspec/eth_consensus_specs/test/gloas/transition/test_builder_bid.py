from eth_consensus_specs.test.context import (
    always_bls,
    ForkMeta,
    get_copy_of_spec,
    spec_with_config_overrides,
    with_fork_metas,
)
from eth_consensus_specs.test.helpers.constants import FULU, GLOAS
from eth_consensus_specs.test.helpers.fork_transition import do_fork, transition_until_fork
from eth_consensus_specs.test.helpers.genesis import build_mock_builder
from eth_consensus_specs.test.helpers.keys import builder_privkeys


@with_fork_metas([ForkMeta(pre_fork_name=FULU, post_fork_name=GLOAS, fork_epoch=2)])
@always_bls
def test_first_gloas_bid_signature_uses_gloas_domain(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    A builder signing a bid for the first Gloas slot may still be working from
    the last Fulu head state. The signature domain must come from the bid slot,
    not from that state's pre-fork state.fork.
    """
    del pre_tag, post_tag

    post_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"GLOAS_FORK_EPOCH": fork_epoch}
    )

    transition_until_fork(spec, state, fork_epoch)
    pre_fork_head_state = state.copy()

    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)
    assert state.slot == post_spec.compute_start_slot_at_epoch(fork_epoch)

    builder_index = 0
    state.builders.append(
        build_mock_builder(
            post_spec,
            builder_index,
            balance=post_spec.MIN_DEPOSIT_AMOUNT,
        )
    )

    bid = post_spec.ExecutionPayloadBid(
        slot=state.slot,
        builder_index=builder_index,
        value=post_spec.Gwei(1),
    )
    signature = post_spec.get_execution_payload_bid_signature(
        pre_fork_head_state,
        bid,
        builder_privkeys[builder_index],
    )
    signed_bid = post_spec.SignedExecutionPayloadBid(
        message=bid,
        signature=signature,
    )

    assert post_spec.verify_execution_payload_bid_signature(state, signed_bid)
