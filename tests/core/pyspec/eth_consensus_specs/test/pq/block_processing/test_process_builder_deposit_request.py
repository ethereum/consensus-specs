from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    run_builder_deposit_request_processing,
)
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.keys import builder_pubkeys, xmss_builder_pubkeys
from eth_consensus_specs.test.helpers.preregistrations import (
    build_pq_builder_preregistration,
    build_pq_validator_preregistration,
    builder_preregistration_withdrawal_credentials,
)


def prepare_builder_deposit_request(
    spec, pubkey, amount, prefix=None, signature=bytes(96), withdrawal_credentials=None
):
    """
    A builder deposit request naming ``pubkey``, after ``prefix``.
    """
    if prefix is None:
        prefix = spec.XMSS_DEPOSIT_PREFIX
    if withdrawal_credentials is None:
        withdrawal_credentials = builder_preregistration_withdrawal_credentials(spec)
    return spec.BuilderDepositRequest(
        pubkey=spec.Bytes48(prefix + pubkey),
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        signature=spec.Bytes96(signature),
    )


def get_builder_index(state, pubkey):
    return [builder.pubkey for builder in state.builders].index(pubkey)


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit(spec, state):
    pubkey = xmss_builder_pubkeys[len(state.builders)]
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(spec, pubkey, amount)

    yield from run_builder_deposit_request_processing(spec, state, request)

    builder = state.builders[get_builder_index(state, pubkey)]
    assert builder.balance == amount
    assert builder.execution_address == request.withdrawal_credentials[12:]


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit_ignores_signature(spec, state):
    pubkey = xmss_builder_pubkeys[len(state.builders)]
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(spec, pubkey, amount, signature=b"\xee" * 96)

    yield from run_builder_deposit_request_processing(spec, state, request)

    builder = state.builders[get_builder_index(state, pubkey)]
    assert builder.balance == amount
    assert builder.withdrawable_epoch == spec.FAR_FUTURE_EPOCH


@with_phases([PQ])
@spec_state_test
def test_legacy_builder_deposit_initiates_exit(spec, state):
    bls_pubkey = builder_pubkeys[len(state.builders)]
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(spec, bls_pubkey[16:], amount, prefix=bls_pubkey[:16])
    assert spec.is_legacy_pubkey(request.pubkey)
    current_epoch = spec.get_current_epoch(state)

    yield from run_builder_deposit_request_processing(spec, state, request)

    builder = state.builders[get_builder_index(state, spec.compute_legacy_xmss_pubkey(bls_pubkey))]
    assert builder.balance == amount
    expected_withdrawable = current_epoch + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    assert builder.withdrawable_epoch == expected_withdrawable


@with_phases([PQ])
@spec_state_test
def test_legacy_builder_deposit_tops_up_unregistered_builder(spec, state):
    # A builder that did not register takes the legacy XMSS public key at the fork
    builder_index = 0
    bls_pubkey = builder_pubkeys[builder_index]
    state.builders[builder_index].pubkey = spec.compute_legacy_xmss_pubkey(bls_pubkey)
    pre_builder_count = len(state.builders)
    pre_balance = state.builders[builder_index].balance
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(spec, bls_pubkey[16:], amount, prefix=bls_pubkey[:16])
    assert spec.is_legacy_pubkey(request.pubkey)

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert len(state.builders) == pre_builder_count
    assert state.builders[builder_index].balance == pre_balance + amount


@with_phases([PQ])
@spec_state_test
def test_builder_top_up(spec, state):
    builder_index = 0
    pre_balance = state.builders[builder_index].balance
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(spec, state.builders[builder_index].pubkey, amount)

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert state.builders[builder_index].balance == pre_balance + amount


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit_matching_preregistration(spec, state):
    index = len(state.builders)
    state.builder_preregistrations.append(
        build_pq_builder_preregistration(
            spec, index, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
        )
    )
    pubkey = xmss_builder_pubkeys[index]
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(spec, pubkey, amount)

    yield from run_builder_deposit_request_processing(spec, state, request)

    builder = state.builders[get_builder_index(state, pubkey)]
    assert builder.balance == amount
    assert builder.execution_address == request.withdrawal_credentials[12:]
    assert len(state.builder_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit_preregistration_mismatched_credentials_discarded(spec, state):
    index = len(state.builders)
    state.builder_preregistrations.append(
        build_pq_builder_preregistration(
            spec, index, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
        )
    )
    pubkey = xmss_builder_pubkeys[index]
    request = prepare_builder_deposit_request(
        spec,
        pubkey,
        spec.MIN_DEPOSIT_AMOUNT,
        withdrawal_credentials=builder_preregistration_withdrawal_credentials(spec, b"\x77"),
    )
    pre_builder_count = len(state.builders)

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert len(state.builders) == pre_builder_count
    assert pubkey not in [builder.pubkey for builder in state.builders]
    assert len(state.builder_preregistrations) == 1


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit_expired_preregistration_not_enforced(spec, state):
    index = len(state.builders)
    state.builder_preregistrations.append(
        build_pq_builder_preregistration(spec, index, state.latest_execution_payload_bid.slot)
    )
    pubkey = xmss_builder_pubkeys[index]
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(
        spec,
        pubkey,
        amount,
        withdrawal_credentials=builder_preregistration_withdrawal_credentials(spec, b"\x77"),
    )

    yield from run_builder_deposit_request_processing(spec, state, request)

    builder = state.builders[get_builder_index(state, pubkey)]
    assert builder.balance == amount
    assert builder.execution_address == request.withdrawal_credentials[12:]
    assert len(state.builder_preregistrations) == 1


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit_ignores_validator_preregistration(spec, state):
    pubkey = xmss_builder_pubkeys[len(state.builders)]
    validator_preregistration = build_pq_validator_preregistration(
        spec, 0, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    )
    validator_preregistration.pubkey = pubkey
    state.validator_preregistrations.append(validator_preregistration)
    amount = spec.MIN_DEPOSIT_AMOUNT
    request = prepare_builder_deposit_request(spec, pubkey, amount)

    yield from run_builder_deposit_request_processing(spec, state, request)

    builder = state.builders[get_builder_index(state, pubkey)]
    assert builder.balance == amount
    assert list(state.validator_preregistrations) == [validator_preregistration]


@with_phases([PQ])
@spec_state_test
def test_builder_deposit_after_preregistration_consumed(spec, state):
    index = len(state.builders)
    state.builder_preregistrations.append(
        build_pq_builder_preregistration(
            spec, index, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
        )
    )
    pubkey = xmss_builder_pubkeys[index]
    amount = spec.MIN_DEPOSIT_AMOUNT
    spec.process_builder_deposit_request(
        state, prepare_builder_deposit_request(spec, pubkey, amount)
    )
    request = prepare_builder_deposit_request(
        spec,
        pubkey,
        amount,
        withdrawal_credentials=builder_preregistration_withdrawal_credentials(spec, b"\x77"),
    )

    yield from run_builder_deposit_request_processing(spec, state, request)

    builder = state.builders[get_builder_index(state, pubkey)]
    assert builder.balance == 2 * amount
    assert builder.execution_address == builder_preregistration_withdrawal_credentials(spec)[12:]
    assert len(state.builder_preregistrations) == 0
