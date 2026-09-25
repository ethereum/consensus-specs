"""Checks for consolidation churn when a request validator is inactive."""

from random import Random
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec

from .coverage import _recs
from .materializer import ConsolidationRequestMaterializer
from .validation import recover


def test_inactive_request_validators_preserve_claimed_churn():
    records = _recs()
    cases = (
        lambda r: r["validator_pubkey_found"] and r["validator_active"] == "F",
        lambda r: (
            r["target_found"] == "T" and r["target_active"] == "F" and r["validator_active"] == "T"
        ),
    )
    for predicate in cases:
        record = next(
            r
            for r in records
            if r["consolidation_churn_to_min_activation"] == "EQ" and predicate(r)
        )
        materializer = ConsolidationRequestMaterializer(spec)
        materializer.rng = Random(0)
        _, parts = materializer.materialize_solution(SimpleNamespace(**record))
        pre = spec.BeaconState.decode_bytes(parts[0][2])
        request = spec.ConsolidationRequest.decode_bytes(parts[1][2])
        assert recover(pre, request)["consolidation_churn_to_min_activation"] == "EQ"
