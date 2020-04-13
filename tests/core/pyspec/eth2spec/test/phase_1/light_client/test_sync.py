from eth2spec.test.context import PHASE0, spec_test, with_all_phases_except, single_phase
from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.utils import bls
from eth2spec.utils.hash_function import hash
from eth2spec.utils.merkle_minimal import zerohashes


def build_compact_committee_by_indices(spec, indices):
    _pubkeys = []
    compact_validators = []
    for i in indices:
        _pubkeys.append(pubkeys[i])
        compact_validators.append(
            spec.pack_compact_validator(i, False, spec.MAX_EFFECTIVE_BALANCE // spec.EFFECTIVE_BALANCE_INCREMENT)
        )
    return spec.CompactCommittee(pubkeys=_pubkeys, compact_validators=compact_validators)


def get_branch(shard_block_header):
    return [
        shard_block_header.shard_parent_root,
        hash(shard_block_header.slot.hash_tree_root() + shard_block_header.proposer_index.hash_tree_root()),
        hash(hash(shard_block_header.body_root.hash_tree_root() + zerohashes[0]) + zerohashes[1]),
    ]


@with_all_phases_except([PHASE0])
@spec_test
@single_phase
def test_update_memory(spec):
    # TODO: document for test format

    # Build LightClientMemory
    header_1 = spec.BeaconBlockHeader(
        slot=1024,
    )
    previous_committee = build_compact_committee_by_indices(spec, list(range(0, 4)))
    current_committee = build_compact_committee_by_indices(spec, list(range(4, 8)))
    next_committee = build_compact_committee_by_indices(spec, list(range(8, 12)))
    memory = spec.LightClientMemory(
        shard=1,
        header=header_1,
        previous_committee=previous_committee,
        current_committee=current_committee,
        next_committee=next_committee,
    )

    # Build LightClientUpdate
    header_2 = spec.BeaconBlockHeader(
        slot=1025,
    )
    header_2_root = header_2.hash_tree_root()
    shard_block_header = spec.ShardBlockHeader(
        beacon_parent_root=header_2_root,  # index = 1
    )
    shard_block_root = shard_block_header.hash_tree_root()
    branch = get_branch(shard_block_header)
    assert spec.is_valid_merkle_branch(
        leaf=header_2_root,
        branch=branch,
        depth=spec.BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_DEPTH,
        index=spec.BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_INDEX,
        root=shard_block_root,
    )

    fork_version = spec.PHASE_1_FORK_VERSION
    domain = spec.compute_domain(spec.DOMAIN_SHARD_COMMITTEE, fork_version)
    signing_root = spec.compute_signing_root(shard_block_header, domain)
    indices = []
    for compact_validator in current_committee.compact_validators:
        index, _, _ = spec.unpack_compact_validator(compact_validator)
        indices.append(index)
    signature = bls.Aggregate([bls.Sign(privkeys[i], signing_root) for i in indices])

    # TODO: Add test for new light client committee cases
    committee = spec.CompactCommittee()
    committee_branch = []
    aggregation_bits = b'1' * 4
    update = spec.LightClientUpdate(
        shard_block_root=shard_block_root,
        fork_version=fork_version,
        aggregation_bits=aggregation_bits,
        signature=signature,
        header=header_2,
        header_branch=branch,
        committee=committee,
        committee_branch=committee_branch,
    )
    shard_count = spec.INITIAL_ACTIVE_SHARDS

    yield 'pre_memory', memory
    yield 'update', update
    yield 'shard_count', shard_count

    spec.update_memory(memory, update, shard_count)

    assert memory.header == header_2

    yield 'post_memory', memory


@with_all_phases_except([PHASE0])
@spec_test
@single_phase
def test_pack_and_unpack(spec):
    index = 10
    slashed = False
    balance = spec.MAX_EFFECTIVE_BALANCE // spec.EFFECTIVE_BALANCE_INCREMENT
    compact_validator = spec.pack_compact_validator(index, slashed, balance)
    unpacked_index, unpacked_slashed, upbacked_balance = spec.unpack_compact_validator(compact_validator)
    assert unpacked_index == index
    assert unpacked_slashed == slashed
    assert upbacked_balance == balance
