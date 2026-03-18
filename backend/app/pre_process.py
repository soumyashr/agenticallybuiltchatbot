"""
UC-08: Clarify Ambiguous or Broad Queries — pre-processing module.

Deterministic detection of vague queries + role-safe clarification
question generation. No LLM calls — pure Python string logic.
"""
from __future__ import annotations

import logging
from app.document_store import get_allowed_roles_map

log = logging.getLogger(__name__)

# ── Broad terms that signal a vague query ────────────────────

BROAD_TERMS = [
    "tell me", "what is", "explain", "about", "overview",
    "everything", "all about", "describe", "summary", "summarize",
    "give me", "show me", "list", "what are",
]

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "about", "like", "through", "after", "over",
    "between", "out", "up", "down", "and", "but", "or", "nor",
    "not", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other",
    "some", "such", "no", "only", "own", "same", "than", "too",
    "very", "just", "because", "if", "when", "while", "how",
    "what", "which", "who", "whom", "this", "that", "these",
    "those", "i", "me", "my", "we", "our", "you", "your", "he",
    "him", "his", "she", "her", "it", "its", "they", "them",
    "their", "tell", "give", "show", "describe", "explain",
    "list", "get", "find",
})

# ── Human-readable labels derived from document filenames ────

_DOC_TOPIC_MAP = {
    "syllabus":    "the course syllabus",
    "operations":  "the academic operations manual",
    "curriculum":  "the curriculum design blueprint",
    "assessment":  "the assessment criteria",
    "senate":      "the faculty senate minutes",
    "restricted":  "the restricted data protocol",
    "protocol":    "the restricted data protocol",
}


def is_ambiguous_query(query: str) -> bool:
    """
    Returns True only if ALL THREE conditions are true:
      1. Query word count < 5
      2. Query contains a broad term from BROAD_TERMS
      3. Query has no specific noun (no word > 6 chars that is not a stop word)
    """
    q = query.strip().lower()
    words = q.split()

    # Condition 1 — too short
    if len(words) >= 5:
        return False

    # Condition 2 — contains a broad term
    has_broad = any(term in q for term in BROAD_TERMS)
    if not has_broad:
        return False

    # Condition 3 — no specific noun
    # A word is "specific" if:
    #   - it's longer than 6 chars and not a stop word, OR
    #   - it's not a stop word AND contains uppercase (acronyms: ML, FAISS), OR
    #   - it contains digits (course codes: CS405)
    original_words = query.strip().split()
    for w in original_words:
        w_lower = w.lower().rstrip("?.,!;:")
        if w_lower in _STOP_WORDS:
            continue
        if len(w_lower) > 6:
            return False
        if any(c.isupper() for c in w):
            return False
        if any(c.isdigit() for c in w):
            return False

    return True


def _get_allowed_filenames(role: str) -> list[str]:
    """Return filenames the role can access from DynamoDB metadata."""
    try:
        roles_map = get_allowed_roles_map()  # {filename: [roles]}
    except Exception as exc:
        log.warning("Cannot load roles map for clarification: %s", exc)
        return []
    return [fname for fname, roles in roles_map.items() if role in roles]


def _topic_from_filename(filename: str) -> str | None:
    """Extract a human-readable topic label from a document filename."""
    lower = filename.lower()
    for keyword, label in _DOC_TOPIC_MAP.items():
        if keyword in lower:
            return label
    return None


def generate_clarification_questions(
    query: str,
    allowed_collections: list[str] | None = None,
    role: str = "student",
) -> list[str]:
    """
    Returns exactly 2 clarification options based on the user's role.
    Options are derived only from documents the role can access.
    Never mentions documents outside allowed_collections — role safety.
    Returns short plain strings without punctuation.
    """
    # If allowed_collections not provided, derive from role
    if allowed_collections is None:
        filenames = _get_allowed_filenames(role)
    else:
        filenames = list(allowed_collections)

    # Build topic labels from accessible documents
    topics: list[str] = []
    seen: set[str] = set()
    for fname in filenames:
        label = _topic_from_filename(fname)
        if label and label not in seen:
            seen.add(label)
            topics.append(label)

    # Need at least 2 topics
    if len(topics) < 2:
        # Fallback generic options that are always safe
        topics = ["a specific topic from your accessible documents",
                  "a particular section or detail"]

    return topics[:2]


CLARIFICATION_RESPONSE_TEMPLATE = (
    "Your question is a bit broad. "
    "Are you asking about {option_1} or {option_2}? "
    "Or you can rephrase your question for a more specific answer."
)
