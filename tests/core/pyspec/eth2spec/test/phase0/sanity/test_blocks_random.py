from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
)
from eth2spec.test.context import (
    with_all_phases,
    spec_state_test,
)


def generate_randomized_scenarios():
    # TODO: WIP schema
    return {
        # ("randomize_state", "ensure all validator states present: pending/deposited, activated, exited, slashed"),
        # ("randomized balances", "ensure distribution of bals"),
        # ("transition to leak if not already, maybe", "assert is or is not leaking"),
        "setup": [],
        "epochs_to_skip": 0, # 0, 1, 2, N, EPOCHS_TO_INACTIVITY_LEAK,
        "slots_to_skip": 0,  # 0, 1, 2, N, SLOTS_PER_EPOCH - 1,
        "transitions": [ # TODO: consider large numbers of blocks, load on generated data
            {
                "block_producer": lambda spec, state: spec.SignedBeaconBlock(),
                "epochs_to_skip": 0, # 0, 1, 2, N, EPOCHS_TO_INACTIVITY_LEAK,
                "slots_to_skip": 0,  # 0, 1, 2, N, SLOTS_PER_EPOCH - 1,
            }
        ],
    }


def id_from_scenario(test_description):
    return '-'.join(':'.join((str(k),str(v))) for k,v in test_description.items())


def pytest_generate_tests(metafunc):
    """
    Pytest hook to generate test cases from dynamically computed data
    """
    generated_name = "test_description"
    generated_values = generate_randomized_scenarios()
    metafunc.parametrize(generated_name, generated_values, ids=id_from_scenario, scope="module")


def pytest_generate_tests_adapter(f):
    """
    Adapter decorator to allow dynamic test case generation
    while leveraging existing decorators specific to spec tests.
    """
    def wrapper(test_description, *args, **kwargs):
        kwargs["test_description"] = test_description
        f(*args, **kwargs)
    return wrapper


@pytest_generate_tests_adapter
@with_all_phases
@spec_state_test
def test_harness_for_randomized_blocks(spec, state, test_description):
    for mutation, validation in test_description["setup"]:
        mutation(spec, state)
        validation(spec, state)
    for _ in range(len(test_description["epochs_to_skip"])):
        next_epoch(spec, state)
    for _ in range(len(test_description["slots_to_skip"])):
        next_slot(spec, state)
    for transition in test_description["transitions"]:
        # TODO apply transition
        pass
