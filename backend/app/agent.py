from __future__ import annotations

import re
import logging
from typing import Any

from langchain.agents import create_react_agent, AgentExecutor
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.prompts import PromptTemplate

from app.config import settings
from app.models import Role, SourceDoc
from app.tools import make_search_tools
from app.escalation_store import save_escalation
from app.document_store import get_allowed_roles_map

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────

MAX_AGENT_RETRIES = 3

_FALLBACK_PHRASES = (
    "i could not find information",
    "no information found",
    "i don't have information",
    "i was unable to find",
    "could not find relevant",
    "agent stopped due to",
    "parsing error",
    "invalid or incomplete response",
)

_AUTH_ERROR_PHRASES = (
    "401",
    "invalid_api_key",
    "authenticationerror",
    "insufficient_quota",
    "429",
    "rate_limit",
)

# ── Typed exceptions ─────────────────────────────────────────


class AgentParseError(Exception):
    """Raised when the agent fails to parse LLM output after retries."""


class AgentRetrievalError(Exception):
    """Raised when FAISS retrieval fails after retries."""


class AgentAccessError(Exception):
    """Raised on authentication/authorization errors from the LLM provider."""


# ── Helper functions ─────────────────────────────────────────


def _is_fallback_response(text: str) -> bool:
    """Return True if the output contains any known fallback phrase."""
    lower = text.lower()
    return any(phrase in lower for phrase in _FALLBACK_PHRASES)


def _has_sources(intermediate_steps: list[Any]) -> bool:
    """Return True if any observation in the steps contains 'Source:'."""
    for _action, observation in intermediate_steps:
        if isinstance(observation, str) and "Source:" in observation:
            return True
    return False


# ── In-memory session store ───────────────────────────────────
# { session_id: { "executor": AgentExecutor, "role": Role } }
_sessions: dict[str, dict] = {}


# ── LLM factory (lazy imports) ───────────────────────────────

def _build_llm():
    provider = settings.ai_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        log.info(f"LLM: OpenAI ({settings.llm_model})")
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_key=settings.openai_api_key,
        )

    elif provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI
        log.info("LLM: Azure OpenAI (%s)", settings.azure_openai_deployment)
        return AzureChatOpenAI(
            azure_deployment=settings.azure_openai_deployment,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            temperature=settings.llm_temperature,
        )

    raise ValueError(
        f"Unknown AI_PROVIDER='{provider}'. "
        "Valid values: 'openai', 'azure_openai'"
    )


# ── ReAct prompt template ────────────────────────────────────

REACT_TEMPLATE = """{system_prompt}

You have access to the following tools:
{tools}

Use this EXACT format — never deviate:

Question: the input question you must answer
Thought: reason step by step about what to search for
Action: the action to take, must be one of [{tool_names}]
Action Input: the search query string
Observation: the result of the action
... (Thought/Action/Action Input/Observation repeats, maximum {max_iterations} times)
Thought: I now have enough information to answer
Final Answer: your complete answer with source document name and page number

RULES:
- Search ONCE. If the Observation contains document content (Source: ..., Page: ...), IMMEDIATELY write your Final Answer using that content. Do NOT search again.
- Only search a SECOND time if the first Observation says "No relevant information found".
- After finding relevant content, IMMEDIATELY write "Final Answer:" — do NOT search again
- Always cite sources as: Source: [filename], Page: [number]
- If the returned content answers the question, summarise it as your Final Answer.
- If the returned content is completely unrelated to the question, write: "Final Answer: I could not find information on this topic in the documents accessible to you."
- Never answer from your own training knowledge — only from search results
- NEVER repeat the same search query — if you already searched, write your Final Answer NOW

CLARIFICATION (UC-08):
- If a user's query is unclear, too broad, or could mean multiple things, ask ONE specific clarifying question before attempting to answer. Do not guess or provide a partial answer. Examples of unclear queries: "tell me everything", "what are the rules", "how does it work".
{clarify_prompt}

IRRELEVANT QUERIES (UC-13):
- If a user's query is completely unrelated to institutional documents, academic policies, curriculum, faculty matters, or organizational information, politely decline with: "Final Answer: I can only assist with questions related to institutional documents and organizational information. For other topics, please use the appropriate resource." Do not attempt to answer off-topic queries such as weather, sports, cooking, or general knowledge.
{irrelevant_query_msg}

Previous conversation:
{chat_history}

Question: {input}
Thought:{agent_scratchpad}""".strip()


def _build_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=[
            "input", "agent_scratchpad",
            "chat_history", "tools", "tool_names",
        ],
        partial_variables={
            "system_prompt":  settings.agent_system_prompt,
            "max_iterations": str(settings.agent_max_iterations),
            "clarify_prompt": settings.clarify_ambiguous_prompt,
            "irrelevant_query_msg": settings.irrelevant_query_response,
        },
        template=REACT_TEMPLATE,
    )


# ── Agent executor factory ───────────────────────────────────

def _create_executor(role: Role) -> AgentExecutor:
    llm    = _build_llm()
    tools  = make_search_tools(user_role=role.value)
    prompt = _build_prompt()
    agent  = create_react_agent(llm=llm, tools=tools, prompt=prompt)

    memory = ConversationBufferWindowMemory(
        memory_key="chat_history",
        k=settings.max_history_turns,
        return_messages=False,
        output_key="output",
    )

    return AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        max_iterations=max(settings.agent_max_iterations, 7),
        early_stopping_method="force",   # Forces Final Answer on iteration limit
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


# ── Session management ───────────────────────────────────────

def get_or_create_session(session_id: str, role: Role) -> AgentExecutor:
    """
    Return existing session executor or create a new one.
    Reusing a session_id with a different role raises PermissionError
    to prevent privilege escalation.
    """
    if session_id in _sessions:
        cached = _sessions[session_id]
        if cached["role"] != role:
            raise PermissionError(
                f"Session '{session_id}' belongs to role '{cached['role']}', "
                f"cannot be reused with role '{role}'."
            )
        return cached["executor"]

    executor = _create_executor(role)
    _sessions[session_id] = {"executor": executor, "role": role}
    log.info(f"New session created: id={session_id} role={role.value}")
    return executor


def clear_session(session_id: str) -> None:
    """Remove a session — called on logout or New Chat."""
    if session_id in _sessions:
        del _sessions[session_id]
        log.info(f"Session cleared: {session_id}")


# ── Source extraction from intermediate steps ────────────────

def _extract_sources(intermediate_steps: list[Any]) -> list[SourceDoc]:
    """
    Parse source citations from agent's tool observation text.
    Format expected: "Source: filename.pdf, Page: 3"
    """
    sources: list[SourceDoc] = []
    seen: set[str] = set()

    for _action, observation in intermediate_steps:
        if not isinstance(observation, str):
            continue
        for block in observation.split("---"):
            source_match = re.search(r"Source:\s*(.+?),\s*Page", block)
            page_match   = re.search(r"Page:\s*(\d+)", block)
            if not source_match:
                continue
            source_name = source_match.group(1).strip()
            page        = int(page_match.group(1)) if page_match else None
            key         = f"{source_name}:{page}"
            if key in seen:
                continue
            seen.add(key)
            # Extract a short snippet
            lines   = block.strip().split("\n")
            snippet = " ".join(lines[1:])[:200] + "…" if len(lines) > 1 else ""
            sources.append(SourceDoc(source=source_name, page=page, snippet=snippet))

    return sources


# ── Post-generation RBAC filter on citations ─────────────────

def _filter_sources_by_role(
    sources: list[SourceDoc],
    user_role: str,
) -> list[SourceDoc]:
    """
    Remove any cited source the user's role cannot access.
    Checks each SourceDoc.source (filename) against allowed_roles
    stored in DynamoDB document metadata.
    Returns only sources the user is authorized to see.
    """
    if not sources:
        return sources
    try:
        roles_map = get_allowed_roles_map()  # {filename: [roles]}
    except Exception as exc:
        log.warning("RBAC citation filter: cannot load roles map (%s); "
                    "returning empty sources for safety.", exc)
        return []

    allowed: list[SourceDoc] = []
    for src in sources:
        doc_roles = roles_map.get(src.source, [])
        if user_role in doc_roles:
            allowed.append(src)
        else:
            log.info("RBAC citation filter: stripped '%s' (role=%s not in %s)",
                     src.source, user_role, doc_roles)
    return allowed


# ── Direct FAISS fallback ────────────────────────────────────

async def _direct_faiss_search(
    message: str,
    role: Role,
) -> dict:
    """
    Last-resort fallback: bypass agent, call FAISS directly,
    then synthesise an answer with a single LLM call.
    """
    log.warning("Using direct FAISS fallback for: %s", message[:80])
    tools = make_search_tools(user_role=role.value)
    search_tool = tools[0]

    try:
        search_result = search_tool.func(message)
    except Exception as exc:
        log.error("Direct FAISS search failed: %s", exc)
        return {
            "answer": "I could not find information on this topic in the documents accessible to you.",
            "sources": [],
            "reasoning_steps": 0,
            "fallback_used": True,
            "error_type": "retrieval_error",
        }

    if "Source:" not in search_result:
        return {
            "answer": "I could not find information on this topic in the documents accessible to you.",
            "sources": [],
            "reasoning_steps": 0,
            "fallback_used": True,
            "error_type": "no_match",
        }

    # Parse sources from the raw search result
    sources: list[SourceDoc] = []
    seen: set[str] = set()
    for block in search_result.split("---"):
        source_match = re.search(r"Source:\s*(.+?),\s*Page", block)
        page_match   = re.search(r"Page:\s*(\d+)", block)
        if not source_match:
            continue
        source_name = source_match.group(1).strip()
        page        = int(page_match.group(1)) if page_match else None
        key         = f"{source_name}:{page}"
        if key not in seen:
            seen.add(key)
            lines   = block.strip().split("\n")
            snippet = " ".join(lines[1:])[:200] + "…" if len(lines) > 1 else ""
            sources.append(SourceDoc(source=source_name, page=page, snippet=snippet))

    # Single LLM call to synthesise
    llm = _build_llm()
    synthesis_prompt = (
        f"Based ONLY on the following document excerpts, answer the user's question.\n"
        f"If the excerpts do not contain the answer, say so.\n"
        f"Always cite sources as: Source: [filename], Page: [number]\n\n"
        f"--- Document Excerpts ---\n{search_result}\n\n"
        f"--- Question ---\n{message}\n\n"
        f"Answer:"
    )

    try:
        llm_response = llm.invoke(synthesis_prompt)
        answer = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
    except Exception as exc:
        log.error("LLM synthesis in fallback failed: %s", exc)
        answer = "I found relevant documents but could not generate a summary. Please try again."

    safe_sources = _filter_sources_by_role(sources, role.value)
    return {
        "answer": answer,
        "sources": [s.dict() for s in safe_sources],
        "reasoning_steps": 1,
        "fallback_used": True,
        "error_type": None,
    }


# ── UC-10 Escalation helpers ─────────────────────────────────

async def _notify_slack(role: str, message: str) -> None:
    """Send Slack webhook notification. Swallows all exceptions."""
    url = settings.slack_webhook_url
    if not url:
        return
    try:
        import httpx
        from datetime import datetime
        payload = {
            "text": (
                f":warning: *Unanswered Query Escalation*\n"
                f"*Role:* {role}\n"
                f"*Query:* {message[:200]}\n"
                f"*Time:* {datetime.utcnow().isoformat()}"
            )
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
    except Exception as exc:
        log.warning("Slack notification failed (non-blocking): %s", exc)


async def _escalate(session_id: str, message: str, role_value: str, reason: str) -> None:
    """Save escalation and optionally notify Slack. Never raises."""
    try:
        if settings.escalation_enabled:
            save_escalation(session_id, message, role_value, reason)
            await _notify_slack(role_value, message)
    except Exception as exc:
        log.warning("Escalation save/notify failed (non-blocking): %s", exc)


# ── Public chat interface ────────────────────────────────────

async def chat(
    message: str,
    session_id: str,
    role: Role,
) -> dict:
    """
    Main entry point. Returns dict matching ChatResponse model.
    Retries on agent parse failures up to MAX_AGENT_RETRIES times.
    Falls back to direct FAISS search if all retries are exhausted.
    """
    executor = get_or_create_session(session_id, role)

    last_answer = None
    last_sources: list[SourceDoc] = []
    last_steps = 0

    for attempt in range(1, MAX_AGENT_RETRIES + 1):
        try:
            result       = executor.invoke({"input": message})
            answer       = result.get("output", "I could not generate an answer.")
            intermediate = result.get("intermediate_steps", [])
            sources      = _extract_sources(intermediate)

            # Handle force-stop default message
            if "Agent stopped" in answer:
                answer = "I could not find information on this topic in the documents accessible to you."

            last_answer  = answer
            last_sources = sources
            last_steps   = len(intermediate)

            # Clean response — return immediately
            if not _is_fallback_response(answer):
                safe_sources = _filter_sources_by_role(sources, role.value)
                return {
                    "answer":          answer,
                    "session_id":      session_id,
                    "role":            role.value,
                    "sources":         [s.dict() for s in safe_sources],
                    "reasoning_steps": len(intermediate),
                    "fallback_used":   False,
                    "error_type":      None,
                }

            # Fallback phrase but FAISS actually ran — genuine not-found
            # Return empty sources: neutral messages must not leak doc names
            # (UIB-44, UIB-52)
            if _has_sources(intermediate):
                return {
                    "answer":          answer,
                    "session_id":      session_id,
                    "role":            role.value,
                    "sources":         [],
                    "reasoning_steps": len(intermediate),
                    "fallback_used":   False,
                    "error_type":      None,
                }

            # Fallback phrase and FAISS never ran — parse failure, retry
            log.warning(
                "Agent parse failure (attempt %d/%d): %s",
                attempt, MAX_AGENT_RETRIES, answer[:100],
            )
            # UC-10: escalate on final parse-failure attempt
            if attempt == MAX_AGENT_RETRIES:
                await _escalate(session_id, message, role.value, "no_answer_found")

        except Exception as exc:
            exc_str = str(exc).lower()
            # Auth/rate-limit errors — raise immediately, do not retry
            if any(phrase in exc_str for phrase in _AUTH_ERROR_PHRASES):
                log.error("Non-retryable error: %s", exc)
                raise AgentAccessError(str(exc)) from exc

            log.warning(
                "Agent exception (attempt %d/%d): %s",
                attempt, MAX_AGENT_RETRIES, exc,
            )
            last_answer = str(exc)

    # All retries exhausted — fall back to direct FAISS search
    log.warning("All %d retries exhausted, using direct FAISS fallback.", MAX_AGENT_RETRIES)
    # UC-10: escalate on exhausted retries
    await _escalate(session_id, message, role.value, "agent_parse_failure")
    fallback_result = await _direct_faiss_search(message, role)
    fallback_result["session_id"] = session_id
    fallback_result["role"] = role.value
    return fallback_result
