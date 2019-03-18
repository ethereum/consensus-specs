from build.utils.minimal_ssz import *
from build.utils.bls_stub import *
def int_to_bytes1(x): return x.to_bytes(1, 'little')
def int_to_bytes2(x): return x.to_bytes(2, 'little')
def int_to_bytes3(x): return x.to_bytes(3, 'little')
def int_to_bytes4(x): return x.to_bytes(4, 'little')
def int_to_bytes8(x): return x.to_bytes(8, 'little')
def int_to_bytes32(x): return x.to_bytes(32, 'little')
def int_to_bytes48(x): return x.to_bytes(48, 'little')
def int_to_bytes96(x): return x.to_bytes(96, 'little')
SLOTS_PER_EPOCH = 64
def slot_to_epoch(x): return x // SLOTS_PER_EPOCH

from typing import (
    Any,
    Callable,
    List,
    NewType,
    Tuple,
)


Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64
ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64
Bytes32 = NewType('Bytes32', bytes)  # bytes32
BLSPubkey = NewType('BLSPubkey', bytes)  # bytes48
BLSSignature = NewType('BLSSignature', bytes)  # bytes96
Any = None
Store = None
    
SHARD_COUNT = 2**10
TARGET_COMMITTEE_SIZE = 2**7
MAX_BALANCE_CHURN_QUOTIENT = 2**5
MAX_INDICES_PER_SLASHABLE_VOTE = 2**12
MAX_EXIT_DEQUEUES_PER_EPOCH = 2**2
SHUFFLE_ROUND_COUNT = 90
DEPOSIT_CONTRACT_ADDRESS = 0x1234567890123567890123456789012357890
DEPOSIT_CONTRACT_TREE_DEPTH = 2**5
MIN_DEPOSIT_AMOUNT = 2**0 * 10**9
MAX_DEPOSIT_AMOUNT = 2**5 * 10**9
FORK_CHOICE_BALANCE_INCREMENT = 2**0 * 10**9
EJECTION_BALANCE = 2**4 * 10**9
GENESIS_FORK_VERSION = 0
GENESIS_SLOT = 2**32
GENESIS_EPOCH = slot_to_epoch(GENESIS_SLOT)
GENESIS_START_SHARD = 0
FAR_FUTURE_EPOCH = 2**64 - 1
ZERO_HASH = int_to_bytes32(0)
EMPTY_SIGNATURE = int_to_bytes96(0)
BLS_WITHDRAWAL_PREFIX_BYTE = int_to_bytes1(0)
SECONDS_PER_SLOT = 6
MIN_ATTESTATION_INCLUSION_DELAY = 2**2
SLOTS_PER_EPOCH = 2**6
MIN_SEED_LOOKAHEAD = 2**0
ACTIVATION_EXIT_DELAY = 2**2
EPOCHS_PER_ETH1_VOTING_PERIOD = 2**4
SLOTS_PER_HISTORICAL_ROOT = 2**13
MIN_VALIDATOR_WITHDRAWABILITY_DELAY = 2**8
PERSISTENT_COMMITTEE_PERIOD = 2**11
LATEST_RANDAO_MIXES_LENGTH = 2**13
LATEST_ACTIVE_INDEX_ROOTS_LENGTH = 2**13
LATEST_SLASHED_EXIT_LENGTH = 2**13
BASE_REWARD_QUOTIENT = 2**5
WHISTLEBLOWER_REWARD_QUOTIENT = 2**9
ATTESTATION_INCLUSION_REWARD_QUOTIENT = 2**3
INACTIVITY_PENALTY_QUOTIENT = 2**24
MIN_PENALTY_QUOTIENT = 2**5
MAX_PROPOSER_SLASHINGS = 2**4
MAX_ATTESTER_SLASHINGS = 2**0
MAX_ATTESTATIONS = 2**7
MAX_DEPOSITS = 2**4
MAX_VOLUNTARY_EXITS = 2**4
MAX_TRANSFERS = 2**4
DOMAIN_BEACON_BLOCK = 0
DOMAIN_RANDAO = 1
DOMAIN_ATTESTATION = 2
DOMAIN_DEPOSIT = 3
DOMAIN_VOLUNTARY_EXIT = 4
DOMAIN_TRANSFER = 5
Fork = SSZType({
    # Previous fork version
    'previous_version': 'bytes4',
    # Current fork version
    'current_version': 'bytes4',
    # Fork epoch number
    'epoch': 'uint64',
})
Crosslink = SSZType({
    # Epoch number
    'epoch': 'uint64',
    # Shard data since the previous crosslink
    'crosslink_data_root': 'bytes32',
})
Eth1Data = SSZType({
    # Root of the deposit tree
    'deposit_root': 'bytes32',
    # Block hash
    'block_hash': 'bytes32',
})
Eth1DataVote = SSZType({
    # Data being voted for
    'eth1_data': Eth1Data,
    # Vote count
    'vote_count': 'uint64',
})
AttestationData = SSZType({
    # LMD GHOST vote
    'slot': 'uint64',
    'beacon_block_root': 'bytes32',

    # FFG vote
    'source_epoch': 'uint64',
    'source_root': 'bytes32',
    'target_root': 'bytes32',

    # Crosslink vote
    'shard': 'uint64',
    'previous_crosslink': Crosslink,
    'crosslink_data_root': 'bytes32',
})
AttestationDataAndCustodyBit = SSZType({
    # Attestation data
    'data': AttestationData,
    # Custody bit
    'custody_bit': 'bool',
})
SlashableAttestation = SSZType({
    # Validator indices
    'validator_indices': ['uint64'],
    # Attestation data
    'data': AttestationData,
    # Custody bitfield
    'custody_bitfield': 'bytes',
    # Aggregate signature
    'aggregate_signature': 'bytes96',
})
DepositInput = SSZType({
    # BLS pubkey
    'pubkey': 'bytes48',
    # Withdrawal credentials
    'withdrawal_credentials': 'bytes32',
    # A BLS signature of this `DepositInput`
    'proof_of_possession': 'bytes96',
})
DepositData = SSZType({
    # Amount in Gwei
    'amount': 'uint64',
    # Timestamp from deposit contract
    'timestamp': 'uint64',
    # Deposit input
    'deposit_input': DepositInput,
})
BeaconBlockHeader = SSZType({
    'slot': 'uint64',
    'previous_block_root': 'bytes32',
    'state_root': 'bytes32',
    'block_body_root': 'bytes32',
    'signature': 'bytes96',
})
Validator = SSZType({
    # BLS public key
    'pubkey': 'bytes48',
    # Withdrawal credentials
    'withdrawal_credentials': 'bytes32',
    # Epoch when validator activated
    'activation_epoch': 'uint64',
    # Epoch when validator exited
    'exit_epoch': 'uint64',
    # Epoch when validator is eligible to withdraw
    'withdrawable_epoch': 'uint64',
    # Did the validator initiate an exit
    'initiated_exit': 'bool',
    # Was the validator slashed
    'slashed': 'bool',
})
PendingAttestation = SSZType({
    # Attester aggregation bitfield
    'aggregation_bitfield': 'bytes',
    # Attestation data
    'data': AttestationData,
    # Custody bitfield
    'custody_bitfield': 'bytes',
    # Inclusion slot
    'inclusion_slot': 'uint64',
})
HistoricalBatch = SSZType({
    # Block roots
    'block_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    # State roots
    'state_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
})
ProposerSlashing = SSZType({
    # Proposer index
    'proposer_index': 'uint64',
    # First block header
    'header_1': BeaconBlockHeader,
    # Second block header
    'header_2': BeaconBlockHeader,
})
AttesterSlashing = SSZType({
    # First slashable attestation
    'slashable_attestation_1': SlashableAttestation,
    # Second slashable attestation
    'slashable_attestation_2': SlashableAttestation,
})
Attestation = SSZType({
    # Attester aggregation bitfield
    'aggregation_bitfield': 'bytes',
    # Attestation data
    'data': AttestationData,
    # Custody bitfield
    'custody_bitfield': 'bytes',
    # BLS aggregate signature
    'aggregate_signature': 'bytes96',
})
Deposit = SSZType({
    # Branch in the deposit tree
    'proof': ['bytes32', DEPOSIT_CONTRACT_TREE_DEPTH],
    # Index in the deposit tree
    'index': 'uint64',
    # Data
    'deposit_data': DepositData,
})
VoluntaryExit = SSZType({
    # Minimum epoch for processing exit
    'epoch': 'uint64',
    # Index of the exiting validator
    'validator_index': 'uint64',
    # Validator signature
    'signature': 'bytes96',
})
Transfer = SSZType({
    # Sender index
    'sender': 'uint64',
    # Recipient index
    'recipient': 'uint64',
    # Amount in Gwei
    'amount': 'uint64',
    # Fee in Gwei for block proposer
    'fee': 'uint64',
    # Inclusion slot
    'slot': 'uint64',
    # Sender withdrawal pubkey
    'pubkey': 'bytes48',
    # Sender signature
    'signature': 'bytes96',
})
BeaconBlockBody = SSZType({
    'randao_reveal': 'bytes96',
    'eth1_data': Eth1Data,
    'proposer_slashings': [ProposerSlashing],
    'attester_slashings': [AttesterSlashing],
    'attestations': [Attestation],
    'deposits': [Deposit],
    'voluntary_exits': [VoluntaryExit],
    'transfers': [Transfer],
})
BeaconBlock = SSZType({
    # Header
    'slot': 'uint64',
    'previous_block_root': 'bytes32',
    'state_root': 'bytes32',
    'body': BeaconBlockBody,
    'signature': 'bytes96',
})
BeaconState = SSZType({
    # Misc
    'slot': 'uint64',
    'genesis_time': 'uint64',
    'fork': Fork,  # For versioning hard forks

    # Validator registry
    'validator_registry': [Validator],
    'validator_balances': ['uint64'],
    'validator_registry_update_epoch': 'uint64',

    # Randomness and committees
    'latest_randao_mixes': ['bytes32', LATEST_RANDAO_MIXES_LENGTH],
    'previous_shuffling_start_shard': 'uint64',
    'current_shuffling_start_shard': 'uint64',
    'previous_shuffling_epoch': 'uint64',
    'current_shuffling_epoch': 'uint64',
    'previous_shuffling_seed': 'bytes32',
    'current_shuffling_seed': 'bytes32',

    # Finality
    'previous_epoch_attestations': [PendingAttestation],
    'current_epoch_attestations': [PendingAttestation],
    'previous_justified_epoch': 'uint64',
    'current_justified_epoch': 'uint64',
    'previous_justified_root': 'bytes32',
    'current_justified_root': 'bytes32',
    'justification_bitfield': 'uint64',
    'finalized_epoch': 'uint64',
    'finalized_root': 'bytes32',

    # Recent state
    'latest_crosslinks': [Crosslink, SHARD_COUNT],
    'latest_block_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    'latest_state_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    'latest_active_index_roots': ['bytes32', LATEST_ACTIVE_INDEX_ROOTS_LENGTH],
    'latest_slashed_balances': ['uint64', LATEST_SLASHED_EXIT_LENGTH],  # Balances slashed at every withdrawal period
    'latest_block_header': BeaconBlockHeader,  # `latest_block_header.state_root == ZERO_HASH` temporarily
    'historical_roots': ['bytes32'],

    # Ethereum 1.0 chain data
    'latest_eth1_data': Eth1Data,
    'eth1_data_votes': [Eth1DataVote],
    'deposit_index': 'uint64'
})
def xor(bytes1: Bytes32, bytes2: Bytes32) -> Bytes32:
    return bytes(a ^ b for a, b in zip(bytes1, bytes2))
def get_temporary_block_header(block: BeaconBlock) -> BeaconBlockHeader:
    """
    Return the block header corresponding to a block with ``state_root`` set to ``ZERO_HASH``.
    """
    return BeaconBlockHeader(
        slot=block.slot,
        previous_block_root=block.previous_block_root,
        state_root=ZERO_HASH,
        block_body_root=hash_tree_root(block.body),
        signature=block.signature,
    )
def slot_to_epoch(slot: Slot) -> Epoch:
    """
    Return the epoch number of the given ``slot``.
    """
    return slot // SLOTS_PER_EPOCH
def get_previous_epoch(state: BeaconState) -> Epoch:
    """`
    Return the previous epoch of the given ``state``.
    """
    return get_current_epoch(state) - 1
def get_current_epoch(state: BeaconState) -> Epoch:
    """
    Return the current epoch of the given ``state``.
    """
    return slot_to_epoch(state.slot)
def get_epoch_start_slot(epoch: Epoch) -> Slot:
    """
    Return the starting slot of the given ``epoch``.
    """
    return epoch * SLOTS_PER_EPOCH
def is_active_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is active.
    """
    return validator.activation_epoch <= epoch < validator.exit_epoch
def get_active_validator_indices(validators: List[Validator], epoch: Epoch) -> List[ValidatorIndex]:
    """
    Get indices of active validators from ``validators``.
    """
    return [i for i, v in enumerate(validators) if is_active_validator(v, epoch)]
def get_permuted_index(index: int, list_size: int, seed: Bytes32) -> int:
    """
    Return `p(index)` in a pseudorandom permutation `p` of `0...list_size-1` with ``seed`` as entropy.

    Utilizes 'swap or not' shuffling found in
    https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf
    See the 'generalized domain' algorithm on page 3.
    """
    assert index < list_size
    assert list_size <= 2**40

    for round in range(SHUFFLE_ROUND_COUNT):
        pivot = bytes_to_int(hash(seed + int_to_bytes1(round))[0:8]) % list_size
        flip = (pivot - index) % list_size
        position = max(index, flip)
        source = hash(seed + int_to_bytes1(round) + int_to_bytes4(position // 256))
        byte = source[(position % 256) // 8]
        bit = (byte >> (position % 8)) % 2
        index = flip if bit else index

    return index
def split(values: List[Any], split_count: int) -> List[List[Any]]:
    """
    Splits ``values`` into ``split_count`` pieces.
    """
    list_length = len(values)
    return [
        values[(list_length * i // split_count): (list_length * (i + 1) // split_count)]
        for i in range(split_count)
    ]
def get_epoch_committee_count(active_validator_count: int) -> int:
    """
    Return the number of committees in one epoch.
    """
    return max(
        1,
        min(
            SHARD_COUNT // SLOTS_PER_EPOCH,
            active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
        )
    ) * SLOTS_PER_EPOCH
def get_shuffling(seed: Bytes32,
                  validators: List[Validator],
                  epoch: Epoch) -> List[List[ValidatorIndex]]:
    """
    Shuffle active validators and split into crosslink committees.
    Return a list of committees (each a list of validator indices).
    """
    # Shuffle active validator indices
    active_validator_indices = get_active_validator_indices(validators, epoch)
    length = len(active_validator_indices)
    shuffled_indices = [active_validator_indices[get_permuted_index(i, length, seed)] for i in range(length)]

    # Split the shuffled active validator indices
    return split(shuffled_indices, get_epoch_committee_count(length))
def get_previous_epoch_committee_count(state: BeaconState) -> int:
    """
    Return the number of committees in the previous epoch of the given ``state``.
    """
    previous_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.previous_shuffling_epoch,
    )
    return get_epoch_committee_count(len(previous_active_validators))
def get_current_epoch_committee_count(state: BeaconState) -> int:
    """
    Return the number of committees in the current epoch of the given ``state``.
    """
    current_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.current_shuffling_epoch,
    )
    return get_epoch_committee_count(len(current_active_validators))
def get_next_epoch_committee_count(state: BeaconState) -> int:
    """
    Return the number of committees in the next epoch of the given ``state``.
    """
    next_active_validators = get_active_validator_indices(
        state.validator_registry,
        get_current_epoch(state) + 1,
    )
    return get_epoch_committee_count(len(next_active_validators))
def get_crosslink_committees_at_slot(state: BeaconState,
                                     slot: Slot,
                                     registry_change: bool=False) -> List[Tuple[List[ValidatorIndex], Shard]]:
    """
    Return the list of ``(committee, shard)`` tuples for the ``slot``.

    Note: There are two possible shufflings for crosslink committees for a
    ``slot`` in the next epoch -- with and without a `registry_change`
    """
    epoch = slot_to_epoch(slot)
    current_epoch = get_current_epoch(state)
    previous_epoch = get_previous_epoch(state)
    next_epoch = current_epoch + 1

    assert previous_epoch <= epoch <= next_epoch

    if epoch == current_epoch:
        committees_per_epoch = get_current_epoch_committee_count(state)
        seed = state.current_shuffling_seed
        shuffling_epoch = state.current_shuffling_epoch
        shuffling_start_shard = state.current_shuffling_start_shard
    elif epoch == previous_epoch:
        committees_per_epoch = get_previous_epoch_committee_count(state)
        seed = state.previous_shuffling_seed
        shuffling_epoch = state.previous_shuffling_epoch
        shuffling_start_shard = state.previous_shuffling_start_shard
    elif epoch == next_epoch:
        epochs_since_last_registry_update = current_epoch - state.validator_registry_update_epoch
        if registry_change:
            committees_per_epoch = get_next_epoch_committee_count(state)
            seed = generate_seed(state, next_epoch)
            shuffling_epoch = next_epoch
            current_committees_per_epoch = get_current_epoch_committee_count(state)
            shuffling_start_shard = (state.current_shuffling_start_shard + current_committees_per_epoch) % SHARD_COUNT
        elif epochs_since_last_registry_update > 1 and is_power_of_two(epochs_since_last_registry_update):
            committees_per_epoch = get_next_epoch_committee_count(state)
            seed = generate_seed(state, next_epoch)
            shuffling_epoch = next_epoch
            shuffling_start_shard = state.current_shuffling_start_shard
        else:
            committees_per_epoch = get_current_epoch_committee_count(state)
            seed = state.current_shuffling_seed
            shuffling_epoch = state.current_shuffling_epoch
            shuffling_start_shard = state.current_shuffling_start_shard

    shuffling = get_shuffling(
        seed,
        state.validator_registry,
        shuffling_epoch,
    )
    offset = slot % SLOTS_PER_EPOCH
    committees_per_slot = committees_per_epoch // SLOTS_PER_EPOCH
    slot_start_shard = (shuffling_start_shard + committees_per_slot * offset) % SHARD_COUNT

    return [
        (
            shuffling[committees_per_slot * offset + i],
            (slot_start_shard + i) % SHARD_COUNT,
        )
        for i in range(committees_per_slot)
    ]
def get_block_root(state: BeaconState,
                   slot: Slot) -> Bytes32:
    """
    Return the block root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.latest_block_roots[slot % SLOTS_PER_HISTORICAL_ROOT]
def get_state_root(state: BeaconState,
                   slot: Slot) -> Bytes32:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.latest_state_roots[slot % SLOTS_PER_HISTORICAL_ROOT]
def get_randao_mix(state: BeaconState,
                   epoch: Epoch) -> Bytes32:
    """
    Return the randao mix at a recent ``epoch``.
    """
    assert get_current_epoch(state) - LATEST_RANDAO_MIXES_LENGTH < epoch <= get_current_epoch(state)
    return state.latest_randao_mixes[epoch % LATEST_RANDAO_MIXES_LENGTH]
def get_active_index_root(state: BeaconState,
                          epoch: Epoch) -> Bytes32:
    """
    Return the index root at a recent ``epoch``.
    """
    assert get_current_epoch(state) - LATEST_ACTIVE_INDEX_ROOTS_LENGTH + ACTIVATION_EXIT_DELAY < epoch <= get_current_epoch(state) + ACTIVATION_EXIT_DELAY
    return state.latest_active_index_roots[epoch % LATEST_ACTIVE_INDEX_ROOTS_LENGTH]
def generate_seed(state: BeaconState,
                  epoch: Epoch) -> Bytes32:
    """
    Generate a seed for the given ``epoch``.
    """
    return hash(
        get_randao_mix(state, epoch - MIN_SEED_LOOKAHEAD) +
        get_active_index_root(state, epoch) +
        int_to_bytes32(epoch)
    )
def get_beacon_proposer_index(state: BeaconState,
                              slot: Slot,
                              registry_change: bool=False) -> ValidatorIndex:
    """
    Return the beacon proposer index for the ``slot``.
    """
    epoch = slot_to_epoch(slot)
    current_epoch = get_current_epoch(state)
    previous_epoch = get_previous_epoch(state)
    next_epoch = current_epoch + 1

    assert previous_epoch <= epoch <= next_epoch

    first_committee, _ = get_crosslink_committees_at_slot(state, slot, registry_change)[0]
    return first_committee[epoch % len(first_committee)]
def verify_merkle_branch(leaf: Bytes32, proof: List[Bytes32], depth: int, index: int, root: Bytes32) -> bool:
    """
    Verify that the given ``leaf`` is on the merkle branch ``proof``
    starting with the given ``root``.
    """
    value = leaf
    for i in range(depth):
        if index // (2**i) % 2:
            value = hash(proof[i] + value)
        else:
            value = hash(value + proof[i])
    return value == root
def get_attestation_participants(state: BeaconState,
                                 attestation_data: AttestationData,
                                 bitfield: bytes) -> List[ValidatorIndex]:
    """
    Return the participant indices at for the ``attestation_data`` and ``bitfield``.
    """
    # Find the committee in the list with the desired shard
    crosslink_committees = get_crosslink_committees_at_slot(state, attestation_data.slot)

    assert attestation_data.shard in [shard for _, shard in crosslink_committees]
    crosslink_committee = [committee for committee, shard in crosslink_committees if shard == attestation_data.shard][0]

    assert verify_bitfield(bitfield, len(crosslink_committee))

    # Find the participating attesters in the committee
    participants = []
    for i, validator_index in enumerate(crosslink_committee):
        aggregation_bit = get_bitfield_bit(bitfield, i)
        if aggregation_bit == 0b1:
            participants.append(validator_index)
    return participants
def is_power_of_two(value: int) -> bool:
    """
    Check if ``value`` is a power of two integer.
    """
    return (value > 0) and (value & (value - 1) == 0)
def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, 'little')
def get_effective_balance(state: BeaconState, index: ValidatorIndex) -> Gwei:
    """
    Return the effective balance (also known as "balance at stake") for a validator with the given ``index``.
    """
    return min(state.validator_balances[index], MAX_DEPOSIT_AMOUNT)
def get_total_balance(state: BeaconState, validators: List[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of an array of ``validators``.
    """
    return sum([get_effective_balance(state, i) for i in validators])
def get_fork_version(fork: Fork,
                     epoch: Epoch) -> bytes:
    """
    Return the fork version of the given ``epoch``.
    """
    if epoch < fork.epoch:
        return fork.previous_version
    else:
        return fork.current_version
def get_domain(fork: Fork,
               epoch: Epoch,
               domain_type: int) -> int:
    """
    Get the domain number that represents the fork meta and signature domain.
    """
    return bytes_to_int(get_fork_version(fork, epoch) + int_to_bytes4(domain_type))
def get_bitfield_bit(bitfield: bytes, i: int) -> int:
    """
    Extract the bit in ``bitfield`` at position ``i``.
    """
    return (bitfield[i // 8] >> (i % 8)) % 2
def verify_bitfield(bitfield: bytes, committee_size: int) -> bool:
    """
    Verify ``bitfield`` against the ``committee_size``.
    """
    if len(bitfield) != (committee_size + 7) // 8:
        return False

    # Check `bitfield` is padded with zero bits only
    for i in range(committee_size, len(bitfield) * 8):
        if get_bitfield_bit(bitfield, i) == 0b1:
            return False

    return True
def verify_slashable_attestation(state: BeaconState, slashable_attestation: SlashableAttestation) -> bool:
    """
    Verify validity of ``slashable_attestation`` fields.
    """
    if slashable_attestation.custody_bitfield != b'\x00' * len(slashable_attestation.custody_bitfield):  # [TO BE REMOVED IN PHASE 1]
        return False

    if len(slashable_attestation.validator_indices) == 0:
        return False

    for i in range(len(slashable_attestation.validator_indices) - 1):
        if slashable_attestation.validator_indices[i] >= slashable_attestation.validator_indices[i + 1]:
            return False

    if not verify_bitfield(slashable_attestation.custody_bitfield, len(slashable_attestation.validator_indices)):
        return False

    if len(slashable_attestation.validator_indices) > MAX_INDICES_PER_SLASHABLE_VOTE:
        return False

    custody_bit_0_indices = []
    custody_bit_1_indices = []
    for i, validator_index in enumerate(slashable_attestation.validator_indices):
        if get_bitfield_bit(slashable_attestation.custody_bitfield, i) == 0b0:
            custody_bit_0_indices.append(validator_index)
        else:
            custody_bit_1_indices.append(validator_index)

    return bls_verify_multiple(
        pubkeys=[
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_0_indices]),
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_1_indices]),
        ],
        message_hashes=[
            hash_tree_root(AttestationDataAndCustodyBit(data=slashable_attestation.data, custody_bit=0b0)),
            hash_tree_root(AttestationDataAndCustodyBit(data=slashable_attestation.data, custody_bit=0b1)),
        ],
        signature=slashable_attestation.aggregate_signature,
        domain=get_domain(state.fork, slot_to_epoch(slashable_attestation.data.slot), DOMAIN_ATTESTATION),
    )
def is_double_vote(attestation_data_1: AttestationData,
                   attestation_data_2: AttestationData) -> bool:
    """
    Check if ``attestation_data_1`` and ``attestation_data_2`` have the same target.
    """
    target_epoch_1 = slot_to_epoch(attestation_data_1.slot)
    target_epoch_2 = slot_to_epoch(attestation_data_2.slot)
    return target_epoch_1 == target_epoch_2
def is_surround_vote(attestation_data_1: AttestationData,
                     attestation_data_2: AttestationData) -> bool:
    """
    Check if ``attestation_data_1`` surrounds ``attestation_data_2``.
    """
    source_epoch_1 = attestation_data_1.source_epoch
    source_epoch_2 = attestation_data_2.source_epoch
    target_epoch_1 = slot_to_epoch(attestation_data_1.slot)
    target_epoch_2 = slot_to_epoch(attestation_data_2.slot)

    return source_epoch_1 < source_epoch_2 and target_epoch_2 < target_epoch_1
def integer_squareroot(n: int) -> int:
    """
    The largest integer ``x`` such that ``x**2`` is less than or equal to ``n``.
    """
    assert n >= 0
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x
def get_delayed_activation_exit_epoch(epoch: Epoch) -> Epoch:
    """
    Return the epoch at which an activation or exit triggered in ``epoch`` takes effect.
    """
    return epoch + 1 + ACTIVATION_EXIT_DELAY
def process_deposit(state: BeaconState, deposit: Deposit) -> None:
    """
    Process a deposit from Ethereum 1.0.
    Note that this function mutates ``state``.
    """
    deposit_input = deposit.deposit_data.deposit_input

    # Should equal 8 bytes for deposit_data.amount +
    #              8 bytes for deposit_data.timestamp +
    #              176 bytes for deposit_data.deposit_input
    # It should match the deposit_data in the eth1.0 deposit contract
    serialized_deposit_data = serialize(deposit.deposit_data)
    # Deposits must be processed in order
    assert deposit.index == state.deposit_index

    # Verify the Merkle branch
    merkle_branch_is_valid = verify_merkle_branch(
        leaf=hash(serialized_deposit_data),
        proof=deposit.proof,
        depth=DEPOSIT_CONTRACT_TREE_DEPTH,
        index=deposit.index,
        root=state.latest_eth1_data.deposit_root,
    )
    assert merkle_branch_is_valid

    # Increment the next deposit index we are expecting. Note that this
    # needs to be done here because while the deposit contract will never
    # create an invalid Merkle branch, it may admit an invalid deposit
    # object, and we need to be able to skip over it
    state.deposit_index += 1

    validator_pubkeys = [v.pubkey for v in state.validator_registry]
    pubkey = deposit_input.pubkey
    amount = deposit.deposit_data.amount
    withdrawal_credentials = deposit_input.withdrawal_credentials

    if pubkey not in validator_pubkeys:
        # Verify the proof of possession
        proof_is_valid = bls_verify(
            pubkey=deposit_input.pubkey,
            message_hash=signed_root(deposit_input),
            signature=deposit_input.proof_of_possession,
            domain=get_domain(
                state.fork,
                get_current_epoch(state),
                DOMAIN_DEPOSIT,
            )
        )
        if not proof_is_valid:
            return

        # Add new validator
        validator = Validator(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
            initiated_exit=False,
            slashed=False,
        )

        # Note: In phase 2 registry indices that have been withdrawn for a long time will be recycled.
        state.validator_registry.append(validator)
        state.validator_balances.append(amount)
    else:
        # Increase balance by deposit amount
        state.validator_balances[validator_pubkeys.index(pubkey)] += amount
def activate_validator(state: BeaconState, index: ValidatorIndex, is_genesis: bool) -> None:
    """
    Activate the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]

    validator.activation_epoch = GENESIS_EPOCH if is_genesis else get_delayed_activation_exit_epoch(get_current_epoch(state))
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    validator.initiated_exit = True
def exit_validator(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Exit the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    delayed_activation_exit_epoch = get_delayed_activation_exit_epoch(get_current_epoch(state))

    # The following updates only occur if not previous exited
    if validator.exit_epoch <= delayed_activation_exit_epoch:
        return
    else:
        validator.exit_epoch = delayed_activation_exit_epoch
def slash_validator(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Slash the validator with index ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    assert state.slot < get_epoch_start_slot(validator.withdrawable_epoch)  # [TO BE REMOVED IN PHASE 2]
    exit_validator(state, index)
    state.latest_slashed_balances[get_current_epoch(state) % LATEST_SLASHED_EXIT_LENGTH] += get_effective_balance(state, index)

    whistleblower_index = get_beacon_proposer_index(state, state.slot)
    whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
    state.validator_balances[whistleblower_index] += whistleblower_reward
    state.validator_balances[index] -= whistleblower_reward
    validator.slashed = True
    validator.withdrawable_epoch = get_current_epoch(state) + LATEST_SLASHED_EXIT_LENGTH
def prepare_validator_for_withdrawal(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Set the validator with the given ``index`` as withdrawable
    ``MIN_VALIDATOR_WITHDRAWABILITY_DELAY`` after the current epoch.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    validator.withdrawable_epoch = get_current_epoch(state) + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
def get_empty_block() -> BeaconBlock:
    """
    Get an empty ``BeaconBlock``.
    """
    return BeaconBlock(
        slot=GENESIS_SLOT,
        previous_block_root=ZERO_HASH,
        state_root=ZERO_HASH,
        body=BeaconBlockBody(
            randao_reveal=EMPTY_SIGNATURE,
            eth1_data=Eth1Data(
                deposit_root=ZERO_HASH,
                block_hash=ZERO_HASH,
            ),
            proposer_slashings=[],
            attester_slashings=[],
            attestations=[],
            deposits=[],
            voluntary_exits=[],
            transfers=[],
        ),
        signature=EMPTY_SIGNATURE,
    )
def get_genesis_beacon_state(genesis_validator_deposits: List[Deposit],
                             genesis_time: int,
                             genesis_eth1_data: Eth1Data) -> BeaconState:
    """
    Get the genesis ``BeaconState``.
    """
    state = BeaconState(
        # Misc
        slot=GENESIS_SLOT,
        genesis_time=genesis_time,
        fork=Fork(
            previous_version=int_to_bytes4(GENESIS_FORK_VERSION),
            current_version=int_to_bytes4(GENESIS_FORK_VERSION),
            epoch=GENESIS_EPOCH,
        ),

        # Validator registry
        validator_registry=[],
        validator_balances=[],
        validator_registry_update_epoch=GENESIS_EPOCH,

        # Randomness and committees
        latest_randao_mixes=[ZERO_HASH for _ in range(LATEST_RANDAO_MIXES_LENGTH)],
        previous_shuffling_start_shard=GENESIS_START_SHARD,
        current_shuffling_start_shard=GENESIS_START_SHARD,
        previous_shuffling_epoch=GENESIS_EPOCH,
        current_shuffling_epoch=GENESIS_EPOCH,
        previous_shuffling_seed=ZERO_HASH,
        current_shuffling_seed=ZERO_HASH,

        # Finality
        previous_epoch_attestations=[],
        current_epoch_attestations=[],
        previous_justified_epoch=GENESIS_EPOCH,
        current_justified_epoch=GENESIS_EPOCH,
        previous_justified_root=ZERO_HASH,
        current_justified_root=ZERO_HASH,
        justification_bitfield=0,
        finalized_epoch=GENESIS_EPOCH,
        finalized_root=ZERO_HASH,

        # Recent state
        latest_crosslinks=[Crosslink(epoch=GENESIS_EPOCH, crosslink_data_root=ZERO_HASH) for _ in range(SHARD_COUNT)],
        latest_block_roots=[ZERO_HASH for _ in range(SLOTS_PER_HISTORICAL_ROOT)],
        latest_state_roots=[ZERO_HASH for _ in range(SLOTS_PER_HISTORICAL_ROOT)],
        latest_active_index_roots=[ZERO_HASH for _ in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH)],
        latest_slashed_balances=[0 for _ in range(LATEST_SLASHED_EXIT_LENGTH)],
        latest_block_header=get_temporary_block_header(get_empty_block()),
        historical_roots=[],

        # Ethereum 1.0 chain data
        latest_eth1_data=genesis_eth1_data,
        eth1_data_votes=[],
        deposit_index=0,
    )

    # Process genesis deposits
    for deposit in genesis_validator_deposits:
        process_deposit(state, deposit)

    # Process genesis activations
    for validator_index, _ in enumerate(state.validator_registry):
        if get_effective_balance(state, validator_index) >= MAX_DEPOSIT_AMOUNT:
            activate_validator(state, validator_index, is_genesis=True)

    genesis_active_index_root = hash_tree_root(get_active_validator_indices(state.validator_registry, GENESIS_EPOCH))
    for index in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH):
        state.latest_active_index_roots[index] = genesis_active_index_root
    state.current_shuffling_seed = generate_seed(state, GENESIS_EPOCH)

    return state
def get_ancestor(store: Store, block: BeaconBlock, slot: Slot) -> BeaconBlock:
    """
    Get the ancestor of ``block`` with slot number ``slot``; return ``None`` if not found.
    """
    if block.slot == slot:
        return block
    elif block.slot < slot:
        return None
    else:
        return get_ancestor(store, store.get_parent(block), slot)
def lmd_ghost(store: Store, start_state: BeaconState, start_block: BeaconBlock) -> BeaconBlock:
    """
    Execute the LMD-GHOST algorithm to find the head ``BeaconBlock``.
    """
    validators = start_state.validator_registry
    active_validator_indices = get_active_validator_indices(validators, slot_to_epoch(start_state.slot))
    attestation_targets = [
        (validator_index, get_latest_attestation_target(store, validator_index))
        for validator_index in active_validator_indices
    ]

    def get_vote_count(block: BeaconBlock) -> int:
        return sum(
            get_effective_balance(start_state.validator_balances[validator_index]) // FORK_CHOICE_BALANCE_INCREMENT
            for validator_index, target in attestation_targets
            if get_ancestor(store, target, block.slot) == block
        )

    head = start_block
    while 1:
        children = get_children(store, head)
        if len(children) == 0:
            return head
        head = max(children, key=lambda x: (get_vote_count(x), hash_tree_root(x)))
def cache_state(state: BeaconState) -> None:
    previous_slot_state_root = hash_tree_root(state)

    # store the previous slot's post state transition root
    state.latest_state_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_slot_state_root

    # cache state root in stored latest_block_header if empty
    if state.latest_block_header.state_root == ZERO_HASH:
        state.latest_block_header.state_root = previous_slot_state_root

    # store latest known block for previous slot
    state.latest_block_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = hash_tree_root(state.latest_block_header)
def get_current_total_balance(state: BeaconState) -> Gwei:
    return get_total_balance(state, get_active_validator_indices(state.validator_registry, get_current_epoch(state)))
def get_previous_total_balance(state: BeaconState) -> Gwei:
    return get_total_balance(state, get_active_validator_indices(state.validator_registry, get_previous_epoch(state)))
def get_attesting_indices(state: BeaconState, attestations: List[PendingAttestation]) -> List[ValidatorIndex]:
    output = set()
    for a in attestations:
        output = output.union(get_attestation_participants(state, a.data, a.aggregation_bitfield))
    return sorted(list(output))
def get_attesting_balance(state: BeaconState, attestations: List[PendingAttestation]) -> Gwei:
    return get_total_balance(state, get_attesting_indices(state, attestations))
def get_current_epoch_boundary_attestations(state: BeaconState) -> List[PendingAttestation]:
    return [
        a for a in state.current_epoch_attestations
        if a.data.target_root == get_block_root(state, get_epoch_start_slot(get_current_epoch(state)))
    ]
def get_previous_epoch_boundary_attestations(state: BeaconState) -> List[PendingAttestation]:
    return [
        a for a in state.previous_epoch_attestations
        if a.data.target_root == get_block_root(state, get_epoch_start_slot(get_previous_epoch(state)))
    ]
def get_previous_epoch_matching_head_attestations(state: BeaconState) -> List[PendingAttestation]:
    return [
        a for a in state.previous_epoch_attestations
        if a.data.beacon_block_root == get_block_root(state, a.data.slot)
    ]
def get_winning_root_and_participants(state: BeaconState, shard: Shard) -> Tuple[Bytes32, List[ValidatorIndex]]:
    all_attestations = state.current_epoch_attestations + state.previous_epoch_attestations
    valid_attestations = [
        a for a in all_attestations if a.data.previous_crosslink == state.latest_crosslinks[shard]
    ]
    all_roots = [a.data.crosslink_data_root for a in valid_attestations]

    # handle when no attestations for shard available
    if len(all_roots) == 0:
        return ZERO_HASH, []

    def get_attestations_for(root) -> List[PendingAttestation]:
        return [a for a in valid_attestations if a.data.crosslink_data_root == root]

    # Winning crosslink root is the root with the most votes for it, ties broken in favor of
    # lexicographically higher hash
    winning_root = max(all_roots, key=lambda r: (get_attesting_balance(state, get_attestations_for(r)), r))

    return winning_root, get_attesting_indices(state, get_attestations_for(winning_root))
def earliest_attestation(state: BeaconState, validator_index: ValidatorIndex) -> PendingAttestation:
    return min([
        a for a in state.previous_epoch_attestations if
        validator_index in get_attestation_participants(state, a.data, a.aggregation_bitfield)
    ], key=lambda a: a.inclusion_slot)
def inclusion_slot(state: BeaconState, validator_index: ValidatorIndex) -> Slot:
    return earliest_attestation(state, validator_index).inclusion_slot
def inclusion_distance(state: BeaconState, validator_index: ValidatorIndex) -> int:
    attestation = earliest_attestation(state, validator_index)
    return attestation.inclusion_slot - attestation.data.slot
def update_justification_and_finalization(state: BeaconState) -> None:
    new_justified_epoch = state.current_justified_epoch
    new_finalized_epoch = state.finalized_epoch

    # Rotate the justification bitfield up one epoch to make room for the current epoch
    state.justification_bitfield <<= 1
    # If the previous epoch gets justified, fill the second last bit
    previous_boundary_attesting_balance = get_attesting_balance(state, get_previous_epoch_boundary_attestations(state))
    if previous_boundary_attesting_balance * 3 >= get_previous_total_balance(state) * 2:
        new_justified_epoch = get_current_epoch(state) - 1
        state.justification_bitfield |= 2
    # If the current epoch gets justified, fill the last bit
    current_boundary_attesting_balance = get_attesting_balance(state, get_current_epoch_boundary_attestations(state))
    if current_boundary_attesting_balance * 3 >= get_current_total_balance(state) * 2:
        new_justified_epoch = get_current_epoch(state)
        state.justification_bitfield |= 1

    # Process finalizations
    bitfield = state.justification_bitfield
    current_epoch = get_current_epoch(state)
    # The 2nd/3rd/4th most recent epochs are all justified, the 2nd using the 4th as source
    if (bitfield >> 1) % 8 == 0b111 and state.previous_justified_epoch == current_epoch - 3:
        new_finalized_epoch = state.previous_justified_epoch
    # The 2nd/3rd most recent epochs are both justified, the 2nd using the 3rd as source
    if (bitfield >> 1) % 4 == 0b11 and state.previous_justified_epoch == current_epoch - 2:
        new_finalized_epoch = state.previous_justified_epoch
    # The 1st/2nd/3rd most recent epochs are all justified, the 1st using the 3rd as source
    if (bitfield >> 0) % 8 == 0b111 and state.current_justified_epoch == current_epoch - 2:
        new_finalized_epoch = state.current_justified_epoch
    # The 1st/2nd most recent epochs are both justified, the 1st using the 2nd as source
    if (bitfield >> 0) % 4 == 0b11 and state.current_justified_epoch == current_epoch - 1:
        new_finalized_epoch = state.current_justified_epoch

    # Update state jusification/finality fields
    state.previous_justified_epoch = state.current_justified_epoch
    state.previous_justified_root = state.current_justified_root
    if new_justified_epoch != state.current_justified_epoch:
        state.current_justified_epoch = new_justified_epoch
        state.current_justified_root = get_block_root(state, get_epoch_start_slot(new_justified_epoch))
    if new_finalized_epoch != state.finalized_epoch:
        state.finalized_epoch = new_finalized_epoch
        state.finalized_root = get_block_root(state, get_epoch_start_slot(new_finalized_epoch))
def process_crosslinks(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    previous_epoch = current_epoch - 1
    next_epoch = current_epoch + 1
    for slot in range(get_epoch_start_slot(previous_epoch), get_epoch_start_slot(next_epoch)):
        for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
            winning_root, participants = get_winning_root_and_participants(state, shard)
            participating_balance = get_total_balance(state, participants)
            total_balance = get_total_balance(state, crosslink_committee)
            if 3 * participating_balance >= 2 * total_balance:
                state.latest_crosslinks[shard] = Crosslink(
                    epoch=slot_to_epoch(slot),
                    crosslink_data_root=winning_root
                )
def maybe_reset_eth1_period(state: BeaconState) -> None:
    if (get_current_epoch(state) + 1) % EPOCHS_PER_ETH1_VOTING_PERIOD == 0:
        for eth1_data_vote in state.eth1_data_votes:
            # If a majority of all votes were for a particular eth1_data value,
            # then set that as the new canonical value
            if eth1_data_vote.vote_count * 2 > EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH:
                state.latest_eth1_data = eth1_data_vote.eth1_data
        state.eth1_data_votes = []
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    if get_previous_total_balance(state) == 0:
        return 0

    adjusted_quotient = integer_squareroot(get_previous_total_balance(state)) // BASE_REWARD_QUOTIENT
    return get_effective_balance(state, index) // adjusted_quotient // 5
def get_inactivity_penalty(state: BeaconState, index: ValidatorIndex, epochs_since_finality: int) -> Gwei:
    return (
        get_base_reward(state, index) +
        get_effective_balance(state, index) * epochs_since_finality // INACTIVITY_PENALTY_QUOTIENT // 2
    )
def get_justification_and_finalization_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    epochs_since_finality = get_current_epoch(state) + 1 - state.finalized_epoch
    if epochs_since_finality <= 4:
        return compute_normal_justification_and_finalization_deltas(state)
    else:
        return compute_inactivity_leak_deltas(state)
def compute_normal_justification_and_finalization_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    # deltas[0] for rewards
    # deltas[1] for penalties
    deltas = [
        [0 for index in range(len(state.validator_registry))],
        [0 for index in range(len(state.validator_registry))]
    ]
    # Some helper variables
    boundary_attestations = get_previous_epoch_boundary_attestations(state)
    boundary_attesting_balance = get_attesting_balance(state, boundary_attestations)
    total_balance = get_previous_total_balance(state)
    total_attesting_balance = get_attesting_balance(state, state.previous_epoch_attestations)
    matching_head_attestations = get_previous_epoch_matching_head_attestations(state)
    matching_head_balance = get_attesting_balance(state, matching_head_attestations)
    # Process rewards or penalties for all validators
    for index in get_active_validator_indices(state.validator_registry, get_previous_epoch(state)):
        # Expected FFG source
        if index in get_attesting_indices(state, state.previous_epoch_attestations):
            deltas[0][index] += get_base_reward(state, index) * total_attesting_balance // total_balance
            # Inclusion speed bonus
            deltas[0][index] += (
                get_base_reward(state, index) * MIN_ATTESTATION_INCLUSION_DELAY //
                inclusion_distance(state, index)
            )
        else:
            deltas[1][index] += get_base_reward(state, index)
        # Expected FFG target
        if index in get_attesting_indices(state, boundary_attestations):
            deltas[0][index] += get_base_reward(state, index) * boundary_attesting_balance // total_balance
        else:
            deltas[1][index] += get_base_reward(state, index)
        # Expected head
        if index in get_attesting_indices(state, matching_head_attestations):
            deltas[0][index] += get_base_reward(state, index) * matching_head_balance // total_balance
        else:
            deltas[1][index] += get_base_reward(state, index)
        # Proposer bonus
        if index in get_attesting_indices(state, state.previous_epoch_attestations):
            proposer_index = get_beacon_proposer_index(state, inclusion_slot(state, index))
            deltas[0][proposer_index] += get_base_reward(state, index) // ATTESTATION_INCLUSION_REWARD_QUOTIENT
    return deltas
def compute_inactivity_leak_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    # deltas[0] for rewards
    # deltas[1] for penalties
    deltas = [
        [0 for index in range(len(state.validator_registry))],
        [0 for index in range(len(state.validator_registry))]
    ]
    boundary_attestations = get_previous_epoch_boundary_attestations(state)
    matching_head_attestations = get_previous_epoch_matching_head_attestations(state)
    active_validator_indices = get_active_validator_indices(state.validator_registry, get_previous_epoch(state))
    epochs_since_finality = get_current_epoch(state) + 1 - state.finalized_epoch
    for index in active_validator_indices:
        if index not in get_attesting_indices(state, state.previous_epoch_attestations):
            deltas[1][index] += get_inactivity_penalty(state, index, epochs_since_finality)
        else:
            # If a validator did attest, apply a small penalty for getting attestations included late
            deltas[0][index] += (
                get_base_reward(state, index) * MIN_ATTESTATION_INCLUSION_DELAY //
                inclusion_distance(state, index)
            )
            deltas[1][index] += get_base_reward(state, index)
        if index not in get_attesting_indices(state, boundary_attestations):
            deltas[1][index] += get_inactivity_penalty(state, index, epochs_since_finality)
        if index not in get_attesting_indices(state, matching_head_attestations):
            deltas[1][index] += get_base_reward(state, index)
    # Penalize slashed-but-inactive validators as though they were active but offline
    for index in range(len(state.validator_registry)):
        eligible = (
            index not in active_validator_indices and
            state.validator_registry[index].slashed and
            get_current_epoch(state) < state.validator_registry[index].withdrawable_epoch
        )
        if eligible:
            deltas[1][index] += (
                2 * get_inactivity_penalty(state, index, epochs_since_finality) +
                get_base_reward(state, index)
            )
    return deltas
def get_crosslink_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    # deltas[0] for rewards
    # deltas[1] for penalties
    deltas = [
        [0 for index in range(len(state.validator_registry))],
        [0 for index in range(len(state.validator_registry))]
    ]
    previous_epoch_start_slot = get_epoch_start_slot(get_previous_epoch(state))
    current_epoch_start_slot = get_epoch_start_slot(get_current_epoch(state))
    for slot in range(previous_epoch_start_slot, current_epoch_start_slot):
        for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
            winning_root, participants = get_winning_root_and_participants(state, shard)
            participating_balance = get_total_balance(state, participants)
            total_balance = get_total_balance(state, crosslink_committee)
            for index in crosslink_committee:
                if index in participants:
                    deltas[0][index] += get_base_reward(state, index) * participating_balance // total_balance
                else:
                    deltas[1][index] += get_base_reward(state, index)
    return deltas
def apply_rewards(state: BeaconState) -> None:
    deltas1 = get_justification_and_finalization_deltas(state)
    deltas2 = get_crosslink_deltas(state)
    for i in range(len(state.validator_registry)):
        state.validator_balances[i] = max(
            0,
            state.validator_balances[i] + deltas1[0][i] + deltas2[0][i] - deltas1[1][i] - deltas2[1][i]
        )
def process_ejections(state: BeaconState) -> None:
    """
    Iterate through the validator registry
    and eject active validators with balance below ``EJECTION_BALANCE``.
    """
    for index in get_active_validator_indices(state.validator_registry, get_current_epoch(state)):
        if state.validator_balances[index] < EJECTION_BALANCE:
            exit_validator(state, index)
def should_update_validator_registry(state: BeaconState) -> bool:
    # Must have finalized a new block
    if state.finalized_epoch <= state.validator_registry_update_epoch:
        return False
    # Must have processed new crosslinks on all shards of the current epoch
    shards_to_check = [
        (state.current_shuffling_start_shard + i) % SHARD_COUNT
        for i in range(get_current_epoch_committee_count(state))
    ]
    for shard in shards_to_check:
        if state.latest_crosslinks[shard].epoch <= state.validator_registry_update_epoch:
            return False
    return True
def update_validator_registry(state: BeaconState) -> None:
    """
    Update validator registry.
    Note that this function mutates ``state``.
    """
    current_epoch = get_current_epoch(state)
    # The active validators
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    # The total effective balance of active validators
    total_balance = get_total_balance(state, active_validator_indices)

    # The maximum balance churn in Gwei (for deposits and exits separately)
    max_balance_churn = max(
        MAX_DEPOSIT_AMOUNT,
        total_balance // (2 * MAX_BALANCE_CHURN_QUOTIENT)
    )

    # Activate validators within the allowable balance churn
    balance_churn = 0
    for index, validator in enumerate(state.validator_registry):
        if validator.activation_epoch == FAR_FUTURE_EPOCH and state.validator_balances[index] >= MAX_DEPOSIT_AMOUNT:
            # Check the balance churn would be within the allowance
            balance_churn += get_effective_balance(state, index)
            if balance_churn > max_balance_churn:
                break

            # Activate validator
            activate_validator(state, index, is_genesis=False)

    # Exit validators within the allowable balance churn
    balance_churn = 0
    for index, validator in enumerate(state.validator_registry):
        if validator.exit_epoch == FAR_FUTURE_EPOCH and validator.initiated_exit:
            # Check the balance churn would be within the allowance
            balance_churn += get_effective_balance(state, index)
            if balance_churn > max_balance_churn:
                break

            # Exit validator
            exit_validator(state, index)

    state.validator_registry_update_epoch = current_epoch
def update_registry_and_shuffling_data(state: BeaconState) -> None:
    # First set previous shuffling data to current shuffling data
    state.previous_shuffling_epoch = state.current_shuffling_epoch
    state.previous_shuffling_start_shard = state.current_shuffling_start_shard
    state.previous_shuffling_seed = state.current_shuffling_seed
    current_epoch = get_current_epoch(state)
    next_epoch = current_epoch + 1
    # Check if we should update, and if so, update
    if should_update_validator_registry(state):
        update_validator_registry(state)
        # If we update the registry, update the shuffling data and shards as well
        state.current_shuffling_epoch = next_epoch
        state.current_shuffling_start_shard = (
            state.current_shuffling_start_shard +
            get_current_epoch_committee_count(state) % SHARD_COUNT
        )
        state.current_shuffling_seed = generate_seed(state, state.current_shuffling_epoch)
    else:
        # If processing at least one crosslink keeps failing, then reshuffle every power of two,
        # but don't update the current_shuffling_start_shard
        epochs_since_last_registry_update = current_epoch - state.validator_registry_update_epoch
        if epochs_since_last_registry_update > 1 and is_power_of_two(epochs_since_last_registry_update):
            state.current_shuffling_epoch = next_epoch
            state.current_shuffling_seed = generate_seed(state, state.current_shuffling_epoch)
def process_slashings(state: BeaconState) -> None:
    """
    Process the slashings.
    Note that this function mutates ``state``.
    """
    current_epoch = get_current_epoch(state)
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    total_balance = get_total_balance(state, active_validator_indices)

    # Compute `total_penalties`
    total_at_start = state.latest_slashed_balances[(current_epoch + 1) % LATEST_SLASHED_EXIT_LENGTH]
    total_at_end = state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
    total_penalties = total_at_end - total_at_start

    for index, validator in enumerate(state.validator_registry):
        if validator.slashed and current_epoch == validator.withdrawable_epoch - LATEST_SLASHED_EXIT_LENGTH // 2:
            penalty = max(
                get_effective_balance(state, index) * min(total_penalties * 3, total_balance) // total_balance,
                get_effective_balance(state, index) // MIN_PENALTY_QUOTIENT
            )
            state.validator_balances[index] -= penalty
def process_exit_queue(state: BeaconState) -> None:
    """
    Process the exit queue.
    Note that this function mutates ``state``.
    """
    def eligible(index):
        validator = state.validator_registry[index]
        # Filter out dequeued validators
        if validator.withdrawable_epoch != FAR_FUTURE_EPOCH:
            return False
        # Dequeue if the minimum amount of time has passed
        else:
            return get_current_epoch(state) >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY

    eligible_indices = filter(eligible, list(range(len(state.validator_registry))))
    # Sort in order of exit epoch, and validators that exit within the same epoch exit in order of validator index
    sorted_indices = sorted(eligible_indices, key=lambda index: state.validator_registry[index].exit_epoch)
    for dequeues, index in enumerate(sorted_indices):
        if dequeues >= MAX_EXIT_DEQUEUES_PER_EPOCH:
            break
        prepare_validator_for_withdrawal(state, index)
def finish_epoch_update(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    next_epoch = current_epoch + 1
    # Set active index root
    index_root_position = (next_epoch + ACTIVATION_EXIT_DELAY) % LATEST_ACTIVE_INDEX_ROOTS_LENGTH
    state.latest_active_index_roots[index_root_position] = hash_tree_root(
        get_active_validator_indices(state.validator_registry, next_epoch + ACTIVATION_EXIT_DELAY)
    )
    # Set total slashed balances
    state.latest_slashed_balances[next_epoch % LATEST_SLASHED_EXIT_LENGTH] = (
        state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
    )
    # Set randao mix
    state.latest_randao_mixes[next_epoch % LATEST_RANDAO_MIXES_LENGTH] = get_randao_mix(state, current_epoch)
    # Set historical root accumulator
    if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_batch = HistoricalBatch(
            block_roots=state.latest_block_roots,
            state_roots=state.latest_state_roots,
        )
        state.historical_roots.append(hash_tree_root(historical_batch))
    # Rotate current/previous epoch attestations
    state.previous_epoch_attestations = state.current_epoch_attestations
    state.current_epoch_attestations = []
def advance_slot(state: BeaconState) -> None:
    state.slot += 1
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the parent matches
    assert block.previous_block_root == hash_tree_root(state.latest_block_header)
    # Save current block as the new latest block
    state.latest_block_header = get_temporary_block_header(block)
    # Verify proposer signature
    proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]
    assert bls_verify(
        pubkey=proposer.pubkey,
        message_hash=signed_root(block),
        signature=block.signature,
        domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_BEACON_BLOCK)
    )
def process_randao(state: BeaconState, block: BeaconBlock) -> None:
    proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]
    # Verify that the provided randao value is valid
    assert bls_verify(
        pubkey=proposer.pubkey,
        message_hash=hash_tree_root(get_current_epoch(state)),
        signature=block.body.randao_reveal,
        domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_RANDAO)
    )
    # Mix it in
    state.latest_randao_mixes[get_current_epoch(state) % LATEST_RANDAO_MIXES_LENGTH] = (
        xor(get_randao_mix(state, get_current_epoch(state)),
            hash(block.body.randao_reveal))
    )
def process_eth1_data(state: BeaconState, block: BeaconBlock) -> None:
    for eth1_data_vote in state.eth1_data_votes:
        # If someone else has already voted for the same hash, add to its counter
        if eth1_data_vote.eth1_data == block.body.eth1_data:
            eth1_data_vote.vote_count += 1
            return
    # If we're seeing this hash for the first time, make a new counter
    state.eth1_data_votes.append(Eth1DataVote(eth1_data=block.body.eth1_data, vote_count=1))
def process_proposer_slashing(state: BeaconState,
                              proposer_slashing: ProposerSlashing) -> None:
    """
    Process ``ProposerSlashing`` transaction.
    Note that this function mutates ``state``.
    """
    proposer = state.validator_registry[proposer_slashing.proposer_index]
    # Verify that the epoch is the same
    assert slot_to_epoch(proposer_slashing.header_1.slot) == slot_to_epoch(proposer_slashing.header_2.slot)
    # But the headers are different
    assert proposer_slashing.header_1 != proposer_slashing.header_2
    # Proposer is not yet slashed
    assert proposer.slashed is False
    # Signatures are valid
    for header in (proposer_slashing.header_1, proposer_slashing.header_2):
        assert bls_verify(
            pubkey=proposer.pubkey,
            message_hash=signed_root(header),
            signature=header.signature,
            domain=get_domain(state.fork, slot_to_epoch(header.slot), DOMAIN_BEACON_BLOCK)
        )
    slash_validator(state, proposer_slashing.proposer_index)
def process_attester_slashing(state: BeaconState,
                              attester_slashing: AttesterSlashing) -> None:
    """
    Process ``AttesterSlashing`` transaction.
    Note that this function mutates ``state``.
    """
    attestation1 = attester_slashing.slashable_attestation_1
    attestation2 = attester_slashing.slashable_attestation_2
    # Check that the attestations are conflicting
    assert attestation1.data != attestation2.data
    assert (
        is_double_vote(attestation1.data, attestation2.data) or
        is_surround_vote(attestation1.data, attestation2.data)
    )
    assert verify_slashable_attestation(state, attestation1)
    assert verify_slashable_attestation(state, attestation2)
    slashable_indices = [
        index for index in attestation1.validator_indices
        if (
            index in attestation2.validator_indices and
            state.validator_registry[index].slashed is False
        )
    ]
    assert len(slashable_indices) >= 1
    for index in slashable_indices:
        slash_validator(state, index)
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    """
    Process ``Attestation`` transaction.
    Note that this function mutates ``state``.
    """
    # Can't submit attestations that are too far in history (or in prehistory)
    assert attestation.data.slot >= GENESIS_SLOT
    assert state.slot <= attestation.data.slot + SLOTS_PER_EPOCH
    # Can't submit attestations too quickly
    assert attestation.data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot
    # Verify that the justified epoch and root is correct
    if slot_to_epoch(attestation.data.slot) >= get_current_epoch(state):
        # Case 1: current epoch attestations
        assert attestation.data.source_epoch == state.current_justified_epoch
        assert attestation.data.source_root == state.current_justified_root
    else:
        # Case 2: previous epoch attestations
        assert attestation.data.source_epoch == state.previous_justified_epoch
        assert attestation.data.source_root == state.previous_justified_root
    # Check that the crosslink data is valid
    acceptable_crosslink_data = {
        # Case 1: Latest crosslink matches the one in the state
        attestation.data.previous_crosslink,
        # Case 2: State has already been updated, state's latest crosslink matches the crosslink
        # the attestation is trying to create
        Crosslink(
            crosslink_data_root=attestation.data.crosslink_data_root,
            epoch=slot_to_epoch(attestation.data.slot)
        )
    }
    assert state.latest_crosslinks[attestation.data.shard] in acceptable_crosslink_data
    # Attestation must be nonempty!
    assert attestation.aggregation_bitfield != b'\x00' * len(attestation.aggregation_bitfield)
    # Custody must be empty (to be removed in phase 1)
    assert attestation.custody_bitfield == b'\x00' * len(attestation.custody_bitfield)
    # Get the committee for the specific shard that this attestation is for
    crosslink_committee = [
        committee for committee, shard in get_crosslink_committees_at_slot(state, attestation.data.slot)
        if shard == attestation.data.shard
    ][0]
    # Custody bitfield must be a subset of the attestation bitfield
    for i in range(len(crosslink_committee)):
        if get_bitfield_bit(attestation.aggregation_bitfield, i) == 0b0:
            assert get_bitfield_bit(attestation.custody_bitfield, i) == 0b0
    # Verify aggregate signature
    participants = get_attestation_participants(state, attestation.data, attestation.aggregation_bitfield)
    custody_bit_1_participants = get_attestation_participants(state, attestation.data, attestation.custody_bitfield)
    custody_bit_0_participants = [i for i in participants if i not in custody_bit_1_participants]

    assert bls_verify_multiple(
        pubkeys=[
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_0_participants]),
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_1_participants]),
        ],
        message_hashes=[
            hash_tree_root(AttestationDataAndCustodyBit(data=attestation.data, custody_bit=0b0)),
            hash_tree_root(AttestationDataAndCustodyBit(data=attestation.data, custody_bit=0b1)),
        ],
        signature=attestation.aggregate_signature,
        domain=get_domain(state.fork, slot_to_epoch(attestation.data.slot), DOMAIN_ATTESTATION),
    )
    # Crosslink data root is zero (to be removed in phase 1)
    assert attestation.data.crosslink_data_root == ZERO_HASH
    # Apply the attestation
    pending_attestation = PendingAttestation(
        data=attestation.data,
        aggregation_bitfield=attestation.aggregation_bitfield,
        custody_bitfield=attestation.custody_bitfield,
        inclusion_slot=state.slot
    )
    if slot_to_epoch(attestation.data.slot) == get_current_epoch(state):
        state.current_epoch_attestations.append(pending_attestation)
    elif slot_to_epoch(attestation.data.slot) == get_previous_epoch(state):
        state.previous_epoch_attestations.append(pending_attestation)
def process_voluntary_exit(state: BeaconState, exit: VoluntaryExit) -> None:
    """
    Process ``VoluntaryExit`` transaction.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[exit.validator_index]
    # Verify the validator has not yet exited
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Verify the validator has not initiated an exit
    assert validator.initiated_exit is False
    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= exit.epoch
    # Must have been in the validator set long enough
    assert get_current_epoch(state) - validator.activation_epoch >= PERSISTENT_COMMITTEE_PERIOD
    # Verify signature
    assert bls_verify(
        pubkey=validator.pubkey,
        message_hash=signed_root(exit),
        signature=exit.signature,
        domain=get_domain(state.fork, exit.epoch, DOMAIN_VOLUNTARY_EXIT)
    )
    # Run the exit
    initiate_validator_exit(state, exit.validator_index)
def process_transfer(state: BeaconState, transfer: Transfer) -> None:
    """
    Process ``Transfer`` transaction.
    Note that this function mutates ``state``.
    """
    # Verify the amount and fee aren't individually too big (for anti-overflow purposes)
    assert state.validator_balances[transfer.sender] >= max(transfer.amount, transfer.fee)
    # Verify that we have enough ETH to send, and that after the transfer the balance will be either
    # exactly zero or at least MIN_DEPOSIT_AMOUNT
    assert (
        state.validator_balances[transfer.sender] == transfer.amount + transfer.fee or
        state.validator_balances[transfer.sender] >= transfer.amount + transfer.fee + MIN_DEPOSIT_AMOUNT
    )
    # A transfer is valid in only one slot
    assert state.slot == transfer.slot
    # Only withdrawn or not-yet-deposited accounts can transfer
    assert (
        get_current_epoch(state) >= state.validator_registry[transfer.sender].withdrawable_epoch or
        state.validator_registry[transfer.sender].activation_epoch == FAR_FUTURE_EPOCH
    )
    # Verify that the pubkey is valid
    assert (
        state.validator_registry[transfer.sender].withdrawal_credentials ==
        BLS_WITHDRAWAL_PREFIX_BYTE + hash(transfer.pubkey)[1:]
    )
    # Verify that the signature is valid
    assert bls_verify(
        pubkey=transfer.pubkey,
        message_hash=signed_root(transfer),
        signature=transfer.signature,
        domain=get_domain(state.fork, slot_to_epoch(transfer.slot), DOMAIN_TRANSFER)
    )
    # Process the transfer
    state.validator_balances[transfer.sender] -= transfer.amount + transfer.fee
    state.validator_balances[transfer.recipient] += transfer.amount
    state.validator_balances[get_beacon_proposer_index(state, state.slot)] += transfer.fee
def verify_block_state_root(state: BeaconState, block: BeaconBlock) -> None:
    assert block.state_root == hash_tree_root(state)

# Monkey patch validator shuffling cache
_get_shuffling = get_shuffling
shuffling_cache = {}
def get_shuffling(seed: Bytes32,
                  validators: List[Validator],
                  epoch: Epoch) -> List[List[ValidatorIndex]]:

    param_hash = (seed, hash_tree_root(validators, [Validator]), epoch)

    if param_hash in shuffling_cache:
        # print("Cache hit, epoch={0}".format(epoch))
        return shuffling_cache[param_hash]
    else:
        # print("Cache miss, epoch={0}".format(epoch))
        ret = _get_shuffling(seed, validators, epoch)
        shuffling_cache[param_hash] = ret
        return ret


# Monkey patch hash cache
_hash = hash
hash_cache = {}
def hash(x):
    if x in hash_cache:
        return hash_cache[x]
    else:
        ret = _hash(x)
        hash_cache[x] = ret
        return ret
    