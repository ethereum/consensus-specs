from eth_consensus_specs.test.helpers.attestations import get_max_attestations
from eth_consensus_specs.test.helpers.attester_slashings import get_max_attester_slashings
from eth_consensus_specs.test.helpers.bls_to_execution_changes import (
    get_max_bls_to_execution_changes,
)
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    get_max_builder_deposit_requests,
)
from eth_consensus_specs.test.helpers.consolidations import get_max_consolidation_requests
from eth_consensus_specs.test.helpers.deposits import get_max_deposits
from eth_consensus_specs.test.helpers.execution_requests import (
    get_max_builder_exit_requests,
    get_max_withdrawal_requests,
)
from eth_consensus_specs.test.helpers.forks import is_post_capella, is_post_electra, is_post_gloas
from eth_consensus_specs.test.helpers.payload_attestation import get_max_payload_attestations
from eth_consensus_specs.test.helpers.proposer_slashings import get_max_proposer_slashings
from eth_consensus_specs.test.helpers.voluntary_exits import get_max_voluntary_exits
from eth_consensus_specs.test.helpers.withdrawals import get_max_withdrawals


def get_soft_list_length_limits(spec):
    """
    Map ProgressiveList types to the consensus/gossip count limits that
    implementations may still enforce at deserialization.
    """
    limits = {
        spec.ProposerSlashings: get_max_proposer_slashings(spec),
        spec.AttesterSlashings: get_max_attester_slashings(spec),
        spec.Attestations: get_max_attestations(spec),
        spec.Deposits: get_max_deposits(spec),
        spec.VoluntaryExits: get_max_voluntary_exits(spec),
    }
    if is_post_capella(spec):
        limits[spec.BLSToExecutionChanges] = get_max_bls_to_execution_changes(spec)
        limits[spec.Withdrawals] = get_max_withdrawals(spec)
    if is_post_electra(spec):
        limits[spec.WithdrawalRequests] = get_max_withdrawal_requests(spec)
        limits[spec.ConsolidationRequests] = get_max_consolidation_requests(spec)
    if is_post_gloas(spec):
        limits[spec.PayloadAttestations] = get_max_payload_attestations(spec)
        limits[spec.BuilderDepositRequests] = get_max_builder_deposit_requests(spec)
        limits[spec.BuilderExitRequests] = get_max_builder_exit_requests(spec)
    return limits
