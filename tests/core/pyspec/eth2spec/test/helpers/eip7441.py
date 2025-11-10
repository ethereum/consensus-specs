from curdleproofs import GenerateWhiskTrackerProof, WhiskTracker
from eth_typing import BLSPubkey
from py_arkworks_bls12381 import G1Point, Scalar

from eth2spec.test.helpers.keys import whisk_ks_initial

# Map of validator index to initial WhiskTracker (r = 1, k = index)
whisk_initial_tracker_cache_by_index = {}
# Map of validator index to k commitment (k = index)
whisk_initial_k_commitment_cache_by_index = {}
# Map of k_r_G to validator index
whisk_initial_tracker_cache_by_k_r_G = {}
INITIAL_R = 1

# Generator
G1 = G1Point()


def compute_whisk_initial_tracker_cached(i: int) -> WhiskTracker:
    if i in whisk_initial_tracker_cache_by_index:
        return whisk_initial_tracker_cache_by_index[i]

    tracker = compute_whisk_tracker(whisk_ks_initial(i), INITIAL_R)
    whisk_initial_tracker_cache_by_index[i] = tracker
    whisk_initial_tracker_cache_by_k_r_G[tracker.k_r_G] = i
    return tracker


def compute_whisk_initial_k_commitment_cached(i: int) -> BLSPubkey:
    if i in whisk_initial_k_commitment_cache_by_index:
        return whisk_initial_k_commitment_cache_by_index[i]

    commitment = compute_whisk_k_commitment(whisk_ks_initial(i))
    whisk_initial_k_commitment_cache_by_index[i] = commitment
    return commitment


def resolve_known_tracker(tracker: WhiskTracker) -> int | None:
    if tracker.k_r_G in whisk_initial_tracker_cache_by_k_r_G:
        return whisk_initial_tracker_cache_by_k_r_G[tracker.k_r_G]
    else:
        return None


def g1point_to_bytes(point: G1Point) -> bytes:
    return bytes(point.to_compressed_bytes())


def compute_whisk_k_commitment(k: int) -> BLSPubkey:
    return g1point_to_bytes(G1 * Scalar(k))


def compute_whisk_tracker(k: int, r: int) -> WhiskTracker:
    r_G = G1 * Scalar(r)
    k_r_G = r_G * Scalar(k)
    return WhiskTracker(g1point_to_bytes(r_G), g1point_to_bytes(k_r_G))


def compute_whisk_tracker_and_commitment(k: int, r: int) -> tuple[WhiskTracker, BLSPubkey]:
    k_G = G1 * Scalar(k)
    r_G = G1 * Scalar(r)
    k_r_G = r_G * Scalar(k)
    tracker = WhiskTracker(g1point_to_bytes(r_G), g1point_to_bytes(k_r_G))
    commitment = g1point_to_bytes(k_G)
    return tracker, commitment


# Trigger condition for first proposal
def set_as_first_proposal(spec, state, proposer_index: int):
    if state.whisk_trackers[proposer_index].r_G != spec.BLS_G1_GENERATOR:
        # Ensure tracker is empty to prevent breaking it
        assert state.whisk_trackers[proposer_index].r_G == spec.BLSG1Point()
        state.whisk_trackers[proposer_index].r_G = spec.BLS_G1_GENERATOR


def is_first_proposal(spec, state, proposer_index: int) -> bool:
    return state.whisk_trackers[proposer_index].r_G == spec.BLS_G1_GENERATOR


def register_tracker(state, proposer_index: int, k: int, r: int):
    tracker, k_commitment = compute_whisk_tracker_and_commitment(k, r)
    state.whisk_trackers[proposer_index] = tracker
    state.whisk_k_commitments[proposer_index] = k_commitment


def set_registration(body, k: int, r: int):
    tracker, k_commitment = compute_whisk_tracker_and_commitment(k, r)
    body.whisk_registration_proof = GenerateWhiskTrackerProof(tracker, Scalar(k))
    body.whisk_tracker = tracker
    body.whisk_k_commitment = k_commitment


def set_opening_proof(spec, state, block, proposer_index: int, k: int, r: int):
    tracker, k_commitment = compute_whisk_tracker_and_commitment(k, r)
    state.whisk_proposer_trackers[state.slot % spec.PROPOSER_TRACKERS_COUNT] = tracker
    state.whisk_k_commitments[proposer_index] = k_commitment
    block.proposer_index = proposer_index
    block.body.whisk_opening_proof = GenerateWhiskTrackerProof(tracker, Scalar(k))
