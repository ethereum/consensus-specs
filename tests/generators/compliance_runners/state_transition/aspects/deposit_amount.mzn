% Realization aspect: deposit-amount profile.
%
% Profiles used by deposit-like handlers:
% ZERO, MINIMUM, ACTIVATION, or ABOVE_ACTIVATION. `amount_nonzero` is the
% derived predicate shared by handlers that only need the zero/nonzero split.

include "base.mzn";

enum AmountProfile = { ZERO, MINIMUM, ACTIVATION, ABOVE_ACTIVATION };

var AmountProfile: amount_profile;
var bool: amount_nonzero;
constraint amount_nonzero <-> amount_profile != ZERO;
