"""
UC-12 Workflow Execution Prevention (UIB-148 + UIB-152).

Detects when a user tries to submit, approve, or process a form/workflow
via the chatbot and returns a refusal message instead of running the agent.

Detection uses configurable keyword patterns (settings.workflow_patterns).
"""
from __future__ import annotations

import logging
import re

from app.config import settings

log = logging.getLogger(__name__)

# ── Default patterns (UIB-150: configurable via WORKFLOW_PATTERNS env) ──

_DEFAULT_PATTERNS: list[str] = [
    r"\bsubmit\b.*\bform\b",
    r"\bsubmit\b.*\bleave\b",
    r"\bsubmit\b.*\bapplication\b",
    r"\bsubmit\b.*\brequest\b",
    r"\bapply\b.*\bnow\b",
    r"\bapprove\b.*\b(my|the|this)\b",
    r"\bprocess\b.*\b(my|the|this)\b",
    r"\bcomplete\b.*\b(my|the|this)\b.*\bform\b",
    r"\bfile\b.*\b(my|the|this)\b.*\b(complaint|grievance)\b",
    r"\bregister\b.*\bme\b",
    r"\benroll\b.*\bme\b",
    r"\bbook\b.*\b(my|a|the)\b",
    r"\bcancel\b.*\b(my|the|this)\b.*\b(registration|enrollment|booking)\b",
    r"\bupdate\b.*\b(my|the)\b.*\b(profile|record|details)\b",
]


def _get_patterns() -> list[re.Pattern]:
    """Return compiled regex patterns from config or defaults.

    WORKFLOW_PATTERNS env var is comma-separated (preferred) or
    pipe-separated (legacy).  Comma is tried first; if only one part
    results and it contains a pipe we fall back to pipe-splitting.
    """
    raw = settings.workflow_patterns
    if raw:
        # Try comma first (standard env-var list separator)
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        # Fallback: if only one part and it contains pipe, split on pipe
        if len(parts) == 1 and "|" in parts[0]:
            parts = [p.strip() for p in raw.split("|") if p.strip()]
    else:
        parts = _DEFAULT_PATTERNS
    return [re.compile(p, re.IGNORECASE) for p in parts]


class WorkflowAttempt(Exception):
    """Raised when a workflow-execution attempt is detected."""

    def __init__(self, matched_pattern: str):
        self.matched_pattern = matched_pattern
        super().__init__(f"Workflow attempt detected: {matched_pattern}")


def detect_workflow_attempt(message: str) -> None:
    """
    Check message against workflow patterns. Raises WorkflowAttempt if matched.
    Called before the agent runs (UIB-148 AC3: flagged but not executed).
    """
    patterns = _get_patterns()
    for pattern in patterns:
        match = pattern.search(message)
        if match:
            log.warning(
                "UC-12 workflow attempt detected: pattern=%s matched='%s' message='%s'",
                pattern.pattern,
                match.group(),
                message[:200],
            )
            raise WorkflowAttempt(pattern.pattern)
