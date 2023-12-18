import random
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
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
    next_slot,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    build_empty_block,
    sign_block,
)

MAX_JUSTIFICATION_RATE = 99
MIN_JUSTIFICATION_RATE = 91

MAX_UNDERJUSTIFICATION_RATE = 70
MIN_UNDERJUSTIFICATION_RATE = 55


class SmLink(tuple):
    @property
    def source(self):
        return self[0]

    @property
    def target(self):
        return self[1]


class BranchTip:
    def __init__(self, beacon_state, attestations, participants):
        self.beacon_state = beacon_state
        self.attestations = attestations
        self.participants = participants


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
                                  if s.beacon_state.current_justified_checkpoint.epoch ==
                                  sm_link.source]
    assert len(tips_with_justified_source) > 0

    # Find and return the most adanced one
    most_recent_tip = max(tips_with_justified_source, key=lambda s: s.beacon_state.slot)
    return BranchTip(most_recent_tip.beacon_state.copy(), most_recent_tip.attestations.copy(), [])


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


def _produce_block(spec, state, attestations):
    """
    Produces a block including as many attestations as it is possible.
    :return: Signed block, the post block state and attestations that were not included into the block.
    """

    # Filter out too old attestastions (TODO relax condition for Deneb)
    eligible_attestations = [a for a in attestations if state.slot <= a.data.slot + spec.SLOTS_PER_EPOCH]

    # Prepare attestations
    attestation_in_block = eligible_attestations[:spec.MAX_ATTESTATIONS]

    # Create a block with attestations
    block = build_empty_block(spec, state)
    for a in attestation_in_block:
        block.body.attestations.append(a)

    # Run state transition and sign off on a block
    post_state = state.copy()
    spec.process_block(post_state, block)
    block.state_root = post_state.hash_tree_root()
    signed_block = sign_block(spec, post_state, block)

    not_included_attestations = [a for a in attestations if a not in attestation_in_block]

    return signed_block, post_state, not_included_attestations


def _attest_to_slot(spec, state, slot_to_attest, participants_filter):
    """
    Creates attestation is a slot respecting participating validators.
    :return: produced attestations
    """

    assert slot_to_attest <= state.slot

    committees_per_slot = spec.get_committee_count_per_slot(state, spec.compute_epoch_at_slot(slot_to_attest))
    attestations_in_slot = []
    for index in range(committees_per_slot):
        beacon_committee = spec.get_beacon_committee(state, slot_to_attest, index)
        participants = participants_filter(beacon_committee)
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


def _advance_branch_to_next_epoch(spec, branch_tip, current_epoch):
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
    target_slot = spec.compute_start_slot_at_epoch(current_epoch + 1)

    while state.slot < target_slot:
        # Produce block if the proposer is among participanting validators
        proposer = spec.get_beacon_proposer_index(state)
        if state.slot > spec.GENESIS_SLOT and proposer in branch_tip.participants:
            signed_block, state, attestations = _produce_block(spec, state, attestations)
            signed_blocks.append(signed_block)

        # Produce attestations
        attestations_in_slot = _attest_to_slot(spec, state, state.slot, participants_filter)
        # And prepend them to the list
        attestations = list(attestations_in_slot) + attestations

        # Advance a slot
        next_slot(spec, state)

    # Cleanup attestations by removing outdated ones
    attestations = [a for a in attestations if
                    a.data.target in (spec.get_previous_epoch(state), spec.get_current_epoch(state))]

    return signed_blocks, BranchTip(state, attestations, branch_tip.participants)


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


def _attesters_in_block(spec, epoch_state, signed_block):
    block = signed_block.message
    attesters = set()
    for a in block.body.attestations:
        attesters.update(spec.get_attesting_indices(epoch_state, a.data, a.aggregation_bits))
    return attesters


def _print_block(spec, epoch_state, signed_block):
    block = signed_block.message
    attesters = _attesters_in_block(spec, epoch_state, signed_block)
    attester_str = str(attesters) if any(attesters) else "{}"

    return "b(p: " + str(block.proposer_index) + ", a:" + attester_str + ")"


def _print_epoch(spec, epoch_state, signed_blocks):
    epoch = spec.get_current_epoch(epoch_state)
    start_slot = spec.compute_start_slot_at_epoch(epoch)
    ret = ""
    for slot in range(start_slot, start_slot + spec.SLOTS_PER_EPOCH + 1):
        blocks_in_slot = [b for b in signed_blocks if b.message.slot == slot]
        if ret != "":
            ret = ret + " <- "
        if any(blocks_in_slot):
            ret = ret + "s(" + str(slot) + ", " + _print_block(spec, epoch_state, blocks_in_slot[0]) + ")"
        else:
            ret = ret + "s(" + str(slot) + ", _)"

    return ret


def _generate_blocks(spec, genesis_state, sm_links, anchor_epoch, rnd: random.Random, debug) -> []:
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
    state = genesis_state.copy()
    signed_blocks = []

    genesis_tip = BranchTip(state.copy(), [], [*range(0, len(state.validators))])

    # Move the state to the anchor_epoch
    anchor_tip = genesis_tip
    for epoch in (spec.GENESIS_EPOCH, anchor_epoch):
        new_signed_blocks, anchor_tip = _advance_branch_to_next_epoch(spec, anchor_tip, epoch)
        signed_blocks = signed_blocks + new_signed_blocks

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
            branch_tips[l] = _create_new_branch_tip(spec, branch_tips, l)

        # Reshuffle partitions if needed
        if _any_change_to_validator_partitions(spec, sm_links, current_epoch, anchor_epoch):
            partitions = _compute_validator_partitions(spec, branch_tips, current_epoch_sm_links, current_epoch, rnd)
            for l in partitions.keys():
                old_tip_state = branch_tips[l]
                new_tip_state = BranchTip(old_tip_state.beacon_state, old_tip_state.attestations, partitions[l])
                branch_tips[l] = new_tip_state

        # Debug checks
        if debug:
            print("\nepoch ", current_epoch, ":")
            # Partitions are disjoint
            for l1 in current_epoch_sm_links:
                l1_participants = branch_tips[l1].participants
                for l2 in current_epoch_sm_links:
                    if l1 != l2:
                        l2_participants = branch_tips[l2].participants
                        intersection = set(l1_participants).intersection(l2_participants)
                        assert len(intersection) == 0, \
                            str(l1) + " and " + str(l2) + " has common participants: " + str(intersection)

        # Advance every branch taking into account attestations from past epochs and voting partitions
        for sm_link in current_epoch_sm_links:
            branch_tip = branch_tips[sm_link]
            assert spec.get_current_epoch(branch_tip.beacon_state) == current_epoch, \
                "Unexpected current_epoch(branch_tip.beacon_state)"
            new_signed_blocks, new_branch_tip = _advance_branch_to_next_epoch(spec, branch_tip, current_epoch)

            # Run sanity checks
            post_state = new_branch_tip.beacon_state
            assert spec.get_current_epoch(post_state) == current_epoch + 1, \
                "Unexpected post_state epoch"
            if sm_link.target == current_epoch:
                assert post_state.previous_justified_checkpoint.epoch == sm_link.source, \
                    "Unexpected previous_justified_checkpoint.epoch"
                assert post_state.current_justified_checkpoint.epoch == sm_link.target, \
                    "Unexpected current_justified_checkpoint.epoch"
            else:
                assert post_state.current_justified_checkpoint.epoch == sm_link.source, \
                    "Unexpected current_justified_checkpoint.epoch"

            # Create the first block of the next epoch to realize justification on chain,
            # neccessary only when the fork won't be advanced in any of the future epochs
            is_fork_advanced_in_future = any((l for l in sm_links if l.source == sm_link.target))
            if sm_link.target == current_epoch and not is_fork_advanced_in_future:
                tip_block, _, _ = _produce_block(spec, new_branch_tip.beacon_state, new_branch_tip.attestations)
                new_signed_blocks.append(tip_block)

            # Debug output
            if debug:
                print(sm_link, ":", _print_epoch(spec, branch_tips[sm_link].beacon_state, new_signed_blocks))
                print("        ", len(branch_tips[sm_link].participants), "participants:",
                      branch_tips[sm_link].participants)

            # Debug checks
            if debug:
                # Proposers are aligned with the partition
                unexpected_proposers = [b.message.proposer_index for b in new_signed_blocks if
                                        b.message.proposer_index not in branch_tip.participants]
                assert len(unexpected_proposers) == 0, \
                    "Unexpected proposer: " + str(unexpected_proposers[0])

                # Attesters are aligned with the partition
                for b in new_signed_blocks:
                    attesters = _attesters_in_block(spec, branch_tips[sm_link].beacon_state, b)
                    unexpected_attesters = attesters.difference(branch_tip.participants)
                    assert len(unexpected_attesters) == 0, \
                        "Unexpected attester: " + str(unexpected_attesters.pop()) + ", slot " + str(b.message.slot)

            # Store the result
            branch_tips[sm_link] = new_branch_tip
            signed_blocks = signed_blocks + new_signed_blocks

    # Sort blocks by a slot
    return sorted(signed_blocks, key=lambda b: b.message.slot)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_generated_sm_links(spec, state):
    """
    Generates a tree of supermajority links
    """
    input = [(2, 3), (2, 4), (3, 8), (3, 7)]
    seed = 1
    debug = False
    anchor_epoch = 2

    rnd = random.Random(seed)
    sm_links = [SmLink(l) for l in input]
    signed_blocks = _generate_blocks(spec, state, sm_links, anchor_epoch, rnd, debug)

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

    yield 'steps', test_steps
