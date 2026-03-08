# Test Record — Happiest Minds Knowledge Hub

**Date:** 2026-03-08
**Codebase:** /Users/soumya.shrivastava/AgenticallyBuiltChatBot

---

## Section 1 — Automated Test Suite

**File:** `backend/tests/test_agent_logic.py`
**Runner:** pytest
**Result:** 43/43 passed

### 1.1 TestIsFallbackResponse (7 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_exact_phrase` | `_is_fallback_response` returns True for "I could not find information" | PASS |
| 2 | `test_case_insensitive` | Detection works regardless of uppercase/mixed case | PASS |
| 3 | `test_embedded_phrase` | Fallback phrase embedded in a longer sentence is still detected | PASS |
| 4 | `test_clean_answer` | A normal answer with citations is not flagged as fallback | PASS |
| 5 | `test_empty_string` | Empty string is not flagged as fallback | PASS |
| 6 | `test_parsing_error` | "parsing error" phrase is detected as fallback | PASS |
| 7 | `test_agent_stopped` | "agent stopped due to" phrase is detected as fallback | PASS |

### 1.2 TestHasSources (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_with_source` | Returns True when an observation contains "Source:" | PASS |
| 2 | `test_without_source` | Returns False when no observation contains "Source:" | PASS |
| 3 | `test_empty_steps` | Returns False for an empty intermediate_steps list | PASS |
| 4 | `test_non_string_observation` | Returns False when observation is not a string (e.g. dict) | PASS |

### 1.3 TestExtractSources (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_single_source` | Extracts one SourceDoc from "Source: file.pdf, Page: 3" format | PASS |
| 2 | `test_multiple_sources` | Extracts multiple SourceDocs from "---"-separated blocks | PASS |
| 3 | `test_dedup` | Duplicate source+page combinations are deduplicated | PASS |
| 4 | `test_no_sources` | Returns empty list when no "Source:" patterns exist | PASS |

### 1.4 TestRetryDecisions (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_fallback_with_sources_returns_immediately` | When `_is_fallback_response` is True but `_has_sources` is True, the answer is returned without retry (genuine not-found) | PASS |
| 2 | `test_fallback_without_sources_triggers_retry` | When `_is_fallback_response` is True and `_has_sources` is False, the agent retries (parse failure) | PASS |

### 1.5 TestHardErrorNoRetry (6 tests, parametrized)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_hard_error[401]` | Exception containing "401" raises AgentAccessError immediately | PASS |
| 2 | `test_hard_error[invalid_api_key]` | Exception containing "invalid_api_key" raises AgentAccessError immediately | PASS |
| 3 | `test_hard_error[authenticationerror]` | Exception containing "authenticationerror" raises AgentAccessError immediately | PASS |
| 4 | `test_hard_error[insufficient_quota]` | Exception containing "insufficient_quota" raises AgentAccessError immediately | PASS |
| 5 | `test_hard_error[429]` | Exception containing "429" raises AgentAccessError immediately | PASS |
| 6 | `test_hard_error[rate_limit]` | Exception containing "rate_limit" raises AgentAccessError immediately | PASS |

### 1.6 TestSoftErrorRetried (1 test)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_soft_error_retried` | A generic exception (e.g. timeout) is retried up to MAX_AGENT_RETRIES times before falling back | PASS |

### 1.7 TestRBAC (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_role_filter_keeps_allowed` | `_filter_by_role` keeps chunks where user role is in `allowed_roles` list | PASS |
| 2 | `test_role_filter_blocks_disallowed` | `_filter_by_role` removes chunks where user role is not in `allowed_roles` | PASS |
| 3 | `test_role_filter_json_string` | `_filter_by_role` handles `allowed_roles` stored as JSON string (not just list) | PASS |
| 4 | `test_role_filter_empty_roles` | `_filter_by_role` returns empty list when `allowed_roles` is empty | PASS |

### 1.8 TestRBACDocumentFiltering (3 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_admin_sees_all` | Admin role can access chunks from all 3 test documents | PASS |
| 2 | `test_student_blocked_from_admin_doc` | Student role cannot access admin-only document chunks | PASS |
| 3 | `test_faculty_blocked_from_admin_doc` | Faculty role cannot access admin-only document chunks | PASS |

### 1.9 TestDocumentIngest (3 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_register_document` | `register_document` inserts a row and returns a valid doc_id | PASS |
| 2 | `test_get_all_documents` | `get_all_documents` returns all registered documents | PASS |
| 3 | `test_search_tool_no_index` | `make_search_tools` returns a tool that handles missing FAISS index gracefully | PASS |

### 1.10 TestChatEndpoint (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_valid_token_returns_200` | `POST /chat` with a valid JWT returns 200 with an `answer` field | PASS |
| 2 | `test_no_token_returns_401` | `POST /chat` without Authorization header returns 401 | PASS |
| 3 | `test_invalid_token_returns_401` | `POST /chat` with a malformed JWT returns 401 | PASS |
| 4 | `test_clear_returns_200` | `POST /chat/clear` with a valid JWT returns 200 with `cleared` field | PASS |

### 1.11 TestDocumentsMyEndpoint (5 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_returns_list` | `GET /documents/my` returns a JSON list | PASS |
| 2 | `test_no_token_returns_401` | `GET /documents/my` without token returns 401 | PASS |
| 3 | `test_admin_sees_all_ingested` | Admin role sees all INGESTED documents | PASS |
| 4 | `test_student_sees_only_allowed` | Student role sees only documents with "student" in allowed_roles | PASS |
| 5 | `test_excludes_non_ingested` | Documents with status != INGESTED are not returned | PASS |

---

## Section 2 — Manual Tests Performed During Build and Deployment

### 2a. RBAC Verification

| Test | User | Action | Expected | Actual | Status |
|------|------|--------|----------|--------|--------|
| Admin access all docs | admin / HMAdmin@2024 | Login, ask about Feature_7 | Full cited answer | Full cited answer with source + page | PASS |
| Admin access Feature_8 | admin | Ask about Feature_8 | Full cited answer | Full cited answer | PASS |
| Faculty limited access | faculty1 / HMFaculty@2024 | Login, view /documents/my | Feature_2, Feature_5, Feature_6 only | Correct filtered list | PASS |
| Student limited access | student1 / HMStudent@2024 | Login, view /documents/my | Feature_2 only | Correct filtered list | PASS |
| Faculty blocked from admin doc | faculty1 | Ask about Feature_7 | "could not find" response, no content leaked | Correct refusal, no restricted content | PASS |
| Student blocked from faculty doc | student1 | Ask about Feature_6 | "could not find" response | Correct refusal | PASS |

### 2b. Chat Response Quality

| Test | User | Query | Expected | Actual | Status |
|------|------|-------|----------|--------|--------|
| Detailed answer with citations | admin | "What was discussed in Feature 7 CS Faculty Senate Minutes Confidential?" | Detailed answer with Source + Page citations | Correct answer on first attempt | PASS |
| Deterministic responses | admin | Same question asked twice | Consistent answer both times | Previously returned inconsistent answers due to ReAct parse errors; fixed by retry logic (MAX_AGENT_RETRIES=3) | PASS (after fix) |
| Force-stop handling | any | Query that exhausts max_iterations | Graceful "could not find" message | "Agent stopped" replaced with user-friendly message | PASS |

**Root cause of inconsistency (now fixed):** The LLM occasionally produced malformed ReAct output (missing "Final Answer:" prefix), causing LangChain to raise a parse error. The agent would then return a fallback phrase without ever calling FAISS. The retry logic now distinguishes between genuine not-found (FAISS ran, no relevant chunks) and parse failures (FAISS never ran), retrying only the latter.

### 2c. AWS Deployment Verification

| Test | Method | Expected | Actual | Status |
|------|--------|----------|--------|--------|
| Backend health check | `GET /health` | `{"status": "ok"}` | `{"status":"ok","service":"Happiest Minds Knowledge Hub"}` | PASS |
| Login endpoint | `POST /auth/token` with admin creds | 200 with JWT | 200, received `access_token`, `username`, `role` | PASS |
| Document upload | `curl -X POST /admin/documents/upload` with PDF + roles | 200 with document ID | 200, document registered with correct ID | PASS |
| Document ingest | `curl -X POST /admin/documents/ingest` | 200, FAISS index built | 200, all documents moved to INGESTED status | PASS |
| Frontend loads | Browser → App Runner URL | Login page renders | Login page with HM branding, logo, test credentials displayed | PASS |
| End-to-end chat | Login via UI, send question | Answer returned with sources | Answer with source citations and reasoning steps | PASS |

**Deployment URL:** `https://gazfq7ai7a.ap-south-1.awsapprunner.com`

### 2d. OpenAI API Key Verification

| Test | Method | Expected | Actual | Status |
|------|--------|----------|--------|--------|
| Key validity | `curl https://api.openai.com/v1/models` with Bearer token | 200 with model list | 200, models returned | PASS |
| Invalid key error | Used incorrect key | 401 with error message | `openai.AuthenticationError` 401 `invalid_api_key` (not `insufficient_quota`) | PASS (error correctly classified as hard error — no retry) |

---

## Section 3 — Known Limitations Not Yet Tested

| Area | Gap | Risk | Notes |
|------|-----|------|-------|
| Load/stress testing | No concurrent user testing performed | Unknown behavior under high load | App Runner auto-scales, but FAISS is loaded in-memory per process |
| Persistent storage | Documents lost on container redeploy | High — admin must re-upload + re-ingest after every deploy | Known open issue; App Runner containers are stateless; mitigation: EFS or S3-backed storage |
| Session timeout | No test for JWT expiry during active session | Low — JWT expires after 8 hours | Frontend does not auto-refresh tokens |
| Direct FAISS fallback path | No automated test for `_direct_faiss_search` | Medium — fallback only triggers after MAX_AGENT_RETRIES (3) exhaustion | Would require mocking executor.invoke to fail 3 consecutive times, then verifying FAISS is called directly |
| Browser compatibility | Only tested in Chrome (macOS) | Low — standard React + inline CSS | No IE11 support expected |
| Large PDF handling | No test with PDFs > 10 MB | Low — 50 MB upload limit set but not stress-tested | PyPDFLoader may be slow on very large documents |
| Conversation memory overflow | No test for sessions exceeding `max_history_turns` (10) | Low — `ConversationBufferWindowMemory` auto-trims | Older messages silently dropped |
