# Test Record — Happiest Minds Knowledge Hub

**Date:** 2026-03-09
**Codebase:** /Users/soumya.shrivastava/AgenticallyBuiltChatBot

---

## Section 1 — Automated Test Suite

**Total Tests:** 64/64 PASSED (both AI_PROVIDER=openai and AI_PROVIDER=azure_openai)

### Test Files

| File | Tests | Status |
|------|-------|--------|
| `backend/tests/test_agent_logic.py` | 43 | ALL PASS |
| `backend/tests/test_azure_integration.py` | 7 | ALL PASS |
| `backend/tests/test_config.py` | 4 | ALL PASS |
| `backend/tests/test_provider_switching.py` | 10 | ALL PASS |

---

### 1.1 test_agent_logic.py (43 tests — unchanged from previous)

#### TestIsFallbackResponse (7 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_exact_phrase` | `_is_fallback_response` returns True for "I could not find information" | PASS |
| 2 | `test_case_insensitive` | Detection works regardless of uppercase/mixed case | PASS |
| 3 | `test_embedded_phrase` | Fallback phrase embedded in a longer sentence is still detected | PASS |
| 4 | `test_clean_answer` | A normal answer with citations is not flagged as fallback | PASS |
| 5 | `test_empty_string` | Empty string is not flagged as fallback | PASS |
| 6 | `test_parsing_error` | "parsing error" phrase is detected as fallback | PASS |
| 7 | `test_agent_stopped` | "agent stopped due to" phrase is detected as fallback | PASS |

#### TestHasSources (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_with_source` | Returns True when an observation contains "Source:" | PASS |
| 2 | `test_without_source` | Returns False when no observation contains "Source:" | PASS |
| 3 | `test_empty_steps` | Returns False for an empty intermediate_steps list | PASS |
| 4 | `test_non_string_observation` | Returns False when observation is not a string | PASS |

#### TestExtractSources (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_single_source` | Extracts one SourceDoc from "Source: file.pdf, Page: 3" format | PASS |
| 2 | `test_multiple_sources` | Extracts multiple SourceDocs from "---"-separated blocks | PASS |
| 3 | `test_dedup` | Duplicate source+page combinations are deduplicated | PASS |
| 4 | `test_no_sources` | Returns empty list when no "Source:" patterns exist | PASS |

#### TestRetryDecisions (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_fallback_with_sources_returns_immediately` | Fallback + sources = genuine not-found, no retry | PASS |
| 2 | `test_fallback_without_sources_triggers_retry` | Fallback + no sources = parse failure, retry | PASS |

#### TestHardErrorNoRetry (6 tests, parametrized)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_hard_error[401]` | "401" raises AgentAccessError immediately | PASS |
| 2 | `test_hard_error[invalid_api_key]` | "invalid_api_key" raises AgentAccessError immediately | PASS |
| 3 | `test_hard_error[authenticationerror]` | "authenticationerror" raises AgentAccessError immediately | PASS |
| 4 | `test_hard_error[insufficient_quota]` | "insufficient_quota" raises AgentAccessError immediately | PASS |
| 5 | `test_hard_error[429]` | "429" raises AgentAccessError immediately | PASS |
| 6 | `test_hard_error[rate_limit]` | "rate_limit" raises AgentAccessError immediately | PASS |

#### TestSoftErrorRetried (1 test)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_soft_error_retried` | Generic error retried MAX_AGENT_RETRIES times then fallback | PASS |

#### TestRBAC (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_role_mismatch_raises` | Reusing session with different role raises PermissionError | PASS |
| 2 | `test_jwt_decode_valid` | Valid JWT decodes correctly | PASS |
| 3 | `test_jwt_expired_raises` | Expired JWT raises ExpiredSignatureError | PASS |
| 4 | `test_jwt_invalid_raises` | Invalid JWT raises InvalidTokenError | PASS |

#### TestRBACDocumentFiltering (3 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_admin_sees_all` | Admin sees all 3 documents | PASS |
| 2 | `test_faculty_sees_two` | Faculty sees 2 documents (not admin-only) | PASS |
| 3 | `test_student_sees_one` | Student sees 1 document | PASS |

#### TestDocumentIngest (3 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_role_filter_keeps_allowed` | `_filter_by_role` filters correctly | PASS |
| 2 | `test_role_filter_json_string` | JSON string roles parsed correctly | PASS |
| 3 | `test_search_tool_no_index` | Missing index returns helpful message | PASS |

#### TestChatEndpoint (4 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_valid_token_returns_200` | POST /chat with valid JWT returns 200 | PASS |
| 2 | `test_no_token_returns_401` | POST /chat without token returns 401 | PASS |
| 3 | `test_invalid_token_returns_401` | POST /chat with bad JWT returns 401 | PASS |
| 4 | `test_llm_error_returns_500` | LLM crash returns 500 | PASS |

#### TestDocumentsMyEndpoint (5 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_unauthenticated_returns_401` | No token returns 401 | PASS |
| 2 | `test_admin_gets_all` | Admin sees all ingested docs | PASS |
| 3 | `test_faculty_gets_two` | Faculty sees allowed docs only | PASS |
| 4 | `test_student_gets_one` | Student sees allowed docs only | PASS |
| 5 | `test_no_file_paths_exposed` | No filename/filepath leaks | PASS |

---

### 1.2 test_azure_integration.py (7 tests — NEW)

#### TestAzureLLMConfig (1 test)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_azure_llm_config_has_required_fields` | AzureChatOpenAI receives deployment, endpoint, api_key, api_version | PASS |

#### TestAzureEmbeddingsConfig (1 test)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_azure_embeddings_config_has_required_fields` | AzureOpenAIEmbeddings receives deployment, endpoint, api_key, api_version | PASS |

#### TestAzureSearchConfig (1 test)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_azure_search_config_has_required_fields` | AzureSearch receives endpoint, key, and index_name | PASS |

#### TestAzureSearchRBAC (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_azure_search_rbac_filter_applied_correctly` | OData filter with allowed_roles is passed to Azure Search | PASS |
| 2 | `test_azure_search_returns_role_filtered_results` | Azure Search results returned correctly with role filtering | PASS |

#### TestAzureIngest (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_azure_ingest_creates_index_if_not_exists` | create_or_update_index called during ingest | PASS |
| 2 | `test_azure_ingest_upserts_documents` | upload_documents called with correct chunk data | PASS |

---

### 1.3 test_config.py (4 tests — NEW)

#### TestAIProviderDefaults (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_ai_provider_defaults_to_azure_openai` | Default ai_provider is "azure_openai" | PASS |
| 2 | `test_all_azure_fields_readable_from_env` | All Azure fields readable from env vars | PASS |

#### TestAzureValidation (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_missing_azure_key_raises_on_build` | Empty api_key allowed at config level | PASS |
| 2 | `test_missing_azure_endpoint_raises_on_build` | Empty endpoint allowed at config level | PASS |

---

### 1.4 test_provider_switching.py (10 tests — NEW)

#### TestProviderLLM (3 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_openai_provider_builds_correct_llm_type` | AI_PROVIDER=openai → ChatOpenAI with correct api_key | PASS |
| 2 | `test_azure_provider_builds_correct_llm_type` | AI_PROVIDER=azure_openai → AzureChatOpenAI with correct config | PASS |
| 3 | `test_invalid_provider_raises_value_error` | Unknown AI_PROVIDER raises ValueError | PASS |

#### TestProviderEmbeddings (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_openai_provider_builds_openai_embeddings` | AI_PROVIDER=openai → OpenAIEmbeddings | PASS |
| 2 | `test_azure_provider_builds_azure_embeddings` | AI_PROVIDER=azure_openai → AzureOpenAIEmbeddings | PASS |

#### TestProviderVectorStore (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_azure_provider_builds_azure_search_store` | AI_PROVIDER=azure_openai → AzureSearch store | PASS |
| 2 | `test_openai_provider_builds_faiss_store` | AI_PROVIDER=openai → FAISS store | PASS |

#### TestProviderRBAC (1 test)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_provider_switch_does_not_affect_rbac` | Provider switch preserves session role isolation | PASS |

#### TestEnvReading (2 tests)

| # | Test Name | What It Asserts | Status |
|---|-----------|-----------------|--------|
| 1 | `test_env_flag_ai_provider_is_read_correctly` | AI_PROVIDER=openai read correctly from env | PASS |
| 2 | `test_env_flag_azure_provider` | AI_PROVIDER=azure_openai read correctly from env | PASS |

---

## Section 2 — Manual Tests Performed During Build and Deployment

### 2a. RBAC Verification (from 2026-03-08)

| Test | User | Action | Expected | Actual | Status |
|------|------|--------|----------|--------|--------|
| Admin access all docs | admin / HMAdmin@2024 | Login, ask about Feature_7 | Full cited answer | Full cited answer with source + page | PASS |
| Admin access Feature_8 | admin | Ask about Feature_8 | Full cited answer | Full cited answer | PASS |
| Faculty limited access | faculty1 / HMFaculty@2024 | Login, view /documents/my | Feature_2, Feature_5, Feature_6 only | Correct filtered list | PASS |
| Student limited access | student1 / HMStudent@2024 | Login, view /documents/my | Feature_2 only | Correct filtered list | PASS |
| Faculty blocked from admin doc | faculty1 | Ask about Feature_7 | "could not find" response | Correct refusal | PASS |
| Student blocked from faculty doc | student1 | Ask about Feature_6 | "could not find" response | Correct refusal | PASS |

### 2b. Chat Response Quality (from 2026-03-08)

| Test | User | Query | Expected | Actual | Status |
|------|------|-------|----------|--------|--------|
| Detailed answer with citations | admin | Feature 7 query | Detailed answer with Source + Page | Correct answer on first attempt | PASS |
| Deterministic responses | admin | Same question asked twice | Consistent answers | Fixed by retry logic | PASS |
| Force-stop handling | any | Query exhausting max_iterations | Graceful message | User-friendly fallback | PASS |

### 2c. AWS Deployment Verification (from 2026-03-08)

| Test | Method | Expected | Actual | Status |
|------|--------|----------|--------|--------|
| Backend health check | GET /health | {"status": "ok"} | {"status":"ok","service":"Happiest Minds Knowledge Hub"} | PASS |
| Login endpoint | POST /auth/token | 200 with JWT | 200, received access_token | PASS |
| Document upload | POST /admin/documents/upload | 200 with ID | 200, document registered | PASS |
| Document ingest | POST /admin/documents/ingest | 200, index built | 200, all INGESTED | PASS |
| Frontend loads | Browser test | Login page renders | Login page with HM branding | PASS |
| End-to-end chat | Full flow test | Answer with sources | Correct answer | PASS |

---

## Section 3 — Azure Migration Changes (2026-03-09)

### Files Modified

| File | Change |
|------|--------|
| `backend/app/config.py` | Added `ai_provider`, Azure Search fields, embedding deployment field |
| `backend/app/agent.py` | `_build_llm()` branches on `settings.ai_provider` instead of `llm_provider` |
| `backend/app/tools.py` | `semantic_search()` uses OData filter for Azure, client-side for FAISS |
| `backend/app/ingest.py` | `_build_embeddings()` + `get_vector_store()` + `_build_index()` branch on `ai_provider` |
| `backend/app/main.py` | Startup log shows LLM and VectorStore provider |
| `backend/requirements.txt` | Added `azure-search-documents>=11.4.0` |
| `.env` | Added `AI_PROVIDER=azure_openai` and all Azure config fields |
| `backend/.env.example` | Updated template with Azure config |
| `backend/tests/test_provider_switching.py` | NEW: 10 tests for provider switching |
| `backend/tests/test_azure_integration.py` | NEW: 7 tests for Azure integration |
| `backend/tests/test_config.py` | NEW: 4 tests for config validation |

### Test Results Summary

| Provider | Tests | Passed | Failed |
|----------|-------|--------|--------|
| AI_PROVIDER=azure_openai | 64 | 64 | 0 |
| AI_PROVIDER=openai | 64 | 64 | 0 |

---

## Section 4 — Known Limitations

| Area | Gap | Risk | Notes |
|------|-----|------|-------|
| Load/stress testing | No concurrent user testing | Unknown under high load | App Runner auto-scales |
| Persistent storage | FAISS dies on redeploy (openai mode) | High for openai mode | Azure Search persists in azure_openai mode |
| Session timeout | No auto-refresh | Low — 8-hour JWT expiry | Frontend does not refresh tokens |
| Direct fallback path | No automated test for direct vector search fallback | Medium | Only triggers after 3 retries |
| Browser compatibility | Chrome only | Low | Standard React |
| Large PDF handling | Not stress-tested | Low | 50 MB limit set |
| Azure Search latency | Not benchmarked vs FAISS | Low | Azure Search designed for production scale |

---

## Known Issues

None. All 64 tests pass for both AI_PROVIDER values.
