from dataclasses import dataclass
from enum import Enum

from eth_utils import encode_hex

from eth_consensus_specs.test.helpers.fork_choice import (
    add_block,
    get_execution_payload_envelope_file_name,
)
from eth_consensus_specs.test.helpers.forks import (
    is_post_capella,
)
from eth_consensus_specs.utils.ssz.bytes import Bytes32


class PayloadStatusV1StatusAlias(Enum):
    NOT_VALIDATED = "NOT_VALIDATED"
    INVALIDATED = "INVALIDATED"


class PayloadStatusV1Status(Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    SYNCING = "SYNCING"
    ACCEPTED = "ACCEPTED"
    INVALID_BLOCK_HASH = "INVALID_BLOCK_HASH"

    @property
    def alias(self) -> PayloadStatusV1StatusAlias:
        if self.value in (self.SYNCING.value, self.ACCEPTED.value):
            return PayloadStatusV1StatusAlias.NOT_VALIDATED
        elif self.value in (self.INVALID.value, self.INVALID_BLOCK_HASH.value):
            return PayloadStatusV1StatusAlias.INVALIDATED


@dataclass
class PayloadStatusV1:
    status: PayloadStatusV1Status = PayloadStatusV1Status.VALID
    latest_valid_hash: Bytes32 | None = None
    validation_error: str | None = None

    @property
    def formatted_output(self):
        return {
            "status": str(self.status.value),
            "latest_valid_hash": (
                encode_hex(self.latest_valid_hash) if self.latest_valid_hash is not None else None
            ),
            "validation_error": (
                str(self.validation_error) if self.validation_error is not None else None
            ),
        }


class MegaStore:
    def __init__(self, spec, fc_store, opt_store):
        self.spec = spec
        self.fc_store = fc_store
        self.opt_store = opt_store
        self.block_payload_statuses: dict[Bytes32, PayloadStatusV1] = {}


def get_optimistic_store(spec, anchor_state, anchor_block):
    assert anchor_block.state_root == anchor_state.hash_tree_root()

    anchor_block_root = anchor_block.hash_tree_root()
    return spec.OptimisticStore(
        optimistic_roots=set(),
        head_block_root=anchor_block_root,
        blocks={anchor_block_root: anchor_block.copy()},
        block_states={anchor_block_root: anchor_state.copy()},
    )


def get_valid_flag_value(status: PayloadStatusV1Status) -> bool:
    if (
        status == PayloadStatusV1Status.VALID
        or status.alias == PayloadStatusV1StatusAlias.NOT_VALIDATED
    ):
        return True
    else:
        # status.alias == PayloadStatusV1StatusAlias.INVALIDATED or other cases
        return False


def add_optimistic_block(
    spec,
    mega_store,
    signed_block,
    test_steps,
    payload_status=None,
    status=PayloadStatusV1Status.SYNCING,
):
    """
    Add a block with optimistic sync logic

    ``valid`` indicates if the given ``signed_block.message.body.execution_payload`` is valid/invalid
    from ``verify_and_notify_new_payload`` method response.
    """
    block = signed_block.message
    block_root = block.hash_tree_root()
    el_block_hash = block.body.execution_payload.block_hash

    if payload_status is None:
        payload_status = PayloadStatusV1(status=status)
        if payload_status.status == PayloadStatusV1Status.VALID:
            payload_status.latest_valid_hash = el_block_hash

    mega_store.block_payload_statuses[block_root] = payload_status
    test_steps.append(
        {
            "block_hash": encode_hex(el_block_hash),
            "payload_status": payload_status.formatted_output,
        }
    )

    # Set `valid` flag
    valid = get_valid_flag_value(payload_status.status)

    # Optimistic sync

    # Case: INVALID
    if payload_status.status == PayloadStatusV1Status.INVALID:
        # Update parent status to INVALID
        assert payload_status.latest_valid_hash is not None
        current_block = block
        while el_block_hash != payload_status.latest_valid_hash and el_block_hash != spec.Bytes32():
            current_block_root = current_block.hash_tree_root()
            assert current_block_root in mega_store.block_payload_statuses
            mega_store.block_payload_statuses[
                current_block_root
            ].status = PayloadStatusV1Status.INVALID
            # Get parent
            current_block = mega_store.fc_store.blocks[current_block.parent_root]
            el_block_hash = current_block.body.execution_payload.block_hash

    yield from add_block(
        spec,
        mega_store.fc_store,
        signed_block,
        valid=valid,
        test_steps=test_steps,
        is_optimistic=True,
    )

    # Update stores
    is_optimistic_candidate = is_post_capella(spec) or spec.is_optimistic_candidate_block(
        mega_store.opt_store,
        current_slot=spec.get_current_slot(mega_store.fc_store),
        block=signed_block.message,
    )
    if is_optimistic_candidate:
        mega_store.opt_store.optimistic_roots.add(block_root)
        mega_store.opt_store.blocks[block_root] = signed_block.message.copy()
        if not is_invalidated(mega_store, block_root):
            mega_store.opt_store.block_states[block_root] = mega_store.fc_store.block_states[
                block_root
            ].copy()

    # Clean up the invalidated blocks
    clean_up_store(mega_store)

    # Update head
    mega_store.opt_store.head_block_root = get_opt_head_block_root(spec, mega_store)
    test_steps.append(
        {
            "checks": {
                "head": get_formatted_optimistic_head_output(mega_store),
            }
        }
    )


def get_opt_head_block_root(spec, mega_store):
    """
    Copied and modified from fork-choice spec `get_head` function.
    """
    store = mega_store.fc_store

    # Get filtered node tree that only includes viable branches
    filtered_node_tree = spec.get_filtered_node_tree(store)
    # Execute the LMD-GHOST fork choice
    head = spec.ForkChoiceNode(root=store.justified_checkpoint.root)
    while True:
        children = [
            child
            for child in spec.get_node_children(store, head)
            if (
                child in filtered_node_tree
                and not is_invalidated(mega_store, child.root)  # For optimistic sync
            )
        ]
        if len(children) == 0:
            return head.root
        # Sort by latest attesting balance with ties broken lexicographically
        # Ties broken by favoring block with lexicographically higher root
        head = max(
            children,
            key=lambda node: (spec.get_weight(store, node), node.root),
        )


def is_invalidated(mega_store, block_root):
    if block_root in mega_store.block_payload_statuses:
        return (
            mega_store.block_payload_statuses[block_root].status.alias
            == PayloadStatusV1StatusAlias.INVALIDATED
        )
    else:
        return False


def get_formatted_optimistic_head_output(mega_store):
    head = mega_store.opt_store.head_block_root
    slot = mega_store.fc_store.blocks[head].slot
    return {
        "slot": int(slot),
        "root": encode_hex(head),
    }


def clean_up_store(mega_store):
    """
    Remove invalidated blocks
    """
    # TODO


class GloasMegaStore(MegaStore):
    """
    Gloas-aware ``MegaStore``.

    Pre-Gloas, a beacon block and its execution payload are delivered
    together in a single ``on_block`` call, so one block root maps to at most
    one EL payload-status verdict (tracked by ``block_payload_statuses``
    above). Gloas (EIP-7732) splits delivery into a beacon block (`on_block`)
    and a separately-delivered envelope (`on_execution_payload_envelope`), and
    a single block root then resolves to two distinct ``ForkChoiceNode``s --
    ``PAYLOAD_STATUS_FULL`` and ``PAYLOAD_STATUS_EMPTY`` -- per
    specs/gloas/fork-choice.md. The EL only ever reports a verdict on a
    payload it was handed, so invalidation only ever targets a block's FULL
    interpretation; this store tracks invalidated FULL roots directly and
    computes which other nodes are implicated via ``spec.is_ancestor``,
    mirroring the EL's "invalidate every ForkChoiceNode that descends from
    B-FULL" semantics (ethereum/consensus-specs#5635).
    """

    def __init__(self, spec, fc_store, opt_store):
        super().__init__(spec, fc_store, opt_store)
        # Roots whose FULL payload has been reported INVALID by the EL.
        self.invalidated_full_roots: set[Bytes32] = set()
        # FULL-payload bookkeeping, keyed by EL block hash / block root, used
        # to walk back from a just-reported payload to the first FULL block
        # that directly extends ``latest_valid_hash`` (i.e. "B" in the issue).
        self.full_root_by_el_hash: dict[Bytes32, Bytes32] = {}
        self.full_parent_el_hash_by_root: dict[Bytes32, Bytes32] = {}
        self.head_payload_status = None


def invalidate_full_payload_chain(spec, mega_store, start_block_root, latest_valid_hash):
    """
    Starting from the FULL block ``start_block_root`` that the EL just
    reported on, walk back along recorded FULL-payload parent-hash pointers
    to find B: the first FULL block whose payload directly extends
    ``latest_valid_hash``. Record B's root as invalidated -- every
    ``ForkChoiceNode`` descended from ``(B, PAYLOAD_STATUS_FULL)`` is then
    filtered out by ``is_gloas_payload_invalidated``.

    Returns B's root.
    """
    current_root = start_block_root
    while True:
        assert current_root in mega_store.full_parent_el_hash_by_root, (
            "invalidation reported against a root with no known FULL payload"
        )
        parent_el_hash = mega_store.full_parent_el_hash_by_root[current_root]
        if parent_el_hash == latest_valid_hash:
            mega_store.invalidated_full_roots.add(current_root)
            return current_root
        assert parent_el_hash in mega_store.full_root_by_el_hash, (
            "latest_valid_hash not found while walking the known FULL-payload chain"
        )
        current_root = mega_store.full_root_by_el_hash[parent_el_hash]


def is_gloas_payload_invalidated(spec, mega_store, node) -> bool:
    """
    Return whether ``node`` (a ``ForkChoiceNode``) descends from any
    EL-invalidated FULL root, per ``spec.is_ancestor``.
    """
    store = mega_store.fc_store
    return any(
        spec.is_ancestor(
            store, node, spec.ForkChoiceNode(root=b, payload_status=spec.PAYLOAD_STATUS_FULL)
        )
        for b in mega_store.invalidated_full_roots
    )


def get_gloas_optimistic_head_node(spec, mega_store):
    """
    Copied and modified from the Gloas `get_head` function (see
    specs/gloas/fork-choice.md) to additionally filter out ``ForkChoiceNode``s
    invalidated by EL payload-status reports.
    """
    store = mega_store.fc_store

    # Get filtered node tree that only includes viable branches
    nodes = spec.get_filtered_node_tree(store)
    viable_nodes = [n for n in nodes if not is_gloas_payload_invalidated(spec, mega_store, n)]

    # Return empty node if there are no viable nodes
    if not any(viable_nodes):
        return spec.ForkChoiceNode(
            root=store.justified_checkpoint.root,
            payload_status=spec.PAYLOAD_STATUS_EMPTY,
        )

    # Execute the LMD-GHOST fork choice
    head = spec.ForkChoiceNode(
        root=store.justified_checkpoint.root,
        payload_status=spec.PAYLOAD_STATUS_PENDING,
    )
    while True:
        children = [child for child in spec.get_node_children(store, head) if child in viable_nodes]
        if len(children) == 0:
            return head
        # Sort by latest attesting balance with ties broken lexicographically,
        # then by the same FULL/EMPTY tiebreaker as the real `get_head`.
        head = max(
            children,
            key=lambda child: (
                spec.get_weight(store, child),
                child.root,
                spec.get_payload_status_tiebreaker(store, child),
            ),
        )


def get_formatted_gloas_optimistic_head_output(spec, mega_store):
    head = get_gloas_optimistic_head_node(spec, mega_store)
    return {
        "slot": int(mega_store.fc_store.blocks[head.root].slot),
        "root": encode_hex(head.root),
        "payload_status": int(head.payload_status),
    }


def add_gloas_payload_info(test_steps, block_hash, payload_status):
    test_steps.append(
        {
            "block_hash": encode_hex(block_hash),
            "payload_status": payload_status.formatted_output,
        }
    )


def add_gloas_optimistic_envelope(
    spec,
    mega_store,
    signed_envelope,
    test_steps,
    payload_status=None,
    status=PayloadStatusV1Status.SYNCING,
):
    """
    Gloas equivalent of ``add_optimistic_block`` for execution payload
    envelopes.

    Unlike pre-Gloas forks, where a beacon block and its payload are the same
    ``on_block`` call, Gloas delivers the payload separately via
    ``on_execution_payload_envelope``, and it is the *envelope* -- not the
    block -- that the EL reports VALID/INVALID/SYNCING for. Callers must add
    the underlying beacon block separately (``add_block`` with
    ``is_optimistic=True``) before calling this, and -- if that block builds
    on a FULL parent -- must have already delivered the parent's envelope
    through this same function, exactly as the non-optimistic ``on_block``
    requires (see ``is_parent_node_full`` in specs/gloas/fork-choice.md).
    """
    envelope = signed_envelope.message
    block_root = envelope.beacon_block_root
    el_block_hash = envelope.payload.block_hash
    el_parent_hash = envelope.payload.parent_hash

    if payload_status is None:
        payload_status = PayloadStatusV1(status=status)
        if payload_status.status == PayloadStatusV1Status.VALID:
            payload_status.latest_valid_hash = el_block_hash

    file_name = get_execution_payload_envelope_file_name(signed_envelope)
    yield file_name, signed_envelope
    test_steps.append({"execution_payload": file_name})

    # Accept the envelope into the fork-choice store unconditionally -- same
    # "provisionally accept, track the EL's real verdict separately" shape as
    # `add_block`'s `is_optimistic` path above.
    spec.on_execution_payload_envelope(mega_store.fc_store, signed_envelope)

    mega_store.full_root_by_el_hash[el_block_hash] = block_root
    mega_store.full_parent_el_hash_by_root[block_root] = el_parent_hash

    if payload_status.status == PayloadStatusV1Status.INVALID:
        assert payload_status.latest_valid_hash is not None
        invalidate_full_payload_chain(
            spec, mega_store, block_root, payload_status.latest_valid_hash
        )

    # Update head
    head = get_gloas_optimistic_head_node(spec, mega_store)
    mega_store.opt_store.head_block_root = head.root
    mega_store.head_payload_status = head.payload_status
    test_steps.append(
        {
            "checks": {
                "head": get_formatted_gloas_optimistic_head_output(spec, mega_store),
            }
        }
    )
