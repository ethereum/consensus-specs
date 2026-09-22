from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request


def get_non_empty_execution_requests(spec):
    deposit_request = prepare_deposit_request(
        spec,
        validator_index=0,
        amount=spec.Gwei(32000000000),
        index=spec.Uint64(0),
        signed=False,
    )

    return spec.ExecutionRequests(
        deposits=spec.DepositRequests.of(deposit_request),
        withdrawals=spec.WithdrawalRequests(),
        consolidations=spec.ConsolidationRequests(),
    )
