import copy

from eth_utils import encode_hex

from eth2spec.test.helpers.state import transition_to

from eth2spec.test.context import MINIMAL, spec_state_test, with_altair_and_later, with_presets

from eth2spec.test.helpers.block import build_empty_block  # NOTE: build_empty_block (not _for_next_slot)
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to
from eth2spec.test.helpers.fork_choice import add_block

from eth2spec.test.helpers.attestations import get_valid_attestations_for_block_at_slot

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

"""
Test on restart to GU
"""

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_restarts_to_gu_when_all_conditions_met(spec, state):
    """
    Test that confirmed_root restarts to GU (not finalized) when all conditions are met:
    1. At epoch start
    2. GU.epoch + 1 == current_epoch (GU is fresh)
    3. GU == unrealized_justifications[head]
    4. slot(confirmed) < slot(block(GU))
    
    Strategy:
    - Epochs 0-4: 100% participation, confirmations and justification advance
    - Epoch 5 start (before FCR):
      * Late slashing arrives → reconfirmation fails → triggers reset
      * GU (epoch 4) is fresh, slot(finalized) < slot(GU)
      * → restart to GU instead of staying at finalized
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch5_start = 5 * S

    # Epochs 0-4: Full participation (up to last slot of epoch 4)
    while fcr.current_slot() < epoch5_start - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch5_start - 1
    assert store.finalized_checkpoint.epoch >= spec.Epoch(2)

    # Last slot of epoch 4: build block, attest
    block_root = fcr.add_and_apply_block(parent_root=fcr.head())
    fcr.attest(block_root=block_root, slot=fcr.current_slot(), participation_rate=100)
    
    # Run FCR at last slot of epoch 4 - this samples GU
    fcr.run_fast_confirmation()
    
    # Now advance to epoch 5 start
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    assert fcr.current_slot() == epoch5_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Capture state before slashing
    confirmed_before_slashing = store.confirmed_root
    gu = store.current_epoch_observed_justified_checkpoint
    finalized = store.finalized_checkpoint.root
    head = fcr.head()
    head_uj = store.unrealized_justifications[head]
    current_epoch = spec.get_current_store_epoch(store)
    
    gu_slot = spec.get_block_slot(store, gu.root)
    finalized_slot = spec.get_block_slot(store, finalized)

    # Verify preconditions for restart-to-GU
    assert gu.epoch + 1 == current_epoch, \
        f"GU not fresh: {gu.epoch} + 1 != {current_epoch}"
    assert confirmed_before_slashing != finalized, \
        "Should have confirmations before slashing"
    assert gu == head_uj, \
        "GU != head's UJ"
    assert finalized_slot < gu_slot, \
        f"slot(finalized)={finalized_slot} >= slot(GU)={gu_slot}"
    assert gu.root != finalized, \
        "GU == finalized (test not meaningful)"

    # Late slashing: slash 50% to break reconfirmation
    fcr.apply_attester_slashing(slashing_percentage=50, slot=fcr.current_slot())

    # Run FCR - should reset due to reconfirmation failure, then restart to GU
    fcr.run_fast_confirmation()

    # Verify restart to GU (not finalized)
    assert store.confirmed_root == gu.root, \
        "Should restart to GU"
    assert store.confirmed_root != finalized, \
        "Should NOT stay at finalized"

    yield from fcr.get_test_artefacts()