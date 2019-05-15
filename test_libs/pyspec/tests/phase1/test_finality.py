from copy import deepcopy

import pytest

import eth2spec.phase1.spec as spec

from eth2spec.phase1.spec import (
    state_transition,
)

from tests.phase0.helpers import (
    build_empty_block_for_next_slot,
    fill_aggregate_attestation,
    get_current_epoch,
    get_epoch_start_slot,
    get_valid_attestation,
    next_epoch,
)

from tests.phase0.test_finality import (
    pytestmark,
    check_finality,
    test_finality_rule_1,
    test_finality_rule_2,
    test_finality_rule_3,
    test_finality_rule_4,
)
