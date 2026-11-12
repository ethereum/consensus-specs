from types import SimpleNamespace

import pytest

from eth_consensus_specs.phase0 import minimal as spec

from .instantiators.helpers import FCTestData, make_events, ProtocolMessage


@pytest.mark.parametrize(
    ("slot_1", "slot_2", "expected_slot"),
    [(8, 17, 18), (17, 8, 18), (8, 8, 9)],
)
def test_make_events_attester_slashing(slot_1, slot_2, expected_slot):
    # Exercise scheduling only, without validating the slashing or its signatures.
    slashing = spec.AttesterSlashing(
        attestation_1=spec.IndexedAttestation(data=spec.AttestationData(slot=slot_1)),
        attestation_2=spec.IndexedAttestation(data=spec.AttestationData(slot=slot_2)),
    )
    block = spec.SignedBeaconBlock(message=spec.BeaconBlock(slot=expected_slot - 1))
    test_data = FCTestData(
        meta={},
        anchor_block=None,
        anchor_state=SimpleNamespace(genesis_time=100, slot=0),
        blocks=[ProtocolMessage(block)],
        slashings=[ProtocolMessage(slashing)],
    )

    events = make_events(spec, test_data)

    assert [event for event in events if event[0] != "tick"] == [
        ("block", block, True),
        ("attester_slashing", slashing, True),
    ]
    assert events[-2:] == [
        ("tick", spec.compute_time_at_slot(100, expected_slot), None),
        ("attester_slashing", slashing, True),
    ]
