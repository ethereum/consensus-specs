% Realization aspect: builder lifecycle (parameterized).
%
% is_active_builder: deposit_epoch < finalized_checkpoint.epoch and
% withdrawable_epoch == FAR_FUTURE_EPOCH (specs/gloas/beacon-chain.md).
% Predicate + derived function over a builder's (deposit_to_finalized_epoch,
% withdrawable_epoch_set) dimensions, instantiable per role. Shared by
% execution_payload_bid and builder_exit_request.

include "base.mzn";

predicate builder_lifecycle_ok(var Dim: deposit_to_finalized_epoch,
                               var Dim: withdrawable_epoch_set, var bool: applicable) =
    (deposit_to_finalized_epoch == NA <-> not applicable)
    /\ (withdrawable_epoch_set == NA <-> not applicable);

function var bool: builder_is_active(var Dim: deposit_to_finalized_epoch,
                                     var Dim: withdrawable_epoch_set) =
    deposit_to_finalized_epoch == LT /\ withdrawable_epoch_set == F;
