% Realization aspect: deposit-amount profile.
%
% Profiles used by deposit-like handlers. They distinguish zero, amounts below
% the protocol minimum, the exact minimum, amounts between the minimum and
% activation thresholds, the activation threshold, and larger amounts.

include "base.mzn";

enum AmountProfile = {
    ZERO,
    BELOW_MINIMUM,
    MINIMUM,
    BETWEEN_MINIMUM_AND_ACTIVATION,
    ACTIVATION,
    ABOVE_ACTIVATION
};

var AmountProfile: amount_profile;
