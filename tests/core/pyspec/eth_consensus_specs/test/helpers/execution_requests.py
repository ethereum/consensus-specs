from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.forks import is_post_gloas


def get_non_empty_execution_requests(spec):
    deposit_request = prepare_deposit_request(
        spec,
        validator_index=0,
        amount=spec.Gwei(32000000000),
        index=spec.uint64(0),
        signed=False,
    )

    if is_post_gloas(spec):
        max_deposit_requests_per_payload = spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD_GLOAS
    else:
        max_deposit_requests_per_payload = spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD

    return spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, max_deposit_requests_per_payload](
            [deposit_request]
        ),
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](),
    )
