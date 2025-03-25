from typing import Optional
from eth2spec.utils.ssz.ssz_typing import uint256, Bytes32
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    compute_el_block_hash,
)
from eth2spec.test.helpers.pow_block import (
    prepare_random_pow_chain,
)
from eth2spec.test.helpers.forks import is_post_eip7732
from eth2spec.test.context import (
    spec_state_test,
    with_bellatrix_and_later,
    spec_configured_state_test,
)


TERMINAL_BLOCK_HASH_CONFIG_VAR = (
    "0x0000000000000000000000000000000000000000000000000000000000000001"
)
TERMINAL_BLOCK_HASH = Bytes32(TERMINAL_BLOCK_HASH_CONFIG_VAR)


def run_validate_merge_block(spec, pow_chain, beacon_block, valid=True):
    """
    Run ``validate_merge_block``
    If ``valid == False``, run expecting ``AssertionError``
    """

    def get_pow_block(hash: spec.Bytes32) -> Optional[spec.PowBlock]:
        for block in pow_chain:
            if block.block_hash == hash:
                return block
        return None

    get_pow_block_backup = spec.get_pow_block

    # Guido authorized everyone to do this
    spec.get_pow_block = get_pow_block
    assertion_error_caught = False
    try:
        spec.validate_merge_block(beacon_block)
    except AssertionError:
        assertion_error_caught = True
    except Exception as e:
        spec.get_pow_block = get_pow_block_backup
        raise e
    spec.get_pow_block = get_pow_block_backup

    if valid:
        assert not assertion_error_caught
    else:
        assert assertion_error_caught


@with_bellatrix_and_later
@spec_state_test
def test_validate_merge_block_success(spec, state):
    pow_chain = prepare_random_pow_chain(spec, 2)
    pow_chain.head(
        -1
    ).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = build_empty_block_for_next_slot(spec, state)
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.parent_block_hash = (
            pow_chain.head().block_hash
        )
        block.body.signed_execution_payload_header.message.block_hash = (
            compute_el_block_hash(spec, payload, state)
        )
    else:
        block.body.execution_payload.parent_hash = pow_chain.head().block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    run_validate_merge_block(spec, pow_chain, block)


@with_bellatrix_and_later
@spec_state_test
def test_validate_merge_block_fail_block_lookup(spec, state):
    pow_chain = prepare_random_pow_chain(spec, 2)
    pow_chain.head(
        -1
    ).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = build_empty_block_for_next_slot(spec, state)
    run_validate_merge_block(spec, pow_chain, block, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_validate_merge_block_fail_parent_block_lookup(spec, state):
    pow_chain = prepare_random_pow_chain(spec, 1)
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = build_empty_block_for_next_slot(spec, state)
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.parent_block_hash = (
            pow_chain.head().block_hash
        )
        block.body.signed_execution_payload_header.message.block_hash = (
            compute_el_block_hash(spec, payload, state)
        )
    else:
        block.body.execution_payload.parent_hash = pow_chain.head().block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    run_validate_merge_block(spec, pow_chain, block, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_validate_merge_block_fail_after_terminal(spec, state):
    pow_chain = prepare_random_pow_chain(spec, 2)
    pow_chain.head(-1).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + uint256(
        1
    )
    block = build_empty_block_for_next_slot(spec, state)
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.parent_block_hash = (
            pow_chain.head().block_hash
        )
        block.body.signed_execution_payload_header.message.block_hash = (
            compute_el_block_hash(spec, payload, state)
        )
    else:
        block.body.execution_payload.parent_hash = pow_chain.head().block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    run_validate_merge_block(spec, pow_chain, block, valid=False)


@with_bellatrix_and_later
@spec_configured_state_test(
    {
        "TERMINAL_BLOCK_HASH": TERMINAL_BLOCK_HASH_CONFIG_VAR,
        "TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH": "0",
    }
)
def test_validate_merge_block_tbh_override_success(spec, state):
    pow_chain = prepare_random_pow_chain(spec, 2)
    # should fail if TTD check is reached
    pow_chain.head(
        -1
    ).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(2)
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(
        1
    )
    pow_chain.head().block_hash = TERMINAL_BLOCK_HASH
    block = build_empty_block_for_next_slot(spec, state)
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.parent_block_hash = (
            pow_chain.head().block_hash
        )
        block.body.signed_execution_payload_header.message.block_hash = (
            compute_el_block_hash(spec, payload, state)
        )
    else:
        block.body.execution_payload.parent_hash = pow_chain.head().block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    run_validate_merge_block(spec, pow_chain, block)


@with_bellatrix_and_later
@spec_configured_state_test(
    {
        "TERMINAL_BLOCK_HASH": TERMINAL_BLOCK_HASH_CONFIG_VAR,
        "TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH": "0",
    }
)
def test_validate_merge_block_fail_parent_hash_is_not_tbh(spec, state):
    pow_chain = prepare_random_pow_chain(spec, 2)
    # shouldn't fail if TTD check is reached
    pow_chain.head(
        -1
    ).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = build_empty_block_for_next_slot(spec, state)
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.parent_block_hash = (
            pow_chain.head().block_hash
        )
        block.body.signed_execution_payload_header.message.block_hash = (
            compute_el_block_hash(spec, payload, state)
        )
    else:
        block.body.execution_payload.parent_hash = pow_chain.head().block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    run_validate_merge_block(spec, pow_chain, block, valid=False)


@with_bellatrix_and_later
@spec_configured_state_test(
    {
        "TERMINAL_BLOCK_HASH": TERMINAL_BLOCK_HASH_CONFIG_VAR,
        "TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH": "1",
    }
)
def test_validate_merge_block_terminal_block_hash_fail_activation_not_reached(
    spec, state
):
    pow_chain = prepare_random_pow_chain(spec, 2)
    # shouldn't fail if TTD check is reached
    pow_chain.head(
        -1
    ).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_chain.head().block_hash = TERMINAL_BLOCK_HASH
    block = build_empty_block_for_next_slot(spec, state)
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.parent_block_hash = (
            pow_chain.head().block_hash
        )
        block.body.signed_execution_payload_header.message.block_hash = (
            compute_el_block_hash(spec, payload, state)
        )
    else:
        block.body.execution_payload.parent_hash = pow_chain.head().block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    run_validate_merge_block(spec, pow_chain, block, valid=False)


@with_bellatrix_and_later
@spec_configured_state_test(
    {
        "TERMINAL_BLOCK_HASH": TERMINAL_BLOCK_HASH_CONFIG_VAR,
        "TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH": "1",
    }
)
def test_validate_merge_block_fail_activation_not_reached_parent_hash_is_not_tbh(
    spec, state
):
    pow_chain = prepare_random_pow_chain(spec, 2)
    # shouldn't fail if TTD check is reached
    pow_chain.head(
        -1
    ).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = build_empty_block_for_next_slot(spec, state)
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.parent_block_hash = (
            pow_chain.head().block_hash
        )
        block.body.signed_execution_payload_header.message.block_hash = (
            compute_el_block_hash(spec, payload, state)
        )
    else:
        block.body.execution_payload.parent_hash = pow_chain.head().block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    run_validate_merge_block(spec, pow_chain, block, valid=False)
