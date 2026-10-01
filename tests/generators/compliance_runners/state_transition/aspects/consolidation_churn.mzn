% Realization aspect: consolidation churn availability.
%
% `consolidation_churn_to_min_activation` compares
% get_consolidation_churn_limit(state) to MIN_ACTIVATION_BALANCE. The derived
% predicate preserves the handler's strict-greater-than gate.
% (specs/electra/beacon-chain.md process_consolidation_request). The materializer
% realizes it by sizing the active validator set. Always applicable.

include "base.mzn";

var CMP: consolidation_churn_to_min_activation;
var bool: sufficient_consolidation_churn;
constraint sufficient_consolidation_churn <-> consolidation_churn_to_min_activation == GT;
