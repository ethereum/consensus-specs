from eth_consensus_specs.test.context import (
    expect_assertion_error,
    ForkMeta,
    get_copy_of_spec,
    spec_with_config_overrides,
    with_fork_metas,
)
from eth_consensus_specs.test.eip8483.block_processing.test_process_validator_pq_registration_request import (
    prepare_validator_pq_registration_request,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
    sign_block,
)
from eth_consensus_specs.test.helpers.constants import EIP8483, GLOAS
from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.fork_transition import state_transition_across_slots
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def _transition_to_eip8483_after_full_payload(spec, post_spec, state, fork_epoch, pre_tag):
    """
    Build blocks up to the last pre-fork slot, whose bid commits to a deposit
    request, then upgrade the state at the fork slot. Return the pre-fork
    blocks, the post-fork state, and the pre-fork execution requests.
    """
    last_pre_fork_slot = spec.Uint64(fork_epoch) * spec.SLOTS_PER_EPOCH - 1
    blocks = [
        pre_tag(block)
        for block in state_transition_across_slots(spec, state, last_pre_fork_slot - 1)
    ]

    requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests.of(
            prepare_deposit_request(
                spec, len(state.validators), spec.MIN_ACTIVATION_BALANCE, signed=True
            )
        ),
    )
    block = build_empty_block_for_next_slot(spec, state)
    bid = block.body.signed_execution_payload_bid.message
    bid.execution_requests_root = spec.hash_tree_root(requests)
    bid.block_hash = spec.Hash32(b"\x42" * 32)
    blocks.append(pre_tag(state_transition_and_sign_block(spec, state, block)))
    assert state.slot == last_pre_fork_slot

    spec.process_slots(state, state.slot + 1)
    state = post_spec.upgrade_to_eip8483(state)

    return blocks, state, requests


def _build_block_on_full_parent(post_spec, state, requests):
    block = build_empty_block(post_spec, state, slot=state.slot)
    block.body.signed_execution_payload_bid.message.parent_block_hash = (
        state.latest_execution_payload_bid.block_hash
    )
    block.body.parent_execution_requests = requests
    return block


@with_fork_metas([ForkMeta(pre_fork_name=GLOAS, post_fork_name=EIP8483, fork_epoch=2)])
def test_transition_full_last_pre_fork_payload(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Test that the first EIP-8483 block can build on the full payload of the
    last Gloas block, whose bid commits to the Gloas ``ExecutionRequests`` type.
    """
    post_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"EIP8483_FORK_EPOCH": fork_epoch}
    )
    yield "pre", state

    blocks, state, pre_fork_requests = _transition_to_eip8483_after_full_payload(
        spec, post_spec, state, fork_epoch, pre_tag
    )
    requests = post_spec.ExecutionRequests(deposits=pre_fork_requests.deposits)
    assert (
        post_spec.hash_tree_root(requests)
        != state.latest_execution_payload_bid.execution_requests_root
    )

    block = _build_block_on_full_parent(post_spec, state, requests)
    pre_pending_deposits_len = len(state.pending_deposits)
    post_spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    blocks.append(post_tag(sign_block(post_spec, state, block)))

    assert state.latest_block_hash == post_spec.Hash32(b"\x42" * 32)
    assert len(state.pending_deposits) == pre_pending_deposits_len + 1

    yield "blocks", blocks
    yield "post", state


@with_fork_metas([ForkMeta(pre_fork_name=GLOAS, post_fork_name=EIP8483, fork_epoch=2)])
def test_transition_full_last_pre_fork_payload_with_pq_registration(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Test that the first EIP-8483 block cannot add PQ registration requests to
    the requests of a full pre-fork parent, since its bid does not commit to
    them.
    """
    post_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"EIP8483_FORK_EPOCH": fork_epoch}
    )
    yield "pre", state

    blocks, state, pre_fork_requests = _transition_to_eip8483_after_full_payload(
        spec, post_spec, state, fork_epoch, pre_tag
    )
    requests = post_spec.ExecutionRequests(
        deposits=pre_fork_requests.deposits,
        validator_pq_registrations=post_spec.ValidatorPQRegistrationRequests.of(
            prepare_validator_pq_registration_request(post_spec, state, 0, b"\x33" * 64)
        ),
    )

    block = _build_block_on_full_parent(post_spec, state, requests)
    expect_assertion_error(lambda: post_spec.process_block(state, block))
    blocks.append(post_tag(sign_block(post_spec, state, block)))

    yield "blocks", blocks
    yield "post", None
