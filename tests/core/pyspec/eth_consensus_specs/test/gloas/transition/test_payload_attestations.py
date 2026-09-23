from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    ForkMeta,
    get_copy_of_spec,
    spec_with_config_overrides,
    with_fork_metas,
)
from eth_consensus_specs.test.gloas.block_processing.test_process_payload_attestation import (
    prepare_signed_payload_attestation,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
    sign_block,
)
from eth_consensus_specs.test.helpers.constants import FULU, GLOAS
from eth_consensus_specs.test.helpers.fork_transition import do_fork, transition_until_fork
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block, transition_to


@with_fork_metas([ForkMeta(pre_fork_name=FULU, post_fork_name=GLOAS, fork_epoch=2)])
@always_bls
def test_transition_rejects_pre_gloas_payload_attestation(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Test that the first Gloas block cannot include a payload attestation for
    the last slot before the fork, even though the zero-filled previous-epoch
    PTC makes it look otherwise valid.
    """
    post_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"GLOAS_FORK_EPOCH": fork_epoch}
    )
    transition_to(spec, state, spec.Uint64(fork_epoch) * spec.SLOTS_PER_EPOCH - 2)
    parent = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, parent)
    yield "pre", state

    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)
    block = build_empty_block(post_spec, state)
    data = post_spec.PayloadAttestationData(
        beacon_block_root=block.parent_root,
        slot=state.slot - 1,
        payload_present=True,
        blob_data_available=True,
    )
    ptc = state.ptc_window[data.slot % post_spec.SLOTS_PER_EPOCH]
    assert all(index == 0 for index in ptc)
    domain = post_spec.get_domain(
        state, post_spec.DOMAIN_PTC_ATTESTER, post_spec.compute_epoch_at_slot(data.slot)
    )
    signature = post_spec.bls.Sign(privkeys[0], post_spec.compute_signing_root(data, domain))
    payload_attestation = post_spec.PayloadAttestation(data=data, signature=signature)
    payload_attestation.aggregation_bits[0] = True
    block.body.payload_attestations.append(payload_attestation)
    assert post_spec.is_valid_indexed_payload_attestation(
        state,
        post_spec.IndexedPayloadAttestation(
            attesting_indices=post_spec.PayloadTimelinessCommitteeIndices.of(0),
            data=data,
            signature=signature,
        ),
    )

    unrestricted_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"GLOAS_FORK_EPOCH": 0}
    )
    unrestricted_state = state.copy()
    unrestricted_spec.process_block(unrestricted_state, block)
    block.state_root = unrestricted_state.hash_tree_root()
    signed_block = sign_block(post_spec, state, block)

    expect_assertion_error(lambda: post_spec.process_block(state, block))
    yield "blocks", [post_tag(signed_block)]
    yield "post", None


@with_fork_metas([ForkMeta(pre_fork_name=FULU, post_fork_name=GLOAS, fork_epoch=2)])
@always_bls
def test_transition_accepts_gloas_payload_attestations(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Test that the fork block carries no payload attestations and that the
    blocks after it accept payload attestations within and across epochs.
    """
    post_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(post_spec), {"GLOAS_FORK_EPOCH": fork_epoch}
    )
    transition_until_fork(spec, state, fork_epoch)
    yield "pre", state

    state, fork_block = do_fork(state, spec, post_spec, fork_epoch)
    assert len(fork_block.message.body.payload_attestations) == 0
    blocks = [post_tag(fork_block)]
    for slot in [
        state.slot + 1,
        post_spec.Uint64(fork_epoch + 1) * post_spec.SLOTS_PER_EPOCH,
    ]:
        if state.slot < slot - 1:
            parent = build_empty_block(post_spec, state, slot=slot - 1)
            blocks.append(post_tag(state_transition_and_sign_block(post_spec, state, parent)))
        block = build_empty_block_for_next_slot(post_spec, state)
        payload_attestation = prepare_signed_payload_attestation(
            post_spec, state, slot=state.slot, beacon_block_root=block.parent_root
        )
        block.body.payload_attestations.append(payload_attestation)
        blocks.append(post_tag(state_transition_and_sign_block(post_spec, state, block)))

    yield "blocks", blocks
    yield "post", state
