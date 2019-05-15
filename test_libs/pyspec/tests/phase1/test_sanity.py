from copy import deepcopy

import pytest

from py_ecc import bls
import eth2spec.phase1.spec as spec

from eth2spec.utils.minimal_ssz import signing_root
from eth2spec.phase1.spec import (
    # constants
    ZERO_HASH,
    SLOTS_PER_HISTORICAL_ROOT,
    # SSZ
    Deposit,
    Transfer,
    VoluntaryExit,
    # functions
    get_active_validator_indices,
    get_beacon_proposer_index,
    get_block_root_at_slot,
    get_current_epoch,
    get_domain,
    process_slot,
    verify_merkle_branch,
    state_transition,
    hash,
)
from eth2spec.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)
from .helpers import (
    advance_slot,
    get_balance,
    build_deposit_data,
    build_empty_block_for_next_slot,
    fill_aggregate_attestation,
    get_state_root,
    get_valid_attestation,
    get_valid_attester_slashing,
    get_valid_proposer_slashing,
    next_slot,
    privkeys,
    pubkeys,
)


# mark entire file as 'sanity'
pytestmark = pytest.mark.sanity

from tests.phase0.test_sanity import (
    test_slot_transition,
    test_empty_block_transition,
    test_skipped_slots,
    test_empty_epoch_transition,
    test_empty_epoch_transition_not_finalizing,
    test_proposer_slashing,
    test_attester_slashing,
    test_deposit_in_block,
    test_deposit_top_up,
    test_attestation,
    test_voluntary_exit,
    test_transfer,
    test_balance_driven_status_transitions,
    test_historical_batch,
    test_eth1_data_votes,
)
