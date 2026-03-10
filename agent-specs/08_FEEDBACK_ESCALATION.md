# 08 — FEEDBACK & ESCALATION
# UC-15 (User Feedback) and UC-10 (Unanswered Query Escalation)
# Prerequisites: 05_AGENT.md and 07_ADMIN_API.md must be COMPLETE.

---

## Overview

Two new DynamoDB tables and supporting backend/frontend code:

| Feature | Table | Endpoints | Frontend |
|---------|-------|-----------|----------|
| UC-15 Feedback | hm-feedback | POST /feedback, GET /admin/feedback | 👍/👎 buttons on each assistant message |
| UC-10 Escalation | hm-escalations | GET /admin/escalations | (automatic — triggered by agent) |

---

## STEP 1 — Config Fields (backend/app/config.py)

Added to `Settings`:
```python
feedback_table: str = "hm-feedback"
escalation_table: str = "hm-escalations"
clarify_ambiguous_prompt: str = ""       # UC-08
irrelevant_query_response: str = ""      # UC-13
slack_webhook_url: str = ""              # UC-10
escalation_enabled: bool = True          # UC-10
```

---

## STEP 2 — DynamoDB Stores

### backend/app/feedback_store.py

- Table: `hm-feedback` (partition key: `id` STRING)
- `init_feedback_table()` — creates table if not exists
- `save_feedback(session_id, message, response_preview, rating, comment, user_role) -> str`
  - Truncates `response_preview` to 200 chars
  - Returns UUID string
- `get_all_feedback() -> list[dict]`
- `get_feedback_by_session(session_id) -> list[dict]`

### backend/app/escalation_store.py

- Table: `hm-escalations` (partition key: `id` STRING)
- `init_escalation_table()` — creates table if not exists
- `save_escalation(session_id, query, user_role, reason) -> str`
  - reason: `"no_answer_found"` or `"agent_parse_failure"`
  - Returns UUID string
- `get_all_escalations() -> list[dict]`
- `mark_escalation_notified(esc_id) -> None`

---

## STEP 3 — Pydantic Models (backend/app/models.py)

```python
from typing import Literal

class FeedbackRequest(BaseModel):
    session_id: str
    message: str
    response_preview: str
    rating: Literal["positive", "negative"]
    comment: str = ""

class FeedbackResponse(BaseModel):
    id: str
    status: str
```

---

## STEP 4 — Feedback Router (backend/app/routers/feedback_router.py)

Two routers:
- `router` — public endpoints
- `admin_router` — admin-only endpoints

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /feedback | Any authenticated user | Submit feedback (positive/negative + optional comment) |
| GET | /admin/feedback | Admin only | View all feedback |
| GET | /admin/escalations | Admin only | View all escalations |

---

## STEP 5 — Agent Escalation (backend/app/agent.py)

### Escalation Triggers

1. **Final parse-failure attempt** (within retry loop, attempt == MAX_AGENT_RETRIES):
   - Reason: `"no_answer_found"`
2. **All retries exhausted** (before FAISS fallback):
   - Reason: `"agent_parse_failure"`

### Helpers

- `_notify_slack(role, message)` — async, sends webhook POST, swallows all exceptions
- `_escalate(session_id, message, role_value, reason)` — saves to DynamoDB + calls Slack, never raises

### Slack Webhook Payload
```json
{
  "text": ":warning: *Unanswered Query Escalation*\n*Role:* student\n*Query:* What is quantum...\n*Time:* 2026-03-10T..."
}
```

---

## STEP 6 — Frontend Feedback UI

### Modified Files
- `frontend/src/services/api.js` — added `submitFeedback()` function
- `frontend/src/hooks/useChat.js` — added `userQuery` to assistant messages, exposed `sessionId`
- `frontend/src/App.jsx` — passes `sessionId` and `token` through to MessageList
- `frontend/src/components/chat/MessageList.jsx` — passes `sessionId` and `token` to MessageBubble
- `frontend/src/components/chat/MessageBubble.jsx` — 👍/👎 feedback row on each assistant message
- `frontend/src/config/theme.js` — added `teal: '#009797'`

### Feedback UI States
1. **idle** — shows 👍 and 👎 buttons
2. **selected** — shows selected rating, comment input, Submit button
3. **submitted** — shows "Thanks for your feedback!"

### API Call
```javascript
submitFeedback(token, {
  sessionId,
  message: message.userQuery,
  responsePreview: message.content.slice(0, 200),
  rating: 'positive' | 'negative',
  comment: '...',
})
```

---

## STEP 7 — Startup (backend/app/main.py)

Added to `startup()`:
```python
from app.feedback_store import init_feedback_table
from app.escalation_store import init_escalation_table
init_feedback_table()
init_escalation_table()
```

Added router registrations:
```python
app.include_router(feedback_router.router,                          tags=["Feedback"])
app.include_router(feedback_router.admin_router,   prefix="/admin", tags=["Admin"])
```

---

## Tests

### test_feedback.py (12 tests)

| Class | Tests | Coverage |
|-------|-------|----------|
| TestFeedbackStore | 5 | DynamoDB CRUD, truncation, defaults |
| TestFeedbackEndpoint | 7 | POST /feedback, auth, validation, admin GET, RBAC |

### test_escalation.py (10 tests)

| Class | Tests | Coverage |
|-------|-------|----------|
| TestEscalationStore | 3 | DynamoDB CRUD, mark_notified |
| TestEscalationLogic | 5 | Agent integration, Slack webhook, failure resilience |
| TestEscalationEndpoint | 2 | Admin GET, student 403 |

All tests use `moto` to mock DynamoDB. No real AWS calls.

---

## Dependencies

- `httpx>=0.27.0` — Async HTTP client used by `_notify_slack()` for Slack webhook POST requests

---

## VERIFICATION CHECKLIST

- [ ] `POST /feedback` with valid token and `rating: "positive"` returns 200
- [ ] `POST /feedback` with `rating: "maybe"` returns 422 (validation error)
- [ ] `POST /feedback` without token returns 401
- [ ] `GET /admin/feedback` with admin token returns list of feedback
- [ ] `GET /admin/feedback` with student token returns 403
- [ ] `GET /admin/escalations` with admin token returns list of escalations
- [ ] `GET /admin/escalations` with student token returns 403
- [ ] Agent parse failure triggers escalation save to DynamoDB
- [ ] Slack webhook called when `SLACK_WEBHOOK_URL` is set
- [ ] Slack failure does not break chat response
- [ ] Frontend 👍/👎 buttons appear on assistant messages
- [ ] Clicking 👍 shows comment input and Submit button
- [ ] Submitting feedback shows "Thanks for your feedback!"
- [ ] `python3 -m pytest tests/ -v` — all 105 tests pass
- [ ] `cd frontend && npm run build` — succeeds
