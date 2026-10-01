from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    MAINNET,
)


@with_gloas_and_later
@spec_test
@single_phase
@with_presets([MAINNET], reason="to check the mainnet value")
def test_min_epochs_for_block_requests(spec):
    # Reduced from 33024 epochs by the churn limits introduced in EIP-8061
    assert spec.compute_min_epochs_for_block_requests() == 14299
