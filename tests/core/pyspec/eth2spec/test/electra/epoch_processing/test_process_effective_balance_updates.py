from eth2spec.test.context import spec_state_test, with_electra_and_later
from eth2spec.test.phase0.epoch_processing.test_process_effective_balance_updates import (
    run_test_effective_balance_hysteresis,
)


@with_electra_and_later
@spec_state_test
def test_effective_balance_hysteresis_with_compounding_credentials(spec, state):
    yield from run_test_effective_balance_hysteresis(spec, state, with_compounding_credentials=True)
