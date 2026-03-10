# 02 — ARCHITECTURE.md
# For Claude Code: Context only. No code to write in this file.
# Read before writing any code. This is the system blueprint.

---

## System Architecture

```
┌──────────────────────────────────────────────────┐
│                 REACT FRONTEND                    │
│  Vite + React 18 │ MVVM │ Pure inline CSS         │
│  Inter font │	 Green #3AB54A on White #FFFFFF      │
│                                                   │
│  LoginScreen → ChatArea → AdminPanel              │
│  Sidebar (role badge) │ Header (tab nav)          │
└───────────────────┬──────────────────────────────┘
                    │ HTTPS/REST + JWT Bearer token
┌───────────────────▼──────────────────────────────┐
│                  FASTAPI                          │
│  Port 8000 │ CORS enabled for :3000               │
│                                                   │
│  /auth/token    → issue JWT                        │
│  /chat          → invoke agent (with retry logic)  │
│  /chat/clear    → clear session memory             │
│  /documents/my  → user's accessible docs (any role)│
│  /admin/*       → document management (admin only) │
│  /health        → liveness check                   │
│                                                   │
│  Middleware: decode JWT → inject role into request │
└──────┬───────────────────────┬────────────────────┘
       │                       │
┌──────▼──────┐    ┌───────────▼──────────────────┐
│   DATA      │    │      LANGCHAIN REACT AGENT    │
│             │    │                               │
│  users.db   │    │  ReAct loop (max 7 iter):     │
│  (SQLite)   │    │  Thought → Action →           │
│             │    │  Observation → Final Answer   │
│  documents  │    │                               │
│  (DynamoDB) │    │  Retry logic (3 attempts):     │
│  table:     │    │  Hard errors → raise immediately│
│  hm-documents│    │  Soft errors → retry           │
│             │    │  Exhausted → direct vector store│
│             │    │                               │
│             │    │  ConversationBufferWindow     │
│             │    │  Memory (last 10 turns)       │
└─────────────┘    └───────────┬────────────────────┘
                               │
                  ┌────────────▼─────────────────┐
                  │    RBAC-AWARE SEARCH TOOL     │
                  │                               │
                  │  semantic_search(query)       │
                  │  → vector store search        │
                  │    (over-fetch k*4 results)   │
                  │  → filter by allowed_roles    │
                  │    (FAISS: client-side filter) │
                  │    (Azure: OData filter)       │
                  │  → trim to top-k              │
                  │  → per-session query dedup    │
                  │  → return allowed chunks only │
                  └────────────┬─────────────────┘
                               │
                  ┌────────────▼─────────────────┐
                  │     VECTOR STORE              │
                  │  (switched by AI_PROVIDER)    │
                  │                               │
                  │  AI_PROVIDER=openai:          │
                  │    FAISS (local disk)         │
                  │    Loaded via @lru_cache      │
                  │    backend/vector_store/      │
                  │                               │
                  │  AI_PROVIDER=azure_openai:    │
                  │    Azure AI Search (cloud)    │
                  │    Index + upsert on ingest   │
                  │    OData RBAC filter on query │
                  │                               │
                  │  Each chunk has metadata:     │
                  │  { source, page,              │
                  │    allowed_roles: [...] }      │
                  └──────────────────────────────┘
```

---

## Query Data Flow (Step by Step)

```
1.  User types question in React ChatInput
2.  POST /chat { message, session_id } + Authorization: Bearer <jwt>
3.  FastAPI: decode JWT → extract { username, role }
4.  agent.chat(message, session_id, role) called
5.  LangChain ReAct agent starts loop (with retry logic):
    a. Thought: what to search for
    b. Action: semantic_search tool called
    c. Tool: vector store similarity_search → over-fetch k*4 chunks
       (FAISS for openai, Azure AI Search for azure_openai)
    d. Tool: filter chunks where user role in allowed_roles → trim to top-k
       (FAISS: client-side filter; Azure: OData filter on allowed_roles)
    e. Observation: filtered chunks returned to agent
    f. Thought: synthesise answer
    g. Final Answer: generated with source citations
    h. If parse failure (fallback phrase + no sources): retry (up to 3x)
    i. If all retries fail: direct vector store fallback (bypass agent, single LLM call)
6.  Return { answer, sources, reasoning_steps, session_id, role, fallback_used, error_type }
7.  React renders MessageBubble with source badge + step counter
```

---

## Document Ingest Data Flow

```
1.  Admin uploads PDF via DocumentUpload component
2.  POST /admin/documents/upload { file, display_name, allowed_roles }
3.  FastAPI: verify admin role, save to backend/data/<filename>
4.  DynamoDB put_item: status=UPLOADED (table: hm-documents)
5.  Admin clicks "Ingest Now" button
6.  POST /admin/documents/ingest
7.  For each UPLOADED document:
    a.  PyPDFLoader loads pages
    b.  RecursiveCharacterTextSplitter → chunks (1000 chars, 200 overlap)
    c.  Each chunk.metadata["allowed_roles"] = roles from documents.db
    d.  Embeddings generated (OpenAI or Azure OpenAI, per AI_PROVIDER)
    e.  AI_PROVIDER=openai: FAISS index rebuilt with ALL ingested chunks
        AI_PROVIDER=azure_openai: Azure AI Search index created + documents upserted
    f.  DynamoDB update_item: status=INGESTED, chunk_count=N
8.  get_vector_store.cache_clear() called (FAISS path)
9.  Next query loads fresh index / hits Azure AI Search
```

---

## RBAC — Two Enforcement Layers

```
Layer 1 — API Route Level (JWT-based):
  /admin/* routes → require role == "admin" (via require_admin dependency) or return 403
  /documents/my → requires any authenticated user (via get_current_user dependency)
  /chat → requires any authenticated user
  JWT tamper protection: modified role claim fails signature verification → 401

Layer 2 — Chunk Retrieval Level (vector store metadata):
  Each chunk stored with metadata: { source, page, allowed_roles: ["admin","faculty"] }
  Vector store returns top k*4 chunks (over-fetch to prevent retrieval starvation)
  AI_PROVIDER=openai: FAISS returns all, client-side filter by allowed_roles
  AI_PROVIDER=azure_openai: Azure AI Search uses OData filter on allowed_roles
  Trim to top-k results
  Per-session query dedup: cached results returned with "write Final Answer NOW" nudge
  Pass filtered chunks to LLM
  If 0 chunks after filter → "No relevant information found"

Both layers must pass for a user to see document content.
Layer 1 alone does not prevent data leakage — Layer 2 is essential.
```

---

## Session Isolation

```
_sessions dict: { session_id → { executor: AgentExecutor, role: Role } }

Rules:
  - Same session_id + same role → reuse session (memory preserved)
  - Same session_id + different role → PermissionError (security)
  - New Chat clicked → new session_id generated → clean memory
  - Sessions stored in memory (reset on server restart)
```

---

## Provider Switching Architecture

```
A single AI_PROVIDER env var controls the entire AI stack:
LLM, embeddings, and vector store are switched together.

AI_PROVIDER     LLM                  Embeddings              Vector Store
──────────────  ───────────────────  ──────────────────────  ──────────────────
openai          ChatOpenAI           OpenAIEmbeddings        FAISS (local)
azure_openai    AzureChatOpenAI      AzureOpenAIEmbeddings   Azure AI Search

Config field: settings.ai_provider (mapped from AI_PROVIDER env var)

agent.py  → _build_llm() branches on settings.ai_provider
ingest.py → _build_embeddings() branches on settings.ai_provider
ingest.py → vector store: FAISS for openai, Azure AI Search for azure_openai
tools.py  → semantic_search: Azure uses OData filter for RBAC, FAISS uses client-side

All imports are LAZY — only active provider imported at runtime
Switching = change AI_PROVIDER in .env only, no code changes
```

---

## Frontend MVVM Layer Rules

```
Config layer     (theme.js, constants.js)
  ↑ imported by
Services layer   (api.js)
  ↑ imported by
Context layer    (AuthContext.jsx)
  ↑ imported by
Hooks layer      (useAuth.js, useChat.js, useDocuments.js)
  ↑ imported by
Components layer (all .jsx files)

RULE: Lower layers NEVER import from higher layers.
RULE: Components NEVER call fetch() directly — only through api.js.
RULE: App.jsx is pure wiring — no business logic, no fetch calls.
```
