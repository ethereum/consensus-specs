from ..constants import PHASE0
from .base import BaseSpecBuilder


class Phase0SpecBuilder(BaseSpecBuilder):
    fork: str = PHASE0

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return """from lru import LRU
from collections import defaultdict
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any, Callable, Dict, DefaultDict, Set, Sequence, Tuple, Optional, TypeVar, NamedTuple, Final
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
    lambda state, attestation: (
        state.randao_mixes.hash_tree_root(),
        state.validators.hash_tree_root(), attestation.hash_tree_root()
    ),
    _get_attesting_indices, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)'''
