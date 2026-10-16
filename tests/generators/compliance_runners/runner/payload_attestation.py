"""Convert aggregate payload attestations to per-validator messages."""

from eth_consensus_specs.test.helpers.keys import privkeys


def payload_attestation_to_messages(spec, state, payload_attestation, signed=False):
    ptc = spec.get_ptc(state, payload_attestation.data.slot)
    bits = payload_attestation.aggregation_bits
    attesting_indices = [index for i, index in enumerate(ptc) if bits[i]]
    messages = []
    for validator_index in attesting_indices:
        if validator_index >= len(privkeys):
            continue
        ptc_message = spec.PayloadAttestationMessage(
            validator_index=validator_index,
            data=payload_attestation.data,
            signature=spec.BLSSignature(),
        )
        if signed:
            ptc_message.signature = spec.get_payload_attestation_message_signature(
                state, ptc_message, privkeys[validator_index]
            )
        messages.append(ptc_message)
    return messages
