from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")


@dataclass
class Check:
    dimension: str
    claimed: object
    actual: object
    status: str


def _decode(p, t):
    return t.decode_bytes(snappy.decompress(p.read_bytes()))


def validate_case(d):
    pre = _decode(d / "pre.ssz_snappy", spec.BeaconState)
    post = _decode(d / "post.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((d / "dimensions.yaml").read_text())["claimed"]
    spe = int(spec.SLOTS_PER_EPOCH)
    epoch = spec.Epoch(spec.get_current_epoch(pre) + spec.MIN_SEED_LOOKAHEAD + 1)
    start = spec.compute_start_slot_at_epoch(epoch)
    expected = list(pre.ptc_window[spe:]) + [
        spec.compute_ptc(pre, spec.Slot(start + i)) for i in range(spe)
    ]
    actual = {
        "epoch_position": "GENESIS_END"
        if int(spec.get_current_epoch(pre)) == 0
        else "LATER_EPOCH_END",
        "old_sections_distinguishable": len(
            {tuple(pre.ptc_window[i : i + spe]) for i in range(0, len(pre.ptc_window), spe)}
        )
        == len(pre.ptc_window) // spe,
        "tail_epoch_to_current": "LOOKAHEAD_PLUS_ONE",
        "retained_sections_shifted": list(post.ptc_window[: len(pre.ptc_window) - spe])
        == list(pre.ptc_window[spe:]),
        "new_tail_recomputed": list(post.ptc_window[len(post.ptc_window) - spe :])
        == expected[len(expected) - spe :],
        "state_effected": pre.ptc_window != post.ptc_window,
        "outcome": "SHIFTED_AND_RECOMPUTED",
    }
    errors = []
    if list(post.ptc_window) != expected:
        errors.append("ptc window does not equal retained suffix plus computed tail")
    check = pre.copy()
    check.ptc_window = expected
    if check.hash_tree_root() != post.hash_tree_root():
        errors.append("unrelated state changed")
    if any(index >= len(post.validators) for committee in post.ptc_window for index in committee):
        errors.append("ptc window contains an invalid validator index")
    probe = post.copy()
    probe.slot = spec.Slot(probe.slot + 1)
    previous_slot = spec.Slot(spec.compute_start_slot_at_epoch(spec.get_current_epoch(probe) - 1))
    current_slot = spec.Slot(spec.compute_start_slot_at_epoch(spec.get_current_epoch(probe)))
    if spec.get_ptc(probe, previous_slot) != post.ptc_window[int(previous_slot % spe)]:
        errors.append("get_ptc does not resolve the shifted previous epoch")
    if spec.get_ptc(probe, current_slot) != post.ptc_window[spe + int(current_slot % spe)]:
        errors.append("get_ptc does not resolve the shifted current epoch")
    checks = [
        Check(k, v, actual.get(k), "ok" if actual.get(k) == v else "mismatch")
        for k, v in claimed.items()
    ]
    return checks, errors
