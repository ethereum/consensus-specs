from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    to_single_attestation,
)
from eth_consensus_specs.test.helpers.constants import ELECTRA
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen, wrap_genesis_block
from eth_consensus_specs.test.helpers.state import next_slot


def get_correct_subnet(spec, state, attestation):
    committees_per_slot = spec.get_committee_count_per_slot(state, attestation.data.target.epoch)
    return spec.compute_subnet_for_attestation(
        committees_per_slot, attestation.data.slot, attestation.committee_index
    )


def run_validate_beacon_attestation_gossip(
    spec, seen, store, state, attestation, subnet_id, current_time_ms
):
    try:
        spec.validate_beacon_attestation_gossip(
            seen, store, state, attestation, subnet_id, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def prepare_single_attestation(spec, state):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()
    next_slot(spec, state)
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)
    single = to_single_attestation(spec, state, attestation)
    return store, signed_anchor, single


@with_phases([ELECTRA])
@spec_state_test
def test_gossip_beacon_attestation__reject_nonzero_data_index(spec, state):
    """
    [New in Electra:EIP7549] Test that a ``SingleAttestation`` with
    ``data.index != 0`` is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, signed_anchor, attestation = prepare_single_attestation(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Set a non-zero data index (EIP-7549 forbids this).
    attestation.data.index = spec.CommitteeIndex(1)

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "attestation data index is non-zero"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ELECTRA])
@spec_state_test
def test_gossip_beacon_attestation__reject_attester_not_in_committee(spec, state):
    """
    [New in Electra:EIP7549] Test that a ``SingleAttestation`` whose
    ``attester_index`` is not a member of the encoded committee is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, signed_anchor, attestation = prepare_single_attestation(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Pick a validator index that is not in the committee for this slot/index.
    committee = set(
        spec.get_beacon_committee(state, attestation.data.slot, attestation.committee_index)
    )
    outsider_index = next(
        spec.ValidatorIndex(i) for i in range(len(state.validators)) if i not in committee
    )
    attestation.attester_index = outsider_index

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "attester is not a member of the committee"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
