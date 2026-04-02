from ..constants import PHASE0
from .base import BaseSpecBuilder


class Phase0SpecBuilder(BaseSpecBuilder):
    fork: str = PHASE0

    @classmethod
    def classes(cls) -> str:
        return """
class GossipIgnore(Exception):
    pass


class GossipReject(Exception):
    pass
"""

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return """from lru import LRU
from collections import defaultdict
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any, Callable, Dict, DefaultDict, Set, Sequence, Tuple, Optional, TypeAlias, TypeVar, NamedTuple, Final
)

from eth_consensus_specs.utils.ssz.ssz_impl import hash_tree_root, copy, uint_to_bytes
from eth_consensus_specs.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64, uint256,
    Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist)
from eth_consensus_specs.utils.ssz.ssz_typing import Bitvector  # noqa: F401
from eth_consensus_specs.utils import bls
from eth_consensus_specs.utils.hash_function import hash
"""

    @classmethod
    def preparations(cls) -> str:
        return """
SSZObject = TypeVar('SSZObject', bound=View)
"""

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
        if key not in cache_dict:
            cache_dict[key] = value_fn(*args, **kw)
        return cache_dict[key]
    return wrapper


_htr_cache: LRU = LRU(size=128)

def _cached_htr(obj: Any) -> Root:
    backing = obj.get_backing()
    key = id(backing)
    if key in _htr_cache:
        cached_backing, root = _htr_cache[key]
        if cached_backing is backing:
            return root
    root = obj.hash_tree_root()
    _htr_cache[key] = (backing, root)
    return root


_compute_shuffled_index = compute_shuffled_index

def _fast_compute_shuffled_index(index: int, index_count: int, seed: bytes) -> uint64:
    assert index < index_count
    index = int(index)
    index_count = int(index_count)
    seed = bytes(seed)
    for current_round in range(SHUFFLE_ROUND_COUNT):
        pivot_hash = hash(seed + uint_to_bytes(uint8(current_round)))
        pivot = int.from_bytes(pivot_hash[:8], 'little') % index_count
        flip = (pivot + index_count - index) % index_count
        position = max(index, flip)
        source = hash(seed + uint_to_bytes(uint8(current_round)) + uint_to_bytes(uint32(position // 256)))
        byte = source[(position % 256) // 8]
        bit = (byte >> (position % 8)) % 2
        if bit:
            index = flip
    return uint64(index)

compute_shuffled_index = cache_this(
    lambda index, index_count, seed: (int(index), int(index_count), bytes(seed)),
    _fast_compute_shuffled_index, lru_size=2**10)

_get_total_active_balance = get_total_active_balance
get_total_active_balance = cache_this(
    lambda state: (_cached_htr(state.validators), compute_epoch_at_slot(state.slot)),
    _get_total_active_balance, lru_size=10)

_get_base_reward = get_base_reward
get_base_reward = cache_this(
    lambda state, index: (_cached_htr(state.validators), state.slot, index),
    _get_base_reward, lru_size=2048)

_get_committee_count_per_slot = get_committee_count_per_slot
get_committee_count_per_slot = cache_this(
    lambda state, epoch: (_cached_htr(state.validators), epoch),
    _get_committee_count_per_slot, lru_size=SLOTS_PER_EPOCH * 3)

_get_active_validator_indices = get_active_validator_indices
get_active_validator_indices = cache_this(
    lambda state, epoch: (_cached_htr(state.validators), epoch),
    _get_active_validator_indices, lru_size=3)

_get_beacon_committee = get_beacon_committee
get_beacon_committee = cache_this(
    lambda state, slot, index: (_cached_htr(state.validators), _cached_htr(state.randao_mixes), slot, index),
    _get_beacon_committee, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)

_get_matching_target_attestations = get_matching_target_attestations
get_matching_target_attestations = cache_this(
    lambda state, epoch: (_cached_htr(state), epoch),
    _get_matching_target_attestations, lru_size=10)

_get_matching_head_attestations = get_matching_head_attestations
get_matching_head_attestations = cache_this(
    lambda state, epoch: (_cached_htr(state), epoch),
    _get_matching_head_attestations, lru_size=10)

_get_attesting_indices = get_attesting_indices
get_attesting_indices = cache_this(
    lambda state, attestation: (
        _cached_htr(state.randao_mixes),
        _cached_htr(state.validators), _cached_htr(attestation)
    ),
    _get_attesting_indices, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)'''
