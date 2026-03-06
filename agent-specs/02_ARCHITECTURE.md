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
│  /auth/token  → issue JWT                         │
│  /chat        → invoke agent                      │
│  /admin/*     → document management (admin only)  │
│  /health      → liveness check                    │
│                                                   │
│  Middleware: decode JWT → inject role into request │
└──────┬───────────────────────┬────────────────────┘
       │                       │
┌──────▼──────┐    ┌───────────▼──────────────────┐
│   SQLITE    │    │      LANGCHAIN REACT AGENT    │
│             │    │                               │
│  users.db   │    │  ReAct loop (max 5 iter):     │
│  documents  │    │  Thought → Action →           │
│  .db        │    │  Observation → Final Answer   │
│             │    │                               │
│  Path:      │    │  ConversationBufferWindow     │
│  backend/   │    │  Memory (last 10 turns)       │
└─────────────┘    └───────────┬────────────────────┘
                               │
                  ┌────────────▼─────────────────┐
                  │    RBAC-AWARE SEARCH TOOL     │
                  │                               │
                  │  semantic_search(query)       │
                  │  → FAISS similarity search    │
                  │    (over-fetch k*4 results)   │
                  │  → filter by allowed_roles    │
                  │  → trim to top-k              │
                  │  → per-session query dedup    │
                  │  → return allowed chunks only │
                  └────────────┬─────────────────┘
                               │
                  ┌────────────▼─────────────────┐
                  │           FAISS               │
                  │                               │
                  │  Each chunk has metadata:     │
                  │  { source, page,              │
                  │    allowed_roles: [...] }      │
                  │                               │
                  │  Loaded once via @lru_cache   │
                  │  Stored in backend/vector_store│
                  └──────────────────────────────┘
```

---

## Query Data Flow (Step by Step)

```
1.  User types question in React ChatInput
2.  POST /chat { message, session_id } + Authorization: Bearer <jwt>
3.  FastAPI: decode JWT → extract { username, role }
4.  agent.chat(message, session_id, role) called
5.  LangChain ReAct agent starts loop:
    a. Thought: what to search for
    b. Action: semantic_search tool called
    c. Tool: FAISS similarity_search → over-fetch k*4 chunks
    d. Tool: filter chunks where user role in allowed_roles → trim to top-k
    e. Observation: filtered chunks returned to agent
    f. Thought: synthesise answer
    g. Final Answer: generated with source citations
6.  Return { answer, sources, reasoning_steps, session_id, role }
7.  React renders MessageBubble with source badge + step counter
```

---

## Document Ingest Data Flow

```
1.  Admin uploads PDF via DocumentUpload component
2.  POST /admin/documents/upload { file, display_name, allowed_roles }
3.  FastAPI: verify admin role, save to backend/data/<filename>
4.  INSERT into documents.db: status=UPLOADED
5.  Admin clicks "Ingest Now" button
6.  POST /admin/documents/ingest
7.  For each UPLOADED document:
    a.  PyPDFLoader loads pages
    b.  RecursiveCharacterTextSplitter → chunks (1000 chars, 200 overlap)
    c.  Each chunk.metadata["allowed_roles"] = roles from documents.db
    d.  OpenAI embeds each chunk → 1536-dim vector
    e.  FAISS index rebuilt with ALL ingested chunks
    f.  documents.db: status=INGESTED, chunk_count=N
8.  get_vector_store.cache_clear() called
9.  Next query loads fresh index
```

---

## RBAC — Two Enforcement Layers

```
Layer 1 — API Route Level:
  /admin/* routes → require role == "admin" or return 403

Layer 2 — Chunk Retrieval Level:
  FAISS returns top k*4 chunks (over-fetch to prevent retrieval starvation)
  Filter: keep only chunks where user_role in chunk.metadata.allowed_roles
  Trim to top-k results
  Per-session query dedup: cached results returned with "write Final Answer NOW" nudge
  Pass filtered chunks to LLM
  If 0 chunks after filter → "No relevant information found"
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
.env flag           Import used              Notes
─────────────────── ──────────────────────── ─────────────────────
LLM_PROVIDER=openai      ChatOpenAI          Default
LLM_PROVIDER=ollama      ChatOllama          Free local
LLM_PROVIDER=azure_openai AzureChatOpenAI    Enterprise

EMBEDDING_PROVIDER=openai  OpenAIEmbeddings  Default
EMBEDDING_PROVIDER=ollama  OllamaEmbeddings  Free local

All imports are LAZY — only active provider imported at runtime
Switching = edit .env only, no code changes
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
