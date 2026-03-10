# 01 — PROJECT_OVERVIEW.md
# For Claude Code: Context only. No code to write in this file.
# Read this to understand what you are building and why.

---

## What You Are Building

**Happiest Minds Knowledge Hub** — an internal AI-powered knowledge assistant for Happiest Minds Technologies.

Employees ask natural language questions. The system searches ingested internal documents and returns grounded, cited answers. Access to documents is controlled by the user's role.

---

## The Core Problem

Happiest Minds employees waste significant time searching for information buried in internal documents — presales artefacts, HR policies, project templates, case studies, compliance documents.

This system gives any employee instant, cited answers from authorised documents — 24/7, from any device.

---

## Two Chatbot Instances (Build Internal First)

| Instance | Users | Auth | Documents |
|----------|-------|------|-----------|
| Internal | Admin, Faculty, Student | JWT + RBAC | All institutional docs |
| External | Public / prospects | None | Public documents only |

**Build the internal instance first. External is Phase 2.**

---

## The One Core Demo

**Same question. Three different answers. Based on who is asking.**

```
Student  asks: "What is in the feature 7 document?"
→ "I could not find information accessible to you."

Faculty  asks: "What is in the feature 7 document?"
→ "I could not find information accessible to you."

Admin    asks: "What is in the feature 7 document?"
→ Full cited answer from feature_7_document.pdf
```

This is the product. Everything else supports this moment.

---

## User Roles

| Role | What They Can See | System Access |
|------|------------------|---------------|
| admin | All documents | Chat + Admin document panel |
| faculty | Feature_6 + Student docs | Chat only |
| student | Student syllabus only | Chat only |

---

## Success Criteria (All Must Pass)

- [ ] Student querying a faculty-only document gets "not available"
- [ ] Faculty querying admin-only document gets "not available"  
- [ ] Admin gets full cited answer for all documents
- [ ] Every answer includes source filename and page number
- [ ] Admin can upload PDF, set roles, ingest — no developer needed
- [ ] App runs in Docker with single command: `./docker/deploy.sh local`
- [ ] All 3 role badges display correctly after login
- [ ] New chat clears conversation memory

---

## Non-Functional Requirements

| Attribute | Target |
|-----------|--------|
| Query latency | < 3 seconds (OpenAI) |
| Auth token expiry | 8 hours |
| Max PDF upload size | 50 MB |
| Chunk size | 1000 characters, 200 overlap |
| Top-K retrieval | 5 chunks |
| Conversation memory | Last 10 turns |
| Agent max iterations | max(5, 7) with force stop + retry (3 attempts) + vector store fallback |
| Vector store | FAISS (AI_PROVIDER=openai) or Azure AI Search (AI_PROVIDER=azure_openai) |
| Document metadata | DynamoDB (table: hm-documents, persists across App Runner redeployments) |

---

## What This Is NOT

- Not a general-purpose chatbot — answers only from ingested documents
- Not a search engine — generates synthesised answers, not links
- Not a prototype — production-ready auth, RBAC, Docker from day one

---

## Reusability Principle

Every domain-specific element (brand, roles, documents) must be separable from platform code.

```
Platform code     → agent.py, ingest.py, tools.py, auth.py
Domain config     → constants.js, theme.js, .env, documents in data/
```

Swapping to a new client = change constants.js + upload new documents. Zero code changes.
