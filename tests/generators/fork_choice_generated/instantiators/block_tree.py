import random
from eth2spec.test.context import (
    spec_state_test,
    with_altair_and_later,
)
from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth2spec.test.helpers.state import (
    transition_to,
    next_slot,
)
from .helpers import (
    ProtocolMessage,
    FCTestData,
    BranchTip,
)
from .helpers import (
    advance_branch_to_next_epoch,
    advance_state_to_anchor_epoch,
    produce_block,
    attest_to_slot,
    yield_fork_choice_test_case,
)
from .debug_helpers import (
    attesters_in_block,
    print_epoch,
    print_block_tree,
)
from eth2spec.utils import bls

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

    # Find anchor epoch
    anchor_epoch = min(sm_links, key=lambda l: l.source).source

    signed_blocks, anchor_tip = advance_state_to_anchor_epoch(spec, genesis_state, anchor_epoch, debug)

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
            new_signed_blocks, new_branch_tip = advance_branch_to_next_epoch(spec, branch_tip)

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
                    advanced_signed_blocks, advanced_branch_tip = advance_branch_to_next_epoch(spec, new_branch_tip,
                                                                                               enable_attesting=False)
                    new_signed_blocks = new_signed_blocks + advanced_signed_blocks

                # Build a block in the next epoch to justify the target on chain
                state = advanced_branch_tip.beacon_state
                while (spec.get_beacon_proposer_index(state) not in advanced_branch_tip.participants):
                    next_slot(spec, state)

                tip_block, _, _, _ = produce_block(spec, state, [])
                new_signed_blocks.append(tip_block)

                assert state.current_justified_checkpoint.epoch == sm_link.target, \
                    'Unexpected state.current_justified_checkpoint: ' + str(
                        state.current_justified_checkpoint.epoch) + ' != ' + str(sm_link.target)

            # Debug output
            if debug:
                print('branch' + str(sm_link) + ':',
                      print_epoch(spec, branch_tips[sm_link].beacon_state, new_signed_blocks))
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
                    attesters = attesters_in_block(spec, current_epoch_state, b, current_epoch)
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


def _spoil_attester_slashing(spec, rnd: random.Random, attester_slashing):
    attester_slashing.attestation_2.data = attester_slashing.attestation_1.data


def _spoil_attestation(spec, rnd: random.Random, attestation):
    attestation.data.target.epoch = spec.GENESIS_EPOCH


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
            if parent_state.validators[proposer].slashed or (
                    with_invalid_messages and rnd.randint(0, 99) < INVALID_MESSAGES_RATE):
                # Do not include attestations and slashings into invalid block
                # as clients may opt in to process or not process attestations contained by invalid block
                signed_block, _, _, _ = produce_block(spec, parent_state, [], [])
                _spoil_block(spec, rnd, signed_block)
                signed_block_messages.append(ProtocolMessage(signed_block, False))
                # Append the parent state as the post state as if the block were not applied
                post_states.append(parent_state)
            else:
                signed_block, post_state, in_block_attestations, in_block_attester_slashings = produce_block(
                    spec, parent_state, in_block_attestations, in_block_attester_slashings)

                # Valid block
                signed_block_messages.append(ProtocolMessage(signed_block, True))
                post_states.append(post_state)

                # Update tips
                block_tree_tips.discard(parent_index)
                block_tree_tips.add(block_index)

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
            attestations_in_slot = attest_to_slot(spec, attesting_state, attesting_state.slot,
                                                  lambda comm: [i for i in comm if i in attesters[index]])

            # Sample on chain and off chain attestations
            for a in attestations_in_slot:
                choice = rnd.randint(0, 99)
                if choice < OFF_CHAIN_ATTESTATION_RATE:
                    if with_invalid_messages and rnd.randint(0, 99) < INVALID_MESSAGES_RATE:
                        _spoil_attestation(spec, rnd, a)
                        attestation_message = ProtocolMessage(a, False)
                    else:
                        attestation_message = ProtocolMessage(a, True)
                    out_of_block_attestation_messages.append(attestation_message)
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
                    if with_invalid_messages and rnd.randint(0, 99) < INVALID_MESSAGES_RATE:
                        _spoil_attester_slashing(spec, rnd, attester_slashing)
                        attester_slashing_message = ProtocolMessage(attester_slashing, False)
                    else:
                        attester_slashing_message = ProtocolMessage(attester_slashing, True)
                    out_of_block_attester_slashing_messages.append(attester_slashing_message)
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
        print('blocks:       ', print_block_tree(spec, post_states[0], [b.payload for b in signed_block_messages]))
        print('              ', 'state.current_justified_checkpoint:',
              '(epoch=' + str(post_states[len(post_states) - 1].current_justified_checkpoint.epoch) +
              ', root=' + str(post_states[len(post_states) - 1].current_justified_checkpoint.root)[:6] + ')')

        print('on_block:')
        print('              ', 'count =', len(signed_block_messages))
        print('              ', 'valid =', len([b for b in signed_block_messages if b.valid]))
        print('on_attestation:')
        print('              ', 'count =', len(out_of_block_attestation_messages))
        print('              ', 'valid =', len([a for a in out_of_block_attestation_messages if a.valid]))
        print('on_attester_slashing:')
        print('              ', 'count =', len(out_of_block_attester_slashing_messages))
        print('              ', 'valid =', len([s for s in out_of_block_attester_slashing_messages if s.valid]))

    return (sorted(signed_block_messages, key=lambda b: b.payload.message.slot),
            sorted(out_of_block_attestation_messages, key=lambda a: a.payload.data.slot),
            sorted(out_of_block_attester_slashing_messages, key=lambda a: a.payload.attestation_1.data.slot))


def gen_block_tree_test_data(spec,
                             state,
                             debug,
                             seed,
                             sm_links,
                             block_parents,
                             with_attester_slashings,
                             with_invalid_messages) -> FCTestData:
    assert (1, 2) not in sm_links, '(1, 2) sm link is not supported due to unsatisfiability'
    sm_links = [SmLink(l) for l in sm_links]

    anchor_state = state
    anchor_block = spec.BeaconBlock(state_root=anchor_state.hash_tree_root())

    # Find a reachable solution trying with different seeds if needed
    # sm_links constraints may not have a solution because of the randomization affecting validator partitions
    signed_block_messages = []
    highest_tip = BranchTip(state, [], [], state.current_justified_checkpoint)
    while True:
        if debug:
            print('\nseed:', seed)
            print('sm_links:', sm_links)
            print('block_parents:', block_parents)

        rnd = random.Random(seed)
        signed_block_messages, highest_tip = _generate_sm_link_tree(spec, state, sm_links, rnd, debug)
        if len(signed_block_messages) > 0:
            break

        new_seed = rnd.randint(1, 10000)
        print('\nUnsatisfiable constraints: sm_links: ' + str(sm_links) + ', seed=' + str(
            seed) + ', will retry with seed=' + str(new_seed))
        seed = new_seed

    # Block tree model
    block_tree, attestation_messages, attester_slashing_messages = _generate_block_tree(
        spec, highest_tip, rnd, debug, block_parents, with_attester_slashings, with_invalid_messages)

    # Merge block_tree and sm_link_tree blocks
    block_tree_root_slot = block_tree[0].payload.message.slot
    signed_block_messages = [b for b in signed_block_messages if b.payload.message.slot < block_tree_root_slot]
    signed_block_messages = signed_block_messages + block_tree

    # Meta data
    meta = {
        'seed': seed,
        'sm_links': str(sm_links),
        'block_parents': str(block_parents),
        'bls_setting': 0 if bls.bls_active else 2,
    }

    return FCTestData(meta, anchor_block, anchor_state,
                      signed_block_messages, attestation_messages, attester_slashing_messages)


@with_altair_and_later
@spec_state_test
def yield_block_tree_test_case(spec,
                               state,
                               debug=False,
                               seed=1,
                               sm_links=None,
                               block_parents=None,
                               with_attester_slashings=False,
                               with_invalid_messages=False):
    # This test is mainly used for the test generation purposes
    # Thus seed, sm_links and block_parents are provided by the generator
    # Define sm_links, seed and block_parents explicitly to execute a certain run of this test
    if sm_links is None or block_parents is None:
        return

    test_data = gen_block_tree_test_data(spec, state, debug, seed, sm_links, block_parents,
                                         with_attester_slashings, with_invalid_messages)

    store = spec.get_forkchoice_store(test_data.anchor_state, test_data.anchor_block)
    yield from yield_fork_choice_test_case(spec, store, test_data, debug)
