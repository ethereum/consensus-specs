% Realization aspect: deposit amount.
%
% Whether request.amount > 0 (credited to the builder balance on a top-up, or
% the initial balance of a newly added builder).

include "base.mzn";

var bool: amount_nonzero;
