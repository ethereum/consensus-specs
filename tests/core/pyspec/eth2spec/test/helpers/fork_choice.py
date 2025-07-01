from collections.abc import Sequence
from typing import Any, NamedTuple

from eth_utils import encode_hex

from eth2spec.fulu.mainnet import DataColumnSidecar
from eth2spec.test.exceptions import BlockNotFoundException
from eth2spec.test.helpers.attestations import (
    next_epoch_with_attestations,
    next_slots_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.forks import is_post_eip7732, is_post_fulu
from eth2spec.test.helpers.state import (
    payload_state_transition,
    payload_state_transition_no_store,
)


def check_head_against_root(spec, store, root):
    head = spec.get_head(store)
    if is_post_eip7732(spec):
        assert head.root == root
    else:
        assert head == root


class BlobData(NamedTuple):
    """
    The return values of ``retrieve_blobs_and_proofs`` helper.
    """

    blobs: Sequence[Any] | None = None
    proofs: Sequence[bytes] | None = None
    sidecars: Sequence[DataColumnSidecar] | None = None

    def is_post_fulu(self):
        return self.sidecars is not None and self.blobs is None and self.proofs is None

    def is_pre_fulu(self):
        return self.blobs is not None and self.proofs is not None and self.sidecars is None


def with_blob_data(spec, blob_data: BlobData, func):
    if not is_post_fulu(spec):
        if blob_data.proofs is None:
            raise ValueError("blob_data.proofs must be provided when pre FULU fork")
        yield from with_blob_data_deneb(spec, blob_data, func)
    else:
        if blob_data.sidecars is None:
            raise ValueError("blob_data.sidecars must be provided when post FULU fork")
        yield from with_blob_data_fulu(spec, blob_data, func)


def with_blob_data_deneb(spec, blob_data: BlobData, func):
    """
    This helper runs the given ``func`` with monkeypatched ``retrieve_blobs_and_proofs``
    that returns ``blob_data.blobs, blob_data.proofs``.
    """

    def retrieve_blobs_and_proofs(_):
        assert blob_data.proofs is not None, "blob_data.proofs must be provided"
        return blob_data.blobs, blob_data.proofs

    retrieve_blobs_and_proofs_backup = spec.retrieve_blobs_and_proofs
    spec.retrieve_blobs_and_proofs = retrieve_blobs_and_proofs

    class AtomicBoolean:
        value = False

    is_called = AtomicBoolean()

    def wrap(flag: AtomicBoolean):
        yield from func()
        flag.value = True

    try:
        yield from wrap(is_called)
    finally:
        spec.retrieve_blobs_and_proofs = retrieve_blobs_and_proofs_backup
    assert is_called.value


def with_blob_data_fulu(spec, blob_data: BlobData, func):
    """
    This helper runs the given ``func`` with monkeypatched ``retrieve_column_sidecars``
    that returns ``blob_data``.
    """

    def retrieve_column_sidecars(_):
        assert blob_data.sidecars is not None, "blob_data.sidecars must be provided"
        if len(blob_data.sidecars) == 0:
            assert False, "Simulation: not all required columns have been sampled"
        return blob_data.sidecars

    retrieve_column_sidecars_backup = spec.retrieve_column_sidecars
    spec.retrieve_column_sidecars = retrieve_column_sidecars

    class AtomicBoolean:
        value = False

    is_called = AtomicBoolean()

    def wrap(flag: AtomicBoolean):
        yield from func()
        flag.value = True

    try:
        yield from wrap(is_called)
    finally:
        spec.retrieve_column_sidecars = retrieve_column_sidecars_backup
    assert is_called.value


def get_anchor_root(spec, state):
    anchor_block_header = state.latest_block_header.copy()
    if anchor_block_header.state_root == spec.Bytes32():
        anchor_block_header.state_root = spec.hash_tree_root(state)
    return spec.hash_tree_root(anchor_block_header)


def tick_and_add_block(
    spec,
    store,
    signed_block,
    test_steps,
    valid=True,
    merge_block=False,
    block_not_found=False,
    is_optimistic=False,
    blob_data: BlobData | None = None,
):
    pre_state = get_store_full_state(spec, store, signed_block.message.parent_root)
    if merge_block:
        assert spec.is_merge_transition_block(pre_state, signed_block.message.body)

    block_time = pre_state.genesis_time + signed_block.message.slot * spec.config.SECONDS_PER_SLOT
    while store.time < block_time:
        time = (
            pre_state.genesis_time
            + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        )
        on_tick_and_append_step(spec, store, time, test_steps)

    post_state = yield from add_block(
        spec,
        store,
        signed_block,
        test_steps,
        valid=valid,
        block_not_found=block_not_found,
        is_optimistic=is_optimistic,
        blob_data=blob_data,
    )

    return post_state


def tick_and_add_block_with_data(spec, store, signed_block, test_steps, blob_data, valid=True):
    def run_func():
        yield from tick_and_add_block(
            spec, store, signed_block, test_steps, blob_data=blob_data, valid=valid
        )

    yield from with_blob_data(spec, blob_data, run_func)


def add_attestation(spec, store, attestation, test_steps, is_from_block=False, valid=True):
    run_on_attestation(spec, store, attestation, is_from_block=is_from_block, valid=valid)
    yield get_attestation_file_name(attestation), attestation
    if valid:
        test_steps.append({"attestation": get_attestation_file_name(attestation)})
    else:
        test_steps.append({"attestation": get_attestation_file_name(attestation), "valid": False})


def add_attestations(spec, store, attestations, test_steps, is_from_block=False):
    for attestation in attestations:
        yield from add_attestation(
            spec, store, attestation, test_steps, is_from_block=is_from_block
        )


def tick_and_run_on_attestation(spec, store, attestation, test_steps, is_from_block=False):
    # Make get_current_slot(store) >= attestation.data.slot + 1
    min_time_to_include = (attestation.data.slot + 1) * spec.config.SECONDS_PER_SLOT
    if store.time < min_time_to_include:
        spec.on_tick(store, min_time_to_include)
        test_steps.append({"tick": int(min_time_to_include)})

    yield from add_attestation(spec, store, attestation, test_steps, is_from_block)


def run_on_attestation(spec, store, attestation, is_from_block=False, valid=True):
    if not valid:
        try:
            spec.on_attestation(store, attestation, is_from_block=is_from_block)
        except AssertionError:
            return
        else:
            assert False

    spec.on_attestation(store, attestation, is_from_block=is_from_block)


def get_genesis_forkchoice_store(spec, genesis_state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, genesis_state)
    return store


def get_genesis_forkchoice_store_and_block(spec, genesis_state):
    assert genesis_state.slot == spec.GENESIS_SLOT
    genesis_block = spec.BeaconBlock(state_root=genesis_state.hash_tree_root())
    if is_post_eip7732(spec):
        genesis_block.body.signed_execution_payload_header.message.block_hash = (
            genesis_state.latest_block_hash
        )
    store = spec.get_forkchoice_store(genesis_state, genesis_block)
    if is_post_eip7732(spec):
        store.execution_payload_states = store.block_states.copy()
    return store, genesis_block


def get_block_file_name(block):
    return f"block_{encode_hex(block.hash_tree_root())}"


def get_attestation_file_name(attestation):
    return f"attestation_{encode_hex(attestation.hash_tree_root())}"


def get_attester_slashing_file_name(attester_slashing):
    return f"attester_slashing_{encode_hex(attester_slashing.hash_tree_root())}"


def get_blobs_file_name(blobs=None, blobs_root=None):
    if blobs:
        return f"blobs_{encode_hex(blobs.hash_tree_root())}"
    else:
        return f"blobs_{encode_hex(blobs_root)}"


def get_sidecars_file_names(sidecars: Sequence[DataColumnSidecar]) -> Sequence[str]:
    """
    Returns the file names for sidecars.
    """
    return [get_sidecar_file_name(sidecar) for sidecar in sidecars]


def get_sidecar_file_name(sidecar: DataColumnSidecar) -> str:
    """
    Returns the file name for a single sidecar.
    """
    return f"column_{encode_hex(sidecar.hash_tree_root())}"


def on_tick_and_append_step(spec, store, time, test_steps):
    assert time >= store.time
    spec.on_tick(store, time)
    test_steps.append({"tick": int(time)})
    output_store_checks(spec, store, test_steps)


def run_on_block(spec, store, signed_block, valid=True):
    if not valid:
        try:
            spec.on_block(store, signed_block)
        except AssertionError:
            return
        else:
            assert False

    spec.on_block(store, signed_block)
    root = signed_block.message.hash_tree_root()
    assert store.blocks[root] == signed_block.message


def get_store_full_state(spec, store, root):
    if is_post_eip7732(spec):
        return store.execution_payload_states[root]
    return store.block_states[root]


def add_block(
    spec,
    store,
    signed_block,
    test_steps,
    valid=True,
    block_not_found=False,
    is_optimistic=False,
    blob_data=None,
):
    """
    Run on_block and on_attestation
    """
    yield get_block_file_name(signed_block), signed_block

    # Check blob_data
    if blob_data is not None:
        assert blob_data.is_pre_fulu() or blob_data.is_post_fulu(), "Integrity fail blob_data"

        if blob_data.is_pre_fulu():
            blobs = spec.List[spec.Blob, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](blob_data.blobs)
            blobs_root = blobs.hash_tree_root()
            yield get_blobs_file_name(blobs_root=blobs_root), blobs

        if blob_data.is_post_fulu():
            for sidecar in blob_data.sidecars:
                yield get_sidecar_file_name(sidecar), sidecar

    def _append_step(valid=True):
        if blob_data is not None:
            if blob_data.is_post_fulu():
                step = {
                    "block": get_block_file_name(signed_block),
                    "columns": get_sidecars_file_names(blob_data.sidecars),
                    "valid": valid,
                }
            if blob_data.is_pre_fulu():
                step = {
                    "block": get_block_file_name(signed_block),
                    "blobs": get_blobs_file_name(blobs_root=blobs_root),
                    "proofs": [encode_hex(proof) for proof in blob_data.proofs],
                    "valid": valid,
                }

            test_steps.append(step)
        else:
            test_steps.append(
                {
                    "block": get_block_file_name(signed_block),
                    "valid": valid,
                }
            )

    if not valid:
        if is_optimistic:
            run_on_block(spec, store, signed_block, valid=True)
            _append_step(valid=False)
        else:
            try:
                run_on_block(spec, store, signed_block, valid=True)
            except (AssertionError, BlockNotFoundException) as e:
                if isinstance(e, BlockNotFoundException) and not block_not_found:
                    assert False
                _append_step(valid=False)
                return
            else:
                assert False
    else:
        run_on_block(spec, store, signed_block, valid=True)
        _append_step()

    # An on_block step implies receiving block's attestations
    for attestation in signed_block.message.body.attestations:
        run_on_attestation(spec, store, attestation, is_from_block=True, valid=True)

    # An on_block step implies receiving block's attester slashings
    for attester_slashing in signed_block.message.body.attester_slashings:
        run_on_attester_slashing(spec, store, attester_slashing, valid=True)

    block_root = signed_block.message.hash_tree_root()
    assert store.blocks[block_root] == signed_block.message
    assert store.block_states[block_root].hash_tree_root() == signed_block.message.state_root
    if not is_optimistic:
        output_store_checks(spec, store, test_steps)

    return store.block_states[signed_block.message.hash_tree_root()]


def run_on_attester_slashing(spec, store, attester_slashing, valid=True):
    if not valid:
        try:
            spec.on_attester_slashing(store, attester_slashing)
        except AssertionError:
            return
        else:
            assert False

    spec.on_attester_slashing(store, attester_slashing)


def add_attester_slashing(spec, store, attester_slashing, test_steps, valid=True):
    slashing_file_name = get_attester_slashing_file_name(attester_slashing)
    yield get_attester_slashing_file_name(attester_slashing), attester_slashing

    if not valid:
        try:
            run_on_attester_slashing(spec, store, attester_slashing)
        except AssertionError:
            test_steps.append(
                {
                    "attester_slashing": slashing_file_name,
                    "valid": False,
                }
            )
            return
        else:
            assert False

    run_on_attester_slashing(spec, store, attester_slashing)
    test_steps.append({"attester_slashing": slashing_file_name})


def get_formatted_head_output(spec, store):
    head = spec.get_head(store)
    if is_post_eip7732(spec):
        return {
            "slot": int(head.slot),
            "root": encode_hex(head.root),
        }

    slot = store.blocks[head].slot
    return {
        "slot": int(slot),
        "root": encode_hex(head),
    }


def output_head_check(spec, store, test_steps):
    test_steps.append(
        {
            "checks": {
                "head": get_formatted_head_output(spec, store),
            }
        }
    )


def output_store_checks(spec, store, test_steps, with_viable_for_head_weights=False):
    checks = {
        "time": int(store.time),
        "head": get_formatted_head_output(spec, store),
        "justified_checkpoint": {
            "epoch": int(store.justified_checkpoint.epoch),
            "root": encode_hex(store.justified_checkpoint.root),
        },
        "finalized_checkpoint": {
            "epoch": int(store.finalized_checkpoint.epoch),
            "root": encode_hex(store.finalized_checkpoint.root),
        },
        "proposer_boost_root": encode_hex(store.proposer_boost_root),
    }

    if with_viable_for_head_weights:
        filtered_block_roots = spec.get_filtered_block_tree(store).keys()
        leaves_viable_for_head = [
            root
            for root in filtered_block_roots
            if not any(c for c in filtered_block_roots if store.blocks[c].parent_root == root)
        ]

        viable_for_head_roots_and_weights = [
            {
                "root": encode_hex(viable_for_head_root),
                "weight": int(spec.get_weight(store, viable_for_head_root)),
            }
            for viable_for_head_root in leaves_viable_for_head
        ]
        checks["viable_for_head_roots_and_weights"] = viable_for_head_roots_and_weights

    test_steps.append({"checks": checks})


def apply_next_epoch_with_attestations(
    spec, state, store, fill_cur_epoch, fill_prev_epoch, participation_fn=None, test_steps=None
):
    if test_steps is None:
        test_steps = []

    _, new_signed_blocks, post_state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn
    )
    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    if is_post_eip7732(spec):
        assert (
            store.execution_payload_states[block_root].hash_tree_root()
            == post_state.hash_tree_root()
        )
    else:
        assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block


def apply_next_slots_with_attestations(
    spec, state, store, slots, fill_cur_epoch, fill_prev_epoch, test_steps, participation_fn=None
):
    _, new_signed_blocks, post_state = next_slots_with_attestations(
        spec, state, slots, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn
    )
    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    if is_post_eip7732(spec):
        assert (
            store.execution_payload_states[block_root].hash_tree_root()
            == post_state.hash_tree_root()
        )
    else:
        assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block


def is_ready_to_justify(spec, state):
    """
    Check if the given ``state`` will trigger justification updates at epoch boundary.
    """
    temp_state = state.copy()
    spec.process_justification_and_finalization(temp_state)
    return temp_state.current_justified_checkpoint.epoch > state.current_justified_checkpoint.epoch


def find_next_justifying_slot(spec, state, fill_cur_epoch, fill_prev_epoch, participation_fn=None):
    temp_state = state.copy()

    signed_blocks = []
    justifying_slot = None
    while justifying_slot is None:
        signed_block = state_transition_with_full_block(
            spec,
            temp_state,
            fill_cur_epoch,
            fill_prev_epoch,
            participation_fn,
        )
        signed_blocks.append(signed_block)
        payload_state_transition_no_store(spec, temp_state, signed_block.message)

        if is_ready_to_justify(spec, temp_state):
            justifying_slot = temp_state.slot

    return signed_blocks, justifying_slot


def get_pow_block_file_name(pow_block):
    return f"pow_block_{encode_hex(pow_block.block_hash)}"


def add_pow_block(spec, store, pow_block, test_steps):
    yield get_pow_block_file_name(pow_block), pow_block
    test_steps.append({"pow_block": get_pow_block_file_name(pow_block)})
