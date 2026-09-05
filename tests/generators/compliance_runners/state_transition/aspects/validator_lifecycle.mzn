% Realization aspect: validator lifecycle (parameterized).
%
%   active  <-> is_active_validator (activation_epoch <= epoch < exit_epoch)
%   exiting <-> exit_epoch != FAR_FUTURE_EPOCH
%
% Parameterized as a predicate over a validator's (active, exiting) coverage
% dimensions, instantiable per role (source, target, or a single validator) —
% the handler declares role-prefixed vars and applies the predicate to each.
% `applicable` is true when the validator resolves.

include "base.mzn";

predicate validator_lifecycle_ok(var Dim: active, var Dim: exiting, var bool: applicable) =
    (active == NA <-> not applicable)
    /\ (exiting == NA <-> not applicable);
