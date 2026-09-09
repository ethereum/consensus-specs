"""MiniZinc model paths for withdrawal-processing coverage and materialization."""

from pathlib import Path

ASPECTS_DIR = Path(__file__).parent.parent.parent / "aspects" / "withdrawal_processing"

PENDING_MODEL = ASPECTS_DIR / "builder_pending_withdrawal_processing.mzn"
WITHDRAWAL_PROCESSING_MODEL = ASPECTS_DIR / "withdrawal_processing.mzn"
PENDING_PARTIAL_WITHDRAWAL_MODEL = (
    ASPECTS_DIR.parent / "validator_withdrawals" / "pending_partial_withdrawal_enumerate.mzn"
)
BUILDER_MODEL = ASPECTS_DIR.parent / "builder" / "builder_enumerate.mzn"
