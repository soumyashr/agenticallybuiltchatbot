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
    """Return compiled regex patterns from config or defaults."""
    raw = settings.workflow_patterns
    if raw:
        # Config value is a pipe-separated string of regex patterns
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
