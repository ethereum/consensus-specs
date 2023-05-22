from ruamel.yaml import YAML
from dataclasses import dataclass, field
from typing import Dict, Optional
yaml = YAML()


class StateID(str):

    @classmethod
    def Root(cls, root):
        return cls(f"root:{root.hex()}")

    @classmethod
    def Slot(cls, slot):
        return cls(f"slot:{slot}")

    @classmethod
    def Head(cls):
        return cls("head")

    @classmethod
    def Genesis(cls):
        return cls("genesis")

    @classmethod
    def Finalized(cls):
        return cls("finalized")

    @classmethod
    def Justified(cls):
        return cls("justified")


@dataclass
class EthV2DebugBeaconStates:
    id: StateID = StateID.Head()
    fields: Dict = field(default_factory=dict)

    def __post_init__(self):
        self.id = str(self.id)

    # Common Attributes
    def state_root(self, state_root):
        self.fields["state_root"] = state_root.hex()
        return self

    def slot(self, slot):
        self.fields["slot"] = int(slot)
        return self

    def genesis_time(self, genesis_time):
        self.fields["genesis_time"] = int(genesis_time)
        return self

    def genesis_validators_root(self, genesis_validators_root):
        self.fields["genesis_validators_root"] = str(genesis_validators_root)
        return self

    def fork(self, fork):
        self.fields["fork"] = {
            "previous_version": fork.previous_version.hex(),
            "current_version": fork.current_version.hex(),
            "epoch": int(fork.epoch),
        }
        return self

    def latest_block_header(self, latest_block_header):
        self.fields["latest_block_header"] = {
            "slot": int(latest_block_header.slot),
            "proposer_index": int(latest_block_header.proposer_index),
            "parent_root": latest_block_header.parent_root.hex(),
            "state_root": latest_block_header.state_root.hex(),
            "body_root": latest_block_header.body_root.hex(),
        }
        return self

    def block_roots(self, block_roots):
        self.fields["block_roots"] = [root.hex() for root in block_roots]
        return self

    def state_roots(self, state_roots):
        self.fields["state_roots"] = [root.hex() for root in state_roots]
        return self

    def historical_roots(self, historical_roots):
        self.fields["historical_roots"] = [root.hex() for root in historical_roots]
        return self

    # Eth1
    def eth1_data(self, eth1_data):
        self.fields["eth1_data"] = {
            "deposit_root": eth1_data.deposit_root.hex(),
            "deposit_count": int(eth1_data.deposit_count),
            "block_hash": eth1_data.block_hash.hex(),
        }
        return self

    def eth1_data_votes(self, eth1_data_votes):
        self.fields["eth1_data_votes"] = [{
            "deposit_root": eth1_data.deposit_root.hex(),
            "deposit_count": int(eth1_data.deposit_count),
            "block_hash": eth1_data.block_hash.hex(),
        } for eth1_data in eth1_data_votes]
        return self

    def eth1_deposit_index(self, eth1_deposit_index):
        self.fields["eth1_deposit_index"] = int(eth1_deposit_index)
        return self

    # Registry
    def validators(self, validators):
        self.fields["validators"] = [{
            "pubkey": validator.pubkey.hex(),
            "withdrawal_credentials": validator.withdrawal_credentials.hex(),
            "effective_balance": int(validator.effective_balance),
            "slashed": bool(validator.slashed),
            "activation_eligibility_epoch": int(validator.activation_eligibility_epoch),
            "activation_epoch": int(validator.activation_epoch),
            "exit_epoch": int(validator.exit_epoch),
            "withdrawable_epoch": int(validator.withdrawable_epoch),
        } for validator in validators]
        return self

    def balances(self, balances):
        self.fields["balances"] = [int(balance) for balance in balances]
        return self

    # Randomness
    def randao_mixes(self, randao_mixes):
        self.fields["randao_mixes"] = [mix.hex() for mix in randao_mixes]
        return self

    # Slashings
    def slashings(self, slashings):
        self.fields["slashings"] = [int(slash) for slash in slashings]
        return self

    # Attestations
    def previous_epoch_attestations(self, previous_epoch_attestations):
        self.fields["previous_epoch_attestations"] = [{
            "aggregation_bits": attestation.aggregation_bits.hex(),
            "data": {
                "slot": int(attestation.data.slot),
                "index": int(attestation.data.index),
                "beacon_block_root": attestation.data.beacon_block_root.hex(),
                "source": {
                    "epoch": int(attestation.data.source.epoch),
                    "root": attestation.data.source.root.hex(),
                },
                "target": {
                    "epoch": int(attestation.data.target.epoch),
                    "root": attestation.data.target.root.hex(),
                },
            },
            "inclusion_delay": int(attestation.inclusion_delay),
            "proposer_index": int(attestation.proposer_index),
        } for attestation in previous_epoch_attestations]
        return self

    def current_epoch_attestations(self, current_epoch_attestations):
        self.fields["current_epoch_attestations"] = [{
            # TODO: this is incorrect
            "aggregation_bits": attestation.aggregation_bits.hex(),
            "data": {
                "slot": int(attestation.data.slot),
                "index": int(attestation.data.index),
                "beacon_block_root": attestation.data.beacon_block_root.hex(),
                "source": {
                    "epoch": int(attestation.data.source.epoch),
                    "root": attestation.data.source.root.hex(),
                },
                "target": {
                    "epoch": int(attestation.data.target.epoch),
                    "root": attestation.data.target.root.hex(),
                },
            },
            "inclusion_delay": int(attestation.inclusion_delay),
            "proposer_index": int(attestation.proposer_index),
        } for attestation in current_epoch_attestations]
        return self

    def previous_epoch_participation(self, previous_epoch_participation):
        self.fields["previous_epoch_participation"] = [
            int(participation)
            for participation in previous_epoch_participation
        ]
        return self

    def current_epoch_participation(self, current_epoch_participation):
        self.fields["current_epoch_participation"] = [
            int(participation)
            for participation in current_epoch_participation
        ]
        return self

    # Finality
    """
    TODO
    def justification_bits(self, justification_bits):
        self.fields["justification_bits"] = justification_bits.hex()
        return self
    """

    def previous_justified_checkpoint(self, previous_justified_checkpoint):
        self.fields["previous_justified_checkpoint"] = {
            "epoch": int(previous_justified_checkpoint.epoch),
            "root": previous_justified_checkpoint.root.hex(),
        }
        return self

    def current_justified_checkpoint(self, current_justified_checkpoint):
        self.fields["current_justified_checkpoint"] = {
            "epoch": int(current_justified_checkpoint.epoch),
            "root": current_justified_checkpoint.root.hex(),
        }
        return self

    def finalized_checkpoint(self, finalized_checkpoint):
        self.fields["finalized_checkpoint"] = {
            "epoch": int(finalized_checkpoint.epoch),
            "root": finalized_checkpoint.root.hex(),
        }
        return self

    # Altair
    def inactivity_scores(self, inactivity_scores):
        self.fields["inactivity_scores"] = [int(score) for score in inactivity_scores]
        return self

    def current_sync_committee(self, current_sync_committee):
        self.fields["current_sync_committee"] = {
            "pubkeys": [pubkey.hex() for pubkey in current_sync_committee.pubkeys],
            "aggregate_pubkey": current_sync_committee.aggregate_pubkey.hex(),
        }
        return self

    def next_sync_committee(self, next_sync_committee):
        self.fields["next_sync_committee"] = {
            "pubkeys": [pubkey.hex() for pubkey in next_sync_committee.pubkeys],
            "aggregate_pubkey": next_sync_committee.aggregate_pubkey.hex(),
        }
        return self

    def from_state(self, state):
        """
        Constructs a full state verification object from the given ``state``.
        Might be too expensive because it checks every single field, and the
        produced yaml file is too big.
        """
        # Common Attributes
        self.state_root(state.hash_tree_root())
        self.slot(state.slot)
        self.genesis_time(state.genesis_time)
        self.genesis_validators_root(state.genesis_validators_root)
        self.fork(state.fork)
        self.latest_block_header(state.latest_block_header)
        self.block_roots(state.block_roots)
        self.state_roots(state.state_roots)
        self.historical_roots(state.historical_roots)

        # Eth1
        self.eth1_data(state.eth1_data)
        self.eth1_data_votes(state.eth1_data_votes)
        self.eth1_deposit_index(state.eth1_deposit_index)

        # Registry
        self.validators(state.validators)
        self.balances(state.balances)

        # Randomness
        self.randao_mixes(state.randao_mixes)

        # Slashings
        self.slashings(state.slashings)

        # Attestations / Participation
        if hasattr(state, "previous_epoch_attestations"):
            self.previous_epoch_attestations(state.previous_epoch_attestations)
        else:
            self.previous_epoch_participation(state.previous_epoch_participation)
        if hasattr(state, "current_epoch_attestations"):
            self.current_epoch_attestations(state.current_epoch_attestations)
        else:
            self.current_epoch_participation(state.current_epoch_participation)

        # Finality
        # TODO: self.justification_bits(state.justification_bits)
        self.previous_justified_checkpoint(state.previous_justified_checkpoint)
        self.current_justified_checkpoint(state.current_justified_checkpoint)
        self.finalized_checkpoint(state.finalized_checkpoint)

        # Altair
        if hasattr(state, "inactivity_scores"):
            self.inactivity_scores(state.inactivity_scores)
        if hasattr(state, "current_sync_committee"):
            self.current_sync_committee(state.current_sync_committee)
        if hasattr(state, "next_sync_committee"):
            self.next_sync_committee(state.next_sync_committee)

        return self

        # TODO: Bellatrix, Capella, Deneb fields


def CheckpointToDict(checkpoint):
    return {
        "epoch": int(checkpoint.epoch),
        "root": checkpoint.root.hex(),
    }


@dataclass
class EthV1BeaconStatesFinalityCheckpoints:
    id: StateID
    finalized: bool
    execution_optimistic: Optional[bool] = None
    data: Dict = field(default_factory=dict)

    def __post_init__(self):
        self.id = str(self.id)

    def previous_justified_checkpoint(self, checkpoint):
        self.data["previous_justified"] = {
            "epoch": int(checkpoint.epoch),
            "root": checkpoint.root.hex(),
        }
        return self

    def current_justified_checkpoint(self, checkpoint):
        self.data["current_justified"] = {
            "epoch": int(checkpoint.epoch),
            "root": checkpoint.root.hex(),
        }
        return self

    def finalized_checkpoint(self, checkpoint):
        self.data["finalized"] = {
            "epoch": int(checkpoint.epoch),
            "root": checkpoint.root.hex(),
        }
        return self

    def from_state(self, state):
        """
        Constructs a finality checkpoint verification object from a given
        state.
        """
        self.previous_justified_checkpoint(state.previous_justified_checkpoint)
        self.current_justified_checkpoint(state.current_justified_checkpoint)
        self.finalized_checkpoint(state.finalized_checkpoint)
        return self


@dataclass
class EthV1BeaconStatesFork:
    id: StateID
    finalized: bool
    execution_optimistic: Optional[bool] = None
    data: Dict = field(default_factory=dict)

    def __post_init__(self):
        self.id = str(self.id)

    def previous_version(self, version):
        self.data["previous_version"] = version.hex()
        return self

    def current_version(self, version):
        self.data["current_version"] = version.hex()
        return self

    def epoch(self, epoch):
        self.data["epoch"] = int(epoch)
        return self

    def from_state(self, state):
        """
        Constructs a finality checkpoint verification object from a given
        state.
        """
        self.previous_version(state.fork.previous_version)
        self.current_version(state.fork.current_version)
        self.epoch(state.fork.epoch)
        return self


yaml.register_class(EthV2DebugBeaconStates)
yaml.register_class(EthV1BeaconStatesFinalityCheckpoints)
yaml.register_class(EthV1BeaconStatesFork)
