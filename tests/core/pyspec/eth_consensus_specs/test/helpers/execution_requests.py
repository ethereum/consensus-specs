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
        deposits=spec.ProgressiveList[spec.DepositRequest]([deposit_request]),
        withdrawals=spec.ProgressiveList[spec.WithdrawalRequest](),
        consolidations=spec.ProgressiveList[spec.ConsolidationRequest](),
    )
