% Realization aspect: builder funds / coverage (can_builder_cover_bid).
%
% Spec (specs/gloas/beacon-chain.md can_builder_cover_bid :737):
%   min_balance = MIN_DEPOSIT_AMOUNT + get_pending_balance_to_withdraw_for_builder(...)
%   if builder.balance < min_balance: return False            # the guard boundary
%   return builder.balance - min_balance >= bid.value          # the coverage boundary
%
% Two comparison dimensions preserve BOTH boundaries (guard and coverage), and
% min_balance includes the pending offset (builder_pending_balance aspect) — the
% materializer must realize min_balance including that term.

include "base.mzn";

var bool: builder_funds_applicable;

% compare(builder.balance, min_balance): LT fails the guard.
var CMP_NA: builder_balance_to_min_balance;
% compare(builder.balance - min_balance, bid.value): only meaningful past the guard.
var CMP_NA: builder_available_to_bid;

constraint (builder_balance_to_min_balance == NA) <-> not builder_funds_applicable;
constraint (builder_available_to_bid == NA) <->
    not (builder_funds_applicable /\ builder_balance_to_min_balance in {EQ, GT});

var bool: builder_can_cover_bid;
constraint builder_can_cover_bid <->
    (builder_balance_to_min_balance in {EQ, GT} /\ builder_available_to_bid in {EQ, GT});

% Coherence: balance == min_balance means zero available, which cannot exceed a
% non-negative bid value, so the available/bid comparison is never GT there.
constraint (builder_balance_to_min_balance == EQ) -> (builder_available_to_bid in {LT, EQ});
