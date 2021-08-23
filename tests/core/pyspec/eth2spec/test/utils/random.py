"""
Utility code to generate randomized block tests
"""

import itertools
import random
import warnings
from typing import Callable
from eth2spec.test.helpers.multi_operations import (
    build_random_block_from_state_for_next_slot,
)
from eth2spec.test.helpers.state import (
    next_slot,
    next_epoch,
    ensure_state_has_validators_across_lifecycle,
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.random import (
    randomize_state as randomize_state_helper,
)

rng = random.Random(1337)

def _warn_if_empty_operations(block):
    if len(block.body.deposits) == 0:
        warnings.warn(f"deposits missing in block at slot {block.slot}")

    if len(block.body.proposer_slashings) == 0:
        warnings.warn(f"proposer slashings missing in block at slot {block.slot}")

    if len(block.body.attester_slashings) == 0:
        warnings.warn(f"attester slashings missing in block at slot {block.slot}")

    if len(block.body.attestations) == 0:
        warnings.warn(f"attestations missing in block at slot {block.slot}")

    if len(block.body.voluntary_exits) == 0:
        warnings.warn(f"voluntary exits missing in block at slot {block.slot}")


# May need to make several attempts to find a block that does not correspond to a slashed
# proposer with the randomization helpers...
BLOCK_ATTEMPTS = 32
# Ensure this many blocks are present in *each* randomized scenario
BLOCK_TRANSITIONS_COUNT = 2

# primitives
## state

def randomize_state(spec, state, exit_fraction=0.1, slash_fraction=0.1):
    randomize_state_helper(spec, state, exit_fraction=exit_fraction, slash_fraction=slash_fraction)


## epochs

def _epochs_until_leak(spec):
    """
    State is "leaking" if the current epoch is at least
    this value after the last finalized epoch.
    """
    return spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY + 1


def _epochs_for_shard_committee_period(spec):
    return spec.config.SHARD_COMMITTEE_PERIOD


## slots

def _last_slot_in_epoch(spec):
    return spec.SLOTS_PER_EPOCH - 1


def _random_slot_in_epoch(rng):
    def _a_slot_in_epoch(spec):
        return rng.randrange(1, spec.SLOTS_PER_EPOCH - 2)
    return _a_slot_in_epoch


def _penultimate_slot_in_epoch(spec):
    return spec.SLOTS_PER_EPOCH - 2


## blocks

def _no_block(_spec, _pre_state, _signed_blocks):
    return None


def random_block(spec, state, _signed_blocks):
    """
    Produce a random block.
    NOTE: this helper may mutate state, as it will attempt
    to produce a block over ``BLOCK_ATTEMPTS`` slots in order
    to find a valid block in the event that the proposer has already been slashed.
    """
    temp_state = state.copy()
    next_slot(spec, temp_state)
    for _ in range(BLOCK_ATTEMPTS):
        proposer_index = spec.get_beacon_proposer_index(temp_state)
        proposer = state.validators[proposer_index]
        if proposer.slashed:
            next_slot(spec, state)
            next_slot(spec, temp_state)
        else:
            block = build_random_block_from_state_for_next_slot(spec, state)
            _warn_if_empty_operations(block)
            return block
    else:
        raise AssertionError("could not find a block with an unslashed proposer, check ``state`` input")


## validations

def _no_op_validation(spec, state):
    return True


def _validate_is_leaking(spec, state):
    return spec.is_in_inactivity_leak(state)


def _validate_is_not_leaking(spec, state):
    return not _validate_is_leaking(spec, state)


# transitions

def _with_validation(transition, validation):
    if isinstance(transition, Callable):
        transition = transition()
    transition["validation"] = validation
    return transition


def _no_op_transition():
    return {}


def _epoch_transition(n=0):
    return {
        "epochs_to_skip": n,
    }


def _slot_transition(n=0):
    return {
        "slots_to_skip": n,
    }


def _transition_to_leaking():
    return {
        "epochs_to_skip": _epochs_until_leak,
        "validation": _validate_is_leaking,
    }


_transition_without_leak = _with_validation(_no_op_transition, _validate_is_not_leaking)

## block transitions

def _transition_with_random_block(block_randomizer):
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
    Return a sequence of pairs of ("mutator", "validator"),
    a function that accepts (spec, state) arguments and performs some change
    and a function that accepts (spec, state) arguments and validates some change was made.
    """
    def _skip_epochs(epoch_producer):
        def f(spec, state):
            """
            The unoptimized spec implementation is too slow to advance via ``next_epoch``.
            Instead, just overwrite the ``state.slot`` and continue...
            """
            epochs_to_skip = epoch_producer(spec)
            slots_to_skip = epochs_to_skip * spec.SLOTS_PER_EPOCH
            state.slot += slots_to_skip
        return f

    def _simulate_honest_execution(spec, state):
        """
        Want to start tests not in a leak state; the finality data
        may not reflect this condition with prior (arbitrary) mutations,
        so this mutator addresses that fact.
        """
        state.justification_bits = (True, True, True, True)
        previous_epoch = spec.get_previous_epoch(state)
        previous_root = spec.get_block_root(state, previous_epoch)
        previous_previous_epoch = max(spec.GENESIS_EPOCH, spec.Epoch(previous_epoch - 1))
        previous_previous_root = spec.get_block_root(state, previous_previous_epoch)
        state.previous_justified_checkpoint = spec.Checkpoint(
            epoch=previous_previous_epoch,
            root=previous_previous_root,
        )
        state.current_justified_checkpoint = spec.Checkpoint(
            epoch=previous_epoch,
            root=previous_root,
        )
        state.finalized_checkpoint = spec.Checkpoint(
            epoch=previous_previous_epoch,
            root=previous_previous_root,
        )

    return (
        # NOTE: the block randomization function assumes at least 1 shard committee period
        # so advance the state before doing anything else.
        (_skip_epochs(_epochs_for_shard_committee_period), _no_op_validation),
        (_simulate_honest_execution, _no_op_validation),
        (state_randomizer, ensure_state_has_validators_across_lifecycle),
    )


def _normalize_transition(transition):
    """
    Provide "empty" or "no op" sub-transitions
    to a given transition.
    """
    if isinstance(transition, Callable):
        transition = transition()
    if "epochs_to_skip" not in transition:
        transition["epochs_to_skip"] = 0
    if "slots_to_skip" not in transition:
        transition["slots_to_skip"] = 0
    if "block_producer" not in transition:
        transition["block_producer"] = _no_block
    if "validation" not in transition:
        transition["validation"] = _no_op_validation
    return transition


def _normalize_scenarios(scenarios, state_randomizer):
    """
    "Normalize" a "scenario" so that a producer of a test case
    does not need to provide every expected key/value.
    """
    for scenario in scenarios:
        if "setup" not in scenario:
            scenario["setup"] = _randomized_scenario_setup(state_randomizer)

        transitions = scenario["transitions"]
        for i, transition in enumerate(transitions):
            transitions[i] = _normalize_transition(transition)


def _flatten(t):
    leak_transition = t[0]
    result = [leak_transition]
    for transition_batch in t[1]:
        for transition in transition_batch:
            result.append(transition)
    return result


def _generate_randomized_scenarios(state_randomizer, block_randomizer):
    """
    Generates a set of randomized testing scenarios.
    Return a sequence of "scenarios" where each scenario:
    1. Provides some setup
    2. Provides a sequence of transitions that mutate the state in some way,
        possibly yielding blocks along the way
    NOTE: scenarios are "normalized" with empty/no-op elements before returning
    to the test generation to facilitate brevity when writing scenarios by hand.
    NOTE: the main block driver builds a block for the **next** slot, so
    the slot transitions are offset by -1 to target certain boundaries.
    """
    # go forward 0 or 1 epochs
    epochs_set = (
        _epoch_transition(n=0),
        _epoch_transition(n=1),
    )
    # within those epochs, go forward to:
    slots_set = (
        # the first slot in an epoch (see note in docstring about offsets...)
        _slot_transition(_last_slot_in_epoch),
        # the second slot in an epoch
        _slot_transition(n=0),
        # some random number of slots, but not at epoch boundaries
        _slot_transition(_random_slot_in_epoch(rng)),
        # the last slot in an epoch (see note in docstring about offsets...)
        _slot_transition(_penultimate_slot_in_epoch),
    )
    # and produce a block...
    blocks_set = (
        _transition_with_random_block(block_randomizer),
    )
    # build a set of block transitions from combinations of sub-transitions
    transitions_generator = (
        itertools.product(epochs_set, slots_set, blocks_set) for
        _ in range(BLOCK_TRANSITIONS_COUNT)
    )
    block_transitions = zip(*transitions_generator)

    # and preface each set of block transitions with the possible leak transitions
    leak_transitions = (
        _transition_without_leak,
        _transition_to_leaking,
    )
    scenarios = [
        {"transitions": _flatten(t)}
        for t in itertools.product(leak_transitions, block_transitions)
    ]
    _normalize_scenarios(scenarios, state_randomizer)
    return scenarios


def _id_from_scenario(test_description):
    """
    Construct a test name for ``pytest`` infra.
    """
    def _to_id_part(prefix, x):
        suffix = str(x)
        if isinstance(x, Callable):
            suffix = x.__name__
        return f"{prefix}{suffix}"

    def _id_from_transition(transition):
        return ",".join((
            _to_id_part("epochs:", transition["epochs_to_skip"]),
            _to_id_part("slots:", transition["slots_to_skip"]),
            _to_id_part("with-block:", transition["block_producer"])
        ))

    return "|".join(map(_id_from_transition, test_description["transitions"]))

# Generate a series of randomized block tests:

def generate_randomized_tests(metafunc, state_randomizer=randomize_state, block_randomizer=random_block):
    """
    Pytest hook to generate test cases from dynamically computed data
    """
    generated_name = "test_description"
    generated_values = _generate_randomized_scenarios(state_randomizer, block_randomizer)
    metafunc.parametrize(generated_name, generated_values, ids=_id_from_scenario, scope="module")


def pytest_generate_tests_adapter(f):
    """
    Adapter decorator to allow dynamic test case generation
    while leveraging existing decorators specific to spec tests.
    """
    def wrapper(test_description, *args, **kwargs):
        kwargs["test_description"] = test_description
        f(*args, **kwargs)
    return wrapper

# Run the generated tests:

def _iter_temporal(spec, callable_or_int):
    """
    Intended to advance some number of {epochs, slots}.
    Caller can provide a constant integer or a callable deriving a number from
    the ``spec`` under consideration.
    """
    numeric = callable_or_int
    if isinstance(callable_or_int, Callable):
        numeric = callable_or_int(spec)
    for i in range(numeric):
        yield i


def run_generated_randomized_test(spec, state, test_description):
    for mutation, validation in test_description["setup"]:
        mutation(spec, state)
        validation(spec, state)

    yield "pre", state

    blocks = []
    for transition in test_description["transitions"]:
        epochs_to_skip = _iter_temporal(spec, transition["epochs_to_skip"])
        for _ in epochs_to_skip:
            next_epoch(spec, state)
        slots_to_skip = _iter_temporal(spec, transition["slots_to_skip"])
        for _ in slots_to_skip:
            next_slot(spec, state)

        block = transition["block_producer"](spec, state, blocks)
        if block:
            signed_block = state_transition_and_sign_block(spec, state, block)
            blocks.append(signed_block)

        assert transition["validation"](spec, state)

    yield "blocks", blocks
    yield "post", state
