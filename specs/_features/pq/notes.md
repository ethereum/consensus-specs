Notes:

- How to handle validators/builders which haven't pre-registered before the
  emergency fork?
  - We must forcibly exit 0x00 validators.
  - We should make 0x01+ validators inert
  - ANSWER: Just forcibly exit all that haven't reregistered.
- How to handle deposit contract; we need to support XMSS sigs.
- Remove sync committees?
- Remove blobs?
- Disable attester slashings?
  - Or just re-org all attester slashings?
- We need to update sys contracts on the EL too.
  - I think it would be better to just not update them & stop new
    deposits/exits.
  - This is actually beneficial imo.
