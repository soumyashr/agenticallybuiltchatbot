# Validation Gap Analysis

Updated: 2026-03-11 (audit pass #2)

Generated: 2026-03-10
Source: `docs/Validation of Internal Chatbot Use cases.xlsx`

Cross-referenced against codebase at commit `bb5b12c` and Jira REST API v3.

**Update 2026-03-10:** C1, C2, C3, C4, M8 fixed — `_filter_sources_by_role()` added
to `agent.py`. Neutral/fallback responses now return empty sources `[]`.

**Update 2026-03-11:** UC-12 production interception fix applied — `detect_workflow_attempt()`
correctly wired before agent in chat endpoint. Citation enrichment applied to all code paths
with consistent filter→enrich order. Comma-separated `WORKFLOW_PATTERNS` env var parsing added
for App Runner compatibility.

---

## 🔴 Critical Gaps — ✅ ALL FIXED

| # | UC | Story | Observation | Code Location | Real Bug? | Effort |
|---|-----|-------|-------------|---------------|-----------|--------|
| C1 | UC-02 (Retrieve Authorized Info) | UIB-31 AC9, UIB-35 AC5 | **Restricted document names visible in citations.** Validator reports: "Unauthorized documents should not appear in the sources list, but they are currently visible." | `agent.py:228-255` (`_extract_sources`) — no role check on extracted sources. `agent.py:400-414` (`chat()`) — returns `sources` without filtering. `chat_router.py:71` — passes through unfiltered. | ✅ **FIXED.** `_filter_sources_by_role()` added in `agent.py`. Sources now checked against `get_allowed_roles_map()` before response return. | Medium |
| C2 | UC-03 (Enforce Access Control) | UIB-44 AC3-4 | **Neutral "could not find" message shown BUT citations still displayed.** Validator: "The chatbot provides a neutral message for unauthorized/restricted documents but still displays citations." | `agent.py:417-426` — when `_is_fallback_response(answer)=True` AND `_has_sources(intermediate)=True`, response returns the fallback message **plus** `sources: [s.dict() for s in sources]`. This is contradictory: user sees "no info" but also gets document references. | ✅ **FIXED.** Neutral/fallback responses now return `sources: []`. No document names leak. | Small |
| C3 | UC-02 | UIB-31 AC2-3 | **Restricted document details (title, source name) shown in response.** Validator: "The chatbot does not generate answers from restricted sources but displays the source title and details." / "Details of restricted documents are shown." | Same root cause as C1 — `_extract_sources()` at `agent.py:228-255`. Additionally, the LLM may echo restricted doc names in its `output` text even though search was filtered. No post-generation redaction exists. | ✅ **FIXED.** `_filter_sources_by_role()` provides defense-in-depth at citation layer. Restricted doc names stripped from `sources` array. | Medium |
| C4 | UC-03 | UIB-40 AC7 | **List of restricted documents displayed to end users.** Validator: "A list of restricted documents is displayed but should not be visible to end users." | Same root cause as C1/C3. The `sources` array in the API response may contain document names the user shouldn't see. No final-stage RBAC filter exists before response serialization. | ✅ **FIXED.** Same fix as C1 — `_filter_sources_by_role()` applied. | Medium |

---

## 🟡 Medium Gaps

| # | UC | Story | Observation | Code Location | Real Bug? | Effort |
|---|-----|-------|-------------|---------------|-----------|--------|
| M1 | UC-02 | UIB-35 AC1-7 | **Page numbers shown but proper citations not displayed.** Validator: "Page numbers are displayed for all answers, but proper citations are not shown." Citation format missing: high-level location, version/date, deep links. | `agent.py:132` (REACT_TEMPLATE) instructs `Source: [filename], Page: [number]` only. `models.py:29-32` (`SourceDoc`) has only `source`, `page`, `snippet` — no `location`, `version`, `url` fields. `tools.py:36-37` (`_format_docs`) outputs only name + page. | ✅ **FIXED.** `SourceDoc` enriched with `display_name` and `uploaded_at` from DynamoDB metadata. `_enrich_sources()` added to `agent.py`. Frontend updated to show display name and upload date. Deep links remain out of scope (no URL stored per chunk). | Medium |
| M2 | UC-02 | UIB-31 AC8 | **Responses not organized or summarized; appear as paragraphs.** Validator: "Responses are not organized or summarized; they appear as paragraphs." Also: "For unauthorized queries, a generic message is shown instead of a specific one." | `agent.py:112-150` (REACT_TEMPLATE) — prompt says "summarise it as your Final Answer" but does not instruct structured/bulleted output. No post-processing of LLM output for formatting. | **Partially real.** The LLM is instructed to summarize but not to format with bullets/structure. Prompt tuning needed, not a code bug. | Small |
| M3 | UC-02 | UIB-23 AC5 | **No audit log for approved document list changes.** Validator: "The approved list of documents change log/analytics is not displayed." | `documents_router.py:104,174-178` — uses `log.info()` to stdout only. `document_store.py:70-89` — no `deleted_by`, `deleted_at`, or audit fields in DynamoDB schema. No separate audit table exists. | **YES — real gap.** Only ephemeral application logs exist; no persistent, queryable audit trail for document CRUD operations. | Medium |
| M4 | UC-06 (Conversational Context) | UIB-93 AC4-7 | **Context points 4,5,6,7 unverified.** | Point 4: `session_memory_ttl_seconds` env-configurable. Point 5: still plaintext in memory (acceptable for server-side). Point 6: ✅ TTL added — sessions auto-expire. Point 7: sessions now expire, preventing stale cross-device reuse. | ✅ **FIXED — session TTL tests added (UIB-103, UIB-109).** TTL added via `_cleanup_expired_sessions()`. Point 5 (encryption) is an infrastructure concern, not a code bug. | Small |
| M5 | UC-02 | UIB-18 AC4 | **Session expiry functionality needs verification.** | ✅ Session memory now has TTL synchronized with JWT expiry (8h default). `_cleanup_expired_sessions()` called on every session access. Expired sessions evicted and recreated with fresh memory. | ✅ **FIXED.** `session_memory_ttl_seconds` config + lazy cleanup in `get_or_create_session()`. Tests added: UIB-103-GENERAL, UIB-109-GENERAL. | Small |
| M6 | UC-02 | UIB-23 AC6 | **Outage/error fallback needs validation.** Validator: "Needs validation under technical issue or outage conditions." | `agent.py:389-457` — retry loop (3 attempts). `agent.py:260-334` — `_direct_faiss_search()` fallback. `agent.py:321-326` — fallback synthesis error returns safe message. `tools.py:60-62` — no-index returns "No documents have been ingested." | **Already handled (partially).** Retry + fallback exists. But no explicit "knowledge sources unavailable" message as UIB-23 AC6 requires ("I'm unable to access internal knowledge sources right now"). Current fallback says "I could not find information..." which is ambiguous. | Small |
| M7 | UC-03 | UIB-48 | **Safe next steps suggestions — needs verification.** | Not implemented. No configurable suggestion system exists. The fallback message is static: "I could not find information on this topic in the documents accessible to you." No role-specific suggestions (e.g., "Contact student support"). | **Real gap.** UIB-48 requires optional, configurable next-step suggestions when no authorized content found. Not implemented at all. | Medium |
| M8 | UC-03 | UIB-52 | **Do not reveal restricted titles/snippets — needs verification.** | Same root cause as C1/C3/C4. Search filtering works (`tools.py:75-90`), but no post-generation redaction of restricted doc names from LLM output text or source citations. | ✅ **FIXED.** `_filter_sources_by_role()` now provides defense-in-depth at citation layer. Same fix as C1. | Medium |
| M9 | UC-16 (Admin Console) | UIB-482 AC1,4 | **No toggle for file formats; only PDF accepted. No max file size UI or admin reset.** Validator: "No option to toggle supported file formats" / "UI does not indicate max file size." | `documents_router.py` — upload endpoint accepts only PDF (hardcoded). No file-size limit validation in backend. No admin UI for format toggles. | **Real gap.** File format restriction is hardcoded, not configurable. No file size limit enforcement. | Medium |
| M10 | UC-16 | UIB-188 AC1,3,4 | **Role & Persona Management — points 1,3,4 not implemented.** Validator: "Point 2 is completely implemented. Points 1, 3, 4 need to be implemented." | `auth.py` — roles are hardcoded enum (`models.py` Role class: admin/faculty/student). No admin UI for persona management, mapping rules, or precedence config. | **Real gap.** Role definitions are static code, not admin-configurable. UC-16 dependency. | Large |
| M11 | UC-01 (Access Interface) | — | **Admin receives different responses. No separate Staff login. "Steps" indicator unclear. Mobile responsiveness not as expected.** | `models.py` Role enum: `admin`, `faculty`, `student` — no `staff` role. Staff/Faculty distinction not implemented. Mobile CSS: frontend uses inline styles, no responsive breakpoints verified. | **Partially real.** Missing `staff` role is a known scope gap. Mobile responsiveness is a frontend issue. | Medium |
| M12 | UC-02 | UIB-23 AC7 | **Chatbot does not automatically provide responses; further testing required.** | `agent.py:391` — `executor.invoke()` is synchronous within the async wrapper. Response requires explicit user query. No proactive/auto-response logic exists. | **Needs clarification.** "Automatically provide responses" is ambiguous — if it means "without user query", that's by design. If it means "response takes too long", that's a performance issue. | — |
| M13 | UC-02 | UIB-27 AC3 | **Source-system permissions (portal/KB/Confluence/Jira ACLs) need verification.** | `tools.py:11-26` (`_filter_by_role`) — filters by `allowed_roles` metadata set at upload time. No live integration with external ACL systems (Confluence, Jira, portal). | **Real gap by design.** RBAC is document-level metadata, not live ACL sync. Acceptable for current scope but doesn't satisfy "source-system permissions respected." | Large |

---

## 🟢 Low / Already Handled

| # | UC | Story | Observation | Code Location | Status |
|---|-----|-------|-------------|---------------|--------|
| L1 | UC-02 | UIB-31 AC5 | Error handling during answer generation needs verification. | `agent.py:389-457` — 3 retries, auth error detection, fallback to FAISS, safe error messages. `chat_router.py:73-76` — catches all exceptions, returns HTTP 500 with generic message. | ✅ **Already handled.** Retry + fallback + safe error messages exist. |
| L2 | UC-02 | UIB-23 AC2 | Restricted information not shown in answer text (but citations leak — see C1). | `tools.py:75-90` — search correctly filters by role before returning results to LLM. | ✅ **Search layer works.** Bug is in citation layer (C1), not search layer. |
| L3 | UC-03 | UIB-40 AC6 | Chatbot responses for timeout/error — needs verification. | `agent.py:437-448` — generic exceptions retried; `agent.py:454` — FAISS fallback after exhaustion. | ✅ **Already handled** via retry + fallback. |
| L4 | UC-06 | UIB-93 AC1 | Chatbot maintains conversational context. | `agent.py:177-182` — `ConversationBufferWindowMemory(k=10)` with `return_messages=False`. `agent.py:198-216` — session persistence via `_sessions` dict. | ✅ **Implemented.** Context maintained within session. |

---

## ⚠️ Out of Scope

| Item | Details |
|------|---------|
| **UC-18: Academic Knowledge Search** (UIB-513, UIB-514, UIB-519, UIB-524, UIB-529) | This UC does **not exist in the original UC-01 to UC-16 scope**. It was added to Jira as a new epic (UIB-513, parent of UIB-514/519/524/529) under UC-18. The validation spreadsheet includes observations for it (Row 19), but **no spec exists and no implementation has been done**. Observations include: response formatting issues, keyword-matching over-inclusion in source lists, grammar-sensitive campus queries, lack of multi-document consolidation. These are general RAG quality issues that would apply to any UC, not Academic Search-specific bugs. |
| **UC-17: Multilingual** (UIB-502) | Referenced in JIRA_TRACKER but not in validation sheet. No spec, no implementation. |
| **UC-19: Cross-Department Search** (UIB-534) | Referenced in JIRA_TRACKER but not in validation sheet. No spec, no implementation. |
| **UC-04: Retrieve Latest Document Version** (UIB-56) | Validation sheet Row 6: "No observations recorded yet." Version governance not implemented per CONFLICTS.md. |
| **UC-05: Handle Multiple Relevant Documents** (UIB-74) | Validation sheet Row 7: "No observations recorded yet." Multi-doc consolidation partially implemented via RAG. |
| **UC-07 through UC-15** | Validation sheet shows "No observations recorded yet" or "Validation pending" for all of these. |

---

## Summary

| Metric | Count |
|--------|-------|
| Total observations analyzed | 27 (across 18 spreadsheet rows) |
| 🔴 Critical bugs confirmed | 4 (C1–C4, all ✅ FIXED — RBAC citation filter added) |
| 🟡 Medium gaps confirmed | 13 (M1–M13) |
| 🟢 Already handled | 4 (L1–L4) |
| ⚠️ Out of scope | 5 UCs (UC-04, UC-05, UC-17, UC-18, UC-19) |
| Blocked on UC-16 (Admin Console) | 3 items (M9, M10, UIB-143-AC4) |

### Root Cause Analysis

**The #1 issue is a single architectural gap:** no post-generation RBAC filter on citations.

- C1, C2, C3, C4, and M8 all trace back to the same root cause
- `_extract_sources()` in `agent.py:228-255` performs zero role validation
- `chat()` returns sources unfiltered at `agent.py:400-414`
- Fix: add a role-aware filter between `_extract_sources()` and the response dict
- This single fix resolves 5 of the 4 critical + 1 medium findings

### Recommended Next Batch (Top 3 Priorities)

1. **UIB-52 / UIB-44 / UIB-35 — RBAC citation filter** (fixes C1+C2+C3+C4+M8)
   - Add role-based filtering to `_extract_sources()` or as a post-extraction step
   - Clear `sources` array when returning fallback/neutral messages
   - Effort: Medium (~1 day), impact: resolves all 4 critical bugs

2. **UIB-35 — Citation format enrichment** (fixes M1)
   - Extend `SourceDoc` model with `location`, `version_date`, `url` fields
   - Update `_format_docs()` and `_extract_sources()` to populate new fields
   - Effort: Medium (~1 day)

3. **UIB-93 — Session TTL + memory cleanup** (fixes M4, M5)
   - Add TTL to `_sessions` dict (e.g., `cachetools.TTLCache`)
   - Align session lifetime with JWT expiry
   - Effort: Small (~2 hours)

---

## Audit Pass #2 — 2026-03-11

### Test Coverage Gaps Fixed
- UC-06/UIB-98: Session clear/reset — 3 new tests added
- UC-07/UIB-103: Session expiry context clear — 2 new tests added
- UC-07/UIB-109: Fresh session on new start — 2 new tests added
- UC-08/UIB-113,117: Ambiguous query clarification — 3 new tests (prompt verification)
- UC-09/UIB-123,126: Fallback response — 2 additional tests
- UC-13/UIB-157,161: Irrelevant query handling — 3 new tests (prompt verification)
- 28 previously untagged tests now have AC references
- Total tests: 210 (was 193), all passing

### Remaining Gaps (unchanged)
- M2: Response organization/summarization — prompt tuning needed
- M3: Audit log for document changes — not implemented
- M6: Outage/error fallback — partially handled
- M7: Safe next steps (UIB-48) — not implemented
- M9-M13: UC-16 Admin Console gaps — blocked on UC-16
