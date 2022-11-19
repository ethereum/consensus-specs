"""
Utility code to generate randomized block tests
"""

import sys
import warnings
from random import Random
from typing import Callable

from eth2spec.test.helpers.multi_operations import (
    build_random_block_from_state_for_next_slot,
    get_random_bls_to_execution_changes,
    get_random_sync_aggregate,
    prepare_state_and_get_random_deposits,
)
from eth2spec.test.helpers.inactivity_scores import (
    randomize_inactivity_scores,
)
from eth2spec.test.helpers.random import (
    randomize_state as randomize_state_helper,
    patch_state_to_non_leaking,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)
from eth2spec.test.helpers.state import (
    next_slot,
    next_epoch,
    ensure_state_has_validators_across_lifecycle,
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
        deposits = prepare_state_and_get_random_deposits(spec, state, rng, num_deposits=num_deposits)
    return {
        "deposits": deposits,
    }


def randomize_state(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    randomize_state_helper(spec, state, exit_fraction=exit_fraction, slash_fraction=slash_fraction)
    scenario_state = _randomize_deposit_state(spec, state, stats)
    return scenario_state


def randomize_state_altair(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state(spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction)
    randomize_inactivity_scores(spec, state)
    return scenario_state


def randomize_state_bellatrix(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_altair(spec,
                                            state,
                                            stats,
                                            exit_fraction=exit_fraction,
                                            slash_fraction=slash_fraction)
    # TODO: randomize execution payload, merge status, etc.
    return scenario_state


def randomize_state_capella(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_bellatrix(spec,
                                               state,
                                               stats,
                                               exit_fraction=exit_fraction,
                                               slash_fraction=slash_fraction)
    # TODO: randomize withdrawals
    return scenario_state


def randomize_state_eip4844(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_capella(spec,
                                             state,
                                             stats,
                                             exit_fraction=exit_fraction,
                                             slash_fraction=slash_fraction)
    # TODO: randomize execution payload
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


def random_slot_in_epoch(spec, rng=Random(1336)):
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
    return all_deposits[start:start + spec.MAX_DEPOSITS]


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
            deposits_for_block = _pull_deposits_from_scenario_state(spec, scenario_state, len(signed_blocks))
            block = build_random_block_from_state_for_next_slot(spec, state, deposits=deposits_for_block)
            _warn_if_empty_operations(block)
            return block
    else:
        raise AssertionError("could not find a block with an unslashed proposer, check ``state`` input")


SYNC_AGGREGATE_PARTICIPATION_BUCKETS = 4


def random_block_altair_with_cycling_sync_committee_participation(spec,
                                                                  state,
                                                                  signed_blocks,
                                                                  scenario_state):
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


def random_block_bellatrix(spec, state, signed_blocks, scenario_state):
    block = random_block_altair_with_cycling_sync_committee_participation(spec, state, signed_blocks, scenario_state)
    # TODO: return randomized execution payload
    return block


def random_block_capella(spec, state, signed_blocks, scenario_state, rng=Random(3456)):
    block = random_block_bellatrix(spec, state, signed_blocks, scenario_state)
    block.body.bls_to_execution_changes = get_random_bls_to_execution_changes(
        spec,
        state,
        num_address_changes=rng.randint(1, spec.MAX_BLS_TO_EXECUTION_CHANGES)
    )
    return block


def random_block_eip4844(spec, state, signed_blocks, scenario_state, rng=Random(3456)):
    block = random_block_capella(spec, state, signed_blocks, scenario_state)
    # TODO: more commitments. blob_kzg_commitments: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]
    opaque_tx, _, blob_kzg_commitments = get_sample_opaque_tx(spec, blob_count=1)
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.blob_kzg_commitments = blob_kzg_commitments

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
    for i in range(numeric):
        yield i


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
