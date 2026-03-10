# 05 — AGENT.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Build the ReAct agent, session management, source extraction.
# Replace the chat_router.py stub with full implementation.
# Prerequisites: 04_RAG_PIPELINE.md must be COMPLETE and VERIFIED.

---

## Note — UC-14 Guardrail Protection

All user messages pass through a two-layer guardrail system (`app/guardrails.py`)
**before** reaching the agent. See `09_GUARDRAILS.md` for details.

---

## STEP 1 — agent.py

Write to `backend/app/agent.py`:
```python
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

    return {
        "answer": answer,
        "sources": [s.dict() for s in sources],
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
                return {
                    "answer":          answer,
                    "session_id":      session_id,
                    "role":            role.value,
                    "sources":         [s.dict() for s in sources],
                    "reasoning_steps": len(intermediate),
                    "fallback_used":   False,
                    "error_type":      None,
                }

            # Fallback phrase but FAISS actually ran — genuine not-found
            if _has_sources(intermediate):
                return {
                    "answer":          answer,
                    "session_id":      session_id,
                    "role":            role.value,
                    "sources":         [s.dict() for s in sources],
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
```

---

## Retry & Fallback Logic (Design Notes)

The `chat()` function implements a multi-layer reliability strategy:

### Error Classification
- **Hard errors** (auth/rate-limit): Match `_AUTH_ERROR_PHRASES`, raise `AgentAccessError` immediately — no retry.
- **Soft errors** (parse failures, timeouts): Retry up to `MAX_AGENT_RETRIES` (3) times.
- **Genuine not-found**: Fallback phrase detected BUT `_has_sources()` is True (vector store ran and returned results) — accept the answer, no retry.
- **Parse failure**: Fallback phrase detected AND `_has_sources()` is False (vector store never ran) — retry.

### Direct Vector Store Fallback (`_direct_faiss_search`)
If all retries are exhausted, the system bypasses the ReAct agent entirely:
1. Calls the vector store directly via the search tool
2. Parses sources from the raw search result
3. Makes a single LLM call to synthesise an answer
4. Returns with `fallback_used: True`

### Response Fields
All responses include two additional fields:
- `fallback_used` (bool): True if the direct vector store fallback was used
- `error_type` (str | null): `"retrieval_error"`, `"no_match"`, or null

### UC-08 Clarification & UC-13 Irrelevant Query Handling
The ReAct prompt now includes two additional sections:
- **UC-08**: Instructs the agent to ask a clarifying question for ambiguous/broad queries
- **UC-13**: Instructs the agent to decline off-topic queries (weather, sports, etc.)
Both are configurable via `CLARIFY_PROMPT` and `IRRELEVANT_QUERY_MSG` env vars.

### UC-10 Escalation
When the agent cannot answer (parse failures or no relevant documents found):
1. `save_escalation()` writes to DynamoDB table `hm-escalations`
2. `_notify_slack()` sends a webhook notification (if `SLACK_WEBHOOK_URL` is set)
3. Both are wrapped in `_escalate()` which never raises — failures are logged and swallowed

Escalation triggers:
- Final parse-failure attempt within retry loop → reason `"no_answer_found"`
- All retries exhausted before FAISS fallback → reason `"agent_parse_failure"`

### max_iterations
`_create_executor` uses `max(settings.agent_max_iterations, 7)` to ensure enough
iterations for the agent to complete even with occasional parse errors.

---

## STEP 2 — Replace chat_router.py stub

Overwrite `backend/app/routers/chat_router.py` with:
```python
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt

from app.auth import decode_token
from app.models import ChatRequest, ChatResponse, Role
from app.agent import chat as agent_chat, clear_session

log = logging.getLogger(__name__)
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Send a message to the ReAct agent and receive a grounded answer."""
    try:
        role   = Role(user["role"])
        result = await agent_chat(
            message=req.message,
            session_id=req.session_id,
            role=role,
        )
        return ChatResponse(**result)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        log.error(f"Chat error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat/clear")
async def clear_chat_endpoint(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Clear conversation memory for a session (New Chat button)."""
    clear_session(req.session_id)
    return {"cleared": req.session_id}
```

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL. Fix all FAILs before moving to 06.

- [ ] `POST /chat` with admin token and message "hello" returns 200 with `answer` field
- [ ] `POST /chat` response contains `reasoning_steps` field (integer >= 0)
- [ ] `POST /chat` response contains `sources` array
- [ ] Admin asks about feature_7_document → receives a real answer (not "not available")
- [ ] Student asks about feature_7_document → answer contains "could not find" or similar refusal
- [ ] Faculty asks about feature_7_document → answer contains "could not find" or similar refusal
- [ ] Faculty asks about feature_6_document → receives a real answer
- [ ] Student asks about student_syllabus → receives a real answer
- [ ] Sources array contains `source` and `page` fields when documents are found
- [ ] `POST /chat/clear` returns `{ "cleared": "<session_id>" }`
- [ ] Asking the same question twice in the same session uses conversation memory
- [ ] Server logs show "Thought:", "Action:", "Observation:" in verbose output
- [ ] `reasoning_steps` value matches the number of Thought/Action/Observe cycles in logs

## Jira Mapping

**Covers:** UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-13

| Story ID | Title | AC | Implementation Status |
|----------|-------|----|-----------------------|
| UIB-79 | Consolidate insights into one clear answer | 0 | ⚠️ Partial |
| UIB-88 | Help users when many documents are relevant | 0 | ❌ Pending |
| UIB-93 | Maintain context within an active session | 0 | ✅ Implemented |
| UIB-98 | Allow user to clear or reset context within a session | 0 | ✅ Implemented |
| UIB-103 | Clear context when session expires or user logs out | 0 | ✅ Implemented |
| UIB-109 | Start fresh context on new session start | 0 | ✅ Implemented |
| UIB-113 | Detect ambiguous or overly broad queries | 0 | ✅ Implemented |
| UIB-117 | Ask user for clarification before answering | 0 | ✅ Implemented |
| UIB-123 | Detect when no matching or authorized content exists | 0 | ✅ Implemented |
| UIB-126 | Return safe fallback instead of speculative answer | 0 | ✅ Implemented |
| UIB-131 | Detect and log unanswered queries with metadata | 0 | ✅ Implemented |
| UIB-135 | Route unanswered queries to designated university teams | 0 | ✅ Implemented |
| UIB-157 | Detect irrelevant or out-of-scope queries | 0 | ✅ Implemented |
| UIB-161 | Provide polite decline and scope guidance | 0 | ✅ Implemented |

### Source of Truth Rules
- Jira AC = WHAT (behavior) — wins on conflicts
- This .md = HOW (implementation) — wins on design decisions
- Conflicts must be flagged in docs/CONFLICTS.md, never silently overridden

---

## UIB-140 Form Guidance Implementation

**Story:** UIB-140 — Answer questions about form purpose and usage
**Date:** 2026-03-10

### What Changed
Added `FORM GUIDANCE (UC-11 — UIB-140)` section to `agent_system_prompt` in both
`backend/app/config.py` (default) and `backend/.env` (runtime override).

### Prompt Behavior
When a user asks about a form, process, or procedure:
- Identify the specific form from the knowledge base using semantic search
- Describe the form's purpose, eligibility criteria, and typical usage scenarios
- If multiple similar forms exist, clearly differentiate them
- Never guess or fabricate form details not in approved documents
- Respect role-based access — only reference forms accessible to the user's role
- If form not found — use standard fallback (UC-09 behavior)

### AC Coverage
| AC | Description | Status |
|----|-------------|--------|
| AC1 | Chatbot identifies relevant form(s) from approved docs | ✅ |
| AC2 | Describes purpose, scenarios, eligibility from official docs | ✅ |
| AC3 | Information strictly from approved sources, no guesses | ✅ |
| AC4 | Clarifies differences when multiple similar forms exist | ✅ |
| AC5 | Falls back to "no matching content" if form undocumented | ✅ |
| AC6 | Role-based differences respected where documented | ✅ |

### Tests
6 tests in `TestFormGuidanceUC11` class (`backend/tests/test_agent_logic.py`),
tagged `# AC: UIB-140-AC1` through `# AC: UIB-140-AC6`.

---

## UIB-143 Form Location Guidance

**Story:** UIB-143 — Guide users on where to find forms
**Date:** 2026-03-10

### What Changed
Added `FORM LOCATION GUIDANCE (UC-11 — UIB-143)` section to `agent_system_prompt`
in both `backend/app/config.py` and `backend/.env`.

### Prompt Behavior
When a user asks where to find or download a form:
- Provide navigation path or location from approved documents if available
- Give step-by-step instructions when no direct link is documented
- Never provide guessed or unverified URLs or links
- If location not in docs — say so clearly and suggest contacting admin
- Only reference locations the user's role is authorized to access

### AC Coverage
| AC | Description | Status |
|----|-------------|--------|
| AC1 | Location info returned when in docs | ✅ |
| AC2 | Location respects RBAC | ✅ |
| AC3 | Step-by-step navigation when no direct link | ✅ |
| AC4 | Form locations configurable by admins | ❌ BLOCKED (UC-16) |
| AC5 | No guessed URLs in response | ✅ |
| AC6 | Access control respected for locations | ✅ |

**BLOCKED:** AC4 requires Admin Console (UC-16) which is not implemented.
Logged in `docs/CONFLICTS.md`.

### Tests
5 tests in `TestFormGuidanceUC11` class (`backend/tests/test_agent_logic.py`),
tagged `# AC: UIB-143-AC1,2,3,5,6`. Plus 1 shared prompt verification test.

---

## RBAC Citation Filter Fix

**Date:** 2026-03-10
**Resolves:** UIB-31, UIB-35, UIB-40, UIB-44, UIB-52
**Root Cause:** `_extract_sources()` returned all sources with zero role validation,
leaking restricted document names to unauthorized users even when answer content
was correctly access-controlled.

### What Changed

1. **New function `_filter_sources_by_role()`** (`agent.py`):
   - Checks each `SourceDoc.source` (filename) against `allowed_roles` from DynamoDB
   - Uses `document_store.get_allowed_roles_map()` to resolve `{filename: [roles]}`
   - Returns only sources the user's role is authorized to see
   - On roles-map load failure → returns `[]` (fail-safe)

2. **`chat()` — clean response path**:
   - `_filter_sources_by_role()` called after `_extract_sources()`, before response return
   - Only authorized citations reach the user

3. **`chat()` — neutral/fallback response path**:
   - When `_is_fallback_response()` is True and `_has_sources()` is True (genuine not-found):
     sources are now `[]` instead of the raw extracted list
   - Neutral messages must never leak document names (UIB-44, UIB-52)

4. **`_direct_faiss_search()` fallback**:
   - `_filter_sources_by_role()` applied before returning sources (defense-in-depth)

### Tests
6 tests in `TestRBACCitationFilter` class (`backend/tests/test_agent_logic.py`):
- `test_citations_filtered_by_role_student` (UIB-31)
- `test_no_restricted_docs_in_student_citations` (UIB-35)
- `test_neutral_response_has_empty_sources` (UIB-44)
- `test_fallback_response_has_empty_sources` (UIB-40)
- `test_admin_citations_include_admin_docs` (UIB-52)
- `test_authorized_user_still_gets_citations` (regression guard)

---

## Session TTL Fix

**Date:** 2026-03-11
**Resolves:** M4, M5 (VALIDATION_GAP_ANALYSIS.md), UIB-93 points 4-7
**Root Cause:** Conversation memory stored in `_sessions` dict had no TTL,
persisting beyond JWT expiry and accumulating indefinitely.

### What Changed

1. **`session_memory_ttl_seconds` setting** (`config.py`):
   - Default: 28800 (8 hours, matching JWT expiry)
   - Overridable via `SESSION_MEMORY_TTL_SECONDS` env var

2. **`_is_session_expired()`** (`agent.py`):
   - Checks `created_at` timestamp against TTL

3. **`_cleanup_expired_sessions()`** (`agent.py`):
   - Called lazily on every `get_or_create_session()` access
   - Removes all sessions that have exceeded TTL

4. **`get_or_create_session()`** updated:
   - Calls `_cleanup_expired_sessions()` at the start of every access
   - Expired sessions are evicted and recreated with fresh memory
   - `created_at` timestamp stored in session dict

### Tests
6 tests in `TestSessionTTLUC07` class (`backend/tests/test_agent_logic.py`):
- `test_expired_session_memory_cleared` (TTL1)
- `test_valid_session_memory_preserved` (TTL2)
- `test_memory_cleared_on_explicit_clear` (TTL3)
- `test_session_ttl_configurable` (TTL4)
- `test_no_memory_leak_across_sessions` (TTL5)
- `test_new_session_has_no_prior_context` (TTL6)

---

## Citation Format Enrichment (M1, UIB-35) — 2026-03-11

### Problem
Citations only showed raw filenames (e.g., `policy_v2.pdf`) and page numbers.
No display-friendly document names, no upload dates. Validation gap M1 / UIB-35.

### Solution
1. **`models.py`** — Added `display_name: Optional[str] = None` and `uploaded_at: Optional[str] = None` to `SourceDoc`
2. **`document_store.py`** — Added `get_document_metadata_map()` returning `{filename: {display_name, uploaded_at}}` for INGESTED docs
3. **`agent.py`** — Added `_enrich_sources()` function that populates `display_name` and `uploaded_at` from DynamoDB metadata. Called at the end of `_extract_sources()` and in `_direct_faiss_search()` fallback
4. **`frontend/MessageBubble.jsx`** — Shows `display_name` when available (falls back to raw `source`), shows upload date below citation title

### Key design decisions
- `source` field (raw filename) preserved for RBAC filter compatibility — `_filter_sources_by_role()` matches on filename
- Enrichment is best-effort: DynamoDB errors return raw sources safely (no crash)
- Empty sources list skips DynamoDB call entirely
- New fields are Optional — backward compatible with existing API consumers

### Tests
7 tests in `TestCitationFormatUC02` class (`backend/tests/test_agent_logic.py`):
- `test_enriched_source_has_display_name` (AC1)
- `test_enriched_source_has_uploaded_at` (AC2)
- `test_unknown_file_stays_raw` (AC3)
- `test_metadata_error_returns_raw_sources` (AC4)
- `test_extract_sources_enriches_results` (AC5)
- `test_empty_sources_no_enrichment_call` (AC6)
- `test_source_doc_new_fields_optional` (AC7)
