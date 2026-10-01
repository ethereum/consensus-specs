% Realization aspect: builder pending balance / queues (parameterized).
%
% get_pending_balance_to_withdraw_for_builder over builder_pending_withdrawals
% and builder_pending_payments (specs/gloas/beacon-chain.md). Predicate + derived
% function, instantiable per role. Shared by execution_payload_bid and
% builder_exit_request.

include "base.mzn";

predicate builder_pending_ok(var Dim: has_withdrawal, var Dim: has_payment, var bool: applicable) =
    (has_withdrawal == NA <-> not applicable)
    /\ (has_payment == NA <-> not applicable);

function var bool: builder_has_pending(var Dim: has_withdrawal, var Dim: has_payment) =
    has_withdrawal == T \/ has_payment == T;
