% Realization aspect: consolidation churn availability.
%
% sufficient_consolidation_churn <-> get_consolidation_churn_limit(state) > MIN_ACTIVATION_BALANCE
% (specs/electra/beacon-chain.md process_consolidation_request). The materializer
% realizes it by sizing the active validator set. Always applicable.

include "base.mzn";

var bool: sufficient_consolidation_churn;
