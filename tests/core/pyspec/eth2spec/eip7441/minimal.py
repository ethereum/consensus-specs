import json
from collections.abc import Callable, Sequence
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any,
    Final,
    NamedTuple,
    Protocol,
    TypeVar,
)

import curdleproofs
from lru import LRU

from eth2spec.altair import minimal as altair
from eth2spec.bellatrix import minimal as bellatrix
from eth2spec.capella import minimal as capella
from eth2spec.phase0 import minimal as phase0
from eth2spec.test.helpers.merkle import build_proof
from eth2spec.utils import bls
from eth2spec.utils.hash_function import hash
from eth2spec.utils.ssz.ssz_impl import copy, hash_tree_root, uint_to_bytes
from eth2spec.utils.ssz.ssz_typing import (
    Bitlist,
    Bitvector,  # noqa: F401
    boolean,
    ByteList,
    Bytes1,
    Bytes4,
    Bytes8,
    Bytes20,
    Bytes32,
    Bytes48,
    Bytes96,
    ByteVector,
    Container,
    List,
    Path,
    uint8,
    uint32,
    uint64,
    uint256,
    Vector,
    View,
)

SSZObject = TypeVar("SSZObject", bound=View)


SSZVariableName = str
GeneralizedIndex = int


fork = "eip7441"


def ceillog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"ceillog2 accepts only positive values, x={x}")
    return uint64((x - 1).bit_length())


def floorlog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"floorlog2 accepts only positive values, x={x}")
    return uint64(x.bit_length() - 1)


FINALIZED_ROOT_GINDEX = GeneralizedIndex(105)
CURRENT_SYNC_COMMITTEE_GINDEX = GeneralizedIndex(54)
NEXT_SYNC_COMMITTEE_GINDEX = GeneralizedIndex(55)
EXECUTION_PAYLOAD_GINDEX = GeneralizedIndex(41)


class Slot(uint64):
    pass


class Epoch(uint64):
    pass


class Gwei(uint64):
    pass


class Hash32(Bytes32):
    pass


class Version(Bytes4):
    pass


class DomainType(Bytes4):
    pass


class BLSSignature(Bytes96):
    pass


class FinalityBranch(
    Vector[Bytes32, floorlog2(FINALIZED_ROOT_GINDEX)]  # type: ignore
):
    pass


class BLSG1Point(Bytes48):
    pass


# Constant vars
UINT64_MAX = uint64(2**64 - 1)
UINT64_MAX_SQRT = uint64(4294967295)
GENESIS_SLOT = Slot(0)
GENESIS_EPOCH = Epoch(0)
FAR_FUTURE_EPOCH = Epoch(2**64 - 1)
BASE_REWARDS_PER_EPOCH = uint64(4)
DEPOSIT_CONTRACT_TREE_DEPTH = uint64(2**5)
JUSTIFICATION_BITS_LENGTH = uint64(4)
ENDIANNESS: Final = "little"
BLS_WITHDRAWAL_PREFIX = Bytes1("0x00")
ETH1_ADDRESS_WITHDRAWAL_PREFIX = Bytes1("0x01")
DOMAIN_BEACON_PROPOSER = DomainType("0x00000000")
DOMAIN_BEACON_ATTESTER = DomainType("0x01000000")
DOMAIN_RANDAO = DomainType("0x02000000")
DOMAIN_DEPOSIT = DomainType("0x03000000")
DOMAIN_VOLUNTARY_EXIT = DomainType("0x04000000")
DOMAIN_SELECTION_PROOF = DomainType("0x05000000")
DOMAIN_AGGREGATE_AND_PROOF = DomainType("0x06000000")
DOMAIN_APPLICATION_MASK = DomainType("0x00000001")
INTERVALS_PER_SLOT = uint64(3)
BASIS_POINTS = uint64(10000)
NODE_ID_BITS = 256
MAX_CONCURRENT_REQUESTS = 2
TARGET_AGGREGATORS_PER_COMMITTEE = 2**4
ETH_TO_GWEI = uint64(10**9)
SAFETY_DECAY = uint64(10)
TIMELY_SOURCE_FLAG_INDEX = 0
TIMELY_TARGET_FLAG_INDEX = 1
TIMELY_HEAD_FLAG_INDEX = 2
TIMELY_SOURCE_WEIGHT = uint64(14)
TIMELY_TARGET_WEIGHT = uint64(26)
TIMELY_HEAD_WEIGHT = uint64(14)
SYNC_REWARD_WEIGHT = uint64(2)
PROPOSER_WEIGHT = uint64(8)
WEIGHT_DENOMINATOR = uint64(64)
DOMAIN_SYNC_COMMITTEE = DomainType("0x07000000")
DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF = DomainType("0x08000000")
DOMAIN_CONTRIBUTION_AND_PROOF = DomainType("0x09000000")
PARTICIPATION_FLAG_WEIGHTS = [TIMELY_SOURCE_WEIGHT, TIMELY_TARGET_WEIGHT, TIMELY_HEAD_WEIGHT]
G2_POINT_AT_INFINITY = BLSSignature(b"\xc0" + b"\x00" * 95)
TARGET_AGGREGATORS_PER_SYNC_SUBCOMMITTEE = 2**4
SYNC_COMMITTEE_SUBNET_COUNT = 4
MAX_REQUEST_LIGHT_CLIENT_UPDATES = 2**7
SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY = 128
DOMAIN_BLS_TO_EXECUTION_CHANGE = DomainType("0x0A000000")
DOMAIN_CANDIDATE_SELECTION = DomainType("0x07000000")
DOMAIN_SHUFFLE = DomainType("0x07100000")
DOMAIN_PROPOSER_SELECTION = DomainType("0x07200000")
BLS_G1_GENERATOR = BLSG1Point(
    "0x97f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb"
)
BLS_MODULUS = 52435875175126190479447740508185965837690552500527637822603658699938581184513
CURDLEPROOFS_CRS = curdleproofs.CurdleproofsCrs.from_json(
    json.dumps(
        {
            "vec_G": [
                "a44aae199242e24a4d00b8e5c96e318793eeeb2e154423ca6dcac20043387323dea3216a69bc13e9a3507ff842da544d",
                "8dff68d38281daa552c587d073e498d1ed311986967192cba052827b07f194a936809ea3de921511db45d15234754993",
                "ad0ff210542fc069d065b53b2cd4228a0f097facebe089a83b989fd3344c53e440ded5da26bc6115299d9d464e1a9f28",
                "b638e703f852d2ac49595141f7688c52a95dcc0b00f82a8548b14d823ebffe8657557ed7dab6bee44b17d39d742f69aa",
            ],
            "vec_H": [
                "9377c7771e07a1a9b9368796ce1a1b93d560d7726afde02627b424ee1dcddb3761ed49f2e1ae5279dca050935bd4a6dd",
                "8d1be282936392c0c61c94745cfb29da0f3334272c9b37fe43c8b869640eb1ea88c8aaf5ff797bd90daf3d6ebeb4efb3",
                "b3b55847d3bcf98b587c4441b0703939b5984bac91b00aabb5f3a45b38445405b61127bc6ee9f6b4b9e88c7a29c3aaa3",
                "afb61afb9f92c37ec21220c02edf14876d2a08eab8ad3c2bc1f3bfe5036abfd23a4a7216616fa1953e14340bf0acab37",
            ],
            "H": "a94133ee96e00465fe5423e0ea52404e0f624ee8cc9d69b4cf94e7d73635dfa2087cd2d2596ac4a75504aac5ef6a02d4",
            "G_t": "a4b93e670e7ee926ffb4ea4e07b87346e5d33c76520912f8a7937cdc3290a4c054586e175c39826b7fafbe777d14e4f4",
            "G_u": "a57540f7c906d9e70ef90580967562f8c06398ac2d77612045dce0ea6fbc2fedcfdbeb3f6ad3bb717e1295d9539ede63",
            "G_sum": "a0d97028d7194094fe1c4f00189e360ae362eca4aa9dc8f92eabb8dcf0d93140a81953d4505cd7dc592504710d696ef9",
            "H_sum": "af415fddfb82e7cbb91fae0c443425c51dbb68e05f0324bd2d79e40b923ecb4f806e96e9993eabadd1c39ac4e12e74bf",
        }
    )
)  # noqa: E501


# Preset vars
MAX_COMMITTEES_PER_SLOT = uint64(4)
TARGET_COMMITTEE_SIZE = uint64(4)
MAX_VALIDATORS_PER_COMMITTEE = uint64(2048)
SHUFFLE_ROUND_COUNT = uint64(10)
HYSTERESIS_QUOTIENT = uint64(4)
HYSTERESIS_DOWNWARD_MULTIPLIER = uint64(1)
HYSTERESIS_UPWARD_MULTIPLIER = uint64(5)
MIN_DEPOSIT_AMOUNT = Gwei(1000000000)
MAX_EFFECTIVE_BALANCE = Gwei(32000000000)
EFFECTIVE_BALANCE_INCREMENT = Gwei(1000000000)
MIN_ATTESTATION_INCLUSION_DELAY = uint64(1)
SLOTS_PER_EPOCH = uint64(8)
MIN_SEED_LOOKAHEAD = uint64(1)
MAX_SEED_LOOKAHEAD = uint64(4)
MIN_EPOCHS_TO_INACTIVITY_PENALTY = uint64(4)
EPOCHS_PER_ETH1_VOTING_PERIOD = uint64(4)
SLOTS_PER_HISTORICAL_ROOT = uint64(64)
EPOCHS_PER_HISTORICAL_VECTOR = uint64(64)
EPOCHS_PER_SLASHINGS_VECTOR = uint64(64)
HISTORICAL_ROOTS_LIMIT = uint64(16777216)
VALIDATOR_REGISTRY_LIMIT = uint64(1099511627776)
BASE_REWARD_FACTOR = uint64(64)
WHISTLEBLOWER_REWARD_QUOTIENT = uint64(512)
PROPOSER_REWARD_QUOTIENT = uint64(8)
INACTIVITY_PENALTY_QUOTIENT = uint64(33554432)
MIN_SLASHING_PENALTY_QUOTIENT = uint64(64)
PROPORTIONAL_SLASHING_MULTIPLIER = uint64(2)
MAX_PROPOSER_SLASHINGS = 16
MAX_ATTESTER_SLASHINGS = 2
MAX_ATTESTATIONS = 128
MAX_DEPOSITS = 16
MAX_VOLUNTARY_EXITS = 16
INACTIVITY_PENALTY_QUOTIENT_ALTAIR = uint64(50331648)
MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR = uint64(64)
PROPORTIONAL_SLASHING_MULTIPLIER_ALTAIR = uint64(2)
SYNC_COMMITTEE_SIZE = uint64(32)
EPOCHS_PER_SYNC_COMMITTEE_PERIOD = uint64(8)
MIN_SYNC_COMMITTEE_PARTICIPANTS = 1
UPDATE_TIMEOUT = 64
INACTIVITY_PENALTY_QUOTIENT_BELLATRIX = uint64(16777216)
MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX = uint64(32)
PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX = uint64(3)
MAX_BYTES_PER_TRANSACTION = uint64(1073741824)
MAX_TRANSACTIONS_PER_PAYLOAD = uint64(1048576)
BYTES_PER_LOGS_BLOOM = uint64(256)
MAX_EXTRA_DATA_BYTES = 32
MAX_BLS_TO_EXECUTION_CHANGES = 16
MAX_WITHDRAWALS_PER_PAYLOAD = uint64(4)
MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP = 16
CURDLEPROOFS_N_BLINDERS = uint64(4)
CANDIDATE_TRACKERS_COUNT = uint64(32)
PROPOSER_TRACKERS_COUNT = uint64(16)
VALIDATORS_PER_SHUFFLE = uint64(4)
MAX_SHUFFLE_PROOF_SIZE = uint64(32768)
MAX_OPENING_PROOF_SIZE = uint64(1024)


# Preset computed constants


class Configuration(NamedTuple):
    PRESET_BASE: str
    MIN_GENESIS_ACTIVE_VALIDATOR_COUNT: uint64
    MIN_GENESIS_TIME: uint64
    GENESIS_FORK_VERSION: Version
    GENESIS_DELAY: uint64
    SECONDS_PER_SLOT: uint64
    SLOT_DURATION_MS: uint64
    SECONDS_PER_ETH1_BLOCK: uint64
    MIN_VALIDATOR_WITHDRAWABILITY_DELAY: uint64
    SHARD_COMMITTEE_PERIOD: uint64
    ETH1_FOLLOW_DISTANCE: uint64
    EJECTION_BALANCE: Gwei
    MIN_PER_EPOCH_CHURN_LIMIT: uint64
    CHURN_LIMIT_QUOTIENT: uint64
    PROPOSER_SCORE_BOOST: uint64
    REORG_HEAD_WEIGHT_THRESHOLD: uint64
    REORG_PARENT_WEIGHT_THRESHOLD: uint64
    REORG_MAX_EPOCHS_SINCE_FINALIZATION: Epoch
    PROPOSER_REORG_CUTOFF_BPS: uint64
    MAX_PAYLOAD_SIZE: int
    MAX_REQUEST_BLOCKS: int
    EPOCHS_PER_SUBNET_SUBSCRIPTION: int
    MIN_EPOCHS_FOR_BLOCK_REQUESTS: int
    ATTESTATION_PROPAGATION_SLOT_RANGE: int
    MAXIMUM_GOSSIP_CLOCK_DISPARITY: int
    MESSAGE_DOMAIN_INVALID_SNAPPY: DomainType
    MESSAGE_DOMAIN_VALID_SNAPPY: DomainType
    SUBNETS_PER_NODE: int
    ATTESTATION_SUBNET_COUNT: int
    ATTESTATION_SUBNET_EXTRA_BITS: int
    ATTESTATION_SUBNET_PREFIX_BITS: int
    ATTESTATION_DUE_BPS: uint64
    AGGREGATE_DUE_BPS: uint64
    INACTIVITY_SCORE_BIAS: uint64
    INACTIVITY_SCORE_RECOVERY_RATE: uint64
    ALTAIR_FORK_VERSION: Version
    ALTAIR_FORK_EPOCH: Epoch
    SYNC_MESSAGE_DUE_BPS: uint64
    CONTRIBUTION_DUE_BPS: uint64
    TERMINAL_TOTAL_DIFFICULTY: int
    TERMINAL_BLOCK_HASH: Hash32
    TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH: int
    BELLATRIX_FORK_VERSION: Version
    BELLATRIX_FORK_EPOCH: Epoch
    CAPELLA_FORK_VERSION: Version
    CAPELLA_FORK_EPOCH: Epoch
    EPOCHS_PER_SHUFFLING_PHASE: Epoch
    PROPOSER_SELECTION_GAP: Epoch
    EIP7441_FORK_VERSION: Version
    EIP7441_FORK_EPOCH: Epoch


config = Configuration(
    PRESET_BASE="minimal",
    MIN_GENESIS_ACTIVE_VALIDATOR_COUNT=uint64(64),
    MIN_GENESIS_TIME=uint64(1578009600),
    GENESIS_FORK_VERSION=Version("0x00000001"),
    GENESIS_DELAY=uint64(300),
    SECONDS_PER_SLOT=uint64(6),
    SLOT_DURATION_MS=uint64(6000),
    SECONDS_PER_ETH1_BLOCK=uint64(14),
    MIN_VALIDATOR_WITHDRAWABILITY_DELAY=uint64(256),
    SHARD_COMMITTEE_PERIOD=uint64(64),
    ETH1_FOLLOW_DISTANCE=uint64(16),
    EJECTION_BALANCE=Gwei(16000000000),
    MIN_PER_EPOCH_CHURN_LIMIT=uint64(2),
    CHURN_LIMIT_QUOTIENT=uint64(32),
    PROPOSER_SCORE_BOOST=uint64(40),
    REORG_HEAD_WEIGHT_THRESHOLD=uint64(20),
    REORG_PARENT_WEIGHT_THRESHOLD=uint64(160),
    REORG_MAX_EPOCHS_SINCE_FINALIZATION=Epoch(2),
    PROPOSER_REORG_CUTOFF_BPS=uint64(1667),
    MAX_PAYLOAD_SIZE=10485760,
    MAX_REQUEST_BLOCKS=1024,
    EPOCHS_PER_SUBNET_SUBSCRIPTION=256,
    MIN_EPOCHS_FOR_BLOCK_REQUESTS=272,
    ATTESTATION_PROPAGATION_SLOT_RANGE=32,
    MAXIMUM_GOSSIP_CLOCK_DISPARITY=500,
    MESSAGE_DOMAIN_INVALID_SNAPPY=DomainType("0x00000000"),
    MESSAGE_DOMAIN_VALID_SNAPPY=DomainType("0x01000000"),
    SUBNETS_PER_NODE=2,
    ATTESTATION_SUBNET_COUNT=64,
    ATTESTATION_SUBNET_EXTRA_BITS=0,
    ATTESTATION_SUBNET_PREFIX_BITS=6,
    ATTESTATION_DUE_BPS=uint64(3333),
    AGGREGATE_DUE_BPS=uint64(6667),
    INACTIVITY_SCORE_BIAS=uint64(4),
    INACTIVITY_SCORE_RECOVERY_RATE=uint64(16),
    ALTAIR_FORK_VERSION=Version("0x01000001"),
    ALTAIR_FORK_EPOCH=Epoch(18446744073709551615),
    SYNC_MESSAGE_DUE_BPS=uint64(3333),
    CONTRIBUTION_DUE_BPS=uint64(6667),
    TERMINAL_TOTAL_DIFFICULTY=115792089237316195423570985008687907853269984665640564039457584007913129638912,
    TERMINAL_BLOCK_HASH=Hash32(
        "0x0000000000000000000000000000000000000000000000000000000000000000"
    ),
    TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH=18446744073709551615,
    BELLATRIX_FORK_VERSION=Version("0x02000001"),
    BELLATRIX_FORK_EPOCH=Epoch(18446744073709551615),
    CAPELLA_FORK_VERSION=Version("0x03000001"),
    CAPELLA_FORK_EPOCH=Epoch(18446744073709551615),
    EPOCHS_PER_SHUFFLING_PHASE=Epoch(4),
    PROPOSER_SELECTION_GAP=Epoch(1),
    EIP7441_FORK_VERSION=Version("0x08000001"),
    EIP7441_FORK_EPOCH=Epoch(18446744073709551615),
)


class Fork(Container):
    previous_version: Version
    current_version: Version
    epoch: Epoch


class SyncAggregate(Container):
    sync_committee_bits: Bitvector[SYNC_COMMITTEE_SIZE]
    sync_committee_signature: BLSSignature


class SyncAggregatorSelectionData(Container):
    slot: Slot
    subcommittee_index: uint64


class PowBlock(Container):
    block_hash: Hash32
    parent_hash: Hash32
    total_difficulty: uint256


class WhiskTracker(Container):
    r_G: BLSG1Point
    k_r_G: BLSG1Point


class CommitteeIndex(uint64):
    pass


class ValidatorIndex(uint64):
    pass


class VoluntaryExit(Container):
    epoch: Epoch
    validator_index: ValidatorIndex


class SignedVoluntaryExit(Container):
    message: VoluntaryExit
    signature: BLSSignature


class Root(Bytes32):
    pass


class HistoricalSummary(Container):
    block_summary_root: Root
    state_summary_root: Root


class SyncCommitteeContribution(Container):
    slot: Slot
    beacon_block_root: Root
    subcommittee_index: uint64
    aggregation_bits: Bitvector[SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT]
    signature: BLSSignature


class ContributionAndProof(Container):
    aggregator_index: ValidatorIndex
    contribution: SyncCommitteeContribution
    selection_proof: BLSSignature


class SignedContributionAndProof(Container):
    message: ContributionAndProof
    signature: BLSSignature


class SyncCommitteeMessage(Container):
    slot: Slot
    beacon_block_root: Root
    validator_index: ValidatorIndex
    signature: BLSSignature


class Eth1Block(Container):
    timestamp: uint64
    deposit_root: Root
    deposit_count: uint64


class BeaconBlockHeader(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body_root: Root


class SignedBeaconBlockHeader(Container):
    message: BeaconBlockHeader
    signature: BLSSignature


class ProposerSlashing(Container):
    signed_header_1: SignedBeaconBlockHeader
    signed_header_2: SignedBeaconBlockHeader


class HistoricalBatch(Container):
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]


class Eth1Data(Container):
    deposit_root: Root
    deposit_count: uint64
    block_hash: Hash32


class Checkpoint(Container):
    epoch: Epoch
    root: Root


class AttestationData(Container):
    slot: Slot
    index: CommitteeIndex
    beacon_block_root: Root
    source: Checkpoint
    target: Checkpoint


class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    signature: BLSSignature


class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation
    selection_proof: BLSSignature


class SignedAggregateAndProof(Container):
    message: AggregateAndProof
    signature: BLSSignature


class PendingAttestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    inclusion_delay: Slot
    proposer_index: ValidatorIndex


class IndexedAttestation(Container):
    attesting_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    signature: BLSSignature


class AttesterSlashing(Container):
    attestation_1: IndexedAttestation
    attestation_2: IndexedAttestation


class ForkData(Container):
    current_version: Version
    genesis_validators_root: Root


class ForkDigest(Bytes4):
    pass


class Domain(Bytes32):
    pass


class SigningData(Container):
    object_root: Root
    domain: Domain


class BLSPubkey(Bytes48):
    pass


class SyncCommittee(Container):
    pubkeys: Vector[BLSPubkey, SYNC_COMMITTEE_SIZE]
    aggregate_pubkey: BLSPubkey


class DepositData(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    signature: BLSSignature


class Deposit(Container):
    proof: Vector[Bytes32, DEPOSIT_CONTRACT_TREE_DEPTH + 1]
    data: DepositData


class DepositMessage(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei


class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    effective_balance: Gwei
    slashed: boolean
    activation_eligibility_epoch: Epoch
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch


class NodeID(uint256):
    pass


class SubnetID(uint64):
    pass


class Ether(uint64):
    pass


class ParticipationFlags(uint8):
    pass


class CurrentSyncCommitteeBranch(
    Vector[Bytes32, floorlog2(CURRENT_SYNC_COMMITTEE_GINDEX)]  # type: ignore
):
    pass


class NextSyncCommitteeBranch(
    Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_GINDEX)]  # type: ignore
):
    pass


class Transaction(ByteList[MAX_BYTES_PER_TRANSACTION]):
    pass


class ExecutionAddress(Bytes20):
    pass


class BLSToExecutionChange(Container):
    validator_index: ValidatorIndex
    from_bls_pubkey: BLSPubkey
    to_execution_address: ExecutionAddress


class SignedBLSToExecutionChange(Container):
    message: BLSToExecutionChange
    signature: BLSSignature


class ExecutionPayloadHeader(Container):
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    block_hash: Hash32
    transactions_root: Root
    # [New in Capella]
    withdrawals_root: Root


class PayloadId(Bytes8):
    pass


class WithdrawalIndex(uint64):
    pass


class Withdrawal(Container):
    index: WithdrawalIndex
    validator_index: ValidatorIndex
    address: ExecutionAddress
    amount: Gwei


class ExecutionPayload(Container):
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    # [New in Capella]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]


class BeaconState(Container):
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_execution_payload_header: ExecutionPayloadHeader
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    # [New in EIP7441]
    whisk_candidate_trackers: Vector[WhiskTracker, CANDIDATE_TRACKERS_COUNT]
    # [New in EIP7441]
    whisk_proposer_trackers: Vector[WhiskTracker, PROPOSER_TRACKERS_COUNT]
    # [New in EIP7441]
    whisk_trackers: List[WhiskTracker, VALIDATOR_REGISTRY_LIMIT]
    # [New in EIP7441]
    whisk_k_commitments: List[BLSG1Point, VALIDATOR_REGISTRY_LIMIT]


class ExecutionBranch(
    Vector[Bytes32, floorlog2(EXECUTION_PAYLOAD_GINDEX)]  # type: ignore
):
    pass


class LightClientHeader(Container):
    beacon: BeaconBlockHeader
    # [New in Capella]
    execution: ExecutionPayloadHeader
    # [New in Capella]
    execution_branch: ExecutionBranch


class LightClientOptimisticUpdate(Container):
    # [Modified in Capella]
    attested_header: LightClientHeader
    sync_aggregate: SyncAggregate
    signature_slot: Slot


class LightClientFinalityUpdate(Container):
    # [Modified in Capella]
    attested_header: LightClientHeader
    # [Modified in Capella]
    finalized_header: LightClientHeader
    finality_branch: FinalityBranch
    sync_aggregate: SyncAggregate
    signature_slot: Slot


class LightClientUpdate(Container):
    # [Modified in Capella]
    attested_header: LightClientHeader
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: NextSyncCommitteeBranch
    # [Modified in Capella]
    finalized_header: LightClientHeader
    finality_branch: FinalityBranch
    sync_aggregate: SyncAggregate
    signature_slot: Slot


class LightClientBootstrap(Container):
    # [Modified in Capella]
    header: LightClientHeader
    current_sync_committee: SyncCommittee
    current_sync_committee_branch: CurrentSyncCommitteeBranch


class BLSFieldElement(uint256):
    pass


class WhiskShuffleProof(ByteList[MAX_SHUFFLE_PROOF_SIZE]):
    pass


class WhiskTrackerProof(ByteList[MAX_OPENING_PROOF_SIZE]):
    pass


class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload: ExecutionPayload
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    # [New in EIP7441]
    whisk_opening_proof: WhiskTrackerProof
    # [New in EIP7441]
    whisk_post_shuffle_trackers: Vector[WhiskTracker, VALIDATORS_PER_SHUFFLE]
    # [New in EIP7441]
    whisk_shuffle_proof: WhiskShuffleProof
    # [New in EIP7441]
    whisk_registration_proof: WhiskTrackerProof
    # [New in EIP7441]
    whisk_tracker: WhiskTracker
    # [New in EIP7441]
    whisk_k_commitment: BLSG1Point


class BeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody


class SignedBeaconBlock(Container):
    message: BeaconBlock
    signature: BLSSignature


@dataclass(eq=True, frozen=True)
class LatestMessage:
    epoch: Epoch
    root: Root


@dataclass
class Store:
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: set[ValidatorIndex]
    blocks: dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: dict[Root, BeaconState] = field(default_factory=dict)
    block_timeliness: dict[Root, boolean] = field(default_factory=dict)
    checkpoint_states: dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: dict[Root, Checkpoint] = field(default_factory=dict)


@dataclass
class LightClientStore:
    # [Modified in Capella]
    finalized_header: LightClientHeader
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # [Modified in Capella]
    best_valid_update: LightClientUpdate | None
    # [Modified in Capella]
    optimistic_header: LightClientHeader
    previous_max_active_participants: uint64
    current_max_active_participants: uint64


@dataclass
class NewPayloadRequest:
    execution_payload: ExecutionPayload


@dataclass
class PayloadAttributes:
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    # [New in Capella]
    withdrawals: Sequence[Withdrawal]


@dataclass
class GetPayloadResponse:
    execution_payload: ExecutionPayload
    block_value: uint256


@dataclass
class OptimisticStore:
    optimistic_roots: set[Root]
    head_block_root: Root
    blocks: dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: dict[Root, BeaconState] = field(default_factory=dict)


class ExecutionEngine(Protocol):
    def notify_new_payload(self, execution_payload: ExecutionPayload) -> bool:
        """
        Return ``True`` if and only if ``execution_payload`` is valid with respect to ``self.execution_state``.
        """
        ...

    def is_valid_block_hash(self, execution_payload: ExecutionPayload) -> bool:
        """
        Return ``True`` if and only if ``execution_payload.block_hash`` is computed correctly.
        """
        ...

    def verify_and_notify_new_payload(self, new_payload_request: NewPayloadRequest) -> bool: ...

    def notify_forkchoice_updated(
        self,
        head_block_hash: Hash32,
        safe_block_hash: Hash32,
        finalized_block_hash: Hash32,
        payload_attributes: PayloadAttributes | None,
    ) -> PayloadId | None: ...

    def get_payload(self, payload_id: PayloadId) -> GetPayloadResponse:
        """
        Return ``GetPayloadResponse`` object.
        """
        ...


def integer_squareroot(n: uint64) -> uint64:
    """
    Return the largest integer ``x`` such that ``x**2 <= n``.
    """
    if n == UINT64_MAX:
        return UINT64_MAX_SQRT
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x


def xor(bytes_1: Bytes32, bytes_2: Bytes32) -> Bytes32:
    """
    Return the exclusive-or of two 32-byte strings.
    """
    return Bytes32(a ^ b for a, b in zip(bytes_1, bytes_2))


def bytes_to_uint64(data: bytes) -> uint64:
    """
    Return the integer deserialization of ``data`` interpreted as ``ENDIANNESS``-endian.
    """
    return uint64(int.from_bytes(data, ENDIANNESS))


def saturating_sub(a: int, b: int) -> int:
    """
    Computes a - b, saturating at numeric bounds.
    """
    return a - b if a > b else 0


def is_active_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is active.
    """
    return validator.activation_epoch <= epoch < validator.exit_epoch


def is_eligible_for_activation_queue(validator: Validator) -> bool:
    """
    Check if ``validator`` is eligible to be placed into the activation queue.
    """
    return (
        validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
        and validator.effective_balance == MAX_EFFECTIVE_BALANCE
    )


def is_eligible_for_activation(state: BeaconState, validator: Validator) -> bool:
    """
    Check if ``validator`` is eligible for activation.
    """
    return (
        # Placement in queue is finalized
        validator.activation_eligibility_epoch <= state.finalized_checkpoint.epoch
        # Has not yet been activated
        and validator.activation_epoch == FAR_FUTURE_EPOCH
    )


def is_slashable_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is slashable.
    """
    return (not validator.slashed) and (
        validator.activation_epoch <= epoch < validator.withdrawable_epoch
    )


def is_slashable_attestation_data(data_1: AttestationData, data_2: AttestationData) -> bool:
    """
    Check if ``data_1`` and ``data_2`` are slashable according to Casper FFG rules.
    """
    return (
        # Double vote
        (data_1 != data_2 and data_1.target.epoch == data_2.target.epoch)
        or
        # Surround vote
        (data_1.source.epoch < data_2.source.epoch and data_2.target.epoch < data_1.target.epoch)
    )


def is_valid_indexed_attestation(
    state: BeaconState, indexed_attestation: IndexedAttestation
) -> bool:
    """
    Check if ``indexed_attestation`` is not empty, has sorted and unique indices and has a valid aggregate signature.
    """
    # Verify indices are sorted and unique
    indices = indexed_attestation.attesting_indices
    if len(indices) == 0 or not indices == sorted(set(indices)):
        return False
    # Verify aggregate signature
    pubkeys = [state.validators[i].pubkey for i in indices]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, indexed_attestation.signature)


def is_valid_merkle_branch(
    leaf: Bytes32, branch: Sequence[Bytes32], depth: uint64, index: uint64, root: Root
) -> bool:
    """
    Check if ``leaf`` at ``index`` verifies against the Merkle ``root`` and ``branch``.
    """
    value = leaf
    for i in range(depth):
        if index // (2**i) % 2:
            value = hash(branch[i] + value)
        else:
            value = hash(value + branch[i])
    return value == root


def compute_shuffled_index(index: uint64, index_count: uint64, seed: Bytes32) -> uint64:
    """
    Return the shuffled index corresponding to ``seed`` (and ``index_count``).
    """
    assert index < index_count

    # Swap or not (https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf)
    # See the 'generalized domain' algorithm on page 3
    for current_round in range(SHUFFLE_ROUND_COUNT):
        pivot = bytes_to_uint64(hash(seed + uint_to_bytes(uint8(current_round)))[0:8]) % index_count
        flip = (pivot + index_count - index) % index_count
        position = max(index, flip)
        source = hash(
            seed + uint_to_bytes(uint8(current_round)) + uint_to_bytes(uint32(position // 256))
        )
        byte = uint8(source[(position % 256) // 8])
        bit = (byte >> (position % 8)) % 2
        index = flip if bit else index

    return index


def compute_proposer_index(
    state: BeaconState, indices: Sequence[ValidatorIndex], seed: Bytes32
) -> ValidatorIndex:
    """
    Return from ``indices`` a random index sampled by effective balance.
    """
    assert len(indices) > 0
    MAX_RANDOM_BYTE = 2**8 - 1
    i = uint64(0)
    total = uint64(len(indices))
    while True:
        candidate_index = indices[compute_shuffled_index(i % total, total, seed)]
        random_byte = hash(seed + uint_to_bytes(uint64(i // 32)))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            return candidate_index
        i += 1


def compute_committee(
    indices: Sequence[ValidatorIndex], seed: Bytes32, index: uint64, count: uint64
) -> Sequence[ValidatorIndex]:
    """
    Return the committee corresponding to ``indices``, ``seed``, ``index``, and committee ``count``.
    """
    start = (len(indices) * index) // count
    end = (len(indices) * uint64(index + 1)) // count
    return [
        indices[compute_shuffled_index(uint64(i), uint64(len(indices)), seed)]
        for i in range(start, end)
    ]


def compute_time_at_slot(state: BeaconState, slot: Slot) -> uint64:
    slots_since_genesis = slot - GENESIS_SLOT
    return uint64(state.genesis_time + slots_since_genesis * config.SECONDS_PER_SLOT)


def compute_epoch_at_slot(slot: Slot) -> Epoch:
    """
    Return the epoch number at ``slot``.
    """
    return Epoch(slot // SLOTS_PER_EPOCH)


def compute_start_slot_at_epoch(epoch: Epoch) -> Slot:
    """
    Return the start slot of ``epoch``.
    """
    return Slot(epoch * SLOTS_PER_EPOCH)


def compute_activation_exit_epoch(epoch: Epoch) -> Epoch:
    """
    Return the epoch during which validator activations and exits initiated in ``epoch`` take effect.
    """
    return Epoch(epoch + 1 + MAX_SEED_LOOKAHEAD)


def compute_fork_data_root(current_version: Version, genesis_validators_root: Root) -> Root:
    """
    Return the 32-byte fork data root for the ``current_version`` and ``genesis_validators_root``.
    This is used primarily in signature domains to avoid collisions across forks/chains.
    """
    return hash_tree_root(
        ForkData(
            current_version=current_version,
            genesis_validators_root=genesis_validators_root,
        )
    )


def compute_domain(
    domain_type: DomainType, fork_version: Version = None, genesis_validators_root: Root = None
) -> Domain:
    """
    Return the domain for the ``domain_type`` and ``fork_version``.
    """
    if fork_version is None:
        fork_version = config.GENESIS_FORK_VERSION
    if genesis_validators_root is None:
        genesis_validators_root = Root()  # all bytes zero by default
    fork_data_root = compute_fork_data_root(fork_version, genesis_validators_root)
    return Domain(domain_type + fork_data_root[:28])


def compute_signing_root(ssz_object: SSZObject, domain: Domain) -> Root:
    """
    Return the signing root for the corresponding signing data.
    """
    return hash_tree_root(
        SigningData(
            object_root=hash_tree_root(ssz_object),
            domain=domain,
        )
    )


def get_current_epoch(state: BeaconState) -> Epoch:
    """
    Return the current epoch.
    """
    return compute_epoch_at_slot(state.slot)


def get_previous_epoch(state: BeaconState) -> Epoch:
    """`
    Return the previous epoch (unless the current epoch is ``GENESIS_EPOCH``).
    """
    current_epoch = get_current_epoch(state)
    return GENESIS_EPOCH if current_epoch == GENESIS_EPOCH else Epoch(current_epoch - 1)


def get_block_root(state: BeaconState, epoch: Epoch) -> Root:
    """
    Return the block root at the start of a recent ``epoch``.
    """
    return get_block_root_at_slot(state, compute_start_slot_at_epoch(epoch))


def get_block_root_at_slot(state: BeaconState, slot: Slot) -> Root:
    """
    Return the block root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.block_roots[slot % SLOTS_PER_HISTORICAL_ROOT]


def get_randao_mix(state: BeaconState, epoch: Epoch) -> Bytes32:
    """
    Return the randao mix at a recent ``epoch``.
    """
    return state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR]


def get_active_validator_indices(state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the sequence of active validator indices at ``epoch``.
    """
    return [
        ValidatorIndex(i) for i, v in enumerate(state.validators) if is_active_validator(v, epoch)
    ]


def get_validator_churn_limit(state: BeaconState) -> uint64:
    """
    Return the validator churn limit for the current epoch.
    """
    active_validator_indices = get_active_validator_indices(state, get_current_epoch(state))
    return max(
        config.MIN_PER_EPOCH_CHURN_LIMIT,
        uint64(len(active_validator_indices)) // config.CHURN_LIMIT_QUOTIENT,
    )


def get_seed(state: BeaconState, epoch: Epoch, domain_type: DomainType) -> Bytes32:
    """
    Return the seed at ``epoch``.
    """
    mix = get_randao_mix(
        state, Epoch(epoch + EPOCHS_PER_HISTORICAL_VECTOR - MIN_SEED_LOOKAHEAD - 1)
    )  # Avoid underflow
    return hash(domain_type + uint_to_bytes(epoch) + mix)


def get_committee_count_per_slot(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of committees in each slot for the given ``epoch``.
    """
    return max(
        uint64(1),
        min(
            MAX_COMMITTEES_PER_SLOT,
            uint64(len(get_active_validator_indices(state, epoch)))
            // SLOTS_PER_EPOCH
            // TARGET_COMMITTEE_SIZE,
        ),
    )


def get_beacon_committee(
    state: BeaconState, slot: Slot, index: CommitteeIndex
) -> Sequence[ValidatorIndex]:
    """
    Return the beacon committee at ``slot`` for ``index``.
    """
    epoch = compute_epoch_at_slot(slot)
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    return compute_committee(
        indices=get_active_validator_indices(state, epoch),
        seed=get_seed(state, epoch, DOMAIN_BEACON_ATTESTER),
        index=(slot % SLOTS_PER_EPOCH) * committees_per_slot + index,
        count=committees_per_slot * SLOTS_PER_EPOCH,
    )


def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    assert (
        state.latest_block_header.slot == state.slot
    )  # sanity check `process_block_header` has been called
    return state.latest_block_header.proposer_index


def get_total_balance(state: BeaconState, indices: set[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of the ``indices``.
    ``EFFECTIVE_BALANCE_INCREMENT`` Gwei minimum to avoid divisions by zero.
    Math safe up to ~10B ETH, after which this overflows uint64.
    """
    return Gwei(
        max(
            EFFECTIVE_BALANCE_INCREMENT,
            sum([state.validators[index].effective_balance for index in indices]),
        )
    )


def get_total_active_balance(state: BeaconState) -> Gwei:
    """
    Return the combined effective balance of the active validators.
    Note: ``get_total_balance`` returns ``EFFECTIVE_BALANCE_INCREMENT`` Gwei minimum to avoid divisions by zero.
    """
    return get_total_balance(
        state, set(get_active_validator_indices(state, get_current_epoch(state)))
    )


def get_domain(state: BeaconState, domain_type: DomainType, epoch: Epoch = None) -> Domain:
    """
    Return the signature domain (fork version concatenated with domain type) of a message.
    """
    epoch = get_current_epoch(state) if epoch is None else epoch
    fork_version = (
        state.fork.previous_version if epoch < state.fork.epoch else state.fork.current_version
    )
    return compute_domain(domain_type, fork_version, state.genesis_validators_root)


def get_indexed_attestation(state: BeaconState, attestation: Attestation) -> IndexedAttestation:
    """
    Return the indexed attestation corresponding to ``attestation``.
    """
    attesting_indices = get_attesting_indices(state, attestation)

    return IndexedAttestation(
        attesting_indices=sorted(attesting_indices),
        data=attestation.data,
        signature=attestation.signature,
    )


def get_attesting_indices(state: BeaconState, attestation: Attestation) -> set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``data`` and ``bits``.
    """
    committee = get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    return set(index for i, index in enumerate(committee) if attestation.aggregation_bits[i])


def increase_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Increase the validator balance at index ``index`` by ``delta``.
    """
    state.balances[index] += delta


def decrease_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Decrease the validator balance at index ``index`` by ``delta``, with underflow protection.
    """
    state.balances[index] = 0 if delta > state.balances[index] else state.balances[index] - delta


def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    validator = state.validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch
    exit_epochs = [v.exit_epoch for v in state.validators if v.exit_epoch != FAR_FUTURE_EPOCH]
    exit_queue_epoch = max(exit_epochs + [compute_activation_exit_epoch(get_current_epoch(state))])
    exit_queue_churn = len([v for v in state.validators if v.exit_epoch == exit_queue_epoch])
    if exit_queue_churn >= get_validator_churn_limit(state):
        exit_queue_epoch += Epoch(1)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = Epoch(
        validator.exit_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )


def slash_validator(
    state: BeaconState, slashed_index: ValidatorIndex, whistleblower_index: ValidatorIndex = None
) -> None:
    """
    Slash the validator with index ``slashed_index``.
    """
    epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    validator = state.validators[slashed_index]
    validator.slashed = True
    validator.withdrawable_epoch = max(
        validator.withdrawable_epoch, Epoch(epoch + EPOCHS_PER_SLASHINGS_VECTOR)
    )
    state.slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] += validator.effective_balance
    # [Modified in Bellatrix]
    slashing_penalty = validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX
    decrease_balance(state, slashed_index, slashing_penalty)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblower_reward = Gwei(validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT)
    proposer_reward = Gwei(whistleblower_reward * PROPOSER_WEIGHT // WEIGHT_DENOMINATOR)
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, Gwei(whistleblower_reward - proposer_reward))


def initialize_beacon_state_from_eth1(
    eth1_block_hash: Hash32, eth1_timestamp: uint64, deposits: Sequence[Deposit]
) -> BeaconState:
    fork = Fork(
        previous_version=config.GENESIS_FORK_VERSION,
        current_version=config.GENESIS_FORK_VERSION,
        epoch=GENESIS_EPOCH,
    )
    state = BeaconState(
        genesis_time=eth1_timestamp + config.GENESIS_DELAY,
        fork=fork,
        eth1_data=Eth1Data(deposit_count=uint64(len(deposits)), block_hash=eth1_block_hash),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
        randao_mixes=[eth1_block_hash]
        * EPOCHS_PER_HISTORICAL_VECTOR,  # Seed RANDAO with Eth1 entropy
    )

    # Process deposits
    leaves = list(map(lambda deposit: deposit.data, deposits))
    for index, deposit in enumerate(deposits):
        deposit_data_list = List[DepositData, 2**DEPOSIT_CONTRACT_TREE_DEPTH](*leaves[: index + 1])
        state.eth1_data.deposit_root = hash_tree_root(deposit_data_list)
        process_deposit(state, deposit)

    # Process activations
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        validator.effective_balance = min(
            balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE
        )
        if validator.effective_balance == MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = hash_tree_root(state.validators)

    return state


def is_valid_genesis_state(state: BeaconState) -> bool:
    if state.genesis_time < config.MIN_GENESIS_TIME:
        return False
    if (
        len(get_active_validator_indices(state, GENESIS_EPOCH))
        < config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    ):
        return False
    return True


def state_transition(
    state: BeaconState, signed_block: SignedBeaconBlock, validate_result: bool = True
) -> None:
    block = signed_block.message
    # Process slots (including those with no blocks) since block
    process_slots(state, block.slot)
    # Verify signature
    if validate_result:
        assert verify_block_signature(state, signed_block)
    # Process block
    process_block(state, block)
    # Verify state root
    if validate_result:
        assert block.state_root == hash_tree_root(state)


def verify_block_signature(state: BeaconState, signed_block: SignedBeaconBlock) -> bool:
    proposer = state.validators[signed_block.message.proposer_index]
    signing_root = compute_signing_root(
        signed_block.message, get_domain(state, DOMAIN_BEACON_PROPOSER)
    )
    return bls.Verify(proposer.pubkey, signing_root, signed_block.signature)


def process_slots(state: BeaconState, slot: Slot) -> None:
    assert state.slot < slot
    while state.slot < slot:
        process_slot(state)
        # Process epoch on the start slot of the next epoch
        if (state.slot + 1) % SLOTS_PER_EPOCH == 0:
            process_epoch(state)
        state.slot = Slot(state.slot + 1)


def process_slot(state: BeaconState) -> None:
    # Cache state root
    previous_state_root = hash_tree_root(state)
    state.state_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_state_root
    # Cache latest block header state root
    if state.latest_block_header.state_root == Bytes32():
        state.latest_block_header.state_root = previous_state_root
    # Cache block root
    previous_block_root = hash_tree_root(state.latest_block_header)
    state.block_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_block_root


def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    # [New in EIP7441]
    process_whisk_updates(state)


def get_matching_source_attestations(
    state: BeaconState, epoch: Epoch
) -> Sequence[PendingAttestation]:
    assert epoch in (get_previous_epoch(state), get_current_epoch(state))
    return (
        state.current_epoch_attestations
        if epoch == get_current_epoch(state)
        else state.previous_epoch_attestations
    )


def get_matching_target_attestations(
    state: BeaconState, epoch: Epoch
) -> Sequence[PendingAttestation]:
    return [
        a
        for a in get_matching_source_attestations(state, epoch)
        if a.data.target.root == get_block_root(state, epoch)
    ]


def get_matching_head_attestations(
    state: BeaconState, epoch: Epoch
) -> Sequence[PendingAttestation]:
    return [
        a
        for a in get_matching_target_attestations(state, epoch)
        if a.data.beacon_block_root == get_block_root_at_slot(state, a.data.slot)
    ]


def get_unslashed_attesting_indices(
    state: BeaconState, attestations: Sequence[PendingAttestation]
) -> set[ValidatorIndex]:
    output: set[ValidatorIndex] = set()
    for a in attestations:
        output = output.union(get_attesting_indices(state, a))
    return set(filter(lambda index: not state.validators[index].slashed, output))


def get_attesting_balance(state: BeaconState, attestations: Sequence[PendingAttestation]) -> Gwei:
    """
    Return the combined effective balance of the set of unslashed validators participating in ``attestations``.
    Note: ``get_total_balance`` returns ``EFFECTIVE_BALANCE_INCREMENT`` Gwei minimum to avoid divisions by zero.
    """
    return get_total_balance(state, get_unslashed_attesting_indices(state, attestations))


def process_justification_and_finalization(state: BeaconState) -> None:
    # Initial FFG checkpoint values have a `0x00` stub for `root`.
    # Skip FFG updates in the first two epochs to avoid corner cases that might result in modifying this stub.
    if get_current_epoch(state) <= GENESIS_EPOCH + 1:
        return
    previous_indices = get_unslashed_participating_indices(
        state, TIMELY_TARGET_FLAG_INDEX, get_previous_epoch(state)
    )
    current_indices = get_unslashed_participating_indices(
        state, TIMELY_TARGET_FLAG_INDEX, get_current_epoch(state)
    )
    total_active_balance = get_total_active_balance(state)
    previous_target_balance = get_total_balance(state, previous_indices)
    current_target_balance = get_total_balance(state, current_indices)
    weigh_justification_and_finalization(
        state, total_active_balance, previous_target_balance, current_target_balance
    )


def weigh_justification_and_finalization(
    state: BeaconState,
    total_active_balance: Gwei,
    previous_epoch_target_balance: Gwei,
    current_epoch_target_balance: Gwei,
) -> None:
    previous_epoch = get_previous_epoch(state)
    current_epoch = get_current_epoch(state)
    old_previous_justified_checkpoint = state.previous_justified_checkpoint
    old_current_justified_checkpoint = state.current_justified_checkpoint

    # Process justifications
    state.previous_justified_checkpoint = state.current_justified_checkpoint
    state.justification_bits[1:] = state.justification_bits[: JUSTIFICATION_BITS_LENGTH - 1]
    state.justification_bits[0] = 0b0
    if previous_epoch_target_balance * 3 >= total_active_balance * 2:
        state.current_justified_checkpoint = Checkpoint(
            epoch=previous_epoch, root=get_block_root(state, previous_epoch)
        )
        state.justification_bits[1] = 0b1
    if current_epoch_target_balance * 3 >= total_active_balance * 2:
        state.current_justified_checkpoint = Checkpoint(
            epoch=current_epoch, root=get_block_root(state, current_epoch)
        )
        state.justification_bits[0] = 0b1

    # Process finalizations
    bits = state.justification_bits
    # The 2nd/3rd/4th most recent epochs are justified, the 2nd using the 4th as source
    if all(bits[1:4]) and old_previous_justified_checkpoint.epoch + 3 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 2nd/3rd most recent epochs are justified, the 2nd using the 3rd as source
    if all(bits[1:3]) and old_previous_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 1st/2nd/3rd most recent epochs are justified, the 1st using the 3rd as source
    if all(bits[0:3]) and old_current_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint
    # The 1st/2nd most recent epochs are justified, the 1st using the 2nd as source
    if all(bits[0:2]) and old_current_justified_checkpoint.epoch + 1 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint


def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    """
    Return the base reward for the validator defined by ``index`` with respect to the current ``state``.
    """
    increments = state.validators[index].effective_balance // EFFECTIVE_BALANCE_INCREMENT
    return Gwei(increments * get_base_reward_per_increment(state))


def get_proposer_reward(state: BeaconState, attesting_index: ValidatorIndex) -> Gwei:
    return Gwei(get_base_reward(state, attesting_index) // PROPOSER_REWARD_QUOTIENT)


def get_finality_delay(state: BeaconState) -> uint64:
    return get_previous_epoch(state) - state.finalized_checkpoint.epoch


def is_in_inactivity_leak(state: BeaconState) -> bool:
    return get_finality_delay(state) > MIN_EPOCHS_TO_INACTIVITY_PENALTY


def get_eligible_validator_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    previous_epoch = get_previous_epoch(state)
    return [
        ValidatorIndex(index)
        for index, v in enumerate(state.validators)
        if is_active_validator(v, previous_epoch)
        or (v.slashed and previous_epoch + 1 < v.withdrawable_epoch)
    ]


def get_attestation_component_deltas(
    state: BeaconState, attestations: Sequence[PendingAttestation]
) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Helper with shared logic for use by get source, target, and head deltas functions
    """
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
    total_balance = get_total_active_balance(state)
    unslashed_attesting_indices = get_unslashed_attesting_indices(state, attestations)
    attesting_balance = get_total_balance(state, unslashed_attesting_indices)
    for index in get_eligible_validator_indices(state):
        if index in unslashed_attesting_indices:
            increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from balance totals to avoid uint64 overflow
            if is_in_inactivity_leak(state):
                # Since full base reward will be canceled out by inactivity penalty deltas,
                # optimal participation receives full base reward compensation here.
                rewards[index] += get_base_reward(state, index)
            else:
                reward_numerator = get_base_reward(state, index) * (attesting_balance // increment)
                rewards[index] += reward_numerator // (total_balance // increment)
        else:
            penalties[index] += get_base_reward(state, index)
    return rewards, penalties


def get_source_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return attester micro-rewards/penalties for source-vote for each validator.
    """
    matching_source_attestations = get_matching_source_attestations(
        state, get_previous_epoch(state)
    )
    return get_attestation_component_deltas(state, matching_source_attestations)


def get_target_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return attester micro-rewards/penalties for target-vote for each validator.
    """
    matching_target_attestations = get_matching_target_attestations(
        state, get_previous_epoch(state)
    )
    return get_attestation_component_deltas(state, matching_target_attestations)


def get_head_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return attester micro-rewards/penalties for head-vote for each validator.
    """
    matching_head_attestations = get_matching_head_attestations(state, get_previous_epoch(state))
    return get_attestation_component_deltas(state, matching_head_attestations)


def get_inclusion_delay_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return proposer and inclusion delay micro-rewards/penalties for each validator.
    """
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    matching_source_attestations = get_matching_source_attestations(
        state, get_previous_epoch(state)
    )
    for index in get_unslashed_attesting_indices(state, matching_source_attestations):
        attestation = min(
            [a for a in matching_source_attestations if index in get_attesting_indices(state, a)],
            key=lambda a: a.inclusion_delay,
        )
        rewards[attestation.proposer_index] += get_proposer_reward(state, index)
        max_attester_reward = Gwei(
            get_base_reward(state, index) - get_proposer_reward(state, index)
        )
        rewards[index] += Gwei(max_attester_reward // attestation.inclusion_delay)

    # No penalties associated with inclusion delay
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    return rewards, penalties


def get_inactivity_penalty_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the inactivity penalty deltas by considering timely target participation flags and inactivity scores.
    """
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    previous_epoch = get_previous_epoch(state)
    matching_target_indices = get_unslashed_participating_indices(
        state, TIMELY_TARGET_FLAG_INDEX, previous_epoch
    )
    for index in get_eligible_validator_indices(state):
        if index not in matching_target_indices:
            penalty_numerator = (
                state.validators[index].effective_balance * state.inactivity_scores[index]
            )
            # [Modified in Bellatrix]
            penalty_denominator = (
                config.INACTIVITY_SCORE_BIAS * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
            )
            penalties[index] += Gwei(penalty_numerator // penalty_denominator)
    return rewards, penalties


def get_attestation_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return attestation reward/penalty deltas for each validator.
    """
    source_rewards, source_penalties = get_source_deltas(state)
    target_rewards, target_penalties = get_target_deltas(state)
    head_rewards, head_penalties = get_head_deltas(state)
    inclusion_delay_rewards, _ = get_inclusion_delay_deltas(state)
    _, inactivity_penalties = get_inactivity_penalty_deltas(state)

    rewards = [
        source_rewards[i] + target_rewards[i] + head_rewards[i] + inclusion_delay_rewards[i]
        for i in range(len(state.validators))
    ]

    penalties = [
        source_penalties[i] + target_penalties[i] + head_penalties[i] + inactivity_penalties[i]
        for i in range(len(state.validators))
    ]

    return rewards, penalties


def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    flag_deltas = [
        get_flag_index_deltas(state, flag_index)
        for flag_index in range(len(PARTICIPATION_FLAG_WEIGHTS))
    ]
    deltas = flag_deltas + [get_inactivity_penalty_deltas(state)]
    for rewards, penalties in deltas:
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
            decrease_balance(state, ValidatorIndex(index), penalties[index])


def process_registry_updates(state: BeaconState) -> None:
    # Process activation eligibility and ejections
    for index, validator in enumerate(state.validators):
        if is_eligible_for_activation_queue(validator):
            validator.activation_eligibility_epoch = get_current_epoch(state) + 1

        if (
            is_active_validator(validator, get_current_epoch(state))
            and validator.effective_balance <= config.EJECTION_BALANCE
        ):
            initiate_validator_exit(state, ValidatorIndex(index))

    # Queue validators eligible for activation and not yet dequeued for activation
    activation_queue = sorted(
        [
            index
            for index, validator in enumerate(state.validators)
            if is_eligible_for_activation(state, validator)
        ],
        # Order by the sequence of activation_eligibility_epoch setting and then index
        key=lambda index: (state.validators[index].activation_eligibility_epoch, index),
    )
    # Dequeued validators for activation up to churn limit
    for index in activation_queue[: get_validator_churn_limit(state)]:
        validator = state.validators[index]
        validator.activation_epoch = compute_activation_exit_epoch(get_current_epoch(state))


def process_slashings(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    total_balance = get_total_active_balance(state)
    adjusted_total_slashing_balance = min(
        sum(state.slashings)
        # [Modified in Bellatrix]
        * PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX,
        total_balance,
    )
    for index, validator in enumerate(state.validators):
        if (
            validator.slashed
            and epoch + EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch
        ):
            increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from penalty numerator to avoid uint64 overflow
            penalty_numerator = (
                validator.effective_balance // increment * adjusted_total_slashing_balance
            )
            penalty = penalty_numerator // total_balance * increment
            decrease_balance(state, ValidatorIndex(index), penalty)


def process_eth1_data_reset(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    # Reset eth1 data votes
    if next_epoch % EPOCHS_PER_ETH1_VOTING_PERIOD == 0:
        state.eth1_data_votes = []


def process_effective_balance_updates(state: BeaconState) -> None:
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        if (
            balance + DOWNWARD_THRESHOLD < validator.effective_balance
            or validator.effective_balance + UPWARD_THRESHOLD < balance
        ):
            validator.effective_balance = min(
                balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE
            )


def process_slashings_reset(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    # Reset slashings
    state.slashings[next_epoch % EPOCHS_PER_SLASHINGS_VECTOR] = Gwei(0)


def process_randao_mixes_reset(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    next_epoch = Epoch(current_epoch + 1)
    # Set randao mix
    state.randao_mixes[next_epoch % EPOCHS_PER_HISTORICAL_VECTOR] = get_randao_mix(
        state, current_epoch
    )


def process_historical_roots_update(state: BeaconState) -> None:
    # Set historical root accumulator
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_batch = HistoricalBatch(
            block_roots=state.block_roots, state_roots=state.state_roots
        )
        state.historical_roots.append(hash_tree_root(historical_batch))


def process_participation_record_updates(state: BeaconState) -> None:
    # Rotate current/previous epoch attestations
    state.previous_epoch_attestations = state.current_epoch_attestations
    state.current_epoch_attestations = []


def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
    # [New in EIP7441]
    process_shuffled_trackers(state, block.body)
    # [New in EIP7441]
    process_whisk_registration(state, block.body)


def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the block is newer than latest block header
    assert block.slot > state.latest_block_header.slot

    # # Verify that proposer index is the correct index
    # assert block.proposer_index == get_beacon_proposer_index(state)

    # Verify that the parent matches
    assert block.parent_root == hash_tree_root(state.latest_block_header)
    # Cache current block as the new latest block
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=Bytes32(),  # Overwritten in the next process_slot call
        body_root=hash_tree_root(block.body),
    )

    # Verify proposer is not slashed
    proposer = state.validators[block.proposer_index]
    assert not proposer.slashed
    # [New in EIP7441]
    process_whisk_opening_proof(state, block)


def process_randao(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    # Verify RANDAO reveal
    proposer = state.validators[get_beacon_proposer_index(state)]
    signing_root = compute_signing_root(epoch, get_domain(state, DOMAIN_RANDAO))
    assert bls.Verify(proposer.pubkey, signing_root, body.randao_reveal)
    # Mix in RANDAO reveal
    mix = xor(get_randao_mix(state, epoch), hash(body.randao_reveal))
    state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR] = mix


def process_eth1_data(state: BeaconState, body: BeaconBlockBody) -> None:
    state.eth1_data_votes.append(body.eth1_data)
    if (
        state.eth1_data_votes.count(body.eth1_data) * 2
        > EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH
    ):
        state.eth1_data = body.eth1_data


def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(
        MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index
    )

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    # [New in Capella]
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)


def process_proposer_slashing(state: BeaconState, proposer_slashing: ProposerSlashing) -> None:
    header_1 = proposer_slashing.signed_header_1.message
    header_2 = proposer_slashing.signed_header_2.message

    # Verify header slots match
    assert header_1.slot == header_2.slot
    # Verify header proposer indices match
    assert header_1.proposer_index == header_2.proposer_index
    # Verify the headers are different
    assert header_1 != header_2
    # Verify the proposer is slashable
    proposer = state.validators[header_1.proposer_index]
    assert is_slashable_validator(proposer, get_current_epoch(state))
    # Verify signatures
    for signed_header in (proposer_slashing.signed_header_1, proposer_slashing.signed_header_2):
        domain = get_domain(
            state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(signed_header.message.slot)
        )
        signing_root = compute_signing_root(signed_header.message, domain)
        assert bls.Verify(proposer.pubkey, signing_root, signed_header.signature)

    slash_validator(state, header_1.proposer_index)


def process_attester_slashing(state: BeaconState, attester_slashing: AttesterSlashing) -> None:
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2
    assert is_slashable_attestation_data(attestation_1.data, attestation_2.data)
    assert is_valid_indexed_attestation(state, attestation_1)
    assert is_valid_indexed_attestation(state, attestation_2)

    slashed_any = False
    indices = set(attestation_1.attesting_indices).intersection(attestation_2.attesting_indices)
    for index in sorted(indices):
        if is_slashable_validator(state.validators[index], get_current_epoch(state)):
            slash_validator(state, index)
            slashed_any = True
    assert slashed_any


def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot <= data.slot + SLOTS_PER_EPOCH
    assert data.index < get_committee_count_per_slot(state, data.target.epoch)

    committee = get_beacon_committee(state, data.slot, data.index)
    assert len(attestation.aggregation_bits) == len(committee)

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(
        state, data, state.slot - data.slot
    )

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Update epoch participation flags
    if data.target.epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)


def get_validator_from_deposit(
    pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: uint64
) -> Validator:
    effective_balance = min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)

    return Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        effective_balance=effective_balance,
        slashed=False,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
    )


def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: uint64
) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, uint64(0))
    # [New in EIP7441]
    k = get_unique_whisk_k(state, ValidatorIndex(len(state.validators) - 1))
    state.whisk_trackers.append(get_initial_tracker(k))
    state.whisk_k_commitments.append(get_k_commitment(k))


def apply_deposit(
    state: BeaconState,
    pubkey: BLSPubkey,
    withdrawal_credentials: Bytes32,
    amount: uint64,
    signature: BLSSignature,
) -> None:
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        deposit_message = DepositMessage(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            amount=amount,
        )
        # Fork-agnostic domain since deposits are valid across forks
        domain = compute_domain(DOMAIN_DEPOSIT)
        signing_root = compute_signing_root(deposit_message, domain)
        if bls.Verify(pubkey, signing_root, signature):
            add_validator_to_registry(state, pubkey, withdrawal_credentials, amount)
    else:
        # Increase balance by deposit amount
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        increase_balance(state, index, amount)


def process_deposit(state: BeaconState, deposit: Deposit) -> None:
    # Verify the Merkle branch
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(deposit.data),
        branch=deposit.proof,
        # Add 1 for the List length mix-in
        depth=DEPOSIT_CONTRACT_TREE_DEPTH + 1,
        index=state.eth1_deposit_index,
        root=state.eth1_data.deposit_root,
    )

    # Deposits must be processed in order
    state.eth1_deposit_index += 1

    apply_deposit(
        state=state,
        pubkey=deposit.data.pubkey,
        withdrawal_credentials=deposit.data.withdrawal_credentials,
        amount=deposit.data.amount,
        signature=deposit.data.signature,
    )


def process_voluntary_exit(state: BeaconState, signed_voluntary_exit: SignedVoluntaryExit) -> None:
    voluntary_exit = signed_voluntary_exit.message
    validator = state.validators[voluntary_exit.validator_index]
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify exit has not been initiated
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= voluntary_exit.epoch
    # Verify the validator has been active long enough
    assert get_current_epoch(state) >= validator.activation_epoch + config.SHARD_COMMITTEE_PERIOD
    # Verify signature
    domain = get_domain(state, DOMAIN_VOLUNTARY_EXIT, voluntary_exit.epoch)
    signing_root = compute_signing_root(voluntary_exit, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)


def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_epoch = get_current_epoch(anchor_state)
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    proposer_boost_root = Root()
    return Store(
        time=uint64(anchor_state.genesis_time + config.SECONDS_PER_SLOT * anchor_state.slot),
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        unrealized_justified_checkpoint=justified_checkpoint,
        unrealized_finalized_checkpoint=finalized_checkpoint,
        proposer_boost_root=proposer_boost_root,
        equivocating_indices=set(),
        blocks={anchor_root: copy(anchor_block)},
        block_states={anchor_root: copy(anchor_state)},
        checkpoint_states={justified_checkpoint: copy(anchor_state)},
        unrealized_justifications={anchor_root: justified_checkpoint},
    )


def get_slots_since_genesis(store: Store) -> int:
    return (store.time - store.genesis_time) // config.SECONDS_PER_SLOT


def get_current_slot(store: Store) -> Slot:
    return Slot(GENESIS_SLOT + get_slots_since_genesis(store))


def get_current_store_epoch(store: Store) -> Epoch:
    return compute_epoch_at_slot(get_current_slot(store))


def compute_slots_since_epoch_start(slot: Slot) -> int:
    return slot - compute_start_slot_at_epoch(compute_epoch_at_slot(slot))


def get_ancestor(store: Store, root: Root, slot: Slot) -> Root:
    block = store.blocks[root]
    if block.slot > slot:
        return get_ancestor(store, block.parent_root, slot)
    return root


def calculate_committee_fraction(state: BeaconState, committee_percent: uint64) -> Gwei:
    committee_weight = get_total_active_balance(state) // SLOTS_PER_EPOCH
    return Gwei((committee_weight * committee_percent) // 100)


def get_checkpoint_block(store: Store, root: Root, epoch: Epoch) -> Root:
    """
    Compute the checkpoint block for epoch ``epoch`` in the chain of block ``root``
    """
    epoch_first_slot = compute_start_slot_at_epoch(epoch)
    return get_ancestor(store, root, epoch_first_slot)


def get_attestation_score(store: Store, root: Root, state: BeaconState) -> Gwei:
    unslashed_and_active_indices = [
        i
        for i in get_active_validator_indices(state, get_current_epoch(state))
        if not state.validators[i].slashed
    ]
    return Gwei(
        sum(
            state.validators[i].effective_balance
            for i in unslashed_and_active_indices
            if (
                i in store.latest_messages
                and i not in store.equivocating_indices
                and get_ancestor(store, store.latest_messages[i].root, store.blocks[root].slot)
                == root
            )
        )
    )


def compute_proposer_score(state: BeaconState) -> Gwei:
    committee_weight = get_total_active_balance(state) // SLOTS_PER_EPOCH
    return (committee_weight * config.PROPOSER_SCORE_BOOST) // 100


def get_proposer_score(store: Store) -> Gwei:
    justified_checkpoint_state = store.checkpoint_states[store.justified_checkpoint]
    return compute_proposer_score(justified_checkpoint_state)


def get_weight(store: Store, root: Root) -> Gwei:
    state = store.checkpoint_states[store.justified_checkpoint]
    attestation_score = get_attestation_score(store, root, state)
    if store.proposer_boost_root == Root():
        # Return only attestation score if ``proposer_boost_root`` is not set
        return attestation_score

    # Calculate proposer score if ``proposer_boost_root`` is set
    proposer_score = Gwei(0)
    # Boost is applied if ``root`` is an ancestor of ``proposer_boost_root``
    if get_ancestor(store, store.proposer_boost_root, store.blocks[root].slot) == root:
        proposer_score = get_proposer_score(store)
    return attestation_score + proposer_score


def get_voting_source(store: Store, block_root: Root) -> Checkpoint:
    """
    Compute the voting source checkpoint in event that block with root ``block_root`` is the head block
    """
    block = store.blocks[block_root]
    current_epoch = get_current_store_epoch(store)
    block_epoch = compute_epoch_at_slot(block.slot)
    if current_epoch > block_epoch:
        # The block is from a prior epoch, the voting source will be pulled-up
        return store.unrealized_justifications[block_root]
    else:
        # The block is not from a prior epoch, therefore the voting source is not pulled up
        head_state = store.block_states[block_root]
        return head_state.current_justified_checkpoint


def filter_block_tree(store: Store, block_root: Root, blocks: dict[Root, BeaconBlock]) -> bool:
    block = store.blocks[block_root]
    children = [
        root for root in store.blocks.keys() if store.blocks[root].parent_root == block_root
    ]

    # If any children branches contain expected finalized/justified checkpoints,
    # add to filtered block-tree and signal viability to parent.
    if any(children):
        filter_block_tree_result = [filter_block_tree(store, child, blocks) for child in children]
        if any(filter_block_tree_result):
            blocks[block_root] = block
            return True
        return False

    current_epoch = get_current_store_epoch(store)
    voting_source = get_voting_source(store, block_root)

    # The voting source should be either at the same height as the store's justified checkpoint or
    # not more than two epochs ago
    correct_justified = (
        store.justified_checkpoint.epoch == GENESIS_EPOCH
        or voting_source.epoch == store.justified_checkpoint.epoch
        or voting_source.epoch + 2 >= current_epoch
    )

    finalized_checkpoint_block = get_checkpoint_block(
        store,
        block_root,
        store.finalized_checkpoint.epoch,
    )

    correct_finalized = (
        store.finalized_checkpoint.epoch == GENESIS_EPOCH
        or store.finalized_checkpoint.root == finalized_checkpoint_block
    )

    # If expected finalized/justified, add to viable block-tree and signal viability to parent.
    if correct_justified and correct_finalized:
        blocks[block_root] = block
        return True

    # Otherwise, branch not viable
    return False


def get_filtered_block_tree(store: Store) -> dict[Root, BeaconBlock]:
    """
    Retrieve a filtered block tree from ``store``, only returning branches
    whose leaf state's justified/finalized info agrees with that in ``store``.
    """
    base = store.justified_checkpoint.root
    blocks: dict[Root, BeaconBlock] = {}
    filter_block_tree(store, base, blocks)
    return blocks


def get_head(store: Store) -> Root:
    # Get filtered block tree that only includes viable branches
    blocks = get_filtered_block_tree(store)
    # Execute the LMD-GHOST fork choice
    head = store.justified_checkpoint.root
    while True:
        children = [root for root in blocks.keys() if blocks[root].parent_root == head]
        if len(children) == 0:
            return head
        # Sort by latest attesting balance with ties broken lexicographically
        # Ties broken by favoring block with lexicographically higher root
        head = max(children, key=lambda root: (get_weight(store, root), root))


def update_checkpoints(
    store: Store, justified_checkpoint: Checkpoint, finalized_checkpoint: Checkpoint
) -> None:
    """
    Update checkpoints in store if necessary
    """
    # Update justified checkpoint
    if justified_checkpoint.epoch > store.justified_checkpoint.epoch:
        store.justified_checkpoint = justified_checkpoint

    # Update finalized checkpoint
    if finalized_checkpoint.epoch > store.finalized_checkpoint.epoch:
        store.finalized_checkpoint = finalized_checkpoint


def update_unrealized_checkpoints(
    store: Store,
    unrealized_justified_checkpoint: Checkpoint,
    unrealized_finalized_checkpoint: Checkpoint,
) -> None:
    """
    Update unrealized checkpoints in store if necessary
    """
    # Update unrealized justified checkpoint
    if unrealized_justified_checkpoint.epoch > store.unrealized_justified_checkpoint.epoch:
        store.unrealized_justified_checkpoint = unrealized_justified_checkpoint

    # Update unrealized finalized checkpoint
    if unrealized_finalized_checkpoint.epoch > store.unrealized_finalized_checkpoint.epoch:
        store.unrealized_finalized_checkpoint = unrealized_finalized_checkpoint


def seconds_to_milliseconds(seconds: uint64) -> uint64:
    """
    Convert seconds to milliseconds with overflow protection.
    Returns ``UINT64_MAX`` if the result would overflow.
    """
    if seconds > UINT64_MAX // 1000:
        return UINT64_MAX
    return seconds * 1000


def get_slot_component_duration_ms(basis_points: uint64) -> uint64:
    """
    Calculate the duration of a slot component in milliseconds.
    """
    return basis_points * config.SLOT_DURATION_MS // BASIS_POINTS


def get_attestation_due_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(config.ATTESTATION_DUE_BPS)


def get_proposer_reorg_cutoff_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(config.PROPOSER_REORG_CUTOFF_BPS)


def get_aggregate_due_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(config.AGGREGATE_DUE_BPS)


def is_head_late(store: Store, head_root: Root) -> bool:
    return not store.block_timeliness[head_root]


def is_shuffling_stable(slot: Slot) -> bool:
    return slot % SLOTS_PER_EPOCH != 0


def is_ffg_competitive(store: Store, head_root: Root, parent_root: Root) -> bool:
    return (
        store.unrealized_justifications[head_root] == store.unrealized_justifications[parent_root]
    )


def is_finalization_ok(store: Store, slot: Slot) -> bool:
    epochs_since_finalization = compute_epoch_at_slot(slot) - store.finalized_checkpoint.epoch
    return epochs_since_finalization <= config.REORG_MAX_EPOCHS_SINCE_FINALIZATION


def is_proposing_on_time(store: Store) -> bool:
    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % config.SLOT_DURATION_MS
    epoch = get_current_store_epoch(store)
    proposer_reorg_cutoff_ms = get_proposer_reorg_cutoff_ms(epoch)
    return time_into_slot_ms <= proposer_reorg_cutoff_ms


def is_head_weak(store: Store, head_root: Root) -> bool:
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    reorg_threshold = calculate_committee_fraction(
        justified_state, config.REORG_HEAD_WEIGHT_THRESHOLD
    )
    head_weight = get_weight(store, head_root)
    return head_weight < reorg_threshold


def is_parent_strong(store: Store, parent_root: Root) -> bool:
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    parent_threshold = calculate_committee_fraction(
        justified_state, config.REORG_PARENT_WEIGHT_THRESHOLD
    )
    parent_weight = get_weight(store, parent_root)
    return parent_weight > parent_threshold


def get_proposer_head(store: Store, head_root: Root, slot: Slot) -> Root:
    head_block = store.blocks[head_root]
    parent_root = head_block.parent_root
    parent_block = store.blocks[parent_root]

    # Only re-org the head block if it arrived later than the attestation deadline.
    head_late = is_head_late(store, head_root)

    # Do not re-org on an epoch boundary where the proposer shuffling could change.
    shuffling_stable = is_shuffling_stable(slot)

    # Ensure that the FFG information of the new head will be competitive with the current head.
    ffg_competitive = is_ffg_competitive(store, head_root, parent_root)

    # Do not re-org if the chain is not finalizing with acceptable frequency.
    finalization_ok = is_finalization_ok(store, slot)

    # Only re-org if we are proposing on-time.
    proposing_on_time = is_proposing_on_time(store)

    # Only re-org a single slot at most.
    parent_slot_ok = parent_block.slot + 1 == head_block.slot
    current_time_ok = head_block.slot + 1 == slot
    single_slot_reorg = parent_slot_ok and current_time_ok

    # Check that the head has few enough votes to be overpowered by our proposer boost.
    assert store.proposer_boost_root != head_root  # ensure boost has worn off
    head_weak = is_head_weak(store, head_root)

    # Check that the missing votes are assigned to the parent and not being hoarded.
    parent_strong = is_parent_strong(store, parent_root)

    if all(
        [
            head_late,
            shuffling_stable,
            ffg_competitive,
            finalization_ok,
            proposing_on_time,
            single_slot_reorg,
            head_weak,
            parent_strong,
        ]
    ):
        # We can re-org the current head by building upon its parent block.
        return parent_root
    else:
        return head_root


def compute_pulled_up_tip(store: Store, block_root: Root) -> None:
    state = store.block_states[block_root].copy()
    # Pull up the post-state of the block to the next epoch boundary
    process_justification_and_finalization(state)

    store.unrealized_justifications[block_root] = state.current_justified_checkpoint
    update_unrealized_checkpoints(
        store, state.current_justified_checkpoint, state.finalized_checkpoint
    )

    # If the block is from a prior epoch, apply the realized values
    block_epoch = compute_epoch_at_slot(store.blocks[block_root].slot)
    current_epoch = get_current_store_epoch(store)
    if block_epoch < current_epoch:
        update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)


def on_tick_per_slot(store: Store, time: uint64) -> None:
    previous_slot = get_current_slot(store)

    # Update store time
    store.time = time

    current_slot = get_current_slot(store)

    # If this is a new slot, reset store.proposer_boost_root
    if current_slot > previous_slot:
        store.proposer_boost_root = Root()

    # If a new epoch, pull-up justification and finalization from previous epoch
    if current_slot > previous_slot and compute_slots_since_epoch_start(current_slot) == 0:
        update_checkpoints(
            store, store.unrealized_justified_checkpoint, store.unrealized_finalized_checkpoint
        )


def validate_target_epoch_against_current_time(store: Store, attestation: Attestation) -> None:
    target = attestation.data.target

    # Attestations must be from the current or previous epoch
    current_epoch = get_current_store_epoch(store)
    # Use GENESIS_EPOCH for previous when genesis to avoid underflow
    previous_epoch = current_epoch - 1 if current_epoch > GENESIS_EPOCH else GENESIS_EPOCH
    # If attestation target is from a future epoch, delay consideration until the epoch arrives
    assert target.epoch in [current_epoch, previous_epoch]


def validate_on_attestation(store: Store, attestation: Attestation, is_from_block: bool) -> None:
    target = attestation.data.target

    # If the given attestation is not from a beacon block message, we have to check the target epoch scope.
    if not is_from_block:
        validate_target_epoch_against_current_time(store, attestation)

    # Check that the epoch number and slot number are matching
    assert target.epoch == compute_epoch_at_slot(attestation.data.slot)

    # Attestation target must be for a known block. If target block is unknown, delay consideration until block is found
    assert target.root in store.blocks

    # Attestations must be for a known block. If block is unknown, delay consideration until the block is found
    assert attestation.data.beacon_block_root in store.blocks
    # Attestations must not be for blocks in the future. If not, the attestation should not be considered
    assert store.blocks[attestation.data.beacon_block_root].slot <= attestation.data.slot

    # LMD vote must be consistent with FFG vote target
    assert target.root == get_checkpoint_block(
        store, attestation.data.beacon_block_root, target.epoch
    )

    # Attestations can only affect the fork choice of subsequent slots.
    # Delay consideration in the fork choice until their slot is in the past.
    assert get_current_slot(store) >= attestation.data.slot + 1


def store_target_checkpoint_state(store: Store, target: Checkpoint) -> None:
    # Store target checkpoint state if not yet seen
    if target not in store.checkpoint_states:
        base_state = copy(store.block_states[target.root])
        if base_state.slot < compute_start_slot_at_epoch(target.epoch):
            process_slots(base_state, compute_start_slot_at_epoch(target.epoch))
        store.checkpoint_states[target] = base_state


def update_latest_messages(
    store: Store, attesting_indices: Sequence[ValidatorIndex], attestation: Attestation
) -> None:
    target = attestation.data.target
    beacon_block_root = attestation.data.beacon_block_root
    non_equivocating_attesting_indices = [
        i for i in attesting_indices if i not in store.equivocating_indices
    ]
    for i in non_equivocating_attesting_indices:
        if i not in store.latest_messages or target.epoch > store.latest_messages[i].epoch:
            store.latest_messages[i] = LatestMessage(epoch=target.epoch, root=beacon_block_root)


def on_tick(store: Store, time: uint64) -> None:
    # If the ``store.time`` falls behind, while loop catches up slot by slot
    # to ensure that every previous slot is processed with ``on_tick_per_slot``
    tick_slot = (time - store.genesis_time) // config.SECONDS_PER_SLOT
    while get_current_slot(store) < tick_slot:
        previous_time = store.genesis_time + (get_current_slot(store) + 1) * config.SECONDS_PER_SLOT
        on_tick_per_slot(store, previous_time)
    on_tick_per_slot(store, time)


def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states
    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    assert get_current_slot(store) >= block.slot

    # Check that block is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert block.slot > finalized_slot
    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    finalized_checkpoint_block = get_checkpoint_block(
        store,
        block.parent_root,
        store.finalized_checkpoint.epoch,
    )
    assert store.finalized_checkpoint.root == finalized_checkpoint_block

    # Check the block is valid and compute the post-state
    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[block.parent_root])
    block_root = hash_tree_root(block)
    state_transition(state, signed_block, True)

    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state

    # Add block timeliness to the store
    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % config.SLOT_DURATION_MS
    epoch = get_current_store_epoch(store)
    attestation_threshold_ms = get_attestation_due_ms(epoch)
    is_before_attesting_interval = time_into_slot_ms < attestation_threshold_ms
    is_timely = get_current_slot(store) == block.slot and is_before_attesting_interval
    store.block_timeliness[hash_tree_root(block)] = is_timely

    # Add proposer score boost if the block is timely and not conflicting with an existing block
    is_first_block = store.proposer_boost_root == Root()
    if is_timely and is_first_block:
        store.proposer_boost_root = hash_tree_root(block)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)


def on_attestation(store: Store, attestation: Attestation, is_from_block: bool = False) -> None:
    """
    Run ``on_attestation`` upon receiving a new ``attestation`` from either within a block or directly on the wire.

    An ``attestation`` that is asserted as invalid may be valid at a later time,
    consider scheduling it for later processing in such case.
    """
    validate_on_attestation(store, attestation, is_from_block)

    store_target_checkpoint_state(store, attestation.data.target)

    # Get state at the `target` to fully validate attestation
    target_state = store.checkpoint_states[attestation.data.target]
    indexed_attestation = get_indexed_attestation(target_state, attestation)
    assert is_valid_indexed_attestation(target_state, indexed_attestation)

    # Update latest messages for attesting indices
    update_latest_messages(store, indexed_attestation.attesting_indices, attestation)


def on_attester_slashing(store: Store, attester_slashing: AttesterSlashing) -> None:
    """
    Run ``on_attester_slashing`` immediately upon receiving a new ``AttesterSlashing``
    from either within a block or directly on the wire.
    """
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2
    assert is_slashable_attestation_data(attestation_1.data, attestation_2.data)
    state = store.block_states[store.justified_checkpoint.root]
    assert is_valid_indexed_attestation(state, attestation_1)
    assert is_valid_indexed_attestation(state, attestation_2)

    indices = set(attestation_1.attesting_indices).intersection(attestation_2.attesting_indices)
    for index in indices:
        store.equivocating_indices.add(index)


def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= config.CAPELLA_FORK_EPOCH:
        return config.CAPELLA_FORK_VERSION
    if epoch >= config.BELLATRIX_FORK_EPOCH:
        return config.BELLATRIX_FORK_VERSION
    if epoch >= config.ALTAIR_FORK_EPOCH:
        return config.ALTAIR_FORK_VERSION
    return config.GENESIS_FORK_VERSION


def compute_fork_digest(
    genesis_validators_root: Root,
    epoch: Epoch,
) -> ForkDigest:
    """
    Return the 4-byte fork digest for the ``genesis_validators_root`` at a given ``epoch``.

    This is a digest primarily used for domain separation on the p2p layer.
    4-bytes suffices for practical separation of forks/chains.
    """
    fork_version = compute_fork_version(epoch)
    base_digest = compute_fork_data_root(fork_version, genesis_validators_root)
    return ForkDigest(base_digest[:4])


def max_compressed_len(n: uint64) -> uint64:
    # Worst-case compressed length for a given payload of size n when using snappy:
    # https://github.com/google/snappy/blob/32ded457c0b1fe78ceb8397632c416568d6714a0/snappy.cc#L218C1-L218C47
    return uint64(32 + n + n / 6)


def max_message_size() -> uint64:
    # Allow 1024 bytes for framing and encoding overhead but at least 1MiB in case config.MAX_PAYLOAD_SIZE is small.
    return max(max_compressed_len(config.MAX_PAYLOAD_SIZE) + 1024, 1024 * 1024)


def compute_subscribed_subnet(node_id: NodeID, epoch: Epoch, index: int) -> SubnetID:
    node_id_prefix = node_id >> (NODE_ID_BITS - config.ATTESTATION_SUBNET_PREFIX_BITS)
    node_offset = node_id % config.EPOCHS_PER_SUBNET_SUBSCRIPTION
    permutation_seed = hash(
        uint_to_bytes(uint64((epoch + node_offset) // config.EPOCHS_PER_SUBNET_SUBSCRIPTION))
    )
    permutated_prefix = compute_shuffled_index(
        node_id_prefix,
        1 << config.ATTESTATION_SUBNET_PREFIX_BITS,
        permutation_seed,
    )
    return SubnetID((permutated_prefix + index) % config.ATTESTATION_SUBNET_COUNT)


def compute_subscribed_subnets(node_id: NodeID, epoch: Epoch) -> Sequence[SubnetID]:
    return [
        compute_subscribed_subnet(node_id, epoch, index) for index in range(config.SUBNETS_PER_NODE)
    ]


def check_if_validator_active(state: BeaconState, validator_index: ValidatorIndex) -> bool:
    validator = state.validators[validator_index]
    return is_active_validator(validator, get_current_epoch(state))


def get_committee_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> tuple[Sequence[ValidatorIndex], CommitteeIndex, Slot] | None:
    """
    Return the committee assignment in the ``epoch`` for ``validator_index``.
    ``assignment`` returned is a tuple of the following form:
        * ``assignment[0]`` is the list of validators in the committee
        * ``assignment[1]`` is the index to which the committee is assigned
        * ``assignment[2]`` is the slot at which the committee is assigned
    Return None if no assignment.
    """
    next_epoch = Epoch(get_current_epoch(state) + 1)
    assert epoch <= next_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    committee_count_per_slot = get_committee_count_per_slot(state, epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        for index in range(committee_count_per_slot):
            committee = get_beacon_committee(state, Slot(slot), CommitteeIndex(index))
            if validator_index in committee:
                return committee, CommitteeIndex(index), Slot(slot)
    return None


def is_proposer(state: BeaconState, validator_index: ValidatorIndex) -> bool:
    return get_beacon_proposer_index(state) == validator_index


def get_epoch_signature(state: BeaconState, block: BeaconBlock, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_RANDAO, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(compute_epoch_at_slot(block.slot), domain)
    return bls.Sign(privkey, signing_root)


def voting_period_start_time(state: BeaconState) -> uint64:
    eth1_voting_period_start_slot = Slot(
        state.slot - state.slot % (EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH)
    )
    return compute_time_at_slot(state, eth1_voting_period_start_slot)


def is_candidate_block(block: Eth1Block, period_start: uint64) -> bool:
    return (
        block.timestamp + config.SECONDS_PER_ETH1_BLOCK * config.ETH1_FOLLOW_DISTANCE
        <= period_start
        and block.timestamp + config.SECONDS_PER_ETH1_BLOCK * config.ETH1_FOLLOW_DISTANCE * 2
        >= period_start
    )


def get_eth1_vote(state: BeaconState, eth1_chain: Sequence[Eth1Block]) -> Eth1Data:
    period_start = voting_period_start_time(state)
    # `eth1_chain` abstractly represents all blocks in the eth1 chain sorted by ascending block height
    votes_to_consider = [
        get_eth1_data(block)
        for block in eth1_chain
        if (
            is_candidate_block(block, period_start)
            # Ensure cannot move back to earlier deposit contract states
            and get_eth1_data(block).deposit_count >= state.eth1_data.deposit_count
        )
    ]

    # Valid votes already cast during this period
    valid_votes = [vote for vote in state.eth1_data_votes if vote in votes_to_consider]

    # Default vote on latest eth1 block data in the period range unless eth1 chain is not live
    # Non-substantive casting for linter
    state_eth1_data: Eth1Data = state.eth1_data
    default_vote = (
        votes_to_consider[len(votes_to_consider) - 1] if any(votes_to_consider) else state_eth1_data
    )

    return max(
        valid_votes,
        # Tiebreak by smallest distance
        key=lambda v: (
            valid_votes.count(v),
            -valid_votes.index(v),
        ),
        default=default_vote,
    )


def compute_new_state_root(state: BeaconState, block: BeaconBlock) -> Root:
    temp_state: BeaconState = state.copy()
    signed_block = SignedBeaconBlock(message=block)
    state_transition(temp_state, signed_block, validate_result=False)
    return hash_tree_root(temp_state)


def get_block_signature(state: BeaconState, block: BeaconBlock, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(block, domain)
    return bls.Sign(privkey, signing_root)


def get_attestation_signature(
    state: BeaconState, attestation_data: AttestationData, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, attestation_data.target.epoch)
    signing_root = compute_signing_root(attestation_data, domain)
    return bls.Sign(privkey, signing_root)


def compute_subnet_for_attestation(
    committees_per_slot: uint64, slot: Slot, committee_index: CommitteeIndex
) -> SubnetID:
    """
    Compute the correct subnet for an attestation for Phase 0.
    Note, this mimics expected future behavior where attestations will be mapped to their shard subnet.
    """
    slots_since_epoch_start = uint64(slot % SLOTS_PER_EPOCH)
    committees_since_epoch_start = committees_per_slot * slots_since_epoch_start

    return SubnetID(
        (committees_since_epoch_start + committee_index) % config.ATTESTATION_SUBNET_COUNT
    )


def get_slot_signature(state: BeaconState, slot: Slot, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_SELECTION_PROOF, compute_epoch_at_slot(slot))
    signing_root = compute_signing_root(slot, domain)
    return bls.Sign(privkey, signing_root)


def is_aggregator(
    state: BeaconState, slot: Slot, index: CommitteeIndex, slot_signature: BLSSignature
) -> bool:
    committee = get_beacon_committee(state, slot, index)
    modulo = max(1, len(committee) // TARGET_AGGREGATORS_PER_COMMITTEE)
    return bytes_to_uint64(hash(slot_signature)[0:8]) % modulo == 0


def get_aggregate_signature(attestations: Sequence[Attestation]) -> BLSSignature:
    signatures = [attestation.signature for attestation in attestations]
    return bls.Aggregate(signatures)


def get_aggregate_and_proof(
    state: BeaconState, aggregator_index: ValidatorIndex, aggregate: Attestation, privkey: int
) -> AggregateAndProof:
    return AggregateAndProof(
        aggregator_index=aggregator_index,
        aggregate=aggregate,
        selection_proof=get_slot_signature(state, aggregate.data.slot, privkey),
    )


def get_aggregate_and_proof_signature(
    state: BeaconState, aggregate_and_proof: AggregateAndProof, privkey: int
) -> BLSSignature:
    aggregate = aggregate_and_proof.aggregate
    domain = get_domain(
        state, DOMAIN_AGGREGATE_AND_PROOF, compute_epoch_at_slot(aggregate.data.slot)
    )
    signing_root = compute_signing_root(aggregate_and_proof, domain)
    return bls.Sign(privkey, signing_root)


def compute_weak_subjectivity_period(state: BeaconState) -> uint64:
    """
    Returns the weak subjectivity period for the current ``state``.
    This computation takes into account the effect of:
        - validator set churn (bounded by ``get_validator_churn_limit()`` per epoch), and
        - validator balance top-ups (bounded by ``MAX_DEPOSITS * SLOTS_PER_EPOCH`` per epoch).
    A detailed calculation can be found at:
    https://github.com/runtimeverification/beacon-chain-verification/blob/master/weak-subjectivity/weak-subjectivity-analysis.pdf
    """
    ws_period = config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    N = len(get_active_validator_indices(state, get_current_epoch(state)))
    t = get_total_active_balance(state) // N // ETH_TO_GWEI
    T = MAX_EFFECTIVE_BALANCE // ETH_TO_GWEI
    delta = get_validator_churn_limit(state)
    Delta = MAX_DEPOSITS * SLOTS_PER_EPOCH
    D = SAFETY_DECAY

    if T * (200 + 3 * D) < t * (200 + 12 * D):
        epochs_for_validator_set_churn = (
            N * (t * (200 + 12 * D) - T * (200 + 3 * D)) // (600 * delta * (2 * t + T))
        )
        epochs_for_balance_top_ups = N * (200 + 3 * D) // (600 * Delta)
        ws_period += max(epochs_for_validator_set_churn, epochs_for_balance_top_ups)
    else:
        ws_period += 3 * N * D * t // (200 * Delta * (T - t))

    return ws_period


def is_within_weak_subjectivity_period(
    store: Store, ws_state: BeaconState, ws_checkpoint: Checkpoint
) -> bool:
    # Clients may choose to validate the input state against the input Weak Subjectivity Checkpoint
    assert get_block_root(ws_state, ws_checkpoint.epoch) == ws_checkpoint.root
    assert compute_epoch_at_slot(ws_state.slot) == ws_checkpoint.epoch

    ws_period = compute_weak_subjectivity_period(ws_state)
    ws_state_epoch = compute_epoch_at_slot(ws_state.slot)
    current_epoch = compute_epoch_at_slot(get_current_slot(store))
    return current_epoch <= ws_state_epoch + ws_period


def add_flag(flags: ParticipationFlags, flag_index: int) -> ParticipationFlags:
    """
    Return a new ``ParticipationFlags`` adding ``flag_index`` to ``flags``.
    """
    flag = ParticipationFlags(2**flag_index)
    return flags | flag


def has_flag(flags: ParticipationFlags, flag_index: int) -> bool:
    """
    Return whether ``flags`` has ``flag_index`` set.
    """
    flag = ParticipationFlags(2**flag_index)
    return flags & flag == flag


def get_index_for_new_validator(state: BeaconState) -> ValidatorIndex:
    return ValidatorIndex(len(state.validators))


def set_or_append_list(list: List, index: ValidatorIndex, value: Any) -> None:
    if index == len(list):
        list.append(value)
    else:
        list[index] = value


def get_next_sync_committee_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    """
    Return the sync committee indices, with possible duplicates, for the next sync committee.
    """
    epoch = Epoch(get_current_epoch(state) + 1)

    MAX_RANDOM_BYTE = 2**8 - 1
    active_validator_indices = get_active_validator_indices(state, epoch)
    active_validator_count = uint64(len(active_validator_indices))
    seed = get_seed(state, epoch, DOMAIN_SYNC_COMMITTEE)
    i = 0
    sync_committee_indices: List[ValidatorIndex] = []
    while len(sync_committee_indices) < SYNC_COMMITTEE_SIZE:
        shuffled_index = compute_shuffled_index(
            uint64(i % active_validator_count), active_validator_count, seed
        )
        candidate_index = active_validator_indices[shuffled_index]
        random_byte = hash(seed + uint_to_bytes(uint64(i // 32)))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            sync_committee_indices.append(candidate_index)
        i += 1
    return sync_committee_indices


def get_next_sync_committee(state: BeaconState) -> SyncCommittee:
    """
    Return the next sync committee, with possible pubkey duplicates.
    """
    indices = get_next_sync_committee_indices(state)
    pubkeys = [state.validators[index].pubkey for index in indices]
    aggregate_pubkey = eth_aggregate_pubkeys(pubkeys)
    return SyncCommittee(pubkeys=pubkeys, aggregate_pubkey=aggregate_pubkey)


def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR
        // integer_squareroot(get_total_active_balance(state))
    )


def get_unslashed_participating_indices(
    state: BeaconState, flag_index: int, epoch: Epoch
) -> set[ValidatorIndex]:
    """
    Return the set of validator indices that are both active and unslashed for the given ``flag_index`` and ``epoch``.
    """
    assert epoch in (get_previous_epoch(state), get_current_epoch(state))
    if epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    active_validator_indices = get_active_validator_indices(state, epoch)
    participating_indices = [
        i for i in active_validator_indices if has_flag(epoch_participation[i], flag_index)
    ]
    return set(filter(lambda index: not state.validators[index].slashed, participating_indices))


def get_attestation_participation_flag_indices(
    state: BeaconState, data: AttestationData, inclusion_delay: uint64
) -> Sequence[int]:
    """
    Return the flag indices that are satisfied by an attestation.
    """
    # Matching source
    if data.target.epoch == get_current_epoch(state):
        justified_checkpoint = state.current_justified_checkpoint
    else:
        justified_checkpoint = state.previous_justified_checkpoint
    is_matching_source = data.source == justified_checkpoint

    # Matching target
    target_root = get_block_root(state, data.target.epoch)
    target_root_matches = data.target.root == target_root
    is_matching_target = is_matching_source and target_root_matches

    # Matching head
    head_root = get_block_root_at_slot(state, data.slot)
    head_root_matches = data.beacon_block_root == head_root
    is_matching_head = is_matching_target and head_root_matches

    assert is_matching_source

    participation_flag_indices = []
    if is_matching_source and inclusion_delay <= integer_squareroot(SLOTS_PER_EPOCH):
        participation_flag_indices.append(TIMELY_SOURCE_FLAG_INDEX)
    if is_matching_target and inclusion_delay <= SLOTS_PER_EPOCH:
        participation_flag_indices.append(TIMELY_TARGET_FLAG_INDEX)
    if is_matching_head and inclusion_delay == MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flag_indices.append(TIMELY_HEAD_FLAG_INDEX)

    return participation_flag_indices


def get_flag_index_deltas(
    state: BeaconState, flag_index: int
) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the deltas for a given ``flag_index`` by scanning through the participation flags.
    """
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
    previous_epoch = get_previous_epoch(state)
    unslashed_participating_indices = get_unslashed_participating_indices(
        state, flag_index, previous_epoch
    )
    weight = PARTICIPATION_FLAG_WEIGHTS[flag_index]
    unslashed_participating_balance = get_total_balance(state, unslashed_participating_indices)
    unslashed_participating_increments = (
        unslashed_participating_balance // EFFECTIVE_BALANCE_INCREMENT
    )
    active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    for index in get_eligible_validator_indices(state):
        base_reward = get_base_reward(state, index)
        if index in unslashed_participating_indices:
            if not is_in_inactivity_leak(state):
                reward_numerator = base_reward * weight * unslashed_participating_increments
                rewards[index] += Gwei(reward_numerator // (active_increments * WEIGHT_DENOMINATOR))
        elif flag_index != TIMELY_HEAD_FLAG_INDEX:
            penalties[index] += Gwei(base_reward * weight // WEIGHT_DENOMINATOR)
    return rewards, penalties


def process_sync_aggregate(state: BeaconState, sync_aggregate: SyncAggregate) -> None:
    # Verify sync committee aggregate signature signing over the previous slot block root
    committee_pubkeys = state.current_sync_committee.pubkeys
    committee_bits = sync_aggregate.sync_committee_bits
    if sum(committee_bits) == SYNC_COMMITTEE_SIZE:
        # All members participated - use precomputed aggregate key
        participant_pubkeys = [state.current_sync_committee.aggregate_pubkey]
    elif sum(committee_bits) > SYNC_COMMITTEE_SIZE // 2:
        # More than half participated - subtract non-participant keys.
        # First determine nonparticipating members
        non_participant_pubkeys = [
            pubkey for pubkey, bit in zip(committee_pubkeys, committee_bits) if not bit
        ]
        # Compute aggregate of non-participants
        non_participant_aggregate = eth_aggregate_pubkeys(non_participant_pubkeys)
        # Subtract non-participants from the full aggregate
        # This is equivalent to: aggregate_pubkey + (-non_participant_aggregate)
        participant_pubkey = bls.add(
            bls.bytes48_to_G1(state.current_sync_committee.aggregate_pubkey),
            bls.neg(bls.bytes48_to_G1(non_participant_aggregate)),
        )
        participant_pubkeys = [BLSPubkey(bls.G1_to_bytes48(participant_pubkey))]
    else:
        # Less than half participated - aggregate participant keys
        participant_pubkeys = [
            pubkey
            for pubkey, bit in zip(committee_pubkeys, sync_aggregate.sync_committee_bits)
            if bit
        ]
    previous_slot = max(state.slot, Slot(1)) - Slot(1)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(previous_slot))
    signing_root = compute_signing_root(get_block_root_at_slot(state, previous_slot), domain)
    # Note: eth_fast_aggregate_verify works with a singleton list containing an aggregated key
    assert eth_fast_aggregate_verify(
        participant_pubkeys, signing_root, sync_aggregate.sync_committee_signature
    )

    # Compute participant and proposer rewards
    total_active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    total_base_rewards = Gwei(get_base_reward_per_increment(state) * total_active_increments)
    max_participant_rewards = Gwei(
        total_base_rewards * SYNC_REWARD_WEIGHT // WEIGHT_DENOMINATOR // SLOTS_PER_EPOCH
    )
    participant_reward = Gwei(max_participant_rewards // SYNC_COMMITTEE_SIZE)
    proposer_reward = Gwei(
        participant_reward * PROPOSER_WEIGHT // (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT)
    )

    # Apply participant and proposer rewards
    all_pubkeys = [v.pubkey for v in state.validators]
    committee_indices = [
        ValidatorIndex(all_pubkeys.index(pubkey)) for pubkey in state.current_sync_committee.pubkeys
    ]
    for participant_index, participation_bit in zip(
        committee_indices, sync_aggregate.sync_committee_bits
    ):
        if participation_bit:
            increase_balance(state, participant_index, participant_reward)
            increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
        else:
            decrease_balance(state, participant_index, participant_reward)


def process_inactivity_updates(state: BeaconState) -> None:
    # Skip the genesis epoch as score updates are based on the previous epoch participation
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    for index in get_eligible_validator_indices(state):
        # Increase the inactivity score of inactive validators
        if index in get_unslashed_participating_indices(
            state, TIMELY_TARGET_FLAG_INDEX, get_previous_epoch(state)
        ):
            state.inactivity_scores[index] -= min(1, state.inactivity_scores[index])
        else:
            state.inactivity_scores[index] += config.INACTIVITY_SCORE_BIAS
        # Decrease the inactivity score of all eligible validators during a leak-free epoch
        if not is_in_inactivity_leak(state):
            state.inactivity_scores[index] -= min(
                config.INACTIVITY_SCORE_RECOVERY_RATE, state.inactivity_scores[index]
            )


def process_participation_flag_updates(state: BeaconState) -> None:
    state.previous_epoch_participation = state.current_epoch_participation
    state.current_epoch_participation = [
        ParticipationFlags(0b0000_0000) for _ in range(len(state.validators))
    ]


def process_sync_committee_updates(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + Epoch(1)
    if next_epoch % EPOCHS_PER_SYNC_COMMITTEE_PERIOD == 0:
        state.current_sync_committee = state.next_sync_committee
        state.next_sync_committee = get_next_sync_committee(state)


def eth_aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    return bls.AggregatePKs(pubkeys)


def eth_fast_aggregate_verify(
    pubkeys: Sequence[BLSPubkey], message: Bytes32, signature: BLSSignature
) -> bool:
    """
    Wrapper to ``bls.FastAggregateVerify`` accepting the ``G2_POINT_AT_INFINITY`` signature when ``pubkeys`` is empty.
    """
    if len(pubkeys) == 0 and signature == G2_POINT_AT_INFINITY:
        return True
    return bls.FastAggregateVerify(pubkeys, message, signature)


def get_sync_message_due_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(config.SYNC_MESSAGE_DUE_BPS)


def get_contribution_due_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(config.CONTRIBUTION_DUE_BPS)


def translate_participation(
    state: BeaconState, pending_attestations: Sequence[phase0.PendingAttestation]
) -> None:
    for attestation in pending_attestations:
        data = attestation.data
        inclusion_delay = attestation.inclusion_delay
        # Translate attestation inclusion info to flag indices
        participation_flag_indices = get_attestation_participation_flag_indices(
            state, data, inclusion_delay
        )

        # Apply flags to all attesting validators
        epoch_participation = state.previous_epoch_participation
        for index in get_attesting_indices(state, attestation):
            for flag_index in participation_flag_indices:
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)


def upgrade_to_altair(pre: phase0.BeaconState) -> BeaconState:
    epoch = phase0.get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=config.ALTAIR_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=pre.validators,
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        previous_epoch_participation=[
            ParticipationFlags(0b0000_0000) for _ in range(len(pre.validators))
        ],
        current_epoch_participation=[
            ParticipationFlags(0b0000_0000) for _ in range(len(pre.validators))
        ],
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        inactivity_scores=[uint64(0) for _ in range(len(pre.validators))],
    )
    # Fill in previous epoch participation from the pre state's pending attestations
    translate_participation(post, pre.previous_epoch_attestations)

    # Fill in sync committees
    # Note: A duplicate committee is assigned for the current and next committee at the fork boundary
    post.current_sync_committee = get_next_sync_committee(post)
    post.next_sync_committee = get_next_sync_committee(post)
    return post


def get_sync_subcommittee_pubkeys(
    state: BeaconState, subcommittee_index: uint64
) -> Sequence[BLSPubkey]:
    # Committees assigned to `slot` sign for `slot - 1`
    # This creates the exceptional logic below when transitioning between sync committee periods
    next_slot_epoch = compute_epoch_at_slot(Slot(state.slot + 1))
    if compute_sync_committee_period(get_current_epoch(state)) == compute_sync_committee_period(
        next_slot_epoch
    ):
        sync_committee = state.current_sync_committee
    else:
        sync_committee = state.next_sync_committee

    # Return pubkeys for the subcommittee index
    sync_subcommittee_size = SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT
    i = subcommittee_index * sync_subcommittee_size
    return sync_committee.pubkeys[i : i + sync_subcommittee_size]


def compute_sync_committee_period(epoch: Epoch) -> uint64:
    return epoch // EPOCHS_PER_SYNC_COMMITTEE_PERIOD


def is_assigned_to_sync_committee(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> bool:
    sync_committee_period = compute_sync_committee_period(epoch)
    current_epoch = get_current_epoch(state)
    current_sync_committee_period = compute_sync_committee_period(current_epoch)
    next_sync_committee_period = current_sync_committee_period + 1
    assert sync_committee_period in (current_sync_committee_period, next_sync_committee_period)

    pubkey = state.validators[validator_index].pubkey
    if sync_committee_period == current_sync_committee_period:
        return pubkey in state.current_sync_committee.pubkeys
    else:  # sync_committee_period == next_sync_committee_period
        return pubkey in state.next_sync_committee.pubkeys


def process_sync_committee_contributions(
    block: BeaconBlock, contributions: set[SyncCommitteeContribution]
) -> None:
    sync_aggregate = SyncAggregate()
    signatures = []
    sync_subcommittee_size = SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT

    for contribution in contributions:
        subcommittee_index = contribution.subcommittee_index
        for index, participated in enumerate(contribution.aggregation_bits):
            if participated:
                participant_index = sync_subcommittee_size * subcommittee_index + index
                sync_aggregate.sync_committee_bits[participant_index] = True
        signatures.append(contribution.signature)

    sync_aggregate.sync_committee_signature = bls.Aggregate(signatures)

    block.body.sync_aggregate = sync_aggregate


def get_sync_committee_message(
    state: BeaconState, block_root: Root, validator_index: ValidatorIndex, privkey: int
) -> SyncCommitteeMessage:
    epoch = get_current_epoch(state)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = compute_signing_root(block_root, domain)
    signature = bls.Sign(privkey, signing_root)

    return SyncCommitteeMessage(
        slot=state.slot,
        beacon_block_root=block_root,
        validator_index=validator_index,
        signature=signature,
    )


def compute_subnets_for_sync_committee(
    state: BeaconState, validator_index: ValidatorIndex
) -> set[SubnetID]:
    next_slot_epoch = compute_epoch_at_slot(Slot(state.slot + 1))
    if compute_sync_committee_period(get_current_epoch(state)) == compute_sync_committee_period(
        next_slot_epoch
    ):
        sync_committee = state.current_sync_committee
    else:
        sync_committee = state.next_sync_committee

    target_pubkey = state.validators[validator_index].pubkey
    sync_committee_indices = [
        index for index, pubkey in enumerate(sync_committee.pubkeys) if pubkey == target_pubkey
    ]
    return set(
        [
            SubnetID(index // (SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT))
            for index in sync_committee_indices
        ]
    )


def get_sync_committee_selection_proof(
    state: BeaconState, slot: Slot, subcommittee_index: uint64, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF, compute_epoch_at_slot(slot))
    signing_data = SyncAggregatorSelectionData(
        slot=slot,
        subcommittee_index=subcommittee_index,
    )
    signing_root = compute_signing_root(signing_data, domain)
    return bls.Sign(privkey, signing_root)


def is_sync_committee_aggregator(signature: BLSSignature) -> bool:
    modulo = max(
        1,
        SYNC_COMMITTEE_SIZE
        // SYNC_COMMITTEE_SUBNET_COUNT
        // TARGET_AGGREGATORS_PER_SYNC_SUBCOMMITTEE,
    )
    return bytes_to_uint64(hash(signature)[0:8]) % modulo == 0


def get_contribution_and_proof(
    state: BeaconState,
    aggregator_index: ValidatorIndex,
    contribution: SyncCommitteeContribution,
    privkey: int,
) -> ContributionAndProof:
    selection_proof = get_sync_committee_selection_proof(
        state,
        contribution.slot,
        contribution.subcommittee_index,
        privkey,
    )
    return ContributionAndProof(
        aggregator_index=aggregator_index,
        contribution=contribution,
        selection_proof=selection_proof,
    )


def get_contribution_and_proof_signature(
    state: BeaconState, contribution_and_proof: ContributionAndProof, privkey: int
) -> BLSSignature:
    contribution = contribution_and_proof.contribution
    domain = get_domain(
        state, DOMAIN_CONTRIBUTION_AND_PROOF, compute_epoch_at_slot(contribution.slot)
    )
    signing_root = compute_signing_root(contribution_and_proof, domain)
    return bls.Sign(privkey, signing_root)


def block_to_light_client_header(block: SignedBeaconBlock) -> LightClientHeader:
    epoch = compute_epoch_at_slot(block.message.slot)

    if epoch >= config.CAPELLA_FORK_EPOCH:
        payload = block.message.body.execution_payload
        execution_header = ExecutionPayloadHeader(
            parent_hash=payload.parent_hash,
            fee_recipient=payload.fee_recipient,
            state_root=payload.state_root,
            receipts_root=payload.receipts_root,
            logs_bloom=payload.logs_bloom,
            prev_randao=payload.prev_randao,
            block_number=payload.block_number,
            gas_limit=payload.gas_limit,
            gas_used=payload.gas_used,
            timestamp=payload.timestamp,
            extra_data=payload.extra_data,
            base_fee_per_gas=payload.base_fee_per_gas,
            block_hash=payload.block_hash,
            transactions_root=hash_tree_root(payload.transactions),
            withdrawals_root=hash_tree_root(payload.withdrawals),
        )
        execution_branch = ExecutionBranch(
            compute_merkle_proof(block.message.body, EXECUTION_PAYLOAD_GINDEX)
        )
    else:
        # Note that during fork transitions, `finalized_header` may still point to earlier forks.
        # While Bellatrix blocks also contain an `ExecutionPayload` (minus `withdrawals_root`),
        # it was not included in the corresponding light client data. To ensure compatibility
        # with legacy data going through `upgrade_lc_header_to_capella`, leave out execution data.
        execution_header = ExecutionPayloadHeader()
        execution_branch = ExecutionBranch()

    return LightClientHeader(
        beacon=BeaconBlockHeader(
            slot=block.message.slot,
            proposer_index=block.message.proposer_index,
            parent_root=block.message.parent_root,
            state_root=block.message.state_root,
            body_root=hash_tree_root(block.message.body),
        ),
        execution=execution_header,
        execution_branch=execution_branch,
    )


def create_light_client_bootstrap(
    state: BeaconState, block: SignedBeaconBlock
) -> LightClientBootstrap:
    assert compute_epoch_at_slot(state.slot) >= config.ALTAIR_FORK_EPOCH

    assert state.slot == state.latest_block_header.slot
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    assert hash_tree_root(header) == hash_tree_root(block.message)

    return LightClientBootstrap(
        header=block_to_light_client_header(block),
        current_sync_committee=state.current_sync_committee,
        current_sync_committee_branch=CurrentSyncCommitteeBranch(
            compute_merkle_proof(state, current_sync_committee_gindex_at_slot(state.slot))
        ),
    )


def create_light_client_update(
    state: BeaconState,
    block: SignedBeaconBlock,
    attested_state: BeaconState,
    attested_block: SignedBeaconBlock,
    finalized_block: SignedBeaconBlock | None,
) -> LightClientUpdate:
    assert compute_epoch_at_slot(attested_state.slot) >= config.ALTAIR_FORK_EPOCH
    assert (
        sum(block.message.body.sync_aggregate.sync_committee_bits)
        >= MIN_SYNC_COMMITTEE_PARTICIPANTS
    )

    assert state.slot == state.latest_block_header.slot
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    assert hash_tree_root(header) == hash_tree_root(block.message)
    update_signature_period = compute_sync_committee_period_at_slot(block.message.slot)

    assert attested_state.slot == attested_state.latest_block_header.slot
    attested_header = attested_state.latest_block_header.copy()
    attested_header.state_root = hash_tree_root(attested_state)
    assert (
        hash_tree_root(attested_header)
        == hash_tree_root(attested_block.message)
        == block.message.parent_root
    )
    update_attested_period = compute_sync_committee_period_at_slot(attested_block.message.slot)

    update = LightClientUpdate()

    update.attested_header = block_to_light_client_header(attested_block)

    # `next_sync_committee` is only useful if the message is signed by the current sync committee
    if update_attested_period == update_signature_period:
        update.next_sync_committee = attested_state.next_sync_committee
        update.next_sync_committee_branch = NextSyncCommitteeBranch(
            compute_merkle_proof(
                attested_state, next_sync_committee_gindex_at_slot(attested_state.slot)
            )
        )

    # Indicate finality whenever possible
    if finalized_block is not None:
        if finalized_block.message.slot != GENESIS_SLOT:
            update.finalized_header = block_to_light_client_header(finalized_block)
            assert (
                hash_tree_root(update.finalized_header.beacon)
                == attested_state.finalized_checkpoint.root
            )
        else:
            assert attested_state.finalized_checkpoint.root == Bytes32()
        update.finality_branch = FinalityBranch(
            compute_merkle_proof(attested_state, finalized_root_gindex_at_slot(attested_state.slot))
        )

    update.sync_aggregate = block.message.body.sync_aggregate
    update.signature_slot = block.message.slot

    return update


def create_light_client_finality_update(update: LightClientUpdate) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=update.attested_header,
        finalized_header=update.finalized_header,
        finality_branch=update.finality_branch,
        sync_aggregate=update.sync_aggregate,
        signature_slot=update.signature_slot,
    )


def create_light_client_optimistic_update(update: LightClientUpdate) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=update.attested_header,
        sync_aggregate=update.sync_aggregate,
        signature_slot=update.signature_slot,
    )


def finalized_root_gindex_at_slot(_slot: Slot) -> GeneralizedIndex:
    return FINALIZED_ROOT_GINDEX


def current_sync_committee_gindex_at_slot(_slot: Slot) -> GeneralizedIndex:
    return CURRENT_SYNC_COMMITTEE_GINDEX


def next_sync_committee_gindex_at_slot(_slot: Slot) -> GeneralizedIndex:
    return NEXT_SYNC_COMMITTEE_GINDEX


def is_valid_light_client_header(header: LightClientHeader) -> bool:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    if epoch < config.CAPELLA_FORK_EPOCH:
        return (
            header.execution == ExecutionPayloadHeader()
            and header.execution_branch == ExecutionBranch()
        )

    return is_valid_merkle_branch(
        leaf=get_lc_execution_root(header),
        branch=header.execution_branch,
        depth=floorlog2(EXECUTION_PAYLOAD_GINDEX),
        index=get_subtree_index(EXECUTION_PAYLOAD_GINDEX),
        root=header.beacon.body_root,
    )


def is_sync_committee_update(update: LightClientUpdate) -> bool:
    return update.next_sync_committee_branch != NextSyncCommitteeBranch()


def is_finality_update(update: LightClientUpdate) -> bool:
    return update.finality_branch != FinalityBranch()


def is_better_update(new_update: LightClientUpdate, old_update: LightClientUpdate) -> bool:
    # Compare supermajority (> 2/3) sync committee participation
    max_active_participants = len(new_update.sync_aggregate.sync_committee_bits)
    new_num_active_participants = sum(new_update.sync_aggregate.sync_committee_bits)
    old_num_active_participants = sum(old_update.sync_aggregate.sync_committee_bits)
    new_has_supermajority = new_num_active_participants * 3 >= max_active_participants * 2
    old_has_supermajority = old_num_active_participants * 3 >= max_active_participants * 2
    if new_has_supermajority != old_has_supermajority:
        return new_has_supermajority
    if not new_has_supermajority and new_num_active_participants != old_num_active_participants:
        return new_num_active_participants > old_num_active_participants

    # Compare presence of relevant sync committee
    new_has_relevant_sync_committee = is_sync_committee_update(new_update) and (
        compute_sync_committee_period_at_slot(new_update.attested_header.beacon.slot)
        == compute_sync_committee_period_at_slot(new_update.signature_slot)
    )
    old_has_relevant_sync_committee = is_sync_committee_update(old_update) and (
        compute_sync_committee_period_at_slot(old_update.attested_header.beacon.slot)
        == compute_sync_committee_period_at_slot(old_update.signature_slot)
    )
    if new_has_relevant_sync_committee != old_has_relevant_sync_committee:
        return new_has_relevant_sync_committee

    # Compare indication of any finality
    new_has_finality = is_finality_update(new_update)
    old_has_finality = is_finality_update(old_update)
    if new_has_finality != old_has_finality:
        return new_has_finality

    # Compare sync committee finality
    if new_has_finality:
        new_has_sync_committee_finality = compute_sync_committee_period_at_slot(
            new_update.finalized_header.beacon.slot
        ) == compute_sync_committee_period_at_slot(new_update.attested_header.beacon.slot)
        old_has_sync_committee_finality = compute_sync_committee_period_at_slot(
            old_update.finalized_header.beacon.slot
        ) == compute_sync_committee_period_at_slot(old_update.attested_header.beacon.slot)
        if new_has_sync_committee_finality != old_has_sync_committee_finality:
            return new_has_sync_committee_finality

    # Tiebreaker 1: Sync committee participation beyond supermajority
    if new_num_active_participants != old_num_active_participants:
        return new_num_active_participants > old_num_active_participants

    # Tiebreaker 2: Prefer older data (fewer changes to best)
    if new_update.attested_header.beacon.slot != old_update.attested_header.beacon.slot:
        return new_update.attested_header.beacon.slot < old_update.attested_header.beacon.slot

    # Tiebreaker 3: Prefer updates with earlier signature slots
    return new_update.signature_slot < old_update.signature_slot


def is_next_sync_committee_known(store: LightClientStore) -> bool:
    return store.next_sync_committee != SyncCommittee()


def get_safety_threshold(store: LightClientStore) -> uint64:
    return (
        max(
            store.previous_max_active_participants,
            store.current_max_active_participants,
        )
        // 2
    )


def get_subtree_index(generalized_index: GeneralizedIndex) -> uint64:
    return uint64(generalized_index % 2 ** (floorlog2(generalized_index)))


def is_valid_normalized_merkle_branch(
    leaf: Bytes32, branch: Sequence[Bytes32], gindex: GeneralizedIndex, root: Root
) -> bool:
    depth = floorlog2(gindex)
    index = get_subtree_index(gindex)
    num_extra = len(branch) - depth
    for i in range(num_extra):
        if branch[i] != Bytes32():
            return False
    return is_valid_merkle_branch(leaf, branch[num_extra:], depth, index, root)


def compute_sync_committee_period_at_slot(slot: Slot) -> uint64:
    return compute_sync_committee_period(compute_epoch_at_slot(slot))


def initialize_light_client_store(
    trusted_block_root: Root, bootstrap: LightClientBootstrap
) -> LightClientStore:
    assert is_valid_light_client_header(bootstrap.header)
    assert hash_tree_root(bootstrap.header.beacon) == trusted_block_root

    assert is_valid_normalized_merkle_branch(
        leaf=hash_tree_root(bootstrap.current_sync_committee),
        branch=bootstrap.current_sync_committee_branch,
        gindex=current_sync_committee_gindex_at_slot(bootstrap.header.beacon.slot),
        root=bootstrap.header.beacon.state_root,
    )

    return LightClientStore(
        finalized_header=bootstrap.header,
        current_sync_committee=bootstrap.current_sync_committee,
        next_sync_committee=SyncCommittee(),
        best_valid_update=None,
        optimistic_header=bootstrap.header,
        previous_max_active_participants=0,
        current_max_active_participants=0,
    )


def validate_light_client_update(
    store: LightClientStore,
    update: LightClientUpdate,
    current_slot: Slot,
    genesis_validators_root: Root,
) -> None:
    # Verify sync committee has sufficient participants
    sync_aggregate = update.sync_aggregate
    assert sum(sync_aggregate.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    # Verify update does not skip a sync committee period
    assert is_valid_light_client_header(update.attested_header)
    update_attested_slot = update.attested_header.beacon.slot
    update_finalized_slot = update.finalized_header.beacon.slot
    assert current_slot >= update.signature_slot > update_attested_slot >= update_finalized_slot
    store_period = compute_sync_committee_period_at_slot(store.finalized_header.beacon.slot)
    update_signature_period = compute_sync_committee_period_at_slot(update.signature_slot)
    if is_next_sync_committee_known(store):
        assert update_signature_period in (store_period, store_period + 1)
    else:
        assert update_signature_period == store_period

    # Verify update is relevant
    update_attested_period = compute_sync_committee_period_at_slot(update_attested_slot)
    update_has_next_sync_committee = not is_next_sync_committee_known(store) and (
        is_sync_committee_update(update) and update_attested_period == store_period
    )
    assert (
        update_attested_slot > store.finalized_header.beacon.slot or update_has_next_sync_committee
    )

    # Verify that the `finality_branch`, if present, confirms `finalized_header`
    # to match the finalized checkpoint root saved in the state of `attested_header`.
    # Note that the genesis finalized checkpoint root is represented as a zero hash.
    if not is_finality_update(update):
        assert update.finalized_header == LightClientHeader()
    else:
        if update_finalized_slot == GENESIS_SLOT:
            assert update.finalized_header == LightClientHeader()
            finalized_root = Bytes32()
        else:
            assert is_valid_light_client_header(update.finalized_header)
            finalized_root = hash_tree_root(update.finalized_header.beacon)
        assert is_valid_normalized_merkle_branch(
            leaf=finalized_root,
            branch=update.finality_branch,
            gindex=finalized_root_gindex_at_slot(update.attested_header.beacon.slot),
            root=update.attested_header.beacon.state_root,
        )

    # Verify that the `next_sync_committee`, if present, actually is the next sync committee saved in the
    # state of the `attested_header`
    if not is_sync_committee_update(update):
        assert update.next_sync_committee == SyncCommittee()
    else:
        if update_attested_period == store_period and is_next_sync_committee_known(store):
            assert update.next_sync_committee == store.next_sync_committee
        assert is_valid_normalized_merkle_branch(
            leaf=hash_tree_root(update.next_sync_committee),
            branch=update.next_sync_committee_branch,
            gindex=next_sync_committee_gindex_at_slot(update.attested_header.beacon.slot),
            root=update.attested_header.beacon.state_root,
        )

    # Verify sync committee aggregate signature
    if update_signature_period == store_period:
        sync_committee = store.current_sync_committee
    else:
        sync_committee = store.next_sync_committee
    participant_pubkeys = [
        pubkey
        for (bit, pubkey) in zip(sync_aggregate.sync_committee_bits, sync_committee.pubkeys)
        if bit
    ]
    fork_version_slot = max(update.signature_slot, Slot(1)) - Slot(1)
    fork_version = compute_fork_version(compute_epoch_at_slot(fork_version_slot))
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, fork_version, genesis_validators_root)
    signing_root = compute_signing_root(update.attested_header.beacon, domain)
    assert bls.FastAggregateVerify(
        participant_pubkeys, signing_root, sync_aggregate.sync_committee_signature
    )


def apply_light_client_update(store: LightClientStore, update: LightClientUpdate) -> None:
    store_period = compute_sync_committee_period_at_slot(store.finalized_header.beacon.slot)
    update_finalized_period = compute_sync_committee_period_at_slot(
        update.finalized_header.beacon.slot
    )
    if not is_next_sync_committee_known(store):
        assert update_finalized_period == store_period
        store.next_sync_committee = update.next_sync_committee
    elif update_finalized_period == store_period + 1:
        store.current_sync_committee = store.next_sync_committee
        store.next_sync_committee = update.next_sync_committee
        store.previous_max_active_participants = store.current_max_active_participants
        store.current_max_active_participants = 0
    if update.finalized_header.beacon.slot > store.finalized_header.beacon.slot:
        store.finalized_header = update.finalized_header
        if store.finalized_header.beacon.slot > store.optimistic_header.beacon.slot:
            store.optimistic_header = store.finalized_header


def process_light_client_store_force_update(store: LightClientStore, current_slot: Slot) -> None:
    if (
        current_slot > store.finalized_header.beacon.slot + UPDATE_TIMEOUT
        and store.best_valid_update is not None
    ):
        # Forced best update when the update timeout has elapsed.
        # Because the apply logic waits for `finalized_header.beacon.slot` to indicate sync committee finality,
        # the `attested_header` may be treated as `finalized_header` in extended periods of non-finality
        # to guarantee progression into later sync committee periods according to `is_better_update`.
        if (
            store.best_valid_update.finalized_header.beacon.slot
            <= store.finalized_header.beacon.slot
        ):
            store.best_valid_update.finalized_header = store.best_valid_update.attested_header
        apply_light_client_update(store, store.best_valid_update)
        store.best_valid_update = None


def process_light_client_update(
    store: LightClientStore,
    update: LightClientUpdate,
    current_slot: Slot,
    genesis_validators_root: Root,
) -> None:
    validate_light_client_update(store, update, current_slot, genesis_validators_root)

    sync_committee_bits = update.sync_aggregate.sync_committee_bits

    # Update the best update in case we have to force-update to it if the timeout elapses
    if store.best_valid_update is None or is_better_update(update, store.best_valid_update):
        store.best_valid_update = update

    # Track the maximum number of active participants in the committee signatures
    store.current_max_active_participants = max(
        store.current_max_active_participants,
        sum(sync_committee_bits),
    )

    # Update the optimistic header
    if (
        sum(sync_committee_bits) > get_safety_threshold(store)
        and update.attested_header.beacon.slot > store.optimistic_header.beacon.slot
    ):
        store.optimistic_header = update.attested_header

    # Update finalized header
    update_has_finalized_next_sync_committee = (
        not is_next_sync_committee_known(store)
        and is_sync_committee_update(update)
        and is_finality_update(update)
        and (
            compute_sync_committee_period_at_slot(update.finalized_header.beacon.slot)
            == compute_sync_committee_period_at_slot(update.attested_header.beacon.slot)
        )
    )
    if sum(sync_committee_bits) * 3 >= len(sync_committee_bits) * 2 and (
        update.finalized_header.beacon.slot > store.finalized_header.beacon.slot
        or update_has_finalized_next_sync_committee
    ):
        # Normal update through 2/3 threshold
        apply_light_client_update(store, update)
        store.best_valid_update = None


def process_light_client_finality_update(
    store: LightClientStore,
    finality_update: LightClientFinalityUpdate,
    current_slot: Slot,
    genesis_validators_root: Root,
) -> None:
    update = LightClientUpdate(
        attested_header=finality_update.attested_header,
        next_sync_committee=SyncCommittee(),
        next_sync_committee_branch=NextSyncCommitteeBranch(),
        finalized_header=finality_update.finalized_header,
        finality_branch=finality_update.finality_branch,
        sync_aggregate=finality_update.sync_aggregate,
        signature_slot=finality_update.signature_slot,
    )
    process_light_client_update(store, update, current_slot, genesis_validators_root)


def process_light_client_optimistic_update(
    store: LightClientStore,
    optimistic_update: LightClientOptimisticUpdate,
    current_slot: Slot,
    genesis_validators_root: Root,
) -> None:
    update = LightClientUpdate(
        attested_header=optimistic_update.attested_header,
        next_sync_committee=SyncCommittee(),
        next_sync_committee_branch=NextSyncCommitteeBranch(),
        finalized_header=LightClientHeader(),
        finality_branch=FinalityBranch(),
        sync_aggregate=optimistic_update.sync_aggregate,
        signature_slot=optimistic_update.signature_slot,
    )
    process_light_client_update(store, update, current_slot, genesis_validators_root)


def is_merge_transition_complete(state: BeaconState) -> bool:
    return state.latest_execution_payload_header != ExecutionPayloadHeader()


def is_merge_transition_block(state: BeaconState, body: BeaconBlockBody) -> bool:
    return not is_merge_transition_complete(state) and body.execution_payload != ExecutionPayload()


def is_execution_enabled(state: BeaconState, body: BeaconBlockBody) -> bool:
    return is_merge_transition_block(state, body) or is_merge_transition_complete(state)


def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload
    # [Modified in Capella]
    # Removed `is_merge_transition_complete` check
    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(execution_payload=payload)
    )
    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        # [New in Capella]
        withdrawals_root=hash_tree_root(payload.withdrawals),
    )


def should_override_forkchoice_update(store: Store, head_root: Root) -> bool:
    head_block = store.blocks[head_root]
    parent_root = head_block.parent_root
    parent_block = store.blocks[parent_root]
    current_slot = get_current_slot(store)
    proposal_slot = head_block.slot + Slot(1)

    # Only re-org the head_block block if it arrived later than the attestation deadline.
    head_late = is_head_late(store, head_root)

    # Shuffling stable.
    shuffling_stable = is_shuffling_stable(proposal_slot)

    # FFG information of the new head_block will be competitive with the current head.
    ffg_competitive = is_ffg_competitive(store, head_root, parent_root)

    # Do not re-org if the chain is not finalizing with acceptable frequency.
    finalization_ok = is_finalization_ok(store, proposal_slot)

    # Only suppress the fork choice update if we are confident that we will propose the next block.
    parent_state_advanced = store.block_states[parent_root].copy()
    process_slots(parent_state_advanced, proposal_slot)
    proposer_index = get_beacon_proposer_index(parent_state_advanced)
    proposing_reorg_slot = validator_is_connected(proposer_index)

    # Single slot re-org.
    parent_slot_ok = parent_block.slot + 1 == head_block.slot
    proposing_on_time = is_proposing_on_time(store)

    # Note that this condition is different from `get_proposer_head`
    current_time_ok = head_block.slot == current_slot or (
        proposal_slot == current_slot and proposing_on_time
    )
    single_slot_reorg = parent_slot_ok and current_time_ok

    # Check the head weight only if the attestations from the head slot have already been applied.
    # Implementations may want to do this in different ways, e.g. by advancing
    # `store.time` early, or by counting queued attestations during the head block's slot.
    if current_slot > head_block.slot:
        head_weak = is_head_weak(store, head_root)
        parent_strong = is_parent_strong(store, parent_root)
    else:
        head_weak = True
        parent_strong = True

    return all(
        [
            head_late,
            shuffling_stable,
            ffg_competitive,
            finalization_ok,
            proposing_reorg_slot,
            single_slot_reorg,
            head_weak,
            parent_strong,
        ]
    )


def is_valid_terminal_pow_block(block: PowBlock, parent: PowBlock) -> bool:
    is_total_difficulty_reached = block.total_difficulty >= config.TERMINAL_TOTAL_DIFFICULTY
    is_parent_total_difficulty_valid = parent.total_difficulty < config.TERMINAL_TOTAL_DIFFICULTY
    return is_total_difficulty_reached and is_parent_total_difficulty_valid


def validate_merge_block(block: BeaconBlock) -> None:
    """
    Check the parent PoW block of execution payload is a valid terminal PoW block.

    Note: Unavailable PoW block(s) may later become available,
    and a client software MAY delay a call to ``validate_merge_block``
    until the PoW block(s) become available.
    """
    if config.TERMINAL_BLOCK_HASH != Hash32():
        # If `config.TERMINAL_BLOCK_HASH` is used as an override, the activation epoch must be reached.
        assert compute_epoch_at_slot(block.slot) >= config.TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH
        assert block.body.execution_payload.parent_hash == config.TERMINAL_BLOCK_HASH
        return

    pow_block = get_pow_block(block.body.execution_payload.parent_hash)
    # Check if `pow_block` is available
    assert pow_block is not None
    pow_parent = get_pow_block(pow_block.parent_hash)
    # Check if `pow_parent` is available
    assert pow_parent is not None
    # Check if `pow_block` is a valid terminal PoW block
    assert is_valid_terminal_pow_block(pow_block, pow_parent)


def upgrade_to_bellatrix(pre: altair.BeaconState) -> BeaconState:
    epoch = altair.get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [New in Bellatrix]
            current_version=config.BELLATRIX_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=pre.validators,
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        previous_epoch_participation=pre.previous_epoch_participation,
        current_epoch_participation=pre.current_epoch_participation,
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        inactivity_scores=pre.inactivity_scores,
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        # [New in Bellatrix]
        latest_execution_payload_header=ExecutionPayloadHeader(),
    )

    return post


def get_pow_block_at_terminal_total_difficulty(
    pow_chain: dict[Hash32, PowBlock],
) -> PowBlock | None:
    # `pow_chain` abstractly represents all blocks in the PoW chain
    for block in pow_chain.values():
        block_reached_ttd = block.total_difficulty >= config.TERMINAL_TOTAL_DIFFICULTY
        if block_reached_ttd:
            # If genesis block, no parent exists so reaching TTD alone qualifies as valid terminal block
            if block.parent_hash == Hash32():
                return block
            parent = pow_chain[block.parent_hash]
            parent_reached_ttd = parent.total_difficulty >= config.TERMINAL_TOTAL_DIFFICULTY
            if not parent_reached_ttd:
                return block

    return None


def get_terminal_pow_block(pow_chain: dict[Hash32, PowBlock]) -> PowBlock | None:
    if config.TERMINAL_BLOCK_HASH != Hash32():
        # Terminal block hash override takes precedence over terminal total difficulty
        if config.TERMINAL_BLOCK_HASH in pow_chain:
            return pow_chain[config.TERMINAL_BLOCK_HASH]
        else:
            return None

    return get_pow_block_at_terminal_total_difficulty(pow_chain)


def prepare_execution_payload(
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    execution_engine: ExecutionEngine,
) -> PayloadId | None:
    # [Modified in Capella]
    # Removed `is_merge_transition_complete` check
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_time_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        # [New in Capella]
        withdrawals=get_expected_withdrawals(state),
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )


def get_execution_payload(
    payload_id: PayloadId | None, execution_engine: ExecutionEngine
) -> ExecutionPayload:
    if payload_id is None:
        # Pre-merge, empty payload
        return ExecutionPayload()
    else:
        return execution_engine.get_payload(payload_id).execution_payload


def is_optimistic(opt_store: OptimisticStore, block: BeaconBlock) -> bool:
    return hash_tree_root(block) in opt_store.optimistic_roots


def latest_verified_ancestor(opt_store: OptimisticStore, block: BeaconBlock) -> BeaconBlock:
    # It is assumed that the `block` parameter is never an INVALIDATED block.
    while True:
        if not is_optimistic(opt_store, block) or block.parent_root == Root():
            return block
        block = opt_store.blocks[block.parent_root]


def is_execution_block(block: BeaconBlock) -> bool:
    return block.body.execution_payload != ExecutionPayload()


def is_optimistic_candidate_block(
    opt_store: OptimisticStore, current_slot: Slot, block: BeaconBlock
) -> bool:
    if is_execution_block(opt_store.blocks[block.parent_root]):
        return True

    if block.slot + SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY <= current_slot:
        return True

    return False


def has_eth1_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x01 prefixed "eth1" withdrawal credential.
    """
    return validator.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX


def is_fully_withdrawable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        has_eth1_withdrawal_credential(validator)
        and validator.withdrawable_epoch <= epoch
        and balance > 0
    )


def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    has_max_effective_balance = validator.effective_balance == MAX_EFFECTIVE_BALANCE
    has_excess_balance = balance > MAX_EFFECTIVE_BALANCE
    return (
        has_eth1_withdrawal_credential(validator)
        and has_max_effective_balance
        and has_excess_balance
    )


def process_historical_summaries_update(state: BeaconState) -> None:
    # Set historical block root accumulator.
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_summary = HistoricalSummary(
            block_summary_root=hash_tree_root(state.block_roots),
            state_summary_root=hash_tree_root(state.state_roots),
        )
        state.historical_summaries.append(historical_summary)


def get_expected_withdrawals(state: BeaconState) -> Sequence[Withdrawal]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []
    bound = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    for _ in range(bound):
        validator = state.validators[validator_index]
        balance = state.balances[validator_index]
        if is_fully_withdrawable_validator(validator, balance, epoch):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=balance,
                )
            )
            withdrawal_index += WithdrawalIndex(1)
        elif is_partially_withdrawable_validator(validator, balance):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=balance - MAX_EFFECTIVE_BALANCE,
                )
            )
            withdrawal_index += WithdrawalIndex(1)
        if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
            break
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
    return withdrawals


def process_withdrawals(state: BeaconState, payload: ExecutionPayload) -> None:
    expected_withdrawals = get_expected_withdrawals(state)
    assert payload.withdrawals == expected_withdrawals

    for withdrawal in expected_withdrawals:
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)

    # Update the next withdrawal index if this block contained withdrawals
    if len(expected_withdrawals) != 0:
        latest_withdrawal = expected_withdrawals[-1]
        state.next_withdrawal_index = WithdrawalIndex(latest_withdrawal.index + 1)

    # Update the next validator index to start the next withdrawal sweep
    if len(expected_withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = ValidatorIndex(
            (expected_withdrawals[-1].validator_index + 1) % len(state.validators)
        )
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        next_validator_index = ValidatorIndex(next_index % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index


def process_bls_to_execution_change(
    state: BeaconState, signed_address_change: SignedBLSToExecutionChange
) -> None:
    address_change = signed_address_change.message

    assert address_change.validator_index < len(state.validators)

    validator = state.validators[address_change.validator_index]

    assert validator.withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX
    assert validator.withdrawal_credentials[1:] == hash(address_change.from_bls_pubkey)[1:]

    # Fork-agnostic domain since address changes are valid across forks
    domain = compute_domain(
        DOMAIN_BLS_TO_EXECUTION_CHANGE, genesis_validators_root=state.genesis_validators_root
    )
    signing_root = compute_signing_root(address_change, domain)
    assert bls.Verify(address_change.from_bls_pubkey, signing_root, signed_address_change.signature)

    validator.withdrawal_credentials = (
        ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + address_change.to_execution_address
    )


def upgrade_to_capella(pre: bellatrix.BeaconState) -> BeaconState:
    epoch = bellatrix.get_current_epoch(pre)
    latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=pre.latest_execution_payload_header.parent_hash,
        fee_recipient=pre.latest_execution_payload_header.fee_recipient,
        state_root=pre.latest_execution_payload_header.state_root,
        receipts_root=pre.latest_execution_payload_header.receipts_root,
        logs_bloom=pre.latest_execution_payload_header.logs_bloom,
        prev_randao=pre.latest_execution_payload_header.prev_randao,
        block_number=pre.latest_execution_payload_header.block_number,
        gas_limit=pre.latest_execution_payload_header.gas_limit,
        gas_used=pre.latest_execution_payload_header.gas_used,
        timestamp=pre.latest_execution_payload_header.timestamp,
        extra_data=pre.latest_execution_payload_header.extra_data,
        base_fee_per_gas=pre.latest_execution_payload_header.base_fee_per_gas,
        block_hash=pre.latest_execution_payload_header.block_hash,
        transactions_root=pre.latest_execution_payload_header.transactions_root,
        # [New in Capella]
        withdrawals_root=Root(),
    )
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=config.CAPELLA_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=pre.validators,
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        previous_epoch_participation=pre.previous_epoch_participation,
        current_epoch_participation=pre.current_epoch_participation,
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        inactivity_scores=pre.inactivity_scores,
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        latest_execution_payload_header=latest_execution_payload_header,
        # [New in Capella]
        next_withdrawal_index=WithdrawalIndex(0),
        # [New in Capella]
        next_withdrawal_validator_index=ValidatorIndex(0),
        # [New in Capella]
        historical_summaries=List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]([]),
    )

    return post


def upgrade_lc_header_to_capella(pre: altair.LightClientHeader) -> LightClientHeader:
    return LightClientHeader(
        beacon=pre.beacon,
        execution=ExecutionPayloadHeader(),
        execution_branch=ExecutionBranch(),
    )


def upgrade_lc_bootstrap_to_capella(pre: altair.LightClientBootstrap) -> LightClientBootstrap:
    return LightClientBootstrap(
        header=upgrade_lc_header_to_capella(pre.header),
        current_sync_committee=pre.current_sync_committee,
        current_sync_committee_branch=pre.current_sync_committee_branch,
    )


def upgrade_lc_update_to_capella(pre: altair.LightClientUpdate) -> LightClientUpdate:
    return LightClientUpdate(
        attested_header=upgrade_lc_header_to_capella(pre.attested_header),
        next_sync_committee=pre.next_sync_committee,
        next_sync_committee_branch=pre.next_sync_committee_branch,
        finalized_header=upgrade_lc_header_to_capella(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )


def upgrade_lc_finality_update_to_capella(
    pre: altair.LightClientFinalityUpdate,
) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=upgrade_lc_header_to_capella(pre.attested_header),
        finalized_header=upgrade_lc_header_to_capella(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )


def upgrade_lc_optimistic_update_to_capella(
    pre: altair.LightClientOptimisticUpdate,
) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=upgrade_lc_header_to_capella(pre.attested_header),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )


def upgrade_lc_store_to_capella(pre: altair.LightClientStore) -> LightClientStore:
    if pre.best_valid_update is None:
        best_valid_update = None
    else:
        best_valid_update = upgrade_lc_update_to_capella(pre.best_valid_update)
    return LightClientStore(
        finalized_header=upgrade_lc_header_to_capella(pre.finalized_header),
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        best_valid_update=best_valid_update,
        optimistic_header=upgrade_lc_header_to_capella(pre.optimistic_header),
        previous_max_active_participants=pre.previous_max_active_participants,
        current_max_active_participants=pre.current_max_active_participants,
    )


def get_lc_execution_root(header: LightClientHeader) -> Root:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    if epoch >= config.CAPELLA_FORK_EPOCH:
        return hash_tree_root(header.execution)

    return Root()


def BLSG1ScalarMultiply(scalar: BLSFieldElement, point: BLSG1Point) -> BLSG1Point:
    return bls.G1_to_bytes48(bls.multiply(bls.bytes48_to_G1(point), scalar))


def bytes_to_bls_field(b: Bytes32) -> BLSFieldElement:
    """
    Convert bytes to a BLS field scalar. The output is not uniform over the BLS field.
    TODO: Deneb will introduces this helper too. Should delete it once it's rebased to post-Deneb.
    """
    field_element = int.from_bytes(b, ENDIANNESS)
    return BLSFieldElement(field_element % BLS_MODULUS)


def IsValidWhiskShuffleProof(
    pre_shuffle_trackers: Sequence[WhiskTracker],
    post_shuffle_trackers: Sequence[WhiskTracker],
    shuffle_proof: WhiskShuffleProof,
) -> bool:
    """
    Verify `post_shuffle_trackers` is a permutation of `pre_shuffle_trackers`.
    Defined in https://github.com/nalinbhardwaj/curdleproofs.pie/blob/dev/curdleproofs/curdleproofs/whisk_interface.py.
    """
    return curdleproofs.IsValidWhiskShuffleProof(
        CURDLEPROOFS_CRS,
        pre_shuffle_trackers,
        post_shuffle_trackers,
        shuffle_proof,
    )


def IsValidWhiskOpeningProof(
    tracker: WhiskTracker, k_commitment: BLSG1Point, tracker_proof: WhiskTrackerProof
) -> bool:
    """
    Verify knowledge of `k` such that `tracker.k_r_G == k * tracker.r_G` and `k_commitment == k * BLS_G1_GENERATOR`.
    Defined in https://github.com/nalinbhardwaj/curdleproofs.pie/blob/dev/curdleproofs/curdleproofs/whisk_interface.py.
    """
    return curdleproofs.IsValidWhiskOpeningProof(tracker, k_commitment, tracker_proof)


def select_whisk_proposer_trackers(state: BeaconState, epoch: Epoch) -> None:
    # Select proposer trackers from candidate trackers
    proposer_seed = get_seed(
        state,
        Epoch(saturating_sub(epoch, config.PROPOSER_SELECTION_GAP)),
        DOMAIN_PROPOSER_SELECTION,
    )
    for i in range(PROPOSER_TRACKERS_COUNT):
        index = compute_shuffled_index(
            uint64(i), uint64(len(state.whisk_candidate_trackers)), proposer_seed
        )
        state.whisk_proposer_trackers[i] = state.whisk_candidate_trackers[index]


def select_whisk_candidate_trackers(state: BeaconState, epoch: Epoch) -> None:
    # Select candidate trackers from active validator trackers
    active_validator_indices = get_active_validator_indices(state, epoch)
    for i in range(CANDIDATE_TRACKERS_COUNT):
        seed = hash(get_seed(state, epoch, DOMAIN_CANDIDATE_SELECTION) + uint_to_bytes(uint64(i)))
        candidate_index = compute_proposer_index(
            state, active_validator_indices, seed
        )  # sample by effective balance
        state.whisk_candidate_trackers[i] = state.whisk_trackers[candidate_index]


def process_whisk_updates(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if (
        next_epoch % config.EPOCHS_PER_SHUFFLING_PHASE == 0
    ):  # select trackers at the start of shuffling phases
        select_whisk_proposer_trackers(state, next_epoch)
        select_whisk_candidate_trackers(state, next_epoch)


def process_whisk_opening_proof(state: BeaconState, block: BeaconBlock) -> None:
    tracker = state.whisk_proposer_trackers[state.slot % PROPOSER_TRACKERS_COUNT]
    k_commitment = state.whisk_k_commitments[block.proposer_index]
    assert IsValidWhiskOpeningProof(tracker, k_commitment, block.body.whisk_opening_proof)


def get_shuffle_indices(randao_reveal: BLSSignature) -> Sequence[uint64]:
    """
    Given a `randao_reveal` return the list of indices that got shuffled from the entire candidate set.
    """
    indices = []
    for i in range(0, VALIDATORS_PER_SHUFFLE):
        # XXX ensure we are not suffering from modulo bias
        pre_image = randao_reveal + uint_to_bytes(uint64(i))
        shuffle_index = bytes_to_uint64(hash(pre_image)[0:8]) % CANDIDATE_TRACKERS_COUNT
        indices.append(shuffle_index)

    return indices


def process_shuffled_trackers(state: BeaconState, body: BeaconBlockBody) -> None:
    shuffle_epoch = get_current_epoch(state) % config.EPOCHS_PER_SHUFFLING_PHASE
    if shuffle_epoch + config.PROPOSER_SELECTION_GAP + 1 >= config.EPOCHS_PER_SHUFFLING_PHASE:
        # Require trackers set to zero during cooldown
        assert body.whisk_post_shuffle_trackers == Vector[WhiskTracker, VALIDATORS_PER_SHUFFLE]()
        assert body.whisk_shuffle_proof == WhiskShuffleProof()
    else:
        # Require shuffled trackers during shuffle
        shuffle_indices = get_shuffle_indices(body.randao_reveal)
        pre_shuffle_trackers = [state.whisk_candidate_trackers[i] for i in shuffle_indices]
        assert IsValidWhiskShuffleProof(
            pre_shuffle_trackers,
            body.whisk_post_shuffle_trackers,
            body.whisk_shuffle_proof,
        )
        # Shuffle candidate trackers
        for i, shuffle_index in enumerate(shuffle_indices):
            state.whisk_candidate_trackers[shuffle_index] = body.whisk_post_shuffle_trackers[i]


def is_k_commitment_unique(state: BeaconState, k_commitment: BLSG1Point) -> bool:
    return all(
        [whisk_k_commitment != k_commitment for whisk_k_commitment in state.whisk_k_commitments]
    )


def process_whisk_registration(state: BeaconState, body: BeaconBlockBody) -> None:
    proposer_index = get_beacon_proposer_index(state)
    if state.whisk_trackers[proposer_index].r_G == BLS_G1_GENERATOR:  # first Whisk proposal
        assert body.whisk_tracker.r_G != BLS_G1_GENERATOR
        assert is_k_commitment_unique(state, body.whisk_k_commitment)
        assert IsValidWhiskOpeningProof(
            body.whisk_tracker,
            body.whisk_k_commitment,
            body.whisk_registration_proof,
        )
        state.whisk_trackers[proposer_index] = body.whisk_tracker
        state.whisk_k_commitments[proposer_index] = body.whisk_k_commitment
    else:  # next Whisk proposals
        assert body.whisk_registration_proof == WhiskTrackerProof()
        assert body.whisk_tracker == WhiskTracker()
        assert body.whisk_k_commitment == BLSG1Point()


def get_initial_whisk_k(validator_index: ValidatorIndex, counter: int) -> BLSFieldElement:
    # hash `validator_index || counter`
    return BLSFieldElement(
        bytes_to_bls_field(hash(uint_to_bytes(validator_index) + uint_to_bytes(uint64(counter))))
    )


def get_unique_whisk_k(state: BeaconState, validator_index: ValidatorIndex) -> BLSFieldElement:
    counter = 0
    while True:
        k = get_initial_whisk_k(validator_index, counter)
        if is_k_commitment_unique(state, BLSG1ScalarMultiply(k, BLS_G1_GENERATOR)):
            return k  # unique by trial and error
        counter += 1


def get_k_commitment(k: BLSFieldElement) -> BLSG1Point:
    return BLSG1ScalarMultiply(k, BLS_G1_GENERATOR)


def get_initial_tracker(k: BLSFieldElement) -> WhiskTracker:
    return WhiskTracker(r_G=BLS_G1_GENERATOR, k_r_G=BLSG1ScalarMultiply(k, BLS_G1_GENERATOR))


def upgrade_to_eip7441(pre: capella.BeaconState) -> BeaconState:
    # Compute initial unsafe trackers for all validators
    ks = [
        get_initial_whisk_k(ValidatorIndex(validator_index), 0)
        for validator_index in range(len(pre.validators))
    ]
    whisk_k_commitments = [get_k_commitment(k) for k in ks]
    whisk_trackers = [get_initial_tracker(k) for k in ks]

    epoch = get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=config.EIP7441_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=[],
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        previous_epoch_participation=pre.previous_epoch_participation,
        current_epoch_participation=pre.current_epoch_participation,
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        inactivity_scores=pre.inactivity_scores,
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        latest_execution_payload_header=pre.latest_execution_payload_header,
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        historical_summaries=pre.historical_summaries,
        # [New in EIP7441]
        whisk_proposer_trackers=[WhiskTracker() for _ in range(PROPOSER_TRACKERS_COUNT)],
        # [New in EIP7441]
        whisk_candidate_trackers=[WhiskTracker() for _ in range(CANDIDATE_TRACKERS_COUNT)],
        # [New in EIP7441]
        whisk_trackers=whisk_trackers,
        # [New in EIP7441]
        whisk_k_commitments=whisk_k_commitments,
    )

    # Do a candidate selection followed by a proposer selection so that we have proposers for the upcoming day
    # Use an old epoch when selecting candidates so that we don't get the same seed as in the next candidate selection
    select_whisk_candidate_trackers(
        post, Epoch(saturating_sub(epoch, config.PROPOSER_SELECTION_GAP + 1))
    )
    select_whisk_proposer_trackers(post, epoch)

    # Do a final round of candidate selection.
    # We need it so that we have something to shuffle over the upcoming shuffling phase.
    select_whisk_candidate_trackers(post, epoch)

    return post


def get_eth1_data(block: Eth1Block) -> Eth1Data:
    """
    A stub function return mocking Eth1Data.
    """
    return Eth1Data(
        deposit_root=block.deposit_root,
        deposit_count=block.deposit_count,
        block_hash=hash_tree_root(block),
    )


def cache_this(key_fn, value_fn, lru_size):  # type: ignore
    cache_dict = LRU(size=lru_size)

    def wrapper(*args, **kw):  # type: ignore
        key = key_fn(*args, **kw)
        if key not in cache_dict:
            cache_dict[key] = value_fn(*args, **kw)
        return cache_dict[key]

    return wrapper


_compute_shuffled_index = compute_shuffled_index
compute_shuffled_index = cache_this(
    lambda index, index_count, seed: (index, index_count, seed),
    _compute_shuffled_index,
    lru_size=SLOTS_PER_EPOCH * 3,
)

_get_total_active_balance = get_total_active_balance
get_total_active_balance = cache_this(
    lambda state: (state.validators.hash_tree_root(), compute_epoch_at_slot(state.slot)),
    _get_total_active_balance,
    lru_size=10,
)

_get_base_reward = get_base_reward
get_base_reward = cache_this(
    lambda state, index: (state.validators.hash_tree_root(), state.slot, index),
    _get_base_reward,
    lru_size=2048,
)

_get_committee_count_per_slot = get_committee_count_per_slot
get_committee_count_per_slot = cache_this(
    lambda state, epoch: (state.validators.hash_tree_root(), epoch),
    _get_committee_count_per_slot,
    lru_size=SLOTS_PER_EPOCH * 3,
)

_get_active_validator_indices = get_active_validator_indices
get_active_validator_indices = cache_this(
    lambda state, epoch: (state.validators.hash_tree_root(), epoch),
    _get_active_validator_indices,
    lru_size=3,
)

_get_beacon_committee = get_beacon_committee
get_beacon_committee = cache_this(
    lambda state, slot, index: (
        state.validators.hash_tree_root(),
        state.randao_mixes.hash_tree_root(),
        slot,
        index,
    ),
    _get_beacon_committee,
    lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3,
)

_get_matching_target_attestations = get_matching_target_attestations
get_matching_target_attestations = cache_this(
    lambda state, epoch: (state.hash_tree_root(), epoch),
    _get_matching_target_attestations,
    lru_size=10,
)

_get_matching_head_attestations = get_matching_head_attestations
get_matching_head_attestations = cache_this(
    lambda state, epoch: (state.hash_tree_root(), epoch),
    _get_matching_head_attestations,
    lru_size=10,
)

_get_attesting_indices = get_attesting_indices
get_attesting_indices = cache_this(
    lambda state, attestation: (
        state.randao_mixes.hash_tree_root(),
        state.validators.hash_tree_root(),
        attestation.hash_tree_root(),
    ),
    _get_attesting_indices,
    lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3,
)


def get_generalized_index(ssz_class: Any, *path: int | SSZVariableName) -> GeneralizedIndex:
    ssz_path = Path(ssz_class)
    for item in path:
        ssz_path = ssz_path / item
    return GeneralizedIndex(ssz_path.gindex())


def compute_merkle_proof(object: SSZObject, index: GeneralizedIndex) -> list[Bytes32]:
    return build_proof(object.get_backing(), index)


ExecutionState = Any


def get_pow_block(hash: Bytes32) -> PowBlock | None:
    return PowBlock(block_hash=hash, parent_hash=Bytes32(), total_difficulty=uint256(0))


def get_execution_state(_execution_state_root: Bytes32) -> ExecutionState:
    pass


def get_pow_chain_head() -> PowBlock:
    pass


def validator_is_connected(validator_index: ValidatorIndex) -> bool:
    # pylint: disable=unused-argument
    return True


class NoopExecutionEngine(ExecutionEngine):
    def notify_new_payload(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
        return True

    def notify_forkchoice_updated(
        self: ExecutionEngine,
        head_block_hash: Hash32,
        safe_block_hash: Hash32,
        finalized_block_hash: Hash32,
        payload_attributes: PayloadAttributes | None,
    ) -> PayloadId | None:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        # pylint: disable=unused-argument
        raise NotImplementedError("no default block production")

    def is_valid_block_hash(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
        return True

    def verify_and_notify_new_payload(
        self: ExecutionEngine, new_payload_request: NewPayloadRequest
    ) -> bool:
        return True


EXECUTION_ENGINE = NoopExecutionEngine()


assert FINALIZED_ROOT_GINDEX == get_generalized_index(BeaconState, "finalized_checkpoint", "root")
assert CURRENT_SYNC_COMMITTEE_GINDEX == get_generalized_index(BeaconState, "current_sync_committee")
assert NEXT_SYNC_COMMITTEE_GINDEX == get_generalized_index(BeaconState, "next_sync_committee")
assert EXECUTION_PAYLOAD_GINDEX == get_generalized_index(BeaconBlockBody, "execution_payload")
