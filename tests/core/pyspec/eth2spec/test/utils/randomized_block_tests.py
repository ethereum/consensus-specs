"""
Utility code to generate randomized block tests
"""

import sys
import warnings
from collections.abc import Callable
from random import Random

from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.test.helpers.execution_payload import (
    build_randomized_execution_payload,
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.genesis import build_mock_builder
from eth2spec.test.helpers.inactivity_scores import (
    randomize_inactivity_scores,
)
from eth2spec.test.helpers.keys import builder_privkeys
from eth2spec.test.helpers.multi_operations import (
    build_random_block_from_state_for_next_slot,
    get_random_bls_to_execution_changes,
    get_random_execution_requests,
    get_random_sync_aggregate,
    prepare_state_and_get_random_deposits,
)
from eth2spec.test.helpers.payload_attestation import get_random_payload_attestations
from eth2spec.test.helpers.random import (
    patch_state_to_non_leaking,
    randomize_state as randomize_state_helper,
)
from eth2spec.test.helpers.state import (
    ensure_state_has_validators_across_lifecycle,
    next_epoch,
    next_slot,
    state_transition_and_sign_block,
)

# primitives:
# state


def _randomize_deposit_state(spec, state, stats):
    """
    To introduce valid, randomized deposits, the ``state`` deposit sub-state
    must be coordinated with the data that will ultimately go into blocks.

    This function randomizes the ``state`` in a way that can signal downstream to
    the block constructors how they should (or should not) make some randomized deposits.
    """
    rng = Random(999)
    block_count = stats.get("block_count", 0)
    deposits = []
    if block_count > 0:
        num_deposits = rng.randrange(1, block_count * spec.MAX_DEPOSITS)
        deposits = prepare_state_and_get_random_deposits(
            spec, state, rng, num_deposits=num_deposits
        )
    return {
        "deposits": deposits,
    }


def randomize_state(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    randomize_state_helper(spec, state, exit_fraction=exit_fraction, slash_fraction=slash_fraction)
    scenario_state = _randomize_deposit_state(spec, state, stats)
    return scenario_state


def randomize_state_altair(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    randomize_inactivity_scores(spec, state)
    return scenario_state


def randomize_state_bellatrix(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_altair(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    # TODO: randomize execution payload, merge status, etc.
    return scenario_state


def randomize_state_capella(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_bellatrix(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    # TODO: randomize withdrawals
    return scenario_state


def randomize_state_deneb(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_capella(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    # TODO: randomize execution payload
    return scenario_state


def randomize_state_electra(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_deneb(
        spec,
        state,
        stats,
        exit_fraction=exit_fraction,
        slash_fraction=slash_fraction,
    )
    return scenario_state


def randomize_state_fulu(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_electra(
        spec,
        state,
        stats,
        exit_fraction=exit_fraction,
        slash_fraction=slash_fraction,
    )
    return scenario_state


def randomize_state_gloas(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_fulu(
        spec,
        state,
        stats,
        exit_fraction=exit_fraction,
        slash_fraction=slash_fraction,
    )

    _add_random_builders(spec, state)

    return scenario_state


# epochs


def epochs_until_leak(spec):
    """
    State is "leaking" if the current epoch is at least
    this value after the last finalized epoch.
    """
    return spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY + 1


def epochs_for_shard_committee_period(spec):
    return spec.config.SHARD_COMMITTEE_PERIOD


# slots


def last_slot_in_epoch(spec):
    return spec.SLOTS_PER_EPOCH - 1


def random_slot_in_epoch(spec, rng=None):
    if rng is None:
        rng = Random(1336)
    return rng.randrange(1, spec.SLOTS_PER_EPOCH - 2)


def penultimate_slot_in_epoch(spec):
    return spec.SLOTS_PER_EPOCH - 2


# blocks


def no_block(_spec, _pre_state, _signed_blocks, _scenario_state):
    return None


# May need to make several attempts to find a block that does not correspond to a slashed
# proposer with the randomization helpers...
BLOCK_ATTEMPTS = 32


def _warn_if_empty_operations(block):
    """
    NOTE: a block may be missing deposits depending on how many were created
    and already inserted into existing blocks in a given scenario.
    """
    if len(block.body.proposer_slashings) == 0:
        warnings.warn(f"proposer slashings missing in block at slot {block.slot}")

    if len(block.body.attester_slashings) == 0:
        warnings.warn(f"attester slashings missing in block at slot {block.slot}")

    if len(block.body.attestations) == 0:
        warnings.warn(f"attestations missing in block at slot {block.slot}")

    if len(block.body.voluntary_exits) == 0:
        warnings.warn(f"voluntary exits missing in block at slot {block.slot}")


def _pull_deposits_from_scenario_state(spec, scenario_state, existing_block_count):
    all_deposits = scenario_state.get("deposits", [])
    start = existing_block_count * spec.MAX_DEPOSITS
    return all_deposits[start : start + spec.MAX_DEPOSITS]


def random_block(spec, state, signed_blocks, scenario_state):
    """
    Produce a random block.
    NOTE: this helper may mutate state, as it will attempt
    to produce a block over ``BLOCK_ATTEMPTS`` slots in order
    to find a valid block in the event that the proposer has already been slashed.
    """
    # NOTE: ``state`` has been "randomized" at this point and so will likely
    # contain a large number of slashed validators. This function needs to return
    # a valid block so it needs to check that the proposer of the next slot is not
    # slashed.
    # To do this, generate a ``temp_state`` to use for checking the propser in the next slot.
    # This ensures no accidental mutations happen to the ``state`` the caller expects to get back
    # after this function returns.
    # Using a copy of the state for proposer sampling is also sound as any inputs used for the
    # shuffling are fixed a few epochs prior to ``spec.get_current_epoch(state)``.
    temp_state = state.copy()
    next_slot(spec, temp_state)
    for _ in range(BLOCK_ATTEMPTS):
        proposer_index = spec.get_beacon_proposer_index(temp_state)
        proposer = state.validators[proposer_index]
        if proposer.slashed:
            next_slot(spec, state)
            next_slot(spec, temp_state)
        else:
            deposits_for_block = _pull_deposits_from_scenario_state(
                spec, scenario_state, len(signed_blocks)
            )
            block = build_random_block_from_state_for_next_slot(
                spec, state, deposits=deposits_for_block
            )
            _warn_if_empty_operations(block)
            return block
    raise AssertionError("could not find a block with an unslashed proposer, check ``state`` input")


SYNC_AGGREGATE_PARTICIPATION_BUCKETS = 4


def random_block_altair_with_cycling_sync_committee_participation(
    spec, state, signed_blocks, scenario_state
):
    block = random_block(spec, state, signed_blocks, scenario_state)
    block_index = len(signed_blocks) % SYNC_AGGREGATE_PARTICIPATION_BUCKETS
    fraction_missed = block_index * (1 / SYNC_AGGREGATE_PARTICIPATION_BUCKETS)
    fraction_participated = 1.0 - fraction_missed
    previous_root = block.parent_root
    block.body.sync_aggregate = get_random_sync_aggregate(
        spec,
        state,
        block.slot - 1,
        block_root=previous_root,
        fraction_participated=fraction_participated,
    )
    return block


def random_block_bellatrix(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_altair_with_cycling_sync_committee_participation(
        spec, state, signed_blocks, scenario_state
    )
    # build execution_payload at the next slot
    state = state.copy()
    next_slot(spec, state)
    block.body.execution_payload = build_randomized_execution_payload(spec, state, rng=rng)
    return block


def random_block_capella(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_bellatrix(spec, state, signed_blocks, scenario_state, rng=rng)
    block.body.bls_to_execution_changes = get_random_bls_to_execution_changes(
        spec, state, num_address_changes=rng.randint(1, spec.MAX_BLS_TO_EXECUTION_CHANGES)
    )
    return block


def random_block_deneb(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_capella(spec, state, signed_blocks, scenario_state, rng=rng)
    # TODO: more commitments. blob_kzg_commitments: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]
    # TODO: add MAX_BLOBS_PER_BLOCK_FULU at fulu
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(
        spec, blob_count=rng.randint(0, spec.config.MAX_BLOBS_PER_BLOCK), rng=rng
    )
    block.body.execution_payload.transactions.append(opaque_tx)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    block.body.blob_kzg_commitments = blob_kzg_commitments

    return block


def random_block_electra(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_deneb(spec, state, signed_blocks, scenario_state, rng=rng)
    block.body.execution_requests = get_random_execution_requests(spec, state, rng=rng)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)

    return block


def random_block_fulu(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_electra(spec, state, signed_blocks, scenario_state, rng=rng)

    return block


def random_block_gloas(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)

    # Get random Altair block
    block = random_block_altair_with_cycling_sync_committee_participation(
        spec, state, signed_blocks, scenario_state
    )

    # Add bls_to_execution_changes
    block.body.bls_to_execution_changes = get_random_bls_to_execution_changes(
        spec, state, num_address_changes=rng.randint(1, spec.MAX_BLS_TO_EXECUTION_CHANGES)
    )

    # Add signed_execution_payload_bid
    block.body.signed_execution_payload_bid = _build_random_signed_bid(spec, state, block, rng)

    # Add payload_attestations
    block.body.payload_attestations = get_random_payload_attestations(spec, state, rng)

    return block


# validations


def no_op_validation(_spec, _state):
    return True


def validate_is_leaking(spec, state):
    return spec.is_in_inactivity_leak(state)


def validate_is_not_leaking(spec, state):
    return not validate_is_leaking(spec, state)


# transitions


def with_validation(transition, validation):
    if isinstance(transition, Callable):
        transition = transition()
    transition["validation"] = validation
    return transition


def no_op_transition():
    return {}


def epoch_transition(n=0):
    return {
        "epochs_to_skip": n,
    }


def slot_transition(n=0):
    return {
        "slots_to_skip": n,
    }


def transition_to_leaking():
    return {
        "epochs_to_skip": epochs_until_leak,
        "validation": validate_is_leaking,
    }


transition_without_leak = with_validation(no_op_transition, validate_is_not_leaking)

# block transitions


def transition_with_random_block(block_randomizer):
    """
    Build a block transition with randomized data.
    Provide optional sub-transitions to advance some
    number of epochs or slots before applying the random block.
    """
    return {
        "block_producer": block_randomizer,
    }


# builders


def _add_random_builders(spec, state, rng=None):
    """Add random builders to state for gloas testing."""
    if rng is None:
        rng = Random(999)

    num_builders = rng.randint(0, 8)

    for i in range(num_builders):
        balance = spec.MIN_DEPOSIT_AMOUNT + rng.randint(0, 10) * spec.EFFECTIVE_BALANCE_INCREMENT
        builder = build_mock_builder(spec, i, balance)
        state.builders.append(builder)


# bids


def _build_random_signed_bid(spec, state, block, rng):
    """Build a random SignedExecutionPayloadBid, using either self-build or a real builder."""
    # Get random blobs to calculate the root
    _, _, blob_kzg_commitments, _ = get_sample_blob_tx(
        spec, blob_count=rng.randint(0, spec.config.MAX_BLOBS_PER_BLOCK), rng=rng
    )
    kzg_list = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        blob_kzg_commitments
    )

    # Find active builders
    active_builders = [
        i for i in range(len(state.builders)) if spec.is_active_builder(state, spec.BuilderIndex(i))
    ]

    # Use actual builder or self-build
    use_real_builder = len(active_builders) > 0 and rng.choice([True, False])

    if use_real_builder:
        builder_index = spec.BuilderIndex(rng.choice(active_builders))
        builder = state.builders[builder_index]
        pending = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
        min_balance = spec.MIN_DEPOSIT_AMOUNT + pending
        available = builder.balance - min_balance if builder.balance > min_balance else 0
        block_hash = spec.Hash32(rng.randbytes(32))
        fee_recipient = builder.execution_address
        value = spec.Gwei(rng.randint(0, available)) if available > 0 else spec.Gwei(0)
    else:
        builder_index = spec.BUILDER_INDEX_SELF_BUILD
        block_hash = spec.Hash32(b"\x01" + b"\x00" * 31)
        fee_recipient = spec.ExecutionAddress()
        value = spec.Gwei(0)

    bid = spec.ExecutionPayloadBid(
        parent_block_hash=state.latest_block_hash,
        parent_block_root=block.parent_root,
        block_hash=block_hash,
        prev_randao=spec.get_randao_mix(state, spec.get_current_epoch(state)),
        fee_recipient=fee_recipient,
        gas_limit=spec.uint64(30000000),
        builder_index=builder_index,
        slot=block.slot,
        value=value,
        execution_payment=spec.Gwei(0),
        blob_kzg_commitments_root=kzg_list.hash_tree_root(),
    )

    if use_real_builder:
        signature = spec.get_execution_payload_bid_signature(
            state, bid, builder_privkeys[builder_index]
        )
    else:
        signature = spec.G2_POINT_AT_INFINITY

    return spec.SignedExecutionPayloadBid(message=bid, signature=signature)


# setup and test gen


def _randomized_scenario_setup(state_randomizer):
    """
    Return a sequence of pairs of ("mutation", "validation").
    A "mutation" is a function that accepts (``spec``, ``state``, ``stats``) arguments and
    allegedly performs some change to the state.
    A "validation" is a function that accepts (spec, state) arguments and validates some change was made.

    The "mutation" may return some state that should be available to any down-stream transitions
    across the **entire** scenario.

    The ``stats`` parameter reflects a summary of actions in a given scenario like
    how many blocks will be produced. This data can be useful to construct a valid
    pre-state and so is provided at the setup stage.
    """

    def _skip_epochs(epoch_producer):
        def f(spec, state, _stats):
            """
            The unoptimized spec implementation is too slow to advance via ``next_epoch``.
            Instead, just overwrite the ``state.slot`` and continue...
            """
            epochs_to_skip = epoch_producer(spec)
            slots_to_skip = epochs_to_skip * spec.SLOTS_PER_EPOCH
            state.slot += slots_to_skip

        return f

    def _simulate_honest_execution(spec, state, _stats):
        """
        Want to start tests not in a leak state; the finality data
        may not reflect this condition with prior (arbitrary) mutations,
        so this mutator addresses that fact.
        """
        patch_state_to_non_leaking(spec, state)

    return (
        # NOTE: the block randomization function assumes at least 1 shard committee period
        # so advance the state before doing anything else.
        (_skip_epochs(epochs_for_shard_committee_period), no_op_validation),
        (_simulate_honest_execution, no_op_validation),
        (state_randomizer, ensure_state_has_validators_across_lifecycle),
    )


# Run the generated tests:


# while the test implementation works via code-gen,
# references to helper code in this module are serialized as str names.
# to resolve this references at runtime, we need a reference to this module:
_this_module = sys.modules[__name__]


def _resolve_ref(ref):
    if isinstance(ref, str):
        return getattr(_this_module, ref)
    return ref


def _iter_temporal(spec, description):
    """
    Intended to advance some number of {epochs, slots}.
    Caller can provide a constant integer or a callable deriving a number from
    the ``spec`` under consideration.
    """
    numeric = _resolve_ref(description)
    if isinstance(numeric, Callable):
        numeric = numeric(spec)
    yield from range(numeric)


def _compute_statistics(scenario):
    block_count = 0
    for transition in scenario["transitions"]:
        block_producer = _resolve_ref(transition.get("block_producer", None))
        if block_producer and block_producer != no_block:
            block_count += 1
    return {
        "block_count": block_count,
    }


def run_generated_randomized_test(spec, state, scenario):
    stats = _compute_statistics(scenario)
    if "setup" not in scenario:
        state_randomizer = _resolve_ref(scenario.get("state_randomizer", randomize_state))
        scenario["setup"] = _randomized_scenario_setup(state_randomizer)

    scenario_state = {}
    for mutation, validation in scenario["setup"]:
        additional_state = mutation(spec, state, stats)
        validation(spec, state)
        if additional_state:
            scenario_state.update(additional_state)

    yield "pre", state

    blocks = []
    for transition in scenario["transitions"]:
        epochs_to_skip = _iter_temporal(spec, transition["epochs_to_skip"])
        for _ in epochs_to_skip:
            next_epoch(spec, state)
        slots_to_skip = _iter_temporal(spec, transition["slots_to_skip"])
        for _ in slots_to_skip:
            next_slot(spec, state)

        block_producer = _resolve_ref(transition["block_producer"])
        block = block_producer(spec, state, blocks, scenario_state)
        if block:
            signed_block = state_transition_and_sign_block(spec, state, block)
            blocks.append(signed_block)

        validation = _resolve_ref(transition["validation"])
        assert validation(spec, state)

    yield "blocks", blocks
    yield "post", state
