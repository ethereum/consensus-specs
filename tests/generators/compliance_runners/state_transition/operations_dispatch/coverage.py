"""Deterministic block-level obligations for operation dispatch and ordering."""

SCENARIOS = (
    {"scenario": "all_lists", "accepted": True},
    {"scenario": "parent_slot_matches", "accepted": True},
    {"scenario": "parent_slot_mismatches", "accepted": True},
    {"scenario": "slash_before_exit", "accepted": False},
    {"scenario": "invalid_payload_attestation", "accepted": False},
)


def build_profile(name: str) -> tuple[list[dict], list[dict]]:
    if name not in ("smoke", "normal", "exceptional", "standard", "all"):
        raise ValueError(f"unknown profile: {name}")
    chosen = [
        record
        for record in SCENARIOS
        if name in ("standard", "all")
        or (name == "smoke" and record["scenario"] in ("all_lists", "slash_before_exit"))
        or (name in ("normal", "exceptional") and record["accepted"] is (name == "normal"))
    ]
    return list(SCENARIOS), chosen
