from dataclasses import dataclass
from .debug_helpers import print_epoch
from eth2spec.test.helpers.state import (
    next_slot,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
    sign_block,
)


@dataclass
class ProtocolMessage:
    payload: object
    valid: bool = True


@dataclass
class FCTestData:
    meta: dict
    anchor_block: object
    anchor_state: object
    blocks: list[ProtocolMessage]
    atts: list[ProtocolMessage]
    slashings: list[ProtocolMessage]


class BranchTip:
    def __init__(self, beacon_state, attestations, participants, eventually_justified_checkpoint):
        self.beacon_state = beacon_state
        self.attestations = attestations
        self.participants = participants
        self.eventually_justified_checkpoint = eventually_justified_checkpoint

    def copy(self):
        return BranchTip(self.beacon_state.copy(),
                         self.attestations.copy(),
                         self.participants.copy(),
                         self.eventually_justified_checkpoint)


def _get_eligible_attestations(spec, state, attestations) -> []:
    def _get_voting_source(target: spec.Checkpoint) -> spec.Checkpoint:
        if target.epoch == spec.get_current_epoch(state):
            return state.current_justified_checkpoint
        else:
            return state.previous_justified_checkpoint

    return [a for a in attestations if
            state.slot <= a.data.slot + spec.SLOTS_PER_EPOCH
            and a.data.source == _get_voting_source(a.data.target)]


def produce_block(spec, state, attestations, attester_slashings=[]):
    """
    Produces a block including as many attestations as it is possible.
    :return: Signed block, the post block state and attestations that were not included into the block.
    """

    # Filter out too old attestastions (TODO relax condition for Deneb)
    eligible_attestations = _get_eligible_attestations(spec, state, attestations)

    # Prepare attestations
    attestation_in_block = eligible_attestations[:spec.MAX_ATTESTATIONS]

    # Create a block with attestations
    block = build_empty_block(spec, state)
    for a in attestation_in_block:
        block.body.attestations.append(a)

    # Add attester slashings
    attester_slashings_in_block = attester_slashings[:spec.MAX_ATTESTER_SLASHINGS]
    for s in attester_slashings_in_block:
        block.body.attester_slashings.append(s)

    # Run state transition and sign off on a block
    post_state = state.copy()

    valid = True
    try:
        spec.process_block(post_state, block)
    except AssertionError:
        valid = False

    block.state_root = post_state.hash_tree_root()
    signed_block = sign_block(spec, post_state, block)

    # Filter out operations only if the block is valid
    not_included_attestations = attestations
    not_included_attester_slashings = attester_slashings
    if valid:
        not_included_attestations = [a for a in attestations if a not in attestation_in_block]
        not_included_attester_slashings = [s for s in attester_slashings if s not in attester_slashings_in_block]

    # Return a pre state if the block is invalid
    if not valid:
        post_state = state

    return signed_block, post_state, not_included_attestations, not_included_attester_slashings


def attest_to_slot(spec, state, slot_to_attest, participants_filter=None) -> []:
    """
    Creates attestation is a slot respecting participating validators.
    :return: produced attestations
    """

    assert slot_to_attest <= state.slot

    committees_per_slot = spec.get_committee_count_per_slot(state, spec.compute_epoch_at_slot(slot_to_attest))
    attestations_in_slot = []
    for index in range(committees_per_slot):
        beacon_committee = spec.get_beacon_committee(state, slot_to_attest, index)
        participants = beacon_committee if participants_filter is None else participants_filter(beacon_committee)
        if any(participants):
            attestation = get_valid_attestation(
                spec,
                state,
                slot_to_attest,
                index=index,
                signed=True,
                filter_participant_set=participants_filter
            )
            attestations_in_slot.append(attestation)

    return attestations_in_slot


def _compute_eventually_justified_epoch(spec, state, attestations, participants):
    # If not all attestations are included on chain
    # and attestation.data.target.epoch > beacon_state.current_justified_checkpoint.epoch
    # compute eventually_justified_checkpoint, a would be state.current_justified_checkpoint if all attestations
    # were included; this computation respects the validator partition that was building the branch
    if len(attestations) > 0 \
            and attestations[0].data.target.epoch > state.current_justified_checkpoint.epoch \
            and attestations[0].data.target.epoch > spec.GENESIS_EPOCH:
        branch_tip = BranchTip(state, attestations, participants, state.current_justified_checkpoint)
        _, new_branch_tip = advance_branch_to_next_epoch(spec, branch_tip, enable_attesting=False)

        return new_branch_tip.beacon_state.current_justified_checkpoint
    else:
        return state.current_justified_checkpoint


def advance_branch_to_next_epoch(spec, branch_tip, enable_attesting=True):
    """
    Advances a state of the block tree branch to the next epoch
    respecting validators participating in building and attesting to this branch.

    The returned beacon state is advanced to the first slot of the next epoch while no block for that slot is created,
    produced attestations that aren't yet included on chain are preserved for the future inclusion.
    """

    def participants_filter(comm):
        return [index for index in comm if index in branch_tip.participants]

    signed_blocks = []
    attestations = branch_tip.attestations.copy()
    state = branch_tip.beacon_state.copy()
    current_epoch = spec.get_current_epoch(state)
    target_slot = spec.compute_start_slot_at_epoch(current_epoch + 1)

    while state.slot < target_slot:
        # Produce block if the proposer is among participanting validators
        proposer = spec.get_beacon_proposer_index(state)
        if state.slot > spec.GENESIS_SLOT and proposer in branch_tip.participants:
            signed_block, state, attestations, _ = produce_block(spec, state, attestations)
            signed_blocks.append(signed_block)

        if enable_attesting:
            # Produce attestations
            attestations_in_slot = attest_to_slot(spec, state, state.slot, participants_filter)
            # And prepend them to the list
            attestations = list(attestations_in_slot) + attestations

        # Advance a slot
        next_slot(spec, state)

    # Cleanup attestations by removing outdated ones
    attestations = [a for a in attestations if
                    a.data.target.epoch in (spec.get_previous_epoch(state), spec.get_current_epoch(state))]

    eventually_justified_checkpoint = _compute_eventually_justified_epoch(spec, state, attestations,
                                                                          branch_tip.participants)

    return signed_blocks, BranchTip(state, attestations, branch_tip.participants, eventually_justified_checkpoint)


def advance_state_to_anchor_epoch(spec, state, anchor_epoch, debug) -> ([], BranchTip):
    signed_blocks = []

    genesis_tip = BranchTip(state.copy(), [], [*range(0, len(state.validators))],
                            state.current_justified_checkpoint)

    # Advance the state to the anchor_epoch
    anchor_tip = genesis_tip
    for epoch in range(spec.GENESIS_EPOCH, anchor_epoch + 1):
        pre_state = anchor_tip.beacon_state
        new_signed_blocks, anchor_tip = advance_branch_to_next_epoch(spec, anchor_tip)
        signed_blocks = signed_blocks + new_signed_blocks
        if debug:
            post_state = anchor_tip.beacon_state
            print('\nepoch', str(epoch) + ':')
            print('branch(*, *):', print_epoch(spec, pre_state, new_signed_blocks))
            print('              ', len(anchor_tip.participants), 'participants:', anchor_tip.participants)
            print('              ', 'state.current_justified_checkpoint:',
                  '(epoch=' + str(post_state.current_justified_checkpoint.epoch) +
                  ', root=' + str(post_state.current_justified_checkpoint.root)[:6] + ')')
            print('              ', 'eventually_justified_checkpoint:',
                  '(epoch=' + str(anchor_tip.eventually_justified_checkpoint.epoch) +
                  ', root=' + str(anchor_tip.eventually_justified_checkpoint.root)[:6] + ')')

    return signed_blocks, anchor_tip


