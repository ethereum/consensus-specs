from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import ALTAIR, BELLATRIX, CAPELLA, MAINNET
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.utils import bls


def get_sync_committee_aggregator(spec, state):
    """
    Find a validator that is in the current sync committee and is an aggregator.
    Returns (aggregator_index, subcommittee_index, subcommittee_pubkeys).
    """
    for validator_index in range(len(state.validators)):
        subnets = spec.compute_subnets_for_sync_committee(state, validator_index)
        for subnet_id in subnets:
            subcommittee_index = subnet_id
            selection_proof = spec.get_sync_committee_selection_proof(
                state,
                state.slot,
                subcommittee_index,
                privkeys[validator_index],
            )
            if spec.is_sync_committee_aggregator(selection_proof):
                subcommittee_pubkeys = spec.get_sync_subcommittee_pubkeys(state, subcommittee_index)
                return validator_index, subcommittee_index, subcommittee_pubkeys
    raise Exception("No sync committee aggregator found")


def get_other_sync_committee_aggregator(spec, state, subcommittee_index, excluded_indices=()):
    """
    Find another aggregator in the given sync subcommittee.
    Returns (aggregator_index, selection_proof).
    """
    subcommittee_pubkeys = spec.get_sync_subcommittee_pubkeys(state, subcommittee_index)
    excluded_indices = set(excluded_indices)
    for validator_index, validator in enumerate(state.validators):
        if validator_index in excluded_indices:
            continue
        if validator.pubkey not in subcommittee_pubkeys:
            continue
        selection_proof = spec.get_sync_committee_selection_proof(
            state,
            state.slot,
            subcommittee_index,
            privkeys[validator_index],
        )
        if spec.is_sync_committee_aggregator(selection_proof):
            return validator_index, selection_proof
    raise Exception("No additional sync committee aggregator found")


def create_valid_signed_contribution_and_proof(
    spec,
    state,
    aggregator_index,
    subcommittee_index,
    subcommittee_pubkeys,
    slot=None,
    block_root=None,
):
    """Create a valid SignedContributionAndProof."""
    if slot is None:
        slot = state.slot
    if block_root is None:
        block_root = spec.Root()

    # Find the aggregator's position in the subcommittee
    aggregator_pubkey = state.validators[aggregator_index].pubkey
    subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT

    # Build aggregation bits with the aggregator participating
    aggregation_bits = [False] * subcommittee_size
    for i, pubkey in enumerate(subcommittee_pubkeys):
        if pubkey == aggregator_pubkey:
            aggregation_bits[i] = True
            break

    # Create the aggregate signature
    epoch = spec.compute_epoch_at_slot(slot)
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = spec.compute_signing_root(block_root, domain)
    aggregate_signature = bls.Sign(privkeys[aggregator_index], signing_root)

    contribution = spec.SyncCommitteeContribution(
        slot=slot,
        beacon_block_root=block_root,
        subcommittee_index=subcommittee_index,
        aggregation_bits=aggregation_bits,
        signature=aggregate_signature,
    )

    # Create selection proof
    selection_proof = spec.get_sync_committee_selection_proof(
        state,
        slot,
        subcommittee_index,
        privkeys[aggregator_index],
    )

    contribution_and_proof = spec.ContributionAndProof(
        aggregator_index=aggregator_index,
        contribution=contribution,
        selection_proof=selection_proof,
    )

    # Sign the ContributionAndProof
    domain = spec.get_domain(state, spec.DOMAIN_CONTRIBUTION_AND_PROOF, epoch)
    signing_root = spec.compute_signing_root(contribution_and_proof, domain)
    signature = bls.Sign(privkeys[aggregator_index], signing_root)

    return spec.SignedContributionAndProof(
        message=contribution_and_proof,
        signature=signature,
    )


def run_validate_contribution_gossip(
    spec, seen, state, signed_contribution_and_proof, current_time_ms
):
    """Run validate_sync_committee_contribution_and_proof_gossip and return the result."""
    try:
        spec.validate_sync_committee_contribution_and_proof_gossip(
            seen,
            state,
            signed_contribution_and_proof,
            current_time_ms,
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__valid(spec, state):
    """Test that a valid contribution passes gossip validation."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_cap), "expected": "valid"}],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__valid_at_period_boundary(spec, state):
    """Test that a valid contribution passes at a sync committee period boundary,
    exercising the next_sync_committee path in get_sync_subcommittee_pubkeys."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"

    # Advance to the last slot of the first sync committee period
    period_length = spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    state.slot = period_length - 1

    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_cap), "expected": "valid"}],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
def test_gossip_sync_committee_contribution_and_proof__ignore_future_slot(spec, state):
    """Test that a contribution from a future slot is ignored."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    future_slot = state.slot + 1
    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
        slot=future_slot,
    )

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms,
    )
    assert result == "ignore"
    assert reason == "contribution is not for the current slot"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_cap),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
def test_gossip_sync_committee_contribution_and_proof__ignore_past_slot(spec, state):
    """Test that a contribution from a past slot is ignored."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    # Advance state so there's a past slot (gap >= 2 needed to exceed MAXIMUM_GOSSIP_CLOCK_DISPARITY)
    state.slot += 3

    yield "state", state

    past_slot = state.slot - 2
    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
        slot=past_slot,
    )

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms,
    )
    assert result == "ignore"
    assert reason == "contribution is not for the current slot"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_cap),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
def test_gossip_sync_committee_contribution_and_proof__reject_invalid_subcommittee_index(
    spec, state
):
    """Test that a contribution with subcommittee index out of range is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    # Tamper with the subcommittee index
    signed_cap.message.contribution.subcommittee_index = spec.SYNC_COMMITTEE_SUBNET_COUNT

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "subcommittee index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
def test_gossip_sync_committee_contribution_and_proof__reject_no_participants(spec, state):
    """Test that a contribution with no participants is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    # Clear all aggregation bits
    subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    signed_cap.message.contribution.aggregation_bits = [False] * subcommittee_size

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "contribution has no participants"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@with_presets([MAINNET], reason="minimal preset has modulo=1, so everyone is an aggregator")
@spec_state_test
def test_gossip_sync_committee_contribution_and_proof__reject_not_aggregator(spec, state):
    """Test that a contribution from a non-aggregator is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)

    # Find a validator in the sync committee that is NOT an aggregator
    non_aggregator_index = None
    for validator_index in range(len(state.validators)):
        subnets = spec.compute_subnets_for_sync_committee(state, validator_index)
        for subnet_id in subnets:
            subcommittee_index = subnet_id
            selection_proof = spec.get_sync_committee_selection_proof(
                state,
                state.slot,
                subcommittee_index,
                privkeys[validator_index],
            )
            if not spec.is_sync_committee_aggregator(selection_proof):
                non_aggregator_index = validator_index
                subcommittee_pubkeys = spec.get_sync_subcommittee_pubkeys(
                    state,
                    subcommittee_index,
                )
                break
        if non_aggregator_index is not None:
            break
    assert non_aggregator_index is not None, "no non-aggregator found"

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        non_aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "validator is not selected as aggregator"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
def test_gossip_sync_committee_contribution_and_proof__reject_aggregator_not_in_subcommittee(
    spec, state
):
    """Test that a contribution where the aggregator is not in the subcommittee is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    # Find a validator NOT in this subcommittee
    for vi in range(len(state.validators)):
        if state.validators[vi].pubkey not in subcommittee_pubkeys:
            signed_cap.message.aggregator_index = vi
            break

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "aggregator not in subcommittee"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
def test_gossip_sync_committee_contribution_and_proof__reject_aggregator_index_out_of_range(
    spec, state
):
    """Test that a contribution with aggregator index out of range is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    signed_cap.message.aggregator_index = len(state.validators)

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "aggregator index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__ignore_superset_contribution(spec, state):
    """Test that a contribution whose bits are a subset of a previously seen one is ignored.
    Sends superset first, then subset — the subset is ignored."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    block_root = spec.Root()
    epoch = spec.compute_epoch_at_slot(state.slot)
    subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT

    # Find aggregator's bit position and a second participant
    aggregator_pubkey = state.validators[aggregator_index].pubkey
    aggregator_bit = None
    for i, pubkey in enumerate(subcommittee_pubkeys):
        if pubkey == aggregator_pubkey:
            aggregator_bit = i
            break
    second_bit = (aggregator_bit + 1) % subcommittee_size

    second_pubkey = subcommittee_pubkeys[second_bit]
    second_validator_index = None
    for vi, v in enumerate(state.validators):
        if v.pubkey == second_pubkey:
            second_validator_index = vi
            break

    # Create superset contribution (two bits set)
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = spec.compute_signing_root(block_root, domain)
    sig1 = bls.Sign(privkeys[aggregator_index], signing_root)
    sig2 = bls.Sign(privkeys[second_validator_index], signing_root)

    superset_bits = [False] * subcommittee_size
    superset_bits[aggregator_bit] = True
    superset_bits[second_bit] = True

    superset_contribution = spec.SyncCommitteeContribution(
        slot=state.slot,
        beacon_block_root=block_root,
        subcommittee_index=subcommittee_index,
        aggregation_bits=superset_bits,
        signature=bls.Aggregate([sig1, sig2]),
    )
    selection_proof = spec.get_sync_committee_selection_proof(
        state,
        state.slot,
        subcommittee_index,
        privkeys[aggregator_index],
    )
    superset_cap = spec.ContributionAndProof(
        aggregator_index=aggregator_index,
        contribution=superset_contribution,
        selection_proof=selection_proof,
    )
    cap_domain = spec.get_domain(state, spec.DOMAIN_CONTRIBUTION_AND_PROOF, epoch)
    signed_superset = spec.SignedContributionAndProof(
        message=superset_cap,
        signature=bls.Sign(
            privkeys[aggregator_index], spec.compute_signing_root(superset_cap, cap_domain)
        ),
    )

    yield get_filename(signed_superset), signed_superset

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # First: superset passes
    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_superset,
        current_time_ms + 500,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {"offset_ms": 500, "message": get_filename(signed_superset), "expected": "valid"}
    )

    # Second: subset (one bit) — prior is a non-strict superset, so this is ignored
    signed_subset = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
        block_root=block_root,
    )

    yield get_filename(signed_subset), signed_subset

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_subset,
        current_time_ms + 600,
    )
    assert result == "ignore"
    assert reason == "already seen contribution for this data"
    messages.append(
        {
            "offset_ms": 600,
            "message": get_filename(signed_subset),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__valid_non_superset_contribution(spec, state):
    """Test that a contribution with new bits not in any prior passes the superset check.
    Sends subset first, then superset — exercises the is_non_strict_superset=False path."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    block_root = spec.Root()
    epoch = spec.compute_epoch_at_slot(state.slot)
    subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT

    # Find aggregator's bit position and a second participant
    aggregator_pubkey = state.validators[aggregator_index].pubkey
    aggregator_bit = None
    for i, pubkey in enumerate(subcommittee_pubkeys):
        if pubkey == aggregator_pubkey:
            aggregator_bit = i
            break
    second_bit = (aggregator_bit + 1) % subcommittee_size

    second_pubkey = subcommittee_pubkeys[second_bit]
    second_validator_index = None
    for vi, v in enumerate(state.validators):
        if v.pubkey == second_pubkey:
            second_validator_index = vi
            break

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # First: subset contribution (one bit) — passes validation
    signed_subset = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
        block_root=block_root,
    )

    yield get_filename(signed_subset), signed_subset

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_subset,
        current_time_ms + 500,
    )
    assert result == "valid"
    assert reason is None
    messages.append({"offset_ms": 500, "message": get_filename(signed_subset), "expected": "valid"})

    # Second: superset contribution (two bits) from a different aggregator
    # The new contribution has a bit the prior doesn't, so is_non_strict_superset=False, break.
    second_aggregator_index, second_selection_proof = get_other_sync_committee_aggregator(
        spec,
        state,
        subcommittee_index,
        excluded_indices=(aggregator_index,),
    )
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = spec.compute_signing_root(block_root, domain)
    sig1 = bls.Sign(privkeys[aggregator_index], signing_root)
    sig2 = bls.Sign(privkeys[second_validator_index], signing_root)

    superset_bits = [False] * subcommittee_size
    superset_bits[aggregator_bit] = True
    superset_bits[second_bit] = True

    superset_contribution = spec.SyncCommitteeContribution(
        slot=state.slot,
        beacon_block_root=block_root,
        subcommittee_index=subcommittee_index,
        aggregation_bits=superset_bits,
        signature=bls.Aggregate([sig1, sig2]),
    )
    superset_cap = spec.ContributionAndProof(
        aggregator_index=second_aggregator_index,
        contribution=superset_contribution,
        selection_proof=second_selection_proof,
    )
    cap_domain = spec.get_domain(state, spec.DOMAIN_CONTRIBUTION_AND_PROOF, epoch)
    signed_superset = spec.SignedContributionAndProof(
        message=superset_cap,
        signature=bls.Sign(
            privkeys[second_aggregator_index],
            spec.compute_signing_root(superset_cap, cap_domain),
        ),
    )

    yield get_filename(signed_superset), signed_superset

    # Superset has new bits → is_non_strict_superset=False, passes the check → valid
    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_superset,
        current_time_ms + 600,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {"offset_ms": 600, "message": get_filename(signed_superset), "expected": "valid"}
    )

    yield "messages", "meta", messages


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__ignore_duplicate_aggregator(spec, state):
    """Test that a second contribution from the same aggregator/slot/subcommittee is ignored,
    even with a different beacon_block_root (bypassing the superset check)."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    # First contribution with default block_root
    signed_cap1 = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    yield get_filename(signed_cap1), signed_cap1

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # First validation should pass
    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap1,
        current_time_ms + 500,
    )
    assert result == "valid"
    assert reason is None
    messages.append({"offset_ms": 500, "message": get_filename(signed_cap1), "expected": "valid"})

    # Second contribution with a different beacon_block_root
    # (different root means the superset check won't match, so we hit the aggregator dedup)
    different_root = spec.Root(b"\x01" * 32)
    signed_cap2 = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
        block_root=different_root,
    )

    yield get_filename(signed_cap2), signed_cap2

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap2,
        current_time_ms + 600,
    )
    assert result == "ignore"
    assert reason == "already seen contribution from this aggregator"
    messages.append(
        {
            "offset_ms": 600,
            "message": get_filename(signed_cap2),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__reject_invalid_selection_proof(spec, state):
    """Test that a contribution with invalid selection proof is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    # Replace selection proof with a valid aggregator proof from another validator in the
    # same subcommittee so the aggregator-selection check still passes.
    _, wrong_selection_proof = get_other_sync_committee_aggregator(
        spec,
        state,
        subcommittee_index,
        excluded_indices=(aggregator_index,),
    )
    signed_cap.message.selection_proof = wrong_selection_proof

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "invalid selection proof signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__reject_invalid_aggregator_signature(
    spec, state
):
    """Test that a contribution with invalid aggregator signature is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    # Replace the outer signature with one signed by a different key
    wrong_key = privkeys[(aggregator_index + 1) % len(privkeys)]
    epoch = spec.compute_epoch_at_slot(state.slot)
    domain = spec.get_domain(state, spec.DOMAIN_CONTRIBUTION_AND_PROOF, epoch)
    signing_root = spec.compute_signing_root(signed_cap.message, domain)
    signed_cap.signature = bls.Sign(wrong_key, signing_root)

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "invalid aggregator signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([ALTAIR, BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_gossip_sync_committee_contribution_and_proof__reject_invalid_aggregate_signature(
    spec, state
):
    """Test that a contribution with invalid aggregate signature is rejected."""
    yield "topic", "meta", "sync_committee_contribution_and_proof"
    yield "state", state

    seen = get_seen(spec)
    aggregator_index, subcommittee_index, subcommittee_pubkeys = get_sync_committee_aggregator(
        spec, state
    )

    signed_cap = create_valid_signed_contribution_and_proof(
        spec,
        state,
        aggregator_index,
        subcommittee_index,
        subcommittee_pubkeys,
    )

    # Replace the aggregate signature with one signed by a different key
    wrong_key = privkeys[(aggregator_index + 1) % len(privkeys)]
    epoch = spec.compute_epoch_at_slot(state.slot)
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = spec.compute_signing_root(
        signed_cap.message.contribution.beacon_block_root, domain
    )
    signed_cap.message.contribution.signature = bls.Sign(wrong_key, signing_root)

    # Re-sign the outer message since modifying the inner contribution changes the hash
    domain = spec.get_domain(state, spec.DOMAIN_CONTRIBUTION_AND_PROOF, epoch)
    signing_root = spec.compute_signing_root(signed_cap.message, domain)
    signed_cap.signature = bls.Sign(privkeys[aggregator_index], signing_root)

    yield get_filename(signed_cap), signed_cap

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_contribution_gossip(
        spec,
        seen,
        state,
        signed_cap,
        current_time_ms + 500,
    )
    assert result == "reject"
    assert reason == "invalid aggregate signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_cap),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
