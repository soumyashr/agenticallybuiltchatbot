# CLAUDE_CODE_README.md
# READ THIS FIRST — before opening any other file

---

## You Are Building: Happiest Minds Knowledge Hub

An internal AI knowledge assistant for Happiest Minds Technologies.
Full stack: FastAPI + LangChain ReAct + FAISS/Azure AI Search + React 18.
Happiest Minds brand: Green #3AB54A, Teal #009797, Inter + Montserrat fonts.
Deployed on AWS App Runner.

---

## Project Root
```
/Users/soumya.shrivastava/AgenticallyBuiltChatBot/
```

## Folder Structure
```
/Users/soumya.shrivastava/AgenticallyBuiltChatBot/
├── agent-specs/          ← all spec files live here (read-only, do not modify)
│   ├── CLAUDE_CODE_README.md
│   ├── 00_DECISIONS.md
│   ├── 01_PROJECT_OVERVIEW.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_BACKEND_CORE.md
│   ├── 04_RAG_PIPELINE.md
│   ├── 05_AGENT.md
│   ├── 06_RBAC.md
│   ├── 07_ADMIN_API.md
│   ├── 08_FRONTEND.md
│   ├── 09_DOCKER.md
│   └── 10_AWS_DEPLOY.md
├── backend/              ← created by spec 03
├── frontend/             ← created by spec 08
└── docker/               ← created by spec 09
```

---

## Your Instruction Files (in order)

| File | What to do |
|------|------------|
| `00_DECISIONS.md` | Read first, every session. All locked decisions live here. |
| `01_PROJECT_OVERVIEW.md` | Read once. Context only — no code. |
| `02_ARCHITECTURE.md` | Read once. Blueprint only — no code. |
| `03_BACKEND_CORE.md` | **Write code.** FastAPI skeleton + auth. |
| `04_RAG_PIPELINE.md` | **Write code.** FAISS/Azure AI Search + ingest + tools. |
| `05_AGENT.md`        | **Write code.** ReAct agent + sessions. |
| `06_RBAC.md`         | **Write code.** Route guards + verify. |
| `07_ADMIN_API.md`    | **Write code.** 5 admin endpoints. |
| `08_FRONTEND.md`     | **Write code.** Full React UI. |
| `09_DOCKER.md`       | **Write code.** Docker + deploy.sh. |
| `10_AWS_DEPLOY.md`   | **Write code.** AWS ECR + EC2 scripts. |

---

## The One Rule That Cannot Be Broken

**Complete each spec fully and pass its verification checklist before moving to the next.**

Never skip ahead. Never work on two specs simultaneously.
The build order exists because each layer depends on the one before it.

---

## How to Start

```
Step 1: Read 00_DECISIONS.md completely
Step 2: Read 01_PROJECT_OVERVIEW.md
Step 3: Read 02_ARCHITECTURE.md
Step 4: Open 03_BACKEND_CORE.md — start writing code
```

---

## When You Finish Each Spec

1. Run every item in the VERIFICATION CHECKLIST at the bottom of the spec
2. Report: PASS ✅ or FAIL ❌ for each item
3. Fix all FAILs before stopping
4. Only then: open the next spec file

---

## If You Are Unsure About Any Decision

Do not invent. Do not assume. Check `00_DECISIONS.md`.
If it is not in `00_DECISIONS.md`, ask the user before proceeding.

---

## Test Credentials (for verification steps)

```
admin    / HMAdmin@2024    → role: admin    (all documents)
faculty1 / HMFaculty@2024 → role: faculty  (feature_6 + student docs)
student1 / HMStudent@2024 → role: student  (student docs only)
```

---

## The Core RBAC Test (Run After Spec 06)

```
student1 asks about feature_7_document → must get "could not find" (not an answer)
faculty1 asks about feature_7_document → must get "could not find" (not an answer)
admin    asks about feature_7_document → must get a real cited answer
```

If any of these three fail, something is wrong with either ingest metadata or the filter function. Fix before continuing.

---

## Brand Reminder (Applies to All UI Code)

```
Primary green     : #3AB54A  (buttons, accents, badges)
Teal accent       : #009797  (sidebar question labels and text)
Sidebar questions : #F0FAF0 bg, #39B54A border, 8px radius
Background        : #FFFFFF  (page background — clean white HM light theme)
Cards/panels      : #F8F9FA  (light grey)
Mid/hover         : #E8F8EA  (green tint)
Border            : #E2E8F0
Text primary      : #1A1A2E  (dark text on light bg)
Text muted        : #666666
Button text       : #FFFFFF  (white on green buttons)
Sidebar           : White (#FFFFFF) with #1A1A2E text
Logo              : HM logo image (assets/hm_logo.png) — used in login + sidebar
Favicon           : public/favicon.png (copied from hm_logo.png)
Font primary      : Inter (loaded from Google Fonts)
Font display      : Montserrat bold 700 (sidebar brand text)
No Tailwind       : Pure inline CSS only
No CSS files      : All styles in JSX style props
```

---

## Key Endpoints (Updated)

```
POST   /auth/token              → JWT token
POST   /chat                    → Agent answer (with retry/fallback)
POST   /chat/clear              → Clear session memory
GET    /documents/my            → User's accessible documents (any role)
GET    /admin/documents         → All documents (admin only)
POST   /admin/documents/upload  → Upload PDF (admin only)
POST   /admin/documents/ingest  → Ingest pending docs (admin only)
DELETE /admin/documents/{id}    → Delete document (admin only)
GET    /health                  → Liveness check
```
