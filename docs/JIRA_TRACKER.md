# Jira Story Tracker

Last Updated: 2026-03-10

## Tracking Rules

- Status is updated by Claude Code after each implementation session
- AC Count = number of acceptance criteria in Jira story
- Tests = number of tagged tests in codebase (# AC: UIB-XXX-ACN)
- Jira is read-only — status tracked locally here

## Story Status

| UC | Epic ID | Story ID | Story Title | AC Count | Tests | Status |
|----|---------|----------|-------------|----------|-------|--------|
| UC-01 | UIB-2 | UIB-1 | Access chatbot widget from approved internal systems | 0 | 0 | ✅ Done |
| UC-01 | UIB-2 | UIB-3 | Seamless SSO-based access to chatbot | 0 | 0 | ✅ Done |
| UC-01 | UIB-2 | UIB-10 | Determine user persona from authentication context | 0 | 0 | ✅ Done |
| UC-01 | UIB-2 | UIB-14 | Start chatbot interaction on user trigger | 0 | 0 | ✅ Done |
| UC-02 | UIB-22 | UIB-18 | Submit a natural-language query | 0 | 0 | ✅ Done |
| UC-02 | UIB-22 | UIB-23 | Retrieve from approved knowledge sources only | 0 | 0 | ✅ Done |
| UC-02 | UIB-22 | UIB-27 | Apply role/group-based permissions to filter results | 0 | 0 | ✅ Done |
| UC-02 | UIB-22 | UIB-31 | Generate response using only authorized content | 0 | 0 | ✅ Done |
| UC-02 | UIB-22 | UIB-35 | Provide citations and links only to authorized documents — enriched with display_name + uploaded_at | 7 | 7 | ✅ Done |
| UC-03 | UIB-39 | UIB-40 | Filter to authorized documents only | 0 | 0 | ✅ Done |
| UC-03 | UIB-39 | UIB-44 | Neutral response when only restricted documents match | 0 | 0 | ✅ Done |
| UC-03 | UIB-39 | UIB-48 | Suggest safe next steps (optional, configurable) | 0 | 0 | ✅ Done |
| UC-03 | UIB-39 | UIB-52 | Do not reveal restricted titles, locations, snippets, or existence | 0 | 0 | ✅ Done |
| UC-04 | UIB-56 | UIB-57 | Admin enables governed current/approved retrieval | 0 | 0 | ⚠️ Partial |
| UC-04 | UIB-56 | UIB-61 | Use only current, approved versions of documents | 0 | 0 | ⚠️ Partial |
| UC-04 | UIB-56 | UIB-65 | Ignore drafts, archived, and superseded versions | 0 | 0 | ❌ Pending |
| UC-04 | UIB-56 | UIB-69 | Cite exact version used (name + version/effective date + link) | 0 | 0 | ❌ Pending |
| UC-05 | UIB-74 | UIB-75 | Aggregate multiple relevant documents | 0 | 0 | ⚠️ Partial |
| UC-05 | UIB-74 | UIB-79 | Consolidate insights into one clear answer | 0 | 0 | ⚠️ Partial |
| UC-05 | UIB-74 | UIB-83 | Cite multiple sources where applicable | 0 | 0 | ⚠️ Partial |
| UC-05 | UIB-74 | UIB-88 | Help users when many documents are relevant | 0 | 0 | ❌ Pending |
| UC-06 | UIB-92 | UIB-93 | Maintain context within an active session | 0 | 0 | ✅ Done |
| UC-06 | UIB-92 | UIB-98 | Allow user to clear or reset context within a session | 0 | 0 | ✅ Done |
| UC-07 | UIB-102 | UIB-103 | Clear context when session expires or user logs out | 0 | 0 | ✅ Done |
| UC-07 | UIB-102 | UIB-109 | Start fresh context on new session start | 0 | 0 | ✅ Done |
| UC-08 | UIB-108 | UIB-113 | Detect ambiguous or overly broad queries | 0 | 0 | ✅ Done |
| UC-08 | UIB-108 | UIB-117 | Ask user for clarification before answering | 0 | 0 | ✅ Done |
| UC-09 | UIB-122 | UIB-123 | Detect when no matching or authorized content exists | 0 | 0 | ✅ Done |
| UC-09 | UIB-122 | UIB-126 | Return safe fallback instead of speculative answer | 0 | 0 | ✅ Done |
| UC-10 | UIB-130 | UIB-131 | Detect and log unanswered queries with metadata | 0 | 11 | ✅ Done |
| UC-10 | UIB-130 | UIB-135 | Route unanswered queries to designated university teams | 0 | 11 | ✅ Done |
| UC-11 | UIB-139 | UIB-140 | Answer questions about form purpose and usage | 6 | 6 | ✅ Done |
| UC-11 | UIB-139 | UIB-143 | Guide users on where to find forms | 6 | 5 | ⚠️ Partial (AC4 blocked on UC-16) |
| UC-12 | UIB-147 | UIB-148 | Detect workflow-execution attempts | 10 | 10 | ✅ Done |
| UC-12 | UIB-147 | UIB-152 | Inform users that workflow execution is not supported | 7 | 7 | ✅ Done |
| UC-13 | UIB-156 | UIB-157 | Detect irrelevant or out-of-scope queries | 0 | 0 | ✅ Done |
| UC-13 | UIB-156 | UIB-161 | Provide polite decline and scope guidance | 0 | 0 | ✅ Done |
| UC-14 | UIB-165 | UIB-166 | Detect abusive or harmful queries | 0 | 27 | ✅ Done |
| UC-14 | UIB-165 | UIB-170 | Block or safely respond according to policy | 0 | 27 | ✅ Done |
| UC-14 | UIB-165 | UIB-174 | Log and optionally escalate security events | 0 | 27 | ✅ Done |
| UC-15 | UIB-178 | UIB-179 | Allow users to rate chatbot responses | 0 | 12 | ✅ Done |
| UC-15 | UIB-178 | UIB-183 | Capture optional free-text feedback | 0 | 12 | ✅ Done |
| UC-16 | UIB-187 | UIB-188 | Role & Persona Management | 0 | 0 | ❌ Pending |
| UC-16 | UIB-187 | UIB-192 | Repository Connector Setup | 0 | 0 | ❌ Pending |
| UC-16 | UIB-187 | UIB-196 | Indexing & Sync Controls | 0 | 0 | ❌ Pending |
| UC-16 | UIB-187 | UIB-200 | Session & Experience Controls | 0 | 0 | ❌ Pending |
| UC-16 | UIB-187 | UIB-204 | Fallback & User Messaging | 0 | 0 | ❌ Pending |
| UC-16 | UIB-187 | UIB-208 | Escalation Routing & Notifications | 0 | 0 | ⚠️ Partial |
| UC-16 | UIB-187 | UIB-212 | Branding & UI Theming | 0 | 0 | ⚠️ Partial |
| UC-16 | UIB-187 | UIB-216 | Analytics & Logging Dashboard | 0 | 0 | ❌ Pending |
| UC-16 | UIB-187 | UIB-482 | Allowed File Formats & Content Processing | 0 | 0 | ❌ Pending |
| UC-16 | UIB-187 | UIB-487 | Connector Settings & Governance | 0 | 0 | ❌ Pending |
| UC-17 | UIB-502 | UIB-503 | Multilingual Query Input | 0 | 0 | ❌ Pending |
| UC-17 | UIB-502 | UIB-508 | Multilingual Response Policy | 0 | 0 | ❌ Pending |
| UC-18 | UIB-513 | UIB-514 | Search Student Policies and Course Learning Docs | 0 | 0 | ❌ Pending |
| UC-18 | UIB-513 | UIB-519 | Campus Navigation and Accessibility Search | 0 | 0 | ❌ Pending |
| UC-18 | UIB-513 | UIB-524 | Search Faculty Academic Operations & Collaboration Docs | 0 | 0 | ❌ Pending |
| UC-18 | UIB-513 | UIB-529 | Role-Aware Filtering and Restricted Content Handling | 0 | 0 | ❌ Pending |
| UC-19 | UIB-534 | UIB-535 | Department Source Onboarding | 0 | 0 | ❌ Pending |
| UC-19 | UIB-534 | UIB-540 | Persona-Based Department Access | 0 | 0 | ❌ Pending |
| UC-19 | UIB-534 | UIB-545 | Cross-Department Search & Routing | 0 | 0 | ❌ Pending |
| UC-19 | UIB-534 | UIB-550 | Unified Answer Format Across Departments | 0 | 0 | ❌ Pending |

## Notes

- **AC Count = 0** for all stories: Jira stories contain only user story descriptions (As a... I want... So that...) with no separate acceptance criteria sections.
- **Tests** column shows test counts from test modules covering that UC (shared across stories in the same UC).
- **UC-17 through UC-19** are additional epics discovered in Jira beyond the original UC-01 to UC-16 scope.
- Status determined by cross-referencing `docs/TEST_RECORD.md` and `agent-specs/` implementation files.
