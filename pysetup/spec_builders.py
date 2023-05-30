from abc import ABC, abstractmethod
from typing import Dict, List, Sequence
from pathlib import Path

from .constants import (
    PHASE0,
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    EIP6110,
    OPTIMIZED_BLS_AGGREGATE_PUBKEYS,
)


class SpecBuilder(ABC):
    @property
    @abstractmethod
    def fork(self) -> str:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def imports(cls, preset_name: str) -> str:
        """
        Import objects from other libraries.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def preparations(cls) -> str:
        """
        Define special types/constants for building pyspec or call functions.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def sundry_functions(cls) -> str:
        """
        The functions that are (1) defined abstractly in specs or (2) adjusted for getting better performance.
        """
        raise NotImplementedError()

    @classmethod
    def execution_engine_cls(cls) -> str:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        """
        The constants that are required for SSZ objects.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:  # TODO
        """
        The constants that are required for custom types.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def build_spec(cls, preset_name: str,
                   source_files: List[Path], preset_files: Sequence[Path], config_file: Path) -> str:
        raise NotImplementedError()


#
# Phase0SpecBuilder
#
class Phase0SpecBuilder(SpecBuilder):
    fork: str = PHASE0

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return '''from lru import LRU
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any, Callable, Dict, Set, Sequence, Tuple, Optional, TypeVar, NamedTuple, Final
)

from eth2spec.utils.ssz.ssz_impl import hash_tree_root, copy, uint_to_bytes
from eth2spec.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64, uint256,
    Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist)
from eth2spec.utils.ssz.ssz_typing import Bitvector  # noqa: F401
from eth2spec.utils import bls
from eth2spec.utils.hash_function import hash
'''

    @classmethod
    def preparations(cls) -> str:
        return  '''
SSZObject = TypeVar('SSZObject', bound=View)
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return '''
def get_eth1_data(block: Eth1Block) -> Eth1Data:
    """
    A stub function return mocking Eth1Data.
    """
    return Eth1Data(
        deposit_root=block.deposit_root,
        deposit_count=block.deposit_count,
        block_hash=hash_tree_root(block))


def cache_this(key_fn, value_fn, lru_size):  # type: ignore
    cache_dict = LRU(size=lru_size)

    def wrapper(*args, **kw):  # type: ignore
        key = key_fn(*args, **kw)
        nonlocal cache_dict
        if key not in cache_dict:
            cache_dict[key] = value_fn(*args, **kw)
        return cache_dict[key]
    return wrapper


_compute_shuffled_index = compute_shuffled_index
compute_shuffled_index = cache_this(
    lambda index, index_count, seed: (index, index_count, seed),
    _compute_shuffled_index, lru_size=SLOTS_PER_EPOCH * 3)

_get_total_active_balance = get_total_active_balance
get_total_active_balance = cache_this(
    lambda state: (state.validators.hash_tree_root(), compute_epoch_at_slot(state.slot)),
    _get_total_active_balance, lru_size=10)

_get_base_reward = get_base_reward
get_base_reward = cache_this(
    lambda state, index: (state.validators.hash_tree_root(), state.slot, index),
    _get_base_reward, lru_size=2048)

_get_committee_count_per_slot = get_committee_count_per_slot
get_committee_count_per_slot = cache_this(
    lambda state, epoch: (state.validators.hash_tree_root(), epoch),
    _get_committee_count_per_slot, lru_size=SLOTS_PER_EPOCH * 3)

_get_active_validator_indices = get_active_validator_indices
get_active_validator_indices = cache_this(
    lambda state, epoch: (state.validators.hash_tree_root(), epoch),
    _get_active_validator_indices, lru_size=3)

_get_beacon_committee = get_beacon_committee
get_beacon_committee = cache_this(
    lambda state, slot, index: (state.validators.hash_tree_root(), state.randao_mixes.hash_tree_root(), slot, index),
    _get_beacon_committee, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)

_get_matching_target_attestations = get_matching_target_attestations
get_matching_target_attestations = cache_this(
    lambda state, epoch: (state.hash_tree_root(), epoch),
    _get_matching_target_attestations, lru_size=10)

_get_matching_head_attestations = get_matching_head_attestations
get_matching_head_attestations = cache_this(
    lambda state, epoch: (state.hash_tree_root(), epoch),
    _get_matching_head_attestations, lru_size=10)

_get_attesting_indices = get_attesting_indices
get_attesting_indices = cache_this(
    lambda state, data, bits: (
        state.randao_mixes.hash_tree_root(),
        state.validators.hash_tree_root(), data.hash_tree_root(), bits.hash_tree_root()
    ),
    _get_attesting_indices, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)'''


    @classmethod
    def execution_engine_cls(cls) -> str:
        return ""


    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        return {}

    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:
        return {}

    @classmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        return functions


# AltairSpecBuilder
#
class AltairSpecBuilder(Phase0SpecBuilder):
    fork: str = ALTAIR

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return super().imports(preset_name) + '\n' + f'''
from typing import NewType, Union as PyUnion

from eth2spec.phase0 import {preset_name} as phase0
from eth2spec.test.helpers.merkle import build_proof
from eth2spec.utils.ssz.ssz_typing import Path
'''

    @classmethod
    def preparations(cls):
        return super().preparations() + '\n' + '''
SSZVariableName = str
GeneralizedIndex = NewType('GeneralizedIndex', int)
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + '''
def get_generalized_index(ssz_class: Any, *path: Sequence[PyUnion[int, SSZVariableName]]) -> GeneralizedIndex:
    ssz_path = Path(ssz_class)
    for item in path:
        ssz_path = ssz_path / item
    return GeneralizedIndex(ssz_path.gindex())


def compute_merkle_proof_for_state(state: BeaconState,
                                   index: GeneralizedIndex) -> Sequence[Bytes32]:
    return build_proof(state.get_backing(), index)'''


    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        constants = {
            'FINALIZED_ROOT_INDEX': 'GeneralizedIndex(105)',
            'CURRENT_SYNC_COMMITTEE_INDEX': 'GeneralizedIndex(54)',
            'NEXT_SYNC_COMMITTEE_INDEX': 'GeneralizedIndex(55)',
        }
        return {**super().hardcoded_ssz_dep_constants(), **constants}

    @classmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        if "eth_aggregate_pubkeys" in functions:
            functions["eth_aggregate_pubkeys"] = OPTIMIZED_BLS_AGGREGATE_PUBKEYS.strip()
        return super().implement_optimizations(functions)

#
# BellatrixSpecBuilder
#
class BellatrixSpecBuilder(AltairSpecBuilder):
    fork: str = BELLATRIX

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from typing import Protocol
from eth2spec.altair import {preset_name} as altair
from eth2spec.utils.ssz.ssz_typing import Bytes8, Bytes20, ByteList, ByteVector
'''

    @classmethod
    def preparations(cls):
        return super().preparations()

    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + """
ExecutionState = Any


def get_pow_block(hash: Bytes32) -> Optional[PowBlock]:
    return PowBlock(block_hash=hash, parent_hash=Bytes32(), total_difficulty=uint256(0))


def get_execution_state(_execution_state_root: Bytes32) -> ExecutionState:
    pass


def get_pow_chain_head() -> PowBlock:
    pass"""

    @classmethod
    def execution_engine_cls(cls) -> str:
        return "\n\n" + """
class NoopExecutionEngine(ExecutionEngine):

    def notify_new_payload(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
        return True

    def notify_forkchoice_updated(self: ExecutionEngine,
                                  head_block_hash: Hash32,
                                  safe_block_hash: Hash32,
                                  finalized_block_hash: Hash32,
                                  payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        # pylint: disable=unused-argument
        raise NotImplementedError("no default block production")

    def is_valid_block_hash(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
        return True

    def verify_and_notify_new_payload(self: ExecutionEngine,
                                      new_payload_request: NewPayloadRequest) -> bool:
        return True


EXECUTION_ENGINE = NoopExecutionEngine()"""


    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> str:
        constants = {
            'MAX_BYTES_PER_TRANSACTION': spec_object.preset_vars['MAX_BYTES_PER_TRANSACTION'].value,
        }
        return {**super().hardcoded_custom_type_dep_constants(spec_object), **constants}


#
# CapellaSpecBuilder
#
class CapellaSpecBuilder(BellatrixSpecBuilder):
    fork: str = CAPELLA

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from eth2spec.bellatrix import {preset_name} as bellatrix
'''


    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + '''
def compute_merkle_proof_for_block_body(body: BeaconBlockBody,
                                        index: GeneralizedIndex) -> Sequence[Bytes32]:
    return build_proof(body.get_backing(), index)'''


    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        constants = {
            'EXECUTION_PAYLOAD_INDEX': 'GeneralizedIndex(25)',
        }
        return {**super().hardcoded_ssz_dep_constants(), **constants}

#
# DenebSpecBuilder
#
class DenebSpecBuilder(CapellaSpecBuilder):
    fork: str = DENEB

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from eth2spec.capella import {preset_name} as capella
'''


    @classmethod
    def preparations(cls):
        return super().preparations() + '\n' + '''
T = TypeVar('T')  # For generic function
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + '''
def retrieve_blobs_and_proofs(beacon_block_root: Root) -> PyUnion[Tuple[Blob, KZGProof], Tuple[str, str]]:
    # pylint: disable=unused-argument
    return ("TEST", "TEST")'''

    @classmethod
    def execution_engine_cls(cls) -> str:
        return "\n\n" + """
class NoopExecutionEngine(ExecutionEngine):

    def notify_new_payload(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
        return True

    def notify_forkchoice_updated(self: ExecutionEngine,
                                  head_block_hash: Hash32,
                                  safe_block_hash: Hash32,
                                  finalized_block_hash: Hash32,
                                  payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        # pylint: disable=unused-argument
        raise NotImplementedError("no default block production")

    def is_valid_block_hash(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
        return True

    def is_valid_versioned_hashes(self: ExecutionEngine, new_payload_request: NewPayloadRequest) -> bool:
        return True

    def verify_and_notify_new_payload(self: ExecutionEngine,
                                      new_payload_request: NewPayloadRequest) -> bool:
        return True


EXECUTION_ENGINE = NoopExecutionEngine()"""


    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> str:
        constants = {
            'BYTES_PER_FIELD_ELEMENT': spec_object.constant_vars['BYTES_PER_FIELD_ELEMENT'].value,
            'FIELD_ELEMENTS_PER_BLOB': spec_object.preset_vars['FIELD_ELEMENTS_PER_BLOB'].value,
            'MAX_BLOBS_PER_BLOCK': spec_object.preset_vars['MAX_BLOBS_PER_BLOCK'].value,
        }
        return {**super().hardcoded_custom_type_dep_constants(spec_object), **constants}


#
# EIP6110SpecBuilder
#
class EIP6110SpecBuilder(DenebSpecBuilder):
    fork: str = EIP6110

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from eth2spec.deneb import {preset_name} as deneb
'''


spec_builders = {
    builder.fork: builder
    for builder in (
        Phase0SpecBuilder,
        AltairSpecBuilder,
        BellatrixSpecBuilder,
        CapellaSpecBuilder,
        DenebSpecBuilder,
        EIP6110SpecBuilder,
    )
}
