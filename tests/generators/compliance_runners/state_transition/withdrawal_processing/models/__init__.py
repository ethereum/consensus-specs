"""MiniZinc model paths for withdrawal-processing coverage and materialization."""

from pathlib import Path

STATE_TRANSITION_ASPECTS_DIR = Path(__file__).parent.parent.parent / "aspects"
WITHDRAWAL_PROCESSING_MODELS_DIR = Path(__file__).parent

PENDING_MODEL = WITHDRAWAL_PROCESSING_MODELS_DIR / "builder_pending_withdrawal_processing.mzn"
WITHDRAWAL_PROCESSING_MODEL = WITHDRAWAL_PROCESSING_MODELS_DIR / "withdrawal_processing.mzn"
PENDING_PARTIAL_WITHDRAWAL_MODEL = (
    STATE_TRANSITION_ASPECTS_DIR
    / "validator_withdrawals"
    / "pending_partial_withdrawal_enumerate.mzn"
)
BUILDER_MODEL = STATE_TRANSITION_ASPECTS_DIR / "builder" / "builder_enumerate.mzn"
