# 00 — DECISIONS.md
# Agent Constitution — Read This First, Every Session

## CRITICAL INSTRUCTION FOR CLAUDE CODE
Read this file at the start of EVERY session before reading any other spec.
Every decision here is LOCKED. Do not deviate. Do not ask for clarification on these items.
If any other spec conflicts with this file, THIS FILE wins.

---

## Project Identity
```
Product name     : Happiest Minds Knowledge Hub
Tagline          : The Mindful IT Company · AI-powered
Company          : Happiest Minds Technologies
Type             : Internal tool — Happiest Minds branded throughout
Root path        : /Users/soumya.shrivastava/AgenticallyBuiltChatBot
```

---

## Brand & Design System (Non-negotiable)
```
Primary Green    : #3AB54A   ← HM official brand green
Green Hover      : #2E9640
Green Light/Dim  : #E8F8EA
Page Background  : #FFFFFF   ← Clean white (HM light theme)
Card Background  : #F8F9FA   ← Light grey cards/panels
Mid Surface      : #E8F8EA   ← Secondary panels, hover states
Border           : #E2E8F0   ← Universal border color
Text Primary     : #1A1A2E   ← Dark text on light backgrounds
Text Muted       : #666666
Text Body        : #334155
Button Text      : #FFFFFF   ← White text on green buttons
Error            : #EF4444
Error Background : #FEF2F2
Warning          : #F59E0B
Info             : #3B82F6

Sidebar          : White (#FFFFFF) background, #1A1A2E text, #666666 muted, #E2E8F0 border
Sidebar Questions: #F0FAF0 background, #009797 (teal) text, #39B54A border, 8px radius
Teal Accent      : #009797   ← Used for sidebar question labels and question text

Font Primary     : Inter (load from Google Fonts CDN)
Font Display     : Montserrat (bold 700, used for sidebar brand text)
Font weights     : 300, 400, 500, 600, 700

Role badge colors:
  admin          : bg #3AB54A, text #0A1A0A
  faculty        : bg #0F3460, text #FFFFFF
  student        : bg transparent, text #3AB54A, border 1px solid #3AB54A

Shadows (light theme):
  shadowSm       : 0 1px 3px rgba(0,0,0,0.08)
  shadowMd       : 0 4px 12px rgba(0,0,0,0.1)
  shadowLg       : 0 8px 24px rgba(0,0,0,0.12)
```

---

## Tech Stack (Locked — Zero Deviations)
```
OS               : Mac Apple Silicon M1/M2/M3 (arm64)
Python           : 3.11
FastAPI          : 0.111.0
Uvicorn          : 0.29.0 (with standard extras)
LangChain        : 0.2.1
langchain-openai : 0.1.8
langchain-ollama : 0.1.1
langchain-community: 0.2.1
FAISS            : faiss-cpu 1.8.0 (used when AI_PROVIDER=openai)
azure-search-documents: >=11.4.0 (used when AI_PROVIDER=azure_openai)
azure-identity       : >=1.15.0 (used when AI_PROVIDER=azure_openai)
boto3                : >=1.34.0 (DynamoDB document metadata store)
moto[dynamodb]       : >=5.0.0 (dev — DynamoDB test mocks)
PyPDF            : 4.2.0
PyJWT            : 2.8.0
bcrypt           : 4.1.3
pydantic-settings: 2.2.1
python-multipart : 0.0.9
aiofiles         : 23.2.1

React            : 18
Vite             : latest
Styling          : Pure inline CSS — NO Tailwind, NO MUI, NO CSS files
State            : React hooks only — NO Redux

Docker base      : python:3.11-slim (amd64 — AWS App Runner / Cloud Shell)
Docker frontend  : node:20-alpine + nginx:alpine (amd64)
```

---

## AI Provider (Switchable via .env — single flag controls entire stack)
```
AI_PROVIDER=openai        → ChatOpenAI + OpenAIEmbeddings + FAISS
AI_PROVIDER=azure_openai  → AzureChatOpenAI + AzureOpenAIEmbeddings + Azure AI Search

Default          : AI_PROVIDER=azure_openai
LLM (openai)     : ChatOpenAI(model="gpt-4o")
Embeddings (openai): OpenAIEmbeddings(model="text-embedding-ada-002") + FAISS
LLM (azure)      : AzureChatOpenAI(azure_deployment=...)
Embeddings (azure): AzureOpenAIEmbeddings(azure_deployment=...) + Azure AI Search

Rule             : All provider imports are LAZY (inside if/elif blocks)
                   Only the active provider's package is imported at runtime
                   A single AI_PROVIDER flag switches LLM + embeddings + vector store together
```

---

## Document Metadata Store (DynamoDB — replaces SQLite)
```
Storage          : AWS DynamoDB (table: hm-documents, region: ap-south-1)
Partition key    : id (String, UUID)
Config fields    : dynamo_table, dynamo_region (in Settings)
IAM role         : apprunner-hm-instance-role (DynamoDB full access)
Persistence      : Survives App Runner redeployments (unlike SQLite)
Dev testing      : moto library mocks DynamoDB in unit tests
```

---

## Roles (Locked — 3 roles, exact names)
```
admin            : Full access — all documents + admin panel
faculty          : faculty + student documents — chat only
student          : student documents only — chat only

Seeded users (created on startup, never change):
  username: admin     password: HMAdmin@2024    role: admin
  username: faculty1  password: HMFaculty@2024  role: faculty
  username: student1  password: HMStudent@2024  role: student
```

---

## Test Documents (3 files — exact RBAC mapping)
```
File 1: student_syllabus.pdf
  allowed_roles: ["admin", "faculty", "student"]

File 2: feature_6_document.pdf
  allowed_roles: ["admin", "faculty"]

File 3: feature_7_document.pdf
  allowed_roles: ["admin"]
```

---

## API Contract (Frontend ↔ Backend — Locked)
```
POST   /auth/token                   → { access_token, token_type, username, role }
POST   /chat                         → { answer, sources, reasoning_steps, session_id, role, fallback_used, error_type }
POST   /chat/clear                   → { cleared: session_id }
GET    /documents/my                 → [ { id, display_name, allowed_roles, chunk_count }, ... ]
GET    /admin/documents              → { pending[], ingesting[], ingested[], failed[], total }
POST   /admin/documents/upload       → { id, filename, display_name, allowed_roles, status }
POST   /admin/documents/ingest       → { message, ingested, total_ingested }
DELETE /admin/documents/{id}         → { deleted, filename }
GET    /admin/documents/{id}/status  → { id, status, chunk_count, error_msg }
GET    /health                       → { status: "ok" }

Auth header format: Authorization: Bearer <jwt_token>
Login format: multipart/form-data with fields: username, password

Note: /documents/my is NOT under /admin — it is on the public_router
and accessible to any authenticated user (used by sidebar for dynamic questions).
```

---

## Folder Structure (Exact — Do Not Deviate)
```
/Users/soumya.shrivastava/AgenticallyBuiltChatBot/
├── backend/
│   ├── app/
│   │   ├── __init__.py          (empty)
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── auth.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── ingest.py
│   │   ├── document_store.py
│   │   ├── guardrails.py
│   │   ├── workflow_guard.py
│   │   ├── feedback_store.py
│   │   ├── escalation_store.py
│   │   └── routers/
│   │       ├── __init__.py      (empty)
│   │       ├── auth_router.py
│   │       ├── chat_router.py
│   │       ├── documents_router.py
│   │       └── feedback_router.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_agent_logic.py       (57 tests — agent retry, RBAC, chat endpoint, citations)
│   │   ├── test_config.py            (4 tests — Settings defaults, Azure fields)
│   │   ├── test_azure_integration.py (7 tests — Azure LLM, embeddings, search, ingest)
│   │   ├── test_cors.py              (5 tests — CORS preflight and origin checks)
│   │   ├── test_document_store.py    (15 tests — DynamoDB CRUD via moto)
│   │   ├── test_escalation.py        (10 tests — escalation store, agent logic, admin endpoint)
│   │   ├── test_feedback.py          (12 tests — feedback store, endpoint, admin)
│   │   ├── test_guardrails.py        (27 tests — layer 1/2 checks, integration, config)
│   │   ├── test_provider_switching.py(14 tests — AI_PROVIDER flag, FAISS vs Azure)
│   │   └── test_workflow_guard.py    (37 tests — form guidance, workflow prevention)
│   ├── data/                    (empty dir, .gitkeep)
│   ├── vector_store/            (empty dir, .gitkeep)
│   ├── requirements.txt
│   ├── .env                     (copy from .env.example, fill API key)
│   └── .env.example
├── frontend/
│   ├── public/
│   │   └── favicon.png          (HM logo favicon)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── assets/
│   │   │   └── hm_logo.png     (Happiest Minds logo image)
│   │   ├── config/
│   │   │   ├── theme.js
│   │   │   └── constants.js
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── context/
│   │   │   └── AuthContext.jsx
│   │   ├── hooks/
│   │   │   ├── useAuth.js
│   │   │   ├── useChat.js
│   │   │   └── useDocuments.js
│   │   └── components/
│   │       ├── auth/
│   │       │   └── LoginScreen.jsx
│   │       ├── layout/
│   │       │   ├── Header.jsx
│   │       │   └── Sidebar.jsx
│   │       ├── chat/
│   │       │   ├── WelcomeScreen.jsx
│   │       │   ├── MessageList.jsx
│   │       │   ├── MessageBubble.jsx
│   │       │   └── TypingIndicator.jsx
│   │       ├── input/
│   │       │   └── ChatInput.jsx
│   │       └── admin/
│   │           ├── AdminPanel.jsx
│   │           ├── DocumentUpload.jsx
│   │           └── DocumentList.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── docker-compose.yml
│   ├── nginx.conf
│   ├── deploy.sh
│   ├── .dockerignore
│   └── .env.example
└── README.md
```

---

## Agent Behaviour Rules
```
1. Create ALL files in the exact paths above — never invent new paths
2. Run the server after creating backend files — fix any errors before reporting done
3. Never use placeholder comments like "# add logic here" — write complete code
4. Never truncate code — every function must be fully implemented
5. After each spec, run the verification checklist and report pass/fail for each item
6. If a checklist item fails — fix it before moving to the next spec
7. Never mix concerns — one spec, one layer
8. All colors must come from the DECISIONS.md brand system — never invent colors
9. All function names must match exactly what is specified — no renaming
10. Import order: stdlib → third-party → local app imports
```

---

## RBAC Test Matrix (3 roles x 3 documents = 9 tests)
```
All 9 must pass before the app is considered complete:

student → student_syllabus    : ALLOW (student can access)
faculty → student_syllabus    : ALLOW (faculty can access)
admin   → student_syllabus    : ALLOW (admin can access)
student → Feature_6           : BLOCK (faculty+admin only)
faculty → Feature_6           : ALLOW (faculty can access)
admin   → Feature_6           : ALLOW (admin can access)
student → Feature_7           : BLOCK (admin only)
faculty → Feature_7           : BLOCK (admin only)
admin   → Feature_7           : ALLOW (admin can access)
```

## Jira Mapping

**Covers:** UC-01, UC-02, UC-03, UC-16

| Story ID | Title | AC | Implementation Status |
|----------|-------|----|-----------------------|
| UIB-1 | Access chatbot widget from approved internal systems | 0 | ✅ Implemented |
| UIB-10 | Determine user persona from authentication context | 0 | ✅ Implemented |
| UIB-23 | Retrieve from approved knowledge sources only | 0 | ✅ Implemented |
| UIB-40 | Filter to authorized documents only | 0 | ✅ Implemented |

### Source of Truth Rules
- Jira AC = WHAT (behavior) — wins on conflicts
- This .md = HOW (implementation) — wins on design decisions
- Conflicts must be flagged in docs/CONFLICTS.md, never silently overridden
