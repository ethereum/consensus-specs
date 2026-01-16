from eth2spec.test.context import MINIMAL, spec_state_test, with_altair_and_later, with_presets
from eth2spec.test.helpers.fast_confirmation import (
    FCRTest,
)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fast_confirm_an_epoch(spec, state):
    fcr_test = FCRTest(spec)
    store = fcr_test.initialize(state, seed=1)
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr_test.next_slot_with_block_and_fast_confirmation()
        # Ensure head is confirmed
        assert store.confirmed_root == fcr_test.head()

    yield from fcr_test.get_test_artefacts()
