* `BLS_WITHDRAWAL_PREFIX`
  * Why int rather than bytes?
* `MIN_SEED_LOOKAHEAD`
  * Is this actually tunable?
  * If so, what are the reprecussions?
* `ACTIVATION_EXIT_DELAY`
  * Reaquaint with purpose
* AttesterSlashings
  * `MAX_ATTESTER_SLASHINGS` is 1.
  * Are there scenarios in which validators can create more effective slashable
    messages than can be included on chain? For example, Validators split up to
    create double attestations for checkpoints but different (junk) crosslink
    data to prevent them from being aggregatable to the fullest
  * Max is for block size, no?
* Signature domains
  * Max 4byte ints
* `Version` not defined in one of the lists of custom types (2!!). ensure in spec
* `PendingAttestation`
  * Don't think `proposer_index` is actually necessary here because effective
    balance is stable until end of epoch so can do dynamic lookups
* is_genesis_trigger
  * only run at ends of blocks to preserve invariant that eth1data.deposit_root
    is the deposit root at the _end_ of an eth1 block
* `Attestation` 
  * why bitfields not together?
* `Transfer`
  * replay mechanism... say the slot gets missed and you sign another transfer
  * in a fork you could include both transfers
* `get_previous_epoch`
  * do a once over on the genesis stuff
* `get_epoch_start_shard`
  * checking next hinges upon the fact that the validator set for the next
    epoch is 100% known at the current epoch. Ensure this is the case
* `get_block_root_at_slot` .. `generate_seed` can be bade into one line
  function signatures
* `get_shuffled_index`
  * I think it should be maybe `assert index_count <= VALIDATOR_REGISTRY_LIMIT`
  * is the `2**40` special for security of alg? probably.


pubkey/privkey g1 vs g2

