from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request


def get_non_empty_execution_requests(spec):
    deposit_request = prepare_deposit_request(
        spec,
        validator_index=0,
        amount=spec.Gwei(32000000000),
        index=spec.uint64(0),
        signed=False,
    )

    return spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](
            [deposit_request]
        ),
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](),
    )
