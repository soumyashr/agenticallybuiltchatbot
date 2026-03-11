# Test Record — Happiest Minds Knowledge Hub

**Date:** 2026-03-10
**Codebase:** /Users/soumya.shrivastava/AgenticallyBuiltChatBot

---

## Summary

| Metric | Value |
|--------|-------|
| Total tests | 193 |
| Pass | 193 |
| Fail | 0 |
| Test files | 10 |
| Python | 3.11.9 |
| Runner | pytest 9.0.2 |

Both provider configurations tested:

| Provider | Tests | Passed | Failed |
|----------|-------|--------|--------|
| AI_PROVIDER=openai | 193 | 193 | 0 |
| AI_PROVIDER=azure_openai | 193 | 193 | 0 |

---

## Test Files

### 1. test_agent_logic.py (76 tests)

Covers: agent retry logic, RBAC filtering, document ingest, chat endpoint,
GET /documents/my sidebar endpoint.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestIsFallbackResponse | 7 | `_is_fallback_response()` unit tests |
| TestHasSources | 4 | `_has_sources()` unit tests |
| TestExtractSources | 4 | `_extract_sources()` source citation parsing |
| TestRetryDecisions | 2 | Agent retry logic (fallback + no-retry paths) |
| TestHardErrorNoRetry | 6 | Auth/rate-limit errors raise immediately (parametrized) |
| TestSoftErrorRetried | 1 | Timeout errors retried, then fallback |
| TestRBAC | 4 | JWT decode, expiry, role mismatch |
| TestRBACDocumentFiltering | 3 | Role-based document visibility (admin/faculty/student) |
| TestDocumentIngest | 3 | `_filter_by_role`, JSON string roles, no-index search |
| TestChatEndpoint | 4 | POST /chat: 401, 200, 500 paths |
| TestDocumentsMyEndpoint | 5 | GET /documents/my: auth, filtering, no field leaks |
| TestFormGuidanceUC11 | 12 | UC-11 form guidance: UIB-140 (6 tests, AC1-AC6), UIB-143 (5 tests, AC1,2,3,5,6), + 1 prompt verification |

AC tags used: `# AC: UIB-140-AC1` through `# AC: UIB-140-AC6`,
`# AC: UIB-143-AC1`, `# AC: UIB-143-AC2`, `# AC: UIB-143-AC3`,
`# AC: UIB-143-AC5`, `# AC: UIB-143-AC6`.

| TestRBACCitationFilter | 6 | RBAC citation filter: UIB-31 (role filtering), UIB-35 (no restricted docs), UIB-44 (neutral=empty sources), UIB-40 (fallback=empty), UIB-52 (admin sees all), regression guard |
| TestSessionTTLUC07 | 6 | Session TTL: expired eviction, valid preservation, explicit clear, TTL configurable, no cross-session leak, fresh context after expiry |
| TestCitationFormatUC02 | 9 | Citation format enrichment: display_name populated, uploaded_at populated, unknown file stays raw, metadata error returns raw, extract+enrich pipeline, empty sources no call, SourceDoc new fields optional, faculty role enrichment (PROD1), all-paths consistency (PROD2) |

AI_PROVIDER coverage: provider-agnostic (mocks LLM/tools at function level).

### 2. test_config.py (4 tests)

Covers: Settings class defaults, Azure field validation.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestAIProviderDefaults | 2 | Default ai_provider, Azure env var reading |
| TestAzureValidation | 2 | Missing Azure key/endpoint at config level |

AI_PROVIDER coverage: tests both `openai` and `azure_openai` values.

### 3. test_azure_integration.py (7 tests)

Covers: Azure-specific LLM, embeddings, search, RBAC filtering, ingest pipeline.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestAzureLLMConfig | 1 | AzureChatOpenAI required fields |
| TestAzureEmbeddingsConfig | 1 | AzureOpenAIEmbeddings required fields |
| TestAzureSearchConfig | 1 | AzureSearch endpoint/key/index_name |
| TestAzureSearchRBAC | 2 | OData filter applied, role-filtered results |
| TestAzureIngest | 2 | Index creation, document upsert |

AI_PROVIDER coverage: all tests use `ai_provider="azure_openai"`.

### 4. test_document_store.py (15 tests)

Covers: DynamoDB-backed document_store CRUD operations.
Uses `moto` library to mock AWS DynamoDB — no real AWS calls.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestInitDB | 2 | Table creation, idempotent init |
| TestRegisterDocument | 3 | UUID id, retrievable, multiple registers |
| TestGetHelpers | 4 | Pending, ingested, roles map, sort order |
| TestStatusTransitions | 4 | INGESTING, INGESTED, FAILED, full lifecycle |
| TestDeleteDocument | 2 | Delete removes item, nonexistent is no-op |

AI_PROVIDER coverage: provider-independent (DynamoDB works regardless of AI_PROVIDER).

### 5. test_provider_switching.py (14 tests)

Covers: AI_PROVIDER flag switching between `openai` and `azure_openai`.
Validates correct LLM, embeddings, and vector store are instantiated.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestProviderLLM | 3 | OpenAI LLM, Azure LLM, invalid provider |
| TestProviderEmbeddings | 2 | OpenAI embeddings, Azure embeddings |
| TestProviderVectorStore | 2 | FAISS (openai), AzureSearch (azure_openai) |
| TestProviderRBAC | 1 | Provider switch does not affect RBAC |
| TestEnvReading | 2 | AI_PROVIDER env var read correctly |
| TestOpenAIProviderUsesCorrectStack | 2 | OpenAI uses FAISS not Azure, OpenAI embeds not Azure |
| TestProviderDocumentStoreIndependence | 2 | DynamoDB works with both providers |

AI_PROVIDER coverage: explicitly tests both `openai` and `azure_openai` paths.

### 6. test_feedback.py (12 tests)

Covers: UC-15 feedback — DynamoDB store, POST /feedback, GET /admin/feedback.
Uses `moto` library to mock AWS DynamoDB.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestFeedbackStore | 5 | save_returns_uuid, correct_fields, by_session, truncated, comment_default |
| TestFeedbackEndpoint | 7 | positive, negative, requires_auth, invalid_rating_422, admin_view, student_403, comment_optional |

AI_PROVIDER coverage: provider-independent (DynamoDB works regardless of AI_PROVIDER).

### 7. test_escalation.py (11 tests)

Covers: UC-10 escalation — DynamoDB store, agent escalation logic, Slack webhook, admin endpoint.
Uses `moto` library to mock AWS DynamoDB, extensive mocking of agent internals.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestEscalationStore | 3 | save_uuid, correct_fields, mark_notified |
| TestEscalationLogic | 6 | saved_on_no_answer, saved_on_parse_failure, slack_sent_when_configured, slack_failure_no_break, httpx_importable, no_slack_when_no_webhook |
| TestEscalationEndpoint | 2 | admin_view, student_403 |

AI_PROVIDER coverage: provider-agnostic (mocks LLM/tools at function level).

### 8. test_guardrails.py (27 tests)

Covers: UC-14 two-layer abuse & security guardrails — sync pattern checks,
LLM classification (mocked), integration, config defaults, HTTP endpoint regression.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestLayer1PatternChecks | 12 | Length limit, injection patterns (4 variants + case-insensitive), repeated chars, script injection (2 variants), clean message, off-topic passes |
| TestLayer2LLMCheck | 5 | UNSAFE blocks, SAFE passes, LLM error fail-open, unexpected response passes, layer2 disabled skips |
| TestGuardrailIntegration | 2 | Layer 1 blocks before Layer 2, both layers pass |
| TestGuardrailConfig | 2 | guardrail_max_length default, guardrail_layer2_enabled default |
| TestGuardrailEndpointIntegration | 6 | HTTP 400 for injection/long/script/act-as, HTTP 200 for clean, escalation logging |

NOTE: TestGuardrailEndpointIntegration (6 tests) added after production
incident — guardrail layer1 fired in isolation but endpoint returned 200.
Root cause: guardrail try/except was nested inside the outer agent try/except
with no fail-open handler; `_build_llm()` inside the guardrail block could
throw non-GuardrailViolation exceptions, bypassing the guardrail entirely and
falling through to the agent. Fix: separated guardrail and agent into two
independent try/except blocks with a generic `except Exception: pass` for
fail-open on guardrail infrastructure errors. Lesson: always test guardrails
at HTTP layer via TestClient, not only at module level.

AI_PROVIDER coverage: provider-agnostic (mocks LLM at function level).

### 9. test_cors.py (5 tests)

Covers: CORS header validation via FastAPI TestClient preflight and actual requests.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestCORSHeaders | 5 | Preflight from frontend origin, preflight from localhost, rejected unknown origin, actual request CORS header, config contains frontend URL |

NOTE: CORS tests added after production incident — curl bypasses CORS so
browser-only failures are invisible to curl-based smoke tests. The frontend
App Runner URL was missing from allow_origins; only discovered when opening
the browser UI. Lesson: always test CORS at the HTTP layer, not just via curl.

AI_PROVIDER coverage: provider-independent (CORS is infrastructure-level).

### 10. test_workflow_guard.py (22 tests)

Covers: UC-12 workflow execution prevention — pattern detection, configurable patterns, HTTP endpoint integration, escalation logging.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestWorkflowDetection | 10 | submit/approve/apply/process/enroll detection, case-insensitive, informational queries pass, exception contains pattern |
| TestWorkflowConfig | 3 | Custom patterns override, empty config uses defaults, pipe-separated patterns |
| TestWorkflowConfig | 5 | Custom patterns override, empty config uses defaults, pipe-separated patterns (legacy), default patterns non-empty (PROD3), comma-separated env var parsing (PROD5) |
| TestWorkflowEndpointIntegration | 7 | Refusal response returned (agent not called), blocked for admin too, informational reaches agent, escalation logged, production regression — intercepted before agent (PROD1), patterns loaded from config (PROD2), detection before agent full path (PROD4) |

AI_PROVIDER coverage: provider-independent (workflow guard is pre-agent infrastructure).

---

## Key Tests for AI_PROVIDER Switching

These tests specifically verify that the `AI_PROVIDER` flag correctly switches
the entire AI stack:

| Test | Provider | What it verifies |
|------|----------|-----------------|
| `test_openai_provider_builds_correct_llm_type` | openai | ChatOpenAI instantiated |
| `test_azure_provider_builds_correct_llm_type` | azure_openai | AzureChatOpenAI instantiated |
| `test_openai_provider_uses_faiss_not_azure_search` | openai | FAISS used, AzureSearch NOT called |
| `test_openai_provider_uses_openai_embeddings_not_azure` | openai | OpenAIEmbeddings used, AzureOpenAIEmbeddings NOT called |
| `test_azure_provider_builds_azure_search_store` | azure_openai | AzureSearch instantiated |
| `test_switching_provider_does_not_break_document_store` | any | DynamoDB unaffected by provider |
| `test_dynamo_works_regardless_of_ai_provider` | openai | DynamoDB CRUD works with openai provider |

---

## Architectural Changes Reflected in Tests

### DynamoDB replacing SQLite documents.db
- `test_document_store.py` (15 tests) uses moto to mock DynamoDB
- All CRUD operations tested: register, get, update status, delete
- Table creation tested (init_db idempotent)
- UUID string IDs (not auto-increment integers)

### Azure OpenAI LLM + Embeddings
- `test_azure_integration.py` verifies AzureChatOpenAI and AzureOpenAIEmbeddings config
- `test_provider_switching.py` verifies correct provider selected per AI_PROVIDER

### Azure AI Search replacing FAISS
- `test_azure_integration.py` verifies AzureSearch config and OData RBAC filters
- `test_provider_switching.py` verifies FAISS used for openai, AzureSearch for azure_openai

### Agent retry logic + typed exceptions
- `test_agent_logic.py` covers MAX_AGENT_RETRIES, hard/soft error classification
- AgentAccessError, AgentParseError, AgentRetrievalError tested

### Dependencies added
- `boto3>=1.34.0` — DynamoDB access
- `moto[dynamodb]>=5.0.0` — DynamoDB mocking in tests
- `azure-search-documents>=11.4.0` — Azure AI Search
- `azure-identity>=1.15.0` — Azure authentication
- `httpx` — Async HTTP client for Slack webhook notifications

---

## Running Tests

```bash
# Default (azure_openai)
cd backend && python3 -m pytest tests/ -v

# Explicit openai
cd backend && AI_PROVIDER=openai python3 -m pytest tests/ -v

# Explicit azure_openai
cd backend && AI_PROVIDER=azure_openai python3 -m pytest tests/ -v

# Single file
cd backend && python3 -m pytest tests/test_document_store.py -v
```

---

## Manual Tests (from deployment verification 2026-03-08)

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| GET /health | {"status": "ok"} | OK | PASS |
| POST /auth/token (admin) | 200 + JWT | OK | PASS |
| POST /admin/documents/upload | 200 + doc ID | OK | PASS |
| POST /admin/documents/ingest | 200, INGESTED | OK | PASS |
| Admin asks Feature_7 query | Cited answer | OK | PASS |
| Faculty asks Feature_7 query | "could not find" | OK | PASS |
| Student asks Feature_7 query | "could not find" | OK | PASS |
| Frontend loads on App Runner | Login page | OK | PASS |

---

## Known Limitations

| Area | Gap | Notes |
|------|-----|-------|
| Load testing | No concurrent user tests | App Runner auto-scales |
| FAISS persistence | Lost on redeploy (openai mode) | Azure Search persists (azure_openai mode) |
| Direct fallback path | No automated test for vector store fallback after 3 retries | Only triggers on exhausted retries |
| Token refresh | No auto-refresh | 8-hour JWT expiry |

---

## Known Issues

None. All 193 tests pass for both AI_PROVIDER values.
