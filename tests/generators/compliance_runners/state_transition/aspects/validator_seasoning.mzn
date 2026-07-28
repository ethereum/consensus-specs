% Realization aspect: validator seasoning (parameterized).
%
% old_enough <-> current_epoch >= activation_epoch + SHARD_COMMITTEE_PERIOD.
% Only source-role validators gate on this. Coherence with lifecycle
% (old_enough and not exiting implies active) is stated by the handler where
% both are instantiated for the same role.

include "base.mzn";

predicate validator_seasoning_ok(var Dim: old_enough, var bool: applicable) =
    (old_enough == NA <-> not applicable);
