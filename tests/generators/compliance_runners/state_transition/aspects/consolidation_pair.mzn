% Realization aspect: consolidation source/target pairing.
%
% same_source_target <-> source_pubkey == target_pubkey. When true, only the
% switch-to-compounding path can apply; otherwise it is a consolidation
% (specs/electra/beacon-chain.md process_consolidation_request).

include "base.mzn";

var bool: same_source_target;
