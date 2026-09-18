% Coverage formula (smoke scope): at most one gate fails.
%
% Yields ACCEPT plus single-fault situations — one decisive failing gate with
% every other applicable gate passing. Non-gate dimensions (pending balance,
% amount, comparison boundaries that still pass) remain free, so several
% assignments may share an outcome; the materializer reduces to the declared
% obligations (e.g. cover_each(outcome)) by coverage fingerprint.
%
% Richer profiles simply relax this bound (n_faults <= 2, or drop it entirely
% for exhaustive) without changing the handler or aspect models.

include "handler_execution_payload_bid.mzn";

constraint n_faults <= 1;
