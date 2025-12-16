from hashlib import sha256

from eth2spec.test.helpers.constants import (
    PHASE0,
    PREVIOUS_FORK_OF,
)
from eth2spec.test.helpers.eip7441 import (
    compute_whisk_initial_k_commitment_cached,
    compute_whisk_initial_tracker_cached,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_header_block_hash,
)
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_bellatrix,
    is_post_capella,
    is_post_deneb,
    is_post_eip7441,
    is_post_electra,
    is_post_fulu,
    is_post_gloas,
)
from eth2spec.test.helpers.keys import builder_pubkeys, pubkeys


def build_mock_builder(spec, i: int, balance: int):
    active_pubkey = builder_pubkeys[i]
    withdrawal_pubkey = builder_pubkeys[-1 - i]
    withdrawal_credentials = (
        spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + spec.hash(withdrawal_pubkey)[12:]
    )
    return spec.Builder(
        pubkey=active_pubkey,
        withdrawal_credentials=withdrawal_credentials,
        balance=balance,
        deposit_epoch=0,
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
    )


def build_mock_validator(spec, i: int, balance: int):
    active_pubkey = pubkeys[i]
    withdrawal_pubkey = pubkeys[-1 - i]
    if is_post_electra(spec):
        if balance > spec.MIN_ACTIVATION_BALANCE:
            # use compounding withdrawal credentials if the balance is higher than MIN_ACTIVATION_BALANCE
            withdrawal_credentials = (
                spec.COMPOUNDING_WITHDRAWAL_PREFIX
                + b"\x00" * 11
                + spec.hash(withdrawal_pubkey)[12:]
            )
        else:
            # insecurely use pubkey as withdrawal key as well
            withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(withdrawal_pubkey)[1:]
        max_effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    else:
        # insecurely use pubkey as withdrawal key as well
        withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(withdrawal_pubkey)[1:]
        max_effective_balance = spec.MAX_EFFECTIVE_BALANCE

    validator = spec.Validator(
        pubkey=active_pubkey,
        withdrawal_credentials=withdrawal_credentials,
        activation_eligibility_epoch=spec.FAR_FUTURE_EPOCH,
        activation_epoch=spec.FAR_FUTURE_EPOCH,
        exit_epoch=spec.FAR_FUTURE_EPOCH,
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        effective_balance=min(
            balance - balance % spec.EFFECTIVE_BALANCE_INCREMENT, max_effective_balance
        ),
    )

    return validator


def get_post_gloas_genesis_execution_payload_header(spec, slot, eth1_block_hash):
    # For Gloas, use the standard ExecutionPayloadHeader from the parent fork
    payload_header = spec.ExecutionPayloadHeader(
        parent_hash=b"\x30" * 32,
        fee_recipient=b"\x42" * 20,
        state_root=b"\x20" * 32,
        receipts_root=b"\x20" * 32,
        logs_bloom=b"\x35" * spec.BYTES_PER_LOGS_BLOOM,
        prev_randao=eth1_block_hash,
        block_number=0,
        gas_limit=30000000,
        gas_used=0,
        timestamp=0,
        extra_data=b"",
        base_fee_per_gas=1000000000,
        block_hash=eth1_block_hash,
        transactions_root=spec.Root(b"\x56" * 32),
        withdrawals_root=spec.Root(b"\x56" * 32),
        blob_gas_used=0,
        excess_blob_gas=0,
    )
    return payload_header


def get_sample_genesis_execution_payload_header(spec, slot, eth1_block_hash=None):
    if eth1_block_hash is None:
        eth1_block_hash = b"\x55" * 32
    if is_post_gloas(spec):
        return get_post_gloas_genesis_execution_payload_header(spec, slot, eth1_block_hash)
    payload_header = spec.ExecutionPayloadHeader(
        parent_hash=b"\x30" * 32,
        fee_recipient=b"\x42" * 20,
        state_root=b"\x20" * 32,
        receipts_root=b"\x20" * 32,
        logs_bloom=b"\x35" * spec.BYTES_PER_LOGS_BLOOM,
        prev_randao=eth1_block_hash,
        block_number=0,
        gas_limit=30000000,
        base_fee_per_gas=1000000000,
        block_hash=eth1_block_hash,
        transactions_root=spec.Root(b"\x56" * 32),
    )

    transactions_trie_root = bytes.fromhex(
        "56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
    )
    withdrawals_trie_root = None
    parent_beacon_block_root = None
    requests_hash = None

    if is_post_capella(spec):
        withdrawals_trie_root = bytes.fromhex(
            "56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
        )
    if is_post_deneb(spec):
        parent_beacon_block_root = bytes.fromhex(
            "0000000000000000000000000000000000000000000000000000000000000000"
        )
    if is_post_electra(spec):
        requests_hash = sha256(b"").digest()

    payload_header.block_hash = compute_el_header_block_hash(
        spec,
        payload_header,
        transactions_trie_root,
        withdrawals_trie_root,
        parent_beacon_block_root,
        requests_hash,
    )
    return payload_header


def create_genesis_state(spec, validator_balances, activation_threshold):
    deposit_root = b"\x42" * 32

    eth1_block_hash = b"\xda" * 32
    previous_version = spec.config.GENESIS_FORK_VERSION
    current_version = spec.config.GENESIS_FORK_VERSION

    if spec.fork != PHASE0:
        previous_fork = PREVIOUS_FORK_OF[spec.fork]
        if previous_fork == PHASE0:
            previous_version = spec.config.GENESIS_FORK_VERSION
        else:
            previous_version = getattr(spec.config, f"{previous_fork.upper()}_FORK_VERSION")
        current_version = getattr(spec.config, f"{spec.fork.upper()}_FORK_VERSION")

    genesis_block_body = spec.BeaconBlockBody()

    state = spec.BeaconState(
        genesis_time=0,
        eth1_deposit_index=len(validator_balances),
        eth1_data=spec.Eth1Data(
            deposit_root=deposit_root,
            deposit_count=len(validator_balances),
            block_hash=eth1_block_hash,
        ),
        fork=spec.Fork(
            previous_version=previous_version,
            current_version=current_version,
            epoch=spec.GENESIS_EPOCH,
        ),
        latest_block_header=spec.BeaconBlockHeader(
            body_root=spec.hash_tree_root(genesis_block_body)
        ),
        randao_mixes=[eth1_block_hash] * spec.EPOCHS_PER_HISTORICAL_VECTOR,
    )

    # We "hack" in the initial validators,
    #  as it is much faster than creating and processing genesis deposits for every single test case.
    state.balances = validator_balances

    state.validators = [
        build_mock_validator(spec, i, state.balances[i]) for i in range(len(validator_balances))
    ]

    # Process genesis activations
    for validator in state.validators:
        if validator.effective_balance >= activation_threshold:
            validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
            validator.activation_epoch = spec.GENESIS_EPOCH
        if is_post_altair(spec):
            state.previous_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
            state.current_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
            state.inactivity_scores.append(spec.uint64(0))

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = spec.hash_tree_root(state.validators)

    if is_post_altair(spec):
        # Fill in sync committees
        # Note: A duplicate committee is assigned for the current and next committee at genesis
        state.current_sync_committee = spec.get_next_sync_committee(state)
        state.next_sync_committee = spec.get_next_sync_committee(state)

    if is_post_gloas(spec):
        # Initialize the latest_execution_payload_bid
        genesis_block_body.signed_execution_payload_bid.message.block_hash = eth1_block_hash
    elif is_post_bellatrix(spec):
        # Initialize the execution payload header (with block number and genesis time set to 0)
        state.latest_execution_payload_header = get_sample_genesis_execution_payload_header(
            spec,
            spec.compute_start_slot_at_epoch(spec.GENESIS_EPOCH),
            eth1_block_hash=eth1_block_hash,
        )

    if is_post_electra(spec):
        state.deposit_requests_start_index = spec.UNSET_DEPOSIT_REQUESTS_START_INDEX

    if is_post_eip7441(spec):
        vc = len(state.validators)
        for i in range(vc):
            state.whisk_k_commitments.append(compute_whisk_initial_k_commitment_cached(i))
            state.whisk_trackers.append(compute_whisk_initial_tracker_cached(i))

        for i in range(spec.CANDIDATE_TRACKERS_COUNT):
            state.whisk_candidate_trackers[i] = compute_whisk_initial_tracker_cached(i % vc)

        for i in range(spec.PROPOSER_TRACKERS_COUNT):
            state.whisk_proposer_trackers[i] = compute_whisk_initial_tracker_cached(i % vc)

    if is_post_electra(spec):
        state.deposit_balance_to_consume = 0
        state.exit_balance_to_consume = 0
        state.earliest_exit_epoch = spec.GENESIS_EPOCH
        state.consolidation_balance_to_consume = 0
        state.earliest_consolidation_epoch = 0
        state.pending_deposits = []
        state.pending_partial_withdrawals = []
        state.pending_consolidations = []

    if is_post_gloas(spec):
        # TODO(jtraglia): make it so that the builder count is not hardcoded.
        builder_balance = 2 * spec.MIN_DEPOSIT_AMOUNT
        state.builders = [build_mock_builder(spec, i, builder_balance) for i in range(8)]
        state.execution_payload_availability = [0b1 for _ in range(spec.SLOTS_PER_HISTORICAL_ROOT)]
        state.payload_expected_withdrawals = spec.List[
            spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD
        ]()
        state.builder_pending_payments = [
            spec.BuilderPendingPayment() for _ in range(2 * spec.SLOTS_PER_EPOCH)
        ]
        state.builder_pending_withdrawals = []

    if is_post_fulu(spec):
        # Initialize proposer lookahead list
        state.proposer_lookahead = spec.initialize_proposer_lookahead(state)

    return state
