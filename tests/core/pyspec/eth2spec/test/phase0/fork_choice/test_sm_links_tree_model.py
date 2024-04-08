import random
from pathlib import Path
from minizinc import (
    Instance,
    Model,
    Solver,
)
from eth2spec.test.context import (
    spec_state_test,
    with_altair_and_later,
    with_presets,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)
from eth2spec.test.helpers.attestations import (
    next_epoch_with_attestations,
    next_slots_with_attestations,
    state_transition_with_full_block,
    get_valid_attestation_at_slot,
    get_valid_attestation,
)
from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
    add_attestation,
    add_attester_slashing,
    add_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
    next_slot,
    next_epoch,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    build_empty_block,
    sign_block,
)

MAX_JUSTIFICATION_RATE = 99
MIN_JUSTIFICATION_RATE = 91

MAX_UNDERJUSTIFICATION_RATE = 65
MIN_UNDERJUSTIFICATION_RATE = 55

EMPTY_SLOTS_RATE = 3
MAX_TIPS_TO_ATTEST = 2

OFF_CHAIN_ATTESTATION_RATE = 10
ON_CHAIN_ATTESTATION_RATE = 20

MAX_ATTESTER_SLASHINGS = 8
ATTESTER_SLASHINGS_RATE = 8
OFF_CHAIN_SLASHING_RATE = 33
ON_CHAIN_SLASHING_RATE = 33

INVALID_MESSAGES_RATE = 5

class SmLink(tuple):
    @property
    def source(self):
        return self[0]

    @property
    def target(self):
        return self[1]


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


class ProtocolMessage:
    def __init__(self, payload, valid=True):
        self.payload = payload
        self.valid = valid


def _justifying_participation_rate(rnd: random.Random):
    """
    Should be high enough to ensure justification happens
    """
    return rnd.randint(MIN_JUSTIFICATION_RATE, MAX_JUSTIFICATION_RATE)


def _under_justifying_participation_rate(rnd: random.Random):
    return rnd.randint(MIN_UNDERJUSTIFICATION_RATE, MAX_UNDERJUSTIFICATION_RATE)


def _create_new_branch_tip(spec, branch_tips: dict[SmLink:BranchTip], sm_link: SmLink) -> BranchTip:
    """
    Initialized a branch tip state for a new branch satisfying the given sm_link.
    :return: a new branch tip.
    """

    # Find all forks with justified source
    tips_with_justified_source = [s for s in branch_tips.values()
                                  if s.eventually_justified_checkpoint.epoch == sm_link.source]
    assert len(tips_with_justified_source) > 0

    # Find and return the most adanced one
    most_recent_tip = max(tips_with_justified_source, key=lambda s: s.beacon_state.slot)
    return BranchTip(most_recent_tip.beacon_state.copy(), most_recent_tip.attestations.copy(), [],
                     most_recent_tip.eventually_justified_checkpoint)


def _sample_validator_partition(spec, state, epoch, participation_rate, rnd) -> []:
    active_validator_indices = spec.get_active_validator_indices(state, epoch)
    participants_count = len(active_validator_indices) * participation_rate // 100
    return rnd.sample(active_validator_indices, participants_count)


def _compute_validator_partitions(spec, branch_tips, current_links, current_epoch, rnd: random.Random) -> dict[
                                                                                                          SmLink:[int]]:
    """
    Note: O(N) complex (N is a number of validators) and might be inefficient with large validator sets

    Uniformly distributes active validators between active forks specified by a given set of sm_links.
    Handles two cases:
        1. Single active fork:
           Randomly sample a single validator partition taking into account
           whether the fork should have a justified checkpoint in the current epoch.
        2. Multiple active forks:
           i. sample the majority partition if one of the forks is about to justify during the current epoch,
           ii. run through a set of active validators and randomly select a fork for it,
               do no consider validators that were sampled into the majority partition.

    Does not take into account validator's effective balance, based on assumption that the EB of every validator
    is nearly the same.

    :return: [SmLink: participants]
    """

    justifying_links = [l for l in current_links if l.target == current_epoch]

    # Justifying conflicting checkpoints isn't supported
    assert len(justifying_links) < 2
    justifying_link = justifying_links[0] if any(justifying_links) else None

    # Sanity check
    for sm_link in current_links:
        assert spec.get_current_epoch(branch_tips[sm_link].beacon_state) == current_epoch

    # Case when there is just one active fork
    if len(current_links) == 1:
        the_sm_link = current_links[0]

        if the_sm_link == justifying_link:
            participation_rate = _justifying_participation_rate(rnd)
        else:
            participation_rate = _under_justifying_participation_rate(rnd)

        state = branch_tips[the_sm_link].beacon_state
        participants = _sample_validator_partition(spec, state, current_epoch, participation_rate, rnd)

        return {the_sm_link: participants}

    # Cases with more than one active fork
    participants = {l: [] for l in current_links}

    # Move the majority to the branch containing justification target
    justifying_participants = []
    if justifying_link is not None:
        state = branch_tips[justifying_link].beacon_state
        justifying_participants = _sample_validator_partition(spec,
                                                              branch_tips[justifying_link].beacon_state,
                                                              current_epoch,
                                                              _justifying_participation_rate(rnd),
                                                              rnd)

        participants[justifying_link] = justifying_participants

    # Collect a set of active validator indexes across all forks
    active_validator_per_branch = {}
    all_active_validators = set()
    for l in current_links:
        state = branch_tips[l].beacon_state
        active_validator_per_branch[l] = spec.get_active_validator_indices(state, current_epoch)
        all_active_validators.update(active_validator_per_branch[l])

    # Remove validators selected for justifying brach from the pool of active participants
    all_active_validators = all_active_validators.difference(justifying_participants)

    # For each index:
    #   1) Collect a set of branches where the validators is in active state (except for justifying branch)
    #   2) Append the index to the list of participants for a randomly selected branch
    for index in all_active_validators:
        active_branches = [l for l in current_links if
                           index in active_validator_per_branch[l] and l not in justifying_links]
        participants[tuple(rnd.choice(active_branches))].append(index)

    return participants


def _get_eligible_attestations(spec, state, attestations) -> []:
    return [a for a in attestations if state.slot <= a.data.slot + spec.SLOTS_PER_EPOCH]


def _produce_block(spec, state, attestations, attester_slashings=[]):
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


def _attest_to_slot(spec, state, slot_to_attest, participants_filter=None) -> []:
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
        _, new_branch_tip = _advance_branch_to_next_epoch(spec, branch_tip, enable_attesting=False)

        return new_branch_tip.beacon_state.current_justified_checkpoint
    else:
        return state.current_justified_checkpoint


def _advance_branch_to_next_epoch(spec, branch_tip, enable_attesting=True):
    """
    Advances a state of the block tree branch to the next epoch
    respecting validators participanting in building and attesting to this branch.

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
            signed_block, state, attestations, _ = _produce_block(spec, state, attestations)
            signed_blocks.append(signed_block)

        if enable_attesting:
            # Produce attestations
            attestations_in_slot = _attest_to_slot(spec, state, state.slot, participants_filter)
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


def _any_change_to_validator_partitions(spec, sm_links, current_epoch, anchor_epoch) -> bool:
    """
    Returns ``true`` if validator partitions should be re-shuffled to advance branches in the current epoch:
        1. The first epoch after the anchor epoch always requires a new shuffling.
        2. Previous epoch has justified checkpoints.
           Therefore, new supermajority links may need to be processed during the current epoch,
           thus new block tree branches with new validator partitions may need to be created.
        3. Current epoch has justified checkpoint.
           Therefore, the majority of validators must be moved to the justifying branch.
    """
    assert current_epoch > anchor_epoch

    previous_epoch = current_epoch - 1

    if previous_epoch == anchor_epoch:
        return True

    for l in sm_links:
        if l.target == current_epoch or l.target == previous_epoch:
            return True

    return False


def _attesters_in_block(spec, epoch_state, signed_block, target_epoch):
    block = signed_block.message
    attesters = set()
    for a in block.body.attestations:
        if a.data.target.epoch == target_epoch:
            attesters.update(spec.get_attesting_indices(epoch_state, a.data, a.aggregation_bits))
    return attesters


def _print_block(spec, epoch_state, signed_block):
    block = signed_block.message
    if spec.get_current_epoch(epoch_state) > spec.GENESIS_EPOCH:
        prev_attesters = _attesters_in_block(spec, epoch_state, signed_block, spec.get_previous_epoch(epoch_state))
    else:
        prev_attesters = set()

    curr_attesters = _attesters_in_block(spec, epoch_state, signed_block, spec.get_current_epoch(epoch_state))
    prev_attester_str = 'a_prev=' + str(prev_attesters) if any(prev_attesters) else 'a_prev={}'
    curr_attester_str = 'a_curr=' + str(curr_attesters) if any(curr_attesters) else 'a_curr={}'

    return 'b(r=' + str(spec.hash_tree_root(block))[:6] + ', p=' + str(
        block.proposer_index) + ', ' + prev_attester_str + ', ' + curr_attester_str + ')'


def _print_slot_range(spec, root_state, signed_blocks, start_slot, end_slot):
    ret = ""
    epoch_state = root_state.copy()
    for slot in range(start_slot, end_slot):
        transition_to(spec, epoch_state, slot)
        blocks_in_slot = [b for b in signed_blocks if b.message.slot == slot]
        if ret != "":
            ret = ret + " <- "
        if any(blocks_in_slot):
            ret = ret + "s(" + str(slot) + ", " + _print_block(spec, epoch_state, blocks_in_slot[0]) + ")"
        else:
            ret = ret + "s(" + str(slot) + ", _)"

    return ret


def _print_epoch(spec, epoch_state, signed_blocks):
    epoch = spec.get_current_epoch(epoch_state)
    start_slot = spec.compute_start_slot_at_epoch(epoch)
    return _print_slot_range(spec, epoch_state, signed_blocks, start_slot, start_slot + spec.SLOTS_PER_EPOCH)


def _print_block_tree(spec, root_state, signed_blocks):
    start_slot = signed_blocks[0].message.slot
    end_slot = signed_blocks[len(signed_blocks) - 1].message.slot + 1
    return _print_slot_range(spec, root_state, signed_blocks, start_slot, end_slot)


def _advance_state_to_anchor_epoch(spec, state, anchor_epoch, debug) -> ([], BranchTip):
    signed_blocks = []

    genesis_tip = BranchTip(state.copy(), [], [*range(0, len(state.validators))],
                            state.current_justified_checkpoint)

    # Advance the state to the anchor_epoch
    anchor_tip = genesis_tip
    for epoch in range(spec.GENESIS_EPOCH, anchor_epoch + 1):
        pre_state = anchor_tip.beacon_state
        new_signed_blocks, anchor_tip = _advance_branch_to_next_epoch(spec, anchor_tip)
        signed_blocks = signed_blocks + new_signed_blocks
        if debug:
            post_state = anchor_tip.beacon_state
            print('\nepoch', str(epoch) + ':')
            print('branch(*, *):', _print_epoch(spec, pre_state, new_signed_blocks))
            print('              ', len(anchor_tip.participants), 'participants:', anchor_tip.participants)
            print('              ', 'state.current_justified_checkpoint:',
                  '(epoch=' + str(post_state.current_justified_checkpoint.epoch) +
                  ', root=' + str(post_state.current_justified_checkpoint.root)[:6] + ')')
            print('              ', 'eventually_justified_checkpoint:',
                  '(epoch=' + str(anchor_tip.eventually_justified_checkpoint.epoch) +
                  ', root=' + str(anchor_tip.eventually_justified_checkpoint.root)[:6] + ')')

    return signed_blocks, anchor_tip


def _generate_sm_link_tree(spec, genesis_state, sm_links, rnd: random.Random, debug) -> ([], BranchTip):
    """
    Generates a sequence of blocks satisfying a tree of supermajority links specified in the sm_links list,
    i.e. a sequence of blocks with attestations required to create given supermajority links.

    The block generation strategy is to run through a span of epochs covered by the supermajority links
    and for each epoch of the span apply the following steps:
        1. Obtain a list of supermajority links covering the epoch.
        2. Create a new block tree branch (fork) for every newly observed supermajority link.
        3. Randomly sample all active validators between a set of forks that are being advanced in the epoch.
           Validator partitions are disjoint and are changing only at the epoch boundary.
           If no new branches are created in the current epoch then partitions from the previous epoch will be used
           to advahce the state of every fork to the next epoch.
        4. Advance every fork to the next epoch respecting a validator partition assigned to it in the current epoch.
           Preserve attestations produced but not yet included on chain for potential inclusion in the next epoch.
        5. Justify required checkpoints by moving the majority of validators to the justifying fork,
           this is taken into account by step (3).

    :return: Sequence of signed blocks oredered by a slot number.
    """
    assert any(sm_links)
    # Cases where source == GENESIS_EPOCH + 1 aren't supported,
    # because the protocol can't justify in epoch GENESIS_EPOCH + 1
    assert len([sm_link for sm_link in sm_links if sm_link.source == spec.GENESIS_EPOCH + 1]) == 0

    # Find anchor epoch
    anchor_epoch = min(sm_links, key=lambda l: l.source).source

    signed_blocks, anchor_tip = _advance_state_to_anchor_epoch(spec, genesis_state, anchor_epoch, debug)

    # branch_tips hold the most recent state, validator partition and not included attestations for every fork
    # Initialize branch tips with the anchor tip
    anchor_link = SmLink((spec.GENESIS_EPOCH, anchor_epoch))
    branch_tips = {anchor_link: anchor_tip}

    highest_target_sm_link = max(sm_links, key=lambda l: l.target)

    # Finish at after the highest justified checkpoint
    for current_epoch in range(anchor_epoch + 1, highest_target_sm_link.target + 1):
        # Obtain sm links that span over the current epoch
        current_epoch_sm_links = [l for l in sm_links if l.source < current_epoch <= l.target]

        # Initialize new forks
        for l in (l for l in current_epoch_sm_links if branch_tips.get(l) is None):
            new_branch_tip = _create_new_branch_tip(spec, branch_tips, l)
            # Abort the test if any sm_links constraint appears to be unreachable
            # because the justification of the source checkpoint hasn't been realized on chain yet
            if l.target == current_epoch and new_branch_tip.beacon_state.current_justified_checkpoint.epoch < l.source:
                return [], new_branch_tip

            branch_tips[l] = new_branch_tip

        # Reshuffle partitions if needed
        if _any_change_to_validator_partitions(spec, sm_links, current_epoch, anchor_epoch):
            partitions = _compute_validator_partitions(spec, branch_tips, current_epoch_sm_links, current_epoch, rnd)
            for l in partitions.keys():
                old_tip_state = branch_tips[l]
                new_tip_state = BranchTip(old_tip_state.beacon_state, old_tip_state.attestations, partitions[l],
                                          old_tip_state.eventually_justified_checkpoint)
                branch_tips[l] = new_tip_state

        # Debug checks
        if debug:
            print('\nepoch', str(current_epoch) + ':')
            # Partitions are disjoint
            for l1 in current_epoch_sm_links:
                l1_participants = branch_tips[l1].participants
                for l2 in current_epoch_sm_links:
                    if l1 != l2:
                        l2_participants = branch_tips[l2].participants
                        intersection = set(l1_participants).intersection(l2_participants)
                        assert len(intersection) == 0, \
                            str(l1) + ' and ' + str(l2) + ' has common participants: ' + str(intersection)

        # Advance every branch taking into account attestations from past epochs and voting partitions
        for sm_link in current_epoch_sm_links:
            branch_tip = branch_tips[sm_link]
            assert spec.get_current_epoch(branch_tip.beacon_state) == current_epoch, \
                'Unexpected current_epoch(branch_tip.beacon_state): ' + str(
                    spec.get_current_epoch(branch_tip.beacon_state)) + ' != ' + str(current_epoch)
            new_signed_blocks, new_branch_tip = _advance_branch_to_next_epoch(spec, branch_tip)

            # Run sanity checks
            post_state = new_branch_tip.beacon_state
            assert spec.get_current_epoch(post_state) == current_epoch + 1, \
                'Unexpected post_state epoch: ' + str(spec.get_current_epoch(post_state)) + ' != ' + str(
                    current_epoch + 1)
            if sm_link.target == current_epoch:
                assert post_state.previous_justified_checkpoint.epoch == sm_link.source, \
                    'Unexpected previous_justified_checkpoint.epoch: ' + str(
                        post_state.previous_justified_checkpoint.epoch) + ' != ' + str(sm_link.source)
                assert new_branch_tip.eventually_justified_checkpoint.epoch == sm_link.target, \
                    'Unexpected eventually_justified_checkpoint.epoch: ' + str(
                        new_branch_tip.eventually_justified_checkpoint.epoch) + ' != ' + str(sm_link.target)
            elif (sm_link.source != new_branch_tip.eventually_justified_checkpoint.epoch):
                # Abort the test as the justification of the source checkpoint can't be realized on chain
                # because of the lack of the block space
                return [], new_branch_tip

            # If the fork won't be advanced in the future epochs
            # ensure 1) all yet not included attestations are included on chain by advancing it to epoch N+1
            #        2) justification is realized by advancing it to epoch N+2
            is_fork_advanced_in_future = any((l for l in sm_links if l.source == sm_link.target))
            if sm_link.target == current_epoch and not is_fork_advanced_in_future:
                advanced_branch_tip = new_branch_tip

                # Advance to N+1 if state.current_justified_checkpoint.epoch < eventually_justified_checkpoint.epoch
                current_justified_epoch = new_branch_tip.beacon_state.current_justified_checkpoint.epoch
                eventually_justified_epoch = new_branch_tip.eventually_justified_checkpoint.epoch
                if current_justified_epoch < eventually_justified_epoch:
                    advanced_signed_blocks, advanced_branch_tip = _advance_branch_to_next_epoch(spec, new_branch_tip,
                                                                                                enable_attesting=False)
                    new_signed_blocks = new_signed_blocks + advanced_signed_blocks

                # Build a block in the next epoch to justify the target on chain
                state = advanced_branch_tip.beacon_state
                while (spec.get_beacon_proposer_index(state) not in advanced_branch_tip.participants):
                    next_slot(spec, state)

                tip_block, _, _, _ = _produce_block(spec, state, [])
                new_signed_blocks.append(tip_block)

                assert state.current_justified_checkpoint.epoch == sm_link.target, \
                    'Unexpected state.current_justified_checkpoint: ' + str(
                        state.current_justified_checkpoint.epoch) + ' != ' + str(sm_link.target)

            # Debug output
            if debug:
                print('branch' + str(sm_link) + ':',
                      _print_epoch(spec, branch_tips[sm_link].beacon_state, new_signed_blocks))
                print('              ', len(branch_tips[sm_link].participants), 'participants:',
                      new_branch_tip.participants)
                print('              ', 'state.current_justified_checkpoint:',
                      '(epoch=' + str(post_state.current_justified_checkpoint.epoch) +
                      ', root=' + str(post_state.current_justified_checkpoint.root)[:6] + ')')
                print('              ', 'eventually_justified_checkpoint:',
                      '(epoch=' + str(new_branch_tip.eventually_justified_checkpoint.epoch) +
                      ', root=' + str(new_branch_tip.eventually_justified_checkpoint.root)[:6] + ')')

            # Debug checks
            if debug:
                # Proposers are aligned with the partition
                unexpected_proposers = [b.message.proposer_index for b in new_signed_blocks if
                                        b.message.proposer_index not in branch_tip.participants]
                assert len(unexpected_proposers) == 0, \
                    'Unexpected proposer: ' + str(unexpected_proposers[0])

                # Attesters are aligned with the partition
                current_epoch_state = branch_tips[sm_link].beacon_state
                for b in new_signed_blocks:
                    # Attesting indexes from on chain attestations
                    attesters = _attesters_in_block(spec, current_epoch_state, b, current_epoch)
                    # Attesting indexes from not yet included attestations
                    for a in new_branch_tip.attestations:
                        if a.data.target.epoch == current_epoch:
                            attesters.update(
                                spec.get_attesting_indices(current_epoch_state, a.data, a.aggregation_bits))
                    unexpected_attesters = attesters.difference(branch_tip.participants)
                    assert len(unexpected_attesters) == 0, \
                        'Unexpected attester: ' + str(unexpected_attesters.pop()) + ', slot ' + str(b.message.slot)

            # Store the result
            branch_tips[sm_link] = new_branch_tip
            signed_blocks = signed_blocks + new_signed_blocks

    # Sort blocks by a slot
    signed_block_messages = [ProtocolMessage(b) for b in signed_blocks]
    return sorted(signed_block_messages, key=lambda b: b.payload.message.slot), branch_tips[highest_target_sm_link]


def _spoil_block(spec, rnd: random.Random, signed_block):
    signed_block.message.state_root = spec.Root(rnd.randbytes(32))


def _generate_block_tree(spec,
                         anchor_tip: BranchTip,
                         rnd: random.Random,
                         debug,
                         block_parents,
                         with_attester_slashings,
                         with_invalid_messages) -> ([], [], []):
    in_block_attestations = anchor_tip.attestations.copy()
    post_states = [anchor_tip.beacon_state.copy()]
    current_slot = anchor_tip.beacon_state.slot
    block_index = 1
    block_tree_tips = set([0])
    in_block_attester_slashings = []
    attester_slashings_count = 0
    out_of_block_attestation_messages = []
    out_of_block_attester_slashing_messages = []
    signed_block_messages = []

    while block_index < len(block_parents):
        # Propose a block if slot shouldn't be empty
        if rnd.randint(1, 100) > EMPTY_SLOTS_RATE:
            # Advance parent state to the current slot
            parent_index = block_parents[block_index]
            parent_state = post_states[parent_index].copy()
            transition_to(spec, parent_state, current_slot)

            # Filter out non-viable attestations
            in_block_attestations = [a for a in in_block_attestations
                                     if parent_state.slot <= a.data.slot + spec.SLOTS_PER_EPOCH]

            # Produce block
            proposer = spec.get_beacon_proposer_index(parent_state)
            block_should_be_valid = rnd.randint(0, 99) >= INVALID_MESSAGES_RATE if with_invalid_messages else True

            if block_should_be_valid:
                signed_block, post_state, in_block_attestations, in_block_attester_slashings = _produce_block(
                    spec, parent_state, in_block_attestations, in_block_attester_slashings)

                # A block can be unintentionally invalid, e.g. a proposer was slashed
                # In this case it is expected that post_state == parent_state,
                # and beacon operations returned from _produce_block are expected to remain untouched
                block_is_valid = post_state.latest_block_header.slot == signed_block.message.slot

                # Valid block
                signed_block_messages.append(ProtocolMessage(signed_block, block_is_valid))
                post_states.append(post_state)

                # Update tips
                if block_is_valid:
                    block_tree_tips.discard(parent_index)
                    block_tree_tips.add(block_index)
            else:
                # Intentionally invalid block
                # Do not update slashings and attestations for them to be included in the future blocks
                signed_block, _, _, _ = _produce_block(
                    spec, parent_state, in_block_attestations, in_block_attester_slashings)
                _spoil_block(spec, rnd, signed_block)
                signed_block_messages.append(ProtocolMessage(signed_block, False))
                # Append the parent state as the post state as if the block were not applied
                post_states.append(parent_state)

            # Next block
            block_index += 1

        # Attest to randomly selected tips
        def split_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

        attesting_tips = rnd.sample(sorted(block_tree_tips), min(len(block_tree_tips), MAX_TIPS_TO_ATTEST))
        validator_count = len(post_states[attesting_tips[0]].validators)
        attesters = split_list([i for i in range(validator_count)], len(attesting_tips))
        for index, attesting_block_index in enumerate(attesting_tips):
            # Advance the state to the current slot
            attesting_state = post_states[attesting_block_index]
            transition_to(spec, attesting_state, current_slot)

            # Attest to the block
            attestations_in_slot = _attest_to_slot(spec, attesting_state, attesting_state.slot,
                                                   lambda comm: [i for i in comm if i in attesters[index]])

            # Sample on chain and off chain attestations
            for a in attestations_in_slot:
                choice = rnd.randint(0, 99)
                if choice < OFF_CHAIN_ATTESTATION_RATE:
                    out_of_block_attestation_messages.append(ProtocolMessage(a, True))
                elif choice < OFF_CHAIN_ATTESTATION_RATE + ON_CHAIN_ATTESTATION_RATE:
                    in_block_attestations.insert(0, a)
                else:
                    out_of_block_attestation_messages.append(ProtocolMessage(a, True))
                    in_block_attestations.insert(0, a)

        # Create attester slashing
        if with_attester_slashings and attester_slashings_count < MAX_ATTESTER_SLASHINGS:
            if rnd.randint(0, 99) < ATTESTER_SLASHINGS_RATE:
                state = post_states[attesting_tips[0]]
                indices = [rnd.randint(0, len(state.validators) - 1)]
                attester_slashing = get_valid_attester_slashing_by_indices(spec, state, indices,
                                                                           slot=current_slot,
                                                                           signed_1=True,
                                                                           signed_2=True)

                choice = rnd.randint(0, 99)
                if choice < OFF_CHAIN_SLASHING_RATE:
                    out_of_block_attester_slashing_messages.append(ProtocolMessage(attester_slashing, True))
                elif choice < OFF_CHAIN_SLASHING_RATE + ON_CHAIN_SLASHING_RATE:
                    in_block_attester_slashings.append(attester_slashing)
                else:
                    out_of_block_attester_slashing_messages.append(ProtocolMessage(attester_slashing, True))
                    in_block_attester_slashings.append(attester_slashing)

                attester_slashings_count += 1

        # Next slot
        current_slot += 1

    if debug:
        print('\nblock_tree:')
        print('blocks:       ', _print_block_tree(spec, post_states[0], [b.payload for b in signed_block_messages]))
        print('              ', 'state.current_justified_checkpoint:',
              '(epoch=' + str(post_states[len(post_states) - 1].current_justified_checkpoint.epoch) +
              ', root=' + str(post_states[len(post_states) - 1].current_justified_checkpoint.root)[:6] + ')')
        print('on_attestation: ')
        print('              ', 'count =', len(out_of_block_attestation_messages))
        print('              ', 'valid =', len([a for a in out_of_block_attestation_messages if a.valid]))
        print('on_attester_slashing: ')
        print('              ', 'count =', len(out_of_block_attester_slashing_messages))
        print('              ', 'valid =', len([s for s in out_of_block_attester_slashing_messages if s.valid]))

    return (sorted(signed_block_messages, key=lambda b: b.payload.message.slot),
            sorted(out_of_block_attestation_messages, key=lambda a: a.payload.data.slot),
            sorted(out_of_block_attester_slashing_messages, key=lambda a: a.payload.attestation_1.data.slot))


def _print_head(spec, store):
    head = spec.get_head(store)
    weight = spec.get_weight(store, head)
    state = store.checkpoint_states[store.justified_checkpoint]
    total_active_balance = spec.get_total_active_balance(state)

    return '(slot=' + str(store.blocks[head].slot) + ', root=' + str(head)[:6] + ', weight=' + str(
        weight * 100 // total_active_balance) + '%)'


def _on_tick_and_append_step(spec, store, slot, test_steps):
    time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    assert store.time == time


@with_altair_and_later
@spec_state_test
def test_sm_links_tree_model(spec,
                             state,
                             debug=False,
                             seed=1,
                             sm_links=None,
                             with_attester_slashings=False,
                             with_invalid_messages=False):
    block_parents = [0, 0, 0, 2, 2, 1, 1, 6, 6, 5, 5, 4, 7, 4, 3, 3]

    # This test is mainly used for the test generation purposes
    # Thus seed and sm_links are provided by the generator
    # Define sm_links and seed explicitly to execute a certain run of this test
    if sm_links is None:
        return

    assert (1, 2) not in sm_links, '(1, 2) sm link is not supported due to unsatisfiability'

    sm_links = [SmLink(l) for l in sm_links]

    # Find a reachable solution trying with different seeds if needed
    # sm_links constraints may not have a solution beacause of the randomization affecting validator partitions
    signed_block_messages = []
    highest_tip = BranchTip(state, [], [], state.current_justified_checkpoint)
    while True:
        if debug:
            print('\nseed:', seed)
            print('\nsm_links:', sm_links)

        rnd = random.Random(seed)
        signed_block_messages, highest_tip = _generate_sm_link_tree(spec, state, sm_links, rnd, debug)
        if len(signed_block_messages) > 0:
            break

        new_seed = rnd.randint(1, 10000)
        print('\nUnsatisfiable constraints: sm_links: ' + str(sm_links) + ', seed=' + str(
            seed) + ', will retry with seed=' + str(new_seed))
        seed = new_seed

    # Block tree model
    attestation_messages = []
    attester_slashing_messages = []
    if block_parents is not None:
        block_tree, attestation_messages, attester_slashing_messages = _generate_block_tree(
            spec, highest_tip, rnd, debug, block_parents, with_attester_slashings, with_invalid_messages)
        # Merge block_tree and sm_link_tree blocks
        block_tree_root_slot = block_tree[0].payload.message.slot
        signed_block_messages = [b for b in signed_block_messages if b.payload.message.slot < block_tree_root_slot]
        signed_block_messages = signed_block_messages + block_tree

    # Yield run parameters
    yield 'seed', 'meta', seed
    yield 'sm_links', 'meta', str(sm_links)

    test_steps = []
    # Store initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    _on_tick_and_append_step(spec, store, state.slot, test_steps)

    # Apply generated messages
    max_block_slot = max(b.payload.message.slot for b in signed_block_messages)
    max_attestation_slot = max(a.payload.data.slot for a in attestation_messages) if any(attestation_messages) else 0
    max_slashing_slot = max(
        s.payload.attestation_1.data.slot for s in attester_slashing_messages) if any(attester_slashing_messages) else 0

    start_slot = min(b.payload.message.slot for b in signed_block_messages)
    end_slot = max(max_block_slot, max_attestation_slot, max_slashing_slot) + 1

    # Advance time to start_slot
    _on_tick_and_append_step(spec, store, start_slot, test_steps)

    # Apply messages to store
    for slot in range(start_slot, end_slot + 1):
        # on_tick
        _on_tick_and_append_step(spec, store, slot, test_steps)

        # on_attestation for attestations from the previous slot
        for attestation_message in (a for a in attestation_messages if a.payload.data.slot == slot - 1):
            yield from add_attestation(spec, store, attestation_message.payload, test_steps, attestation_message.valid)

        # on_attester_slashing for slashing from the previous slot
        for attester_slashing_message in (s for s in attester_slashing_messages
                                          if s.payload.attestation_1.data.slot == slot - 1):
            yield from add_attester_slashing(spec, store, attester_slashing_message.payload,
                                             test_steps, attester_slashing_message.valid)

        # on_block for blocks from the current slot
        for signed_block_message in (b for b in signed_block_messages if b.payload.message.slot == slot):
            yield from add_block(spec, store, signed_block_message.payload, test_steps, signed_block_message.valid)
            block_root = signed_block_message.payload.message.hash_tree_root()
            if signed_block_message.valid:
                assert store.blocks[block_root] == signed_block_message.payload.message
            else:
                assert block_root not in store.blocks.values()

    if debug:
        print('               head: ' + _print_head(spec, store))

    yield 'steps', test_steps


def _generate_filter_block_tree(spec, genesis_state, block_epochs, parents, previous_justifications,
        current_justifications, rnd: random.Random, debug) -> ([], []):
    anchor_epoch = block_epochs[0]

    signed_blocks, anchor_tip = _advance_state_to_anchor_epoch(spec, genesis_state, anchor_epoch, debug)

    block_tips = [None for _ in range(0, len(block_epochs))]
    # Initialize with the anchor block
    block_tips[0] = anchor_tip

    JUSTIFYING_SLOT = 2 * spec.SLOTS_PER_EPOCH // 3 + 1

    for epoch in range(anchor_epoch + 1, max(block_epochs) + 1):
        current_blocks = [i for i, e in enumerate(block_epochs) if e == epoch]
        if len(current_blocks) == 0:
            continue

        # There should be enough slots to propose all blocks
        assert (spec.SLOTS_PER_EPOCH - JUSTIFYING_SLOT) >= len(
            current_blocks), "Unsatisfiable constraints: not enough slots to propose all blocks: " + str(current_blocks)

        # Case 2. Blocks are from disjoint subtrees -- not supported yet
        assert len(
            set([a for i, a in enumerate(parents) if i in current_blocks])) == 1, 'Disjoint trees are not supported'

        # Case 1. Blocks have common ancestor
        a = parents[current_blocks[0]]
        ancestor_tip = block_tips[a].copy()

        state = ancestor_tip.beacon_state
        attestations = ancestor_tip.attestations
        threshold_slot = spec.compute_start_slot_at_epoch(epoch) + JUSTIFYING_SLOT

        # Build the chain up to but excluding a block that will justify current checkpoint
        while (state.slot < threshold_slot):
            # Do not include attestations into blocks
            if (state.slot < spec.compute_start_slot_at_epoch(epoch)):
                new_block, state, _, _ = _produce_block(spec, state, [])
                signed_blocks.append(new_block)
            else:
                new_block, state, attestations, _ = _produce_block(spec, state, attestations)
                signed_blocks.append(new_block)

            # Attest
            curr_slot_attestations = _attest_to_slot(spec, state, state.slot)
            attestations = curr_slot_attestations + attestations

            # Next slot
            next_slot(spec, state)

        common_state = state

        # Assumption: one block is enough to satisfy previous_justifications[b] and current_justifications[b],
        # i.e. block capacity is enough to accommodate attestations to justify previus and current epoch checkpoints
        # if that needed. Considering that most of attestations were already included into the common chain prefix,
        # we assume it is possible
        empty_slot_count = spec.SLOTS_PER_EPOCH - JUSTIFYING_SLOT - len(current_blocks)
        block_distribution = current_blocks.copy() + [-1 for _ in range(0, empty_slot_count)]

        # Randomly distribute blocks across slots
        rnd.shuffle(block_distribution)

        for index, block in enumerate(block_distribution):
            slot = threshold_slot + index
            state = common_state.copy()

            # Advance state to the slot
            if state.slot < slot:
                transition_to(spec, state, slot)

            # Propose a block if slot isn't empty
            block_attestations = []
            if block > -1:
                previous_epoch_attestations = [a for a in attestations if
                                               epoch == spec.compute_epoch_at_slot(a.data.slot) + 1]
                current_epoch_attestations = [a for a in attestations if
                                              epoch == spec.compute_epoch_at_slot(a.data.slot)]
                if (previous_justifications[block]):
                    block_attestations = block_attestations + previous_epoch_attestations
                if (current_justifications[block]):
                    block_attestations = block_attestations + current_epoch_attestations

                # Propose block
                new_block, state, _, _ = _produce_block(spec, state, block_attestations)
                signed_blocks.append(new_block)

            # Attest
            # TODO pick a random tip to make attestation with if the slot is empty
            curr_slot_attestations = _attest_to_slot(spec, state, state.slot)
            attestations = curr_slot_attestations + attestations

            # Next slot
            next_slot(spec, state)

            if block > -1:
                not_included_attestations = [a for a in attestations if a not in block_attestations]

                check_up_state = state.copy()
                spec.process_justification_and_finalization(check_up_state)

                if current_justifications[block]:
                    assert check_up_state.current_justified_checkpoint.epoch == epoch, 'Unexpected current_jusitified_checkpoint.epoch: ' + str(
                        check_up_state.current_justified_checkpoint.epoch) + ' != ' + str(epoch)
                elif previous_justifications[block]:
                    assert check_up_state.current_justified_checkpoint.epoch + 1 == epoch, 'Unexpected current_jusitified_checkpoint.epoch: ' + str(
                        check_up_state.current_justified_checkpoint.epoch) + ' != ' + str(epoch - 1)

                block_tips[block] = BranchTip(state, not_included_attestations, [*range(0, len(state.validators))],
                                              check_up_state.current_justified_checkpoint)

    return signed_blocks, block_tips


@with_altair_and_later
@spec_state_test
def test_filter_block_tree_model(spec, state, model_params=None, debug=False, seed=1):
    if model_params is None:
        return

    print('\nseed:', seed)
    print('predicates:', str(model_params['predicates']))
    print('model_params:', str(model_params))

    block_epochs = model_params['block_epochs']
    parents = model_params['parents']
    previous_justifications = model_params['previous_justifications']
    current_justifications = model_params['current_justifications']

    store_justified_epoch = model_params['store_justified_epoch']
    target_block = model_params['target_block']

    anchor_epoch = block_epochs[0]

    # Ensure that epoch(block) == epoch(parent) + 1
    for b in range(1, len(block_epochs)):
        assert block_epochs[b] == block_epochs[parents[b]] + 1, 'epoch(' + str(b) + ') != epoch(' + str(
            parents[b]) + ') + 1, block_epochs=' + str(block_epochs) + ', parents=' + str(parents)

    # Ensure that a descendant doesn't attempt to justify the previous epoch checkpoint
    # if it has already been justified by its ancestor
    for b in range(1, len(block_epochs)):
        if previous_justifications[b]:
            a = parents[b]
            assert not current_justifications[a], str(b) + ' attempts to justify already justified epoch'

    rnd = random.Random(seed)
    signed_blocks, post_block_tips = _generate_filter_block_tree(spec,
                                                                 state,
                                                                 block_epochs,
                                                                 parents,
                                                                 previous_justifications,
                                                                 current_justifications,
                                                                 rnd,
                                                                 debug)

    # Yield run parameters
    yield 'seed', 'meta', seed
    yield 'model_params', 'meta', model_params

    test_steps = []
    # Store initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Apply generated blocks
    for signed_block in signed_blocks:
        block = signed_block.message
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block

    # Advance the store to the current epoch as per model
    current_epoch_slot = spec.compute_start_slot_at_epoch(model_params['current_epoch'])
    current_epoch_time = state.genesis_time + current_epoch_slot * spec.config.SECONDS_PER_SLOT
    if store.time < current_epoch_time:
        on_tick_and_append_step(spec, store, current_epoch_time, test_steps)

    current_epoch = spec.get_current_store_epoch(store)
    # Ensure the epoch is correct
    assert current_epoch == model_params['current_epoch']
    # Ensure the store.justified_checkpoint.epoch is as expected
    assert store.justified_checkpoint.epoch == store_justified_epoch
    # Ensure the target block is in filtered_blocks
    filtered_block_roots = list(spec.get_filtered_block_tree(store).keys())
    target_block_root = spec.hash_tree_root(post_block_tips[target_block].beacon_state.latest_block_header)

    # Check predicates
    predicates = model_params['predicates']
    if predicates['store_je_eq_zero']:
        assert store.justified_checkpoint.epoch == spec.GENESIS_EPOCH, "store_je_eq_zero not satisfied"

    if predicates['block_is_leaf']:
        assert not any(
            b for b in store.blocks.values() if b.parent_root == target_block_root), "block_is_leaf not satisfied"
    else:
        assert any(
            b for b in store.blocks.values() if b.parent_root == target_block_root), "block_is_leaf not satisfied"

    voting_source = spec.get_voting_source(store, target_block_root)
    if predicates['block_vse_eq_store_je']:
        assert voting_source.epoch == store.justified_checkpoint.epoch, "block_vse_eq_store_je not satisfied"
    else:
        assert voting_source.epoch != store.justified_checkpoint.epoch, "block_vse_eq_store_je not satisfied"

    if predicates['block_vse_plus_two_ge_curr_e']:
        assert voting_source.epoch + 2 >= current_epoch, "block_vse_plus_two_ge_curr_e not satisfied"
    else:
        assert voting_source.epoch + 2 < current_epoch, "block_vse_plus_two_ge_curr_e not satisfied"

    # Ensure the target block is in filtered blocks if it is a leaf and eligible
    if (predicates['block_is_leaf']
            and (predicates['store_je_eq_zero']
                 or predicates['block_vse_eq_store_je']
                 or predicates['block_vse_plus_two_ge_curr_e'])):
        assert target_block_root in filtered_block_roots

    test_steps.append({'property_checks': {'filtered_block_roots': [str(r) for r in filtered_block_roots]}})

    yield 'steps', test_steps
