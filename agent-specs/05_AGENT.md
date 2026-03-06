# 05 — AGENT.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Build the ReAct agent, session management, source extraction.
# Replace the chat_router.py stub with full implementation.
# Prerequisites: 04_RAG_PIPELINE.md must be COMPLETE and VERIFIED.

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

log = logging.getLogger(__name__)

# ── In-memory session store ───────────────────────────────────
# { session_id: { "executor": AgentExecutor, "role": Role } }
_sessions: dict[str, dict] = {}


# ── LLM factory (lazy imports) ───────────────────────────────

def _build_llm():
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        log.info(f"LLM: OpenAI ({settings.llm_model})")
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_key=settings.openai_api_key,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        log.info(f"LLM: Ollama ({settings.llm_model})")
        return ChatOllama(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )

    elif provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI
        log.info(f"LLM: Azure OpenAI ({settings.llm_model})")
        return AzureChatOpenAI(
            azure_deployment=settings.azure_openai_deployment or settings.llm_model,
            azure_endpoint=settings.azure_openai_endpoint,
            openai_api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER='{provider}'. "
        "Valid values: 'openai', 'ollama', 'azure_openai'"
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
        max_iterations=settings.agent_max_iterations,
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


# ── Public chat interface ────────────────────────────────────

async def chat(
    message: str,
    session_id: str,
    role: Role,
) -> dict:
    """
    Main entry point. Returns dict matching ChatResponse model.
    """
    executor     = get_or_create_session(session_id, role)
    result       = executor.invoke({"input": message})
    answer       = result.get("output", "I could not generate an answer.")
    intermediate = result.get("intermediate_steps", [])

    sources      = _extract_sources(intermediate)

    # Handle force-stop default message
    if "Agent stopped" in answer:
        answer = "I could not find information on this topic in the documents accessible to you."

    return {
        "answer":          answer,
        "session_id":      session_id,
        "role":            role.value,
        "sources":         [s.dict() for s in sources],
        "reasoning_steps": len(intermediate),
    }
```

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
