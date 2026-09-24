"""Coverage of the genesis guard and the reward/penalty component effects."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    constant,
    coverage_spec,
    factor,
    Integer,
)

from .observation import observe_attributes

current_epoch = attribute("current_epoch", Integer(min=0))
eligible_count = attribute("eligible_count", Integer(min=0))
leaking = attribute("leaking", Boolean())
flag_reward = attribute("flag_reward", Boolean())
flag_penalty = attribute("flag_penalty", Boolean())
inactivity_penalty = attribute("inactivity_penalty", Boolean())
genesis_epoch = constant("genesis_epoch", Integer(min=0))

REACHED = factor("after_genesis", current_epoch > genesis_epoch)
GUARD = aspect("guard", REACHED)
DELTAS = aspect(
    "deltas",
    factor("has_eligible_validator", eligible_count > 0, when=REACHED),
    factor("in_inactivity_leak", leaking, when=REACHED),
    factor("has_flag_reward", flag_reward, when=REACHED),
    factor("has_flag_penalty", flag_penalty, when=REACHED),
    factor("has_inactivity_penalty", inactivity_penalty, when=REACHED),
)
ASPECTS = (GUARD, DELTAS)
PROFILES = {
    "smoke": GUARD.each() | DELTAS.each(),
    "normal": GUARD.each() | DELTAS.nwise(2),
    "standard": GUARD.each() | DELTAS.nwise(2),
}

COVERAGE = coverage_spec(
    "rewards_and_penalties",
    focus="process_rewards_and_penalties: genesis guard, eligible set, leak, and nonzero delta sources",
    record="one vector; delta factors mean at least one validator receives that component",
    attributes=(
        current_epoch,
        eligible_count,
        leaking,
        flag_reward,
        flag_penalty,
        inactivity_penalty,
    ),
    constants=(genesis_epoch,),
    aspects=ASPECTS,
    profiles=PROFILES,
    feasible=lambda a, _g: (
        (
            a.get("has_eligible_validator") is not False
            or not any(
                a.get(name) is True
                for name in ("has_flag_reward", "has_flag_penalty", "has_inactivity_penalty")
            )
        )
        and not (a.get("in_inactivity_leak") is True and a.get("has_flag_reward") is True)
        and not (
            a.get("has_inactivity_penalty") is True
            and a.get("has_flag_penalty") is False
        )
        and not (
            a.get("has_eligible_validator") is True
            and a.get("in_inactivity_leak") is False
            and a.get("has_flag_reward") is False
            and a.get("has_flag_penalty") is False
        )
    ),
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={"genesis_epoch": lambda spec: int(spec.GENESIS_EPOCH)},
)
