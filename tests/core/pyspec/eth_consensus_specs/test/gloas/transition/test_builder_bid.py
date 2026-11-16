from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    ForkMeta,
    get_copy_of_spec,
    spec_with_config_overrides,
    with_fork_metas,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    next_epoch_with_attestations,
    next_slots_with_attestations,
)
from eth_consensus_specs.test.helpers.block import build_empty_block, sign_block
from eth_consensus_specs.test.helpers.constants import FULU, GLOAS, MINIMAL
from eth_consensus_specs.test.helpers.deposits import (
    make_withdrawal_credentials,
    prepare_pending_deposit,
)
from eth_consensus_specs.test.helpers.fork_transition import do_fork
from eth_consensus_specs.test.helpers.gloas.bid import build_signed_bid
from eth_consensus_specs.test.helpers.keys import builder_privkeys, builder_pubkeys


def _transition_to_pre_fork_head_with_queued_builder(spec, post_spec, state, fork_epoch):
    """
    Return the post-state of the last Fulu block, the head state of a builder
    bidding for the first Gloas slot. A builder deposit is queued for
    ``upgrade_to_gloas`` to onboard, and the chain finalizes past its deposit
    epoch at the fork so that the builder is active in the first Gloas block.
    """
    # A top-up larger than all deposit churn before the fork holds the builder
    # deposit in the queue, so Fulu does not apply it as a validator deposit.
    churn = spec.get_activation_exit_churn_limit(state)
    state.pending_deposits.append(prepare_pending_deposit(spec, 0, churn * (fork_epoch + 1)))
    state.pending_deposits.append(
        prepare_pending_deposit(
            spec,
            validator_index=None,
            amount=spec.MIN_ACTIVATION_BALANCE,
            pubkey=builder_pubkeys[0],
            privkey=builder_privkeys[0],
            withdrawal_credentials=make_withdrawal_credentials(
                spec, post_spec.BUILDER_WITHDRAWAL_PREFIX, b"\x11"
            ),
            signed=True,
        )
    )

    for _ in range(fork_epoch - 1):
        _, _, state = next_epoch_with_attestations(
            spec, state, fill_cur_epoch=True, fill_prev_epoch=True
        )
    _, _, state = next_slots_with_attestations(
        spec, state, spec.SLOTS_PER_EPOCH - 1, fill_cur_epoch=True, fill_prev_epoch=True
    )

    assert state.slot == spec.compute_start_slot_at_epoch(fork_epoch) - 1
    assert state.pending_deposits[-1].pubkey == builder_pubkeys[0]
    return state


def _build_first_gloas_block_with_builder_bid(post_spec, state, sign_bid):
    builder_index = post_spec.BuilderIndex(0)
    assert state.builders[builder_index].pubkey == builder_pubkeys[0]
    assert post_spec.is_active_builder(state, builder_index)

    block = build_empty_block(post_spec, state)
    signed_bid = build_signed_bid(
        post_spec,
        state,
        builder_index,
        slot=state.slot,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=block.parent_root,
        value=post_spec.Gwei(10**9),
        valid_signature=False,
    )
    signed_bid.signature = sign_bid(signed_bid.message)
    block.body.signed_execution_payload_bid = signed_bid
    return block


@with_fork_metas([ForkMeta(pre_fork_name=FULU, post_fork_name=GLOAS, fork_epoch=4)])
@with_presets([MINIMAL], reason="too slow")
@always_bls
def test_transition_builder_bid_signed_from_pre_fork_head(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Test that the first Gloas block accepts a bid that the builder signed from
    its head state, the post-state of the last Fulu block. That state still has
    the Fulu fork, but the bid must be signed with the Gloas fork version.
    """
    post_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"GLOAS_FORK_EPOCH": fork_epoch}
    )
    state = _transition_to_pre_fork_head_with_queued_builder(spec, post_spec, state, fork_epoch)
    head_state = state.copy()
    yield "pre", state

    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)
    block = _build_first_gloas_block_with_builder_bid(
        post_spec,
        state,
        lambda bid: post_spec.get_execution_payload_bid_signature(
            head_state, bid, builder_privkeys[0]
        ),
    )
    post_spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    signed_block = sign_block(post_spec, state, block)

    assert state.latest_execution_payload_bid == block.body.signed_execution_payload_bid.message
    yield "blocks", [post_tag(signed_block)]
    yield "post", state


@with_fork_metas([ForkMeta(pre_fork_name=FULU, post_fork_name=GLOAS, fork_epoch=4)])
@with_presets([MINIMAL], reason="too slow")
@always_bls
def test_transition_builder_bid_signed_with_pre_fork_version(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Test that the first Gloas block rejects a bid signed with the Fulu fork
    version, as a builder taking the fork from its pre-fork head state would.
    The block's state root assumes the bid signature is valid, so the bid
    signature is the only reason to reject the block.
    """
    post_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"GLOAS_FORK_EPOCH": fork_epoch}
    )
    state = _transition_to_pre_fork_head_with_queued_builder(spec, post_spec, state, fork_epoch)
    yield "pre", state

    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)
    domain = post_spec.compute_domain(
        post_spec.DOMAIN_BEACON_BUILDER,
        spec.config.FULU_FORK_VERSION,
        state.genesis_validators_root,
    )
    block = _build_first_gloas_block_with_builder_bid(
        post_spec,
        state,
        lambda bid: post_spec.bls.Sign(
            builder_privkeys[0], post_spec.compute_signing_root(bid, domain)
        ),
    )

    lenient_spec = get_copy_of_spec(post_spec)
    lenient_spec.verify_execution_payload_bid_signature = lambda state, signed_bid: True
    lenient_state = state.copy()
    lenient_spec.process_block(lenient_state, block)
    block.state_root = lenient_state.hash_tree_root()
    signed_block = sign_block(post_spec, state, block)

    expect_assertion_error(lambda: post_spec.process_block(state, block))
    yield "blocks", [post_tag(signed_block)]
    yield "post", None
