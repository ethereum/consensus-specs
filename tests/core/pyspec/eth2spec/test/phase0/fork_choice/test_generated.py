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


def _justifying_participation_rate():
    # Hight particiaption rate is required to ensure high probability of justifying the target
    return 95


def _under_justifying_participation_rate():
    # Hight particiaption rate is required to ensure high probability of justifying the target
    return 65


def _create_new_branch_tip(spec, branch_tips: dict[SmLink:BranchTip], sm_link: SmLink) -> BranchTip:
    tips_with_justified_source = [s for s in branch_tips.values()
                                  if s.beacon_state.current_justified_checkpoint.epoch ==
                                  sm_link.source]
    assert len(tips_with_justified_source) > 0

    most_recent_tip = max(tips_with_justified_source, key=lambda s: s.beacon_state.slot)
    return BranchTip(most_recent_tip.beacon_state.copy(), most_recent_tip.attestations.copy(), [])


def _compute_partitions(spec, branch_tips, current_links, current_epoch, rnd: random.Random):
    """
    Uniformly distributes active validators between branches to advance
    O(N) complex -- N is a number of validators, might be inefficient with large validator sets

    Does not take into account validator's effective balance, based on assumption that EB is nearly the same

    :param spec: spec
    :param branch_tips: {(source, target): tip_state} tip_states of all branches to process in an epoch
    :param branches_to_advance: [(source, target)] a list of sm link branches that validators should be spread accross
    :return: {(source, target): participants}
    """

    justification_targets = [l for l in current_links if l.target == current_epoch]

    # Justifying two different checkpoints isn't supported
    assert len(justification_targets) < 2

    # Case when there is just 1 link and there is no justification target
    if len(current_links) == 1 and not any(justification_targets):
        l = current_links[0]
        state = branch_tips[l].beacon_state
        active_validator_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
        participant_count = len(active_validator_indices) * _under_justifying_participation_rate() // 100
        return {l: rnd.sample(active_validator_indices, participant_count)}

    participants = {l: [] for l in current_links}

    # Move the majority to the branch containing justification target
    justifying_participants = []
    if any(justification_targets):
        justification_target = justification_targets[0]
        state = branch_tips[justification_target].beacon_state
        active_validator_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
        participant_count = len(active_validator_indices) * _justifying_participation_rate() // 100
        justifying_participants = rnd.sample(active_validator_indices, participant_count)
        participants[justification_target] = justifying_participants

        # Case when the justification target is the only branch
        if justification_targets == current_links:
            return {justification_target: justifying_participants}

    # Genereral case

    # Collect a set of active validator indexes across all branches
    active_validator_per_branch = {}
    active_validators_total = set()
    for l in current_links:
        state = branch_tips[l].beacon_state
        active_validator_per_branch[l] = spec.get_active_validator_indices(state,
                                                                           spec.get_current_epoch(state))
        active_validators_total.update(active_validator_per_branch[l])

    # remove selected participants from the active validators set
    active_validators_total = active_validators_total.difference(justifying_participants)

    # For each index:
    #   1) Collect a set of branches where the validators is in active state (except for justifying branch)
    #   2) Append the index to the list of participants for a randomly selected branch
    for index in active_validators_total:
        active_branches = [l for l in current_links if
                           index in active_validator_per_branch[l] and l not in justification_targets]
        participants[tuple(rnd.choice(active_branches))].append(index)

    return participants


def _advance_branch_to_next_epoch(spec, branch_tip, current_epoch):
    def participants_filter(comm):
        return [index for index in comm if index in branch_tip.participants]

    signed_blocks = []
    attestations = branch_tip.attestations.copy()
    state = branch_tip.beacon_state.copy()
    target_slot = spec.compute_start_slot_at_epoch(current_epoch + 1)

    while state.slot < target_slot:
        # Produce a block if the proposer is in the network partition building a branch
        if spec.get_beacon_proposer_index(state) in branch_tip.participants and state.slot > spec.GENESIS_SLOT:

            # Remove too old attestations (TODO change for Deneb and after)
            attestations = [a for a in attestations if state.slot <= a.data.slot + spec.SLOTS_PER_EPOCH]

            # Prepare attestations
            attestation_in_block = attestations[:spec.MAX_ATTESTATIONS]
            attestations = attestations[spec.MAX_ATTESTATIONS:]

            # Create a block with attestations
            block = build_empty_block(spec, state)
            for a in attestation_in_block:
                block.body.attestations.append(a)

            # Run state transition and sign off on a block
            spec.process_block(state, block)
            block.state_root = state.hash_tree_root()
            signed_block = sign_block(spec, state, block)
            signed_blocks.append(signed_block)

        # Produce attestations
        slot_to_attest = state.slot
        committees_per_slot = spec.get_committee_count_per_slot(state, spec.compute_epoch_at_slot(slot_to_attest))
        attestations_in_slot = []
        for index in range(committees_per_slot):
            beacon_committee = spec.get_beacon_committee(state, slot_to_attest, index)
            participants = participants_filter(beacon_committee)
            if len(participants) > 0:
                attestation = get_valid_attestation(
                    spec,
                    state,
                    slot_to_attest,
                    index=index,
                    signed=True,
                    filter_participant_set=participants_filter
                )
                attestations_in_slot.append(attestation)

        # And prepend them to the list
        attestations = list(attestations_in_slot) + attestations

        # Advance a slot
        next_slot(spec, state)

    # Clean up attestations that aren't eligible to be on chain anymore
    attestations = [a for a in attestations if spec.compute_epoch_at_slot(a.data.slot) in (
        spec.get_current_epoch(state), spec.get_previous_epoch(state))]

    return signed_blocks, BranchTip(state, attestations, branch_tip.participants)


def _any_change_to_voting_partitions(spec, sm_links, current_epoch) -> bool:
    if current_epoch == spec.GENESIS_EPOCH:
        return True

    previous_epoch = current_epoch - 1

    # Previous epoch is genesis one -- set up new partitions
    if previous_epoch == spec.GENESIS_EPOCH:
        return True

    # Previous or current epoch is justification target
    #   a) Previous epoch accounts for newly created branches or an even reshuffling between branches in current epoch
    #   b) Current epoch accounts for moving the majority to a branch with the justifying target
    if any([l for l in sm_links if l.target == current_epoch or l.target == previous_epoch]):
        return True

    # No new branch satisfying any SM link can be created without a new justified checkpoint from the previous epoch
    # So partitions remain the same unless previous epoch has a justification
    return False


def _generate_blocks(spec, initial_state, sm_links, rnd: random.Random) -> []:
    state = initial_state.copy()

    signed_blocks = []

    # Sort sm_links
    sm_links = sorted(sm_links)

    # Fill GENESIS_EPOCH with blocks
    # _, genesis_epoch_blocks, state = next_slots_with_attestations(
    #     spec,
    #     state,
    #     spec.SLOTS_PER_EPOCH - 1,
    #     True,
    #     False
    # )
    # next_slot(spec, state)
    # TODO: fill two slots with attestations or start branching from GENESIS?
    # signed_blocks = signed_blocks + genesis_epoch_blocks
    # assert spec.get_current_epoch(state) == spec.compute_epoch_at_slot(spec.GENESIS_SLOT) + 1

    # Initialize branch tips with the genesis tip
    genesis_tip = BranchTip(state.copy(), [], [])
    branch_tips = {(spec.GENESIS_EPOCH, spec.GENESIS_EPOCH): genesis_tip}

    # Finish at after the highest justified target
    highest_target = max(sm_links, key=lambda l: l.target).target

    # Skip to target
    # 1. Skip with empty slots?
    # 2. Skip with empty blocks?
    # 3. Skip with partially full blocks?
    # 4. Mix of 1, 2 and 3
    # 5. Pivot from existing chain or built from the checkpoint block? if many chains which one to use?
    #    and which epoch to start a skip from?
    # with sm_links = [(0, 2), (0, 3)], (0, 3) has the following options:
    #     - (0, 2): 0 blocks, 0 blocks, full blocks | (0, 3): < 1/3 blocks
    #
    # Justify target
    # 1. Checkpoint slot empty?
    # 2. Missed blocks in the end of the target epoch?
    for current_epoch in range(spec.GENESIS_EPOCH, highest_target + 1):
        # Every epoch there are new randomly sampled partitions in the network
        # If the current epoch is an SM link target then there is one major justifying patition and a number of small ones
        # Attestations that are not included in the current epoch are left for inclusion in subsequent epochs
        # We ensure high probability of justifying the target by setting high participation rate
        # TODO: allow for partitioning in the middle of an epoch/epoch span when applicable

        # Advance only those branches that are required to build SM links in the future
        # Branches that aren't containing a source of a future SM link won't be advanced
        current_links = [l for l in sm_links if l.source < current_epoch <= l.target]

        # Initialize new branches
        for l in (l for l in current_links if branch_tips.get(l) is None):
            branch_tips[l] = _create_new_branch_tip(spec, branch_tips, l)

        # Reshuffle partitions if needed
        if _any_change_to_voting_partitions(spec, sm_links, current_epoch):
            partitions = _compute_partitions(spec, branch_tips, current_links, current_epoch, rnd)
            for l in partitions.keys():
                old_tip_state = branch_tips[l]
                new_tip_state = BranchTip(old_tip_state.beacon_state, old_tip_state.attestations, partitions[l])
                branch_tips[l] = new_tip_state

        # Advance every branch taking into account attestations from the previous epochs and voting partitions
        for l in current_links:
            branch_tip = branch_tips[l]
            new_signed_blocks, new_branch_tip = _advance_branch_to_next_epoch(spec, branch_tip, current_epoch)

            post_state = new_branch_tip.beacon_state
            assert spec.get_current_epoch(post_state) == current_epoch + 1
            if l.target == current_epoch:
                assert post_state.previous_justified_checkpoint.epoch == l.source
                assert post_state.current_justified_checkpoint.epoch == l.target
            else:
                assert post_state.current_justified_checkpoint.epoch == l.source

            branch_tips[l] = new_branch_tip
            signed_blocks = signed_blocks + new_signed_blocks

    # Add the last block to the top most branch
    branch_tip = branch_tips[max(sm_links, key=lambda l: l.target)]
    new_signed_blocks, _ = _advance_branch_to_next_epoch(spec, branch_tip, highest_target + 1)
    signed_blocks = signed_blocks + new_signed_blocks

    return sorted(signed_blocks, key=lambda b: b.message.slot)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_generated_sm_links(spec, state):
    """
    Creates a tree of supermajority links
    """
    input = [(2, 3), (2, 4), (3, 8), (3, 7), (0, 2)]
    seed = 1

    rnd = random.Random(seed)
    sm_links = [SmLink(l) for l in input]
    signed_blocks = _generate_blocks(spec, state, sm_links, rnd)

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
