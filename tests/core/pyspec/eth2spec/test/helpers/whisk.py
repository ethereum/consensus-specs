from typing import Tuple
from eth_typing import BLSPubkey
from py_ecc.optimized_bls12_381.optimized_curve import G1, multiply
from py_ecc.bls.g2_primitives import G1_to_pubkey as py_ecc_G1_to_bytes48
from curdleproofs import GenerateWhiskTrackerProof, WhiskTracker


def get_whisk_k_commitment(k: int) -> BLSPubkey:
    return py_ecc_G1_to_bytes48(multiply(G1, int(k)))


def get_whisk_tracker(k: int, r: int) -> WhiskTracker:
    r_G = multiply(G1, int(r))
    k_r_G = multiply(r_G, int(k))
    return WhiskTracker(py_ecc_G1_to_bytes48(r_G), py_ecc_G1_to_bytes48(k_r_G))


def get_whisk_tracker_and_commitment(k: int, r: int) -> Tuple[WhiskTracker, BLSPubkey]:
    k_G = multiply(G1, int(k))
    r_G = multiply(G1, int(r))
    k_r_G = multiply(r_G, int(k))
    tracker = WhiskTracker(py_ecc_G1_to_bytes48(r_G), py_ecc_G1_to_bytes48(k_r_G))
    commitment = py_ecc_G1_to_bytes48(k_G)
    return tracker, commitment


# Trigger condition for first proposal
def set_as_first_proposal(spec, state, proposer_index: int):
    # Ensure tracker is empty to prevent breaking it
    assert state.validators[proposer_index].whisk_tracker.r_G == spec.BLSG1Point()
    state.validators[proposer_index].whisk_tracker.r_G = spec.BLS_G1_GENERATOR


def is_first_proposal(spec, state, proposer_index: int) -> bool:
    return state.validators[proposer_index].whisk_tracker.r_G == spec.BLS_G1_GENERATOR


def set_registration(body, k: int, r: int):
    tracker, k_commitment = get_whisk_tracker_and_commitment(k, r)
    body.whisk_registration_proof = GenerateWhiskTrackerProof(tracker, k)
    body.whisk_tracker = tracker
    body.whisk_k_commitment = k_commitment


def set_opening_proof(spec, state, block, proposer_index: int, k: int, r: int):
    tracker, k_commitment = get_whisk_tracker_and_commitment(k, r)
    state.whisk_proposer_trackers[state.slot % spec.WHISK_PROPOSER_TRACKERS_COUNT] = tracker
    state.validators[proposer_index].whisk_k_commitment = k_commitment
    block.proposer_index = proposer_index
    block.body.whisk_opening_proof = GenerateWhiskTrackerProof(tracker, k)
