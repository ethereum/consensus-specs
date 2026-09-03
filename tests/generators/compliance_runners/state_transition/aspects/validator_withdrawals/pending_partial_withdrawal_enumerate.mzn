% Enumeration model for the validator pending partial withdrawal aspect.
%
% Declares a single unrestricted ValidatorPendingPartialWithdrawal decision
% variable subject to pending_partial_withdrawal_constraints so all feasible
% solutions can be enumerated.

include "pending_partial_withdrawal.mzn";

var ValidatorPendingPartialWithdrawal: w;

constraint pending_partial_withdrawal_constraints(w);

solve satisfy;
