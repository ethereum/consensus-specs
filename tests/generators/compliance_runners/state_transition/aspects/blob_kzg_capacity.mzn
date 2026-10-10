% Realization aspect: blob KZG commitment capacity.
%
% Spec: len(bid.blob_kzg_commitments) <= get_blob_parameters(...).max_blobs_per_block
% (specs/gloas/beacon-chain.md process_execution_payload_bid :1633).
% Always applicable (checked on both branches).

include "base.mzn";

var CMP: bid_kzg_to_max;  % compare(len(commitments), max_blobs_per_block)

var bool: bid_kzg_under_limit;
constraint bid_kzg_under_limit <-> (bid_kzg_to_max in {LT, EQ});
