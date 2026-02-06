import random

from eth2spec.debug.random_value import (
    get_random_ssz_object,
    RandomizationMode,
)
from eth2spec.test.context import (
    single_phase,
    spec_state_test,
    spec_test,
    with_all_phases_from_to,
    with_fulu_and_later,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.test.helpers.block import (
    sign_block,
)
from eth2spec.test.helpers.constants import (
    FULU,
    GLOAS,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.forks import (
    is_post_gloas,
)

# Helpers


def compute_data_column_sidecar(spec, state):
    rng = random.Random(5566)
    block = get_random_ssz_object(
        rng,
        spec.BeaconBlock,
        max_bytes_length=2000,
        max_list_length=2000,
        mode=RandomizationMode,
        chaos=True,
    )

    opaque_tx, blobs, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=2)
    cells_and_kzg_proofs = [spec.compute_cells_and_kzg_proofs(blob) for blob in blobs]

    if is_post_gloas(spec):
        block.body.signed_execution_payload_bid.message.blob_kzg_commitments = spec.List[
            spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
        ](blob_kzg_commitments)
    else:
        block.body.blob_kzg_commitments = blob_kzg_commitments
        block.body.execution_payload.transactions = [opaque_tx]
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    signed_block = sign_block(spec, state, block, proposer_index=0)
    sidecar = spec.get_data_column_sidecars_from_block(signed_block, cells_and_kzg_proofs)[0]
    return sidecar, blob_kzg_commitments


def _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments):
    if is_post_gloas(spec):
        return spec.verify_data_column_sidecar(sidecar, blob_kzg_commitments)
    return spec.verify_data_column_sidecar(sidecar)


def _verify_data_column_sidecar_kzg_proofs(spec, sidecar, blob_kzg_commitments):
    if is_post_gloas(spec):
        return spec.verify_data_column_sidecar_kzg_proofs(sidecar, blob_kzg_commitments)
    return spec.verify_data_column_sidecar_kzg_proofs(sidecar)


# Tests for verify_data_column_sidecar


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__valid(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    assert _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_zero_blobs(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    sidecar.column = []
    sidecar.kzg_proofs = []
    if is_post_gloas(spec):
        blob_kzg_commitments = []
    else:
        sidecar.kzg_commitments = []
    assert not _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_index(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    sidecar.index = 128
    assert not _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_mismatch_len_column(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    sidecar.column = sidecar.column[1:]
    assert not _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_mismatch_len_kzg_commitments(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    if is_post_gloas(spec):
        del blob_kzg_commitments[0]
    else:
        sidecar.kzg_commitments = sidecar.kzg_commitments[1:]
    assert not _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_mismatch_len_kzg_proofs(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    sidecar.kzg_proofs = sidecar.kzg_proofs[1:]
    assert not _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_kzg_commitments_over_max_blobs(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    slot = sidecar.signed_block_header.message.slot
    epoch = spec.compute_epoch_at_slot(slot)
    max_blobs = spec.get_blob_parameters(epoch).max_blobs_per_block

    for _ in range(max_blobs - len(sidecar.kzg_commitments) + 1):
        sidecar.kzg_commitments.append(sidecar.kzg_commitments[0])
    assert len(sidecar.kzg_commitments) > max_blobs

    assert not _verify_data_column_sidecar(spec, sidecar, blob_kzg_commitments)


# Tests for verify_data_column_sidecar_kzg_proofs


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__valid(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    assert _verify_data_column_sidecar_kzg_proofs(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__invalid_wrong_column(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    sidecar.column[0] = sidecar.column[1]
    assert not _verify_data_column_sidecar_kzg_proofs(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__invalid_wrong_commitment(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    if is_post_gloas(spec):
        blob_kzg_commitments[0] = blob_kzg_commitments[1]
    else:
        sidecar.kzg_commitments[0] = sidecar.kzg_commitments[1]
    assert not _verify_data_column_sidecar_kzg_proofs(spec, sidecar, blob_kzg_commitments)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__invalid_wrong_proof(spec, state):
    sidecar, blob_kzg_commitments = compute_data_column_sidecar(spec, state)
    sidecar.kzg_proofs[0] = sidecar.kzg_proofs[1]
    assert not _verify_data_column_sidecar_kzg_proofs(spec, sidecar, blob_kzg_commitments)


# Tests for verify_data_column_sidecar_inclusion_proof


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_inclusion_proof__valid(spec, state):
    sidecar, _ = compute_data_column_sidecar(spec, state)
    assert spec.verify_data_column_sidecar_inclusion_proof(sidecar)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_inclusion_proof__invalid_missing_commitment(spec, state):
    sidecar, _ = compute_data_column_sidecar(spec, state)
    sidecar.kzg_commitments = sidecar.kzg_commitments[1:]
    assert not spec.verify_data_column_sidecar_inclusion_proof(sidecar)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_inclusion_proof__invalid_duplicate_commitment(spec, state):
    sidecar, _ = compute_data_column_sidecar(spec, state)
    sidecar.kzg_commitments = sidecar.kzg_commitments + [sidecar.kzg_commitments[0]]
    assert not spec.verify_data_column_sidecar_inclusion_proof(sidecar)


# Tests for compute_subnet_for_data_column_sidecar


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_subnet_for_data_column_sidecar(spec):
    subnet_results = []
    for column_index in range(spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT):
        subnet_results.append(spec.compute_subnet_for_data_column_sidecar(column_index))
    # no duplicates
    assert len(subnet_results) == len(set(subnet_results))
    # next one should be duplicate
    next_subnet = spec.compute_subnet_for_data_column_sidecar(
        spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    )
    assert next_subnet == subnet_results[0]


# Tests for get_validators_custody_requirement


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__zero_validators(spec, state):
    validator_indices = []
    result = spec.get_validators_custody_requirement(state, validator_indices)
    # With 0 balance, count = 0, so max(0, VALIDATOR_CUSTODY_REQUIREMENT) = VALIDATOR_CUSTODY_REQUIREMENT
    assert result == spec.config.VALIDATOR_CUSTODY_REQUIREMENT


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__single_validator(spec, state):
    validator_indices = [0]

    state.validators[0].effective_balance = spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP

    result = spec.get_validators_custody_requirement(state, validator_indices)

    assert result == spec.config.VALIDATOR_CUSTODY_REQUIREMENT


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__multiple_validators(spec, state):
    assert len(state.validators) > 10, "Test requires more than 10 validators"
    assert 10 < spec.config.NUMBER_OF_CUSTODY_GROUPS, (
        "Test requires NUMBER_OF_CUSTODY_GROUPS to be more than 10"
    )

    # Use enough validators to get above minimum but below maximum
    # Need balance >= VALIDATOR_CUSTODY_REQUIREMENT * BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
    # That's 8 * 32 ETH = 256 ETH = 8 validators at 32 ETH each
    validator_indices = range(10)

    for validator_index in validator_indices:
        state.validators[
            validator_index
        ].effective_balance = spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP

    result = spec.get_validators_custody_requirement(state, validator_indices)

    # Calculate expected: total_balance // BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
    total_balance = sum(state.validators[i].effective_balance for i in validator_indices)
    expected_count = total_balance // spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
    expected = min(
        max(expected_count, spec.config.VALIDATOR_CUSTODY_REQUIREMENT),
        spec.config.NUMBER_OF_CUSTODY_GROUPS,
    )

    assert result == expected


def _run_get_validators_custody_requirement__maximum(spec, state, validator_indices):
    # This will force count to be more than NUMBER_OF_CUSTODY_GROUPS
    for validator_index in validator_indices:
        state.validators[validator_index].effective_balance = (
            (
                (
                    spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
                    * spec.config.NUMBER_OF_CUSTODY_GROUPS
                )
                // len(validator_indices)
            )
            + spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
            + 1
        )

    # Check here that it is
    total_node_balance = sum(
        state.validators[index].effective_balance for index in validator_indices
    )
    assert total_node_balance > (
        spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP * spec.config.NUMBER_OF_CUSTODY_GROUPS
    )
    count = total_node_balance // spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
    assert count > spec.config.NUMBER_OF_CUSTODY_GROUPS

    result = spec.get_validators_custody_requirement(state, validator_indices)

    assert result == spec.config.NUMBER_OF_CUSTODY_GROUPS


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__maximum_one_validator(spec, state):
    validator_indices = [0]

    _run_get_validators_custody_requirement__maximum(spec, state, validator_indices)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__maximum_ten_validators(spec, state):
    assert len(state.validators) > 10, "Test requires more than 10 validators"

    validator_indices = range(10)

    _run_get_validators_custody_requirement__maximum(spec, state, validator_indices)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__maximum_all_validators(spec, state):
    validator_indices = list(range(len(state.validators)))

    _run_get_validators_custody_requirement__maximum(spec, state, validator_indices)


def _run_get_validators_custody_requirement__minimum(spec, state, validator_indices):
    # This will force count to be more than NUMBER_OF_CUSTODY_GROUPS
    for validator_index in validator_indices:
        state.validators[validator_index].effective_balance = (
            (spec.config.VALIDATOR_CUSTODY_REQUIREMENT * spec.config.NUMBER_OF_CUSTODY_GROUPS)
            // len(validator_indices)
        ) - 1

    # Check here that it is
    total_node_balance = sum(
        state.validators[index].effective_balance for index in validator_indices
    )
    assert total_node_balance < (
        spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP * spec.config.VALIDATOR_CUSTODY_REQUIREMENT
    )
    count = total_node_balance // spec.config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
    assert count < spec.config.VALIDATOR_CUSTODY_REQUIREMENT

    result = spec.get_validators_custody_requirement(state, validator_indices)

    assert result == spec.config.VALIDATOR_CUSTODY_REQUIREMENT


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__minimum_one_validator(spec, state):
    validator_indices = [0]

    _run_get_validators_custody_requirement__minimum(spec, state, validator_indices)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__minimum_ten_validators(spec, state):
    assert len(state.validators) > 10, "Test requires more than 10 validators"

    validator_indices = range(10)

    _run_get_validators_custody_requirement__minimum(spec, state, validator_indices)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_get_validators_custody_requirement__minimum_all_validators(spec, state):
    validator_indices = list(range(len(state.validators)))

    _run_get_validators_custody_requirement__minimum(spec, state, validator_indices)
