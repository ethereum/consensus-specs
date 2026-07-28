% Realization aspect: builder funds / coverage (parameterized).
%
% can_builder_cover_bid (specs/gloas/beacon-chain.md can_builder_cover_bid):
%   min_balance = MIN_DEPOSIT_AMOUNT + get_pending_balance_to_withdraw_for_builder(...)
%   if builder.balance < min_balance: return False        # guard boundary
%   return builder.balance - min_balance >= bid.value      # coverage boundary
% Two comparison dimensions preserve both boundaries; the predicate carries the
% nested applicability and the balance==min coherence, and a function derives
% can_cover. min_balance must be realized including the pending offset.

include "base.mzn";

predicate builder_funds_ok(var Dim: balance_to_min, var Dim: available_to_bid, var bool: applicable) =
    (balance_to_min == NA <-> not applicable)
    /\ (available_to_bid == NA <-> not (applicable /\ balance_to_min in {EQ, GT}))
    % balance == min_balance means zero available, which cannot exceed a
    % non-negative bid value, so the available/bid comparison is never GT there.
    /\ (balance_to_min == EQ -> available_to_bid in {LT, EQ});

function var bool: builder_can_cover(var Dim: balance_to_min, var Dim: available_to_bid) =
    balance_to_min in {EQ, GT} /\ available_to_bid in {EQ, GT};
