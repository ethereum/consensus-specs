"""
This test format currently uses code generation to assemble the tests
as the current test infra does not have a facility to dynamically
generate tests that can be seen by ``pytest``.

This will likely change in future releases of the testing infra.

NOTE: To add additional scenarios, add test cases below in ``_generate_randomized_scenarios``.
"""

import sys
import random
import warnings
from typing import Callable
import itertools

from eth2spec.test.utils.randomized_block_tests import (
    no_block,
    no_op_validation,
    randomize_state,
    randomize_state_altair,
    randomize_state_bellatrix,
    randomize_state_capella,
    randomize_state_deneb,
    randomize_state_electra,
    randomize_state_fulu,
    random_block,
    random_block_altair_with_cycling_sync_committee_participation,
    random_block_bellatrix,
    random_block_capella,
    random_block_deneb,
    random_block_electra,
    random_block_fulu,
    last_slot_in_epoch,
    random_slot_in_epoch,
    penultimate_slot_in_epoch,
    epoch_transition,
    slot_transition,
    transition_with_random_block,
    transition_to_leaking,
    transition_without_leak,
)
from eth2spec.test.helpers.constants import (
    PHASE0,
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    FULU,
)


# Ensure this many blocks are present in *each* randomized scenario
BLOCK_TRANSITIONS_COUNT = 2


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
        transition["block_producer"] = no_block
    if "validation" not in transition:
        transition["validation"] = no_op_validation
    return transition


def _normalize_scenarios(scenarios):
    """
    "Normalize" a "scenario" so that a producer of a test case
    does not need to provide every expected key/value.
    """
    for scenario in scenarios:
        transitions = scenario["transitions"]
        for i, transition in enumerate(transitions):
            transitions[i] = _normalize_transition(transition)


def _flatten(t):
    leak_transition = t[0]
    result = [leak_transition]
    for transition_batch in t[1]:
        for transition in transition_batch:
            if isinstance(transition, tuple):
                for subtransition in transition:
                    result.append(subtransition)
            else:
                result.append(transition)
    return result


def _generate_randomized_scenarios(block_randomizer):
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
        epoch_transition(n=0),
        epoch_transition(n=1),
    )
    # within those epochs, go forward to:
    slots_set = (
        # the first slot in an epoch (see note in docstring about offsets...)
        slot_transition(last_slot_in_epoch),
        # the second slot in an epoch
        slot_transition(n=0),
        # some random number of slots, but not at epoch boundaries
        slot_transition(random_slot_in_epoch),
        # the last slot in an epoch (see note in docstring about offsets...)
        slot_transition(penultimate_slot_in_epoch),
    )
    # and produce a block...
    blocks_set = (transition_with_random_block(block_randomizer),)

    rng = random.Random(1447)
    all_skips = list(itertools.product(epochs_set, slots_set))
    randomized_skips = (
        rng.sample(all_skips, len(all_skips)) for _ in range(BLOCK_TRANSITIONS_COUNT)
    )

    # build a set of block transitions from combinations of sub-transitions
    transitions_generator = (itertools.product(prefix, blocks_set) for prefix in randomized_skips)
    block_transitions = zip(*transitions_generator)

    # and preface each set of block transitions with the possible leak transitions
    leak_transitions = (
        transition_without_leak,
        transition_to_leaking,
    )
    scenarios = [
        {"transitions": _flatten(t)} for t in itertools.product(leak_transitions, block_transitions)
    ]
    _normalize_scenarios(scenarios)
    return scenarios


def _id_from_scenario(test_description):
    """
    Construct a name for the scenario based its data.
    """

    def _to_id_part(prefix, x):
        suffix = str(x)
        if isinstance(x, Callable):
            suffix = x.__name__
        return f"{prefix}{suffix}"

    def _id_from_transition(transition):
        return ",".join(
            (
                _to_id_part("epochs:", transition["epochs_to_skip"]),
                _to_id_part("slots:", transition["slots_to_skip"]),
                _to_id_part("with-block:", transition["block_producer"]),
            )
        )

    return "|".join(map(_id_from_transition, test_description["transitions"]))


test_imports_template = """\"\"\"
This module is generated from the ``random`` test generator.
Please do not edit this file manually.
See the README for that generator for more information.
\"\"\"

from eth2spec.test.helpers.constants import {phase}
from eth2spec.test.context import (
    misc_balances_in_default_range_with_many_validators,
    with_phases,
    zero_activation_threshold,
    only_generator,
)
from eth2spec.test.context import (
    always_bls,
    spec_test,
    with_custom_state,
    single_phase,
)
from eth2spec.test.utils.randomized_block_tests import (
    run_generated_randomized_test,
)"""

test_template = """
@only_generator(\"randomized test for broad coverage, not point-to-point CI\")
@with_phases([{phase}])
@with_custom_state(
    balances_fn=misc_balances_in_default_range_with_many_validators,
    threshold_fn=zero_activation_threshold
)
@spec_test
@single_phase
@always_bls
def test_randomized_{index}(spec, state):
    # scenario as high-level, informal text:
{name_as_comment}
    scenario = {scenario}  # noqa: E501
    yield from run_generated_randomized_test(
        spec,
        state,
        scenario,
    )"""


def _to_comment(name, indent_level):
    parts = name.split("|")
    indentation = "    " * indent_level
    parts = [indentation + "# " + part for part in parts]
    return "\n".join(parts)


def run_generate_tests_to_std_out(phase, state_randomizer, block_randomizer):
    scenarios = _generate_randomized_scenarios(block_randomizer)
    test_content = {"phase": phase.upper()}
    test_imports = test_imports_template.format(**test_content)
    test_file = [test_imports]
    for index, scenario in enumerate(scenarios):
        # required for setup phase
        scenario["state_randomizer"] = state_randomizer.__name__

        # need to pass name, rather than function reference...
        transitions = scenario["transitions"]
        for transition in transitions:
            for name, value in transition.items():
                if isinstance(value, Callable):
                    transition[name] = value.__name__

        test_content = test_content.copy()
        name = _id_from_scenario(scenario)
        test_content["name_as_comment"] = _to_comment(name, 1)
        test_content["index"] = index
        test_content["scenario"] = scenario
        test_instance = test_template.format(**test_content)
        test_file.append(test_instance)
    print("\n\n".join(test_file))


if __name__ == "__main__":
    did_generate = False
    if PHASE0 in sys.argv:
        did_generate = True
        run_generate_tests_to_std_out(
            PHASE0,
            state_randomizer=randomize_state,
            block_randomizer=random_block,
        )
    if ALTAIR in sys.argv:
        did_generate = True
        run_generate_tests_to_std_out(
            ALTAIR,
            state_randomizer=randomize_state_altair,
            block_randomizer=random_block_altair_with_cycling_sync_committee_participation,
        )
    if BELLATRIX in sys.argv:
        did_generate = True
        run_generate_tests_to_std_out(
            BELLATRIX,
            state_randomizer=randomize_state_bellatrix,
            block_randomizer=random_block_bellatrix,
        )
    if CAPELLA in sys.argv:
        did_generate = True
        run_generate_tests_to_std_out(
            CAPELLA,
            state_randomizer=randomize_state_capella,
            block_randomizer=random_block_capella,
        )
    if DENEB in sys.argv:
        did_generate = True
        run_generate_tests_to_std_out(
            DENEB,
            state_randomizer=randomize_state_deneb,
            block_randomizer=random_block_deneb,
        )
    if ELECTRA in sys.argv:
        did_generate = True
        run_generate_tests_to_std_out(
            ELECTRA,
            state_randomizer=randomize_state_electra,
            block_randomizer=random_block_electra,
        )
    if FULU in sys.argv:
        did_generate = True
        run_generate_tests_to_std_out(
            FULU,
            state_randomizer=randomize_state_fulu,
            block_randomizer=random_block_fulu,
        )
    if not did_generate:
        warnings.warn("no phase given for test generation")
