Ethereum 2.0 Phase 0 -- The Beacon Chain
========================================

**NOTICE**: This document is a work-in-progress for researchers and
implementers. It reflects recent spec changes and takes precedence over
the Python proof-of-concept implementation
python-poc_.


Introduction
------------

This document represents the specification for Phase 0 of Ethereum 2.0
-- The Beacon Chain.

At the core of Ethereum 2.0 is a system chain called the "beacon chain".
The beacon chain stores and manages the registry of
`validators <#dfn-validator>`__. In the initial deployment phases of
Ethereum 2.0 the only mechanism to become a
`validator <#dfn-validator>`__ is to make a one-way ETH transaction to a
deposit contract on Ethereum 1.0. Activation as a
`validator <#dfn-validator>`__ happens when Ethereum 1.0 deposit
receipts are processed by the beacon chain, the activation balance is
reached, and after a queuing process. Exit is either voluntary or done
forcibly as a penalty for misbehavior.

The primary source of load on the beacon chain is "attestations".
Attestations are availability votes for a shard block, and
simultaneously proof of stake votes for a beacon block. A sufficient
number of attestations for the same shard block create a "crosslink",
confirming the shard segment up to that shard block into the beacon
chain. Crosslinks also serve as infrastructure for asynchronous
cross-shard communication.

Notation
--------

Code snippets appearing in ``this style`` are to be interpreted as
Python code.

Terminology
-----------

-  **Validator** - a registered participant in the beacon chain. You can
   become one by sending Ether into the Ethereum 1.0 deposit contract.
-  **Active validator** - an active participant in the Ethereum 2.0
   consensus invited to, among other things, propose and attest to
   blocks and vote for crosslinks.
-  **Committee** - a (pseudo-) randomly sampled subset of `active
   validators <#dfn-active-validator>`__. When a committee is referred
   to collectively, as in "this committee attests to X", this is assumed
   to mean "some subset of that committee that contains enough
   `validators <#dfn-validator>`__ that the protocol recognizes it as
   representing the committee".
-  **Proposer** - the `validator <#dfn-validator>`__ that creates a
   beacon chain block
-  **Attester** - a `validator <#dfn-validator>`__ that is part of a
   committee that needs to sign off on a beacon chain block while
   simultaneously creating a link (crosslink) to a recent shard block on
   a particular shard chain.
-  **Beacon chain** - the central PoS chain that is the base of the
   sharding system.
-  **Shard chain** - one of the chains on which user transactions take
   place and account data is stored.
-  **Block root** - a 32-byte Merkle root of a beacon chain block or
   shard chain block. Previously called "block hash".
-  **Crosslink** - a set of signatures from a committee attesting to a
   block in a shard chain, which can be included into the beacon chain.
   Crosslinks are the main means by which the beacon chain "learns
   about" the updated state of shard chains.
-  **Slot** - a period during which one proposer has the ability to
   create a beacon chain block and some attesters have the ability to
   make attestations
-  **Epoch** - an aligned span of slots during which all
   `validators <#dfn-validator>`__ get exactly one chance to make an
   attestation
-  **Finalized**, **justified** - see Casper FFG finalization casper-ffg_
-  **Withdrawal period** - the number of slots between a
   `validator <#dfn-validator>`__ exit and the
   `validator <#dfn-validator>`__ balance being withdrawable
-  **Genesis time** - the Unix time of the genesis beacon chain block at
   slot 0

Constants
---------

Misc
~~~~

+----------------------------------------------+-----------------------+
| Name                                         | Value                 |
+==============================================+=======================+
| ``SHARD_COUNT``                              | ``2**10`` (= 1,024)   |
+----------------------------------------------+-----------------------+
| ``TARGET_COMMITTEE_SIZE``                    | ``2**7`` (= 128)      |
+----------------------------------------------+-----------------------+
| ``MAX_BALANCE_CHURN_QUOTIENT``               | ``2**5`` (= 32)       |
+----------------------------------------------+-----------------------+
| ``MAX_SLASHABLE_ATTESTATION_PARTICIPANTS``   | ``2**12`` (= 4,096)   |
+----------------------------------------------+-----------------------+
| ``MAX_EXIT_DEQUEUES_PER_EPOCH``              | ``2**2`` (= 4)        |
+----------------------------------------------+-----------------------+
| ``SHUFFLE_ROUND_COUNT``                      | 90                    |
+----------------------------------------------+-----------------------+

-  For the safety of crosslinks ``TARGET_COMMITTEE_SIZE`` exceeds `the
   recommended minimum committee size of
   111 <https://vitalik.ca/files/Ithaca201807_Sharding.pdf>`__; with
   sufficient active validators (at least
   ``SLOTS_PER_EPOCH * TARGET_COMMITTEE_SIZE``), the shuffling algorithm
   ensures committee sizes of at least ``TARGET_COMMITTEE_SIZE``.
   (Unbiasable randomness with a Verifiable Delay Function (VDF) will
   improve committee robustness and lower the safe minimum committee
   size.)

Deposit contract
~~~~~~~~~~~~~~~~

+-----------------------------------+-------------------+
| Name                              | Value             |
+===================================+===================+
| ``DEPOSIT_CONTRACT_ADDRESS``      | **TBD**           |
+-----------------------------------+-------------------+
| ``DEPOSIT_CONTRACT_TREE_DEPTH``   | ``2**5`` (= 32)   |
+-----------------------------------+-------------------+

Gwei values
~~~~~~~~~~~

+------------------------------+---------------------------------------+--------+
| Name                         | Value                                 | Unit   |
+==============================+=======================================+========+
| ``MIN_DEPOSIT_AMOUNT``       | ``2**0 * 10**9`` (= 1,000,000,000)    | Gwei   |
+------------------------------+---------------------------------------+--------+
| ``MAX_DEPOSIT_AMOUNT``       | ``2**5 * 10**9`` (= 32,000,000,000)   | Gwei   |
+------------------------------+---------------------------------------+--------+
| ``EJECTION_BALANCE``         | ``2**4 * 10**9`` (= 16,000,000,000)   | Gwei   |
+------------------------------+---------------------------------------+--------+
| ``HIGH_BALANCE_INCREMENT``   | ``2**0 * 10**9`` (= 1,000,000,000)    | Gwei   |
+------------------------------+---------------------------------------+--------+

Initial values
~~~~~~~~~~~~~~

+----------------------------------+-----------------------------------+
| Name                             | Value                             |
+==================================+===================================+
| ``GENESIS_FORK_VERSION``         | ``int_to_bytes4(0)``              |
+----------------------------------+-----------------------------------+
| ``GENESIS_SLOT``                 | ``2**32``                         |
+----------------------------------+-----------------------------------+
| ``GENESIS_EPOCH``                | ``slot_to_epoch(GENESIS_SLOT)``   |
+----------------------------------+-----------------------------------+
| ``GENESIS_START_SHARD``          | ``0``                             |
+----------------------------------+-----------------------------------+
| ``FAR_FUTURE_EPOCH``             | ``2**64 - 1``                     |
+----------------------------------+-----------------------------------+
| ``ZERO_HASH``                    | ``int_to_bytes32(0)``             |
+----------------------------------+-----------------------------------+
| ``EMPTY_SIGNATURE``              | ``int_to_bytes96(0)``             |
+----------------------------------+-----------------------------------+
| ``BLS_WITHDRAWAL_PREFIX_BYTE``   | ``int_to_bytes1(0)``              |
+----------------------------------+-----------------------------------+

-  ``GENESIS_SLOT`` should be at least as large in terms of time as the
   largest of the time parameters or state list lengths below (ie. it
   should be at least as large as any value measured in slots, and at
   least ``SLOTS_PER_EPOCH`` times as large as any value measured in
   epochs).

Time parameters
~~~~~~~~~~~~~~~

+-------------------------------------------+-----------------------+-----------+----------------+
| Name                                      | Value                 | Unit      | Duration       |
+===========================================+=======================+===========+================+
| ``SECONDS_PER_SLOT``                      | ``6``                 | seconds   | 6 seconds      |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``MIN_ATTESTATION_INCLUSION_DELAY``       | ``2**2`` (= 4)        | slots     | 24 seconds     |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``SLOTS_PER_EPOCH``                       | ``2**6`` (= 64)       | slots     | 6.4 minutes    |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``MIN_SEED_LOOKAHEAD``                    | ``2**0`` (= 1)        | epochs    | 6.4 minutes    |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``ACTIVATION_EXIT_DELAY``                 | ``2**2`` (= 4)        | epochs    | 25.6 minutes   |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``EPOCHS_PER_ETH1_VOTING_PERIOD``         | ``2**4`` (= 16)       | epochs    | ~1.7 hours     |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``SLOTS_PER_HISTORICAL_ROOT``             | ``2**13`` (= 8,192)   | slots     | ~13 hours      |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``MIN_VALIDATOR_WITHDRAWABILITY_DELAY``   | ``2**8`` (= 256)      | epochs    | ~27 hours      |
+-------------------------------------------+-----------------------+-----------+----------------+
| ``PERSISTENT_COMMITTEE_PERIOD``           | ``2**11`` (= 2,048)   | epochs    | 9 days         |
+-------------------------------------------+-----------------------+-----------+----------------+

State list lengths
~~~~~~~~~~~~~~~~~~

+----------------------------------------+-----------------------+----------+------------+
| Name                                   | Value                 | Unit     | Duration   |
+========================================+=======================+==========+============+
| ``LATEST_RANDAO_MIXES_LENGTH``         | ``2**13`` (= 8,192)   | epochs   | ~36 days   |
+----------------------------------------+-----------------------+----------+------------+
| ``LATEST_ACTIVE_INDEX_ROOTS_LENGTH``   | ``2**13`` (= 8,192)   | epochs   | ~36 days   |
+----------------------------------------+-----------------------+----------+------------+
| ``LATEST_SLASHED_EXIT_LENGTH``         | ``2**13`` (= 8,192)   | epochs   | ~36 days   |
+----------------------------------------+-----------------------+----------+------------+

Reward and penalty quotients
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+---------------------------------------------+----------------------------+
| Name                                        | Value                      |
+=============================================+============================+
| ``BASE_REWARD_QUOTIENT``                    | ``2**5`` (= 32)            |
+---------------------------------------------+----------------------------+
| ``WHISTLEBLOWER_REWARD_QUOTIENT``           | ``2**9`` (= 512)           |
+---------------------------------------------+----------------------------+
| ``ATTESTATION_INCLUSION_REWARD_QUOTIENT``   | ``2**3`` (= 8)             |
+---------------------------------------------+----------------------------+
| ``INACTIVITY_PENALTY_QUOTIENT``             | ``2**24`` (= 16,777,216)   |
+---------------------------------------------+----------------------------+
| ``MIN_PENALTY_QUOTIENT``                    | ``2**5`` (= 32)            |
+---------------------------------------------+----------------------------+

-  The ``BASE_REWARD_QUOTIENT`` parameter dictates the per-epoch reward.
   It corresponds to ~2.54% annual interest assuming 10 million
   participating ETH in every epoch.
-  The ``INACTIVITY_PENALTY_QUOTIENT`` equals
   ``INVERSE_SQRT_E_DROP_TIME**2`` where
   ``INVERSE_SQRT_E_DROP_TIME := 2**12 epochs`` (~18 days) is the time
   it takes the inactivity penalty to reduce the balance of
   non-participating `validators <#dfn-validator>`__ to about
   ``1/sqrt(e) ~= 60.6%``. Indeed, the balance retained by offline
   `validators <#dfn-validator>`__ after ``n`` epochs is about
   ``(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(n**2/2)`` so after
   ``INVERSE_SQRT_E_DROP_TIME`` epochs it is roughly
   ``(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(INACTIVITY_PENALTY_QUOTIENT/2) ~= 1/sqrt(e)``.

Max transactions per block
~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------------------+--------------------+
| Name                         | Value              |
+==============================+====================+
| ``MAX_PROPOSER_SLASHINGS``   | ``2**4`` (= 16)    |
+------------------------------+--------------------+
| ``MAX_ATTESTER_SLASHINGS``   | ``2**0`` (= 1)     |
+------------------------------+--------------------+
| ``MAX_ATTESTATIONS``         | ``2**7`` (= 128)   |
+------------------------------+--------------------+
| ``MAX_DEPOSITS``             | ``2**4`` (= 16)    |
+------------------------------+--------------------+
| ``MAX_VOLUNTARY_EXITS``      | ``2**4`` (= 16)    |
+------------------------------+--------------------+
| ``MAX_TRANSFERS``            | ``2**4`` (= 16)    |
+------------------------------+--------------------+

Signature domains
~~~~~~~~~~~~~~~~~

+-----------------------------+---------+
| Name                        | Value   |
+=============================+=========+
| ``DOMAIN_BEACON_BLOCK``     | ``0``   |
+-----------------------------+---------+
| ``DOMAIN_RANDAO``           | ``1``   |
+-----------------------------+---------+
| ``DOMAIN_ATTESTATION``      | ``2``   |
+-----------------------------+---------+
| ``DOMAIN_DEPOSIT``          | ``3``   |
+-----------------------------+---------+
| ``DOMAIN_VOLUNTARY_EXIT``   | ``4``   |
+-----------------------------+---------+
| ``DOMAIN_TRANSFER``         | ``5``   |
+-----------------------------+---------+

Data structures
---------------

The following data structures are defined as `SimpleSerialize
(SSZ) <https://github.com/ethereum/eth2.0-specs/blob/master/specs/simple-serialize.md>`__
objects.

The types are defined topologically to aid in facilitating an executable
version of the spec.

Misc dependencies
~~~~~~~~~~~~~~~~~

``Fork``
^^^^^^^^

.. code:: python

    {
        # Previous fork version
        'previous_version': 'bytes4',
        # Current fork version
        'current_version': 'bytes4',
        # Fork epoch number
        'epoch': 'uint64',
    }

``Crosslink``
^^^^^^^^^^^^^

.. code:: python

    {
        # Epoch number
        'epoch': 'uint64',
        # Shard data since the previous crosslink
        'crosslink_data_root': 'bytes32',
    }

``Eth1Data``
^^^^^^^^^^^^

.. code:: python

    {
        # Root of the deposit tree
        'deposit_root': 'bytes32',
        # Total number of deposits
        'deposit_count': 'uint64',
        # Block hash
        'block_hash': 'bytes32',
    }

``Eth1DataVote``
^^^^^^^^^^^^^^^^

.. code:: python

    {
        # Data being voted for
        'eth1_data': Eth1Data,
        # Vote count
        'vote_count': 'uint64',
    }

``AttestationData``
^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # LMD GHOST vote
        'slot': 'uint64',
        'beacon_block_root': 'bytes32',

        # FFG vote
        'source_epoch': 'uint64',
        'source_root': 'bytes32',
        'target_root': 'bytes32',

        # Crosslink vote
        'shard': 'uint64',
        'previous_crosslink': Crosslink,
        'crosslink_data_root': 'bytes32',
    }

``AttestationDataAndCustodyBit``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # Attestation data
        'data': AttestationData,
        # Custody bit
        'custody_bit': 'bool',
    }

``SlashableAttestation``
^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # Validator indices
        'validator_indices': ['uint64'],
        # Attestation data
        'data': AttestationData,
        # Custody bitfield
        'custody_bitfield': 'bytes',
        # Aggregate signature
        'aggregate_signature': 'bytes96',
    }

``DepositInput``
^^^^^^^^^^^^^^^^

.. code:: python

    {
        # BLS pubkey
        'pubkey': 'bytes48',
        # Withdrawal credentials
        'withdrawal_credentials': 'bytes32',
        # A BLS signature of this `DepositInput`
        'proof_of_possession': 'bytes96',
    }

``DepositData``
^^^^^^^^^^^^^^^

.. code:: python

    {
        # Amount in Gwei
        'amount': 'uint64',
        # Timestamp from deposit contract
        'timestamp': 'uint64',
        # Deposit input
        'deposit_input': DepositInput,
    }

``BeaconBlockHeader``
^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        'slot': 'uint64',
        'previous_block_root': 'bytes32',
        'state_root': 'bytes32',
        'block_body_root': 'bytes32',
        'signature': 'bytes96',
    }

``Validator``
^^^^^^^^^^^^^

.. code:: python

    {
        # BLS public key
        'pubkey': 'bytes48',
        # Withdrawal credentials
        'withdrawal_credentials': 'bytes32',
        # Epoch when validator activated
        'activation_epoch': 'uint64',
        # Epoch when validator exited
        'exit_epoch': 'uint64',
        # Epoch when validator is eligible to withdraw
        'withdrawable_epoch': 'uint64',
        # Did the validator initiate an exit
        'initiated_exit': 'bool',
        # Was the validator slashed
        'slashed': 'bool',
        # Rounded balance
        'high_balance': 'uint64'
    }

``PendingAttestation``
^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # Attester aggregation bitfield
        'aggregation_bitfield': 'bytes',
        # Attestation data
        'data': AttestationData,
        # Custody bitfield
        'custody_bitfield': 'bytes',
        # Inclusion slot
        'inclusion_slot': 'uint64',
    }

``HistoricalBatch``
^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # Block roots
        'block_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
        # State roots
        'state_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    }

Beacon transactions
~~~~~~~~~~~~~~~~~~~

``ProposerSlashing``
^^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # Proposer index
        'proposer_index': 'uint64',
        # First block header
        'header_1': BeaconBlockHeader,
        # Second block header
        'header_2': BeaconBlockHeader,
    }

``AttesterSlashing``
^^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # First slashable attestation
        'slashable_attestation_1': SlashableAttestation,
        # Second slashable attestation
        'slashable_attestation_2': SlashableAttestation,
    }

``Attestation``
^^^^^^^^^^^^^^^

.. code:: python

    {
        # Attester aggregation bitfield
        'aggregation_bitfield': 'bytes',
        # Attestation data
        'data': AttestationData,
        # Custody bitfield
        'custody_bitfield': 'bytes',
        # BLS aggregate signature
        'aggregate_signature': 'bytes96',
    }

``Deposit``
^^^^^^^^^^^

.. code:: python

    {
        # Branch in the deposit tree
        'proof': ['bytes32', DEPOSIT_CONTRACT_TREE_DEPTH],
        # Index in the deposit tree
        'index': 'uint64',
        # Data
        'deposit_data': DepositData,
    }

``VoluntaryExit``
^^^^^^^^^^^^^^^^^

.. code:: python

    {
        # Minimum epoch for processing exit
        'epoch': 'uint64',
        # Index of the exiting validator
        'validator_index': 'uint64',
        # Validator signature
        'signature': 'bytes96',
    }

``Transfer``
^^^^^^^^^^^^

.. code:: python

    {
        # Sender index
        'sender': 'uint64',
        # Recipient index
        'recipient': 'uint64',
        # Amount in Gwei
        'amount': 'uint64',
        # Fee in Gwei for block proposer
        'fee': 'uint64',
        # Inclusion slot
        'slot': 'uint64',
        # Sender withdrawal pubkey
        'pubkey': 'bytes48',
        # Sender signature
        'signature': 'bytes96',
    }

Beacon blocks
~~~~~~~~~~~~~

``BeaconBlockBody``
^^^^^^^^^^^^^^^^^^^

.. code:: python

    {
        'randao_reveal': 'bytes96',
        'eth1_data': Eth1Data,
        'proposer_slashings': [ProposerSlashing],
        'attester_slashings': [AttesterSlashing],
        'attestations': [Attestation],
        'deposits': [Deposit],
        'voluntary_exits': [VoluntaryExit],
        'transfers': [Transfer],
    }

``BeaconBlock``
^^^^^^^^^^^^^^^

.. code:: python

    {
        # Header
        'slot': 'uint64',
        'previous_block_root': 'bytes32',
        'state_root': 'bytes32',
        'body': BeaconBlockBody,
        'signature': 'bytes96',
    }

Beacon state
~~~~~~~~~~~~

``BeaconState``
^^^^^^^^^^^^^^^

.. code:: python

    {
        # Misc
        'slot': 'uint64',
        'genesis_time': 'uint64',
        'fork': Fork,  # For versioning hard forks

        # Validator registry
        'validator_registry': [Validator],
        'balances': ['uint64'],
        'validator_registry_update_epoch': 'uint64',

        # Randomness and committees
        'latest_randao_mixes': ['bytes32', LATEST_RANDAO_MIXES_LENGTH],
        'previous_shuffling_start_shard': 'uint64',
        'current_shuffling_start_shard': 'uint64',
        'previous_shuffling_epoch': 'uint64',
        'current_shuffling_epoch': 'uint64',
        'previous_shuffling_seed': 'bytes32',
        'current_shuffling_seed': 'bytes32',

        # Finality
        'previous_epoch_attestations': [PendingAttestation],
        'current_epoch_attestations': [PendingAttestation],
        'previous_justified_epoch': 'uint64',
        'current_justified_epoch': 'uint64',
        'previous_justified_root': 'bytes32',
        'current_justified_root': 'bytes32',
        'justification_bitfield': 'uint64',
        'finalized_epoch': 'uint64',
        'finalized_root': 'bytes32',

        # Recent state
        'latest_crosslinks': [Crosslink, SHARD_COUNT],
        'latest_block_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
        'latest_state_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
        'latest_active_index_roots': ['bytes32', LATEST_ACTIVE_INDEX_ROOTS_LENGTH],
        'latest_slashed_balances': ['uint64', LATEST_SLASHED_EXIT_LENGTH],  # Balances slashed at every withdrawal period
        'latest_block_header': BeaconBlockHeader,  # `latest_block_header.state_root == ZERO_HASH` temporarily
        'historical_roots': ['bytes32'],

        # Ethereum 1.0 chain data
        'latest_eth1_data': Eth1Data,
        'eth1_data_votes': [Eth1DataVote],
        'deposit_index': 'uint64',
    }

Custom Types
------------

We define the following Python custom types for type hinting and
readability:

+----------------------+------------------+------------------------------+
| Name                 | SSZ equivalent   | Description                  |
+======================+==================+==============================+
| ``Slot``             | ``uint64``       | a slot number                |
+----------------------+------------------+------------------------------+
| ``Epoch``            | ``uint64``       | an epoch number              |
+----------------------+------------------+------------------------------+
| ``Shard``            | ``uint64``       | a shard number               |
+----------------------+------------------+------------------------------+
| ``ValidatorIndex``   | ``uint64``       | a validator registry index   |
+----------------------+------------------+------------------------------+
| ``Gwei``             | ``uint64``       | an amount in Gwei            |
+----------------------+------------------+------------------------------+
| ``Bytes32``          | ``bytes32``      | 32 bytes of binary data      |
+----------------------+------------------+------------------------------+
| ``BLSPubkey``        | ``bytes48``      | a BLS12-381 public key       |
+----------------------+------------------+------------------------------+
| ``BLSSignature``     | ``bytes96``      | a BLS12-381 signature        |
+----------------------+------------------+------------------------------+

Helper functions
----------------

Note: The definitions below are for specification purposes and are not
necessarily optimal implementations.

``xor``
~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: xor

``hash``
~~~~~~~~

The hash function is denoted by ``hash``. In Phase 0 the beacon chain is
deployed with the same hash function as Ethereum 1.0, i.e. Keccak-256
(also incorrectly known as SHA3).

Note: We aim to migrate to a S[T/N]ARK-friendly hash function in a
future Ethereum 2.0 deployment phase.


``hash_tree_root``
~~~~~~~~~~~~~~~~~~

``def hash_tree_root(object: SSZSerializable) -> Bytes32`` is a function
for hashing objects into a single root utilizing a hash tree structure.
``hash_tree_root`` is defined in the `SimpleSerialize
spec <https://github.com/ethereum/eth2.0-specs/blob/master/specs/simple-serialize.md#tree-hash>`__.

``signed_root``
~~~~~~~~~~~~~~~

``def signed_root(object: SSZContainer) -> Bytes32`` is a function
defined in the `SimpleSerialize
spec <https://github.com/ethereum/eth2.0-specs/blob/master/specs/simple-serialize.md#signed-roots>`__
to compute signed messages.

``get_temporary_block_header``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_temporary_block_header

``slot_to_epoch``
~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: slot_to_epoch

``get_previous_epoch``
~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_previous_epoch

``get_current_epoch``
~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_current_epoch

``get_epoch_start_slot``
~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_epoch_start_slot

``is_active_validator``
~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: is_active_validator

``is_slashable_validator``
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: is_slashable_validator

``get_active_validator_indices``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_active_validator_indices

``get_balance``
~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_balance


``set_balance``
~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: set_balance

``increase_balance``
~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: increase_balance

``decrease_balance``
~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: decrease_balance

``get_permuted_index``
~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_permuted_index

``get_split_offset``
~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_split_offset

``get_epoch_committee_count``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_epoch_committee_count

``compute_committee``
~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: compute_committee

**Note**: this definition and the next few definitions are highly
inefficient as algorithms as they re-calculate many sub-expressions.
Production implementations are expected to appropriately use
caching/memoization to avoid redoing work.

``get_previous_epoch_committee_count``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_previous_epoch_committee_count

``get_current_epoch_committee_count``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_current_epoch_committee_count

``get_next_epoch_committee_count``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_next_epoch_committee_count

``get_crosslink_committees_at_slot``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_crosslink_committees_at_slot

``get_block_root``
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_crosslink_committees_at_slot

``get_block_root(_, s)`` should always return ``hash_tree_root`` of the
block in the beacon chain at slot ``s``, and
``get_crosslink_committees_at_slot(_, s)`` should not change unless the
`validator <#dfn-validator>`__ registry changes.

``get_state_root``
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_state_root

``get_randao_mix``
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_randao_mix

``get_active_index_root``
~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_active_index_root

``generate_seed``
~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: generate_seed

``get_beacon_proposer_index``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_beacon_proposer_index

``verify_merkle_branch``
~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: verify_merkle_branch

``get_attestation_participants``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_attestation_participants

``is_power_of_two``
~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: is_power_of_two

``int_to_bytes1``, ``int_to_bytes2``, ...
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``int_to_bytes1(x): return x.to_bytes(1, 'little')``,
``int_to_bytes2(x): return x.to_bytes(2, 'little')``, and so on for all
integers, particularly 1, 2, 3, 4, 8, 32, 48, 96.

``bytes_to_int``
~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: bytes_to_int

``get_effective_balance``
~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_effective_balance

``get_total_balance``
~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_total_balance

``get_fork_version``
~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_fork_version

``get_domain``
~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_domain

``get_bitfield_bit``
~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_bitfield_bit

``verify_bitfield``
~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: verify_bitfield

``verify_slashable_attestation``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: verify_slashable_attestation

``is_double_vote``
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: is_double_vote

``is_surround_vote``
~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: is_surround_vote

``integer_squareroot``
~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: integer_squareroot

``get_delayed_activation_exit_epoch``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: get_delayed_activation_exit_epoch

``bls_verify``
~~~~~~~~~~~~~~

``bls_verify`` is a function for verifying a BLS signature, defined in
the `BLS Signature
spec <https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_verify>`__.

``bls_verify_multiple``
~~~~~~~~~~~~~~~~~~~~~~~

``bls_verify_multiple`` is a function for verifying a BLS signature
constructed from multiple messages, defined in the `BLS Signature
spec <https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_verify_multiple>`__.

``bls_aggregate_pubkeys``
~~~~~~~~~~~~~~~~~~~~~~~~~

``bls_aggregate_pubkeys`` is a function for aggregating multiple BLS
public keys into a single aggregate key, defined in the `BLS Signature
spec <https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_aggregate_pubkeys>`__.

``process_deposit``
~~~~~~~~~~~~~~~~~~~

Used to add a `validator <#dfn-validator>`__ or top up an existing
`validator <#dfn-validator>`__'s balance by some ``deposit`` amount:

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: process_deposit

Routines for updating validator status
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Note: All functions in this section mutate ``state``.

``activate_validator``
^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: activate_validator

``initiate_validator_exit``
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: initiate_validator_exit

``exit_validator``
^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: exit_validator

``slash_validator``
^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: slash_validator 

``prepare_validator_for_withdrawal``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../eth2_specs/phase0/spec.py
   :pyobject: prepare_validator_for_withdrawal

Ethereum 1.0 deposit contract
-----------------------------

The initial deployment phases of Ethereum 2.0 are implemented without
consensus changes to Ethereum 1.0. A deposit contract at address
``DEPOSIT_CONTRACT_ADDRESS`` is added to Ethereum 1.0 for deposits of
ETH to the beacon chain. Validator balances will be withdrawable to the
shards in phase 2, i.e. when the EVM2.0 is deployed and the shards have
state.

Deposit arguments
~~~~~~~~~~~~~~~~~

The deposit contract has a single ``deposit`` function which takes as
argument a SimpleSerialize'd ``DepositInput``.

Withdrawal credentials
~~~~~~~~~~~~~~~~~~~~~~

One of the ``DepositInput`` fields is ``withdrawal_credentials``. It is
a commitment to credentials for withdrawals to shards. The first byte of
``withdrawal_credentials`` is a version number. As of now the only
expected format is as follows:

-  ``withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE``
-  ``withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]`` where
   ``withdrawal_pubkey`` is a BLS pubkey

The private key corresponding to ``withdrawal_pubkey`` will be required
to initiate a withdrawal. It can be stored separately until a withdrawal
is required, e.g. in cold storage.

``Deposit`` logs
~~~~~~~~~~~~~~~~

Every Ethereum 1.0 deposit, of size between ``MIN_DEPOSIT_AMOUNT`` and
``MAX_DEPOSIT_AMOUNT``, emits a ``Deposit`` log for consumption by the
beacon chain. The deposit contract does little validation, pushing most
of the validator onboarding logic to the beacon chain. In particular,
the proof of possession (a BLS12 signature) is not verified by the
deposit contract.

``Eth2Genesis`` log
~~~~~~~~~~~~~~~~~~~

When sufficiently many full deposits have been made the deposit contract
emits the ``Eth2Genesis`` log. The beacon chain state may then be
initialized by calling the ``get_genesis_beacon_state`` function
(defined below) where:

-  ``genesis_time`` equals ``time`` in the ``Eth2Genesis`` log
-  ``latest_eth1_data.deposit_root`` equals ``deposit_root`` in the
   ``Eth2Genesis`` log
-  ``latest_eth1_data.deposit_count`` equals ``deposit_count`` in the
   ``Eth2Genesis`` log
-  ``latest_eth1_data.block_hash`` equals the hash of the block that
   included the log
-  ``genesis_validator_deposits`` is a list of ``Deposit`` objects built
   according to the ``Deposit`` logs up to the deposit that triggered
   the ``Eth2Genesis`` log, processed in the order in which they were
   emitted (oldest to newest)

Vyper code
~~~~~~~~~~

The source for the Vyper contract lives in a `separate
repository <https://github.com/ethereum/deposit_contract>`__ at
https://github.com/ethereum/deposit_contract/blob/master/deposit_contract/contracts/validator_registration.v.py.

Note: to save ~10x on gas this contract uses a somewhat unintuitive
progressive Merkle root calculation algo that requires only O(log(n))
storage. See
https://github.com/ethereum/research/blob/master/beacon\_chain\_impl/progressive\_merkle\_tree.py
for an implementation of the same algo in python tested for correctness.

For convenience, we provide the interface to the contract here:

-  ``__init__()``: initializes the contract
-  ``get_deposit_root() -> bytes32``: returns the current root of the
   deposit tree
-  ``deposit(bytes[512])``: adds a deposit instance to the deposit tree,
   incorporating the input argument and the value transferred in the
   given call. Note: the amount of value transferred *must* be within
   ``MIN_DEPOSIT_AMOUNT`` and ``MAX_DEPOSIT_AMOUNT``, inclusive. Each of
   these constants are specified in units of Gwei.

On genesis
----------

When enough full deposits have been made to the deposit contract, an
``Eth2Genesis`` log is emitted. Construct a corresponding
``genesis_state`` and ``genesis_block`` as follows:

-  Let ``genesis_validator_deposits`` be the list of deposits, ordered
   chronologically, up to and including the deposit that triggered the
   ``Eth2Genesis`` log.
-  Let ``genesis_time`` be the timestamp specified in the
   ``Eth2Genesis`` log.
-  Let ``genesis_eth1_data`` be the ``Eth1Data`` object where:

   -  ``genesis_eth1_data.deposit_root`` is the ``deposit_root``
      contained in the ``Eth2Genesis`` log.
   -  ``genesis_eth1_data.deposit_count`` is the ``deposit_count``
      contained in the ``Eth2Genesis`` log.
   -  ``genesis_eth1_data.block_hash`` is the hash of the Ethereum 1.0
      block that emitted the ``Eth2Genesis`` log.

-  Let
   ``genesis_state = get_genesis_beacon_state(genesis_validator_deposits, genesis_time, genesis_eth1_data)``.
-  Let ``genesis_block = get_empty_block()``.
-  Set ``genesis_block.state_root = hash_tree_root(genesis_state)``.

.. code:: python

    def get_empty_block() -> BeaconBlock:
        """
        Get an empty ``BeaconBlock``.
        """
        return BeaconBlock(
            slot=GENESIS_SLOT,
            previous_block_root=ZERO_HASH,
            state_root=ZERO_HASH,
            body=BeaconBlockBody(
                randao_reveal=EMPTY_SIGNATURE,
                eth1_data=Eth1Data(
                    deposit_root=ZERO_HASH,
                    deposit_count=0,
                    block_hash=ZERO_HASH,
                ),
                proposer_slashings=[],
                attester_slashings=[],
                attestations=[],
                deposits=[],
                voluntary_exits=[],
                transfers=[],
            ),
            signature=EMPTY_SIGNATURE,
        )

.. code:: python

    def get_genesis_beacon_state(genesis_validator_deposits: List[Deposit],
                                 genesis_time: int,
                                 genesis_eth1_data: Eth1Data) -> BeaconState:
        """
        Get the genesis ``BeaconState``.
        """
        state = BeaconState(
            # Misc
            slot=GENESIS_SLOT,
            genesis_time=genesis_time,
            fork=Fork(
                previous_version=GENESIS_FORK_VERSION,
                current_version=GENESIS_FORK_VERSION,
                epoch=GENESIS_EPOCH,
            ),

            # Validator registry
            validator_registry=[],
            balances=[],
            validator_registry_update_epoch=GENESIS_EPOCH,

            # Randomness and committees
            latest_randao_mixes=Vector([ZERO_HASH for _ in range(LATEST_RANDAO_MIXES_LENGTH)]),
            previous_shuffling_start_shard=GENESIS_START_SHARD,
            current_shuffling_start_shard=GENESIS_START_SHARD,
            previous_shuffling_epoch=GENESIS_EPOCH - 1,
            current_shuffling_epoch=GENESIS_EPOCH,
            previous_shuffling_seed=ZERO_HASH,
            current_shuffling_seed=ZERO_HASH,

            # Finality
            previous_epoch_attestations=[],
            current_epoch_attestations=[],
            previous_justified_epoch=GENESIS_EPOCH - 1,
            current_justified_epoch=GENESIS_EPOCH,
            previous_justified_root=ZERO_HASH,
            current_justified_root=ZERO_HASH,
            justification_bitfield=0,
            finalized_epoch=GENESIS_EPOCH,
            finalized_root=ZERO_HASH,

            # Recent state
            latest_crosslinks=Vector([Crosslink(epoch=GENESIS_EPOCH, crosslink_data_root=ZERO_HASH) for _ in range(SHARD_COUNT)]),
            latest_block_roots=Vector([ZERO_HASH for _ in range(SLOTS_PER_HISTORICAL_ROOT)]),
            latest_state_roots=Vector([ZERO_HASH for _ in range(SLOTS_PER_HISTORICAL_ROOT)]),
            latest_active_index_roots=Vector([ZERO_HASH for _ in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH)]),
            latest_slashed_balances=Vector([0 for _ in range(LATEST_SLASHED_EXIT_LENGTH)]),
            latest_block_header=get_temporary_block_header(get_empty_block()),
            historical_roots=[],

            # Ethereum 1.0 chain data
            latest_eth1_data=genesis_eth1_data,
            eth1_data_votes=[],
            deposit_index=0,
        )

        # Process genesis deposits
        for deposit in genesis_validator_deposits:
            process_deposit(state, deposit)

        # Process genesis activations
        for validator_index, _ in enumerate(state.validator_registry):
            if get_effective_balance(state, validator_index) >= MAX_DEPOSIT_AMOUNT:
                activate_validator(state, validator_index, is_genesis=True)

        genesis_active_index_root = hash_tree_root(get_active_validator_indices(state.validator_registry, GENESIS_EPOCH))
        for index in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH):
            state.latest_active_index_roots[index] = genesis_active_index_root
        state.current_shuffling_seed = generate_seed(state, GENESIS_EPOCH)

        return state

Beacon chain processing
-----------------------

The beacon chain is the system chain for Ethereum 2.0. The main
responsibilities of the beacon chain are:

-  Store and maintain the registry of `validators <#dfn-validator>`__
-  Process crosslinks (see above)
-  Process its per-block consensus, as well as the finality gadget

Processing the beacon chain is similar to processing the Ethereum 1.0
chain. Clients download and process blocks, and maintain a view of what
is the current "canonical chain", terminating at the current "head".
However, because of the beacon chain's relationship with Ethereum 1.0,
and because it is a proof-of-stake chain, there are differences.

For a beacon chain block, ``block``, to be processed by a node, the
following conditions must be met:

-  The parent block with root ``block.previous_block_root`` has been
   processed and accepted.
-  An Ethereum 1.0 block pointed to by the
   ``state.latest_eth1_data.block_hash`` has been processed and
   accepted.
-  The node's Unix time is greater than or equal to
   ``state.genesis_time + (block.slot - GENESIS_SLOT) * SECONDS_PER_SLOT``.
   (Note that leap seconds mean that slots will occasionally last
   ``SECONDS_PER_SLOT + 1`` or ``SECONDS_PER_SLOT - 1`` seconds,
   possibly several times a year.)

If these conditions are not met, the client should delay processing the
beacon block until the conditions are all satisfied.

Beacon block production is significantly different because of the proof
of stake mechanism. A client simply checks what it thinks is the
canonical chain when it should create a block, and looks up what its
slot number is; when the slot arrives, it either proposes or attests to
a block as required. Note that this requires each node to have a clock
that is roughly (i.e. within ``SECONDS_PER_SLOT`` seconds) synchronized
with the other nodes.

Beacon chain fork choice rule
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The beacon chain fork choice rule is a hybrid that combines
justification and finality with Latest Message Driven (LMD) Greediest
Heaviest Observed SubTree (GHOST). At any point in time a
`validator <#dfn-validator>`__ ``v`` subjectively calculates the beacon
chain head as follows.

-  Abstractly define ``Store`` as the type of storage object for the
   chain data and ``store`` be the set of attestations and blocks that
   the `validator <#dfn-validator>`__ ``v`` has observed and verified
   (in particular, block ancestors must be recursively verified).
   Attestations not yet included in any chain are still included in
   ``store``.
-  Let ``finalized_head`` be the finalized block with the highest epoch.
   (A block ``B`` is finalized if there is a descendant of ``B`` in
   ``store`` the processing of which sets ``B`` as finalized.)
-  Let ``justified_head`` be the descendant of ``finalized_head`` with
   the highest epoch that has been justified for at least 1 epoch. (A
   block ``B`` is justified if there is a descendant of ``B`` in
   ``store`` the processing of which sets ``B`` as justified.) If no
   such descendant exists set ``justified_head`` to ``finalized_head``.
-  Let
   ``get_ancestor(store: Store, block: BeaconBlock, slot: Slot) -> BeaconBlock``
   be the ancestor of ``block`` with slot number ``slot``. The
   ``get_ancestor`` function can be defined recursively as:

.. code:: python

    def get_ancestor(store: Store, block: BeaconBlock, slot: Slot) -> BeaconBlock:
        """
        Get the ancestor of ``block`` with slot number ``slot``; return ``None`` if not found.
        """
        if block.slot == slot:
            return block
        elif block.slot < slot:
            return None
        else:
            return get_ancestor(store, store.get_parent(block), slot)

-  Let
   ``get_latest_attestation(store: Store, validator_index: ValidatorIndex) -> Attestation``
   be the attestation with the highest slot number in ``store`` from the
   validator with the given ``validator_index``. If several such
   attestations exist, use the one the `validator <#dfn-validator>`__
   ``v`` observed first.
-  Let
   ``get_latest_attestation_target(store: Store, validator_index: ValidatorIndex) -> BeaconBlock``
   be the target block in the attestation
   ``get_latest_attestation(store, validator_index)``.
-  Let
   ``get_children(store: Store, block: BeaconBlock) -> List[BeaconBlock]``
   returns the child blocks of the given ``block``.
-  Let ``justified_head_state`` be the resulting ``BeaconState`` object
   from processing the chain up to the ``justified_head``.
-  The ``head`` is
   ``lmd_ghost(store, justified_head_state, justified_head)`` where the
   function ``lmd_ghost`` is defined below. Note that the implementation
   below is suboptimal; there are implementations that compute the head
   in time logarithmic in slot count.

.. code:: python

    def lmd_ghost(store: Store, start_state: BeaconState, start_block: BeaconBlock) -> BeaconBlock:
        """
        Execute the LMD-GHOST algorithm to find the head ``BeaconBlock``.
        """
        validators = start_state.validator_registry
        active_validator_indices = get_active_validator_indices(validators, slot_to_epoch(start_state.slot))
        attestation_targets = [
            (validator_index, get_latest_attestation_target(store, validator_index))
            for validator_index in active_validator_indices
        ]

        # Use the rounded-balance-with-hysteresis supplied by the protocol for fork
        # choice voting. This reduces the number of recomputations that need to be
        # made for optimized implementations that precompute and save data
        def get_vote_count(block: BeaconBlock) -> int:
            return sum(
                start_state.validator_registry[validator_index].high_balance
                for validator_index, target in attestation_targets
                if get_ancestor(store, target, block.slot) == block
            )

        head = start_block
        while 1:
            children = get_children(store, head)
            if len(children) == 0:
                return head
            head = max(children, key=lambda x: (get_vote_count(x), hash_tree_root(x)))

Beacon chain state transition function
--------------------------------------

We now define the state transition function. At a high level the state
transition is made up of four parts:

1. State caching, which happens at the start of every slot.
2. The per-epoch transitions, which happens at the start of the first
   slot of every epoch.
3. The per-slot transitions, which happens at every slot.
4. The per-block transitions, which happens at every block.

Transition section notes: \* The state caching, caches the state root of
the previous slot. \* The per-epoch transitions focus on the
`validator <#dfn-validator>`__ registry, including adjusting balances
and activating and exiting `validators <#dfn-validator>`__, as well as
processing crosslinks and managing block justification/finalization. \*
The per-slot transitions focus on the slot counter and block roots
records updates. \* The per-block transitions generally focus on
verifying aggregate signatures and saving temporary records relating to
the per-block activity in the ``BeaconState``.

Beacon blocks that trigger unhandled Python exceptions (e.g.
out-of-range list accesses) and failed ``assert``\ s during the state
transition are considered invalid.

*Note*: If there are skipped slots between a block and its parent block,
run the steps in the `state-root <#state-caching>`__,
`per-epoch <#per-epoch-processing>`__, and
`per-slot <#per-slot-processing>`__ sections once for each skipped slot
and then once for the slot containing the new block.

State caching
~~~~~~~~~~~~~

At every ``slot > GENESIS_SLOT`` run the following function:

.. code:: python

    def cache_state(state: BeaconState) -> None:
        previous_slot_state_root = hash_tree_root(state)

        # store the previous slot's post state transition root
        state.latest_state_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_slot_state_root

        # cache state root in stored latest_block_header if empty
        if state.latest_block_header.state_root == ZERO_HASH:
            state.latest_block_header.state_root = previous_slot_state_root

        # store latest known block for previous slot
        state.latest_block_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = hash_tree_root(state.latest_block_header)

Per-epoch processing
~~~~~~~~~~~~~~~~~~~~

The steps below happen when
``state.slot > GENESIS_SLOT and (state.slot + 1) % SLOTS_PER_EPOCH == 0``.

Helper functions
^^^^^^^^^^^^^^^^

We define some helper functions utilized when processing an epoch
transition:

.. code:: python

    def get_current_total_balance(state: BeaconState) -> Gwei:
        return get_total_balance(state, get_active_validator_indices(state.validator_registry, get_current_epoch(state)))

.. code:: python

    def get_previous_total_balance(state: BeaconState) -> Gwei:
        return get_total_balance(state, get_active_validator_indices(state.validator_registry, get_previous_epoch(state)))

.. code:: python

    def get_attesting_indices(state: BeaconState, attestations: List[PendingAttestation]) -> List[ValidatorIndex]:
        output = set()
        for a in attestations:
            output = output.union(get_attestation_participants(state, a.data, a.aggregation_bitfield))
        return sorted(list(output))

.. code:: python

    def get_attesting_balance(state: BeaconState, attestations: List[PendingAttestation]) -> Gwei:
        return get_total_balance(state, get_attesting_indices(state, attestations))

.. code:: python

    def get_current_epoch_boundary_attestations(state: BeaconState) -> List[PendingAttestation]:
        return [
            a for a in state.current_epoch_attestations
            if a.data.target_root == get_block_root(state, get_epoch_start_slot(get_current_epoch(state)))
        ]

.. code:: python

    def get_previous_epoch_boundary_attestations(state: BeaconState) -> List[PendingAttestation]:
        return [
            a for a in state.previous_epoch_attestations
            if a.data.target_root == get_block_root(state, get_epoch_start_slot(get_previous_epoch(state)))
        ]

.. code:: python

    def get_previous_epoch_matching_head_attestations(state: BeaconState) -> List[PendingAttestation]:
        return [
            a for a in state.previous_epoch_attestations
            if a.data.beacon_block_root == get_block_root(state, a.data.slot)
        ]

**Note**: Total balances computed for the previous epoch might be
marginally different than the actual total balances during the previous
epoch transition. Due to the tight bound on validator churn each epoch
and small per-epoch rewards/penalties, the potential balance difference
is very low and only marginally affects consensus safety.

.. code:: python

    def get_winning_root_and_participants(state: BeaconState, shard: Shard) -> Tuple[Bytes32, List[ValidatorIndex]]:
        all_attestations = state.current_epoch_attestations + state.previous_epoch_attestations
        valid_attestations = [
            a for a in all_attestations if a.data.previous_crosslink == state.latest_crosslinks[shard]
        ]
        all_roots = [a.data.crosslink_data_root for a in valid_attestations]

        # handle when no attestations for shard available
        if len(all_roots) == 0:
            return ZERO_HASH, []

        def get_attestations_for(root) -> List[PendingAttestation]:
            return [a for a in valid_attestations if a.data.crosslink_data_root == root]

        # Winning crosslink root is the root with the most votes for it, ties broken in favor of
        # lexicographically higher hash
        winning_root = max(all_roots, key=lambda r: (get_attesting_balance(state, get_attestations_for(r)), r))

        return winning_root, get_attesting_indices(state, get_attestations_for(winning_root))

.. code:: python

    def earliest_attestation(state: BeaconState, validator_index: ValidatorIndex) -> PendingAttestation:
        return min([
            a for a in state.previous_epoch_attestations if
            validator_index in get_attestation_participants(state, a.data, a.aggregation_bitfield)
        ], key=lambda a: a.inclusion_slot)

.. code:: python

    def inclusion_slot(state: BeaconState, validator_index: ValidatorIndex) -> Slot:
        return earliest_attestation(state, validator_index).inclusion_slot

.. code:: python

    def inclusion_distance(state: BeaconState, validator_index: ValidatorIndex) -> int:
        attestation = earliest_attestation(state, validator_index)
        return attestation.inclusion_slot - attestation.data.slot

Justification
^^^^^^^^^^^^^

Run the following function:

.. code:: python

    def update_justification_and_finalization(state: BeaconState) -> None:
        new_justified_epoch = state.current_justified_epoch
        new_finalized_epoch = state.finalized_epoch

        # Rotate the justification bitfield up one epoch to make room for the current epoch
        state.justification_bitfield <<= 1
        # If the previous epoch gets justified, fill the second last bit
        previous_boundary_attesting_balance = get_attesting_balance(state, get_previous_epoch_boundary_attestations(state))
        if previous_boundary_attesting_balance * 3 >= get_previous_total_balance(state) * 2:
            new_justified_epoch = get_current_epoch(state) - 1
            state.justification_bitfield |= 2
        # If the current epoch gets justified, fill the last bit
        current_boundary_attesting_balance = get_attesting_balance(state, get_current_epoch_boundary_attestations(state))
        if current_boundary_attesting_balance * 3 >= get_current_total_balance(state) * 2:
            new_justified_epoch = get_current_epoch(state)
            state.justification_bitfield |= 1

        # Process finalizations
        bitfield = state.justification_bitfield
        current_epoch = get_current_epoch(state)
        # The 2nd/3rd/4th most recent epochs are all justified, the 2nd using the 4th as source
        if (bitfield >> 1) % 8 == 0b111 and state.previous_justified_epoch == current_epoch - 3:
            new_finalized_epoch = state.previous_justified_epoch
        # The 2nd/3rd most recent epochs are both justified, the 2nd using the 3rd as source
        if (bitfield >> 1) % 4 == 0b11 and state.previous_justified_epoch == current_epoch - 2:
            new_finalized_epoch = state.previous_justified_epoch
        # The 1st/2nd/3rd most recent epochs are all justified, the 1st using the 3rd as source
        if (bitfield >> 0) % 8 == 0b111 and state.current_justified_epoch == current_epoch - 2:
            new_finalized_epoch = state.current_justified_epoch
        # The 1st/2nd most recent epochs are both justified, the 1st using the 2nd as source
        if (bitfield >> 0) % 4 == 0b11 and state.current_justified_epoch == current_epoch - 1:
            new_finalized_epoch = state.current_justified_epoch

        # Update state jusification/finality fields
        state.previous_justified_epoch = state.current_justified_epoch
        state.previous_justified_root = state.current_justified_root
        if new_justified_epoch != state.current_justified_epoch:
            state.current_justified_epoch = new_justified_epoch
            state.current_justified_root = get_block_root(state, get_epoch_start_slot(new_justified_epoch))
        if new_finalized_epoch != state.finalized_epoch:
            state.finalized_epoch = new_finalized_epoch
            state.finalized_root = get_block_root(state, get_epoch_start_slot(new_finalized_epoch))

Crosslinks
^^^^^^^^^^

Run the following function:

.. code:: python

    def process_crosslinks(state: BeaconState) -> None:
        current_epoch = get_current_epoch(state)
        previous_epoch = current_epoch - 1
        next_epoch = current_epoch + 1
        for slot in range(get_epoch_start_slot(previous_epoch), get_epoch_start_slot(next_epoch)):
            for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
                winning_root, participants = get_winning_root_and_participants(state, shard)
                participating_balance = get_total_balance(state, participants)
                total_balance = get_total_balance(state, crosslink_committee)
                if 3 * participating_balance >= 2 * total_balance:
                    state.latest_crosslinks[shard] = Crosslink(
                        epoch=slot_to_epoch(slot),
                        crosslink_data_root=winning_root
                    )

Eth1 data
^^^^^^^^^

Run the following function:

.. code:: python

    def maybe_reset_eth1_period(state: BeaconState) -> None:
        if (get_current_epoch(state) + 1) % EPOCHS_PER_ETH1_VOTING_PERIOD == 0:
            for eth1_data_vote in state.eth1_data_votes:
                # If a majority of all votes were for a particular eth1_data value,
                # then set that as the new canonical value
                if eth1_data_vote.vote_count * 2 > EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH:
                    state.latest_eth1_data = eth1_data_vote.eth1_data
            state.eth1_data_votes = []

Rewards and penalties
^^^^^^^^^^^^^^^^^^^^^

First, we define some additional helpers:

.. code:: python

    def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
        if get_previous_total_balance(state) == 0:
            return 0

        adjusted_quotient = integer_squareroot(get_previous_total_balance(state)) // BASE_REWARD_QUOTIENT
        return get_effective_balance(state, index) // adjusted_quotient // 5

.. code:: python

    def get_inactivity_penalty(state: BeaconState, index: ValidatorIndex, epochs_since_finality: int) -> Gwei:
        return (
            get_base_reward(state, index) +
            get_effective_balance(state, index) * epochs_since_finality // INACTIVITY_PENALTY_QUOTIENT // 2
        )

Note: When applying penalties in the following balance recalculations
implementers should make sure the ``uint64`` does not underflow.

Justification and finalization
''''''''''''''''''''''''''''''

.. code:: python

    def get_justification_and_finalization_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
        epochs_since_finality = get_current_epoch(state) + 1 - state.finalized_epoch
        if epochs_since_finality <= 4:
            return compute_normal_justification_and_finalization_deltas(state)
        else:
            return compute_inactivity_leak_deltas(state)

When blocks are finalizing normally...

.. code:: python

    def compute_normal_justification_and_finalization_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
        # deltas[0] for rewards
        # deltas[1] for penalties
        deltas = [
            [0 for index in range(len(state.validator_registry))],
            [0 for index in range(len(state.validator_registry))]
        ]
        # Some helper variables
        boundary_attestations = get_previous_epoch_boundary_attestations(state)
        boundary_attesting_balance = get_attesting_balance(state, boundary_attestations)
        total_balance = get_previous_total_balance(state)
        total_attesting_balance = get_attesting_balance(state, state.previous_epoch_attestations)
        matching_head_attestations = get_previous_epoch_matching_head_attestations(state)
        matching_head_balance = get_attesting_balance(state, matching_head_attestations)
        # Process rewards or penalties for all validators
        for index in get_active_validator_indices(state.validator_registry, get_previous_epoch(state)):
            # Expected FFG source
            if index in get_attesting_indices(state, state.previous_epoch_attestations):
                deltas[0][index] += get_base_reward(state, index) * total_attesting_balance // total_balance
                # Inclusion speed bonus
                deltas[0][index] += (
                    get_base_reward(state, index) * MIN_ATTESTATION_INCLUSION_DELAY //
                    inclusion_distance(state, index)
                )
            else:
                deltas[1][index] += get_base_reward(state, index)
            # Expected FFG target
            if index in get_attesting_indices(state, boundary_attestations):
                deltas[0][index] += get_base_reward(state, index) * boundary_attesting_balance // total_balance
            else:
                deltas[1][index] += get_base_reward(state, index)
            # Expected head
            if index in get_attesting_indices(state, matching_head_attestations):
                deltas[0][index] += get_base_reward(state, index) * matching_head_balance // total_balance
            else:
                deltas[1][index] += get_base_reward(state, index)
            # Proposer bonus
            if index in get_attesting_indices(state, state.previous_epoch_attestations):
                proposer_index = get_beacon_proposer_index(state, inclusion_slot(state, index))
                deltas[0][proposer_index] += get_base_reward(state, index) // ATTESTATION_INCLUSION_REWARD_QUOTIENT
        return deltas

When blocks are not finalizing normally...

.. code:: python

    def compute_inactivity_leak_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
        # deltas[0] for rewards
        # deltas[1] for penalties
        deltas = [
            [0 for index in range(len(state.validator_registry))],
            [0 for index in range(len(state.validator_registry))]
        ]
        boundary_attestations = get_previous_epoch_boundary_attestations(state)
        matching_head_attestations = get_previous_epoch_matching_head_attestations(state)
        active_validator_indices = get_active_validator_indices(state.validator_registry, get_previous_epoch(state))
        epochs_since_finality = get_current_epoch(state) + 1 - state.finalized_epoch
        for index in active_validator_indices:
            if index not in get_attesting_indices(state, state.previous_epoch_attestations):
                deltas[1][index] += get_inactivity_penalty(state, index, epochs_since_finality)
            else:
                # If a validator did attest, apply a small penalty for getting attestations included late
                deltas[0][index] += (
                    get_base_reward(state, index) * MIN_ATTESTATION_INCLUSION_DELAY //
                    inclusion_distance(state, index)
                )
                deltas[1][index] += get_base_reward(state, index)
            if index not in get_attesting_indices(state, boundary_attestations):
                deltas[1][index] += get_inactivity_penalty(state, index, epochs_since_finality)
            if index not in get_attesting_indices(state, matching_head_attestations):
                deltas[1][index] += get_base_reward(state, index)
        # Penalize slashed-but-inactive validators as though they were active but offline
        for index in range(len(state.validator_registry)):
            eligible = (
                index not in active_validator_indices and
                state.validator_registry[index].slashed and
                get_current_epoch(state) < state.validator_registry[index].withdrawable_epoch
            )
            if eligible:
                deltas[1][index] += (
                    2 * get_inactivity_penalty(state, index, epochs_since_finality) +
                    get_base_reward(state, index)
                )
        return deltas

Crosslinks
''''''''''

.. code:: python

    def get_crosslink_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
        rewards = [0 for index in range(len(state.validator_registry))]
        penalties = [0 for index in range(len(state.validator_registry))]
        previous_epoch_start_slot = get_epoch_start_slot(get_previous_epoch(state))
        current_epoch_start_slot = get_epoch_start_slot(get_current_epoch(state))
        for slot in range(previous_epoch_start_slot, current_epoch_start_slot):
            for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
                winning_root, participants = get_winning_root_and_participants(state, shard)
                participating_balance = get_total_balance(state, participants)
                total_balance = get_total_balance(state, crosslink_committee)
                for index in crosslink_committee:
                    if index in participants:
                        rewards[index] += get_base_reward(state, index) * participating_balance // total_balance
                    else:
                        penalties[index] += get_base_reward(state, index)
        return [rewards, penalties]

Apply rewards
^^^^^^^^^^^^^

Run the following:

.. code:: python

    def apply_rewards(state: BeaconState) -> None:
        rewards1, penalties1 = get_justification_and_finalization_deltas(state)
        rewards2, penalties2 = get_crosslink_deltas(state)
        for i in range(len(state.validator_registry)):
            set_balance(
                state,
                i,
                max(
                    0,
                    get_balance(state, i) + rewards1[i] + rewards2[i] - penalties1[i] - penalties2[i],
                ),
            )

Ejections
^^^^^^^^^

Run ``process_ejections(state)``.

.. code:: python

    def process_ejections(state: BeaconState) -> None:
        """
        Iterate through the validator registry
        and eject active validators with balance below ``EJECTION_BALANCE``.
        """
        for index in get_active_validator_indices(state.validator_registry, get_current_epoch(state)):
            if get_balance(state, index) < EJECTION_BALANCE:
                initiate_validator_exit(state, index)

Validator registry and shuffling seed data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    def should_update_validator_registry(state: BeaconState) -> bool:
        # Must have finalized a new block
        if state.finalized_epoch <= state.validator_registry_update_epoch:
            return False
        # Must have processed new crosslinks on all shards of the current epoch
        shards_to_check = [
            (state.current_shuffling_start_shard + i) % SHARD_COUNT
            for i in range(get_current_epoch_committee_count(state))
        ]
        for shard in shards_to_check:
            if state.latest_crosslinks[shard].epoch <= state.validator_registry_update_epoch:
                return False
        return True

.. code:: python

    def update_validator_registry(state: BeaconState) -> None:
        """
        Update validator registry.
        Note that this function mutates ``state``.
        """
        current_epoch = get_current_epoch(state)
        # The active validators
        active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
        # The total effective balance of active validators
        total_balance = get_total_balance(state, active_validator_indices)

        # The maximum balance churn in Gwei (for deposits and exits separately)
        max_balance_churn = max(
            MAX_DEPOSIT_AMOUNT,
            total_balance // (2 * MAX_BALANCE_CHURN_QUOTIENT)
        )

        # Activate validators within the allowable balance churn
        balance_churn = 0
        for index, validator in enumerate(state.validator_registry):
            if validator.activation_epoch == FAR_FUTURE_EPOCH and get_balance(state, index) >= MAX_DEPOSIT_AMOUNT:
                # Check the balance churn would be within the allowance
                balance_churn += get_effective_balance(state, index)
                if balance_churn > max_balance_churn:
                    break

                # Activate validator
                activate_validator(state, index, is_genesis=False)

        # Exit validators within the allowable balance churn
        if current_epoch < state.validator_registry_update_epoch + LATEST_SLASHED_EXIT_LENGTH:
            balance_churn = (
                state.latest_slashed_balances[state.validator_registry_update_epoch % LATEST_SLASHED_EXIT_LENGTH] -
                state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
            )

            for index, validator in enumerate(state.validator_registry):
                if validator.exit_epoch == FAR_FUTURE_EPOCH and validator.initiated_exit:
                    # Check the balance churn would be within the allowance
                    balance_churn += get_effective_balance(state, index)
                    if balance_churn > max_balance_churn:
                        break

                    # Exit validator
                    exit_validator(state, index)

        state.validator_registry_update_epoch = current_epoch

Run the following function:

.. code:: python

    def update_registry_and_shuffling_data(state: BeaconState) -> None:
        # First set previous shuffling data to current shuffling data
        state.previous_shuffling_epoch = state.current_shuffling_epoch
        state.previous_shuffling_start_shard = state.current_shuffling_start_shard
        state.previous_shuffling_seed = state.current_shuffling_seed
        current_epoch = get_current_epoch(state)
        next_epoch = current_epoch + 1
        # Check if we should update, and if so, update
        if should_update_validator_registry(state):
            update_validator_registry(state)
            # If we update the registry, update the shuffling data and shards as well
            state.current_shuffling_epoch = next_epoch
            state.current_shuffling_start_shard = (
                state.current_shuffling_start_shard +
                get_current_epoch_committee_count(state) % SHARD_COUNT
            )
            state.current_shuffling_seed = generate_seed(state, state.current_shuffling_epoch)
        else:
            # If processing at least one crosslink keeps failing, then reshuffle every power of two,
            # but don't update the current_shuffling_start_shard
            epochs_since_last_registry_update = current_epoch - state.validator_registry_update_epoch
            if epochs_since_last_registry_update > 1 and is_power_of_two(epochs_since_last_registry_update):
                state.current_shuffling_epoch = next_epoch
                state.current_shuffling_seed = generate_seed(state, state.current_shuffling_epoch)

**Invariant**: the active index root that is hashed into the shuffling
seed actually is the ``hash_tree_root`` of the validator set that is
used for that epoch.

Slashings and exit queue
^^^^^^^^^^^^^^^^^^^^^^^^

Run ``process_slashings(state)`` and ``process_exit_queue(state)``:

.. code:: python

    def process_slashings(state: BeaconState) -> None:
        """
        Process the slashings.
        Note that this function mutates ``state``.
        """
        current_epoch = get_current_epoch(state)
        active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
        total_balance = get_total_balance(state, active_validator_indices)

        # Compute `total_penalties`
        total_at_start = state.latest_slashed_balances[(current_epoch + 1) % LATEST_SLASHED_EXIT_LENGTH]
        total_at_end = state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
        total_penalties = total_at_end - total_at_start

        for index, validator in enumerate(state.validator_registry):
            if validator.slashed and current_epoch == validator.withdrawable_epoch - LATEST_SLASHED_EXIT_LENGTH // 2:
                penalty = max(
                    get_effective_balance(state, index) * min(total_penalties * 3, total_balance) // total_balance,
                    get_effective_balance(state, index) // MIN_PENALTY_QUOTIENT
                )
                decrease_balance(state, index, penalty)

.. code:: python

    def process_exit_queue(state: BeaconState) -> None:
        """
        Process the exit queue.
        Note that this function mutates ``state``.
        """
        def eligible(index):
            validator = state.validator_registry[index]
            # Filter out dequeued validators
            if validator.withdrawable_epoch != FAR_FUTURE_EPOCH:
                return False
            # Dequeue if the minimum amount of time has passed
            else:
                return get_current_epoch(state) >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY

        eligible_indices = filter(eligible, list(range(len(state.validator_registry))))
        # Sort in order of exit epoch, and validators that exit within the same epoch exit in order of validator index
        sorted_indices = sorted(eligible_indices, key=lambda index: state.validator_registry[index].exit_epoch)
        for dequeues, index in enumerate(sorted_indices):
            if dequeues >= MAX_EXIT_DEQUEUES_PER_EPOCH:
                break
            prepare_validator_for_withdrawal(state, index)

Final updates
^^^^^^^^^^^^^

Run the following function:

.. code:: python

    def finish_epoch_update(state: BeaconState) -> None:
        current_epoch = get_current_epoch(state)
        next_epoch = current_epoch + 1
        # Set active index root
        index_root_position = (next_epoch + ACTIVATION_EXIT_DELAY) % LATEST_ACTIVE_INDEX_ROOTS_LENGTH
        state.latest_active_index_roots[index_root_position] = hash_tree_root(
            get_active_validator_indices(state.validator_registry, next_epoch + ACTIVATION_EXIT_DELAY)
        )
        # Set total slashed balances
        state.latest_slashed_balances[next_epoch % LATEST_SLASHED_EXIT_LENGTH] = (
            state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
        )
        # Set randao mix
        state.latest_randao_mixes[next_epoch % LATEST_RANDAO_MIXES_LENGTH] = get_randao_mix(state, current_epoch)
        # Set historical root accumulator
        if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
            historical_batch = HistoricalBatch(
                block_roots=state.latest_block_roots,
                state_roots=state.latest_state_roots,
            )
            state.historical_roots.append(hash_tree_root(historical_batch))
        # Rotate current/previous epoch attestations
        state.previous_epoch_attestations = state.current_epoch_attestations
        state.current_epoch_attestations = []

Per-slot processing
~~~~~~~~~~~~~~~~~~~

At every ``slot > GENESIS_SLOT`` run the following function:

.. code:: python

    def advance_slot(state: BeaconState) -> None:
        state.slot += 1

Per-block processing
~~~~~~~~~~~~~~~~~~~~

For every ``block`` except the genesis block, run
``process_block_header(state, block)``, ``process_randao(state, block)``
and ``process_eth1_data(state, block)``.

Block header
^^^^^^^^^^^^

.. code:: python

    def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
        # Verify that the slots match
        assert block.slot == state.slot
        # Verify that the parent matches
        assert block.previous_block_root == hash_tree_root(state.latest_block_header)
        # Save current block as the new latest block
        state.latest_block_header = get_temporary_block_header(block)
        # Verify proposer is not slashed
        proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]
        assert not proposer.slashed
        # Verify proposer signature
        assert bls_verify(
            pubkey=proposer.pubkey,
            message_hash=signed_root(block),
            signature=block.signature,
            domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_BEACON_BLOCK)
        )

RANDAO
^^^^^^

.. code:: python

    def process_randao(state: BeaconState, block: BeaconBlock) -> None:
        proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]
        # Verify that the provided randao value is valid
        assert bls_verify(
            pubkey=proposer.pubkey,
            message_hash=hash_tree_root(get_current_epoch(state)),
            signature=block.body.randao_reveal,
            domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_RANDAO)
        )
        # Mix it in
        state.latest_randao_mixes[get_current_epoch(state) % LATEST_RANDAO_MIXES_LENGTH] = (
            xor(get_randao_mix(state, get_current_epoch(state)),
                hash(block.body.randao_reveal))
        )

Eth1 data
^^^^^^^^^

.. code:: python

    def process_eth1_data(state: BeaconState, block: BeaconBlock) -> None:
        for eth1_data_vote in state.eth1_data_votes:
            # If someone else has already voted for the same hash, add to its counter
            if eth1_data_vote.eth1_data == block.body.eth1_data:
                eth1_data_vote.vote_count += 1
                return
        # If we're seeing this hash for the first time, make a new counter
        state.eth1_data_votes.append(Eth1DataVote(eth1_data=block.body.eth1_data, vote_count=1))

Transactions
^^^^^^^^^^^^

Proposer slashings
''''''''''''''''''

Verify that
``len(block.body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS``.

For each ``proposer_slashing`` in ``block.body.proposer_slashings``, run
the following function:

.. code:: python

    def process_proposer_slashing(state: BeaconState,
                                  proposer_slashing: ProposerSlashing) -> None:
        """
        Process ``ProposerSlashing`` transaction.
        Note that this function mutates ``state``.
        """
        proposer = state.validator_registry[proposer_slashing.proposer_index]
        # Verify that the epoch is the same
        assert slot_to_epoch(proposer_slashing.header_1.slot) == slot_to_epoch(proposer_slashing.header_2.slot)
        # But the headers are different
        assert proposer_slashing.header_1 != proposer_slashing.header_2
        # Check proposer is slashable
        assert is_slashable_validator(proposer, get_current_epoch(state))
        # Signatures are valid
        for header in (proposer_slashing.header_1, proposer_slashing.header_2):
            assert bls_verify(
                pubkey=proposer.pubkey,
                message_hash=signed_root(header),
                signature=header.signature,
                domain=get_domain(state.fork, slot_to_epoch(header.slot), DOMAIN_BEACON_BLOCK)
            )
        slash_validator(state, proposer_slashing.proposer_index)

Attester slashings
''''''''''''''''''

Verify that
``len(block.body.attester_slashings) <= MAX_ATTESTER_SLASHINGS``.

For each ``attester_slashing`` in ``block.body.attester_slashings``, run
the following function:

.. code:: python

    def process_attester_slashing(state: BeaconState,
                                  attester_slashing: AttesterSlashing) -> None:
        """
        Process ``AttesterSlashing`` transaction.
        Note that this function mutates ``state``.
        """
        attestation1 = attester_slashing.slashable_attestation_1
        attestation2 = attester_slashing.slashable_attestation_2
        # Check that the attestations are conflicting
        assert attestation1.data != attestation2.data
        assert (
            is_double_vote(attestation1.data, attestation2.data) or
            is_surround_vote(attestation1.data, attestation2.data)
        )
        assert verify_slashable_attestation(state, attestation1)
        assert verify_slashable_attestation(state, attestation2)
        slashable_indices = [
            index for index in attestation1.validator_indices
            if (
                index in attestation2.validator_indices and
                is_slashable_validator(state.validator_registry[index], get_current_epoch(state))
            )
        ]
        assert len(slashable_indices) >= 1
        for index in slashable_indices:
            slash_validator(state, index)

Attestations
''''''''''''

Verify that ``len(block.body.attestations) <= MAX_ATTESTATIONS``.

For each ``attestation`` in ``block.body.attestations``, run the
following function:

.. code:: python

    def process_attestation(state: BeaconState, attestation: Attestation) -> None:
        """
        Process ``Attestation`` transaction.
        Note that this function mutates ``state``.
        """
        assert max(GENESIS_SLOT, state.slot - SLOTS_PER_EPOCH) <= attestation.data.slot
        assert attestation.data.slot <= state.slot - MIN_ATTESTATION_INCLUSION_DELAY

        # Check target epoch, source epoch, and source root
        target_epoch = slot_to_epoch(attestation.data.slot)
        assert (target_epoch, attestation.data.source_epoch, attestation.data.source_root) in {
            (get_current_epoch(state), state.current_justified_epoch, state.current_justified_root), 
            (get_previous_epoch(state), state.previous_justified_epoch, state.previous_justified_root),
        }

        # Check crosslink data
        assert attestation.data.crosslink_data_root == ZERO_HASH  # [to be removed in phase 1]
        assert state.latest_crosslinks[attestation.data.shard] in {
            attestation.data.previous_crosslink,  # Case 1: latest crosslink matches previous crosslink
            Crosslink(                            # Case 2: latest crosslink matches current crosslink
                crosslink_data_root=attestation.data.crosslink_data_root,
                epoch=target_epoch,
            ),
        }

        # Check custody bits [to be generalised in phase 1]
        assert attestation.custody_bitfield == b'\x00' * len(attestation.custody_bitfield)

        # Check aggregate signature [to be generalised in phase 1]
        participants = get_attestation_participants(state, attestation.data, attestation.aggregation_bitfield)
        assert len(participants) != 0
        assert bls_verify(
            pubkey=bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in participants]),
            message_hash=hash_tree_root(AttestationDataAndCustodyBit(data=attestation.data, custody_bit=0b0)),
            signature=attestation.aggregate_signature,
            domain=get_domain(state.fork, target_epoch, DOMAIN_ATTESTATION),
        )

        # Cache pending attestation
        pending_attestation = PendingAttestation(
            data=attestation.data,
            aggregation_bitfield=attestation.aggregation_bitfield,
            custody_bitfield=attestation.custody_bitfield,
            inclusion_slot=state.slot
        )
        if target_epoch == get_current_epoch(state):
            state.current_epoch_attestations.append(pending_attestation)
        else:
            state.previous_epoch_attestations.append(pending_attestation)

Deposits
''''''''

Verify that
``len(block.body.deposits) == min(MAX_DEPOSITS, latest_eth1_data.deposit_count - state.deposit_index)``.

For each ``deposit`` in ``block.body.deposits``, run
``process_deposit(state, deposit)``.

Voluntary exits
'''''''''''''''

Verify that ``len(block.body.voluntary_exits) <= MAX_VOLUNTARY_EXITS``.

For each ``exit`` in ``block.body.voluntary_exits``, run the following
function:

.. code:: python

    def process_voluntary_exit(state: BeaconState, exit: VoluntaryExit) -> None:
        """
        Process ``VoluntaryExit`` transaction.
        Note that this function mutates ``state``.
        """
        validator = state.validator_registry[exit.validator_index]
        # Verify the validator is active
        assert is_active_validator(validator, get_current_epoch(state))
        # Verify the validator has not yet exited
        assert validator.exit_epoch == FAR_FUTURE_EPOCH
        # Verify the validator has not initiated an exit
        assert validator.initiated_exit is False
        # Exits must specify an epoch when they become valid; they are not valid before then
        assert get_current_epoch(state) >= exit.epoch
        # Verify the validator has been active long enough
        assert get_current_epoch(state) - validator.activation_epoch >= PERSISTENT_COMMITTEE_PERIOD
        # Verify signature
        assert bls_verify(
            pubkey=validator.pubkey,
            message_hash=signed_root(exit),
            signature=exit.signature,
            domain=get_domain(state.fork, exit.epoch, DOMAIN_VOLUNTARY_EXIT)
        )
        # Initiate exit
        initiate_validator_exit(state, exit.validator_index)

Transfers
'''''''''

Note: Transfers are a temporary functionality for phases 0 and 1, to be
removed in phase 2.

Verify that ``len(block.body.transfers) <= MAX_TRANSFERS`` and that all
transfers are distinct.

For each ``transfer`` in ``block.body.transfers``, run the following
function:

.. code:: python

    def process_transfer(state: BeaconState, transfer: Transfer) -> None:
        """
        Process ``Transfer`` transaction.
        Note that this function mutates ``state``.
        """
        # Verify the amount and fee aren't individually too big (for anti-overflow purposes)
        assert get_balance(state, transfer.sender) >= max(transfer.amount, transfer.fee)
        # Verify that we have enough ETH to send, and that after the transfer the balance will be either
        # exactly zero or at least MIN_DEPOSIT_AMOUNT
        assert (
            get_balance(state, transfer.sender) == transfer.amount + transfer.fee or
            get_balance(state, transfer.sender) >= transfer.amount + transfer.fee + MIN_DEPOSIT_AMOUNT
        )
        # A transfer is valid in only one slot
        assert state.slot == transfer.slot
        # Only withdrawn or not-yet-deposited accounts can transfer
        assert (
            get_current_epoch(state) >= state.validator_registry[transfer.sender].withdrawable_epoch or
            state.validator_registry[transfer.sender].activation_epoch == FAR_FUTURE_EPOCH
        )
        # Verify that the pubkey is valid
        assert (
            state.validator_registry[transfer.sender].withdrawal_credentials ==
            BLS_WITHDRAWAL_PREFIX_BYTE + hash(transfer.pubkey)[1:]
        )
        # Verify that the signature is valid
        assert bls_verify(
            pubkey=transfer.pubkey,
            message_hash=signed_root(transfer),
            signature=transfer.signature,
            domain=get_domain(state.fork, slot_to_epoch(transfer.slot), DOMAIN_TRANSFER)
        )
        # Process the transfer
        decrease_balance(state, transfer.sender, transfer.amount + transfer.fee)
        increase_balance(state, transfer.recipient, transfer.amount)
        increase_balance(state, get_beacon_proposer_index(state, state.slot), transfer.fee)

State root verification
^^^^^^^^^^^^^^^^^^^^^^^

Verify the block's ``state_root`` by running the following function:

.. code:: python

    def verify_block_state_root(state: BeaconState, block: BeaconBlock) -> None:
        assert block.state_root == hash_tree_root(state)

References
==========

This section is divided into Normative and Informative references.
Normative references are those that must be read in order to implement
this specification, while Informative references are merely that,
information. An example of the former might be the details of a required
consensus algorithm, and an example of the latter might be a pointer to
research that demonstrates why a particular consensus algorithm might be
better suited for inclusion in the standard than another.

Normative
---------

Informative
-----------

.. _casper-ffg:

**casper-ffg**   *Casper the Friendly Finality Gadget*. V. Buterin and V. Griffith. URL: https://arxiv.org/abs/1710.09437

.. _python-poc:

**python-poc**  *Python proof-of-concept implementation*. Ethereum Foundation. URL: https://github.com/ethereum/beacon\_chain

Copyright
=========

Copyright and related rights waived via
`CC0 <https://creativecommons.org/publicdomain/zero/1.0/>`__.
