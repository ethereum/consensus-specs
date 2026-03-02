from dataclasses import dataclass, field

from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    sign_block,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestation,
    add_attester_slashing,
    add_block,
    get_attestation_file_name,
    get_attester_slashing_file_name,
    get_block_file_name,
    on_tick_and_append_step,
    output_store_checks,
    run_on_attestation,
    run_on_attester_slashing,
    run_on_block,
)
from eth_consensus_specs.test.helpers.state import (
    next_slot,
)
from eth_consensus_specs.utils.ssz.ssz_typing import View

from .debug_helpers import print_epoch, print_head


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
    atts: list[ProtocolMessage] = field(default_factory=list)
    slashings: list[ProtocolMessage] = field(default_factory=list)
    store_final_time: int = 0


class BranchTip:
    def __init__(self, beacon_state, attestations, participants, eventually_justified_checkpoint):
        self.beacon_state = beacon_state
        self.attestations = attestations
        self.participants = participants
        self.eventually_justified_checkpoint = eventually_justified_checkpoint

    def copy(self):
        return BranchTip(
            self.beacon_state.copy(),
            self.attestations.copy(),
            self.participants.copy(),
            self.eventually_justified_checkpoint,
        )


def _get_eligible_attestations(spec, state, attestations) -> []:
    def _get_voting_source(target: spec.Checkpoint) -> spec.Checkpoint:
        if target.epoch == spec.get_current_epoch(state):
            return state.current_justified_checkpoint
        else:
            return state.previous_justified_checkpoint

    return [
        a
        for a in attestations
        if state.slot <= a.data.slot + spec.SLOTS_PER_EPOCH
        and a.data.source == _get_voting_source(a.data.target)
    ]


def _compute_pseudo_randao_reveal(spec, proposer_index, epoch):
    pseudo_vrn = spec.uint64((proposer_index + 1) * (epoch + 1))
    pseudo_vrn_bytes = spec.uint_to_bytes(pseudo_vrn)
    randao_reveal_bytes = bytes(96 - len(pseudo_vrn_bytes)) + pseudo_vrn_bytes
    return spec.BLSSignature(randao_reveal_bytes)


def produce_block(spec, state, attestations, attester_slashings=[]):
    """
    Produces a block including as many attestations as it is possible.
    :return: Signed block, the post block state and attestations that were not included into the block.
    """

    # Filter out too old attestastions (TODO relax condition for Deneb)
    eligible_attestations = _get_eligible_attestations(spec, state, attestations)

    # Create a block with attestations
    block = build_empty_block(spec, state)
    block.body.randao_reveal = _compute_pseudo_randao_reveal(
        spec, block.proposer_index, spec.get_current_epoch(state)
    )

    # Prepare attestations
    limit = type(block.body.attestations).limit()
    attestation_in_block = eligible_attestations[:limit]

    for a in attestation_in_block:
        block.body.attestations.append(a)

    # Add attester slashings
    attester_slashings_in_block = attester_slashings[: spec.MAX_ATTESTER_SLASHINGS]
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
        not_included_attester_slashings = [
            s for s in attester_slashings if s not in attester_slashings_in_block
        ]

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

    committees_per_slot = spec.get_committee_count_per_slot(
        state, spec.compute_epoch_at_slot(slot_to_attest)
    )
    attestations_in_slot = []
    for index in range(committees_per_slot):
        beacon_committee = spec.get_beacon_committee(state, slot_to_attest, index)
        participants = (
            beacon_committee
            if participants_filter is None
            else participants_filter(beacon_committee)
        )
        if any(participants):
            attestation = get_valid_attestation(
                spec,
                state,
                slot_to_attest,
                index=index,
                signed=True,
                filter_participant_set=participants_filter,
            )
            attestations_in_slot.append(attestation)

    return attestations_in_slot


def _compute_eventually_justified_epoch(spec, state, attestations, participants):
    # If not all attestations are included on chain
    # and attestation.data.target.epoch > beacon_state.current_justified_checkpoint.epoch
    # compute eventually_justified_checkpoint, a would be state.current_justified_checkpoint if all attestations
    # were included; this computation respects the validator partition that was building the branch
    if (
        len(attestations) > 0
        and attestations[0].data.target.epoch > state.current_justified_checkpoint.epoch
        and attestations[0].data.target.epoch > spec.GENESIS_EPOCH
    ):
        branch_tip = BranchTip(
            state, attestations, participants, state.current_justified_checkpoint
        )
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
    attestations = [
        a
        for a in attestations
        if a.data.target.epoch in (spec.get_previous_epoch(state), spec.get_current_epoch(state))
    ]

    eventually_justified_checkpoint = _compute_eventually_justified_epoch(
        spec, state, attestations, branch_tip.participants
    )

    return signed_blocks, BranchTip(
        state, attestations, branch_tip.participants, eventually_justified_checkpoint
    )


def advance_state_to_anchor_epoch(spec, state, anchor_epoch, debug) -> ([], BranchTip):
    signed_blocks = []

    genesis_tip = BranchTip(
        state.copy(), [], [*range(0, len(state.validators))], state.current_justified_checkpoint
    )

    # Advance the state to the anchor_epoch
    anchor_tip = genesis_tip
    for epoch in range(spec.GENESIS_EPOCH, anchor_epoch + 1):
        pre_state = anchor_tip.beacon_state
        new_signed_blocks, anchor_tip = advance_branch_to_next_epoch(spec, anchor_tip)
        signed_blocks = signed_blocks + new_signed_blocks
        if debug:
            post_state = anchor_tip.beacon_state
            print("\nepoch", str(epoch) + ":")
            print("branch(*, *):", print_epoch(spec, pre_state, new_signed_blocks))
            print(
                "              ",
                len(anchor_tip.participants),
                "participants:",
                anchor_tip.participants,
            )
            print(
                "              ",
                "state.current_justified_checkpoint:",
                "(epoch="
                + str(post_state.current_justified_checkpoint.epoch)
                + ", root="
                + str(post_state.current_justified_checkpoint.root)[:6]
                + ")",
            )
            print(
                "              ",
                "eventually_justified_checkpoint:",
                "(epoch="
                + str(anchor_tip.eventually_justified_checkpoint.epoch)
                + ", root="
                + str(anchor_tip.eventually_justified_checkpoint.root)[:6]
                + ")",
            )

    return signed_blocks, anchor_tip


def make_events(spec, test_data: FCTestData) -> list[tuple[int, object, bool]]:
    """
    Makes test events from `test_data`'s blocks, attestations and slashings, sorted by an effective slot.
    Each event is a triple ('tick'|'block'|'attestation'|'attester_slashing', message, valid).
    """
    genesis_time = test_data.anchor_state.genesis_time
    test_events = []

    def slot_to_time(slot):
        return slot * spec.config.SLOT_DURATION_MS // 1000 + genesis_time

    def add_tick_step(time):
        test_events.append(("tick", time, None))

    def add_message_step(kind, message):
        test_events.append((kind, message.payload, message.valid))

    add_tick_step(slot_to_time(test_data.anchor_state.slot))
    slot = test_data.anchor_state.slot

    def get_seffective_slot(message):
        event_kind, data, _ = message
        if event_kind == "block":
            return data.message.slot
        elif event_kind == "attestation":
            return data.data.slot + 1
        elif event_kind == "attester_slashing":
            return max(data.attestation_1.data.slot, data.attestation_1.data.slot) + 1
        else:
            assert False

    messages = (
        [("attestation", m.payload, m.valid) for m in test_data.atts]
        + [("attester_slashing", m.payload, m.valid) for m in test_data.slashings]
        + [("block", m.payload, m.valid) for m in test_data.blocks]
    )

    for event in sorted(messages, key=get_seffective_slot):
        event_kind, message, valid = event
        event_slot = get_seffective_slot(event)
        while slot < event_slot:
            slot += 1
            add_tick_step(slot_to_time(slot))
        add_message_step(event_kind, ProtocolMessage(message, valid))

    if slot is None or slot_to_time(slot) < test_data.store_final_time:
        add_tick_step(test_data.store_final_time)

    return test_events


def filter_out_duplicate_messages(fn):
    def wrapper(*args, **kwargs):
        processed_keys = set()
        for data in fn(*args, **kwargs):
            if len(data) != 2:
                yield data
            else:
                (key, value) = data
                if value is not None and isinstance(value, bytes | View):
                    # skip already processed ssz parts
                    if key not in processed_keys:
                        processed_keys.add(key)
                        yield data
                else:
                    yield data

    return wrapper


def _add_block(spec, store, signed_block, test_steps):
    """
    Helper method to add a block, when it's unknown whether it's valid or not
    """
    yield get_block_file_name(signed_block), signed_block
    try:
        run_on_block(spec, store, signed_block)
        valid = True
    except AssertionError:
        valid = False

    test_steps.append({"block": get_block_file_name(signed_block), "valid": valid})

    if valid:
        # An on_block step implies receiving block's attestations
        for attestation in signed_block.message.body.attestations:
            try:
                run_on_attestation(spec, store, attestation, is_from_block=True, valid=True)
            except AssertionError:
                # ignore possible faults, if the block is valid
                pass

        # An on_block step implies receiving block's attester slashings
        for attester_slashing in signed_block.message.body.attester_slashings:
            try:
                run_on_attester_slashing(spec, store, attester_slashing, valid=True)
            except AssertionError:
                # ignore possible faults, if the block is valid
                pass


@filter_out_duplicate_messages
def yield_fork_choice_test_events(
    spec, store, test_data: FCTestData, test_events: list, debug: bool
):
    # Yield meta
    for k, v in test_data.meta.items():
        yield k, "meta", v

    # Yield anchor state and block initialization
    yield "anchor_state", test_data.anchor_state
    yield "anchor_block", test_data.anchor_block

    for message in test_data.blocks:
        block = message.payload
        yield get_block_file_name(block), block.encode_bytes()

    for message in test_data.atts:
        attestation = message.payload
        yield get_attestation_file_name(attestation), attestation.encode_bytes()

    for message in test_data.slashings:
        attester_slashing = message.payload
        yield get_attester_slashing_file_name(attester_slashing), attester_slashing.encode_bytes()

    test_steps = []

    def try_add_mesage(runner, message):
        try:
            runner(spec, store, message, valid=True)
            return True
        except AssertionError:
            return False

    # record initial tick
    on_tick_and_append_step(spec, store, store.time, test_steps)

    for event in test_events:
        event_kind = event[0]
        if event_kind == "tick":
            _, time, _ = event
            if time > store.time:
                on_tick_and_append_step(spec, store, time, test_steps)
                assert store.time == time
        elif event_kind == "block":
            _, signed_block, valid = event
            if valid is None:
                yield from _add_block(spec, store, signed_block, test_steps)
            else:
                yield from add_block(spec, store, signed_block, test_steps, valid=valid)

                block_root = signed_block.message.hash_tree_root()
                if valid:
                    assert store.blocks[block_root] == signed_block.message
                else:
                    assert block_root not in store.blocks.values()
            output_store_checks(spec, store, test_steps)
        elif event_kind == "attestation":
            _, attestation, valid = event
            if valid is None:
                valid = try_add_mesage(run_on_attestation, attestation)
            yield from add_attestation(spec, store, attestation, test_steps, valid=valid)
            output_store_checks(spec, store, test_steps)
        elif event_kind == "attester_slashing":
            _, attester_slashing, valid = event
            if valid is None:
                valid = try_add_mesage(run_on_attester_slashing, attester_slashing)
            yield from add_attester_slashing(
                spec, store, attester_slashing, test_steps, valid=valid
            )
            output_store_checks(spec, store, test_steps)
        else:
            raise ValueError("Unknown event " + str(event_kind))

    if debug:
        print("               head: " + print_head(spec, store))

    output_store_checks(spec, store, test_steps, with_viable_for_head_weights=True)

    yield "steps", test_steps
