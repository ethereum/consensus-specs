from lru import LRU
from collections import defaultdict
from dataclasses import (
    dataclass,
    field,
)
from hashlib import sha256 as sha256_hash
from typing import Any, Callable, Counter, Sequence, TypeAlias, TypeVar, NamedTuple, Final

from ssz.bitfields import BitList, BitVector
from ssz.boolean import Boolean
from ssz.collections import List, ProgressiveList, Vector
from ssz.container import Container
from ssz.ssz_base import SSZType
from ssz.uint import BaseUint as Uint, Byte, Uint8, Uint16, Uint32, Uint64, Uint256
from eth_consensus_specs.utils.ssz.bytes import Bytes1, Bytes4, Bytes20, Bytes32, Bytes48, Bytes96
from eth_consensus_specs.utils.ssz.ssz_impl import ssz_deserialize, ssz_serialize
from eth_consensus_specs.utils import bls


from typing import NewType, Union as PyUnion

from eth_consensus_specs.phase0 import minimal as phase0
from eth_consensus_specs.test.helpers.merkle import build_proof, get_generalized_index


from typing import Protocol
from eth_consensus_specs.altair import minimal as altair
from ssz.byte_arrays import ByteList, ByteVector
from eth_consensus_specs.utils.ssz.bytes import Bytes8


from eth_consensus_specs.bellatrix import minimal as bellatrix


from eth_consensus_specs.capella import minimal as capella
from eth_consensus_specs.utils import kzg


from eth_consensus_specs.deneb import minimal as deneb


from frozendict import frozendict
from eth_consensus_specs.electra import minimal as electra


from ssz.bitfields import ProgressiveBitList
from ssz.container import active_fields, ProgressiveContainer

from eth_consensus_specs.fulu import minimal as fulu


from eth_consensus_specs.gloas import minimal as gloas
from eth_consensus_specs.utils.ssz.bytes import Bytes64


SSZObject = TypeVar("SSZObject", bound=SSZType)


SSZVariableName = str
GeneralizedIndex = int


fork = "prereg"


def ceillog2(x: int) -> Uint64:
    if x < 1:
        raise ValueError(f"ceillog2 accepts only positive values, x={x}")
    return Uint64((x - 1).bit_length())


def floorlog2(x: int) -> Uint64:
    if x < 1:
        raise ValueError(f"floorlog2 accepts only positive values, x={x}")
    return Uint64(x.bit_length() - 1)


FINALIZED_ROOT_GINDEX = GeneralizedIndex(105)
CURRENT_SYNC_COMMITTEE_GINDEX = GeneralizedIndex(54)
NEXT_SYNC_COMMITTEE_GINDEX = GeneralizedIndex(55)
EXECUTION_PAYLOAD_GINDEX = GeneralizedIndex(25)
FINALIZED_ROOT_GINDEX_ELECTRA = GeneralizedIndex(169)
CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA = GeneralizedIndex(86)
NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA = GeneralizedIndex(87)
FINALIZED_ROOT_GINDEX_GLOAS = GeneralizedIndex(735)
CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS = GeneralizedIndex(2945)
NEXT_SYNC_COMMITTEE_GINDEX_GLOAS = GeneralizedIndex(2946)
EXECUTION_BLOCK_HASH_GINDEX = GeneralizedIndex(412)
EXECUTION_BLOCK_HASH_GINDEX_DENEB = GeneralizedIndex(812)
EXECUTION_BLOCK_HASH_GINDEX_GLOAS = GeneralizedIndex(2856)


BLSSignature: TypeAlias = gloas.BLSSignature


Domain: TypeAlias = gloas.Domain


DomainType: TypeAlias = gloas.DomainType


Epoch: TypeAlias = gloas.Epoch


Gwei: TypeAlias = gloas.Gwei


Hash32: TypeAlias = gloas.Hash32


Slot: TypeAlias = gloas.Slot


Version: TypeAlias = gloas.Version


ExecutionAddress: TypeAlias = gloas.ExecutionAddress


PayloadValidationStatus: TypeAlias = gloas.PayloadValidationStatus


BuilderIndex: TypeAlias = gloas.BuilderIndex


PayloadStatus: TypeAlias = gloas.PayloadStatus


# Constant vars
UINT64_MAX = Uint64(2**64 - 1)
UINT64_MAX_SQRT = Uint64(4294967295)
GENESIS_SLOT = Slot(0)
GENESIS_EPOCH = Epoch(0)
FAR_FUTURE_EPOCH = Epoch(2**64 - 1)
BASE_REWARDS_PER_EPOCH = Uint64(4)
JUSTIFICATION_BITS_LENGTH = Uint64(4)
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
DEPOSIT_CONTRACT_TREE_DEPTH = Uint64(2**5)
BASIS_POINTS = Uint64(10000)
NODE_ID_BITS = Uint64(256)
MAX_CONCURRENT_REQUESTS = Uint64(2)
TARGET_AGGREGATORS_PER_COMMITTEE = Uint64(2**4)
ETH_TO_GWEI = Uint64(10**9)
SAFETY_DECAY = Uint64(10)
TIMELY_SOURCE_FLAG_INDEX = Uint64(0)
TIMELY_TARGET_FLAG_INDEX = Uint64(1)
TIMELY_HEAD_FLAG_INDEX = Uint64(2)
TIMELY_SOURCE_WEIGHT = Uint64(14)
TIMELY_TARGET_WEIGHT = Uint64(26)
TIMELY_HEAD_WEIGHT = Uint64(14)
SYNC_REWARD_WEIGHT = Uint64(2)
PROPOSER_WEIGHT = Uint64(8)
WEIGHT_DENOMINATOR = Uint64(64)
DOMAIN_SYNC_COMMITTEE = DomainType("0x07000000")
DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF = DomainType("0x08000000")
DOMAIN_CONTRIBUTION_AND_PROOF = DomainType("0x09000000")
PARTICIPATION_FLAG_WEIGHTS = [TIMELY_SOURCE_WEIGHT, TIMELY_TARGET_WEIGHT, TIMELY_HEAD_WEIGHT]
G2_POINT_AT_INFINITY = BLSSignature(b"\xc0" + b"\x00" * 95)
TARGET_AGGREGATORS_PER_SYNC_SUBCOMMITTEE = Uint64(2**4)
SYNC_COMMITTEE_SUBNET_COUNT = Uint64(2**2)
MAX_REQUEST_LIGHT_CLIENT_UPDATES = Uint64(2**7)
EMPTY_BLOCK_HASH = Hash32()
SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY = Slot(128)
PAYLOAD_STATUS_VALID = PayloadValidationStatus(0)
PAYLOAD_STATUS_INVALIDATED = PayloadValidationStatus(1)
PAYLOAD_STATUS_NOT_VALIDATED = PayloadValidationStatus(2)
DOMAIN_BLS_TO_EXECUTION_CHANGE = DomainType("0x0A000000")
VERSIONED_HASH_VERSION_KZG = Bytes1("0x01")
BYTES_PER_FIELD_ELEMENT = Uint64(32)
UNSET_DEPOSIT_REQUESTS_START_INDEX = Uint64(2**64 - 1)
FULL_EXIT_REQUEST_AMOUNT = Gwei(0)
COMPOUNDING_WITHDRAWAL_PREFIX = Bytes1("0x02")
DEPOSIT_REQUEST_TYPE = Bytes1("0x00")
WITHDRAWAL_REQUEST_TYPE = Bytes1("0x01")
CONSOLIDATION_REQUEST_TYPE = Bytes1("0x02")
UINT256_MAX = Uint256(2**256 - 1)
BUILDER_INDEX_FLAG = Uint64(2**40)
DOMAIN_BEACON_BUILDER = DomainType("0x0B000000")
DOMAIN_PTC_ATTESTER = DomainType("0x0C000000")
DOMAIN_PROPOSER_PREFERENCES = DomainType("0x0D000000")
DOMAIN_BUILDER_DEPOSIT = DomainType("0x0E000000")
BUILDER_INDEX_SELF_BUILD = BuilderIndex(UINT64_MAX)
BUILDER_PAYMENT_THRESHOLD_NUMERATOR = Uint64(6)
BUILDER_PAYMENT_THRESHOLD_DENOMINATOR = Uint64(10)
BUILDER_WITHDRAWAL_PREFIX = Bytes1("0xB0")
PAYLOAD_BUILDER_VERSION = Uint8(0)
BUILDER_DEPOSIT_REQUEST_TYPE = Bytes1("0x03")
BUILDER_EXIT_REQUEST_TYPE = Bytes1("0x04")
PAYLOAD_STATUS_EMPTY = PayloadStatus(0)
PAYLOAD_STATUS_FULL = PayloadStatus(1)
PAYLOAD_STATUS_PENDING = PayloadStatus(2)
ATTESTATION_TIMELINESS_INDEX = Uint64(0)
PTC_TIMELINESS_INDEX = Uint64(1)
NUM_BLOCK_TIMELINESS_DEADLINES = Uint64(2)
VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE = Bytes1("0x06")
BUILDER_PQ_REGISTRATION_REQUEST_TYPE = Bytes1("0x07")


# Preset vars
MAX_COMMITTEES_PER_SLOT = Uint64(4)
TARGET_COMMITTEE_SIZE = Uint64(4)
MAX_VALIDATORS_PER_COMMITTEE = Uint64(2048)
SHUFFLE_ROUND_COUNT = Uint64(10)
HYSTERESIS_QUOTIENT = Uint64(4)
HYSTERESIS_DOWNWARD_MULTIPLIER = Uint64(1)
HYSTERESIS_UPWARD_MULTIPLIER = Uint64(5)
MIN_DEPOSIT_AMOUNT = Gwei(1000000000)
MAX_EFFECTIVE_BALANCE = Gwei(32000000000)
EFFECTIVE_BALANCE_INCREMENT = Gwei(1000000000)
MIN_ATTESTATION_INCLUSION_DELAY = Slot(1)
SLOTS_PER_EPOCH = Slot(8)
MIN_SEED_LOOKAHEAD = Epoch(1)
MAX_SEED_LOOKAHEAD = Epoch(4)
MIN_EPOCHS_TO_INACTIVITY_PENALTY = Epoch(4)
EPOCHS_PER_ETH1_VOTING_PERIOD = Epoch(4)
SLOTS_PER_HISTORICAL_ROOT = Slot(64)
EPOCHS_PER_HISTORICAL_VECTOR = Epoch(64)
EPOCHS_PER_SLASHINGS_VECTOR = Epoch(64)
HISTORICAL_ROOTS_LIMIT = Uint64(16777216)
VALIDATOR_REGISTRY_LIMIT = Uint64(1099511627776)
BASE_REWARD_FACTOR = Uint64(64)
WHISTLEBLOWER_REWARD_QUOTIENT = Uint64(512)
PROPOSER_REWARD_QUOTIENT = Uint64(8)
INACTIVITY_PENALTY_QUOTIENT = Uint64(33554432)
MIN_SLASHING_PENALTY_QUOTIENT = Uint64(64)
PROPORTIONAL_SLASHING_MULTIPLIER = Uint64(2)
MAX_PROPOSER_SLASHINGS = Uint64(16)
MAX_ATTESTER_SLASHINGS = Uint64(2)
MAX_ATTESTATIONS = Uint64(128)
MAX_DEPOSITS = Uint64(16)
MAX_VOLUNTARY_EXITS = Uint64(16)
INACTIVITY_PENALTY_QUOTIENT_ALTAIR = Uint64(50331648)
MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR = Uint64(64)
PROPORTIONAL_SLASHING_MULTIPLIER_ALTAIR = Uint64(2)
SYNC_COMMITTEE_SIZE = Uint64(32)
EPOCHS_PER_SYNC_COMMITTEE_PERIOD = Epoch(8)
MIN_SYNC_COMMITTEE_PARTICIPANTS = Uint64(1)
UPDATE_TIMEOUT = Slot(64)
INACTIVITY_PENALTY_QUOTIENT_BELLATRIX = Uint64(16777216)
MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX = Uint64(32)
PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX = Uint64(3)
MAX_BYTES_PER_TRANSACTION = Uint64(1073741824)
MAX_TRANSACTIONS_PER_PAYLOAD = Uint64(1048576)
BYTES_PER_LOGS_BLOOM = Uint64(256)
MAX_EXTRA_DATA_BYTES = Uint64(32)
MAX_BLS_TO_EXECUTION_CHANGES = Uint64(16)
MAX_WITHDRAWALS_PER_PAYLOAD = Uint64(4)
MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP = Uint64(16)
FIELD_ELEMENTS_PER_BLOB = Uint64(4096)
MAX_BLOB_COMMITMENTS_PER_BLOCK = Uint64(4096)
KZG_COMMITMENT_INCLUSION_PROOF_DEPTH = Uint64(17)
MIN_ACTIVATION_BALANCE = Gwei(32000000000)
MAX_EFFECTIVE_BALANCE_ELECTRA = Gwei(2048000000000)
MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA = Uint64(4096)
WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA = Uint64(4096)
PENDING_DEPOSITS_LIMIT = Uint64(134217728)
PENDING_PARTIAL_WITHDRAWALS_LIMIT = Uint64(64)
PENDING_CONSOLIDATIONS_LIMIT = Uint64(64)
MAX_ATTESTER_SLASHINGS_ELECTRA = Uint64(1)
MAX_ATTESTATIONS_ELECTRA = Uint64(8)
MAX_DEPOSIT_REQUESTS_PER_PAYLOAD = Uint64(8192)
MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD = Uint64(16)
MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD = Uint64(2)
MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP = Uint64(2)
MAX_PENDING_DEPOSITS_PER_EPOCH = Uint64(16)
FIELD_ELEMENTS_PER_EXT_BLOB = 8192
FIELD_ELEMENTS_PER_CELL = Uint64(64)
CELLS_PER_EXT_BLOB = 128
NUMBER_OF_COLUMNS = Uint64(128)
KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH = Uint64(4)
PTC_SIZE = Uint64(16)
MAX_PAYLOAD_ATTESTATIONS = Uint64(4)
MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD = Uint64(64)
MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD = Uint64(16)
MAX_BUILDERS_PER_WITHDRAWALS_SWEEP = Uint64(16)
MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE = Uint64(1462)
MAX_ATTESTER_SLASHING_SIZE = Uint64(131536)
MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE = Uint64(196932)
MAX_VALIDATOR_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD = Uint64(1024)
MAX_BUILDER_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD = Uint64(16)


# Preset computed constants
PAYLOAD_TIMELY_THRESHOLD = Uint64(PTC_SIZE // 2)
DATA_AVAILABILITY_TIMELY_THRESHOLD = Uint64(PTC_SIZE // 2)


class Configuration(NamedTuple):
    PRESET_BASE: str
    MIN_GENESIS_ACTIVE_VALIDATOR_COUNT: Uint64
    MIN_GENESIS_TIME: Uint64
    GENESIS_FORK_VERSION: Version
    GENESIS_DELAY: Uint64
    SLOT_DURATION_MS: Uint64
    SECONDS_PER_ETH1_BLOCK: Uint64
    MIN_VALIDATOR_WITHDRAWABILITY_DELAY: Epoch
    SHARD_COMMITTEE_PERIOD: Epoch
    ETH1_FOLLOW_DISTANCE: Uint64
    EJECTION_BALANCE: Gwei
    MIN_PER_EPOCH_CHURN_LIMIT: Uint64
    CHURN_LIMIT_QUOTIENT: Uint64
    DEPOSIT_CHAIN_ID: Uint64
    DEPOSIT_NETWORK_ID: Uint64
    DEPOSIT_CONTRACT_ADDRESS: ExecutionAddress
    CONFIRMATION_BYZANTINE_THRESHOLD: Uint64
    PROPOSER_SCORE_BOOST: Uint64
    REORG_HEAD_WEIGHT_THRESHOLD: Uint64
    REORG_PARENT_WEIGHT_THRESHOLD: Uint64
    REORG_MAX_EPOCHS_SINCE_FINALIZATION: Epoch
    PROPOSER_REORG_CUTOFF_BPS: Uint64
    MAX_PAYLOAD_SIZE: Uint64
    EPOCHS_PER_SUBNET_SUBSCRIPTION: Epoch
    MAXIMUM_GOSSIP_CLOCK_DISPARITY: Uint64
    MESSAGE_DOMAIN_INVALID_SNAPPY: DomainType
    MESSAGE_DOMAIN_VALID_SNAPPY: DomainType
    SUBNETS_PER_NODE: Uint64
    ATTESTATION_SUBNET_COUNT: Uint64
    ATTESTATION_SUBNET_EXTRA_BITS: Uint64
    INACTIVITY_SCORE_BIAS: Uint64
    INACTIVITY_SCORE_RECOVERY_RATE: Uint64
    ALTAIR_FORK_VERSION: Version
    ALTAIR_FORK_EPOCH: Epoch
    TERMINAL_TOTAL_DIFFICULTY: Uint256
    BELLATRIX_FORK_VERSION: Version
    BELLATRIX_FORK_EPOCH: Epoch
    CAPELLA_FORK_VERSION: Version
    CAPELLA_FORK_EPOCH: Epoch
    DENEB_FORK_VERSION: Version
    DENEB_FORK_EPOCH: Epoch
    MAX_REQUEST_BLOCKS_DENEB: Uint64
    MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS: Epoch
    MAX_BLOBS_PER_BLOCK_ELECTRA: Uint64
    MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA: Gwei
    ELECTRA_FORK_VERSION: Version
    ELECTRA_FORK_EPOCH: Epoch
    BLOB_SCHEDULE: tuple[frozendict[str, Any], ...]
    SAMPLES_PER_SLOT: Uint64
    NUMBER_OF_CUSTODY_GROUPS: Uint64
    CUSTODY_REQUIREMENT: Uint64
    FULU_FORK_VERSION: Version
    FULU_FORK_EPOCH: Epoch
    DATA_COLUMN_SIDECAR_SUBNET_COUNT: Uint64
    MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS: Epoch
    VALIDATOR_CUSTODY_REQUIREMENT: Uint64
    BALANCE_PER_ADDITIONAL_CUSTODY_GROUP: Gwei
    CHURN_LIMIT_QUOTIENT_GLOAS: Uint64
    CONSOLIDATION_CHURN_LIMIT_QUOTIENT: Uint64
    MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS: Gwei
    MIN_BUILDER_WITHDRAWABILITY_DELAY: Epoch
    GAS_LIMIT_SCHEDULE: tuple[frozendict[str, Any], ...]
    GLOAS_FORK_VERSION: Version
    GLOAS_FORK_EPOCH: Epoch
    MAX_REQUEST_PAYLOADS: Uint64
    ATTESTATION_DUE_BPS_GLOAS: Uint64
    AGGREGATE_DUE_BPS_GLOAS: Uint64
    SYNC_MESSAGE_DUE_BPS_GLOAS: Uint64
    CONTRIBUTION_DUE_BPS_GLOAS: Uint64
    PAYLOAD_DUE_BPS: Uint64
    PAYLOAD_ATTESTATION_DUE_BPS: Uint64
    PREREG_FORK_VERSION: Version
    PREREG_FORK_EPOCH: Epoch


config = Configuration(
    PRESET_BASE="minimal",
    MIN_GENESIS_ACTIVE_VALIDATOR_COUNT=Uint64(64),
    MIN_GENESIS_TIME=Uint64(1578009600),
    GENESIS_FORK_VERSION=Version("0x00000001"),
    GENESIS_DELAY=Uint64(300),
    SLOT_DURATION_MS=Uint64(6000),
    SECONDS_PER_ETH1_BLOCK=Uint64(14),
    MIN_VALIDATOR_WITHDRAWABILITY_DELAY=Epoch(256),
    SHARD_COMMITTEE_PERIOD=Epoch(64),
    ETH1_FOLLOW_DISTANCE=Uint64(16),
    EJECTION_BALANCE=Gwei(16000000000),
    MIN_PER_EPOCH_CHURN_LIMIT=Uint64(2),
    CHURN_LIMIT_QUOTIENT=Uint64(32),
    DEPOSIT_CHAIN_ID=Uint64(5),
    DEPOSIT_NETWORK_ID=Uint64(5),
    DEPOSIT_CONTRACT_ADDRESS=ExecutionAddress("0x1234567890123456789012345678901234567890"),
    CONFIRMATION_BYZANTINE_THRESHOLD=Uint64(25),
    PROPOSER_SCORE_BOOST=Uint64(40),
    REORG_HEAD_WEIGHT_THRESHOLD=Uint64(20),
    REORG_PARENT_WEIGHT_THRESHOLD=Uint64(160),
    REORG_MAX_EPOCHS_SINCE_FINALIZATION=Epoch(2),
    PROPOSER_REORG_CUTOFF_BPS=Uint64(1667),
    MAX_PAYLOAD_SIZE=Uint64(10485760),
    EPOCHS_PER_SUBNET_SUBSCRIPTION=Epoch(256),
    MAXIMUM_GOSSIP_CLOCK_DISPARITY=Uint64(500),
    MESSAGE_DOMAIN_INVALID_SNAPPY=DomainType("0x00000000"),
    MESSAGE_DOMAIN_VALID_SNAPPY=DomainType("0x01000000"),
    SUBNETS_PER_NODE=Uint64(2),
    ATTESTATION_SUBNET_COUNT=Uint64(64),
    ATTESTATION_SUBNET_EXTRA_BITS=Uint64(0),
    INACTIVITY_SCORE_BIAS=Uint64(4),
    INACTIVITY_SCORE_RECOVERY_RATE=Uint64(16),
    ALTAIR_FORK_VERSION=Version("0x01000001"),
    ALTAIR_FORK_EPOCH=Epoch(18446744073709551615),
    TERMINAL_TOTAL_DIFFICULTY=Uint256(
        115792089237316195423570985008687907853269984665640564039457584007913129638912
    ),
    BELLATRIX_FORK_VERSION=Version("0x02000001"),
    BELLATRIX_FORK_EPOCH=Epoch(18446744073709551615),
    CAPELLA_FORK_VERSION=Version("0x03000001"),
    CAPELLA_FORK_EPOCH=Epoch(18446744073709551615),
    DENEB_FORK_VERSION=Version("0x04000001"),
    DENEB_FORK_EPOCH=Epoch(18446744073709551615),
    MAX_REQUEST_BLOCKS_DENEB=Uint64(128),
    MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS=Epoch(4096),
    MAX_BLOBS_PER_BLOCK_ELECTRA=Uint64(9),
    MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA=Gwei(64000000000),
    ELECTRA_FORK_VERSION=Version("0x05000001"),
    ELECTRA_FORK_EPOCH=Epoch(18446744073709551615),
    BLOB_SCHEDULE=tuple[frozendict[str, Any], ...](()),
    SAMPLES_PER_SLOT=Uint64(8),
    NUMBER_OF_CUSTODY_GROUPS=Uint64(128),
    CUSTODY_REQUIREMENT=Uint64(4),
    FULU_FORK_VERSION=Version("0x06000001"),
    FULU_FORK_EPOCH=Epoch(18446744073709551615),
    DATA_COLUMN_SIDECAR_SUBNET_COUNT=Uint64(128),
    MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS=Epoch(4096),
    VALIDATOR_CUSTODY_REQUIREMENT=Uint64(8),
    BALANCE_PER_ADDITIONAL_CUSTODY_GROUP=Gwei(32000000000),
    CHURN_LIMIT_QUOTIENT_GLOAS=Uint64(16),
    CONSOLIDATION_CHURN_LIMIT_QUOTIENT=Uint64(32),
    MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS=Gwei(128000000000),
    MIN_BUILDER_WITHDRAWABILITY_DELAY=Epoch(2),
    GAS_LIMIT_SCHEDULE=tuple[frozendict[str, Any], ...](()),
    GLOAS_FORK_VERSION=Version("0x07000001"),
    GLOAS_FORK_EPOCH=Epoch(18446744073709551615),
    MAX_REQUEST_PAYLOADS=Uint64(128),
    ATTESTATION_DUE_BPS_GLOAS=Uint64(2500),
    AGGREGATE_DUE_BPS_GLOAS=Uint64(5000),
    SYNC_MESSAGE_DUE_BPS_GLOAS=Uint64(2500),
    CONTRIBUTION_DUE_BPS_GLOAS=Uint64(5000),
    PAYLOAD_DUE_BPS=Uint64(5000),
    PAYLOAD_ATTESTATION_DUE_BPS=Uint64(7500),
    PREREG_FORK_VERSION=Version("0xe8483001"),
    PREREG_FORK_EPOCH=Epoch(18446744073709551615),
)


class GossipIgnore(Exception):
    pass


class GossipReject(Exception):
    pass


AggregationBits: TypeAlias = gloas.AggregationBits


Balances: TypeAlias = gloas.Balances


DepositProof: TypeAlias = gloas.DepositProof


JustificationBits: TypeAlias = gloas.JustificationBits


RandaoMixes: TypeAlias = gloas.RandaoMixes


Slashings: TypeAlias = gloas.Slashings


Fork: TypeAlias = gloas.Fork


Attnets: TypeAlias = gloas.Attnets


ErrorMessage: TypeAlias = gloas.ErrorMessage


InactivityScores: TypeAlias = gloas.InactivityScores


SyncCommitteeBits: TypeAlias = gloas.SyncCommitteeBits


SyncAggregate: TypeAlias = gloas.SyncAggregate


Syncnets: TypeAlias = gloas.Syncnets


SyncSubcommitteeBits: TypeAlias = gloas.SyncSubcommitteeBits


SyncAggregatorSelectionData: TypeAlias = gloas.SyncAggregatorSelectionData


CurrentSyncCommitteeBranch: TypeAlias = gloas.CurrentSyncCommitteeBranch


FinalityBranch: TypeAlias = gloas.FinalityBranch


NextSyncCommitteeBranch: TypeAlias = gloas.NextSyncCommitteeBranch


ExtraData: TypeAlias = gloas.ExtraData


LogsBloom: TypeAlias = gloas.LogsBloom


Transaction: TypeAlias = gloas.Transaction


Transactions: TypeAlias = gloas.Transactions


PowBlock: TypeAlias = gloas.PowBlock


ExecutionBranch: TypeAlias = gloas.ExecutionBranch


Blob: TypeAlias = gloas.Blob


Blobs: TypeAlias = gloas.Blobs


CommitteeBits: TypeAlias = gloas.CommitteeBits


Cell: TypeAlias = gloas.Cell


Cells: TypeAlias = gloas.Cells


DataColumn: TypeAlias = gloas.DataColumn


CellsBitList: TypeAlias = gloas.CellsBitList


PartialDataColumnPartsMetadata: TypeAlias = gloas.PartialDataColumnPartsMetadata


BlockAccessList: TypeAlias = gloas.BlockAccessList


ExecutionPayloadAvailability: TypeAlias = gloas.ExecutionPayloadAvailability


PayloadTimelinessCommitteeBits: TypeAlias = gloas.PayloadTimelinessCommitteeBits


BuilderPendingWithdrawal: TypeAlias = gloas.BuilderPendingWithdrawal


BuilderPendingWithdrawals: TypeAlias = gloas.BuilderPendingWithdrawals


CustodyColumnBits: TypeAlias = gloas.CustodyColumnBits


BLSPubkey: TypeAlias = gloas.BLSPubkey


class BuilderPQRegistration(Container):
    builder_pubkey: BLSPubkey
    pq_data: Bytes32


class BuilderPQRegistrations(ProgressiveList[BuilderPQRegistration]):
    """
    The registered builder PQ material, at most one entry per builder.
    """


class BuilderPQRegistrationRequest(Container):
    source_address: ExecutionAddress
    builder_pubkey: BLSPubkey
    pq_data: Bytes32


class BuilderPQRegistrationRequests(ProgressiveList[BuilderPQRegistrationRequest]):
    """
    The builder PQ registration requests pertaining to a single execution payload.
    """


class ValidatorPQRegistrationRequest(Container):
    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
    pq_data: Bytes64


class ValidatorPQRegistrationRequests(ProgressiveList[ValidatorPQRegistrationRequest]):
    """
    The validator PQ registration requests pertaining to a single execution payload.
    """


BuilderExitRequest: TypeAlias = gloas.BuilderExitRequest


BuilderExitRequests: TypeAlias = gloas.BuilderExitRequests


BuilderDepositRequest: TypeAlias = gloas.BuilderDepositRequest


BuilderDepositRequests: TypeAlias = gloas.BuilderDepositRequests


Builder: TypeAlias = gloas.Builder


Builders: TypeAlias = gloas.Builders


ConsolidationRequest: TypeAlias = gloas.ConsolidationRequest


ConsolidationRequests: TypeAlias = gloas.ConsolidationRequests


WithdrawalRequest: TypeAlias = gloas.WithdrawalRequest


WithdrawalRequests: TypeAlias = gloas.WithdrawalRequests


DepositRequest: TypeAlias = gloas.DepositRequest


DepositRequests: TypeAlias = gloas.DepositRequests


class ExecutionRequests(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=7)

    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    consolidations: ConsolidationRequests
    builder_deposits: BuilderDepositRequests
    builder_exits: BuilderExitRequests
    # [New in Prereg]
    validator_pq_registrations: ValidatorPQRegistrationRequests
    # [New in Prereg]
    builder_pq_registrations: BuilderPQRegistrationRequests


PendingDeposit: TypeAlias = gloas.PendingDeposit


PendingDeposits: TypeAlias = gloas.PendingDeposits


SyncCommitteePubkeys: TypeAlias = gloas.SyncCommitteePubkeys


SyncCommittee: TypeAlias = gloas.SyncCommittee


DepositData: TypeAlias = gloas.DepositData


DepositDataList: TypeAlias = gloas.DepositDataList


Deposit: TypeAlias = gloas.Deposit


Deposits: TypeAlias = gloas.Deposits


DepositMessage: TypeAlias = gloas.DepositMessage


Validator: TypeAlias = gloas.Validator


Validators: TypeAlias = gloas.Validators


CommitteeIndex: TypeAlias = gloas.CommitteeIndex


ForkDigest: TypeAlias = gloas.ForkDigest


Root: TypeAlias = gloas.Root


ExecutionPayloadEnvelopeRoots: TypeAlias = gloas.ExecutionPayloadEnvelopeRoots


PayloadAttestationData: TypeAlias = gloas.PayloadAttestationData


PayloadAttestation: TypeAlias = gloas.PayloadAttestation


PayloadAttestations: TypeAlias = gloas.PayloadAttestations


PartialDataColumnGroupID: TypeAlias = gloas.PartialDataColumnGroupID


HistoricalSummary: TypeAlias = gloas.HistoricalSummary


HistoricalSummaries: TypeAlias = gloas.HistoricalSummaries


SyncCommitteeContribution: TypeAlias = gloas.SyncCommitteeContribution


Eth1Block: TypeAlias = gloas.Eth1Block


BeaconBlockRoots: TypeAlias = gloas.BeaconBlockRoots


SigningData: TypeAlias = gloas.SigningData


Eth1Data: TypeAlias = gloas.Eth1Data


Eth1DataVotes: TypeAlias = gloas.Eth1DataVotes


Checkpoint: TypeAlias = gloas.Checkpoint


AttestationData: TypeAlias = gloas.AttestationData


Attestation: TypeAlias = gloas.Attestation


Attestations: TypeAlias = gloas.Attestations


ForkData: TypeAlias = gloas.ForkData


StateRoots: TypeAlias = gloas.StateRoots


HistoricalRoots: TypeAlias = gloas.HistoricalRoots


BlockRoots: TypeAlias = gloas.BlockRoots


ValidatorIndex: TypeAlias = gloas.ValidatorIndex


class ValidatorPQRegistration(Container):
    validator_index: ValidatorIndex
    pq_data: Bytes64


class ValidatorPQRegistrations(ProgressiveList[ValidatorPQRegistration]):
    """
    The registered validator PQ material, at most one entry per validator.
    """


ProposerPreferences: TypeAlias = gloas.ProposerPreferences


SignedProposerPreferences: TypeAlias = gloas.SignedProposerPreferences


PayloadAttestationMessage: TypeAlias = gloas.PayloadAttestationMessage


BuilderPendingPayment: TypeAlias = gloas.BuilderPendingPayment


BuilderPendingPayments: TypeAlias = gloas.BuilderPendingPayments


PayloadTimelinessCommitteeIndices: TypeAlias = gloas.PayloadTimelinessCommitteeIndices


IndexedPayloadAttestation: TypeAlias = gloas.IndexedPayloadAttestation


PayloadTimelinessCommittee: TypeAlias = gloas.PayloadTimelinessCommittee


PayloadTimelinessCommitteeWindow: TypeAlias = gloas.PayloadTimelinessCommitteeWindow


ProposerLookahead: TypeAlias = gloas.ProposerLookahead


ProposerIndices: TypeAlias = gloas.ProposerIndices


SingleAttestation: TypeAlias = gloas.SingleAttestation


PendingConsolidation: TypeAlias = gloas.PendingConsolidation


PendingConsolidations: TypeAlias = gloas.PendingConsolidations


PendingPartialWithdrawal: TypeAlias = gloas.PendingPartialWithdrawal


PendingPartialWithdrawals: TypeAlias = gloas.PendingPartialWithdrawals


BLSToExecutionChange: TypeAlias = gloas.BLSToExecutionChange


SignedBLSToExecutionChange: TypeAlias = gloas.SignedBLSToExecutionChange


BLSToExecutionChanges: TypeAlias = gloas.BLSToExecutionChanges


ContributionAndProof: TypeAlias = gloas.ContributionAndProof


SignedContributionAndProof: TypeAlias = gloas.SignedContributionAndProof


SyncCommitteeMessage: TypeAlias = gloas.SyncCommitteeMessage


AggregateAndProof: TypeAlias = gloas.AggregateAndProof


SignedAggregateAndProof: TypeAlias = gloas.SignedAggregateAndProof


VoluntaryExit: TypeAlias = gloas.VoluntaryExit


SignedVoluntaryExit: TypeAlias = gloas.SignedVoluntaryExit


VoluntaryExits: TypeAlias = gloas.VoluntaryExits


BeaconBlockHeader: TypeAlias = gloas.BeaconBlockHeader


LightClientHeader: TypeAlias = gloas.LightClientHeader


LightClientOptimisticUpdate: TypeAlias = gloas.LightClientOptimisticUpdate


LightClientFinalityUpdate: TypeAlias = gloas.LightClientFinalityUpdate


LightClientUpdate: TypeAlias = gloas.LightClientUpdate


LightClientUpdates: TypeAlias = gloas.LightClientUpdates


LightClientBootstrap: TypeAlias = gloas.LightClientBootstrap


SignedBeaconBlockHeader: TypeAlias = gloas.SignedBeaconBlockHeader


ProposerSlashing: TypeAlias = gloas.ProposerSlashing


ProposerSlashings: TypeAlias = gloas.ProposerSlashings


AttestingIndices: TypeAlias = gloas.AttestingIndices


IndexedAttestation: TypeAlias = gloas.IndexedAttestation


AttesterSlashing: TypeAlias = gloas.AttesterSlashing


AttesterSlashings: TypeAlias = gloas.AttesterSlashings


NodeID: TypeAlias = gloas.NodeID


SubnetID: TypeAlias = gloas.SubnetID


Ether: TypeAlias = gloas.Ether


ParticipationFlags: TypeAlias = gloas.ParticipationFlags


EpochParticipation: TypeAlias = gloas.EpochParticipation


PayloadId: TypeAlias = gloas.PayloadId


WithdrawalIndex: TypeAlias = gloas.WithdrawalIndex


Withdrawal: TypeAlias = gloas.Withdrawal


Withdrawals: TypeAlias = gloas.Withdrawals


ExecutionPayload: TypeAlias = gloas.ExecutionPayload


class ExecutionPayloadEnvelope(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=5)

    payload: ExecutionPayload
    execution_requests: ExecutionRequests
    builder_index: BuilderIndex
    beacon_block_root: Root
    parent_beacon_block_root: Root


class SignedExecutionPayloadEnvelope(Container):
    message: ExecutionPayloadEnvelope
    signature: BLSSignature


class SignedExecutionPayloadEnvelopes(List[SignedExecutionPayloadEnvelope]):
    """
    Signed execution payload envelopes returned in an
    ``ExecutionPayloadEnvelopesByRange`` or
    ``ExecutionPayloadEnvelopesByRoot`` response.
    """

    LIMIT = config.MAX_REQUEST_PAYLOADS


BlobIndex: TypeAlias = gloas.BlobIndex


KZGCommitment: TypeAlias = gloas.KZGCommitment


BlobKZGCommitments: TypeAlias = gloas.BlobKZGCommitments


ExecutionPayloadBid: TypeAlias = gloas.ExecutionPayloadBid


class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=48)

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    eth1_data: Eth1Data
    eth1_data_votes: Eth1DataVotes
    eth1_deposit_index: Uint64
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    deposit_requests_start_index: Uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: PendingDeposits
    pending_partial_withdrawals: PendingPartialWithdrawals
    pending_consolidations: PendingConsolidations
    proposer_lookahead: ProposerLookahead
    builders: Builders
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: ExecutionPayloadAvailability
    builder_pending_payments: BuilderPendingPayments
    builder_pending_withdrawals: BuilderPendingWithdrawals
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PayloadTimelinessCommitteeWindow
    # [New in Prereg]
    validator_pq_registrations: ValidatorPQRegistrations
    # [New in Prereg]
    builder_pq_registrations: BuilderPQRegistrations


SignedExecutionPayloadBid: TypeAlias = gloas.SignedExecutionPayloadBid


class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=13)

    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    # [Modified in Gloas:EIP7688]
    proposer_slashings: ProposerSlashings
    # [Modified in Gloas:EIP7688]
    attester_slashings: AttesterSlashings
    # [Modified in Gloas:EIP7688]
    attestations: Attestations
    # [Modified in Gloas:EIP7688]
    deposits: Deposits
    # [Modified in Gloas:EIP7688]
    voluntary_exits: VoluntaryExits
    sync_aggregate: SyncAggregate
    # [Modified in Gloas:EIP7732]
    # Removed `execution_payload`
    # [Modified in Gloas:EIP7688]
    bls_to_execution_changes: BLSToExecutionChanges
    # [Modified in Gloas:EIP7732]
    # Removed `blob_kzg_commitments`
    # [Modified in Gloas:EIP7732]
    # Removed `execution_requests`
    # [New in Gloas:EIP7732]
    signed_execution_payload_bid: SignedExecutionPayloadBid
    # [New in Gloas:EIP7732]
    payload_attestations: PayloadAttestations
    # [New in Gloas:EIP7732]
    parent_execution_requests: ExecutionRequests


class BeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody


class SignedBeaconBlock(Container):
    message: BeaconBlock
    signature: BLSSignature


class SignedBeaconBlocks(List[SignedBeaconBlock]):
    """
    Signed beacon blocks returned in a ``BeaconBlocksByRange`` or
    ``BeaconBlocksByRoot`` response.
    """

    LIMIT = config.MAX_REQUEST_BLOCKS_DENEB


KZGProof: TypeAlias = gloas.KZGProof


CellKZGProofs: TypeAlias = gloas.CellKZGProofs


Proofs: TypeAlias = gloas.Proofs


KZGProofs: TypeAlias = gloas.KZGProofs


PartialDataColumnSidecar: TypeAlias = gloas.PartialDataColumnSidecar


VersionedHash: TypeAlias = gloas.VersionedHash


VersionedHashes: TypeAlias = gloas.VersionedHashes


class NewPayloadRequest(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    execution_payload: ExecutionPayload
    versioned_hashes: VersionedHashes
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests


CellIndex: TypeAlias = gloas.CellIndex


ColumnIndex: TypeAlias = gloas.ColumnIndex


DataColumnIndices: TypeAlias = gloas.DataColumnIndices


DataColumnsByRootIdentifier: TypeAlias = gloas.DataColumnsByRootIdentifier


DataColumnsByRootIdentifiers: TypeAlias = gloas.DataColumnsByRootIdentifiers


DataColumnSidecar: TypeAlias = gloas.DataColumnSidecar


CustodyIndex: TypeAlias = gloas.CustodyIndex


RowIndex: TypeAlias = gloas.RowIndex


MatrixEntry: TypeAlias = gloas.MatrixEntry


ForkChoiceNode: TypeAlias = gloas.ForkChoiceNode


LatestMessage: TypeAlias = gloas.LatestMessage


@dataclass
class Store:
    time_ms: Uint64
    genesis_time_ms: Uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: set[ValidatorIndex]
    blocks: dict[Root, BeaconBlock]
    block_states: dict[Root, BeaconState]
    # [Modified in Gloas:EIP7732]
    block_timeliness: dict[Root, list[bool]]
    checkpoint_states: dict[Checkpoint, BeaconState]
    latest_messages: dict[ValidatorIndex, LatestMessage]
    unrealized_justifications: dict[Root, Checkpoint]
    # [New in Gloas:EIP7732]
    payloads: dict[Root, ExecutionPayloadEnvelope]
    # [New in Gloas:EIP7732]
    payload_timeliness_vote: dict[Root, list[Boolean | None]]
    # [New in Gloas:EIP7732]
    payload_data_availability_vote: dict[Root, list[Boolean | None]]


@dataclass
class FastConfirmationStore:
    store: Store
    confirmed_root: Root
    previous_epoch_observed_justified_checkpoint: Checkpoint
    current_epoch_observed_justified_checkpoint: Checkpoint
    previous_epoch_greatest_unrealized_checkpoint: Checkpoint
    previous_slot_head: Root
    current_slot_head: Root


Seen: TypeAlias = gloas.Seen


LightClientStore: TypeAlias = gloas.LightClientStore


PayloadAttributes: TypeAlias = gloas.PayloadAttributes


@dataclass
class OptimisticStore:
    optimistic_roots: set[Root]
    head_block_root: Root
    blocks: dict[Root, BeaconBlock]
    block_states: dict[Root, BeaconState]


ExpectedWithdrawals: TypeAlias = gloas.ExpectedWithdrawals


BlobsBundle: TypeAlias = gloas.BlobsBundle


GetPayloadResponse: TypeAlias = gloas.GetPayloadResponse


BlobParameters: TypeAlias = gloas.BlobParameters


class ExecutionEngine(Protocol):
    def notify_new_payload(
        self,
        execution_payload: ExecutionPayload,
        parent_beacon_block_root: Root,
        execution_requests_list: Sequence[bytes],
    ) -> bool:
        """
        Return ``True`` if and only if ``execution_payload`` and ``execution_requests_list``
        are valid with respect to ``self.execution_state``.
        """

    def is_valid_block_hash(
        self,
        execution_payload: ExecutionPayload,
        parent_beacon_block_root: Root,
        execution_requests_list: Sequence[bytes],
    ) -> bool:
        """
        Return ``True`` if and only if ``execution_payload.block_hash`` is computed correctly.
        """

    def verify_and_notify_new_payload(self, new_payload_request: NewPayloadRequest) -> bool: ...

    def notify_forkchoice_updated(
        self,
        head_block_hash: Hash32,
        safe_block_hash: Hash32,
        finalized_block_hash: Hash32,
        payload_attributes: PayloadAttributes | None,
        # [New in Gloas:EIP8070]
        custody_columns: CustodyColumnBits | None,
    ) -> PayloadId | None: ...

    def get_payload(self, payload_id: PayloadId) -> GetPayloadResponse:
        """
        Return ExecutionPayload, Uint256, BlobsBundle, and execution requests (as Sequence[bytes]) objects.
        """

    def is_valid_versioned_hashes(self, new_payload_request: NewPayloadRequest) -> bool:
        """
        Return ``True`` if and only if the version hashes computed by the blob transactions of
        ``new_payload_request.execution_payload`` matches ``new_payload_request.versioned_hashes``.
        """


def get_set_bit_count(bits: Sequence[Boolean]) -> Uint64:
    """
    Return the number of bits that are set in ``bits``.
    """
    return Uint64(sum(1 for bit in bits if bit))


def integer_squareroot(n: Uint64) -> Uint64:
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
    return Bytes32(byte_1 ^ byte_2 for byte_1, byte_2 in zip(bytes_1, bytes_2, strict=True))


def uint_to_bytes(n: Uint) -> bytes:
    """
    Return the SSZ serialization of ``n``, a ``Uint``.
    """
    return ssz_serialize(n)


def bytes_to_uint64(data: bytes) -> Uint64:
    """
    Return the integer deserialization of ``data`` as a ``Uint64``.
    """
    return Uint64(int.from_bytes(data, ENDIANNESS))


def saturating_sub(a: Uint64, b: int) -> Any:
    """
    Return ``a - b``, saturating at zero.
    """
    return a - b if a > b else a - a


def sha256(data: bytes) -> Bytes32:
    """
    Return the SHA256 hash of ``data``.
    """
    return Bytes32(sha256_hash(data).digest())


def hash_tree_root(object: SSZObject) -> Root:
    """
    Return the hash tree root of ``object``.
    """
    return Root(object.hash_tree_root())


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
        # [Modified in Electra:EIP7251]
        and validator.effective_balance >= MIN_ACTIVATION_BALANCE
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
    if (
        len(indices) == 0
        # [New in Gloas:EIP7688]
        or len(indices) > MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT
        or list(indices) != sorted(set(indices))
    ):
        return False
    # Verify aggregate signature
    pubkeys = [state.validators[index].pubkey for index in indices]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, indexed_attestation.signature)


def compute_merkle_branch_root(
    leaf: Bytes32, branch: Sequence[Bytes32], depth: Uint64, index: Uint64
) -> Root:
    """
    Return the Merkle root obtained by hashing ``leaf`` at ``index`` with ``branch``.
    """
    value = leaf
    for i in range(depth):
        if index // (2**i) % 2:
            value = sha256(branch[i] + value)
        else:
            value = sha256(value + branch[i])
    return Root(value)


def is_valid_merkle_branch(
    leaf: Bytes32, branch: Sequence[Bytes32], depth: Uint64, index: Uint64, root: Root
) -> bool:
    """
    Check if ``leaf`` at ``index`` verifies against the Merkle ``root`` and ``branch``.
    """
    if depth != len(branch):
        return False
    return compute_merkle_branch_root(leaf, branch, depth, index) == root


def compute_shuffled_permutation(index_count: Uint64, seed: Bytes32) -> Sequence[Uint64]:
    """
    Return the full shuffled permutation corresponding to ``seed`` (and ``index_count``).
    """
    # Swap or not (https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf)
    # See the 'generalized domain' algorithm on page 3
    indices = [Uint64(index) for index in range(index_count)]
    for current_round in range(SHUFFLE_ROUND_COUNT):
        round_bytes = uint_to_bytes(Uint8(current_round))
        pivot = bytes_to_uint64(sha256(seed + round_bytes)[0:8]) % index_count
        source_by_bucket: dict[Uint64, Bytes32] = {}
        for i in range(index_count):
            flip = (pivot + index_count - indices[i]) % index_count
            position = max(indices[i], flip)
            position_bucket = position // 256
            if position_bucket not in source_by_bucket:
                source_by_bucket[position_bucket] = sha256(
                    seed + round_bytes + uint_to_bytes(Uint32(position_bucket))
                )
            source = source_by_bucket[position_bucket]
            byte_val = source[(position % 256) // 8]
            bit = (byte_val >> (position % 8)) % 2
            indices[i] = flip if bit else indices[i]
    return indices


def compute_shuffled_index(index: Uint64, index_count: Uint64, seed: Bytes32) -> Uint64:
    """
    Return the shuffled index corresponding to ``seed`` (and ``index_count``).
    """
    assert index < index_count
    return compute_shuffled_permutation(index_count, seed)[index]


def compute_committee(
    indices: Sequence[ValidatorIndex], seed: Bytes32, index: Uint64, count: Uint64
) -> Sequence[ValidatorIndex]:
    """
    Return the committee corresponding to ``indices``, ``seed``, ``index``, and committee ``count``.
    """
    start = (len(indices) * index) // count
    end = (len(indices) * Uint64(index + 1)) // count
    return [
        indices[compute_shuffled_index(Uint64(index), Uint64(len(indices)), seed)]
        for index in range(start, end)
    ]


def compute_time_at_slot(genesis_time: Uint64, slot: Slot) -> Uint64:
    """
    Return the time in seconds at the start of the given slot.
    """
    genesis_time_ms = seconds_to_milliseconds(genesis_time)
    time_ms = compute_time_at_slot_ms(genesis_time_ms, slot)
    return milliseconds_to_seconds(time_ms)


def compute_slot_at_time(genesis_time: Uint64, time: Uint64) -> Slot:
    """
    Return the slot at Unix time ``time``.
    """
    genesis_time_ms = seconds_to_milliseconds(genesis_time)
    time_ms = seconds_to_milliseconds(time)
    return compute_slot_at_time_ms(genesis_time_ms, time_ms)


def compute_time_at_slot_ms(genesis_time_ms: Uint64, slot: Slot) -> Uint64:
    """
    Return the time in milliseconds at the start of the given slot.
    """
    return Uint64(genesis_time_ms + slot * config.SLOT_DURATION_MS)


def compute_slot_at_time_ms(genesis_time_ms: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot at Unix time ``time_ms``.
    """
    return Slot((time_ms - genesis_time_ms) // config.SLOT_DURATION_MS)


def compute_epoch_at_slot(slot: Slot) -> Epoch:
    """
    Return the epoch number at ``slot``.
    """
    return Epoch(slot // SLOTS_PER_EPOCH)


def compute_start_slot_at_epoch(epoch: Epoch) -> Slot:
    """
    Return the start slot of ``epoch``.
    """
    return Slot(epoch) * SLOTS_PER_EPOCH


def compute_activation_exit_epoch(epoch: Epoch) -> Epoch:
    """
    Return the epoch during which validator activations and exits initiated in ``epoch`` take effect.
    """
    return epoch + 1 + MAX_SEED_LOOKAHEAD


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
    domain_type: DomainType,
    fork_version: Version | None = None,
    genesis_validators_root: Root | None = None,
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
    return saturating_sub(get_current_epoch(state), 1)


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
        ValidatorIndex(index)
        for index, validator in enumerate(state.validators)
        if is_active_validator(validator, epoch)
    ]


def get_validator_churn_limit(state: BeaconState) -> Uint64:
    """
    Return the validator churn limit for the current epoch.
    """
    active_validator_indices = get_active_validator_indices(state, get_current_epoch(state))
    return max(
        config.MIN_PER_EPOCH_CHURN_LIMIT,
        Uint64(len(active_validator_indices)) // config.CHURN_LIMIT_QUOTIENT,
    )


def get_seed(state: BeaconState, epoch: Epoch, domain_type: DomainType) -> Bytes32:
    """
    Return the seed at ``epoch``.
    """
    mix = get_randao_mix(
        state, epoch + EPOCHS_PER_HISTORICAL_VECTOR - MIN_SEED_LOOKAHEAD - 1
    )  # Avoid underflow
    return sha256(domain_type + uint_to_bytes(epoch) + mix)


def get_committee_count_per_slot(state: BeaconState, epoch: Epoch) -> Uint64:
    """
    Return the number of committees in each slot for the given ``epoch``.
    """
    return max(
        Uint64(1),
        min(
            MAX_COMMITTEES_PER_SLOT,
            Uint64(len(get_active_validator_indices(state, epoch)))
            // Uint64(SLOTS_PER_EPOCH)
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
        index=Uint64(slot % SLOTS_PER_EPOCH) * committees_per_slot + index,
        count=committees_per_slot * Uint64(SLOTS_PER_EPOCH),
    )


def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    return state.proposer_lookahead[state.slot % SLOTS_PER_EPOCH]


def get_total_balance(state: BeaconState, indices: set[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of the ``indices``.
    ``EFFECTIVE_BALANCE_INCREMENT`` Gwei minimum to avoid divisions by zero.
    Math safe up to ~10B ETH, after which this overflows Uint64.
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


def get_domain(state: BeaconState, domain_type: DomainType, epoch: Epoch | None = None) -> Domain:
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
        attesting_indices=AttestingIndices(data=sorted(attesting_indices)),
        data=attestation.data,
        signature=attestation.signature,
    )


def get_attesting_indices(state: BeaconState, attestation: Attestation) -> set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``aggregation_bits`` and ``committee_bits``.
    """
    output: set[ValidatorIndex] = set()
    committee_indices = get_committee_indices(attestation.committee_bits)
    committee_offset = 0
    for committee_index in committee_indices:
        committee = get_beacon_committee(state, attestation.data.slot, committee_index)
        committee_attesters = {
            attester_index
            for index, attester_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + index]
        }
        output = output.union(committee_attesters)

        committee_offset += len(committee)

    return output


def increase_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Increase the validator balance at index ``index`` by ``delta``.
    """
    state.balances[index] += delta


def decrease_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Decrease the validator balance at index ``index`` by ``delta``.
    """
    state.balances[index] = saturating_sub(state.balances[index], delta)


def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    validator = state.validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch [Modified in Electra:EIP7251]
    exit_queue_epoch = compute_exit_epoch_and_update_churn(state, validator.effective_balance)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = validator.exit_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY


def slash_validator(
    state: BeaconState,
    slashed_index: ValidatorIndex,
    whistleblower_index: ValidatorIndex | None = None,
) -> None:
    """
    Slash the validator with index ``slashed_index``.
    """
    epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    validator = state.validators[slashed_index]
    validator.slashed = Boolean(True)
    validator.withdrawable_epoch = max(
        validator.withdrawable_epoch, epoch + EPOCHS_PER_SLASHINGS_VECTOR
    )
    state.slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] += validator.effective_balance
    slashing_penalty = validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA
    decrease_balance(state, slashed_index, slashing_penalty)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblower_reward = validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA
    proposer_reward = whistleblower_reward * PROPOSER_WEIGHT // WEIGHT_DENOMINATOR
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, whistleblower_reward - proposer_reward)

    # [New in Gloas:EIP7732]
    # Remove pending builder payments for blocks proposed by the slashed validator
    for payment_index, payment in enumerate(state.builder_pending_payments):
        if payment.proposer_index == slashed_index:
            state.builder_pending_payments[payment_index] = BuilderPendingPayment.empty()


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
        state.slot = state.slot + 1


def process_slot(state: BeaconState) -> None:
    slot_index = state.slot % SLOTS_PER_HISTORICAL_ROOT
    # Cache state root
    previous_state_root = hash_tree_root(state)
    state.state_roots[slot_index] = previous_state_root
    # Cache latest block header state root
    if state.latest_block_header.state_root == Bytes32():
        state.latest_block_header.state_root = previous_state_root
    # Cache block root
    previous_block_root = hash_tree_root(state.latest_block_header)
    state.block_roots[slot_index] = previous_block_root
    # [New in Gloas:EIP7732]
    # Unset the next payload availability
    next_slot_index = (state.slot + 1) % SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[next_slot_index] = Boolean(False)


def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    # [Modified in Gloas:EIP8061]
    process_pending_deposits(state)
    process_pending_consolidations(state)
    # [New in Gloas:EIP7732]
    process_builder_pending_payments(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    # [New in Gloas:EIP7732]
    process_ptc_window(state)


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
    state.justification_bits[0] = Boolean(False)
    if previous_epoch_target_balance * 3 >= total_active_balance * 2:
        state.current_justified_checkpoint = Checkpoint(
            epoch=previous_epoch, root=get_block_root(state, previous_epoch)
        )
        state.justification_bits[1] = Boolean(True)
    if current_epoch_target_balance * 3 >= total_active_balance * 2:
        state.current_justified_checkpoint = Checkpoint(
            epoch=current_epoch, root=get_block_root(state, current_epoch)
        )
        state.justification_bits[0] = Boolean(True)

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
    return increments * get_base_reward_per_increment(state)


def get_finality_delay(state: BeaconState) -> Epoch:
    return get_previous_epoch(state) - state.finalized_checkpoint.epoch


def is_in_inactivity_leak(state: BeaconState) -> bool:
    return get_finality_delay(state) > MIN_EPOCHS_TO_INACTIVITY_PENALTY


def get_eligible_validator_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    previous_epoch = get_previous_epoch(state)
    return [
        ValidatorIndex(index)
        for index, validator in enumerate(state.validators)
        if is_active_validator(validator, previous_epoch)
        or (validator.slashed and previous_epoch + 1 < validator.withdrawable_epoch)
    ]


def get_inactivity_penalty_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the inactivity penalty deltas by considering timely target participation flags and inactivity scores.
    """
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
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
            penalties[index] += penalty_numerator // penalty_denominator
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
    current_epoch = get_current_epoch(state)
    activation_epoch = compute_activation_exit_epoch(current_epoch)

    # Process activation eligibility, ejections, and activations
    for index, validator in enumerate(state.validators):
        # [Modified in Electra:EIP7251]
        if is_eligible_for_activation_queue(validator):
            validator.activation_eligibility_epoch = current_epoch + 1
        elif (
            is_active_validator(validator, current_epoch)
            and validator.effective_balance <= config.EJECTION_BALANCE
        ):
            # [Modified in Electra:EIP7251]
            initiate_validator_exit(state, ValidatorIndex(index))
        elif is_eligible_for_activation(state, validator):
            validator.activation_epoch = activation_epoch


def process_slashings(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    total_balance = get_total_active_balance(state)
    adjusted_total_slashing_balance = min(
        Gwei(sum(state.slashings)) * PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX, total_balance
    )
    increment = (
        EFFECTIVE_BALANCE_INCREMENT  # Factored out from total balance to avoid Uint64 overflow
    )
    penalty_per_effective_balance_increment = adjusted_total_slashing_balance // (
        total_balance // increment
    )
    for index, validator in enumerate(state.validators):
        if (
            validator.slashed
            and epoch + EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch
        ):
            effective_balance_increments = validator.effective_balance // increment
            # [Modified in Electra:EIP7251]
            penalty = penalty_per_effective_balance_increment * effective_balance_increments
            decrease_balance(state, ValidatorIndex(index), penalty)


def process_eth1_data_reset(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
    # Reset eth1 data votes
    if next_epoch % EPOCHS_PER_ETH1_VOTING_PERIOD == 0:
        state.eth1_data_votes = Eth1DataVotes()


def process_effective_balance_updates(state: BeaconState) -> None:
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = Uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        # [Modified in Electra:EIP7251]
        max_effective_balance = get_max_effective_balance(validator)

        if (
            balance + DOWNWARD_THRESHOLD < validator.effective_balance
            or validator.effective_balance + UPWARD_THRESHOLD < balance
        ):
            validator.effective_balance = min(
                balance - balance % EFFECTIVE_BALANCE_INCREMENT, max_effective_balance
            )


def process_slashings_reset(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
    # Reset slashings
    state.slashings[next_epoch % EPOCHS_PER_SLASHINGS_VECTOR] = Gwei(0)


def process_randao_mixes_reset(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    next_epoch = current_epoch + 1
    # Set randao mix
    state.randao_mixes[next_epoch % EPOCHS_PER_HISTORICAL_VECTOR] = get_randao_mix(
        state, current_epoch
    )


def process_block(state: BeaconState, block: BeaconBlock) -> None:
    # [New in Gloas:EIP7732]
    parent_slot = state.latest_block_header.slot

    # [New in Gloas:EIP7732]
    process_parent_execution_payload(state, block)
    process_block_header(state, block)
    # [Modified in Gloas:EIP7732]
    process_withdrawals(state)
    # [Modified in Gloas:EIP7732]
    # Removed `process_execution_payload`
    # [New in Gloas:EIP7732]
    process_execution_payload_bid(state, block.body.signed_execution_payload_bid)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in Gloas:EIP7732]
    process_operations(state, block.body, parent_slot)
    process_sync_aggregate(state, block.body.sync_aggregate)


def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the block is newer than latest block header
    assert block.slot > state.latest_block_header.slot
    # Verify that proposer index is the correct index
    assert block.proposer_index == get_beacon_proposer_index(state)
    # Verify that the parent matches
    assert block.parent_root == hash_tree_root(state.latest_block_header)
    # Cache current block as the new latest block
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=Root(),  # Overwritten in the next process_slot call
        body_root=hash_tree_root(block.body),
    )

    # Verify proposer is not slashed
    proposer = state.validators[block.proposer_index]
    assert not proposer.slashed


def process_randao(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    # Verify RANDAO reveal
    proposer = state.validators[get_beacon_proposer_index(state)]
    signing_root = compute_signing_root(epoch, get_domain(state, DOMAIN_RANDAO))
    assert bls.Verify(proposer.pubkey, signing_root, body.randao_reveal)
    # Mix in RANDAO reveal
    mix = xor(get_randao_mix(state, epoch), sha256(body.randao_reveal))
    state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR] = mix


def process_eth1_data(state: BeaconState, body: BeaconBlockBody) -> None:
    state.eth1_data_votes.append(body.eth1_data)
    if (
        state.eth1_data_votes.count(body.eth1_data) * 2
        > Uint64(EPOCHS_PER_ETH1_VOTING_PERIOD) * SLOTS_PER_EPOCH
    ):
        state.eth1_data = body.eth1_data


def process_operations(
    state: BeaconState,
    body: BeaconBlockBody,
    # [New in Gloas:EIP7732]
    parent_slot: Slot,
) -> None:
    assert len(body.deposits) == 0

    # [Modified in Gloas:EIP7732]
    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    # [New in Gloas:EIP7688]
    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.attester_slashings) <= MAX_ATTESTER_SLASHINGS_ELECTRA
    assert len(body.attestations) <= MAX_ATTESTATIONS_ELECTRA
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    assert len(body.bls_to_execution_changes) <= MAX_BLS_TO_EXECUTION_CHANGES
    assert len(body.payload_attestations) <= MAX_PAYLOAD_ATTESTATIONS

    # [Modified in Gloas:EIP7732]
    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    # [Modified in Gloas:EIP7732]
    for_ops(body.attestations, process_attestation, parent_slot)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    # [Modified in Gloas:EIP7732]
    # Removed `process_deposit_request`
    # [Modified in Gloas:EIP7732]
    # Removed `process_withdrawal_request`
    # [Modified in Gloas:EIP7732]
    # Removed `process_consolidation_request`
    # [New in Gloas:EIP7732]
    for_ops(body.payload_attestations, process_payload_attestation)


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


def process_attestation(
    state: BeaconState,
    attestation: Attestation,
    # [New in Gloas:EIP7732]
    parent_slot: Slot,
) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot

    # [Modified in Gloas:EIP7732]
    assert data.index < 2
    committee_indices = get_committee_indices(attestation.committee_bits)
    committee_offset = 0
    for committee_index in committee_indices:
        assert committee_index < get_committee_count_per_slot(state, data.target.epoch)
        committee = get_beacon_committee(state, data.slot, committee_index)
        committee_attesters = {
            attester_index
            for index, attester_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + index]
        }
        assert len(committee_attesters) > 0
        committee_offset += len(committee)

    # Bitfield length matches total number of participants
    assert len(attestation.aggregation_bits) == committee_offset

    # Participation flag indices
    # [Modified in Gloas:EIP7732]
    participation_flag_indices = get_attestation_participation_flag_indices(
        state, data, state.slot - data.slot, parent_slot
    )

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # [Modified in Gloas:EIP7732]
    if data.target.epoch == get_current_epoch(state):
        current_epoch_target = True
        epoch_participation = state.current_epoch_participation
        payment = state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH]
    else:
        current_epoch_target = False
        epoch_participation = state.previous_epoch_participation
        payment = state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH]

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        # [New in Gloas:EIP7732]
        had_no_participation = epoch_participation[index] == 0b0000_0000
        will_set_new_flag = False

        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight
                # [New in Gloas:EIP7732]
                will_set_new_flag = True

        # [New in Gloas:EIP7732]
        if (
            will_set_new_flag
            and had_no_participation
            and is_attestation_same_slot(state, data)
            and payment.withdrawal.amount > 0
        ):
            payment.weight += state.validators[index].effective_balance

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)

    # [New in Gloas:EIP7732]
    # Update builder payment weight
    if current_epoch_target:
        state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH] = payment
    else:
        state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH] = payment


def get_validator_from_deposit(
    pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Gwei
) -> Validator:
    validator = Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        effective_balance=Gwei(0),
        slashed=Boolean(False),
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
    )

    # [Modified in Electra:EIP7251]
    max_effective_balance = get_max_effective_balance(validator)
    validator.effective_balance = min(
        amount - amount % EFFECTIVE_BALANCE_INCREMENT, max_effective_balance
    )

    return validator


def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Gwei
) -> None:
    index = get_index_for_new_validator(state)
    # [Modified in Electra:EIP7251]
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, Uint64(0))


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
    # [New in Electra:EIP7251]
    # Only exit validator if it has no pending withdrawals in the queue
    assert get_pending_balance_to_withdraw(state, voluntary_exit.validator_index) == 0
    # Verify signature
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, config.CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)


def get_fast_confirmation_store(store: Store) -> FastConfirmationStore:
    return FastConfirmationStore(
        store=store,
        confirmed_root=store.finalized_checkpoint.root,
        previous_epoch_observed_justified_checkpoint=store.finalized_checkpoint,
        current_epoch_observed_justified_checkpoint=store.finalized_checkpoint,
        previous_epoch_greatest_unrealized_checkpoint=store.finalized_checkpoint,
        previous_slot_head=store.finalized_checkpoint.root,
        current_slot_head=store.finalized_checkpoint.root,
    )


def get_node_for_root(block_root: Root) -> ForkChoiceNode:
    # [Modified in Gloas:EIP7732]
    return ForkChoiceNode(root=block_root, payload_status=PAYLOAD_STATUS_PENDING)


def get_block_slot(store: Store, block_root: Root) -> Slot:
    """
    Return a slot of the block.
    """
    return store.blocks[block_root].slot


def get_block_epoch(store: Store, block_root: Root) -> Epoch:
    """
    Return an epoch of the block.
    """
    return compute_epoch_at_slot(store.blocks[block_root].slot)


def get_checkpoint_for_block(store: Store, block_root: Root, epoch: Epoch) -> Checkpoint:
    """
    Return a checkpoint in the chain of the block at the ``epoch``.
    """
    return Checkpoint(epoch=epoch, root=get_checkpoint_block(store, block_root, epoch))


def get_current_target(store: Store) -> Checkpoint:
    """
    Return current epoch target.
    """
    head = get_head(store).root
    current_epoch = get_current_store_epoch(store)
    return get_checkpoint_for_block(store, head, current_epoch)


def is_start_slot_at_epoch(slot: Slot) -> bool:
    """
    Return ``True`` if ``slot`` is the start slot of an epoch.
    """
    return compute_slots_since_epoch_start(slot) == 0


def get_ancestor_roots(store: Store, block_root: Root, terminal_root: Root) -> Sequence[Root]:
    """
    Return a list of ancestors of ``block_root`` inclusive until ``terminal_root`` exclusive.
    """
    root = block_root
    ancestor_roots: list[Root] = []
    while store.blocks[root].slot > store.blocks[terminal_root].slot:
        ancestor_roots.insert(0, root)
        root = store.blocks[root].parent_root

        # Return when terminal_root is reached
        if root == terminal_root:
            return ancestor_roots

    # Return empty list if terminal_root is not in the chain of block_root
    return []


def get_slot_committee(store: Store, slot: Slot) -> set[ValidatorIndex]:
    """
    Return participants of all committees in ``slot``.
    """
    head = get_head(store).root
    shuffling_source = store.block_states[head]
    committees_count = get_committee_count_per_slot(shuffling_source, compute_epoch_at_slot(slot))
    participants: set[ValidatorIndex] = set()
    for i in range(committees_count):
        participants.update(get_beacon_committee(shuffling_source, slot, CommitteeIndex(i)))
    return participants


def get_pulled_up_head_state(store: Store) -> BeaconState:
    """
    Return the state of the head pulled up to the current epoch if needed.
    """
    head = get_head(store).root
    head_state = store.block_states[head]
    if get_current_epoch(head_state) < get_current_store_epoch(store):
        pulled_up_state = head_state.copy()
        process_slots(pulled_up_state, compute_start_slot_at_epoch(get_current_store_epoch(store)))
        return pulled_up_state
    else:
        return head_state


def get_previous_balance_source(fcr_store: FastConfirmationStore) -> BeaconState:
    store = fcr_store.store
    return store.checkpoint_states[fcr_store.previous_epoch_observed_justified_checkpoint]


def get_current_balance_source(fcr_store: FastConfirmationStore) -> BeaconState:
    store = fcr_store.store
    return store.checkpoint_states[fcr_store.current_epoch_observed_justified_checkpoint]


def get_node_support_between_slots(
    store: Store,
    balance_source: BeaconState,
    node: ForkChoiceNode,
    start_slot: Slot,
    end_slot: Slot,
) -> Gwei:
    """
    Return support of the node by validators assigned to slots
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    participants: set[ValidatorIndex] = set()
    for slot in range(start_slot, end_slot + 1):
        participants.update(get_slot_committee(store, Slot(slot)))

    # Keep validators that were active at the balance_source epoch to be consistent
    # with get_total_active_balance() computation, also filter out slashed validators
    unslashed_and_active_indices = [
        index
        for index in participants
        if (
            not balance_source.validators[index].slashed
            and is_active_validator(
                balance_source.validators[index], get_current_epoch(balance_source)
            )
        )
    ]

    return Gwei(
        sum(
            balance_source.validators[index].effective_balance
            for index in unslashed_and_active_indices
            # Check that validator has voted in the support of the node
            # and has not been slashed
            if (
                index in store.latest_messages
                and get_supported_node(store, store.latest_messages[index]) == node
                and index not in store.equivocating_indices
            )
        )
    )


def is_full_validator_set_covered(start_slot: Slot, end_slot: Slot) -> bool:
    """
    Return ``True`` if the range between ``start_slot`` and ``end_slot`` (inclusive of both) includes an entire epoch.
    """
    start_full_epoch = compute_epoch_at_slot(start_slot + SLOTS_PER_EPOCH - 1)
    end_full_epoch = compute_epoch_at_slot(end_slot + 1)
    return start_full_epoch < end_full_epoch


def compute_committee_weight_between_slots(
    store: Store, balance_source: BeaconState, start_slot: Slot, end_slot: Slot
) -> Gwei:
    """
    Compute total weight of committees
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """

    # Sanity check
    if start_slot > end_slot:
        return Gwei(0)

    # If an entire epoch is covered by the range, return the total active balance
    if is_full_validator_set_covered(start_slot, end_slot):
        return get_total_active_balance(balance_source)

    # Get indices of validators assigned to committees between the slots
    participants: set[ValidatorIndex] = set()
    for slot in range(start_slot, end_slot + 1):
        participants.update(get_slot_committee(store, Slot(slot)))

    # Sort out validators not active in the view of a balance source
    active_participants: set[ValidatorIndex] = set()
    current_epoch = get_current_epoch(balance_source)
    for index in participants:
        if is_active_validator(balance_source.validators[index], current_epoch):
            active_participants.add(index)

    # Return total balance of the participants
    return get_total_balance(balance_source, active_participants)


def get_equivocation_score(
    store: Store,
    balance_source: BeaconState,
    start_slot: Slot,
    end_slot: Slot,
) -> Gwei:
    """
    Return total weight of equivocating participants of all committees
    in the slots between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    committee_indices: set[ValidatorIndex] = set()
    for slot in range(start_slot, end_slot + 1):
        committee_indices.update(get_slot_committee(store, Slot(slot)))

    # Keep equivocating validators that were active at the balance_source epoch to be consistent
    # with get_total_active_balance() computation
    active_equivocating_indices = [
        index
        for index in committee_indices.intersection(store.equivocating_indices)
        if is_active_validator(balance_source.validators[index], get_current_epoch(balance_source))
    ]

    return Gwei(
        sum(
            balance_source.validators[index].effective_balance
            for index in active_equivocating_indices
        )
    )


def compute_adversarial_weight(
    store: Store,
    balance_source: BeaconState,
    start_slot: Slot,
    end_slot: Slot,
) -> Gwei:
    """
    Return maximum possible adversarial weight in the committees of the slots
    between ``start_slot`` and ``end_slot`` (inclusive of both).
    """
    maximum_weight = compute_committee_weight_between_slots(
        store, balance_source, start_slot, end_slot
    )
    max_adversarial_weight = maximum_weight // 100 * config.CONFIRMATION_BYZANTINE_THRESHOLD

    # Discount total weight of equivocating validators
    equivocation_score = get_equivocation_score(store, balance_source, start_slot, end_slot)
    if max_adversarial_weight > equivocation_score:
        return max_adversarial_weight - equivocation_score
    else:
        return Gwei(0)


def get_adversarial_weight(store: Store, balance_source: BeaconState, block_root: Root) -> Gwei:
    """
    Return maximum adversarial weight that can support the block.
    """
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    if get_block_epoch(store, block_root) > get_block_epoch(store, block.parent_root):
        # Use the first epoch slot as the start slot when crossing epoch boundary
        start_slot = compute_start_slot_at_epoch(get_block_epoch(store, block_root))
        return compute_adversarial_weight(store, balance_source, start_slot, current_slot - 1)
    else:
        return compute_adversarial_weight(store, balance_source, block.slot, current_slot - 1)


def compute_empty_slot_support_discount(
    store: Store, balance_source: BeaconState, block_root: Root
) -> Gwei:
    """
    Return weight that can be discounted during the safety threshold computation
    if there are empty slots preceding the block.
    """
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]
    # No empty slot
    if parent_block.slot + 1 == block.slot:
        return Gwei(0)

    # Discount votes supporting the parent block if they are from the committees of empty slots
    parent_node = get_ancestor(store, get_node_for_root(block_root), parent_block.slot)
    parent_support_in_empty_slots = get_node_support_between_slots(
        store,
        balance_source,
        parent_node,
        parent_block.slot + 1,
        block.slot - 1,
    )
    # Adversarial weight is not discounted
    adversarial_weight = compute_adversarial_weight(
        store, balance_source, parent_block.slot + 1, block.slot - 1
    )
    if parent_support_in_empty_slots > adversarial_weight:
        return parent_support_in_empty_slots - adversarial_weight
    else:
        return Gwei(0)


def get_support_discount(store: Store, balance_source: BeaconState, block_root: Root) -> Gwei:
    """
    Return weight that can be discounted during the safety threshold computation for the block.
    """
    return compute_empty_slot_support_discount(store, balance_source, block_root)


def compute_safety_threshold(store: Store, block_root: Root, balance_source: BeaconState) -> Gwei:
    """
    Compute the LMD-GHOST safety threshold for ``block_root``.
    """
    current_slot = get_current_slot(store)
    block = store.blocks[block_root]
    parent_block = store.blocks[block.parent_root]

    proposer_score = compute_proposer_score(balance_source)
    maximum_support = compute_committee_weight_between_slots(
        store, balance_source, parent_block.slot + 1, current_slot - 1
    )
    support_discount = get_support_discount(store, balance_source, block_root)
    adversarial_weight = get_adversarial_weight(store, balance_source, block_root)

    # With precise committee weight computation
    # support_discount must never exceed maximum_support
    assert support_discount <= maximum_support

    # Return (maximum_support + proposer_score - support_discount) // 2 + adversarial_weight
    return (maximum_support + proposer_score + 2 * adversarial_weight - support_discount) // 2


def is_one_confirmed(store: Store, balance_source: BeaconState, block_root: Root) -> bool:
    """
    Return ``True`` if and only if the block is LMD-GHOST safe.
    """
    support = get_attestation_score(store, get_node_for_root(block_root), balance_source)
    safety_threshold = compute_safety_threshold(store, block_root, balance_source)
    return support > safety_threshold


def is_confirmed_chain_safe(fcr_store: FastConfirmationStore, confirmed_root: Root) -> bool:
    """
    Return ``True`` if and only if all blocks of the confirmed chain
    starting from current_epoch_observed_justified_checkpoint are LMD-GHOST safe.
    """
    store = fcr_store.store
    # Check if the confirmed_root has current_epoch_observed_justified_checkpoint in its chain
    if fcr_store.current_epoch_observed_justified_checkpoint != get_checkpoint_for_block(
        store, confirmed_root, fcr_store.current_epoch_observed_justified_checkpoint.epoch
    ):
        return False

    current_epoch = get_current_store_epoch(store)
    if fcr_store.current_epoch_observed_justified_checkpoint.epoch + 1 >= current_epoch:
        # Exclude the justified checkpoint block if it is from the previous epoch
        # as then this block will always be canonical in this case.
        start_root_exclusive = fcr_store.current_epoch_observed_justified_checkpoint.root
    else:
        # Limit reconfirmation to the first block of the previous epoch
        # as if it is successful, reconfirmation of the ancestors is implied.
        ancestor_at_previous_epoch_start = get_ancestor(
            store,
            get_node_for_root(confirmed_root),
            compute_start_slot_at_epoch(current_epoch - 1),
        ).root
        if get_block_epoch(store, ancestor_at_previous_epoch_start) + 1 == current_epoch:
            # The parent of the first block of the previous epoch
            start_root_exclusive = store.blocks[ancestor_at_previous_epoch_start].parent_root
        else:
            # The last block of the epoch before the previous one
            start_root_exclusive = ancestor_at_previous_epoch_start

    # Run is_one_confirmed for each block in the confirmed chain with the previous epoch balance source
    chain_roots = get_ancestor_roots(store, confirmed_root, start_root_exclusive)
    return all(
        is_one_confirmed(store, get_previous_balance_source(fcr_store), root)
        for root in chain_roots
    )


def get_current_target_score(store: Store) -> Gwei:
    """
    Return the estimate of FFG support of the current epoch target by using LMD-GHOST votes.
    """
    target = get_current_target(store)
    state = get_pulled_up_head_state(store)
    unslashed_and_active_indices = [
        index
        for index in get_active_validator_indices(state, get_current_epoch(state))
        if not state.validators[index].slashed
    ]
    return Gwei(
        sum(
            state.validators[index].effective_balance
            for index in unslashed_and_active_indices
            if (
                index in store.latest_messages
                and index not in store.equivocating_indices
                and target
                == get_checkpoint_for_block(
                    store,
                    store.latest_messages[index].root,
                    get_latest_message_epoch(store.latest_messages[index]),
                )
            )
        )
    )


def compute_honest_ffg_support_for_current_target(store: Store) -> Gwei:
    """
    Compute honest FFG support of the current epoch target.
    """
    current_slot = get_current_slot(store)
    current_epoch = compute_epoch_at_slot(current_slot)
    balance_source = get_pulled_up_head_state(store)
    total_active_balance = get_total_active_balance(balance_source)

    # Compute FFG support for the target
    ffg_support_for_checkpoint = get_current_target_score(store)

    # Compute the total FFG weight up to, but excluding, the current slot
    ffg_weight_till_now = compute_committee_weight_between_slots(
        store, balance_source, compute_start_slot_at_epoch(current_epoch), current_slot - 1
    )

    # Compute remaining honest FFG weight
    remaining_ffg_weight = total_active_balance - ffg_weight_till_now
    remaining_honest_ffg_weight = (
        remaining_ffg_weight // 100 * (100 - config.CONFIRMATION_BYZANTINE_THRESHOLD)
    )

    # Compute potential adversarial weight
    adversarial_weight = compute_adversarial_weight(
        store, balance_source, compute_start_slot_at_epoch(current_epoch), current_slot - 1
    )

    # Compute min honest FFG support
    min_honest_ffg_support = saturating_sub(ffg_support_for_checkpoint, adversarial_weight)

    return min_honest_ffg_support + remaining_honest_ffg_weight


def will_no_conflicting_checkpoint_be_justified(store: Store) -> bool:
    """
    Return ``True`` if and only if no checkpoint conflicting with the current target can ever be justified.
    """

    # If the target is unrealized justified then no conflicting checkpoint can be justified
    if get_current_target(store) == store.unrealized_justified_checkpoint:
        return True

    state = get_pulled_up_head_state(store)
    total_active_balance = get_total_active_balance(state)
    honest_ffg_support = compute_honest_ffg_support_for_current_target(store)
    return 3 * honest_ffg_support > 1 * total_active_balance


def will_current_target_be_justified(store: Store) -> bool:
    """
    Return ``True`` if and only if the current target will eventually be justified.
    """
    state = get_pulled_up_head_state(store)
    total_active_balance = get_total_active_balance(state)
    honest_ffg_support = compute_honest_ffg_support_for_current_target(store)
    return 3 * honest_ffg_support >= 2 * total_active_balance


def update_fast_confirmation_variables(fcr_store: FastConfirmationStore) -> None:
    # Update prev and curr slot head
    store = fcr_store.store
    fcr_store.previous_slot_head = fcr_store.current_slot_head
    fcr_store.current_slot_head = get_head(store).root

    # Update greatest unrealized justified checkpoint at the last slot of an epoch
    if is_start_slot_at_epoch(get_current_slot(store) + 1):
        fcr_store.previous_epoch_greatest_unrealized_checkpoint = (
            store.unrealized_justified_checkpoint
        )

    # Update observed justified checkpoints at the start of an epoch
    if is_start_slot_at_epoch(get_current_slot(store)):
        fcr_store.previous_epoch_observed_justified_checkpoint = (
            fcr_store.current_epoch_observed_justified_checkpoint
        )
        fcr_store.current_epoch_observed_justified_checkpoint = (
            fcr_store.previous_epoch_greatest_unrealized_checkpoint
        )


def find_latest_confirmed_descendant(
    fcr_store: FastConfirmationStore, latest_confirmed_root: Root
) -> Root:
    """
    Return the most recent confirmed block in the suffix of the canonical chain
    starting from ``latest_confirmed_root``.
    """
    store = fcr_store.store
    head = get_head(store).root
    current_epoch = get_current_store_epoch(store)
    confirmed_root = latest_confirmed_root

    if (
        get_block_epoch(store, confirmed_root) + 1 == current_epoch
        and get_voting_source(store, fcr_store.previous_slot_head).epoch + 2 >= current_epoch
        and (
            is_start_slot_at_epoch(get_current_slot(store))
            or (
                will_no_conflicting_checkpoint_be_justified(store)
                and (
                    store.unrealized_justifications[fcr_store.previous_slot_head].epoch + 1
                    >= current_epoch
                    or store.unrealized_justifications[head].epoch + 1 >= current_epoch
                )
            )
        )
    ):
        # Get suffix of the canonical chain
        canonical_roots = get_ancestor_roots(store, head, confirmed_root)

        # Starting with the child of the latest_confirmed_root
        # move towards the head in attempt to advance the confirmed block
        # and stop when the first unconfirmed descendant is encountered
        for block_root in canonical_roots:
            block_epoch = get_block_epoch(store, block_root)

            # If the current epoch is reached, exit the loop
            # as this code is meant to confirm blocks from the previous epoch
            if block_epoch == current_epoch:
                break

            # The algorithm can only rely on the previous head
            # if it is a descendant of the block that is attempted to be confirmed
            if not is_ancestor(
                store,
                get_node_for_root(fcr_store.previous_slot_head),
                get_node_for_root(block_root),
            ):
                break

            if not is_one_confirmed(store, get_current_balance_source(fcr_store), block_root):
                break

            confirmed_root = block_root

    if (
        is_start_slot_at_epoch(get_current_slot(store))
        or store.unrealized_justifications[head].epoch + 1 >= current_epoch
    ):
        # Get suffix of the canonical chain
        canonical_roots = get_ancestor_roots(store, head, confirmed_root)

        tentative_confirmed_root = confirmed_root

        for block_root in canonical_roots:
            block_epoch = get_block_epoch(store, block_root)
            tentative_confirmed_epoch = get_block_epoch(store, tentative_confirmed_root)

            # The following condition can only be true the first time
            # the algorithm advances to a block from the current epoch
            if block_epoch > tentative_confirmed_epoch:
                # To confirm blocks from the current epoch ensure that
                # current epoch target will be justified
                if not will_current_target_be_justified(store):
                    break

            if not is_one_confirmed(store, get_current_balance_source(fcr_store), block_root):
                break

            tentative_confirmed_root = block_root

        # The tentative_confirmed_root can only be confirmed
        # if it is for sure not going to be reorged out in either the current or next epoch.
        if get_block_epoch(store, tentative_confirmed_root) == current_epoch or (
            get_voting_source(store, tentative_confirmed_root).epoch + 2 >= current_epoch
            and (
                is_start_slot_at_epoch(get_current_slot(store))
                or will_no_conflicting_checkpoint_be_justified(store)
            )
        ):
            confirmed_root = tentative_confirmed_root

    return confirmed_root


def get_latest_confirmed(fcr_store: FastConfirmationStore) -> Root:
    """
    Return the most recent confirmed block by executing the FCR algorithm.
    """
    store = fcr_store.store
    confirmed_root = fcr_store.confirmed_root
    current_epoch = get_current_store_epoch(store)

    # Revert to finalized block if either of the following is true:
    # 1) the latest confirmed block's epoch is older than the previous epoch,
    # 2) the latest confirmed block does not belong to the canonical chain,
    # 3) the confirmed chain starting from the current epoch observed justified checkpoint
    #    cannot be re-confirmed at the start of the current epoch.
    head = get_head(store).root
    if (
        get_block_epoch(store, confirmed_root) + 1 < current_epoch
        or not is_ancestor(store, get_node_for_root(head), get_node_for_root(confirmed_root))
        or (
            is_start_slot_at_epoch(get_current_slot(store))
            and not is_confirmed_chain_safe(fcr_store, confirmed_root)
        )
    ):
        confirmed_root = store.finalized_checkpoint.root

    # Restart the confirmation chain if each of the following conditions are true:
    # 1) it is the start of the current epoch,
    # 2) epoch of fcr_store.current_epoch_observed_justified_checkpoint.root equals to the previous epoch,
    # 3) fcr_store.current_epoch_observed_justified_checkpoint equals to unrealized justification of the head,
    # 4) confirmed block is older than the block of fcr_store.current_epoch_observed_justified_checkpoint.
    is_epoch_start = is_start_slot_at_epoch(get_current_slot(store))
    observed_justified_block_slot = get_block_slot(
        store, fcr_store.current_epoch_observed_justified_checkpoint.root
    )
    is_observed_justified_block_epoch_ok = (
        compute_epoch_at_slot(observed_justified_block_slot) + 1 == current_epoch
    )
    is_head_unrealized_justified_ok = (
        fcr_store.current_epoch_observed_justified_checkpoint
        == store.unrealized_justifications[head]
    )
    is_confirmed_block_stale = get_block_slot(store, confirmed_root) < observed_justified_block_slot
    if (
        is_epoch_start
        and is_observed_justified_block_epoch_ok
        and is_head_unrealized_justified_ok
        and is_confirmed_block_stale
    ):
        confirmed_root = fcr_store.current_epoch_observed_justified_checkpoint.root

    # Attempt to further advance the latest confirmed block
    if get_block_epoch(store, confirmed_root) + 1 >= current_epoch:
        return find_latest_confirmed_descendant(fcr_store, confirmed_root)
    else:
        return confirmed_root


def block_should_be_finalized(store: Store, block_root: Root) -> bool:
    block_slot = get_block_slot(store, block_root)
    next_checkpoint_epoch = compute_epoch_at_slot(block_slot + SLOTS_PER_EPOCH - 1)
    earliest_finality_slot = compute_start_slot_at_epoch(next_checkpoint_epoch + 2)
    return earliest_finality_slot <= get_current_slot(store)


def get_restart_resilient_confirmed_root(fcr_store: FastConfirmationStore) -> Root:
    store = fcr_store.store
    root_before_restart = get_root_confirmed_before_restart()
    root_before_restart_slot = get_block_slot(store, root_before_restart)

    # Recently confirmed block has advanced beyond the block that was confirmed
    # before the node restart
    if root_before_restart_slot <= get_block_slot(store, fcr_store.confirmed_root):
        return fcr_store.confirmed_root

    # If the block is old enough it either has been finalized already or
    # finality has been delayed which makes block confirmed before restart
    # unreliable
    if block_should_be_finalized(store, root_before_restart):
        return fcr_store.confirmed_root

    # If a block confirmed before the restart is not canonical,
    # return the recently confirmed block
    if not is_ancestor(store, get_head(store), get_node_for_root(root_before_restart)):
        return fcr_store.confirmed_root

    return root_before_restart


def on_fast_confirmation(fcr_store: FastConfirmationStore) -> None:
    update_fast_confirmation_variables(fcr_store)
    fcr_store.confirmed_root = get_latest_confirmed(fcr_store)


def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_epoch = get_current_epoch(anchor_state)
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    genesis_time_ms = seconds_to_milliseconds(anchor_state.genesis_time)
    return Store(
        time_ms=compute_time_at_slot_ms(genesis_time_ms, anchor_state.slot),
        genesis_time_ms=genesis_time_ms,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        unrealized_justified_checkpoint=justified_checkpoint,
        unrealized_finalized_checkpoint=finalized_checkpoint,
        proposer_boost_root=Root(),
        equivocating_indices=set(),
        blocks={anchor_root: anchor_block.copy()},
        block_states={anchor_root: anchor_state.copy()},
        # [New in Gloas:EIP7732]
        block_timeliness={anchor_root: [True, True]},
        checkpoint_states={justified_checkpoint: anchor_state.copy()},
        latest_messages={},
        unrealized_justifications={anchor_root: justified_checkpoint},
        # [New in Gloas:EIP7732]
        payloads={},
        # [New in Gloas:EIP7732]
        payload_timeliness_vote={anchor_root: [None] * PTC_SIZE},
        # [New in Gloas:EIP7732]
        payload_data_availability_vote={anchor_root: [None] * PTC_SIZE},
    )


def get_time_into_slot_ms(store: Store) -> Uint64:
    return store.time_ms - compute_time_at_slot_ms(store.genesis_time_ms, get_current_slot(store))


def get_slots_since_genesis(store: Store) -> Slot:
    return compute_slot_at_time_ms(store.genesis_time_ms, store.time_ms)


def get_current_slot(store: Store) -> Slot:
    return get_slots_since_genesis(store)


def get_current_store_epoch(store: Store) -> Epoch:
    return compute_epoch_at_slot(get_current_slot(store))


def compute_slots_since_epoch_start(slot: Slot) -> Slot:
    return slot - compute_start_slot_at_epoch(compute_epoch_at_slot(slot))


def get_ancestor(store: Store, node: ForkChoiceNode, slot: Slot) -> ForkChoiceNode:
    block = store.blocks[node.root]
    if block.slot > slot:
        # [Modified in Gloas:EIP7732]
        parent = ForkChoiceNode(
            root=block.parent_root,
            payload_status=get_parent_payload_status(store, block),
        )
        return get_ancestor(store, parent, slot)
    return node


def is_ancestor(store: Store, node: ForkChoiceNode, ancestor: ForkChoiceNode) -> bool:
    node_ancestor = get_ancestor(store, node, store.blocks[ancestor.root].slot)
    if node_ancestor.root != ancestor.root:
        return False

    # [New in Gloas:EIP7732]
    return (
        node_ancestor.payload_status == ancestor.payload_status
        or ancestor.payload_status == PAYLOAD_STATUS_PENDING
    )


def calculate_committee_fraction(state: BeaconState, committee_percent: Uint64) -> Gwei:
    unslashed_and_active_indices: set[ValidatorIndex] = set()
    for index in get_active_validator_indices(state, get_current_epoch(state)):
        if not state.validators[index].slashed:
            unslashed_and_active_indices.add(index)
    total_balance = get_total_balance(state, unslashed_and_active_indices)
    committee_weight = total_balance // Uint64(SLOTS_PER_EPOCH)
    return (committee_weight * committee_percent) // 100


def get_checkpoint_block(store: Store, root: Root, epoch: Epoch) -> Root:
    """
    Compute the checkpoint block for epoch ``epoch`` in the chain of block ``root``
    """
    epoch_first_slot = compute_start_slot_at_epoch(epoch)
    # [Modified in Gloas:EIP7732]
    node = ForkChoiceNode(root=root, payload_status=PAYLOAD_STATUS_PENDING)
    return get_ancestor(store, node, epoch_first_slot).root


def get_supported_node(store: Store, message: LatestMessage) -> ForkChoiceNode:
    """
    Return a node supported by the ``message``.
    """
    # [New in Gloas:EIP7732]
    block = store.blocks[message.root]
    if block.slot < message.slot:
        if message.payload_present:
            payload_status = PAYLOAD_STATUS_FULL
        else:
            payload_status = PAYLOAD_STATUS_EMPTY
    else:
        payload_status = PAYLOAD_STATUS_PENDING

    # [Modified in Gloas:EIP7732]
    return ForkChoiceNode(root=message.root, payload_status=payload_status)


def get_attestation_score(store: Store, node: ForkChoiceNode, state: BeaconState) -> Gwei:
    unslashed_and_active_indices = [
        index
        for index in get_active_validator_indices(state, get_current_epoch(state))
        if not state.validators[index].slashed
    ]
    return Gwei(
        sum(
            state.validators[index].effective_balance
            for index in unslashed_and_active_indices
            if (
                index in store.latest_messages
                and index not in store.equivocating_indices
                and is_ancestor(
                    store, get_supported_node(store, store.latest_messages[index]), node
                )
            )
        )
    )


def compute_proposer_score(state: BeaconState) -> Gwei:
    return calculate_committee_fraction(state, config.PROPOSER_SCORE_BOOST)


def get_proposer_score(store: Store) -> Gwei:
    justified_checkpoint_state = store.checkpoint_states[store.justified_checkpoint]
    return compute_proposer_score(justified_checkpoint_state)


def get_weight(store: Store, node: ForkChoiceNode) -> Gwei:
    # [New in Gloas:EIP7732]
    if is_previous_slot_payload_decision(store, node):
        return Gwei(0)

    state = store.checkpoint_states[store.justified_checkpoint]
    attestation_score = get_attestation_score(store, node, state)
    # [Modified in Gloas:EIP7732]
    if not should_apply_proposer_boost(store):
        # Return only attestation score if proposer boost should not apply
        return attestation_score

    # Calculate proposer score if proposer boost should apply
    proposer_score = Gwei(0)
    # [Modified in Gloas:EIP7732]
    proposer_boost_node = ForkChoiceNode(
        root=store.proposer_boost_root, payload_status=PAYLOAD_STATUS_PENDING
    )
    # Boost is applied if ``node`` is an ancestor of ``proposer_boost_node``
    if is_ancestor(store, proposer_boost_node, node):
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


def get_node_children(store: Store, node: ForkChoiceNode) -> Sequence[ForkChoiceNode]:
    if node.payload_status == PAYLOAD_STATUS_PENDING:
        children = [ForkChoiceNode(root=node.root, payload_status=PAYLOAD_STATUS_EMPTY)]
        if is_payload_verified(store, node.root):
            children.append(ForkChoiceNode(root=node.root, payload_status=PAYLOAD_STATUS_FULL))
        return children
    else:
        return [
            ForkChoiceNode(root=root, payload_status=PAYLOAD_STATUS_PENDING)
            for root in store.blocks
            if (
                store.blocks[root].parent_root == node.root
                and node.payload_status == get_parent_payload_status(store, store.blocks[root])
            )
        ]


def filter_node_tree(store: Store, node: ForkChoiceNode) -> Sequence[ForkChoiceNode]:
    children = get_node_children(store, node)

    # If any children branches contain expected finalized/justified checkpoints,
    # include this node and those descendants in the filtered node tree.
    if any(children):
        viable_nodes: list[ForkChoiceNode] = []
        for child in children:
            viable_nodes.extend(filter_node_tree(store, child))
        if any(viable_nodes):
            return viable_nodes + [node]
        return []

    current_epoch = get_current_store_epoch(store)
    voting_source = get_voting_source(store, node.root)

    # The voting source should be either at the same height as the store's justified checkpoint or
    # not more than two epochs ago
    correct_justified = (
        store.justified_checkpoint.epoch == GENESIS_EPOCH
        or voting_source.epoch == store.justified_checkpoint.epoch
        or voting_source.epoch + 2 >= current_epoch
    )

    finalized_checkpoint_block = get_checkpoint_block(
        store,
        node.root,
        store.finalized_checkpoint.epoch,
    )

    correct_finalized = (
        store.finalized_checkpoint.epoch == GENESIS_EPOCH
        or store.finalized_checkpoint.root == finalized_checkpoint_block
    )

    # If expected finalized/justified, add to viable node tree and signal viability to parent.
    if correct_justified and correct_finalized:
        return [node]

    # Otherwise, branch not viable
    return []


def get_filtered_node_tree(store: Store) -> Sequence[ForkChoiceNode]:
    """
    Retrieve a filtered node tree from ``store``, only returning branches
    whose leaf state's justified/finalized info agrees with that in ``store``.
    """
    # [Modified in Gloas:EIP7732]
    base = ForkChoiceNode(
        root=store.justified_checkpoint.root,
        payload_status=PAYLOAD_STATUS_PENDING,
    )
    return filter_node_tree(store, base)


def get_head(store: Store) -> ForkChoiceNode:
    # Get filtered node tree that only includes viable branches
    nodes = get_filtered_node_tree(store)

    # [New in Gloas:EIP7732]
    # Return empty node if there are no viable nodes
    if not any(nodes):
        return ForkChoiceNode(
            root=store.justified_checkpoint.root,
            payload_status=PAYLOAD_STATUS_EMPTY,
        )

    # Execute the LMD-GHOST fork-choice
    head = ForkChoiceNode(
        root=store.justified_checkpoint.root,
        # [New in Gloas:EIP7732]
        payload_status=PAYLOAD_STATUS_PENDING,
    )

    while True:
        children = [child for child in get_node_children(store, head) if child in nodes]
        if len(children) == 0:
            return head
        # Sort by latest attesting balance with ties broken lexicographically
        head = max(
            children,
            key=lambda child: (
                get_weight(store, child),
                child.root,
                # [New in Gloas:EIP7732]
                get_payload_status_tiebreaker(store, child),
            ),
        )


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


def get_latest_message_epoch(latest_message: LatestMessage) -> Epoch:
    return compute_epoch_at_slot(latest_message.slot)


def seconds_to_milliseconds(seconds: Uint64) -> Uint64:
    """
    Convert seconds to milliseconds with overflow protection.
    Returns ``UINT64_MAX`` if the result would overflow.
    """
    if seconds > UINT64_MAX // 1000:
        return UINT64_MAX
    return seconds * 1000


def milliseconds_to_seconds(milliseconds: Uint64) -> Uint64:
    """
    Convert milliseconds to seconds, discarding any remainder.
    """
    return milliseconds // 1000


def get_slot_component_duration_ms(basis_points: Uint64) -> Uint64:
    """
    Calculate the duration of a slot component, rounded to the nearest millisecond.
    """
    return (basis_points * config.SLOT_DURATION_MS + BASIS_POINTS // 2) // BASIS_POINTS


def get_attestation_due_ms() -> Uint64:
    # [Modified in Gloas]
    return get_slot_component_duration_ms(config.ATTESTATION_DUE_BPS_GLOAS)


def get_proposer_reorg_cutoff_ms() -> Uint64:
    return get_slot_component_duration_ms(config.PROPOSER_REORG_CUTOFF_BPS)


def get_aggregate_due_ms() -> Uint64:
    # [Modified in Gloas]
    return get_slot_component_duration_ms(config.AGGREGATE_DUE_BPS_GLOAS)


def is_head_late(store: Store, head_root: Root) -> bool:
    return not store.block_timeliness[head_root][ATTESTATION_TIMELINESS_INDEX]


def is_ffg_competitive(store: Store, head_root: Root, parent_root: Root) -> bool:
    return (
        store.unrealized_justifications[head_root] == store.unrealized_justifications[parent_root]
    )


def is_finalization_ok(store: Store, slot: Slot) -> bool:
    epochs_since_finalization = compute_epoch_at_slot(slot) - store.finalized_checkpoint.epoch
    return epochs_since_finalization <= config.REORG_MAX_EPOCHS_SINCE_FINALIZATION


def is_proposing_on_time(store: Store) -> bool:
    return get_time_into_slot_ms(store) <= get_proposer_reorg_cutoff_ms()


def is_head_weak(store: Store, head_root: Root) -> bool:
    # Calculate weight threshold for weak head
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    reorg_threshold = calculate_committee_fraction(
        justified_state, config.REORG_HEAD_WEIGHT_THRESHOLD
    )

    # Compute head weight including equivocations
    head_state = store.block_states[head_root]
    head_block = store.blocks[head_root]
    epoch = compute_epoch_at_slot(head_block.slot)
    # [Modified in Gloas:EIP7732]
    head_node = ForkChoiceNode(root=head_root, payload_status=PAYLOAD_STATUS_PENDING)
    head_weight = get_attestation_score(store, head_node, justified_state)
    for index in range(get_committee_count_per_slot(head_state, epoch)):
        committee = get_beacon_committee(head_state, head_block.slot, CommitteeIndex(index))
        head_weight += Gwei(
            sum(
                justified_state.validators[index].effective_balance
                for index in committee
                if index in store.equivocating_indices
            )
        )

    return head_weight < reorg_threshold


def is_parent_strong(store: Store, root: Root) -> bool:
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    parent_threshold = calculate_committee_fraction(
        justified_state, config.REORG_PARENT_WEIGHT_THRESHOLD
    )
    parent_root = store.blocks[root].parent_root
    # [Modified in Gloas:EIP7732]
    parent_node = ForkChoiceNode(root=parent_root, payload_status=PAYLOAD_STATUS_PENDING)
    parent_weight = get_attestation_score(store, parent_node, justified_state)
    return parent_weight > parent_threshold


def is_proposer_equivocation(store: Store, root: Root) -> bool:
    block = store.blocks[root]
    proposer_index = block.proposer_index
    slot = block.slot
    # roots from the same slot and proposer
    matching_roots = [
        root
        for root, block in store.blocks.items()
        if (block.proposer_index == proposer_index and block.slot == slot)
    ]
    return len(matching_roots) > 1


def get_proposer_head(store: Store, head_node: ForkChoiceNode, slot: Slot) -> ForkChoiceNode:
    head_block = store.blocks[head_node.root]
    parent_root = head_block.parent_root
    parent_block = store.blocks[parent_root]
    # [Modified in Gloas:EIP7732]
    parent_payload_status = get_parent_payload_status(store, head_block)
    parent_node = ForkChoiceNode(root=parent_root, payload_status=parent_payload_status)

    # Only re-org the head block if it arrived later than the attestation deadline.
    head_late = is_head_late(store, head_node.root)

    # Ensure that the FFG information of the new head will be competitive with the current head.
    ffg_competitive = is_ffg_competitive(store, head_node.root, parent_root)

    # Do not re-org if the chain is not finalizing with acceptable frequency.
    finalization_ok = is_finalization_ok(store, slot)

    # Only re-org if we are proposing on-time.
    proposing_on_time = is_proposing_on_time(store)

    # Only re-org a single slot at most.
    parent_slot_ok = parent_block.slot + 1 == head_block.slot
    current_time_ok = head_block.slot + 1 == slot
    single_slot_reorg = parent_slot_ok and current_time_ok

    # Check that the head has few enough votes to be overpowered by our proposer boost.
    assert store.proposer_boost_root != head_node.root  # ensure boost has worn off
    head_weak = is_head_weak(store, head_node.root)

    # Check that the missing votes are assigned to the parent and not being hoarded.
    parent_strong = is_parent_strong(store, head_node.root)

    # Re-org more aggressively if there is a proposer equivocation in the previous slot.
    proposer_equivocation = is_proposer_equivocation(store, head_node.root)

    if all(
        [
            head_late,
            ffg_competitive,
            finalization_ok,
            proposing_on_time,
            single_slot_reorg,
            head_weak,
            parent_strong,
        ]
    ):
        # We can re-org the current head by building upon its parent node.
        return parent_node
    elif all([head_weak, current_time_ok, proposer_equivocation]):
        return parent_node
    else:
        return head_node


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


def on_tick_per_slot(store: Store, time_ms: Uint64) -> None:
    previous_slot = get_current_slot(store)

    # Update store time
    store.time_ms = time_ms

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
    previous_epoch = saturating_sub(current_epoch, 1)
    # If attestation target is from a future epoch, delay consideration until the epoch arrives
    assert target.epoch in [current_epoch, previous_epoch]


def validate_on_attestation(store: Store, attestation: Attestation, is_from_block: bool) -> None:
    target = attestation.data.target

    # If the given attestation is not from a beacon block message,
    # we have to check the target epoch scope.
    if not is_from_block:
        validate_target_epoch_against_current_time(store, attestation)

    # Check that the epoch number and slot number are matching.
    assert target.epoch == compute_epoch_at_slot(attestation.data.slot)

    # Attestation target must be for a known block. If target block
    # is unknown, delay consideration until block is found.
    assert target.root in store.blocks

    # Attestations must be for a known block. If block
    # is unknown, delay consideration until the block is found.
    assert attestation.data.beacon_block_root in store.blocks
    # Attestations must not be for blocks in the future.
    # If not, the attestation should not be considered.
    block_slot = store.blocks[attestation.data.beacon_block_root].slot
    assert block_slot <= attestation.data.slot

    # [New in Gloas:EIP7732]
    assert attestation.data.index in [0, 1]
    if block_slot == attestation.data.slot:
        assert attestation.data.index == 0
    # [New in Gloas:EIP7732]
    # If attesting for a full node, the payload must be known
    if attestation.data.index == 1:
        assert is_payload_verified(store, attestation.data.beacon_block_root)

    # LMD vote must be consistent with FFG vote target
    assert target.root == get_checkpoint_block(
        store, attestation.data.beacon_block_root, target.epoch
    )

    # Attestations can only affect the fork-choice of subsequent slots.
    # Delay consideration in the fork-choice until their slot is in the past.
    assert get_current_slot(store) >= attestation.data.slot + 1


def store_target_checkpoint_state(store: Store, target: Checkpoint) -> None:
    # Store target checkpoint state if not yet seen
    if target not in store.checkpoint_states:
        base_state = store.block_states[target.root].copy()
        if base_state.slot < compute_start_slot_at_epoch(target.epoch):
            process_slots(base_state, compute_start_slot_at_epoch(target.epoch))
        store.checkpoint_states[target] = base_state


def update_latest_messages(
    store: Store, attesting_indices: Sequence[ValidatorIndex], attestation: Attestation
) -> None:
    slot = attestation.data.slot
    beacon_block_root = attestation.data.beacon_block_root
    payload_present = attestation.data.index == 1
    non_equivocating_attesting_indices = [
        index for index in attesting_indices if index not in store.equivocating_indices
    ]
    for i in non_equivocating_attesting_indices:
        if i not in store.latest_messages or slot > store.latest_messages[i].slot:
            # [Modified in Gloas:EIP7732]
            store.latest_messages[i] = LatestMessage(
                slot=slot,
                root=beacon_block_root,
                payload_present=payload_present,
            )


def record_block_timeliness(store: Store, root: Root) -> None:
    block = store.blocks[root]
    time_into_slot_ms = get_time_into_slot_ms(store)
    attestation_threshold_ms = get_attestation_due_ms()
    # [New in Gloas:EIP7732]
    is_current_slot = get_current_slot(store) == block.slot
    ptc_threshold_ms = get_payload_attestation_due_ms()
    # [Modified in Gloas:EIP7732]
    store.block_timeliness[root] = [
        is_current_slot and time_into_slot_ms < threshold
        for threshold in [attestation_threshold_ms, ptc_threshold_ms]
    ]


def compute_shuffling_lookahead_start_slot(epoch: Epoch) -> Slot:
    lookahead_epoch = saturating_sub(epoch, MIN_SEED_LOOKAHEAD)
    return compute_start_slot_at_epoch(lookahead_epoch)


def compute_shuffling_dependent_slot(epoch: Epoch) -> Slot:
    lookahead_start_slot = compute_shuffling_lookahead_start_slot(epoch)
    return saturating_sub(lookahead_start_slot, 1)


def get_shuffling_dependent_root(store: Store, root: Root, epoch: Epoch) -> Root:
    # [Modified in Gloas:EIP7732]
    node = ForkChoiceNode(
        root=root,
        payload_status=PAYLOAD_STATUS_PENDING,
    )
    dependent_slot = compute_shuffling_dependent_slot(epoch)
    return get_ancestor(store, node, dependent_slot).root


def update_proposer_boost_root(store: Store, head: Root, root: Root) -> None:
    is_first_block = store.proposer_boost_root == Root()
    # [Modified in Gloas:EIP7732]
    is_timely = store.block_timeliness[root][ATTESTATION_TIMELINESS_INDEX]
    epoch = get_current_store_epoch(store)
    head_dependent_root = get_shuffling_dependent_root(store, head, epoch)
    block_dependent_root = get_shuffling_dependent_root(store, root, epoch)
    is_same_dependent_root = head_dependent_root == block_dependent_root

    # Add proposer score boost if the block is timely, not conflicting with an
    # existing block, with the same dependent root as the canonical chain head.
    if is_timely and is_first_block and is_same_dependent_root:
        store.proposer_boost_root = root


def on_tick(store: Store, time_ms: Uint64) -> None:
    # If the ``store.time_ms`` falls behind, while loop catches up slot by slot
    # to ensure that every previous slot is processed with ``on_tick_per_slot``
    tick_slot = compute_slot_at_time_ms(store.genesis_time_ms, time_ms)
    while get_current_slot(store) < tick_slot:
        next_slot = get_current_slot(store) + 1
        next_slot_time_ms = compute_time_at_slot_ms(store.genesis_time_ms, next_slot)
        on_tick_per_slot(store, next_slot_time_ms)
    on_tick_per_slot(store, time_ms)


def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    block_root = hash_tree_root(block)

    # Return early if the block is already known
    if block_root in store.blocks:
        return

    # Parent block must be known
    assert block.parent_root in store.block_states

    # If this block builds on the parent's full payload, that payload must
    # have been verified by on_execution_payload_envelope
    if is_parent_node_full(store, block):
        assert is_payload_verified(store, block.parent_root)

    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    current_slot = get_current_slot(store)
    assert current_slot >= block.slot

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

    # Make a copy of the state to avoid mutability issues
    state = store.block_states[block.parent_root].copy()

    # Check the block is valid and compute the post-state
    state_transition(state, signed_block, validate_result=True)

    # Compute head before applying the block
    head = get_head(store)
    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state
    # Add a new PTC voting for this block to the store
    store.payload_timeliness_vote[block_root] = [None] * PTC_SIZE
    store.payload_data_availability_vote[block_root] = [None] * PTC_SIZE

    # Notify the store about the payload_attestations in the block
    notify_ptc_messages(store, state, block.body.payload_attestations)

    record_block_timeliness(store, block_root)
    update_proposer_boost_root(store, head.root, block_root)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)


def on_attestation(store: Store, attestation: Attestation, is_from_block: bool = False) -> None:
    """
    Run ``on_attestation`` upon receiving a new attestation from either within a block or directly on the wire.

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
    Run ``on_attester_slashing`` immediately upon receiving a new attester slashing
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
    if epoch >= config.PREREG_FORK_EPOCH:
        return config.PREREG_FORK_VERSION
    if epoch >= config.GLOAS_FORK_EPOCH:
        return config.GLOAS_FORK_VERSION
    if epoch >= config.FULU_FORK_EPOCH:
        return config.FULU_FORK_VERSION
    if epoch >= config.ELECTRA_FORK_EPOCH:
        return config.ELECTRA_FORK_VERSION
    if epoch >= config.DENEB_FORK_EPOCH:
        return config.DENEB_FORK_VERSION
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

    # [New in Fulu:EIP7892]
    if epoch < config.FULU_FORK_EPOCH:
        return ForkDigest(base_digest[:4])

    # [Modified in Fulu:EIP7892]
    # Bitmask digest with hash of blob parameters
    blob_parameters = get_blob_parameters(epoch)
    return ForkDigest(
        xor(
            base_digest,
            sha256(
                uint_to_bytes(Uint64(blob_parameters.epoch))
                + uint_to_bytes(Uint64(blob_parameters.max_blobs_per_block))
            ),
        )[:4]
    )


def is_future_slot(
    store: Store,
    slot: Slot,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the given slot is in the future
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    slot_time_ms = compute_time_at_slot_ms(store.genesis_time_ms, slot)
    return current_time_ms + config.MAXIMUM_GOSSIP_CLOCK_DISPARITY < slot_time_ms


def is_future_epoch(
    store: Store,
    epoch: Epoch,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the given epoch is in the future
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    current_time_with_disparity_ms = current_time_ms + config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    current_slot = compute_slot_at_time_ms(store.genesis_time_ms, current_time_with_disparity_ms)
    return compute_epoch_at_slot(current_slot) < epoch


def is_within_slot_range(
    store: Store,
    slot: Slot,
    slot_range: Uint64,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the current time is within the inclusive slot range ``[slot, slot + slot_range]``
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance on both ends).
    """
    start_time_ms = compute_time_at_slot_ms(store.genesis_time_ms, slot)
    if current_time_ms + config.MAXIMUM_GOSSIP_CLOCK_DISPARITY < start_time_ms:
        return False
    end_time_ms = compute_time_at_slot_ms(store.genesis_time_ms, slot + slot_range + 1)
    if end_time_ms + config.MAXIMUM_GOSSIP_CLOCK_DISPARITY < current_time_ms:
        return False
    return True


def compute_attestation_subnet_prefix_bits() -> Uint64:
    """
    Return the number of NodeId bits to use when mapping to a subscribed subnet.
    """
    return ceillog2(config.ATTESTATION_SUBNET_COUNT) + config.ATTESTATION_SUBNET_EXTRA_BITS


def compute_min_epochs_for_block_requests() -> Epoch:
    """
    Return the minimum epoch range over which a node must serve blocks.
    """
    # [Modified in Gloas:EIP8061]
    numerator = 3 * config.CHURN_LIMIT_QUOTIENT_GLOAS * config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    denominator = (
        2 * config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT + 3 * config.CHURN_LIMIT_QUOTIENT_GLOAS
    )
    return config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY + (numerator // denominator) // 2


def is_non_strict_superset(
    seen_bits_set: set[tuple[bool, ...]],
    new_bits: tuple[bool, ...],
) -> bool:
    """
    Return True if any prior bitset in ``seen_bits_set`` is a non-strict
    superset of ``new_bits`` (every bit set in new is also set in that prior).
    """
    for prior_bits in seen_bits_set:
        is_superset = True
        for prior_bit, new_bit in zip(prior_bits, new_bits, strict=True):
            if new_bit and not prior_bit:
                is_superset = False
                break
        if is_superset:
            return True
    return False


def max_compressed_len(n: Uint64) -> Uint64:
    # Worst-case compressed length for a given payload of size n when using snappy:
    # https://github.com/google/snappy/blob/32ded457c0b1fe78ceb8397632c416568d6714a0/snappy.cc#L218C1-L218C47
    return 32 + n + n // 6


def max_message_size() -> Uint64:
    # Allow 1024 bytes for framing and encoding overhead but at least 1MiB in case config.MAX_PAYLOAD_SIZE is small.
    return max(max_compressed_len(config.MAX_PAYLOAD_SIZE) + 1024, Uint64(1024 * 1024))


def validate_beacon_block_gossip(
    seen: Seen,
    store: Store,
    signed_beacon_block: SignedBeaconBlock,
    current_time_ms: Uint64,
    # [Modified in Gloas:EIP7732]
    # Removed `block_payload_statuses`
) -> None:
    """
    Validate a SignedBeaconBlock for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block = signed_beacon_block.message
    bid = block.body.signed_execution_payload_bid.message

    # [IGNORE] The block is the first block with valid signature received for the slot and proposer
    proposer_slot_key = (block.slot, block.proposer_index)
    if proposer_slot_key in seen.proposer_slots:
        raise GossipIgnore("block is not the first valid block for this slot and proposer")

    # [IGNORE] The block is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if is_future_slot(store, block.slot, current_time_ms):
        raise GossipIgnore("block is from a future slot")

    # [IGNORE] The block is from a slot greater than the latest finalized slot
    # (MAY choose to validate and store such blocks for additional purposes
    # -- e.g. slashing detection, archive nodes, etc)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if block.slot <= finalized_slot:
        raise GossipIgnore("block is not from a slot greater than the latest finalized slot")

    # [New in Gloas:EIP7688]
    # [REJECT] The block body operation counts are within their limits
    verify_block_body_operation_limits(block.body)

    # [New in Gloas:EIP7688]
    # [REJECT] The parent execution request counts are within their limits
    verify_execution_requests_limits(block.body.parent_execution_requests)

    # [IGNORE] The block's parent has been seen (via gossip or non-gossip sources)
    # (MAY be queued until parent is retrieved)
    if block.parent_root not in store.blocks:
        raise GossipIgnore("block's parent has not been seen")

    # [REJECT] The block's parent passes validation
    if block.parent_root not in store.block_states:
        raise GossipReject("block's parent is invalid")

    state = store.block_states[get_head(store).root]

    # [REJECT] The proposer index is a valid validator index
    if block.proposer_index >= len(state.validators):
        raise GossipReject("proposer index out of range")

    # [REJECT] The proposer signature is valid
    proposer = state.validators[block.proposer_index]
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(block, domain)
    if not bls.Verify(proposer.pubkey, signing_root, signed_beacon_block.signature):
        raise GossipReject("invalid proposer signature")

    # [New in Gloas:EIP7732]
    # [IGNORE] If the parent block is full, the parent payload is valid
    # (MAY be queued until the parent payload is verified)
    if is_parent_node_full(store, block):
        if not is_payload_verified(store, block.parent_root):
            raise GossipIgnore("parent payload is not verified")

    # [REJECT] The block is from a higher slot than its parent
    if block.slot <= store.blocks[block.parent_root].slot:
        raise GossipReject("block is not from a higher slot than its parent")

    # [REJECT] The current finalized checkpoint is an ancestor of the block
    finalized_epoch = store.finalized_checkpoint.epoch
    finalized_checkpoint_block = get_checkpoint_block(store, block.parent_root, finalized_epoch)
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipReject("finalized checkpoint is not an ancestor of block")

    # [Modified in Gloas:EIP7732]
    # [REJECT] The bid's blob KZG commitment count is within the per-epoch limit
    max_blobs = get_blob_parameters(compute_epoch_at_slot(block.slot)).max_blobs_per_block
    if len(bid.blob_kzg_commitments) > max_blobs:
        raise GossipReject("too many blob kzg commitments")

    # [Modified in Gloas:EIP7732]
    # [REJECT] The bid's parent equals the block's parent
    if bid.parent_block_root != block.parent_root:
        raise GossipReject("bid's parent does not equal block's parent")

    # [REJECT] The block is proposed by the expected proposer for the slot
    parent_state = store.block_states[block.parent_root].copy()
    process_slots(parent_state, block.slot)
    expected_proposer = get_beacon_proposer_index(parent_state)
    if block.proposer_index != expected_proposer:
        raise GossipReject("block proposer_index does not match expected proposer")

    # [New in Gloas:EIP7732]
    # [REJECT] If the parent is not full, the bid builds on the parent's execution head
    if not is_parent_node_full(store, block):
        if bid.parent_block_hash != parent_state.latest_block_hash:
            raise GossipReject("bid does not build on the parent's execution head")

    # Mark this block as seen
    seen.proposer_slots.add(proposer_slot_key)


def validate_beacon_aggregate_and_proof_gossip(
    seen: Seen,
    store: Store,
    signed_aggregate_and_proof: SignedAggregateAndProof,
    current_time_ms: Uint64,
    # [New in Gloas:EIP7732]
    block_payload_statuses: dict[Root, PayloadValidationStatus],
) -> None:
    """
    Validate a SignedAggregateAndProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    aggregate_and_proof = signed_aggregate_and_proof.message
    aggregate = aggregate_and_proof.aggregate
    aggregation_bits = aggregate.aggregation_bits

    # [New in Gloas:EIP7732]
    # [REJECT] The aggregate attestation's data index is 0 or 1
    if aggregate.data.index > 1:
        raise GossipReject("aggregate data index must be 0 or 1")

    # [REJECT] Exactly one committee is specified by the committee bits
    committee_indices = get_committee_indices(aggregate.committee_bits)
    if len(committee_indices) != 1:
        raise GossipReject("aggregate committee bits must specify exactly one committee")
    index = committee_indices[0]

    # [IGNORE] A valid aggregate with a superset of aggregation bits has not already been seen
    aggregate_data_root = hash_tree_root(aggregate.data)
    aggregate_cache_key = (aggregate_data_root, index)
    aggregate_bits = tuple(bool(bit) for bit in aggregation_bits)
    seen_bits = seen.aggregate_data_roots.get(aggregate_cache_key, set())
    if is_non_strict_superset(seen_bits, aggregate_bits):
        raise GossipIgnore("already seen aggregate for this data")

    # [IGNORE] This is the first valid aggregate for this epoch and aggregator
    aggregator_index = aggregate_and_proof.aggregator_index
    target_epoch = aggregate.data.target.epoch
    aggregator_epoch_key = (target_epoch, aggregator_index)
    if aggregator_epoch_key in seen.aggregator_epochs:
        raise GossipIgnore("already seen aggregate for this epoch and aggregator")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    block_root = aggregate.data.beacon_block_root
    if block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    state = store.block_states[get_head(store).root]

    # [REJECT] The committee index is within the expected range
    committee_count = get_committee_count_per_slot(state, aggregate.data.target.epoch)
    if index >= committee_count:
        raise GossipReject("committee index out of range")

    # [IGNORE] The aggregate attestation's slot is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if is_future_slot(store, aggregate.data.slot, current_time_ms):
        raise GossipIgnore("aggregate slot is from a future slot")

    # [IGNORE] The aggregate attestation's epoch is either the current or previous epoch
    attestation_epoch = compute_epoch_at_slot(aggregate.data.slot)
    if not is_current_or_previous_epoch(store, attestation_epoch, current_time_ms):
        raise GossipIgnore("aggregate epoch is not current or previous epoch")

    # [REJECT] The aggregate attestation's epoch matches its target
    if aggregate.data.target.epoch != compute_epoch_at_slot(aggregate.data.slot):
        raise GossipReject("attestation epoch does not match target epoch")

    # [REJECT] The number of aggregation bits matches the committee size
    committee = get_beacon_committee(state, aggregate.data.slot, index)
    if len(aggregation_bits) != len(committee):
        raise GossipReject("aggregation bits length does not match committee size")

    # [REJECT] The aggregate attestation has participants
    attesting_indices = get_attesting_indices(state, aggregate)
    if len(attesting_indices) < 1:
        raise GossipReject("aggregate has no participants")

    # [REJECT] The selection proof selects the validator as an aggregator
    if not is_aggregator(state, aggregate.data.slot, index, aggregate_and_proof.selection_proof):
        raise GossipReject("validator is not selected as aggregator")

    # [REJECT] The aggregator is a member of the committee
    if aggregator_index not in committee:
        raise GossipReject("aggregator is not a member of the committee")

    # [REJECT] The selection proof signature is valid
    aggregator = state.validators[aggregator_index]
    domain = get_domain(state, DOMAIN_SELECTION_PROOF, target_epoch)
    signing_root = compute_signing_root(aggregate.data.slot, domain)
    if not bls.Verify(aggregator.pubkey, signing_root, aggregate_and_proof.selection_proof):
        raise GossipReject("invalid selection proof signature")

    # [REJECT] The aggregator signature is valid
    domain = get_domain(state, DOMAIN_AGGREGATE_AND_PROOF, target_epoch)
    signing_root = compute_signing_root(aggregate_and_proof, domain)
    if not bls.Verify(aggregator.pubkey, signing_root, signed_aggregate_and_proof.signature):
        raise GossipReject("invalid aggregator signature")

    # [REJECT] The aggregate signature is valid
    if not is_valid_indexed_attestation(state, get_indexed_attestation(state, aggregate)):
        raise GossipReject("invalid aggregate signature")

    # [REJECT] The target block is an ancestor of the LMD vote block
    checkpoint_block = get_checkpoint_block(store, block_root, aggregate.data.target.epoch)
    if checkpoint_block != aggregate.data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The finalized checkpoint is an ancestor of the block
    finalized_epoch = store.finalized_checkpoint.epoch
    finalized_checkpoint_block = get_checkpoint_block(store, block_root, finalized_epoch)
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # [New in Gloas:EIP7732]
    # The attested payload status is consistent with the block's execution payload
    verify_attestation_payload_status(store, aggregate.data, block_payload_statuses)

    # Mark this aggregate as seen
    seen.aggregator_epochs.add(aggregator_epoch_key)
    if aggregate_cache_key not in seen.aggregate_data_roots:
        seen.aggregate_data_roots[aggregate_cache_key] = set()
    seen.aggregate_data_roots[aggregate_cache_key].add(aggregate_bits)


def validate_voluntary_exit_gossip(
    seen: Seen,
    store: Store,
    signed_voluntary_exit: SignedVoluntaryExit,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedVoluntaryExit for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    voluntary_exit = signed_voluntary_exit.message
    validator_index = voluntary_exit.validator_index

    # [IGNORE] The voluntary exit is the first valid voluntary exit received for the validator
    if validator_index in seen.voluntary_exit_indices:
        raise GossipIgnore("already seen voluntary exit for this validator")

    # [IGNORE] The voluntary exit epoch is not in the future
    if is_future_epoch(store, voluntary_exit.epoch, current_time_ms):
        raise GossipIgnore("voluntary exit epoch is in the future")

    state = store.block_states[get_head(store).root]

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    validator = state.validators[validator_index]
    current_epoch = get_current_epoch(state)

    # [IGNORE] The validator has not already initiated exit
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        raise GossipIgnore("validator has already initiated exit")

    # [REJECT] The validator is active
    if not is_active_validator(validator, current_epoch):
        raise GossipReject("validator is not active")

    # [REJECT] The validator has been active long enough
    if current_epoch < validator.activation_epoch + config.SHARD_COMMITTEE_PERIOD:
        raise GossipReject("validator has not been active long enough")

    # [New in Electra:EIP7251]
    # [IGNORE] The validator has no pending partial withdrawals
    if get_pending_balance_to_withdraw(state, validator_index) != 0:
        raise GossipIgnore("validator has pending partial withdrawals")

    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, config.CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)
    if not bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature):
        raise GossipReject("invalid voluntary exit signature")

    # Mark this voluntary exit as seen
    seen.voluntary_exit_indices.add(validator_index)


def validate_proposer_slashing_gossip(
    seen: Seen,
    store: Store,
    proposer_slashing: ProposerSlashing,
) -> None:
    """
    Validate a ProposerSlashing for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    header_1 = proposer_slashing.signed_header_1.message
    header_2 = proposer_slashing.signed_header_2.message
    proposer_index = header_1.proposer_index

    # [IGNORE] The proposer slashing is the first valid proposer slashing received for this proposer
    if proposer_index in seen.proposer_slashing_indices:
        raise GossipIgnore("already seen proposer slashing for this proposer")

    # [REJECT] The header slots match
    if header_1.slot != header_2.slot:
        raise GossipReject("header slots do not match")

    # [REJECT] The header proposer indices match
    if header_1.proposer_index != header_2.proposer_index:
        raise GossipReject("header proposer indices do not match")

    # [REJECT] The headers are different
    if header_1 == header_2:
        raise GossipReject("headers are not different")

    state = store.block_states[get_head(store).root]

    # [REJECT] The proposer index is a valid validator index
    if proposer_index >= len(state.validators):
        raise GossipReject("proposer index out of range")

    # [REJECT] The proposer is slashable
    proposer = state.validators[proposer_index]
    if not is_slashable_validator(proposer, get_current_epoch(state)):
        raise GossipReject("proposer is not slashable")

    # [REJECT] The signatures are valid
    for signed_header in (proposer_slashing.signed_header_1, proposer_slashing.signed_header_2):
        domain = get_domain(
            state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(signed_header.message.slot)
        )
        signing_root = compute_signing_root(signed_header.message, domain)
        if not bls.Verify(proposer.pubkey, signing_root, signed_header.signature):
            raise GossipReject("invalid proposer slashing signature")

    # Mark this proposer slashing as seen
    seen.proposer_slashing_indices.add(proposer_index)


def validate_attester_slashing_gossip(
    seen: Seen,
    store: Store,
    attester_slashing: AttesterSlashing,
) -> None:
    """
    Validate an AttesterSlashing for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2

    attesting_indices_1 = set(attestation_1.attesting_indices)
    attesting_indices_2 = set(attestation_2.attesting_indices)
    slashable_indices = attesting_indices_1.intersection(attesting_indices_2)

    # [IGNORE] At least one index in the intersection has not yet been seen
    new_indices = slashable_indices.difference(seen.attester_slashing_indices)
    if len(new_indices) == 0:
        raise GossipIgnore("all attester slashing indices already seen")

    # [REJECT] The attestation data is slashable (double vote or surround vote)
    if not is_slashable_attestation_data(attestation_1.data, attestation_2.data):
        raise GossipReject("attestation data is not slashable")

    state = store.block_states[get_head(store).root]

    # [REJECT] All validator indices in the first indexed attestation are valid
    if any(index >= len(state.validators) for index in attestation_1.attesting_indices):
        raise GossipReject("validator index out of range in indexed attestation 1")

    # [REJECT] The first indexed attestation has valid properties
    if not is_valid_indexed_attestation(state, attestation_1):
        raise GossipReject("invalid indexed attestation 1")

    # [REJECT] All validator indices in the second indexed attestation are valid
    if any(index >= len(state.validators) for index in attestation_2.attesting_indices):
        raise GossipReject("validator index out of range in indexed attestation 2")

    # [REJECT] The second indexed attestation has valid properties
    if not is_valid_indexed_attestation(state, attestation_2):
        raise GossipReject("invalid indexed attestation 2")

    # [REJECT] At least one validator in the intersection is slashable
    slashable_any = False
    current_epoch = get_current_epoch(state)
    for index in slashable_indices:
        if is_slashable_validator(state.validators[index], current_epoch):
            slashable_any = True
            break
    if not slashable_any:
        raise GossipReject("no slashable validators in intersection")

    # Mark these indices as seen
    seen.attester_slashing_indices.update(slashable_indices)


def validate_beacon_attestation_gossip(
    seen: Seen,
    store: Store,
    attestation: SingleAttestation,
    current_time_ms: Uint64,
    subnet_id: SubnetID,
    # [New in Gloas:EIP7732]
    block_payload_statuses: dict[Root, PayloadValidationStatus],
) -> None:
    """
    Validate a SingleAttestation for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = attestation.data
    committee_index = attestation.committee_index
    attester_index = attestation.attester_index
    target_epoch = data.target.epoch

    # [IGNORE] No other valid attestation seen for this target epoch and validator
    attestation_epoch_key = (target_epoch, attester_index)
    if attestation_epoch_key in seen.attestation_validator_epochs:
        raise GossipIgnore("already seen attestation for this epoch and validator")

    # [New in Gloas:EIP7732]
    # [REJECT] The attestation's data index is 0 or 1
    if data.index > 1:
        raise GossipReject("attestation data index must be 0 or 1")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    block_root = data.beacon_block_root
    if block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    state = store.block_states[get_head(store).root]

    # [REJECT] The committee index is within the expected range
    committees_per_slot = get_committee_count_per_slot(state, target_epoch)
    if committee_index >= committees_per_slot:
        raise GossipReject("committee index out of range")

    # [REJECT] The attestation is for the correct subnet
    expected_subnet = compute_subnet_for_attestation(
        committees_per_slot, data.slot, committee_index
    )
    if expected_subnet != subnet_id:
        raise GossipReject("attestation is for wrong subnet")

    # [IGNORE] The attestation's slot is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if is_future_slot(store, data.slot, current_time_ms):
        raise GossipIgnore("attestation slot is from a future slot")

    # [IGNORE] The attestation's epoch is either the current or previous epoch
    attestation_epoch = compute_epoch_at_slot(data.slot)
    if not is_current_or_previous_epoch(store, attestation_epoch, current_time_ms):
        raise GossipIgnore("attestation epoch is not current or previous epoch")

    # [REJECT] The attestation's epoch matches its target
    if target_epoch != compute_epoch_at_slot(data.slot):
        raise GossipReject("attestation epoch does not match target epoch")

    # [REJECT] The attester is a member of the committee
    committee = get_beacon_committee(state, data.slot, committee_index)
    if attester_index not in committee:
        raise GossipReject("attester is not a member of the committee")

    # [REJECT] The attestation signature is valid
    attester = state.validators[attester_index]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, target_epoch)
    signing_root = compute_signing_root(data, domain)
    if not bls.Verify(attester.pubkey, signing_root, attestation.signature):
        raise GossipReject("invalid attestation signature")

    # [REJECT] The attestation's target block is an ancestor of the LMD vote block
    target_checkpoint_block = get_checkpoint_block(store, block_root, target_epoch)
    if target_checkpoint_block != data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The current finalized checkpoint is an ancestor of the block
    finalized_epoch = store.finalized_checkpoint.epoch
    finalized_checkpoint_block = get_checkpoint_block(store, block_root, finalized_epoch)
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # [New in Gloas:EIP7732]
    # The attested payload status is consistent with the block's execution payload
    verify_attestation_payload_status(store, data, block_payload_statuses)

    # Mark this attestation as seen
    seen.attestation_validator_epochs.add(attestation_epoch_key)


def compute_subscribed_subnet(node_id: NodeID, epoch: Epoch, index: int) -> SubnetID:
    prefix_bits = int(compute_attestation_subnet_prefix_bits())
    node_id_prefix = node_id >> int(NODE_ID_BITS - prefix_bits)
    node_offset = Uint64(node_id % Uint256(config.EPOCHS_PER_SUBNET_SUBSCRIPTION))
    permutation_seed = sha256(
        uint_to_bytes(Uint64((epoch + node_offset) // config.EPOCHS_PER_SUBNET_SUBSCRIPTION))
    )
    permutated_prefix = compute_shuffled_index(
        Uint64(node_id_prefix),
        Uint64(1 << prefix_bits),
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
    next_epoch = get_current_epoch(state) + 1
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


def voting_period_start_time(state: BeaconState) -> Uint64:
    eth1_voting_period_start_slot = state.slot - state.slot % (
        Uint64(EPOCHS_PER_ETH1_VOTING_PERIOD) * SLOTS_PER_EPOCH
    )
    return compute_time_at_slot(state.genesis_time, eth1_voting_period_start_slot)


def is_candidate_block(block: Eth1Block, period_start: Uint64) -> bool:
    return (
        block.timestamp + config.SECONDS_PER_ETH1_BLOCK * config.ETH1_FOLLOW_DISTANCE
        <= period_start
        and block.timestamp + config.SECONDS_PER_ETH1_BLOCK * config.ETH1_FOLLOW_DISTANCE * 2
        >= period_start
    )


def compute_new_state_root(state: BeaconState, block: BeaconBlock) -> Root:
    temp_state: BeaconState = state.copy()
    signed_block = SignedBeaconBlock(message=block, signature=BLSSignature())
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
    committees_per_slot: Uint64, slot: Slot, committee_index: CommitteeIndex
) -> SubnetID:
    """
    Compute the correct subnet for an attestation for Phase 0.
    Note, this mimics expected future behavior where attestations will be mapped to their shard subnet.
    """
    slots_since_epoch_start = Uint64(slot % SLOTS_PER_EPOCH)
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
    return bytes_to_uint64(sha256(slot_signature)[0:8]) % modulo == 0


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


def compute_weak_subjectivity_period(state: BeaconState) -> Epoch:
    """
    Returns the weak subjectivity period for the current ``state``.
    This computation takes into account the effect of:
        - exit churn (weighted 2/3)
        - activation churn (weighted 1/3)
        - consolidation churn (weighted 1)
    """
    t = get_total_active_balance(state)
    # [Modified in Gloas:EIP8061]
    delta = (
        2 * get_exit_churn_limit(state) // 3
        + get_activation_churn_limit(state) // 3
        + get_consolidation_churn_limit(state)
    )
    epochs_for_validator_set_churn = Epoch(SAFETY_DECAY * t // (2 * delta * 100))
    return config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY + epochs_for_validator_set_churn


def is_within_weak_subjectivity_period(
    store: Store, ws_state: BeaconState, ws_checkpoint: Checkpoint
) -> bool:
    # Clients may choose to validate the input state against the input Weak Subjectivity Checkpoint
    assert get_block_root(ws_state, ws_checkpoint.epoch) == ws_checkpoint.root
    assert compute_epoch_at_slot(ws_state.slot) == ws_checkpoint.epoch

    # [Modified in Electra]
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


def set_or_append_list(
    list: List | ProgressiveList,
    index: Uint64,
    value: SSZObject,
) -> None:
    if index == len(list):
        list.append(value)
    else:
        list[index] = value


def get_next_sync_committee_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    """
    Return the sync committee indices, with possible duplicates, for the next sync committee.
    """
    epoch = get_current_epoch(state) + 1
    seed = get_seed(state, epoch, DOMAIN_SYNC_COMMITTEE)
    indices = get_active_validator_indices(state, epoch)
    return compute_balance_weighted_selection(
        state, indices, seed, size=SYNC_COMMITTEE_SIZE, shuffle_indices=True
    )


def get_next_sync_committee(state: BeaconState) -> SyncCommittee:
    """
    Return the next sync committee, with possible pubkey duplicates.
    """
    indices = get_next_sync_committee_indices(state)
    pubkeys = SyncCommitteePubkeys(data=[state.validators[index].pubkey for index in indices])
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
        index
        for index in active_validator_indices
        if has_flag(epoch_participation[index], flag_index)
    ]
    return set(filter(lambda index: not state.validators[index].slashed, participating_indices))


def get_attestation_participation_flag_indices(
    state: BeaconState,
    data: AttestationData,
    inclusion_delay: Uint64,
    # [New in Gloas:EIP7732]
    parent_slot: Slot,
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

    # [New in Gloas:EIP7732]
    if is_attestation_same_slot(state, data):
        assert data.index == 0
        payload_matches = True
    else:
        slot_index = parent_slot % SLOTS_PER_HISTORICAL_ROOT
        payload_index = state.execution_payload_availability[slot_index]
        payload_matches = Uint64(data.index) == Uint64(payload_index)

    # Matching head
    head_root = get_block_root_at_slot(state, data.slot)
    head_root_matches = data.beacon_block_root == head_root
    # [Modified in Gloas:EIP7732]
    is_matching_head = is_matching_target and head_root_matches and payload_matches

    assert is_matching_source

    participation_flag_indices = []
    if is_matching_source and inclusion_delay <= integer_squareroot(SLOTS_PER_EPOCH):
        participation_flag_indices.append(TIMELY_SOURCE_FLAG_INDEX)
    if is_matching_target:
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
                rewards[index] += reward_numerator // (active_increments * WEIGHT_DENOMINATOR)
        elif flag_index != TIMELY_HEAD_FLAG_INDEX:
            penalties[index] += base_reward * weight // WEIGHT_DENOMINATOR
    return rewards, penalties


def process_sync_aggregate(state: BeaconState, sync_aggregate: SyncAggregate) -> None:
    # Verify sync committee aggregate signature signing over the previous slot block root
    committee_pubkeys = state.current_sync_committee.pubkeys
    committee_bits = sync_aggregate.sync_committee_bits
    if get_set_bit_count(committee_bits) == SYNC_COMMITTEE_SIZE:
        # All members participated - use precomputed aggregate key
        participant_pubkeys = [state.current_sync_committee.aggregate_pubkey]
    elif get_set_bit_count(committee_bits) > SYNC_COMMITTEE_SIZE // 2:
        # More than half participated - subtract non-participant keys.
        # First determine nonparticipating members
        non_participant_pubkeys = [
            pubkey for pubkey, bit in zip(committee_pubkeys, committee_bits, strict=True) if not bit
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
            for pubkey, bit in zip(
                committee_pubkeys, sync_aggregate.sync_committee_bits, strict=True
            )
            if bit
        ]
    previous_slot = saturating_sub(state.slot, 1)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(previous_slot))
    signing_root = compute_signing_root(get_block_root_at_slot(state, previous_slot), domain)
    # Note: eth_fast_aggregate_verify works with a singleton list containing an aggregated key
    assert eth_fast_aggregate_verify(
        participant_pubkeys, signing_root, sync_aggregate.sync_committee_signature
    )

    # Compute participant and proposer rewards
    total_active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    total_base_rewards = get_base_reward_per_increment(state) * total_active_increments
    max_participant_rewards = (
        total_base_rewards * SYNC_REWARD_WEIGHT // WEIGHT_DENOMINATOR // Uint64(SLOTS_PER_EPOCH)
    )
    participant_reward = max_participant_rewards // SYNC_COMMITTEE_SIZE
    proposer_reward = participant_reward * PROPOSER_WEIGHT // (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT)

    # Apply participant and proposer rewards
    all_pubkeys = [validator.pubkey for validator in state.validators]
    committee_indices = [
        ValidatorIndex(all_pubkeys.index(pubkey)) for pubkey in state.current_sync_committee.pubkeys
    ]
    for participant_index, participation_bit in zip(
        committee_indices, sync_aggregate.sync_committee_bits, strict=True
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
            state.inactivity_scores[index] = saturating_sub(state.inactivity_scores[index], 1)
        else:
            state.inactivity_scores[index] += config.INACTIVITY_SCORE_BIAS
        # Decrease the inactivity score of all eligible validators during a leak-free epoch
        if not is_in_inactivity_leak(state):
            state.inactivity_scores[index] = saturating_sub(
                state.inactivity_scores[index], config.INACTIVITY_SCORE_RECOVERY_RATE
            )


def process_participation_flag_updates(state: BeaconState) -> None:
    state.previous_epoch_participation = state.current_epoch_participation
    state.current_epoch_participation = EpochParticipation(
        data=[ParticipationFlags(0b0000_0000) for _ in range(len(state.validators))]
    )


def process_sync_committee_updates(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
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


def get_sync_message_due_ms() -> Uint64:
    # [Modified in Gloas]
    return get_slot_component_duration_ms(config.SYNC_MESSAGE_DUE_BPS_GLOAS)


def get_contribution_due_ms() -> Uint64:
    # [Modified in Gloas]
    return get_slot_component_duration_ms(config.CONTRIBUTION_DUE_BPS_GLOAS)


def is_current_slot(
    store: Store,
    slot: Slot,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the given slot is the current slot
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    return is_within_slot_range(store, slot, Uint64(0), current_time_ms)


def get_sync_subcommittee_pubkeys(
    state: BeaconState, subcommittee_index: Uint64
) -> Sequence[BLSPubkey]:
    # Committees assigned to `slot` sign for `slot - 1`
    # This creates the exceptional logic below when transitioning between sync committee periods
    next_slot_epoch = compute_epoch_at_slot(state.slot + 1)
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


def validate_sync_committee_contribution_and_proof_gossip(
    seen: Seen,
    store: Store,
    signed_contribution_and_proof: SignedContributionAndProof,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedContributionAndProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    contribution_and_proof = signed_contribution_and_proof.message
    contribution = contribution_and_proof.contribution

    # [IGNORE] A valid sync committee contribution with equal slot, beacon_block_root
    # and subcommittee_index whose aggregation_bits is non-strict superset
    # has not already been seen
    contribution_key = (
        contribution.slot,
        contribution.beacon_block_root,
        contribution.subcommittee_index,
    )
    contribution_bits = tuple(bool(bit) for bit in contribution.aggregation_bits)
    seen_bits = seen.sync_contribution_data.get(contribution_key, set())
    if is_non_strict_superset(seen_bits, contribution_bits):
        raise GossipIgnore("already seen contribution for this data")

    # [IGNORE] The sync committee contribution is the first valid contribution received
    # for the slot contribution.slot, aggregator with index contribution_and_proof.aggregator_index,
    # and subcommittee index contribution.subcommittee_index
    aggregator_key = (
        contribution.slot,
        contribution_and_proof.aggregator_index,
        contribution.subcommittee_index,
    )
    if aggregator_key in seen.sync_contribution_aggregator_slots:
        raise GossipIgnore("already seen contribution from this aggregator")

    # [IGNORE] The contribution's slot is for the current slot
    if not is_current_slot(store, contribution.slot, current_time_ms):
        raise GossipIgnore("contribution is not for the current slot")

    # [REJECT] The subcommittee index is in the allowed range
    if contribution.subcommittee_index >= SYNC_COMMITTEE_SUBNET_COUNT:
        raise GossipReject("subcommittee index out of range")

    # [REJECT] The contribution has participants
    if not any(contribution.aggregation_bits):
        raise GossipReject("contribution has no participants")

    # [REJECT] The selection_proof selects the validator as an aggregator for the slot
    if not is_sync_committee_aggregator(contribution_and_proof.selection_proof):
        raise GossipReject("validator is not selected as aggregator")

    state = store.block_states[get_head(store).root]

    # [REJECT] The aggregator index is valid
    if contribution_and_proof.aggregator_index >= len(state.validators):
        raise GossipReject("aggregator index out of range")

    # [REJECT] The aggregator is a member of the committee
    aggregator_pubkey = state.validators[contribution_and_proof.aggregator_index].pubkey
    subcommittee_pubkeys = get_sync_subcommittee_pubkeys(state, contribution.subcommittee_index)
    if aggregator_pubkey not in subcommittee_pubkeys:
        raise GossipReject("aggregator is not a member of the committee")

    # [REJECT] The contribution_and_proof.selection_proof is a valid signature
    # of the SyncAggregatorSelectionData derived from the contribution
    # by the validator with index contribution_and_proof.aggregator_index
    selection_data = SyncAggregatorSelectionData(
        slot=contribution.slot,
        subcommittee_index=contribution.subcommittee_index,
    )
    domain = get_domain(
        state, DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF, compute_epoch_at_slot(contribution.slot)
    )
    signing_root = compute_signing_root(selection_data, domain)
    if not bls.Verify(aggregator_pubkey, signing_root, contribution_and_proof.selection_proof):
        raise GossipReject("invalid selection proof signature")

    # [REJECT] The aggregator signature, signed_contribution_and_proof.signature, is valid
    domain = get_domain(
        state, DOMAIN_CONTRIBUTION_AND_PROOF, compute_epoch_at_slot(contribution.slot)
    )
    signing_root = compute_signing_root(contribution_and_proof, domain)
    if not bls.Verify(aggregator_pubkey, signing_root, signed_contribution_and_proof.signature):
        raise GossipReject("invalid aggregator signature")

    # [REJECT] The aggregate signature is valid for the message beacon_block_root
    # and aggregate pubkey derived from the participation info in aggregation_bits
    # for the subcommittee specified by the contribution.subcommittee_index
    participant_pubkeys = [
        subcommittee_pubkeys[index]
        for index, bit in enumerate(contribution.aggregation_bits)
        if bit
    ]
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(contribution.slot))
    signing_root = compute_signing_root(contribution.beacon_block_root, domain)
    if not eth_fast_aggregate_verify(participant_pubkeys, signing_root, contribution.signature):
        raise GossipReject("invalid aggregate signature")

    # Mark this contribution as seen
    seen.sync_contribution_aggregator_slots.add(aggregator_key)
    if contribution_key not in seen.sync_contribution_data:
        seen.sync_contribution_data[contribution_key] = set()
    seen.sync_contribution_data[contribution_key].add(contribution_bits)


def validate_sync_committee_message_gossip(
    seen: Seen,
    store: Store,
    sync_committee_message: SyncCommitteeMessage,
    current_time_ms: Uint64,
    subnet_id: SubnetID,
) -> None:
    """
    Validate a SyncCommitteeMessage for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    # [IGNORE] There has been no other valid sync committee message for the declared slot
    # for the validator referenced by sync_committee_message.validator_index
    # (this validation is per topic so that for a given slot, multiple messages could be
    # forwarded with the same validator_index as long as the subnet_ids are distinct)
    message_key = (sync_committee_message.slot, sync_committee_message.validator_index, subnet_id)
    if message_key in seen.sync_message_validator_slots:
        raise GossipIgnore("already seen message from this validator for this slot and subnet")

    # [IGNORE] The message's slot is for the current slot
    if not is_current_slot(store, sync_committee_message.slot, current_time_ms):
        raise GossipIgnore("message is not for the current slot")

    state = store.block_states[get_head(store).root]

    # [REJECT] The validator index is valid
    if sync_committee_message.validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [REJECT] The subnet_id is valid for the given validator
    # (this implies the validator is part of the broader current sync committee
    # along with the correct subcommittee)
    valid_subnets = compute_subnets_for_sync_committee(
        state, sync_committee_message.validator_index
    )
    if subnet_id not in valid_subnets:
        raise GossipReject("subnet_id is not valid for the validator")

    # [REJECT] The signature is valid
    validator = state.validators[sync_committee_message.validator_index]
    domain = get_domain(
        state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(sync_committee_message.slot)
    )
    signing_root = compute_signing_root(sync_committee_message.beacon_block_root, domain)
    if not bls.Verify(validator.pubkey, signing_root, sync_committee_message.signature):
        raise GossipReject("invalid sync committee message signature")

    # Mark this message as seen
    seen.sync_message_validator_slots.add(message_key)


def compute_sync_committee_period(epoch: Epoch) -> Uint64:
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
    sync_aggregate = SyncAggregate.empty()
    signatures = []
    sync_subcommittee_size = SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT

    for contribution in contributions:
        subcommittee_index = contribution.subcommittee_index
        for index, participated in enumerate(contribution.aggregation_bits):
            if participated:
                participant_index = sync_subcommittee_size * subcommittee_index + index
                sync_aggregate.sync_committee_bits[participant_index] = Boolean(True)
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
    next_slot_epoch = compute_epoch_at_slot(state.slot + 1)
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
    return {
        SubnetID(index // (SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT))
        for index in sync_committee_indices
    }


def get_sync_committee_selection_proof(
    state: BeaconState, slot: Slot, subcommittee_index: Uint64, privkey: int
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
    return bytes_to_uint64(sha256(signature)[0:8]) % modulo == 0


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
    return LightClientHeader(
        beacon=BeaconBlockHeader(
            slot=block.message.slot,
            proposer_index=block.message.proposer_index,
            parent_root=block.message.parent_root,
            state_root=block.message.state_root,
            body_root=hash_tree_root(block.message.body),
        ),
        # [Modified in Gloas:EIP7732]
        execution_block_hash=(
            block.message.body.signed_execution_payload_bid.message.parent_block_hash
        ),
        # [Modified in Gloas:EIP7732]
        execution_branch=ExecutionBranch(
            data=compute_merkle_proof(block.message.body, EXECUTION_BLOCK_HASH_GINDEX_GLOAS)
        ),
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
            data=compute_merkle_proof(state, current_sync_committee_gindex_at_slot(state.slot))
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
        get_set_bit_count(block.message.body.sync_aggregate.sync_committee_bits)
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

    update = LightClientUpdate.empty()

    update.attested_header = block_to_light_client_header(attested_block)

    # `next_sync_committee` is only useful if the message is signed by the current sync committee
    if update_attested_period == update_signature_period:
        update.next_sync_committee = attested_state.next_sync_committee
        update.next_sync_committee_branch = NextSyncCommitteeBranch(
            data=compute_merkle_proof(
                attested_state,
                next_sync_committee_gindex_at_slot(attested_state.slot),
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
            data=compute_merkle_proof(
                attested_state,
                finalized_root_gindex_at_slot(attested_state.slot),
            )
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


def finalized_root_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Gloas:EIP7688]
    if epoch >= config.GLOAS_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_GLOAS
    if epoch >= config.ELECTRA_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_ELECTRA
    return FINALIZED_ROOT_GINDEX


def current_sync_committee_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Gloas:EIP7688]
    if epoch >= config.GLOAS_FORK_EPOCH:
        return CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS
    if epoch >= config.ELECTRA_FORK_EPOCH:
        return CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return CURRENT_SYNC_COMMITTEE_GINDEX


def next_sync_committee_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Gloas:EIP7688]
    if epoch >= config.GLOAS_FORK_EPOCH:
        return NEXT_SYNC_COMMITTEE_GINDEX_GLOAS
    if epoch >= config.ELECTRA_FORK_EPOCH:
        return NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return NEXT_SYNC_COMMITTEE_GINDEX


def is_valid_light_client_header(header: LightClientHeader) -> bool:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    # [New in Gloas:EIP7732]
    if epoch >= config.GLOAS_FORK_EPOCH:
        return is_valid_normalized_merkle_branch(
            leaf=Bytes32(header.execution_block_hash),
            branch=header.execution_branch,
            gindex=EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
            root=header.beacon.body_root,
        )

    # [Modified in Gloas:EIP7732]
    if epoch >= config.DENEB_FORK_EPOCH:
        return is_valid_normalized_merkle_branch(
            leaf=Bytes32(header.execution_block_hash),
            branch=header.execution_branch,
            gindex=EXECUTION_BLOCK_HASH_GINDEX_DENEB,
            root=header.beacon.body_root,
        )

    # [Modified in Gloas:EIP7732]
    if epoch >= config.CAPELLA_FORK_EPOCH:
        return is_valid_normalized_merkle_branch(
            leaf=Bytes32(header.execution_block_hash),
            branch=header.execution_branch,
            gindex=EXECUTION_BLOCK_HASH_GINDEX,
            root=header.beacon.body_root,
        )

    # [Modified in Gloas:EIP7732]
    return header.execution_block_hash == Hash32() and header.execution_branch == ExecutionBranch()


def is_sync_committee_update(update: LightClientUpdate) -> bool:
    return update.next_sync_committee_branch != NextSyncCommitteeBranch()


def is_finality_update(update: LightClientUpdate) -> bool:
    return update.finality_branch != FinalityBranch()


def is_better_update(new_update: LightClientUpdate, old_update: LightClientUpdate) -> bool:
    # Compare supermajority (> 2/3) sync committee participation
    max_active_participants = len(new_update.sync_aggregate.sync_committee_bits)
    new_num_active_participants = get_set_bit_count(new_update.sync_aggregate.sync_committee_bits)
    old_num_active_participants = get_set_bit_count(old_update.sync_aggregate.sync_committee_bits)
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
    return store.next_sync_committee != SyncCommittee.empty()


def get_safety_threshold(store: LightClientStore) -> Uint64:
    return (
        max(
            store.previous_max_active_participants,
            store.current_max_active_participants,
        )
        // 2
    )


def get_subtree_index(generalized_index: GeneralizedIndex) -> Uint64:
    return Uint64(generalized_index % 2 ** (floorlog2(generalized_index)))


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


def compute_sync_committee_period_at_slot(slot: Slot) -> Uint64:
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
        next_sync_committee=SyncCommittee.empty(),
        best_valid_update=None,
        optimistic_header=bootstrap.header,
        previous_max_active_participants=Uint64(0),
        current_max_active_participants=Uint64(0),
    )


def validate_light_client_update(
    store: LightClientStore,
    update: LightClientUpdate,
    current_slot: Slot,
    genesis_validators_root: Root,
) -> None:
    # Verify sync committee has sufficient participants
    sync_aggregate = update.sync_aggregate
    assert get_set_bit_count(sync_aggregate.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

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
        assert update.finalized_header == LightClientHeader.empty()
    else:
        if update_finalized_slot == GENESIS_SLOT:
            assert update.finalized_header == LightClientHeader.empty()
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
        assert update.next_sync_committee == SyncCommittee.empty()
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
        for (bit, pubkey) in zip(
            sync_aggregate.sync_committee_bits, sync_committee.pubkeys, strict=True
        )
        if bit
    ]
    fork_version_slot = saturating_sub(update.signature_slot, 1)
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
        store.current_max_active_participants = Uint64(0)
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
        get_set_bit_count(sync_committee_bits),
    )

    # Update the optimistic header
    if (
        get_set_bit_count(sync_committee_bits) > get_safety_threshold(store)
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
    if get_set_bit_count(sync_committee_bits) * 3 >= len(sync_committee_bits) * 2 and (
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
        next_sync_committee=SyncCommittee.empty(),
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
        next_sync_committee=SyncCommittee.empty(),
        next_sync_committee_branch=NextSyncCommitteeBranch(),
        finalized_header=LightClientHeader.empty(),
        finality_branch=FinalityBranch(),
        sync_aggregate=optimistic_update.sync_aggregate,
        signature_slot=optimistic_update.signature_slot,
    )
    process_light_client_update(store, update, current_slot, genesis_validators_root)


def get_safe_execution_block_hash(fcr_store: FastConfirmationStore) -> Hash32:
    safe_block = fcr_store.store.blocks[fcr_store.confirmed_root]
    # [Modified in Gloas:EIP7732]
    return safe_block.body.signed_execution_payload_bid.message.parent_block_hash


def is_valid_terminal_pow_block(block: PowBlock, parent: PowBlock) -> bool:
    is_total_difficulty_reached = block.total_difficulty >= config.TERMINAL_TOTAL_DIFFICULTY
    is_parent_total_difficulty_valid = parent.total_difficulty < config.TERMINAL_TOTAL_DIFFICULTY
    return is_total_difficulty_reached and is_parent_total_difficulty_valid


def is_optimistic(opt_store: OptimisticStore, block: BeaconBlock) -> bool:
    return hash_tree_root(block) in opt_store.optimistic_roots


def latest_verified_ancestor(opt_store: OptimisticStore, block: BeaconBlock) -> BeaconBlock:
    # It is assumed that the `block` parameter is never an INVALIDATED block.
    while True:
        if not is_optimistic(opt_store, block) or block.parent_root == Root():
            return block
        block = opt_store.blocks[block.parent_root]


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


def prepare_execution_payload(
    # [New in Gloas:EIP7732]
    store: Store,
    # [New in Gloas:EIP7732]
    head: ForkChoiceNode,
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    # [New in Gloas]
    target_gas_limit: Uint64,
    execution_engine: ExecutionEngine,
) -> PayloadId | None:
    # [New in Gloas:EIP7732]
    parent_bid = state.latest_execution_payload_bid
    if should_build_on_full(store, head, state.slot):
        envelope = store.payloads[head.root]
        # Make a copy of the state to avoid mutability issues
        state = state.copy()
        # Apply parent payload before computing withdrawals
        apply_parent_execution_payload(state, envelope.execution_requests)
        withdrawals = get_expected_withdrawals(state).withdrawals
        head_block_hash = parent_bid.block_hash
    else:
        withdrawals = state.payload_expected_withdrawals
        head_block_hash = parent_bid.parent_block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_time_at_slot(state.genesis_time, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        # [Modified in Gloas:EIP7732]
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
        # [New in Gloas:EIP7843]
        slot_number=state.slot,
        # [New in Gloas]
        target_gas_limit=target_gas_limit,
    )
    return execution_engine.notify_forkchoice_updated(
        # [Modified in Gloas:EIP7732]
        head_block_hash=head_block_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
        # [New in Gloas:EIP8070]
        custody_columns=None,
    )


def get_execution_payload(
    payload_id: PayloadId | None, execution_engine: ExecutionEngine
) -> ExecutionPayload:
    if payload_id is None:
        # Pre-merge, empty payload
        return ExecutionPayload.empty()
    else:
        return execution_engine.get_payload(payload_id).execution_payload


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
        # [Modified in Electra:EIP7251]
        has_execution_withdrawal_credential(validator)
        and validator.withdrawable_epoch <= epoch
        and balance > 0
    )


def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    max_effective_balance = get_max_effective_balance(validator)
    # [Modified in Electra:EIP7251]
    has_max_effective_balance = validator.effective_balance == max_effective_balance
    # [Modified in Electra:EIP7251]
    has_excess_balance = balance > max_effective_balance
    return (
        # [Modified in Electra:EIP7251]
        has_execution_withdrawal_credential(validator)
        and has_max_effective_balance
        and has_excess_balance
    )


def process_historical_summaries_update(state: BeaconState) -> None:
    # Set historical block root accumulator.
    next_epoch = get_current_epoch(state) + 1
    if next_epoch % Uint64(SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_summary = HistoricalSummary(
            block_summary_root=hash_tree_root(state.block_roots),
            state_summary_root=hash_tree_root(state.state_roots),
        )
        state.historical_summaries.append(historical_summary)


def get_balance_after_withdrawals(
    state: BeaconState,
    validator_index: ValidatorIndex,
    withdrawals: Sequence[Withdrawal],
) -> Gwei:
    withdrawn = sum(
        withdrawal.amount
        for withdrawal in withdrawals
        if withdrawal.validator_index == validator_index
    )
    return state.balances[validator_index] - withdrawn


def get_validators_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    validators_limit = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD
    # There must be at least one space reserved for validator sweep withdrawals
    assert len(prior_withdrawals) < withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    validator_index = state.next_withdrawal_validator_index
    for _ in range(validators_limit):
        all_withdrawals = list(prior_withdrawals) + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        validator = state.validators[validator_index]
        balance = get_balance_after_withdrawals(state, validator_index, all_withdrawals)
        if is_fully_withdrawable_validator(validator, balance, epoch):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=balance,
                )
            )
            withdrawal_index += 1
        elif is_partially_withdrawable_validator(validator, balance):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    # [Modified in Electra:EIP7251]
                    amount=balance - get_max_effective_balance(validator),
                )
            )
            withdrawal_index += 1

        validator_index = (validator_index + 1) % len(state.validators)
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count


def get_expected_withdrawals(state: BeaconState) -> ExpectedWithdrawals:
    withdrawal_index = state.next_withdrawal_index
    withdrawals: list[Withdrawal] = []

    # [New in Gloas:EIP7732]
    # Get builder withdrawals
    builder_withdrawals, withdrawal_index, processed_builder_withdrawals_count = (
        get_builder_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(builder_withdrawals)

    # Get partial withdrawals
    partial_withdrawals, withdrawal_index, processed_partial_withdrawals_count = (
        get_pending_partial_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(partial_withdrawals)

    # [New in Gloas:EIP7732]
    # Get builders sweep withdrawals
    builders_sweep_withdrawals, withdrawal_index, processed_builders_sweep_count = (
        get_builders_sweep_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(builders_sweep_withdrawals)

    # Get validators sweep withdrawals
    validators_sweep_withdrawals, withdrawal_index, processed_validators_sweep_count = (
        get_validators_sweep_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(validators_sweep_withdrawals)

    return ExpectedWithdrawals(
        withdrawals,
        # [New in Gloas:EIP7732]
        processed_builder_withdrawals_count,
        processed_partial_withdrawals_count,
        # [New in Gloas:EIP7732]
        processed_builders_sweep_count,
        processed_validators_sweep_count,
    )


def apply_withdrawals(state: BeaconState, withdrawals: Sequence[Withdrawal]) -> None:
    for withdrawal in withdrawals:
        # [Modified in Gloas:EIP7732]
        if is_builder_index(withdrawal.validator_index):
            builder_index = convert_validator_index_to_builder_index(withdrawal.validator_index)
            state.builders[builder_index].balance = saturating_sub(
                state.builders[builder_index].balance, withdrawal.amount
            )
        else:
            decrease_balance(state, withdrawal.validator_index, withdrawal.amount)


def update_next_withdrawal_index(state: BeaconState, withdrawals: Sequence[Withdrawal]) -> None:
    # Update the next withdrawal index if this block contained withdrawals
    if len(withdrawals) != 0:
        latest_withdrawal = withdrawals[-1]
        state.next_withdrawal_index = latest_withdrawal.index + 1


def update_next_withdrawal_validator_index(
    state: BeaconState, withdrawals: Sequence[Withdrawal]
) -> None:
    # Update the next validator index to start the next withdrawal sweep
    if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = (withdrawals[-1].validator_index + 1) % len(state.validators)
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        next_validator_index = next_index % len(state.validators)
        state.next_withdrawal_validator_index = next_validator_index


def process_withdrawals(
    state: BeaconState,
    # [Modified in Gloas:EIP7732]
    # Removed `payload`
) -> None:
    # [New in Gloas:EIP7732]
    # Return early if the parent block is empty
    if state.latest_block_hash != state.latest_execution_payload_bid.block_hash:
        return

    # Get expected withdrawals
    expected = get_expected_withdrawals(state)

    # Apply expected withdrawals
    apply_withdrawals(state, expected.withdrawals)

    # Update withdrawals fields in the state
    update_next_withdrawal_index(state, expected.withdrawals)
    # [New in Gloas:EIP7732]
    update_payload_expected_withdrawals(state, expected.withdrawals)
    # [New in Gloas:EIP7732]
    update_builder_pending_withdrawals(state, expected.processed_builder_withdrawals_count)
    update_pending_partial_withdrawals(state, expected.processed_partial_withdrawals_count)
    # [New in Gloas:EIP7732]
    update_next_withdrawal_builder_index(state, expected.processed_builders_sweep_count)
    update_next_withdrawal_validator_index(state, expected.withdrawals)


def process_bls_to_execution_change(
    state: BeaconState, signed_address_change: SignedBLSToExecutionChange
) -> None:
    address_change = signed_address_change.message

    assert address_change.validator_index < len(state.validators)

    validator = state.validators[address_change.validator_index]

    assert validator.withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX
    assert validator.withdrawal_credentials[1:] == sha256(address_change.from_bls_pubkey)[1:]

    # Fork-agnostic domain since address changes are valid across forks
    domain = compute_domain(
        DOMAIN_BLS_TO_EXECUTION_CHANGE, genesis_validators_root=state.genesis_validators_root
    )
    signing_root = compute_signing_root(address_change, domain)
    assert bls.Verify(address_change.from_bls_pubkey, signing_root, signed_address_change.signature)

    validator.withdrawal_credentials = Bytes32(
        ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + address_change.to_execution_address
    )


def validate_bls_to_execution_change_gossip(
    seen: Seen,
    store: Store,
    signed_bls_to_execution_change: SignedBLSToExecutionChange,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedBLSToExecutionChange for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    bls_to_execution_change = signed_bls_to_execution_change.message
    validator_index = bls_to_execution_change.validator_index

    # [IGNORE] This is the first valid bls_to_execution_change received for the validator
    if validator_index in seen.bls_to_execution_change_indices:
        raise GossipIgnore("already seen BLS to execution change for this validator")

    # [IGNORE] The current epoch is at or after the Capella fork epoch
    if is_future_epoch(store, config.CAPELLA_FORK_EPOCH, current_time_ms):
        raise GossipIgnore("current epoch is pre-capella")

    state = store.block_states[get_head(store).root]

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    validator = state.validators[validator_index]

    # [REJECT] The validator has BLS withdrawal credentials
    if validator.withdrawal_credentials[:1] != BLS_WITHDRAWAL_PREFIX:
        raise GossipReject("validator does not have BLS withdrawal credentials")

    # [REJECT] The bls_to_execution_change is for the validator's withdrawal pubkey
    pubkey = bls_to_execution_change.from_bls_pubkey
    if validator.withdrawal_credentials[1:] != sha256(pubkey)[1:]:
        raise GossipReject("pubkey does not match validator withdrawal credentials")

    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_BLS_TO_EXECUTION_CHANGE, genesis_validators_root=state.genesis_validators_root
    )
    signing_root = compute_signing_root(bls_to_execution_change, domain)
    if not bls.Verify(pubkey, signing_root, signed_bls_to_execution_change.signature):
        raise GossipReject("invalid BLS to execution change signature")

    # Mark this bls_to_execution_change as seen
    seen.bls_to_execution_change_indices.add(validator_index)


def get_lc_execution_root(header: LightClientHeader) -> Root:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    # [New in Gloas:EIP7732]
    if epoch >= config.GLOAS_FORK_EPOCH:
        return Root(header.execution_block_hash)

    # [Modified in Gloas:EIP7732]
    if epoch >= config.DENEB_FORK_EPOCH:
        if header.beacon.slot == GENESIS_SLOT:
            return hash_tree_root(deneb.ExecutionPayloadHeader.empty())
        BLOCK_HASH_GINDEX = get_generalized_index(deneb.ExecutionPayloadHeader, "block_hash")
    elif epoch >= config.CAPELLA_FORK_EPOCH:
        if header.beacon.slot == GENESIS_SLOT:
            return hash_tree_root(capella.ExecutionPayloadHeader.empty())
        BLOCK_HASH_GINDEX = get_generalized_index(capella.ExecutionPayloadHeader, "block_hash")
    else:
        return Root()

    # [Modified in Gloas:EIP7732]
    inner = header.execution_branch[
        : len(header.execution_branch) - floorlog2(EXECUTION_PAYLOAD_GINDEX)
    ]
    return compute_merkle_branch_root(
        leaf=Bytes32(header.execution_block_hash),
        branch=inner[len(inner) - floorlog2(BLOCK_HASH_GINDEX) :],
        depth=floorlog2(BLOCK_HASH_GINDEX),
        index=get_subtree_index(BLOCK_HASH_GINDEX),
    )


def kzg_commitment_to_versioned_hash(kzg_commitment: KZGCommitment) -> VersionedHash:
    return VersionedHash(VERSIONED_HASH_VERSION_KZG + sha256(kzg_commitment)[1:])


def is_data_available(beacon_block_root: Root) -> bool:
    # `retrieve_column_sidecars_and_kzg_commitments` is implementation and
    # context dependent, replacing `retrieve_column_sidecars`. For the given
    # block root, it returns all column sidecars to sample, or raises an
    # exception if they are not available, in addition it returns all the
    # corresponding kzg commitments. The p2p network does not guarantee sidecar
    # retrieval outside of `config.MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` epochs.
    column_sidecars, kzg_commitments = retrieve_column_sidecars_and_kzg_commitments(
        beacon_block_root
    )
    return all(
        verify_data_column_sidecar(column_sidecar, kzg_commitments)
        and verify_data_column_sidecar_kzg_proofs(column_sidecar, kzg_commitments)
        for column_sidecar in column_sidecars
    )


def is_within_epoch(
    store: Store,
    epoch: Epoch,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the current time is within the given epoch
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance on both ends).
    """
    return is_within_slot_range(
        store,
        compute_start_slot_at_epoch(epoch),
        SLOTS_PER_EPOCH - 1,
        current_time_ms,
    )


def is_current_or_previous_epoch(
    store: Store,
    epoch: Epoch,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the given epoch is the current or previous epoch
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    is_current = is_within_epoch(store, epoch, current_time_ms)
    is_previous = is_within_epoch(store, epoch + 1, current_time_ms)
    return is_current or is_previous


def compute_signed_block_header(signed_block: SignedBeaconBlock) -> SignedBeaconBlockHeader:
    block = signed_block.message
    block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=block.state_root,
        body_root=hash_tree_root(block.body),
    )
    return SignedBeaconBlockHeader(message=block_header, signature=signed_block.signature)


def is_compounding_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    return withdrawal_credentials[:1] == COMPOUNDING_WITHDRAWAL_PREFIX


def has_compounding_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x02 prefixed "compounding" withdrawal credential.
    """
    return is_compounding_withdrawal_credential(validator.withdrawal_credentials)


def has_execution_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has a 0x01 or 0x02 prefixed withdrawal credential.
    """
    return (
        has_eth1_withdrawal_credential(validator)  # 0x01
        or has_compounding_withdrawal_credential(validator)  # 0x02
    )


def is_eligible_for_partial_withdrawals(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` can process a pending partial withdrawal.
    """
    has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
    has_excess_balance = balance > MIN_ACTIVATION_BALANCE
    return (
        validator.exit_epoch == FAR_FUTURE_EPOCH
        and has_sufficient_effective_balance
        and has_excess_balance
    )


def get_committee_indices(committee_bits: BitVector) -> Sequence[CommitteeIndex]:
    return [CommitteeIndex(index) for index, bit in enumerate(committee_bits) if bit]


def get_max_effective_balance(validator: Validator) -> Gwei:
    """
    Get max effective balance for ``validator``.
    """
    if has_compounding_withdrawal_credential(validator):
        return MAX_EFFECTIVE_BALANCE_ELECTRA
    else:
        return MIN_ACTIVATION_BALANCE


def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit reserved for consolidations (EIP-7251).
    Derived from total active balance and rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = get_total_active_balance(state) // config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT


def get_pending_balance_to_withdraw(state: BeaconState, validator_index: ValidatorIndex) -> Gwei:
    balance = Gwei(0)
    for withdrawal in state.pending_partial_withdrawals:
        if withdrawal.validator_index == validator_index:
            balance += withdrawal.amount
    return balance


def switch_to_compounding_validator(state: BeaconState, index: ValidatorIndex) -> None:
    validator = state.validators[index]
    validator.withdrawal_credentials = Bytes32(
        COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    )
    queue_excess_active_balance(state, index)


def queue_excess_active_balance(state: BeaconState, index: ValidatorIndex) -> None:
    balance = state.balances[index]
    if balance > MIN_ACTIVATION_BALANCE:
        excess_balance = balance - MIN_ACTIVATION_BALANCE
        state.balances[index] = MIN_ACTIVATION_BALANCE
        validator = state.validators[index]
        # Use G2_POINT_AT_INFINITY as a signature field placeholder
        # and GENESIS_SLOT to distinguish from a pending deposit request
        state.pending_deposits.append(
            PendingDeposit(
                pubkey=validator.pubkey,
                withdrawal_credentials=validator.withdrawal_credentials,
                amount=excess_balance,
                signature=G2_POINT_AT_INFINITY,
                slot=GENESIS_SLOT,
            )
        )


def compute_exit_epoch_and_update_churn(state: BeaconState, exit_balance: Gwei) -> Epoch:
    earliest_exit_epoch = max(
        state.earliest_exit_epoch, compute_activation_exit_epoch(get_current_epoch(state))
    )
    # [Modified in Gloas:EIP8061]
    per_epoch_churn = get_exit_churn_limit(state)
    # New epoch for exits.
    if state.earliest_exit_epoch < earliest_exit_epoch:
        exit_balance_to_consume = per_epoch_churn
    else:
        exit_balance_to_consume = state.exit_balance_to_consume

    # Exit doesn't fit in the current earliest epoch.
    if exit_balance > exit_balance_to_consume:
        balance_to_process = exit_balance - exit_balance_to_consume
        additional_epochs = (balance_to_process - 1) // per_epoch_churn + 1
        earliest_exit_epoch += Epoch(additional_epochs)
        exit_balance_to_consume += additional_epochs * per_epoch_churn

    # Consume the balance and update state variables.
    state.exit_balance_to_consume = exit_balance_to_consume - exit_balance
    state.earliest_exit_epoch = earliest_exit_epoch

    return state.earliest_exit_epoch


def compute_consolidation_epoch_and_update_churn(
    state: BeaconState, consolidation_balance: Gwei
) -> Epoch:
    earliest_consolidation_epoch = max(
        state.earliest_consolidation_epoch, compute_activation_exit_epoch(get_current_epoch(state))
    )
    per_epoch_consolidation_churn = get_consolidation_churn_limit(state)
    # New epoch for consolidations.
    if state.earliest_consolidation_epoch < earliest_consolidation_epoch:
        consolidation_balance_to_consume = per_epoch_consolidation_churn
    else:
        consolidation_balance_to_consume = state.consolidation_balance_to_consume

    # Consolidation doesn't fit in the current earliest epoch.
    if consolidation_balance > consolidation_balance_to_consume:
        balance_to_process = consolidation_balance - consolidation_balance_to_consume
        additional_epochs = (balance_to_process - 1) // per_epoch_consolidation_churn + 1
        earliest_consolidation_epoch += Epoch(additional_epochs)
        consolidation_balance_to_consume += additional_epochs * per_epoch_consolidation_churn

    # Consume the balance and update state variables.
    state.consolidation_balance_to_consume = (
        consolidation_balance_to_consume - consolidation_balance
    )
    state.earliest_consolidation_epoch = earliest_consolidation_epoch

    return state.earliest_consolidation_epoch


def apply_pending_deposit(state: BeaconState, deposit: PendingDeposit) -> None:
    """
    Applies ``deposit`` to the ``state``.
    """
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if deposit.pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        if is_valid_deposit_signature(
            deposit.pubkey, deposit.withdrawal_credentials, deposit.amount, deposit.signature
        ):
            add_validator_to_registry(
                state, deposit.pubkey, deposit.withdrawal_credentials, deposit.amount
            )
    else:
        validator_index = ValidatorIndex(validator_pubkeys.index(deposit.pubkey))
        increase_balance(state, validator_index, deposit.amount)


def process_pending_deposits(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
    # [Modified in Gloas:EIP8061]
    # Deposits still consume the activation-only churn budget in Gloas.
    available_for_processing = state.deposit_balance_to_consume + get_activation_churn_limit(state)
    processed_amount = 0
    next_deposit_index = 0
    deposits_to_postpone = []
    is_churn_limit_reached = False
    finalized_slot = compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)

    for deposit in state.pending_deposits:
        # Check if deposit has been finalized, otherwise, stop processing.
        if deposit.slot > finalized_slot:
            break

        # Check if number of processed deposits has not reached the limit, otherwise, stop processing.
        if next_deposit_index >= MAX_PENDING_DEPOSITS_PER_EPOCH:
            break

        # Read validator state
        is_validator_exited = False
        is_validator_withdrawn = False
        validator_pubkeys = [validator.pubkey for validator in state.validators]
        if deposit.pubkey in validator_pubkeys:
            validator = state.validators[ValidatorIndex(validator_pubkeys.index(deposit.pubkey))]
            is_validator_exited = validator.exit_epoch < FAR_FUTURE_EPOCH
            is_validator_withdrawn = validator.withdrawable_epoch < next_epoch

        if is_validator_withdrawn:
            # Deposited balance will never become active. Increase balance but do not consume churn
            apply_pending_deposit(state, deposit)
        elif is_validator_exited:
            # Validator is exiting, postpone the deposit until after withdrawable epoch
            deposits_to_postpone.append(deposit)
        else:
            # Check if deposit fits in the churn, otherwise, do no more deposit processing in this epoch.
            is_churn_limit_reached = processed_amount + deposit.amount > available_for_processing
            if is_churn_limit_reached:
                break

            # Consume churn and apply deposit.
            processed_amount += deposit.amount
            apply_pending_deposit(state, deposit)

        # Regardless of how the deposit was handled, we move on in the queue.
        next_deposit_index += 1

    state.pending_deposits = state.pending_deposits[next_deposit_index:] + deposits_to_postpone

    # Accumulate churn only if the churn limit has been hit.
    if is_churn_limit_reached:
        state.deposit_balance_to_consume = available_for_processing - processed_amount
    else:
        state.deposit_balance_to_consume = Gwei(0)


def process_pending_consolidations(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
    next_pending_consolidation = 0
    for pending_consolidation in state.pending_consolidations:
        source_validator = state.validators[pending_consolidation.source_index]
        if source_validator.slashed:
            next_pending_consolidation += 1
            continue
        if source_validator.withdrawable_epoch > next_epoch:
            break

        # Calculate the consolidated balance
        source_effective_balance = min(
            state.balances[pending_consolidation.source_index], source_validator.effective_balance
        )

        # Move active balance to target. Excess balance is withdrawable.
        decrease_balance(state, pending_consolidation.source_index, source_effective_balance)
        increase_balance(state, pending_consolidation.target_index, source_effective_balance)
        next_pending_consolidation += 1

    state.pending_consolidations = state.pending_consolidations[next_pending_consolidation:]


def get_pending_partial_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    withdrawals_limit = min(
        len(prior_withdrawals) + MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        MAX_WITHDRAWALS_PER_PAYLOAD - 1,
    )
    assert len(prior_withdrawals) <= withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    for withdrawal in state.pending_partial_withdrawals:
        all_withdrawals = list(prior_withdrawals) + withdrawals
        is_withdrawable = withdrawal.withdrawable_epoch <= epoch
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if not is_withdrawable or has_reached_limit:
            break

        validator_index = withdrawal.validator_index
        validator = state.validators[validator_index]
        balance = get_balance_after_withdrawals(state, validator_index, all_withdrawals)
        if is_eligible_for_partial_withdrawals(validator, balance):
            withdrawal_amount = min(balance - MIN_ACTIVATION_BALANCE, withdrawal.amount)
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=withdrawal_amount,
                )
            )
            withdrawal_index += 1

        processed_count += 1

    return withdrawals, withdrawal_index, processed_count


def update_pending_partial_withdrawals(
    state: BeaconState, processed_partial_withdrawals_count: Uint64
) -> None:
    state.pending_partial_withdrawals = state.pending_partial_withdrawals[
        processed_partial_withdrawals_count:
    ]


def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests: Sequence[tuple[Bytes1, ProgressiveList]] = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
        (BUILDER_DEPOSIT_REQUEST_TYPE, execution_requests.builder_deposits),
        (BUILDER_EXIT_REQUEST_TYPE, execution_requests.builder_exits),
        # [New in Prereg]
        (VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE, execution_requests.validator_pq_registrations),
        # [New in Prereg]
        (BUILDER_PQ_REGISTRATION_REQUEST_TYPE, execution_requests.builder_pq_registrations),
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]


def is_valid_deposit_signature(
    pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Gwei, signature: BLSSignature
) -> bool:
    deposit_message = DepositMessage(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    # Fork-agnostic domain since deposits are valid across forks
    domain = compute_domain(DOMAIN_DEPOSIT)
    signing_root = compute_signing_root(deposit_message, domain)
    return bls.Verify(pubkey, signing_root, signature)


def process_withdrawal_request(state: BeaconState, withdrawal_request: WithdrawalRequest) -> None:
    amount = withdrawal_request.amount
    is_full_exit_request = amount == FULL_EXIT_REQUEST_AMOUNT

    # If partial withdrawal queue is full, only full exits are processed
    if (
        len(state.pending_partial_withdrawals) == PENDING_PARTIAL_WITHDRAWALS_LIMIT
        and not is_full_exit_request
    ):
        return

    validator_pubkeys = [validator.pubkey for validator in state.validators]
    # Verify pubkey exists
    request_pubkey = withdrawal_request.validator_pubkey
    if request_pubkey not in validator_pubkeys:
        return
    index = ValidatorIndex(validator_pubkeys.index(request_pubkey))
    validator = state.validators[index]

    # Verify withdrawal credentials
    has_correct_credential = has_execution_withdrawal_credential(validator)
    is_correct_source_address = (
        validator.withdrawal_credentials[12:] == withdrawal_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return
    # Verify the validator is active
    if not is_active_validator(validator, get_current_epoch(state)):
        return
    # Verify exit has not been initiated
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    # Verify the validator has been active long enough
    if get_current_epoch(state) < validator.activation_epoch + config.SHARD_COMMITTEE_PERIOD:
        return

    pending_balance_to_withdraw = get_pending_balance_to_withdraw(state, index)

    if is_full_exit_request:
        # Only exit validator if it has no pending withdrawals in the queue
        if pending_balance_to_withdraw == 0:
            initiate_validator_exit(state, index)
        return

    has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
    has_excess_balance = (
        state.balances[index] > MIN_ACTIVATION_BALANCE + pending_balance_to_withdraw
    )

    # Only allow partial withdrawals with compounding withdrawal credentials
    if (
        has_compounding_withdrawal_credential(validator)
        and has_sufficient_effective_balance
        and has_excess_balance
    ):
        to_withdraw = min(
            state.balances[index] - MIN_ACTIVATION_BALANCE - pending_balance_to_withdraw, amount
        )
        exit_queue_epoch = compute_exit_epoch_and_update_churn(state, to_withdraw)
        withdrawable_epoch = exit_queue_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        state.pending_partial_withdrawals.append(
            PendingPartialWithdrawal(
                validator_index=index,
                amount=to_withdraw,
                withdrawable_epoch=withdrawable_epoch,
            )
        )


def process_deposit_request(state: BeaconState, deposit_request: DepositRequest) -> None:
    state.pending_deposits.append(
        PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=state.slot,
        )
    )


def is_valid_switch_to_compounding_request(
    state: BeaconState, consolidation_request: ConsolidationRequest
) -> bool:
    # Switch to compounding requires source and target be equal
    if consolidation_request.source_pubkey != consolidation_request.target_pubkey:
        return False

    # Verify pubkey exists
    source_pubkey = consolidation_request.source_pubkey
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if source_pubkey not in validator_pubkeys:
        return False

    source_validator = state.validators[ValidatorIndex(validator_pubkeys.index(source_pubkey))]

    # Verify request has been authorized
    if source_validator.withdrawal_credentials[12:] != consolidation_request.source_address:
        return False

    # Verify source withdrawal credentials
    if not has_eth1_withdrawal_credential(source_validator):
        return False

    # Verify the source is active
    current_epoch = get_current_epoch(state)
    if not is_active_validator(source_validator, current_epoch):
        return False

    # Verify exit for source has not been initiated
    if source_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return False

    return True


def process_consolidation_request(
    state: BeaconState, consolidation_request: ConsolidationRequest
) -> None:
    if is_valid_switch_to_compounding_request(state, consolidation_request):
        validator_pubkeys = [validator.pubkey for validator in state.validators]
        request_source_pubkey = consolidation_request.source_pubkey
        source_index = ValidatorIndex(validator_pubkeys.index(request_source_pubkey))
        switch_to_compounding_validator(state, source_index)
        return

    # Verify that source != target, so a consolidation cannot be used as an exit
    if consolidation_request.source_pubkey == consolidation_request.target_pubkey:
        return
    # If the pending consolidations queue is full, consolidation requests are ignored
    if len(state.pending_consolidations) == PENDING_CONSOLIDATIONS_LIMIT:
        return
    # If there is too little available consolidation churn limit, consolidation requests are ignored
    if get_consolidation_churn_limit(state) <= MIN_ACTIVATION_BALANCE:
        return

    validator_pubkeys = [validator.pubkey for validator in state.validators]
    # Verify pubkeys exists
    request_source_pubkey = consolidation_request.source_pubkey
    request_target_pubkey = consolidation_request.target_pubkey
    if request_source_pubkey not in validator_pubkeys:
        return
    if request_target_pubkey not in validator_pubkeys:
        return
    source_index = ValidatorIndex(validator_pubkeys.index(request_source_pubkey))
    target_index = ValidatorIndex(validator_pubkeys.index(request_target_pubkey))
    source_validator = state.validators[source_index]
    target_validator = state.validators[target_index]

    # Verify source withdrawal credentials
    has_correct_credential = has_execution_withdrawal_credential(source_validator)
    is_correct_source_address = (
        source_validator.withdrawal_credentials[12:] == consolidation_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return

    # Verify that target has compounding withdrawal credentials
    if not has_compounding_withdrawal_credential(target_validator):
        return

    # Verify the source and the target are active
    current_epoch = get_current_epoch(state)
    if not is_active_validator(source_validator, current_epoch):
        return
    if not is_active_validator(target_validator, current_epoch):
        return
    # Verify exits for source and target have not been initiated
    if source_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    if target_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    # Verify the source has been active long enough
    if current_epoch < source_validator.activation_epoch + config.SHARD_COMMITTEE_PERIOD:
        return
    # Verify the source has no pending withdrawals in the queue
    if get_pending_balance_to_withdraw(state, source_index) > 0:
        return

    # Initiate source validator exit and append pending consolidation
    source_validator.exit_epoch = compute_consolidation_epoch_and_update_churn(
        state, source_validator.effective_balance
    )
    source_validator.withdrawable_epoch = (
        source_validator.exit_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    state.pending_consolidations.append(
        PendingConsolidation(source_index=source_index, target_index=target_index)
    )


def compute_on_chain_aggregate(network_aggregates: Sequence[Attestation]) -> Attestation:
    aggregates = sorted(
        network_aggregates, key=lambda a: get_committee_indices(a.committee_bits)[0]
    )

    data = aggregates[0].data
    aggregation_bits = AggregationBits()
    for a in aggregates:
        for b in a.aggregation_bits:
            aggregation_bits.append(b)

    signature = bls.Aggregate([aggregate.signature for aggregate in aggregates])

    committee_indices = [
        get_committee_indices(aggregate.committee_bits)[0] for aggregate in aggregates
    ]
    committee_flags = [(index in committee_indices) for index in range(MAX_COMMITTEES_PER_SLOT)]
    committee_bits = CommitteeBits(data=committee_flags)

    return Attestation(
        aggregation_bits=AggregationBits(data=aggregation_bits),
        data=data,
        signature=signature,
        committee_bits=CommitteeBits(data=committee_bits),
    )


def get_execution_requests(execution_requests_list: Sequence[bytes]) -> ExecutionRequests:
    deposits = DepositRequests()
    withdrawals = WithdrawalRequests()
    consolidations = ConsolidationRequests()
    builder_deposits = BuilderDepositRequests()
    builder_exits = BuilderExitRequests()
    # [New in Prereg]
    validator_pq_registrations = ValidatorPQRegistrationRequests()
    # [New in Prereg]
    builder_pq_registrations = BuilderPQRegistrationRequests()

    request_types = [
        DEPOSIT_REQUEST_TYPE,
        WITHDRAWAL_REQUEST_TYPE,
        CONSOLIDATION_REQUEST_TYPE,
        BUILDER_DEPOSIT_REQUEST_TYPE,
        BUILDER_EXIT_REQUEST_TYPE,
        # [New in Prereg]
        VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE,
        # [New in Prereg]
        BUILDER_PQ_REGISTRATION_REQUEST_TYPE,
    ]

    prev_request_type = None
    for request in execution_requests_list:
        request_type, request_data = request[0:1], request[1:]

        # Check that the request type is valid
        assert request_type in request_types
        # Check that the request data is not empty
        assert len(request_data) != 0
        # Check that requests are in strictly ascending order
        # Each successive type must be greater than the last with no duplicates
        assert prev_request_type is None or prev_request_type < request_type
        prev_request_type = request_type

        if request_type == DEPOSIT_REQUEST_TYPE:
            deposits = ssz_deserialize(DepositRequests, request_data)
        elif request_type == WITHDRAWAL_REQUEST_TYPE:
            withdrawals = ssz_deserialize(WithdrawalRequests, request_data)
        elif request_type == CONSOLIDATION_REQUEST_TYPE:
            consolidations = ssz_deserialize(ConsolidationRequests, request_data)
        elif request_type == BUILDER_DEPOSIT_REQUEST_TYPE:
            builder_deposits = ssz_deserialize(BuilderDepositRequests, request_data)
        elif request_type == BUILDER_EXIT_REQUEST_TYPE:
            builder_exits = ssz_deserialize(BuilderExitRequests, request_data)
        # [New in Prereg]
        elif request_type == VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE:
            validator_pq_registrations = ssz_deserialize(
                ValidatorPQRegistrationRequests, request_data
            )
        # [New in Prereg]
        elif request_type == BUILDER_PQ_REGISTRATION_REQUEST_TYPE:
            builder_pq_registrations = ssz_deserialize(BuilderPQRegistrationRequests, request_data)

    return ExecutionRequests(
        deposits=deposits,
        withdrawals=withdrawals,
        consolidations=consolidations,
        builder_deposits=builder_deposits,
        builder_exits=builder_exits,
        # [New in Prereg]
        validator_pq_registrations=validator_pq_registrations,
        # [New in Prereg]
        builder_pq_registrations=builder_pq_registrations,
    )


def normalize_merkle_branch(
    branch: Sequence[Bytes32], gindex: GeneralizedIndex
) -> Sequence[Bytes32]:
    depth = floorlog2(gindex)
    num_extra = depth - len(branch)
    return [Bytes32()] * num_extra + [*branch]


def get_blob_parameters(epoch: Epoch) -> BlobParameters:
    """
    Return the blob parameters at a given epoch.
    """
    for entry in sorted(config.BLOB_SCHEDULE, key=lambda e: e["EPOCH"], reverse=True):
        if epoch >= entry["EPOCH"]:
            return BlobParameters(entry["EPOCH"], entry["MAX_BLOBS_PER_BLOCK"])
    return BlobParameters(config.ELECTRA_FORK_EPOCH, config.MAX_BLOBS_PER_BLOCK_ELECTRA)


def compute_proposer_indices(
    state: BeaconState, epoch: Epoch, seed: Bytes32, indices: Sequence[ValidatorIndex]
) -> ProposerIndices:
    """
    Return the proposer indices for the given ``epoch``.
    """
    start_slot = compute_start_slot_at_epoch(epoch)
    seeds = [sha256(seed + uint_to_bytes(start_slot + index)) for index in range(SLOTS_PER_EPOCH)]
    # [Modified in Gloas:EIP7732]
    return ProposerIndices(
        data=[
            compute_balance_weighted_selection(
                state,
                indices,
                seed,
                size=Uint64(1),
                shuffle_indices=True,
            )[0]
            for seed in seeds
        ]
    )


def get_beacon_proposer_indices(state: BeaconState, epoch: Epoch) -> ProposerIndices:
    """
    Return the proposer indices for the given ``epoch``.
    """
    # [Modified in Gloas:EIP8045]
    indices = [
        index
        for index in get_active_validator_indices(state, epoch)
        if not state.validators[index].slashed
    ]
    seed = get_seed(state, epoch, DOMAIN_BEACON_PROPOSER)
    return compute_proposer_indices(state, epoch, seed, indices)


def process_proposer_lookahead(state: BeaconState) -> None:
    last_epoch_start = len(state.proposer_lookahead) - SLOTS_PER_EPOCH
    # Shift out proposers in the first epoch
    state.proposer_lookahead[:last_epoch_start] = state.proposer_lookahead[SLOTS_PER_EPOCH:]
    # Fill in the last epoch with new proposer indices
    last_epoch_proposers = get_beacon_proposer_indices(
        state, get_current_epoch(state) + MIN_SEED_LOOKAHEAD + 1
    )
    state.proposer_lookahead[last_epoch_start:] = last_epoch_proposers


def get_custody_groups(node_id: NodeID, custody_group_count: Uint64) -> Sequence[CustodyIndex]:
    assert custody_group_count <= config.NUMBER_OF_CUSTODY_GROUPS

    # Skip computation if all groups are custodied
    if custody_group_count == config.NUMBER_OF_CUSTODY_GROUPS:
        return [CustodyIndex(index) for index in range(config.NUMBER_OF_CUSTODY_GROUPS)]

    current_id = Uint256(node_id)
    custody_groups: list[CustodyIndex] = []
    while len(custody_groups) < custody_group_count:
        custody_group = CustodyIndex(
            bytes_to_uint64(sha256(uint_to_bytes(current_id))[0:8])
            % config.NUMBER_OF_CUSTODY_GROUPS
        )
        if custody_group not in custody_groups:
            custody_groups.append(custody_group)
        if current_id == UINT256_MAX:
            # Overflow prevention
            current_id = Uint256(0)
        else:
            current_id += 1

    assert len(custody_groups) == len(set(custody_groups))
    return sorted(custody_groups)


def compute_columns_for_custody_group(custody_group: CustodyIndex) -> Sequence[ColumnIndex]:
    assert custody_group < config.NUMBER_OF_CUSTODY_GROUPS
    columns_per_group = NUMBER_OF_COLUMNS // config.NUMBER_OF_CUSTODY_GROUPS
    return [
        ColumnIndex(config.NUMBER_OF_CUSTODY_GROUPS * index + custody_group)
        for index in range(columns_per_group)
    ]


def compute_matrix(blobs: Sequence[Blob]) -> Sequence[MatrixEntry]:
    """
    Return the full, flattened sequence of matrix entries.

    This helper demonstrates the relationship between blobs and the matrix of cells/proofs.
    The data structure for storing cells/proofs is implementation-dependent.
    """
    matrix = []
    for blob_index, blob in enumerate(blobs):
        cells, proofs = kzg.compute_cells_and_kzg_proofs(blob)
        for cell_index, (cell, proof) in enumerate(zip(cells, proofs, strict=True)):
            matrix.append(
                MatrixEntry(
                    cell=cell,
                    kzg_proof=proof,
                    column_index=ColumnIndex(cell_index),
                    row_index=RowIndex(blob_index),
                )
            )
    return matrix


def recover_matrix(
    partial_matrix: Sequence[MatrixEntry], blob_count: Uint64
) -> Sequence[MatrixEntry]:
    """
    Recover the full, flattened sequence of matrix entries.

    This helper demonstrates how to apply ``kzg.recover_cells_and_kzg_proofs``.
    The data structure for storing cells/proofs is implementation-dependent.
    """
    matrix = []
    for blob_index in range(blob_count):
        cell_indices = [e.column_index for e in partial_matrix if e.row_index == blob_index]
        cells = [e.cell for e in partial_matrix if e.row_index == blob_index]
        recovered_cells, recovered_proofs = kzg.recover_cells_and_kzg_proofs(cell_indices, cells)
        for cell_index, (cell, proof) in enumerate(
            zip(recovered_cells, recovered_proofs, strict=True)
        ):
            matrix.append(
                MatrixEntry(
                    cell=cell,
                    kzg_proof=proof,
                    column_index=ColumnIndex(cell_index),
                    row_index=RowIndex(blob_index),
                )
            )
    return matrix


def compute_max_request_data_column_sidecars() -> Uint64:
    """
    Return the maximum number of data column sidecars in a single request.
    """
    return config.MAX_REQUEST_BLOCKS_DENEB * NUMBER_OF_COLUMNS


def verify_data_column_sidecar(
    sidecar: DataColumnSidecar,
    # [New in Gloas:EIP7732]
    kzg_commitments: BlobKZGCommitments,
) -> bool:
    """
    Verify if the data column sidecar is valid.
    """
    # The sidecar index must be within the valid range
    if sidecar.index >= NUMBER_OF_COLUMNS:
        return False

    # [Modified in Gloas:EIP7732]
    # A sidecar for zero blobs is invalid
    if len(sidecar.column) == 0:
        return False

    # [Modified in Gloas:EIP7732]
    # The column length must be equal to the number of commitments
    if len(sidecar.column) != len(kzg_commitments):
        return False

    # The column length must be equal to the number of proofs
    if len(sidecar.column) != len(sidecar.kzg_proofs):
        return False

    return True


def verify_data_column_sidecar_kzg_proofs(
    sidecar: DataColumnSidecar,
    # [New in Gloas:EIP7732]
    kzg_commitments: BlobKZGCommitments,
) -> bool:
    """
    Verify if the KZG proofs are correct.
    """
    # The column index also represents the cell index
    cell_indices = [CellIndex(sidecar.index)] * len(sidecar.column)

    # Batch verify that the cells match the corresponding commitments and proofs
    return kzg.verify_cell_kzg_proof_batch(
        # [Modified in Gloas:EIP7732]
        commitments_bytes=kzg_commitments,
        cell_indices=cell_indices,
        cells=sidecar.column,
        proofs_bytes=sidecar.kzg_proofs,
    )


def compute_subnet_for_data_column_sidecar(column_index: ColumnIndex) -> SubnetID:
    return SubnetID(column_index % config.DATA_COLUMN_SIDECAR_SUBNET_COUNT)


def validate_data_column_sidecar_gossip(
    seen: Seen,
    store: Store,
    sidecar: DataColumnSidecar,
    current_time_ms: Uint64,
    subnet_id: SubnetID,
) -> None:
    """
    Validate a DataColumnSidecar for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    # [IGNORE] This is the first sidecar seen for this block root and column index
    sidecar_key = (sidecar.beacon_block_root, sidecar.index)
    if sidecar_key in seen.data_column_sidecar_tuples:
        raise GossipIgnore("already seen sidecar for this block root and index")

    # [REJECT] The sidecar is for the correct subnet
    if compute_subnet_for_data_column_sidecar(sidecar.index) != subnet_id:
        raise GossipReject("sidecar is for wrong subnet")

    # [IGNORE] The sidecar is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if is_future_slot(store, sidecar.slot, current_time_ms):
        raise GossipIgnore("sidecar is from a future slot")

    # [IGNORE] A block for the sidecar has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    # (SHOULD queue at least one sidecar per peer per subnet)
    if sidecar.beacon_block_root not in store.blocks:
        raise GossipIgnore("block for sidecar's beacon block root has not been seen")

    # [REJECT] The block for the sidecar passes validation
    if sidecar.beacon_block_root not in store.block_states:
        raise GossipReject("block for sidecar's beacon block root failed validation")

    block = store.blocks[sidecar.beacon_block_root]

    # [REJECT] The sidecar's slot matches the slot of the block
    if sidecar.slot != block.slot:
        raise GossipReject("sidecar's slot does not match block's slot")

    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The sidecar passes structural validation
    if not verify_data_column_sidecar(sidecar, bid.blob_kzg_commitments):
        raise GossipReject("invalid sidecar")

    # [REJECT] The sidecar's column data passes KZG verification
    if not verify_data_column_sidecar_kzg_proofs(sidecar, bid.blob_kzg_commitments):
        raise GossipReject("invalid sidecar kzg proofs")

    # Mark this data column sidecar as seen
    seen.data_column_sidecar_tuples.add(sidecar_key)


def get_validators_custody_requirement(
    state: BeaconState, validator_indices: Sequence[ValidatorIndex]
) -> Uint64:
    total_node_balance = sum(
        state.validators[index].effective_balance for index in validator_indices
    )
    count = total_node_balance // config.BALANCE_PER_ADDITIONAL_CUSTODY_GROUP
    return min(max(count, config.VALIDATOR_CUSTODY_REQUIREMENT), config.NUMBER_OF_CUSTODY_GROUPS)


def get_data_column_sidecars(
    # [Modified in Gloas:EIP7732]
    # Removed `signed_block_header`
    # [New in Gloas:EIP7732]
    beacon_block_root: Root,
    # [New in Gloas:EIP7732]
    slot: Slot,
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments`
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments_inclusion_proof`
    cells_and_kzg_proofs: Sequence[tuple[Cells, Proofs]],
) -> Sequence[DataColumnSidecar]:
    """
    Given a beacon block root and the cells/proofs associated with each blob
    in the corresponding payload, assemble the sidecars which can be
    distributed to peers.
    """
    if len(cells_and_kzg_proofs) == 0:
        return []

    sidecars = []
    for column_index in range(NUMBER_OF_COLUMNS):
        column_cells = DataColumn()
        column_proofs = KZGProofs()
        for cells, proofs in cells_and_kzg_proofs:
            column_cells.append(cells[column_index])
            column_proofs.append(proofs[column_index])
        sidecars.append(
            # [Modified in Gloas:EIP7732]
            DataColumnSidecar(
                index=ColumnIndex(column_index),
                column=column_cells,
                kzg_proofs=column_proofs,
                slot=slot,
                beacon_block_root=beacon_block_root,
            )
        )
    return sidecars


def get_data_column_sidecars_from_block(
    signed_block: SignedBeaconBlock,
    cells_and_kzg_proofs: Sequence[tuple[Cells, Proofs]],
) -> Sequence[DataColumnSidecar]:
    """
    Given a signed block and the cells/proofs associated with each blob in the
    block, assemble the sidecars which can be distributed to peers.
    """
    beacon_block_root = hash_tree_root(signed_block.message)
    return get_data_column_sidecars(
        beacon_block_root,
        signed_block.message.slot,
        cells_and_kzg_proofs,
    )


def get_data_column_sidecars_from_column_sidecar(
    sidecar: DataColumnSidecar,
    cells_and_kzg_proofs: Sequence[tuple[Cells, Proofs]],
) -> Sequence[DataColumnSidecar]:
    """
    Given a data column sidecar and the cells/proofs associated with each blob
    in the corresponding payload, assemble the sidecars which can be
    distributed to peers.
    """
    # [Modified in Gloas:EIP7732]
    return get_data_column_sidecars(
        sidecar.beacon_block_root,
        sidecar.slot,
        cells_and_kzg_proofs,
    )


def verify_partial_data_column_sidecar_kzg_proofs(
    sidecar: PartialDataColumnSidecar,
    all_commitments: BlobKZGCommitments,
    column_index: ColumnIndex,
) -> bool:
    """
    Verify the KZG proofs.
    """
    # Get the blob indices from the bitmap
    blob_indices = [index for index, bit in enumerate(sidecar.cells_present_bitmap) if bit]

    # The cell index is the column index for all cells in this column
    cell_indices = [CellIndex(column_index)] * len(blob_indices)

    # Batch verify that the cells match the corresponding commitments and proofs
    return kzg.verify_cell_kzg_proof_batch(
        commitments_bytes=[all_commitments[index] for index in blob_indices],
        cell_indices=cell_indices,
        cells=sidecar.partial_column,
        proofs_bytes=sidecar.kzg_proofs,
    )


def validate_partial_data_column_sidecar_gossip(
    # [Modified in Gloas:EIP7732]
    # Removed `seen`
    store: Store,
    sidecar: PartialDataColumnSidecar,
    # [Modified in Gloas:EIP7732]
    # Removed `current_time_ms`
    group_id: PartialDataColumnGroupID,
    column_index: ColumnIndex,
) -> None:
    """
    Validate a PartialDataColumnSidecar for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    num_cells_present = get_set_bit_count(sidecar.cells_present_bitmap)

    # [Modified in Gloas:EIP7732]
    # [REJECT] The message contains at least one cell
    if num_cells_present == 0:
        raise GossipReject("partial message is semantically empty")

    # [REJECT] The cell count equals the number of set bits in the bitmap
    if len(sidecar.partial_column) != num_cells_present:
        raise GossipReject("number of cells does not match number of set bits")

    # [REJECT] The proof count equals the number of set bits in the bitmap
    if len(sidecar.kzg_proofs) != num_cells_present:
        raise GossipReject("number of proofs does not match number of set bits")

    # [New in Gloas:EIP7732]
    # [IGNORE] The group ID's block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    # (SHOULD queue at least one sidecar per peer per subnet)
    if group_id.beacon_block_root not in store.blocks:
        raise GossipIgnore("group id's block has not been seen")

    # [New in Gloas:EIP7732]
    # [REJECT] The group ID's block passes validation
    if group_id.beacon_block_root not in store.block_states:
        raise GossipReject("group id's block failed validation")

    block = store.blocks[group_id.beacon_block_root]

    # [New in Gloas:EIP7732]
    # [REJECT] The group ID's slot matches the slot of the block
    if group_id.slot != block.slot:
        raise GossipReject("group id's slot does not match the block's slot")

    bid = block.body.signed_execution_payload_bid.message

    # [Modified in Gloas:EIP7732]
    # [REJECT] The cells present bitmap length equals the number of bid commitments
    if len(sidecar.cells_present_bitmap) != len(bid.blob_kzg_commitments):
        raise GossipReject("bitmap length does not match commitments length")

    # [Modified in Gloas:EIP7732]
    # [REJECT] The sidecar's cell and proof data passes KZG verification
    if not verify_partial_data_column_sidecar_kzg_proofs(
        sidecar, bid.blob_kzg_commitments, column_index
    ):
        raise GossipReject("invalid sidecar kzg proofs")


def is_builder_index(validator_index: ValidatorIndex) -> bool:
    return (validator_index & BUILDER_INDEX_FLAG) != 0


def is_active_builder(state: BeaconState, builder_index: BuilderIndex) -> bool:
    """
    Check if the builder at ``builder_index`` is active for the given ``state``.
    """
    builder = state.builders[builder_index]
    return (
        # Placement in builder list is finalized
        builder.deposit_epoch < state.finalized_checkpoint.epoch
        # Has not initiated exit
        and builder.withdrawable_epoch == FAR_FUTURE_EPOCH
    )


def is_builder_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    return withdrawal_credentials[:1] == BUILDER_WITHDRAWAL_PREFIX


def is_attestation_same_slot(state: BeaconState, data: AttestationData) -> bool:
    """
    Check if the attestation is for the block proposed at the attestation slot.
    """
    if data.slot == 0:
        return True

    blockroot = data.beacon_block_root
    slot_blockroot = get_block_root_at_slot(state, data.slot)
    prev_blockroot = get_block_root_at_slot(state, data.slot - 1)

    return blockroot == slot_blockroot and blockroot != prev_blockroot


def is_valid_indexed_payload_attestation(
    state: BeaconState, attestation: IndexedPayloadAttestation
) -> bool:
    """
    Check if ``attestation`` is non-empty, has sorted indices, and has
    a valid aggregate signature.
    """
    # Verify indices are non-empty and sorted
    indices = attestation.attesting_indices
    if len(indices) == 0 or list(indices) != sorted(indices):
        return False

    # Verify aggregate signature
    pubkeys = [state.validators[index].pubkey for index in indices]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(attestation.data.slot))
    signing_root = compute_signing_root(attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, attestation.signature)


def is_pending_validator(pending_deposits: Sequence[PendingDeposit], pubkey: BLSPubkey) -> bool:
    """
    Check if a pending deposit with a valid signature is in the queue for the given pubkey.
    """
    for pending_deposit in pending_deposits:
        if pending_deposit.pubkey != pubkey:
            continue
        if is_valid_deposit_signature(
            pending_deposit.pubkey,
            pending_deposit.withdrawal_credentials,
            pending_deposit.amount,
            pending_deposit.signature,
        ):
            return True
    return False


def convert_builder_index_to_validator_index(builder_index: BuilderIndex) -> ValidatorIndex:
    return ValidatorIndex(builder_index | BUILDER_INDEX_FLAG)


def convert_validator_index_to_builder_index(validator_index: ValidatorIndex) -> BuilderIndex:
    return BuilderIndex(validator_index & ~BUILDER_INDEX_FLAG)


def get_scheduled_gas_limit(epoch: Epoch) -> Uint64 | None:
    """
    Return the scheduled gas limit at a given epoch, if any.
    """
    for entry in sorted(config.GAS_LIMIT_SCHEDULE, key=lambda e: e["EPOCH"], reverse=True):
        if epoch >= entry["EPOCH"]:
            return entry["GAS_LIMIT"]
    return None


def get_pending_balance_to_withdraw_for_builder(
    state: BeaconState, builder_index: BuilderIndex
) -> Gwei:
    balance = Gwei(0)
    for withdrawal in state.builder_pending_withdrawals:
        if withdrawal.builder_index == builder_index:
            balance += withdrawal.amount
    for payment in state.builder_pending_payments:
        if payment.withdrawal.builder_index == builder_index:
            balance += payment.withdrawal.amount
    return balance


def can_builder_cover_bid(
    state: BeaconState, builder_index: BuilderIndex, bid_amount: Gwei
) -> bool:
    builder_balance = state.builders[builder_index].balance
    pending_withdrawals_amount = get_pending_balance_to_withdraw_for_builder(state, builder_index)
    min_balance = MIN_DEPOSIT_AMOUNT + pending_withdrawals_amount
    if builder_balance < min_balance:
        return False
    return builder_balance - min_balance >= bid_amount


def compute_balance_weighted_selection(
    state: BeaconState,
    indices: Sequence[ValidatorIndex],
    seed: Bytes32,
    size: Uint64,
    shuffle_indices: bool,
) -> Sequence[ValidatorIndex]:
    """
    Return ``size`` indices sampled by effective balance, using ``indices``
    as candidates. If ``shuffle_indices`` is ``True``, candidate indices
    are themselves sampled from ``indices`` by shuffling it, otherwise
    ``indices`` is traversed in order. The returned list can contain duplicates.
    """
    MAX_RANDOM_VALUE = 2**16 - 1
    total = Uint64(len(indices))
    assert total > 0
    effective_balances = [state.validators[index].effective_balance for index in indices]
    selected: list[ValidatorIndex] = []
    i = Uint64(0)
    while len(selected) < size:
        offset = i % 16 * 2
        if offset == 0:
            random_bytes = sha256(seed + uint_to_bytes(i // 16))
        next_index = i % total
        if shuffle_indices:
            next_index = compute_shuffled_index(next_index, total, seed)
        weight = effective_balances[next_index] * MAX_RANDOM_VALUE
        random_value = bytes_to_uint64(random_bytes[offset : offset + 2])
        threshold = MAX_EFFECTIVE_BALANCE_ELECTRA * random_value
        if weight >= threshold:
            selected.append(indices[next_index])
        i += 1
    return selected


def compute_ptc(state: BeaconState, slot: Slot) -> PayloadTimelinessCommittee:
    """
    Get the payload timeliness committee, with possible duplicates, for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = sha256(get_seed(state, epoch, DOMAIN_PTC_ATTESTER) + uint_to_bytes(slot))
    indices: list[ValidatorIndex] = []
    # Concatenate all committees for this slot in order
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    for i in range(committees_per_slot):
        committee = get_beacon_committee(state, slot, CommitteeIndex(i))
        indices.extend(committee)
    return PayloadTimelinessCommittee(
        data=compute_balance_weighted_selection(
            state, indices, seed, size=PTC_SIZE, shuffle_indices=False
        )
    )


def get_ptc(state: BeaconState, slot: Slot) -> PayloadTimelinessCommittee:
    """
    Get the payload timeliness committee for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    assert epoch >= config.GLOAS_FORK_EPOCH
    state_epoch = get_current_epoch(state)
    if epoch < state_epoch:
        assert epoch + 1 == state_epoch
        return state.ptc_window[slot % SLOTS_PER_EPOCH]
    assert epoch <= state_epoch + MIN_SEED_LOOKAHEAD
    offset = Uint64(epoch - state_epoch + 1) * SLOTS_PER_EPOCH
    return state.ptc_window[offset + slot % SLOTS_PER_EPOCH]


def get_indexed_payload_attestation(
    state: BeaconState, payload_attestation: PayloadAttestation
) -> IndexedPayloadAttestation:
    """
    Return the indexed payload attestation corresponding to ``payload_attestation``.
    """
    slot = payload_attestation.data.slot
    ptc = get_ptc(state, slot)
    bits = payload_attestation.aggregation_bits
    attesting_indices = [
        validator_index for index, validator_index in enumerate(ptc) if bits[index]
    ]

    return IndexedPayloadAttestation(
        attesting_indices=PayloadTimelinessCommitteeIndices(data=sorted(attesting_indices)),
        data=payload_attestation.data,
        signature=payload_attestation.signature,
    )


def get_builder_payment_quorum_threshold(state: BeaconState) -> Gwei:
    """
    Calculate the quorum threshold for builder payments.
    """
    per_slot_balance = get_total_active_balance(state) // Uint64(SLOTS_PER_EPOCH)
    quorum = per_slot_balance * BUILDER_PAYMENT_THRESHOLD_NUMERATOR
    return quorum // BUILDER_PAYMENT_THRESHOLD_DENOMINATOR


def get_activation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for activations, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    churn = churn - churn % EFFECTIVE_BALANCE_INCREMENT
    return min(config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, churn)


def get_exit_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for exits, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT


def initiate_builder_exit(state: BeaconState, builder_index: BuilderIndex) -> None:
    """
    Initiate the exit of the builder with index ``index``.
    """
    # Set builder exit epoch
    builder = state.builders[builder_index]
    builder.withdrawable_epoch = get_current_epoch(state) + config.MIN_BUILDER_WITHDRAWABILITY_DELAY


def settle_builder_payment(state: BeaconState, payment_index: Uint64) -> None:
    assert payment_index < len(state.builder_pending_payments)
    payment = state.builder_pending_payments[payment_index]
    if payment.withdrawal.amount > 0:
        state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments[payment_index] = BuilderPendingPayment.empty()


def process_builder_pending_payments(state: BeaconState) -> None:
    """
    Processes the builder pending payments from the previous epoch.
    """
    quorum = get_builder_payment_quorum_threshold(state)
    for payment in state.builder_pending_payments[:SLOTS_PER_EPOCH]:
        if payment.weight >= quorum:
            state.builder_pending_withdrawals.append(payment.withdrawal)

    old_payments = state.builder_pending_payments[SLOTS_PER_EPOCH:]
    state.builder_pending_payments[:SLOTS_PER_EPOCH] = old_payments
    new_payments = [BuilderPendingPayment.empty() for _ in range(SLOTS_PER_EPOCH)]
    state.builder_pending_payments[SLOTS_PER_EPOCH:] = new_payments


def process_ptc_window(state: BeaconState) -> None:
    """
    Update the cached PTC window.
    """
    # Shift all epochs forward by one
    state.ptc_window[: len(state.ptc_window) - SLOTS_PER_EPOCH] = state.ptc_window[SLOTS_PER_EPOCH:]
    # Fill in the last epoch
    next_epoch = get_current_epoch(state) + MIN_SEED_LOOKAHEAD + 1
    start_slot = compute_start_slot_at_epoch(next_epoch)
    state.ptc_window[len(state.ptc_window) - SLOTS_PER_EPOCH :] = [
        compute_ptc(state, Slot(slot)) for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH)
    ]


def apply_parent_execution_payload(
    state: BeaconState,
    requests: ExecutionRequests,
) -> None:
    parent_bid = state.latest_execution_payload_bid
    parent_slot = state.latest_block_header.slot
    parent_epoch = compute_epoch_at_slot(parent_slot)

    assert len(requests.withdrawals) <= MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
    assert len(requests.consolidations) <= MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
    assert len(requests.builder_deposits) <= MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
    assert len(requests.builder_exits) <= MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
    # [New in Prereg]
    assert (
        len(requests.validator_pq_registrations)
        <= MAX_VALIDATOR_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD
    )
    # [New in Prereg]
    assert (
        len(requests.builder_pq_registrations) <= MAX_BUILDER_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD
    )

    # Settle the builder payment before the requests so that a builder exit
    # request is rejected while the payment is pending
    if parent_epoch == get_current_epoch(state):
        payment_index = SLOTS_PER_EPOCH + parent_slot % SLOTS_PER_EPOCH
        settle_builder_payment(state, payment_index)
    elif parent_epoch == get_previous_epoch(state):
        payment_index = parent_slot % SLOTS_PER_EPOCH
        settle_builder_payment(state, payment_index)
    elif parent_bid.value > 0:
        # Parent is older than the previous epoch, its payment entry has been
        # evicted from builder_pending_payments. Append the withdrawal directly.
        state.builder_pending_withdrawals.append(
            BuilderPendingWithdrawal(
                fee_recipient=parent_bid.fee_recipient,
                amount=parent_bid.value,
                builder_index=parent_bid.builder_index,
            )
        )

    # Process execution requests from parent's payload. The execution
    # requests are processed at state.slot (child's slot), not the parent's slot.
    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    for_ops(requests.consolidations, process_consolidation_request)
    for_ops(requests.builder_deposits, process_builder_deposit_request)
    for_ops(requests.builder_exits, process_builder_exit_request)
    # [New in Prereg]
    for_ops(requests.validator_pq_registrations, process_validator_pq_registration_request)
    # [New in Prereg]
    for_ops(requests.builder_pq_registrations, process_builder_pq_registration_request)

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash


def process_parent_execution_payload(state: BeaconState, block: BeaconBlock) -> None:
    bid = block.body.signed_execution_payload_bid.message
    parent_bid = state.latest_execution_payload_bid
    requests = block.body.parent_execution_requests

    if bid.parent_block_hash != parent_bid.block_hash:
        # Parent was EMPTY -- no execution requests expected
        assert requests == ExecutionRequests.empty()
        return

    # Parent was FULL -- verify the bid commitment and apply the payload
    assert hash_tree_root(requests) == parent_bid.execution_requests_root
    apply_parent_execution_payload(state, requests)


def get_builder_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD - 1
    assert len(prior_withdrawals) <= withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    for withdrawal in state.builder_pending_withdrawals:
        all_withdrawals = list(prior_withdrawals) + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        builder_index = withdrawal.builder_index
        withdrawals.append(
            Withdrawal(
                index=withdrawal_index,
                validator_index=convert_builder_index_to_validator_index(builder_index),
                address=withdrawal.fee_recipient,
                amount=withdrawal.amount,
            )
        )
        withdrawal_index += 1
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count


def get_builder_balance_after_withdrawals(
    state: BeaconState, builder_index: BuilderIndex, withdrawals: Sequence[Withdrawal]
) -> Gwei:
    validator_index = convert_builder_index_to_validator_index(builder_index)
    withdrawn = Gwei(
        sum(
            withdrawal.amount
            for withdrawal in withdrawals
            if withdrawal.validator_index == validator_index
        )
    )
    return saturating_sub(state.builders[builder_index].balance, withdrawn)


def get_builders_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    builders_limit = min(len(state.builders), MAX_BUILDERS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD - 1
    assert len(prior_withdrawals) <= withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    builder_index = state.next_withdrawal_builder_index
    for _ in range(builders_limit):
        all_withdrawals = list(prior_withdrawals) + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        builder = state.builders[builder_index]
        balance = get_builder_balance_after_withdrawals(state, builder_index, all_withdrawals)
        if builder.withdrawable_epoch <= epoch and balance > 0:
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=convert_builder_index_to_validator_index(builder_index),
                    address=builder.execution_address,
                    amount=balance,
                )
            )
            withdrawal_index += 1

        builder_index = (builder_index + 1) % len(state.builders)
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count


def update_payload_expected_withdrawals(
    state: BeaconState, withdrawals: Sequence[Withdrawal]
) -> None:
    state.payload_expected_withdrawals = Withdrawals(data=withdrawals)


def update_builder_pending_withdrawals(
    state: BeaconState, processed_builder_withdrawals_count: Uint64
) -> None:
    state.builder_pending_withdrawals = state.builder_pending_withdrawals[
        processed_builder_withdrawals_count:
    ]


def update_next_withdrawal_builder_index(
    state: BeaconState, processed_builders_sweep_count: Uint64
) -> None:
    if len(state.builders) > 0:
        # Update the next builder index to start the next withdrawal sweep
        next_index = state.next_withdrawal_builder_index + processed_builders_sweep_count
        next_builder_index = next_index % len(state.builders)
        state.next_withdrawal_builder_index = next_builder_index


def verify_execution_payload_envelope_signature(
    state: BeaconState, signed_envelope: SignedExecutionPayloadEnvelope
) -> bool:
    builder_index = signed_envelope.message.builder_index
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        validator_index = state.latest_block_header.proposer_index
        pubkey = state.validators[validator_index].pubkey
    else:
        pubkey = state.builders[builder_index].pubkey

    signing_root = compute_signing_root(
        signed_envelope.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(pubkey, signing_root, signed_envelope.signature)


def verify_execution_payload_bid_signature(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> bool:
    builder = state.builders[signed_bid.message.builder_index]
    signing_root = compute_signing_root(
        signed_bid.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(builder.pubkey, signing_root, signed_bid.signature)


def process_execution_payload_bid(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> None:
    bid = signed_bid.message
    builder_index = bid.builder_index
    amount = bid.value

    # For self-builds, amount must be zero regardless of withdrawal credential prefix
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        assert amount == 0
        assert signed_bid.signature == bls.G2_POINT_AT_INFINITY
    else:
        # Verify that the builder is active
        assert is_active_builder(state, builder_index)
        # Verify that the builder is a payload builder
        assert state.builders[builder_index].version == PAYLOAD_BUILDER_VERSION
        # Verify that the builder has funds to cover the bid
        assert can_builder_cover_bid(state, builder_index, amount)
        # Verify that the bid signature is valid
        assert verify_execution_payload_bid_signature(state, signed_bid)

    # Verify commitments are under limit
    assert (
        len(bid.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    # Verify that the bid is for the current slot
    assert bid.slot == state.slot
    assert state.slot > GENESIS_SLOT
    # Verify that the bid is for the right parent block
    assert bid.parent_block_hash == state.latest_block_hash
    # Verify that the bid's block hash differs from its parent block hash
    assert bid.block_hash != bid.parent_block_hash
    assert bid.parent_block_root == get_block_root_at_slot(state, state.slot - 1)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))

    # Record the pending payment if there is some payment
    if amount > 0:
        pending_payment = BuilderPendingPayment(
            weight=Gwei(0),
            withdrawal=BuilderPendingWithdrawal(
                fee_recipient=bid.fee_recipient,
                amount=amount,
                builder_index=builder_index,
            ),
            proposer_index=get_beacon_proposer_index(state),
        )
        state.builder_pending_payments[SLOTS_PER_EPOCH + bid.slot % SLOTS_PER_EPOCH] = (
            pending_payment
        )

    # Cache the signed execution payload bid
    state.latest_execution_payload_bid = bid


def is_valid_builder_deposit_signature(request: BuilderDepositRequest) -> bool:
    deposit_message = DepositMessage(
        pubkey=request.pubkey,
        withdrawal_credentials=request.withdrawal_credentials,
        amount=request.amount,
    )
    domain = compute_domain(DOMAIN_BUILDER_DEPOSIT)
    signing_root = compute_signing_root(deposit_message, domain)
    return bls.Verify(request.pubkey, signing_root, request.signature)


def get_index_for_new_builder(state: BeaconState) -> BuilderIndex:
    for index, builder in enumerate(state.builders):
        if builder.withdrawable_epoch <= get_current_epoch(state) and builder.balance == 0:
            return BuilderIndex(index)
    return BuilderIndex(len(state.builders))


def add_builder_to_registry(
    state: BeaconState,
    pubkey: BLSPubkey,
    version: Uint8,
    execution_address: ExecutionAddress,
    amount: Gwei,
    slot: Slot,
) -> None:
    set_or_append_list(
        state.builders,
        get_index_for_new_builder(state),
        Builder(
            pubkey=pubkey,
            version=version,
            execution_address=execution_address,
            balance=amount,
            deposit_epoch=compute_epoch_at_slot(slot),
            withdrawable_epoch=FAR_FUTURE_EPOCH,
        ),
    )


def process_builder_deposit_request(state: BeaconState, request: BuilderDepositRequest) -> None:
    # Ignore deposits with unexpected withdrawal credential prefixes
    if not is_builder_withdrawal_credential(request.withdrawal_credentials):
        return

    builder_pubkeys = [builder.pubkey for builder in state.builders]
    if request.pubkey not in builder_pubkeys:
        if is_valid_builder_deposit_signature(request):
            add_builder_to_registry(
                state,
                request.pubkey,
                PAYLOAD_BUILDER_VERSION,
                ExecutionAddress(request.withdrawal_credentials[12:]),
                request.amount,
                state.slot,
            )
    else:
        builder_index = BuilderIndex(builder_pubkeys.index(request.pubkey))
        builder = state.builders[builder_index]

        # If exited and swept, reset the withdrawable epoch
        if builder.withdrawable_epoch != FAR_FUTURE_EPOCH and builder.balance == 0:
            epoch = get_current_epoch(state)
            builder.withdrawable_epoch = epoch + config.MIN_BUILDER_WITHDRAWABILITY_DELAY

        # Increase balance by deposit amount
        builder.balance += request.amount


def process_builder_exit_request(state: BeaconState, request: BuilderExitRequest) -> None:
    builder_pubkeys = [builder.pubkey for builder in state.builders]
    if request.pubkey not in builder_pubkeys:
        return

    builder_index = BuilderIndex(builder_pubkeys.index(request.pubkey))
    builder = state.builders[builder_index]

    if not is_active_builder(state, builder_index):
        return
    if builder.execution_address != request.source_address:
        return
    if get_pending_balance_to_withdraw_for_builder(state, builder_index) != 0:
        return

    initiate_builder_exit(state, builder_index)


def process_payload_attestation(
    state: BeaconState, payload_attestation: PayloadAttestation
) -> None:
    data = payload_attestation.data

    # Check that the attestation is for the parent beacon block
    assert data.beacon_block_root == state.latest_block_header.parent_root
    # Check that the attestation is for the previous slot
    assert data.slot + 1 == state.slot
    # Verify signature
    indexed_payload_attestation = get_indexed_payload_attestation(state, payload_attestation)
    assert is_valid_indexed_payload_attestation(state, indexed_payload_attestation)


def get_execution_payload_bid_signature(
    state: BeaconState, bid: ExecutionPayloadBid, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_BUILDER, compute_epoch_at_slot(bid.slot))
    signing_root = compute_signing_root(bid, domain)
    return bls.Sign(privkey, signing_root)


def get_execution_payload_envelope_signature(
    state: BeaconState, envelope: ExecutionPayloadEnvelope, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_BUILDER, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(envelope, domain)
    return bls.Sign(privkey, signing_root)


def get_custody_column_bits(node_id: NodeID, custody_group_count: Uint64) -> CustodyColumnBits:
    """
    Compute the bitvector of column indices custodied by ``node_id``.
    """
    bits = CustodyColumnBits()
    for custody_group in get_custody_groups(node_id, custody_group_count):
        for column in compute_columns_for_custody_group(custody_group):
            bits[column] = Boolean(True)
    return bits


def notify_ptc_messages(
    store: Store, state: BeaconState, payload_attestations: Sequence[PayloadAttestation]
) -> None:
    """
    Extracts a list of ``PayloadAttestationMessage`` from ``payload_attestations`` and updates the store with them
    These Payload attestations are assumed to be in the beacon block hence signature verification is not needed
    """
    if state.slot == 0:
        return
    for payload_attestation in payload_attestations:
        indexed_payload_attestation = get_indexed_payload_attestation(state, payload_attestation)
        for idx in indexed_payload_attestation.attesting_indices:
            on_payload_attestation_message(
                store,
                PayloadAttestationMessage(
                    validator_index=idx,
                    data=payload_attestation.data,
                    signature=BLSSignature(),
                ),
                is_from_block=True,
            )


def is_payload_verified(store: Store, root: Root) -> bool:
    """
    Return whether the execution payload envelope for the beacon block with
    root ``root`` has been locally delivered and verified via
    ``on_execution_payload_envelope``.
    """
    return root in store.payloads


def payload_timeliness(store: Store, root: Root, timely: bool) -> bool:
    """
    Return whether the execution payload for the beacon block with root ``root``
    is considered ``timely`` (or not, when ``timely`` is ``False``), taking into
    consideration local availability and PTC votes.
    """
    # The beacon block root must be known
    assert root in store.payload_timeliness_vote

    # If the payload is not locally available, the payload
    # is not considered available regardless of the PTC vote
    if not is_payload_verified(store, root):
        return not timely

    votes = [bool(vote) for vote in store.payload_timeliness_vote[root] if vote is not None]
    return sum(vote == timely for vote in votes) > PAYLOAD_TIMELY_THRESHOLD


def payload_data_availability(store: Store, root: Root, available: bool) -> bool:
    """
    Return whether the blob data for the beacon block with root ``root`` is
    considered ``available`` (or not, when ``available`` is ``False``), taking into
    consideration local availability and PTC votes.
    """
    # The beacon block root must be known
    assert root in store.payload_data_availability_vote

    # If the payload is not locally available, the blob data
    # is not considered available regardless of the PTC vote
    if not is_payload_verified(store, root):
        return not available

    votes = [bool(vote) for vote in store.payload_data_availability_vote[root] if vote is not None]
    return sum(vote == available for vote in votes) > DATA_AVAILABILITY_TIMELY_THRESHOLD


def get_parent_payload_status(store: Store, block: BeaconBlock) -> PayloadStatus:
    parent = store.blocks[block.parent_root]
    parent_block_hash = block.body.signed_execution_payload_bid.message.parent_block_hash
    message_block_hash = parent.body.signed_execution_payload_bid.message.block_hash
    return PAYLOAD_STATUS_FULL if parent_block_hash == message_block_hash else PAYLOAD_STATUS_EMPTY


def is_parent_node_full(store: Store, block: BeaconBlock) -> bool:
    return get_parent_payload_status(store, block) == PAYLOAD_STATUS_FULL


def is_previous_slot_payload_decision(store: Store, node: ForkChoiceNode) -> bool:
    is_previous_slot = store.blocks[node.root].slot + 1 == get_current_slot(store)
    is_payload_decision = node.payload_status in [PAYLOAD_STATUS_EMPTY, PAYLOAD_STATUS_FULL]
    return is_previous_slot and is_payload_decision


def should_build_on_full(store: Store, head: ForkChoiceNode, slot: Slot) -> bool:
    assert head.payload_status != PAYLOAD_STATUS_PENDING
    if store.blocks[head.root].slot + 1 != slot:
        return head.payload_status == PAYLOAD_STATUS_FULL
    if head.payload_status == PAYLOAD_STATUS_EMPTY:
        return False
    if payload_timeliness(store, head.root, timely=False):
        return False
    if payload_data_availability(store, head.root, available=False):
        return False
    return True


def should_extend_payload(store: Store, root: Root) -> bool:
    assert store.blocks[root].slot + 1 == get_current_slot(store)
    if not is_payload_verified(store, root):
        return False
    proposer_root = store.proposer_boost_root
    payload_is_timely = payload_timeliness(store, root, timely=True)
    payload_data_is_available = payload_data_availability(store, root, available=True)
    return (
        (payload_is_timely and payload_data_is_available)
        or proposer_root == Root()
        or store.blocks[proposer_root].parent_root != root
        or is_parent_node_full(store, store.blocks[proposer_root])
    )


def get_payload_status_tiebreaker(store: Store, node: ForkChoiceNode) -> Uint8:
    if is_previous_slot_payload_decision(store, node):
        # To decide on a payload from the previous slot, choose
        # between FULL and EMPTY based on `should_extend_payload`
        if node.payload_status == PAYLOAD_STATUS_EMPTY:
            return Uint8(1)
        if should_extend_payload(store, node.root):
            return Uint8(2)
        return Uint8(0)
    else:
        return node.payload_status


def should_apply_proposer_boost(store: Store) -> bool:
    if store.proposer_boost_root == Root():
        return False

    block = store.blocks[store.proposer_boost_root]
    parent_root = block.parent_root
    parent = store.blocks[parent_root]
    slot = block.slot

    # Apply proposer boost if `parent` is not from the previous slot
    if parent.slot + 1 < slot:
        return True

    # Apply proposer boost if `parent` is not weak
    if not is_head_weak(store, parent_root):
        return True

    # If `parent` is weak and from the previous slot, apply
    # proposer boost if there are no early equivocations
    equivocations = [
        root
        for root, block in store.blocks.items()
        if (
            store.block_timeliness[root][PTC_TIMELINESS_INDEX]
            and block.proposer_index == parent.proposer_index
            and block.slot + 1 == slot
            and root != parent_root
        )
    ]

    return len(equivocations) == 0


def verify_execution_payload_envelope(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
) -> None:
    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Verify consistency with the beacon block
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    assert envelope.beacon_block_root == hash_tree_root(header)
    assert envelope.parent_beacon_block_root == state.latest_block_header.parent_root

    # Verify consistency with the committed bid
    bid = state.latest_execution_payload_bid
    assert envelope.builder_index == bid.builder_index
    assert payload.prev_randao == bid.prev_randao
    assert payload.gas_limit == bid.gas_limit
    assert payload.block_hash == bid.block_hash
    assert hash_tree_root(envelope.execution_requests) == bid.execution_requests_root

    # Verify the execution payload is valid
    assert payload.slot_number == state.slot
    assert payload.parent_hash == state.latest_block_hash
    assert payload.timestamp == compute_time_at_slot(state.genesis_time, state.slot)
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    # Compute versioned hashes
    versioned_hashes = VersionedHashes()
    for commitment in bid.blob_kzg_commitments:
        versioned_hashes.append(kzg_commitment_to_versioned_hash(commitment))

    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=envelope.parent_beacon_block_root,
            execution_requests=envelope.execution_requests,
        )
    )


def is_valid_dependent_root(store: Store, root: Root, dependent_slot: Slot) -> bool:
    """
    Check if the block with the given ``root`` is a possible dependent block
    for the given ``dependent_slot``, meaning that on some branch it is, or
    could become, the latest block at or before ``dependent_slot``.
    """
    if root == get_head(store).root:
        return True
    for block in store.blocks.values():
        if block.parent_root == root:
            if block.slot > dependent_slot:
                return True
    return False


def get_payload_due_ms() -> Uint64:
    return get_slot_component_duration_ms(config.PAYLOAD_DUE_BPS)


def get_payload_attestation_due_ms() -> Uint64:
    return get_slot_component_duration_ms(config.PAYLOAD_ATTESTATION_DUE_BPS)


def on_execution_payload_envelope(
    store: Store, signed_envelope: SignedExecutionPayloadEnvelope
) -> None:
    """
    Run ``on_execution_payload_envelope`` upon receiving a new execution payload envelope.
    """
    envelope = signed_envelope.message
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    state = store.block_states[envelope.beacon_block_root]

    # Verify the execution payload envelope
    verify_execution_payload_envelope(state, signed_envelope, EXECUTION_ENGINE)

    # Add execution payload envelope to the store
    store.payloads[envelope.beacon_block_root] = envelope


def on_payload_attestation_message(
    store: Store, ptc_message: PayloadAttestationMessage, is_from_block: bool = False
) -> None:
    """
    Run ``on_payload_attestation_message`` upon receiving a new payload attestation message
    from either within a block or directly on the wire.
    """
    data = ptc_message.data

    # PTC attestation must be for a known block. If block is unknown, delay consideration until the block is found
    assert data.beacon_block_root in store.block_states
    state = store.block_states[data.beacon_block_root]

    # PTC votes can only change the vote for their assigned beacon block, return early otherwise
    if data.slot != state.slot:
        return

    # Get all positions of the attester in the PTC
    ptc_indices = []
    ptc = get_ptc(state, data.slot)
    for ptc_index, validator_index in enumerate(ptc):
        if validator_index == ptc_message.validator_index:
            ptc_indices.append(ptc_index)

    # Check that the attester is from the PTC
    assert len(ptc_indices) > 0

    # Verify the signature and check that its for the current slot if it is coming from the wire
    if not is_from_block:
        # Check that the attestation is for the current slot
        assert data.slot == get_current_slot(store)
        # Verify the signature
        assert is_valid_indexed_payload_attestation(
            state,
            IndexedPayloadAttestation(
                attesting_indices=PayloadTimelinessCommitteeIndices(
                    data=[ptc_message.validator_index]
                ),
                data=data,
                signature=ptc_message.signature,
            ),
        )

    # Update the votes for the block
    payload_timeliness_vote = store.payload_timeliness_vote[data.beacon_block_root]
    payload_data_availability_vote = store.payload_data_availability_vote[data.beacon_block_root]
    for ptc_index in ptc_indices:
        payload_timeliness_vote[ptc_index] = data.payload_present
        payload_data_availability_vote[ptc_index] = data.blob_data_available


def initialize_ptc_window(
    state: BeaconState,
) -> PayloadTimelinessCommitteeWindow:
    """
    Return the cached PTC window starting from the current epoch.
    Used to initialize the ``ptc_window`` field in the beacon state at genesis and after forks.
    """
    empty_previous_epoch = [
        PayloadTimelinessCommittee(data=[ValidatorIndex(0) for _ in range(PTC_SIZE)])
        for _ in range(SLOTS_PER_EPOCH)
    ]

    ptcs = []
    current_epoch = get_current_epoch(state)
    for e in range(1 + MIN_SEED_LOOKAHEAD):
        epoch = current_epoch + e
        start_slot = compute_start_slot_at_epoch(epoch)
        ptcs += [compute_ptc(state, start_slot + index) for index in range(SLOTS_PER_EPOCH)]

    return PayloadTimelinessCommitteeWindow(data=empty_previous_epoch + ptcs)


def onboard_builders_from_pending_deposits(state: BeaconState) -> None:
    """
    Applies any pending deposit for builders, effectively
    onboarding builders at the fork.
    """
    validator_pubkeys = [validator.pubkey for validator in state.validators]

    pending_deposits = PendingDeposits()
    for deposit in state.pending_deposits:
        # Only builder-credential deposits can fund builders at the fork.
        if not is_builder_withdrawal_credential(deposit.withdrawal_credentials):
            pending_deposits.append(deposit)
            continue

        # Note that applying a deposit below can mutate the state and
        # may add a builder to the registry. For this reason, the list
        # of builder pubkeys must be recomputed each iteration.
        builder_pubkeys = [builder.pubkey for builder in state.builders]

        if deposit.pubkey not in builder_pubkeys:
            if not is_valid_deposit_signature(
                deposit.pubkey,
                deposit.withdrawal_credentials,
                deposit.amount,
                deposit.signature,
            ):
                # Preserve validator top-ups when no builder can receive them.
                if deposit.pubkey in validator_pubkeys or is_pending_validator(
                    pending_deposits, deposit.pubkey
                ):
                    pending_deposits.append(deposit)
                continue

            add_builder_to_registry(
                state,
                deposit.pubkey,
                PAYLOAD_BUILDER_VERSION,
                ExecutionAddress(deposit.withdrawal_credentials[12:]),
                deposit.amount,
                deposit.slot,
            )
        else:
            builder_index = BuilderIndex(builder_pubkeys.index(deposit.pubkey))
            state.builders[builder_index].balance += deposit.amount

    state.pending_deposits = pending_deposits


def upgrade_attestation_to_gloas(pre: fulu.Attestation) -> Attestation:
    return Attestation(
        aggregation_bits=AggregationBits(data=pre.aggregation_bits),
        data=pre.data,
        signature=pre.signature,
        committee_bits=pre.committee_bits,
    )


def upgrade_indexed_attestation_to_gloas(pre: fulu.IndexedAttestation) -> IndexedAttestation:
    return IndexedAttestation(
        attesting_indices=AttestingIndices(data=pre.attesting_indices),
        data=pre.data,
        signature=pre.signature,
    )


def upgrade_attester_slashing_to_gloas(pre: fulu.AttesterSlashing) -> AttesterSlashing:
    return AttesterSlashing(
        attestation_1=upgrade_indexed_attestation_to_gloas(pre.attestation_1),
        attestation_2=upgrade_indexed_attestation_to_gloas(pre.attestation_2),
    )


def compute_max_data_column_sidecar_size() -> Uint64:
    """
    Return the maximum size of a serialized ``DataColumnSidecar`` computed
    using the largest ``max_blobs_per_block`` value from the blob schedule,
    regardless of whether or not that is the current ``max_blobs_per_block``.
    """
    max_blobs = config.MAX_BLOBS_PER_BLOCK_ELECTRA
    for entry in config.BLOB_SCHEDULE:
        max_blobs = max(max_blobs, entry["MAX_BLOBS_PER_BLOCK"])

    sidecar = DataColumnSidecar(
        index=ColumnIndex(),
        column=DataColumn(data=[Cell()] * max_blobs),
        kzg_proofs=KZGProofs(data=[KZGProof()] * max_blobs),
        slot=Slot(),
        beacon_block_root=Root(),
    )
    return Uint64(len(ssz_serialize(sidecar)))


def is_current_or_next_slot(
    store: Store,
    slot: Slot,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the given slot is the current slot or the next slot
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    is_current = is_current_slot(store, slot, current_time_ms)
    is_next = is_current_slot(store, slot - 1, current_time_ms)
    return is_current or is_next


def is_past_slot(
    store: Store,
    slot: Slot,
    current_time_ms: Uint64,
) -> bool:
    """
    Check if the given slot is in the past
    (with config.MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    slot_time_ms = compute_time_at_slot_ms(store.genesis_time_ms, slot)
    return current_time_ms > slot_time_ms + config.MAXIMUM_GOSSIP_CLOCK_DISPARITY


def is_gas_limit_target_compatible(
    parent_gas_limit: Uint64, gas_limit: Uint64, target_gas_limit: Uint64
) -> bool:
    """
    Check if ``gas_limit`` is compatible with ``target_gas_limit`` under the
    EIP-1559 transition rule from ``parent_gas_limit``.
    """
    max_gas_limit_difference = saturating_sub(parent_gas_limit // 1024, 1)
    min_gas_limit = parent_gas_limit - max_gas_limit_difference
    max_gas_limit = parent_gas_limit + max_gas_limit_difference

    if target_gas_limit < min_gas_limit:
        return gas_limit == min_gas_limit
    if target_gas_limit > max_gas_limit:
        return gas_limit == max_gas_limit
    return gas_limit == target_gas_limit


def is_bid_compatible_with_head(store: Store, bid: ExecutionPayloadBid) -> bool:
    """
    Check if ``bid`` is compatible with the head branch.
    """
    head_node = get_head(store)
    head_block = store.blocks[head_node.root]
    head_bid = head_block.body.signed_execution_payload_bid.message

    builds_on_parent_block = bid.parent_block_root == head_block.parent_root
    builds_on_parent_payload = bid.parent_block_hash == head_bid.parent_block_hash

    if builds_on_parent_block and builds_on_parent_payload:
        return True

    if bid.parent_block_root != head_node.root:
        return False

    builds_on_head_payload = bid.parent_block_hash == head_bid.block_hash

    if should_build_on_full(store, head_node, bid.slot):
        return builds_on_head_payload

    return builds_on_parent_payload


def verify_attestation_payload_status(
    store: Store,
    data: AttestationData,
    block_payload_statuses: dict[Root, PayloadValidationStatus],
) -> None:
    """
    Verify that the attested payload status is consistent with the block's payload.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block_root = data.beacon_block_root
    block = store.blocks[block_root]

    # [REJECT] For same-slot attestations, the payload cannot yet be present
    if block.slot == data.slot and data.index != 0:
        raise GossipReject("same-slot attestation must attest with index 0")

    if data.index != 1:
        return

    # [IGNORE] The corresponding execution payload envelope has been seen and verified
    # (MAY queue attestations for processing once the payload is retrieved and
    # SHOULD request the payload envelope via ExecutionPayloadEnvelopesByRoot
    # using data.beacon_block_root)
    if not is_payload_verified(store, block_root):
        raise GossipIgnore("execution payload envelope has not been seen")

    # [IGNORE] The attested execution payload is optimistic
    payload_status = block_payload_statuses.get(block_root, PAYLOAD_STATUS_NOT_VALIDATED)
    if payload_status == PAYLOAD_STATUS_NOT_VALIDATED:
        raise GossipIgnore("attested payload is optimistic")

    # [REJECT] The attested execution payload is processed and invalid
    if payload_status == PAYLOAD_STATUS_INVALIDATED:
        raise GossipReject("attested payload is invalid")


def verify_block_body_operation_limits(body: BeaconBlockBody) -> None:
    """
    Verify that each block body operation count is within its limit.
    Raises GossipReject on validation failure.
    """
    # [REJECT] The proposer slashing count is within the limit
    if len(body.proposer_slashings) > MAX_PROPOSER_SLASHINGS:
        raise GossipReject("too many proposer slashings")

    # [REJECT] The attester slashing count is within the limit
    if len(body.attester_slashings) > MAX_ATTESTER_SLASHINGS_ELECTRA:
        raise GossipReject("too many attester slashings")

    # [REJECT] The attestation count is within the limit
    if len(body.attestations) > MAX_ATTESTATIONS_ELECTRA:
        raise GossipReject("too many attestations")

    # [REJECT] The block contains no deposits
    if len(body.deposits) != 0:
        raise GossipReject("block must not contain deposits")

    # [REJECT] The voluntary exit count is within the limit
    if len(body.voluntary_exits) > MAX_VOLUNTARY_EXITS:
        raise GossipReject("too many voluntary exits")

    # [REJECT] The BLS to execution change count is within the limit
    if len(body.bls_to_execution_changes) > MAX_BLS_TO_EXECUTION_CHANGES:
        raise GossipReject("too many bls to execution changes")

    # [REJECT] The payload attestation count is within the limit
    if len(body.payload_attestations) > MAX_PAYLOAD_ATTESTATIONS:
        raise GossipReject("too many payload attestations")


def verify_execution_requests_limits(execution_requests: ExecutionRequests) -> None:
    """
    Verify that each execution request count is within its limit.
    Raises GossipReject on validation failure.
    """
    # [REJECT] The withdrawal request count is within the limit
    if len(execution_requests.withdrawals) > MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many withdrawal requests")

    # [REJECT] The consolidation request count is within the limit
    if len(execution_requests.consolidations) > MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many consolidation requests")

    # [REJECT] The builder deposit request count is within the limit
    if len(execution_requests.builder_deposits) > MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder deposit requests")

    # [REJECT] The builder exit request count is within the limit
    if len(execution_requests.builder_exits) > MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder exit requests")

    # [New in Prereg]
    # [REJECT] The validator PQ registration request count is within the limit
    validator_pq_registrations = execution_requests.validator_pq_registrations
    if len(validator_pq_registrations) > MAX_VALIDATOR_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many validator PQ registration requests")

    # [New in Prereg]
    # [REJECT] The builder PQ registration request count is within the limit
    builder_pq_registrations = execution_requests.builder_pq_registrations
    if len(builder_pq_registrations) > MAX_BUILDER_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder PQ registration requests")


def validate_execution_payload_envelope_gossip(
    seen: Seen,
    store: Store,
    signed_execution_payload_envelope: SignedExecutionPayloadEnvelope,
) -> None:
    """
    Validate a SignedExecutionPayloadEnvelope for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    envelope = signed_execution_payload_envelope.message
    payload = envelope.payload
    block_root = envelope.beacon_block_root

    # [IGNORE] The node has not seen another valid envelope for this block root from this builder
    envelope_key = (block_root, envelope.builder_index)
    if envelope_key in seen.execution_payload_envelopes:
        raise GossipIgnore("already seen envelope for this block root from this builder")

    # [IGNORE] The envelope's block root has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if block_root not in store.blocks:
        raise GossipIgnore("envelope's block has not been seen")

    # [REJECT] The envelope's block passes validation
    if block_root not in store.block_states:
        raise GossipReject("envelope's block failed validation")

    state = store.block_states[block_root]

    # [IGNORE] The envelope is from a slot greater than or equal to the latest finalized slot
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if payload.slot_number < finalized_slot:
        raise GossipIgnore("envelope is from a slot before the latest finalized slot")

    block = store.blocks[block_root]
    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The block's slot matches the payload's slot number
    if block.slot != payload.slot_number:
        raise GossipReject("block's slot does not match payload's slot number")

    # [REJECT] The envelope is from the builder committed to by the bid
    if envelope.builder_index != bid.builder_index:
        raise GossipReject("envelope's builder index does not match the bid's builder index")

    # [REJECT] The payload's block hash matches the bid's block hash
    if payload.block_hash != bid.block_hash:
        raise GossipReject("payload's block hash does not match the bid's block hash")

    # [REJECT] The envelope's execution requests root matches the bid's execution requests root
    if hash_tree_root(envelope.execution_requests) != bid.execution_requests_root:
        raise GossipReject("envelope's execution requests root does not match the bid's")

    # [REJECT] The execution request counts are within their limits
    verify_execution_requests_limits(envelope.execution_requests)

    # [REJECT] The number of withdrawals is within the limit
    if len(payload.withdrawals) > MAX_WITHDRAWALS_PER_PAYLOAD:
        raise GossipReject("too many withdrawals")

    # [REJECT] The envelope signature is valid
    if not verify_execution_payload_envelope_signature(state, signed_execution_payload_envelope):
        raise GossipReject("invalid envelope signature")

    # Mark this envelope as seen and store its payload
    seen.execution_payload_envelopes.add(envelope_key)
    seen.execution_payloads[payload.block_hash] = payload


def validate_payload_attestation_message_gossip(
    seen: Seen,
    store: Store,
    payload_attestation_message: PayloadAttestationMessage,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a PayloadAttestationMessage for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = payload_attestation_message.data
    validator_index = payload_attestation_message.validator_index

    # [REJECT] The payload attestation's slot is at or after the Gloas fork
    if compute_epoch_at_slot(data.slot) < config.GLOAS_FORK_EPOCH:
        raise GossipReject("payload attestation's slot is pre-gloas")

    # [IGNORE] This is the first valid payload attestation from this validator index
    payload_attestation_key = (data.slot, validator_index)
    if payload_attestation_key in seen.payload_attestation_validators:
        raise GossipIgnore("already seen payload attestation from this validator")

    # [IGNORE] The payload attestation's slot is for the current slot
    if not is_current_slot(store, data.slot, current_time_ms):
        raise GossipIgnore("payload attestation is not for the current slot")

    # [IGNORE] The payload attestation's block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if data.beacon_block_root not in store.blocks:
        raise GossipIgnore("payload attestation's block has not been seen")

    # [REJECT] The payload attestation's block passes validation
    if data.beacon_block_root not in store.block_states:
        raise GossipReject("payload attestation's block failed validation")

    # [IGNORE] The payload attestation's block is at the assigned slot
    if store.blocks[data.beacon_block_root].slot != data.slot:
        raise GossipIgnore("payload attestation's block is not at the assigned slot")

    state = store.block_states[get_head(store).root]

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [REJECT] The validator is a member of the payload timeliness committee
    if validator_index not in get_ptc(state, data.slot):
        raise GossipReject("validator is not in the payload timeliness committee")

    # [REJECT] The signature is valid
    validator = state.validators[validator_index]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    if not bls.Verify(validator.pubkey, signing_root, payload_attestation_message.signature):
        raise GossipReject("invalid payload attestation signature")

    # Mark this payload_attestation as seen
    seen.payload_attestation_validators.add(payload_attestation_key)


def validate_execution_payload_bid_gossip(
    seen: Seen,
    store: Store,
    signed_execution_payload_bid: SignedExecutionPayloadBid,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedExecutionPayloadBid for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    bid = signed_execution_payload_bid.message

    # [IGNORE] This is the first bid for this slot, parent, and builder
    bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root, bid.builder_index)
    if bid_key in seen.execution_payload_bids:
        raise GossipIgnore("already seen valid bid for this slot, parent, and builder")

    # [IGNORE] This is the highest value bid seen for the slot and parent
    best_bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root)
    if best_bid_key in seen.best_execution_payload_bid:
        if bid.value <= seen.best_execution_payload_bid[best_bid_key]:
            raise GossipIgnore("bid is not the highest value bid seen for this slot and parent")

    # [IGNORE] The bid's slot is the current slot or the next slot
    if not is_current_or_next_slot(store, bid.slot, current_time_ms):
        raise GossipIgnore("bid's slot is not the current or next slot")

    # [REJECT] The bid's execution payment is zero
    if bid.execution_payment != 0:
        raise GossipReject("bid's execution payment must be zero")

    # [REJECT] The bid's block hash is not equal to its parent block hash
    if bid.block_hash == bid.parent_block_hash:
        raise GossipReject("bid's block hash equals its parent block hash")

    # [REJECT] The bid's blob KZG commitment count is within the per-epoch limit
    proposal_epoch = compute_epoch_at_slot(bid.slot)
    max_blobs = get_blob_parameters(proposal_epoch).max_blobs_per_block
    if len(bid.blob_kzg_commitments) > max_blobs:
        raise GossipReject("too many blob kzg commitments")

    # [IGNORE] The bid's parent block root is a known beacon block
    # (MAY be queued until parent is retrieved)
    if bid.parent_block_root not in store.blocks:
        raise GossipIgnore("bid's parent block root is not a known beacon block")

    # [REJECT] The bid is for a higher slot than its parent block
    if bid.slot <= store.blocks[bid.parent_block_root].slot:
        raise GossipReject("bid's slot is not higher than its parent's slot")

    # [IGNORE] The bid's parent block has been imported
    # (MAY be queued until parent is imported)
    if bid.parent_block_root not in store.block_states:
        raise GossipIgnore("bid's parent block post-state is unavailable")

    state = store.block_states[bid.parent_block_root]

    # [IGNORE] The bid's slot is within the parent's proposer lookahead
    if proposal_epoch > get_current_epoch(state) + MIN_SEED_LOOKAHEAD:
        raise GossipIgnore("bid's slot is past the parent's proposer lookahead")

    # [IGNORE] The matching proposer preferences have been seen
    dependent_root = get_shuffling_dependent_root(store, bid.parent_block_root, proposal_epoch)
    prefs_key = (bid.slot, dependent_root)
    if prefs_key not in seen.proposer_preferences:
        raise GossipIgnore("matching proposer preferences have not been seen")

    proposer_preferences = seen.proposer_preferences[prefs_key]

    # [IGNORE] The bid's fee recipient matches the proposer's preference
    if bid.fee_recipient != proposer_preferences.fee_recipient:
        raise GossipIgnore("bid's fee recipient does not match the proposer's preference")

    # [IGNORE] The bid's parent block hash is the hash of a known execution payload
    if bid.parent_block_hash not in seen.execution_payloads:
        raise GossipIgnore("bid's parent block hash is not a known execution payload")

    # [IGNORE] The bid's gas limit is compatible with the proposer's target gas limit
    parent_gas_limit = seen.execution_payloads[bid.parent_block_hash].gas_limit
    if not is_gas_limit_target_compatible(
        parent_gas_limit, bid.gas_limit, proposer_preferences.target_gas_limit
    ):
        raise GossipIgnore("bid's gas limit is not compatible with the proposer's target")

    # [IGNORE] The bid is compatible with the current head branch
    if not is_bid_compatible_with_head(store, bid):
        raise GossipIgnore("bid is not compatible with the current head branch")

    # [REJECT] The bid's previous randao is correct
    if bid.prev_randao != get_randao_mix(state, get_current_epoch(state)):
        raise GossipReject("bid's previous randao is incorrect")

    state = state.copy()
    process_slots(state, bid.slot)

    # [REJECT] The builder index is valid
    if bid.builder_index >= len(state.builders):
        raise GossipReject("builder index out of range")

    builder = state.builders[bid.builder_index]

    # [REJECT] The builder is a payload builder
    if builder.version != PAYLOAD_BUILDER_VERSION:
        raise GossipReject("builder is not a payload builder")

    # [REJECT] The builder is active
    if not is_active_builder(state, bid.builder_index):
        raise GossipReject("builder is not active")

    # [IGNORE] The builder can cover the bid
    if not can_builder_cover_bid(state, bid.builder_index, bid.value):
        raise GossipIgnore("builder cannot cover bid value")

    # [IGNORE] The parent's payload does not try to exit the builder
    if bid.parent_block_hash == state.latest_execution_payload_bid.block_hash:
        envelope = store.payloads[bid.parent_block_root]
        for request in envelope.execution_requests.builder_exits:
            if request.pubkey == builder.pubkey:
                if request.source_address == builder.execution_address:
                    raise GossipIgnore("builder may exit")

    # [REJECT] The bid signature is valid
    if not verify_execution_payload_bid_signature(state, signed_execution_payload_bid):
        raise GossipReject("invalid bid signature")

    # Mark this bid as seen and update the highest-value bid for this slot/parent
    seen.execution_payload_bids.add(bid_key)
    seen.best_execution_payload_bid[best_bid_key] = bid.value


def validate_proposer_preferences_gossip(
    seen: Seen,
    store: Store,
    signed_proposer_preferences: SignedProposerPreferences,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedProposerPreferences for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    preferences = signed_proposer_preferences.message

    # [IGNORE] These are the first valid preferences seen for this dependent root and slot
    prefs_key = (preferences.proposal_slot, preferences.dependent_root)
    if prefs_key in seen.proposer_preferences:
        raise GossipIgnore("already seen preferences for this dependent root and proposal slot")

    # [IGNORE] The proposal epoch is after the Gloas upgrade
    proposal_epoch = compute_epoch_at_slot(preferences.proposal_slot)
    if proposal_epoch < config.GLOAS_FORK_EPOCH:
        raise GossipIgnore("proposal epoch is pre-gloas")

    # [IGNORE] The proposal slot has not started yet
    if is_past_slot(store, preferences.proposal_slot, current_time_ms):
        raise GossipIgnore("proposal slot has already started")

    # [IGNORE] The proposer for the proposal slot is known
    lookahead_start_slot = compute_shuffling_lookahead_start_slot(proposal_epoch)
    if is_future_slot(store, lookahead_start_slot, current_time_ms):
        raise GossipIgnore("proposer for the proposal slot is not yet known")

    # [IGNORE] The dependent block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if preferences.dependent_root not in store.blocks:
        raise GossipIgnore("dependent block has not been seen")

    # [IGNORE] The dependent block passes validation
    if preferences.dependent_root not in store.block_states:
        raise GossipIgnore("dependent block failed validation")

    # [REJECT] The dependent block's slot is not after the shuffling dependent slot
    dependent_slot = compute_shuffling_dependent_slot(proposal_epoch)
    if store.blocks[preferences.dependent_root].slot > dependent_slot:
        raise GossipReject("dependent block is after the shuffling dependent slot")

    # [IGNORE] The dependent block is a possible dependent block for the proposer lookahead
    if not is_valid_dependent_root(store, preferences.dependent_root, dependent_slot):
        raise GossipIgnore("dependent block is not a possible dependent block")

    state = store.block_states[preferences.dependent_root].copy()
    if state.slot < lookahead_start_slot:
        process_slots(state, lookahead_start_slot)

    # [REJECT] The validator is the proposer for the given slot in the proposer lookahead
    lookahead_index = preferences.proposal_slot - lookahead_start_slot
    if state.proposer_lookahead[lookahead_index] != preferences.validator_index:
        raise GossipReject("validator is not the proposer for the given slot")

    # [REJECT] The signature is valid
    validator = state.validators[preferences.validator_index]
    domain = compute_domain(
        DOMAIN_PROPOSER_PREFERENCES,
        compute_fork_version(proposal_epoch),
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(preferences, domain)
    if not bls.Verify(validator.pubkey, signing_root, signed_proposer_preferences.signature):
        raise GossipReject("invalid proposer preferences signature")

    # Mark these preferences as seen
    seen.proposer_preferences[prefs_key] = preferences


def get_ptc_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Slot | None:
    """
    Returns the slot during the requested epoch in which the validator with
    index ``validator_index`` is a member of the PTC. Returns None if no
    assignment is found.
    """
    max_epoch = get_current_epoch(state) + MIN_SEED_LOOKAHEAD
    assert epoch <= max_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_ptc(state, Slot(slot)):
            return Slot(slot)
    return None


def get_upcoming_proposal_slots(
    state: BeaconState, validator_index: ValidatorIndex
) -> Sequence[Slot]:
    """
    Get the future slots within the proposer lookahead for which
    ``validator_index`` is proposing.
    """
    current_epoch_start_slot = compute_start_slot_at_epoch(get_current_epoch(state))
    upcoming_proposal_slots = []
    for offset, proposer_index in enumerate(state.proposer_lookahead):
        slot = current_epoch_start_slot + offset
        if slot <= state.slot:
            continue
        if validator_index == proposer_index:
            upcoming_proposal_slots.append(slot)
    return upcoming_proposal_slots


def get_signed_proposer_preferences(
    store: Store,
    state: BeaconState,
    head_root: Root,
    proposal_slot: Slot,
    validator_index: ValidatorIndex,
    fee_recipient: ExecutionAddress,
    target_gas_limit: Uint64,
    privkey: int,
) -> SignedProposerPreferences:
    proposal_epoch = compute_epoch_at_slot(proposal_slot)
    dependent_root = get_shuffling_dependent_root(store, head_root, proposal_epoch)
    preferences = ProposerPreferences(
        dependent_root=dependent_root,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=fee_recipient,
        target_gas_limit=target_gas_limit,
    )
    domain = compute_domain(
        DOMAIN_PROPOSER_PREFERENCES,
        compute_fork_version(proposal_epoch),
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(preferences, domain)
    signature = bls.Sign(privkey, signing_root)
    return SignedProposerPreferences(message=preferences, signature=signature)


def get_payload_attestation_message_signature(
    state: BeaconState, attestation: PayloadAttestationMessage, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(attestation.data.slot))
    signing_root = compute_signing_root(attestation.data, domain)
    return bls.Sign(privkey, signing_root)


def upgrade_lc_header_to_gloas(pre: electra.LightClientHeader) -> LightClientHeader:
    if pre == electra.LightClientHeader.empty():
        return LightClientHeader.empty()

    epoch = compute_epoch_at_slot(pre.beacon.slot)

    if epoch >= config.DENEB_FORK_EPOCH:
        BLOCK_HASH_GINDEX = get_generalized_index(deneb.ExecutionPayloadHeader, "block_hash")
        return LightClientHeader(
            beacon=pre.beacon,
            execution_block_hash=pre.execution.block_hash,
            execution_branch=ExecutionBranch(
                data=normalize_merkle_branch(
                    list(compute_merkle_proof(pre.execution, BLOCK_HASH_GINDEX))
                    + list(pre.execution_branch),
                    EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
                )
            ),
        )

    if epoch >= config.CAPELLA_FORK_EPOCH:
        execution_header = capella.ExecutionPayloadHeader(
            parent_hash=pre.execution.parent_hash,
            fee_recipient=pre.execution.fee_recipient,
            state_root=pre.execution.state_root,
            receipts_root=pre.execution.receipts_root,
            logs_bloom=pre.execution.logs_bloom,
            prev_randao=pre.execution.prev_randao,
            block_number=pre.execution.block_number,
            gas_limit=pre.execution.gas_limit,
            gas_used=pre.execution.gas_used,
            timestamp=pre.execution.timestamp,
            extra_data=pre.execution.extra_data,
            base_fee_per_gas=pre.execution.base_fee_per_gas,
            block_hash=pre.execution.block_hash,
            transactions_root=pre.execution.transactions_root,
            withdrawals_root=pre.execution.withdrawals_root,
        )
        BLOCK_HASH_GINDEX = get_generalized_index(capella.ExecutionPayloadHeader, "block_hash")
        return LightClientHeader(
            beacon=pre.beacon,
            execution_block_hash=pre.execution.block_hash,
            execution_branch=ExecutionBranch(
                data=normalize_merkle_branch(
                    list(compute_merkle_proof(execution_header, BLOCK_HASH_GINDEX))
                    + list(pre.execution_branch),
                    EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
                )
            ),
        )

    return LightClientHeader(
        beacon=pre.beacon,
        execution_block_hash=Hash32(),
        execution_branch=ExecutionBranch(),
    )


def upgrade_lc_bootstrap_to_gloas(pre: electra.LightClientBootstrap) -> LightClientBootstrap:
    return LightClientBootstrap(
        header=upgrade_lc_header_to_gloas(pre.header),
        current_sync_committee=pre.current_sync_committee,
        current_sync_committee_branch=CurrentSyncCommitteeBranch(
            data=normalize_merkle_branch(
                pre.current_sync_committee_branch, CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS
            )
        ),
    )


def upgrade_lc_update_to_gloas(pre: electra.LightClientUpdate) -> LightClientUpdate:
    return LightClientUpdate(
        attested_header=upgrade_lc_header_to_gloas(pre.attested_header),
        next_sync_committee=pre.next_sync_committee,
        next_sync_committee_branch=NextSyncCommitteeBranch(
            data=normalize_merkle_branch(
                pre.next_sync_committee_branch, NEXT_SYNC_COMMITTEE_GINDEX_GLOAS
            )
        ),
        finalized_header=upgrade_lc_header_to_gloas(pre.finalized_header),
        finality_branch=FinalityBranch(
            data=normalize_merkle_branch(pre.finality_branch, FINALIZED_ROOT_GINDEX_GLOAS)
        ),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )


def upgrade_lc_finality_update_to_gloas(
    pre: electra.LightClientFinalityUpdate,
) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=upgrade_lc_header_to_gloas(pre.attested_header),
        finalized_header=upgrade_lc_header_to_gloas(pre.finalized_header),
        finality_branch=FinalityBranch(
            data=normalize_merkle_branch(pre.finality_branch, FINALIZED_ROOT_GINDEX_GLOAS)
        ),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )


def upgrade_lc_optimistic_update_to_gloas(
    pre: electra.LightClientOptimisticUpdate,
) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=upgrade_lc_header_to_gloas(pre.attested_header),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )


def upgrade_lc_store_to_gloas(pre: electra.LightClientStore) -> LightClientStore:
    if pre.best_valid_update is None:
        best_valid_update = None
    else:
        best_valid_update = upgrade_lc_update_to_gloas(pre.best_valid_update)
    return LightClientStore(
        finalized_header=upgrade_lc_header_to_gloas(pre.finalized_header),
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        best_valid_update=best_valid_update,
        optimistic_header=upgrade_lc_header_to_gloas(pre.optimistic_header),
        previous_max_active_participants=pre.previous_max_active_participants,
        current_max_active_participants=pre.current_max_active_participants,
    )


def compute_max_partial_data_column_sidecar_size() -> Uint64:
    """
    Return the maximum size of a serialized ``PartialDataColumnSidecar``
    computed using the largest ``max_blobs_per_block`` value from the blob
    schedule, regardless of whether or not that is the current
    ``max_blobs_per_block``.
    """
    max_blobs = config.MAX_BLOBS_PER_BLOCK_ELECTRA
    for entry in config.BLOB_SCHEDULE:
        max_blobs = max(max_blobs, entry["MAX_BLOBS_PER_BLOCK"])

    sidecar = PartialDataColumnSidecar(
        cells_present_bitmap=CellsBitList(data=[Boolean()] * max_blobs),
        partial_column=DataColumn(data=[Cell()] * max_blobs),
        kzg_proofs=KZGProofs(data=[KZGProof()] * max_blobs),
    )
    return Uint64(len(ssz_serialize(sidecar)))


def process_validator_pq_registration_request(
    state: BeaconState, request: ValidatorPQRegistrationRequest
) -> None:
    # Verify the validator exists
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if request.validator_pubkey not in validator_pubkeys:
        return
    validator_index = ValidatorIndex(validator_pubkeys.index(request.validator_pubkey))
    validator = state.validators[validator_index]

    # Verify the request comes from the validator's withdrawal address
    has_correct_credential = has_execution_withdrawal_credential(validator)
    is_correct_source_address = validator.withdrawal_credentials[12:] == request.source_address
    if not (has_correct_credential and is_correct_source_address):
        return

    # Verify the XMSS public key is not already registered
    registered_xmss_pubkeys = [
        registration.pq_data[:32] for registration in state.validator_pq_registrations
    ]
    if request.pq_data[:32] in registered_xmss_pubkeys:
        return

    # Verify the VRF data is not already registered
    registered_vrf_data = [
        registration.pq_data[32:] for registration in state.validator_pq_registrations
    ]
    if request.pq_data[32:] in registered_vrf_data:
        return

    # Overwrite an existing registration for this validator
    for registration in state.validator_pq_registrations:
        if registration.validator_index == validator_index:
            registration.pq_data = request.pq_data
            return

    # Otherwise append a new registration
    state.validator_pq_registrations.append(
        ValidatorPQRegistration(validator_index=validator_index, pq_data=request.pq_data)
    )


def process_builder_pq_registration_request(
    state: BeaconState, request: BuilderPQRegistrationRequest
) -> None:
    # Verify the builder exists
    builder_pubkeys = [builder.pubkey for builder in state.builders]
    if request.builder_pubkey not in builder_pubkeys:
        return
    builder = state.builders[builder_pubkeys.index(request.builder_pubkey)]

    # Verify the request comes from the builder's execution address
    if builder.execution_address != request.source_address:
        return

    # Verify the XMSS public key is not already registered
    registered_xmss_pubkeys = [
        registration.pq_data for registration in state.builder_pq_registrations
    ]
    if request.pq_data in registered_xmss_pubkeys:
        return

    # Overwrite an existing registration for this builder
    for registration in state.builder_pq_registrations:
        if registration.builder_pubkey == request.builder_pubkey:
            registration.pq_data = request.pq_data
            return

    # Otherwise append a new registration
    state.builder_pq_registrations.append(
        BuilderPQRegistration(builder_pubkey=request.builder_pubkey, pq_data=request.pq_data)
    )


def upgrade_to_prereg(pre: gloas.BeaconState) -> BeaconState:
    epoch = gloas.get_current_epoch(pre)

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [Modified in Prereg]
            current_version=config.PREREG_FORK_VERSION,
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
        latest_block_hash=pre.latest_block_hash,
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        historical_summaries=pre.historical_summaries,
        deposit_requests_start_index=pre.deposit_requests_start_index,
        deposit_balance_to_consume=pre.deposit_balance_to_consume,
        exit_balance_to_consume=pre.exit_balance_to_consume,
        earliest_exit_epoch=pre.earliest_exit_epoch,
        consolidation_balance_to_consume=pre.consolidation_balance_to_consume,
        earliest_consolidation_epoch=pre.earliest_consolidation_epoch,
        pending_deposits=pre.pending_deposits,
        pending_partial_withdrawals=pre.pending_partial_withdrawals,
        pending_consolidations=pre.pending_consolidations,
        proposer_lookahead=pre.proposer_lookahead,
        builders=pre.builders,
        next_withdrawal_builder_index=pre.next_withdrawal_builder_index,
        execution_payload_availability=pre.execution_payload_availability,
        builder_pending_payments=pre.builder_pending_payments,
        builder_pending_withdrawals=pre.builder_pending_withdrawals,
        latest_execution_payload_bid=pre.latest_execution_payload_bid,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
        ptc_window=pre.ptc_window,
        # [New in Prereg]
        validator_pq_registrations=ValidatorPQRegistrations(),
        # [New in Prereg]
        builder_pq_registrations=BuilderPQRegistrations(),
    )

    return post


def get_eth1_data(block: Eth1Block) -> Eth1Data:
    """
    A stub function return mocking Eth1Data.
    """
    return Eth1Data(
        deposit_root=block.deposit_root,
        deposit_count=block.deposit_count,
        block_hash=Hash32(hash_tree_root(block)),
    )


def get_root_confirmed_before_restart() -> Root:
    return Root()


def cache_this(key_fn, value_fn, lru_size):
    cache_dict = LRU(size=lru_size)

    def wrapper(*args, **kw):
        key = key_fn(*args, **kw)
        if key not in cache_dict:
            cache_dict[key] = value_fn(*args, **kw)
        return cache_dict[key]

    return wrapper


_compute_shuffled_permutation = compute_shuffled_permutation
compute_shuffled_permutation = cache_this(
    lambda index_count, seed: (index_count, seed), _compute_shuffled_permutation, lru_size=256
)

_get_total_active_balance = get_total_active_balance
get_total_active_balance = cache_this(
    lambda state: (state.validators.hash_tree_root(), compute_epoch_at_slot(state.slot)),
    _get_total_active_balance,
    lru_size=10,
)

_get_base_reward = get_base_reward
get_base_reward = cache_this(
    lambda state, index, *args: (state.validators.hash_tree_root(), state.slot, index, *args),
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


def compute_merkle_proof(object: SSZObject, index: GeneralizedIndex) -> list[Bytes32]:
    return [Bytes32(chunk) for chunk in build_proof(object, index)]


ExecutionState = Any


def get_pow_block(hash: Hash32) -> PowBlock | None:
    return PowBlock(block_hash=hash, parent_hash=Hash32(), total_difficulty=Uint256(0))


def validator_is_connected(validator_index: ValidatorIndex) -> bool:
    return True


def retrieve_blobs_and_proofs(beacon_block_root: Root) -> tuple[Sequence[Blob], Sequence[KZGProof]]:
    return [], []


def retrieve_column_sidecars(beacon_block_root: Root) -> Sequence[DataColumnSidecar]:
    return []


def retrieve_column_sidecars_and_kzg_commitments(
    beacon_block_root: Root,
) -> tuple[Sequence[DataColumnSidecar], BlobKZGCommitments]:
    return [], BlobKZGCommitments()


_get_parent_payload_status = get_parent_payload_status
get_parent_payload_status = cache_this(
    lambda store, block: block.hash_tree_root(), _get_parent_payload_status, lru_size=1024
)

_compute_balance_weighted_selection = compute_balance_weighted_selection
compute_balance_weighted_selection = cache_this(
    lambda state, indices, seed, size, shuffle_indices: (
        state.validators.hash_tree_root(),
        tuple(indices),
        seed,
        size,
        shuffle_indices,
    ),
    _compute_balance_weighted_selection,
    lru_size=SLOTS_PER_EPOCH * 6,
)


class NoopExecutionEngine(ExecutionEngine):
    def notify_new_payload(
        self: ExecutionEngine,
        execution_payload: ExecutionPayload,
        parent_beacon_block_root: Root,
        execution_requests_list: Sequence[bytes],
    ) -> bool:
        return True

    def notify_forkchoice_updated(
        self: ExecutionEngine,
        head_block_hash: Hash32,
        safe_block_hash: Hash32,
        finalized_block_hash: Hash32,
        payload_attributes: PayloadAttributes | None,
        custody_columns: CustodyColumnBits | None,
    ) -> PayloadId | None:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        raise NotImplementedError("no default block production")

    def is_valid_block_hash(
        self: ExecutionEngine,
        execution_payload: ExecutionPayload,
        parent_beacon_block_root: Root,
        execution_requests_list: Sequence[bytes],
    ) -> bool:
        return True

    def is_valid_versioned_hashes(
        self: ExecutionEngine, new_payload_request: NewPayloadRequest
    ) -> bool:
        return True

    def verify_and_notify_new_payload(
        self: ExecutionEngine, new_payload_request: NewPayloadRequest
    ) -> bool:
        return True


EXECUTION_ENGINE = NoopExecutionEngine()


assert FINALIZED_ROOT_GINDEX == get_generalized_index(
    altair.BeaconState, "finalized_checkpoint", "root"
)
assert CURRENT_SYNC_COMMITTEE_GINDEX == get_generalized_index(
    altair.BeaconState, "current_sync_committee"
)
assert NEXT_SYNC_COMMITTEE_GINDEX == get_generalized_index(
    altair.BeaconState, "next_sync_committee"
)
assert EXECUTION_PAYLOAD_GINDEX == get_generalized_index(
    capella.BeaconBlockBody, "execution_payload"
)
assert FINALIZED_ROOT_GINDEX_ELECTRA == get_generalized_index(
    electra.BeaconState, "finalized_checkpoint", "root"
)
assert CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA == get_generalized_index(
    electra.BeaconState, "current_sync_committee"
)
assert NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA == get_generalized_index(
    electra.BeaconState, "next_sync_committee"
)
assert FINALIZED_ROOT_GINDEX_GLOAS == get_generalized_index(
    BeaconState, "finalized_checkpoint", "root"
)
assert CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS == get_generalized_index(
    BeaconState, "current_sync_committee"
)
assert NEXT_SYNC_COMMITTEE_GINDEX_GLOAS == get_generalized_index(BeaconState, "next_sync_committee")
assert EXECUTION_BLOCK_HASH_GINDEX == get_generalized_index(
    capella.BeaconBlockBody, "execution_payload", "block_hash"
)
assert EXECUTION_BLOCK_HASH_GINDEX_DENEB == get_generalized_index(
    deneb.BeaconBlockBody, "execution_payload", "block_hash"
)
assert EXECUTION_BLOCK_HASH_GINDEX_GLOAS == get_generalized_index(
    BeaconBlockBody, "signed_execution_payload_bid", "message", "parent_block_hash"
)
