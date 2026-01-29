from eth2spec.test.context import (
    default_activation_threshold,
    default_balances,
    MINIMAL,
    single_phase,
    spec_test,
    with_altair_and_later,
    with_custom_state,
    with_presets,
)
from eth2spec.test.helpers.fast_confirmation import (
    FCRTest,
)


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fast_confirm_an_epoch(spec, state):
    fcr_test = FCRTest(spec, seed=1)
    store = fcr_test.initialize(state)
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr_test.next_slot_with_block_and_fast_confirmation()
        # Ensure head is confirmed
        assert store.confirmed_root == fcr_test.head()

    yield from fcr_test.get_test_artefacts()
