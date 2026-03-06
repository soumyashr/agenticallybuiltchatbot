import json
import logging
from langchain.tools import Tool

from app.config import settings
from app.ingest import get_vector_store

log = logging.getLogger(__name__)


def _filter_by_role(docs: list, user_role: str) -> list:
    """
    Keep only chunks the user's role is allowed to see.
    chunk.metadata["allowed_roles"] is a list: ["admin", "faculty"]
    """
    allowed = []
    for doc in docs:
        roles = doc.metadata.get("allowed_roles", [])
        if isinstance(roles, str):
            try:
                roles = json.loads(roles)
            except json.JSONDecodeError:
                roles = []
        if user_role in roles:
            allowed.append(doc)
    return allowed


def _format_docs(docs: list) -> str:
    if not docs:
        return "No relevant information found in documents accessible to you."
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "Unknown document")
        page   = doc.metadata.get("page", "?")
        parts.append(
            f"[{i}] Source: {source}, Page: {page}\n{doc.page_content}"
        )
    return "\n---\n".join(parts)


def make_search_tools(user_role: str) -> list[Tool]:
    """
    Returns a list containing the semantic_search tool,
    pre-configured for the given user role.
    Called once per session at session creation time.
    """

    _seen_queries: dict[str, str] = {}  # per-session dedup cache

    def semantic_search(query: str) -> str:
        # Break agent loops — if the exact query was already run,
        # return the cached results with a strong nudge to answer.
        if query in _seen_queries:
            prev = _seen_queries[query]
            if "No relevant information found" in prev:
                return prev
            return (
                prev
                + "\n\n---\n"
                + "SYSTEM: These results were already returned. "
                  "Write your Final Answer NOW summarising the document "
                  "content above. Do NOT search again."
            )

        vs = get_vector_store()
        if vs is None:
            return (
                "No documents have been ingested yet. "
                "Please ask an administrator to upload and ingest documents."
            )
        # Over-fetch so role filtering still leaves enough results.
        # Without this, restricted docs can dominate the top-k and
        # crowd out documents the user is actually allowed to see.
        fetch_k = settings.retriever_top_k * 4
        raw_docs = vs.similarity_search(query, k=fetch_k)
        filtered = _filter_by_role(raw_docs, user_role)[
            : settings.retriever_top_k
        ]
        log.info(
            f"Search '{query[:50]}...' "
            f"raw={len(raw_docs)} filtered={len(filtered)} role={user_role}"
        )
        result = _format_docs(filtered)
        _seen_queries[query] = result
        return result

    return [
        Tool(
            name="semantic_search",
            func=semantic_search,
            description=(
                "Search Happiest Minds internal documents for relevant information. "
                "Input should be a clear, specific search query. "
                "Returns the most relevant document chunks accessible to the current user. "
                "Use this tool to find answers — do not answer from memory."
            ),
        )
    ]
