# UC-08: Clarify Ambiguous or Broad Queries

**Jira Stories:** UIB-113, UIB-117  
**Sprint:** Sprint 1  
**Priority:** P1  
**Author:** Soumya Shrivastava  
**Last Updated:** March 2026  

---

## Why This Matters

Right now if a student types "courses" or "tell me about documents" the chatbot
either dumps everything it knows or returns "I could not find information."
Neither is useful. The user gets frustrated and loses trust in the product.

The fix is simple — before we even call the LLM or search FAISS, we check
whether the query is too vague to answer meaningfully. If it is, we return
two targeted clarification options as clickable chips. The user clicks one,
the refined query goes through the normal pipeline, and they get a good answer.

This is the single biggest UX improvement we can ship without touching
infrastructure.

---

## What We're Building

```
User types "courses"
        ↓
pre_process.py checks: is this too vague?
        ↓ YES
generate_clarification_questions() returns:
  ["the course syllabus", "the assessment criteria"]
        ↓
Response returned with is_clarification: true
        ↓
Frontend renders clickable chips:
  [ the course syllabus ]  [ the assessment criteria ]
        ↓
User clicks a chip → that text is submitted as next query
        ↓
Normal RAG pipeline runs with the refined query
        ↓
Good answer with citations ✅
```

---

## What We Are NOT Doing

- Not calling the LLM to detect vague queries — that's too slow and expensive
- Not changing the RAG pipeline, FAISS, or agent logic
- Not adding new dependencies
- Not touching auth, ingest, tools, or config
- Not changing any existing test

The detection is pure Python string logic. Fast, cheap, deterministic.

---

## Design Decisions

This section explains every architectural choice made before writing a single
line of code. If you are a developer reading this for the first time, read
this section before looking at the implementation — it will save you hours
of confusion later.

A senior engineer exploring this codebase would spend 15-20 minutes reading
the existing files before making these decisions. Here is what they found
and why each decision was made the way it was.

---

### Decision 1 — Why a new file `pre_process.py` instead of adding to `agent.py`

**What we found when reading `agent.py`:**
```
agent.py already handles:
  - Building the LLM (_build_llm)
  - Creating the ReAct agent executor (_create_executor)
  - Managing sessions (get_or_create_session)
  - Retry logic and fallback (chat function — ~100 lines)
  - Source extraction (_extract_sources)
  - Direct FAISS fallback (_direct_faiss_search)
```

`agent.py` is already doing too much. Adding detection logic there
would make it even harder to read, test, and maintain.

**The principle applied:** Single Responsibility Principle — each file
should have one reason to change. `agent.py` changes when agent
orchestration changes. A new `pre_process.py` changes only when query
preprocessing changes. These are independent concerns.

**Why `pre_process.py` specifically?**
The name describes exactly what it does — it runs BEFORE the agent
processes the query. Python convention is snake_case descriptive names.
`pre_process.py` is immediately obvious to any developer who opens the
`app/` folder.

**Alternatives considered and rejected:**

| Alternative | Why rejected |
|-------------|-------------|
| Add to `agent.py` | Already too large, mixes concerns |
| Add to `tools.py` | tools.py is for FAISS search tools, not query analysis |
| Add to `config.py` | config.py is for settings, not logic |
| Add to `chat_router.py` | Router should route, not analyse query content |

---

### Decision 2 — Why pure Python string detection instead of an LLM call

**The naive approach** — ask the LLM: "Is this query too vague?"

That costs one LLM API call (~$0.002) on every single message before
we even start answering. With 1000 messages per day that is $2/day
just for vague detection — and it adds 1-2 seconds of latency to
every query.

**What we do instead** — three deterministic string checks:
1. Word count < 5
2. Contains a broad term from a fixed list
3. No specific noun found

This runs in under 1 millisecond, costs nothing, and is fully
testable with simple unit tests. No mocking required.

**The tradeoff accepted:**
The string rules will miss some edge cases that an LLM would catch.
That is acceptable. We would rather occasionally miss a vague query
(it falls through to the normal pipeline and gets a mediocre answer)
than add latency and cost to every single query.

---

### Decision 3 — Why ALL THREE conditions must be true, not just one

**Early draft used OR logic** — flag if any condition matched.

Testing showed this caused too many false positives:
- "What is FAISS?" → flagged because it contains "what is"
  but it is actually a specific technical question
- "Explain CS405" → flagged on word count but "CS405" is specific
- "List" → flagged but too aggressive, user might be following up

**Switching to AND logic** — all three must match simultaneously:
- "What is FAISS?" → passes Condition 3 (has "FAISS", specific noun)
  → NOT flagged → direct answer ✅
- "Explain CS405" → passes Condition 3 (has "CS405") → NOT flagged ✅
- "What is the syllabus" → fails Condition 3 ("syllabus" is 8 chars,
  specific noun) → NOT flagged → direct answer ✅
- "courses" → fails all three → FLAGGED → clarification ✅

The three-condition AND gate gives precision over recall. We would
rather ask for clarification less often and correctly than constantly
interrupt users with unnecessary questions.

---

### Decision 4 — Why clarification options come from `allowed_collections`

**The temptation** — hardcode a list of topic categories:
```python
options = ["the syllabus", "the assessment criteria",
           "the academic calendar", "the faculty guidelines"]
```

This breaks role safety. A student would see "the faculty guidelines"
as a chip option even though they cannot access that content.
Clicking it would either fail with "not found" or worse — leak the
existence of restricted documents.

**The correct approach** — derive options only from `allowed_collections`,
which is the same RBAC-filtered list that FAISS already uses.

```
Student allowed_collections: ["Feature2_CS405_Syllabus.pdf"]
Admin allowed_collections:   all five documents

Student gets chips from CS405 Syllabus only.
Admin gets chips from all five documents.
```

The RBAC boundary is enforced automatically — no special-case code.

---

### Decision 5 — Why a `try/except` wraps the clarification block

If `generate_clarification_questions()` raises any exception,
we do NOT want the chat to fail. The user asked a question and
deserves an answer — even if it is a vague one.

The `try/except` logs a warning and falls through to the normal
agent pipeline. The user gets a response either way.

This is a graceful degradation pattern — clarification is an
enhancement, not a requirement for the core function to work.

---

### Decision 6 — Why `is_clarification` and `clarification_options` are in ALL response dicts

The frontend needs a consistent response shape. If some responses
have these fields and others do not, the React component needs
defensive null checks everywhere:

```javascript
// Without consistent shape — messy:
if (response.is_clarification !== undefined &&
    response.is_clarification === true) { ... }

// With consistent shape — clean:
if (response.is_clarification) { ... }
```

By adding `is_clarification=False` and `clarification_options=[]`
to every return dict in `agent.py`, the frontend can always safely
read these fields without null checks. Small backend discipline,
significantly cleaner frontend code.

---

### How to Apply This Thinking to Future Features

When implementing a new feature, ask these questions in order:

```
1. What does each existing file already own?
   Read every file in backend/app/ before deciding.

2. Does this logic belong in an existing file or a new one?
   New file if it is a new concern.
   Existing file only if it is the same concern.

3. If new file — write one sentence describing what it does.
   That sentence becomes the filename.

4. What is the failure mode if this feature breaks?
   Catastrophic → make it required, no fallthrough.
   Non-critical → wrap in try/except, fall through gracefully.

5. Does this feature touch any security boundary (RBAC, auth)?
   If yes — derive from existing security primitives.
   Never hardcode a separate list.
```

Following this process takes 20-30 minutes per feature but saves
days of debugging and refactoring later.

---

## Files Changed

| File | Type | What changes |
|------|------|-------------|
| `backend/app/pre_process.py` | New | Detection logic + question generation |
| `backend/app/agent.py` | Modified | Clarification short-circuit before FAISS |
| `backend/app/routers/chat_router.py` | Modified | New response fields |
| `frontend/src/components/ChatMessage.jsx` | Modified | Clickable suggestion chips |
| `backend/tests/test_agent_logic.py` | Modified | 6 new tests added |

---

## Understanding the Detection Logic

This is the core of the feature. Read this before implementing.

```python
def is_ambiguous_query(query: str) -> bool:
```

We flag a query as ambiguous only if ALL THREE conditions are true simultaneously:

**Condition 1 — Too short**
Query has fewer than 5 words. "courses" or "tell me" are too short to be specific.

**Condition 2 — Contains a broad term**
Query starts with or contains one of the broad terms:
`tell me, what is, explain, about, overview, everything, all about,
describe, summary, summarize, give me, show me, list, what are`

**Condition 3 — No specific noun**
Query has no word longer than 6 characters that is not a stop word.
"CS405" or "syllabus" or "Faculty" are specific nouns.
"about" or "the" or "me" are not.

Why all three? Because we don't want false positives. "What is the Tier 4
Restricted Data Protocol?" contains "what is" (broad term) but it's a
specific question — it passes Condition 3 (has "Restricted", "Protocol").
So it correctly goes to the RAG pipeline without triggering clarification.

---

## Role Safety — Non-Negotiable

The clarification options must never reveal restricted content.

**Wrong — leaks admin content to student:**
```
Are you asking about the Faculty Senate Minutes or the Tier 4 Protocol?
```

**Correct — role-safe for student:**
```
Are you asking about the course syllabus or the assessment criteria?
```

The `generate_clarification_questions()` function must filter options based
on `allowed_collections` — the same RBAC list already used by FAISS.
If a collection is not in the user's allowed list, it never appears
as a clarification option.

---

## Claude Code Prompt

> Copy everything inside the code block and paste into Claude Code.

```
Implement UC-08: Clarify Ambiguous or Broad Queries.
Jira stories: UIB-113 (detect ambiguous queries) and UIB-117
(ask for clarification before answering).

Current state:
  - backend/app/agent.py has a clarify_ambiguous_prompt config
    that defaults to empty
  - The prompt template has a CLARIFICATION section
  - No deterministic detection exists — it relies purely on LLM
  - No suggestion chips exist in the frontend

Required changes — no infrastructure changes needed:

─────────────────────────────────────────────────────────────
CHANGE 1 — Create backend/app/pre_process.py
─────────────────────────────────────────────────────────────
Create a new file backend/app/pre_process.py with:

  BROAD_TERMS = [
      "tell me", "what is", "explain", "about", "overview",
      "everything", "all about", "describe", "summary", "summarize",
      "give me", "show me", "list", "what are"
  ]

  def is_ambiguous_query(query: str) -> bool:
      """
      Returns True only if ALL THREE conditions are true:
        1. Query word count < 5
        2. Query contains a broad term from BROAD_TERMS
        3. Query has no specific noun (no word > 6 chars
           that is not a stop word)
      A query is only flagged if genuinely vague — not just short.
      """

  def generate_clarification_questions(
      query: str,
      allowed_collections: list[str],
      role: str
  ) -> list[str]:
      """
      Returns exactly 2 clarification options based on:
        - The user's query intent
        - The document categories in allowed_collections only
      Never mentions document names or topics outside
      allowed_collections — role safety is mandatory.
      Returns short plain strings without punctuation.
      Example: ["the course syllabus", "the assessment criteria"]
      """

  CLARIFICATION_RESPONSE_TEMPLATE = (
      "Your question is a bit broad. "
      "Are you asking about {option_1} or {option_2}? "
      "Or you can rephrase your question for a more specific answer."
  )

─────────────────────────────────────────────────────────────
CHANGE 2 — Update backend/app/agent.py chat() function
─────────────────────────────────────────────────────────────
At the top of the chat() function, before calling
executor.invoke(), add this block:

  from app.pre_process import is_ambiguous_query, \
      generate_clarification_questions, \
      CLARIFICATION_RESPONSE_TEMPLATE

  if is_ambiguous_query(message):
      try:
          questions = generate_clarification_questions(
              query=message,
              allowed_collections=allowed_collections,
              role=role.value
          )
          if questions and len(questions) >= 2:
              answer = CLARIFICATION_RESPONSE_TEMPLATE.format(
                  option_1=questions[0],
                  option_2=questions[1]
              )
              return {
                  "answer":                answer,
                  "session_id":            session_id,
                  "role":                  role.value,
                  "sources":               [],
                  "reasoning_steps":       0,
                  "fallback_used":         False,
                  "error_type":            None,
                  "is_clarification":      True,
                  "clarification_options": questions,
              }
      except Exception as e:
          log.warning(f"Clarification generation failed: {e}. "
                      f"Falling through to normal agent.")

Add is_clarification=False and clarification_options=[] to ALL
other return dicts in chat() so the response shape is always
consistent regardless of which path is taken.

─────────────────────────────────────────────────────────────
CHANGE 3 — Update backend/app/routers/chat_router.py
─────────────────────────────────────────────────────────────
Add the two new fields to the ChatResponse model:

  class ChatResponse(BaseModel):
      answer:                str
      session_id:            str
      role:                  str
      sources:               list
      reasoning_steps:       int
      fallback_used:         bool
      error_type:            Optional[str]
      is_clarification:      bool = False
      clarification_options: list[str] = []

─────────────────────────────────────────────────────────────
CHANGE 4 — Update frontend chat message component
─────────────────────────────────────────────────────────────
Find the component that renders bot messages
(likely ChatMessage.jsx or MessageList.jsx).

When is_clarification is true AND clarification_options
has 2 or more items:
  - Render the answer text as normal
  - Below the answer render a row of clickable chips
  - Each chip shows one option from clarification_options
  - Clicking a chip calls the existing sendMessage() function
    with that chip text as the message
  - Chips styled: background #009797 (HM teal), white text,
    border-radius 16px, padding 6px 14px, cursor pointer
  - Chips disappear after one is clicked (set state)
  - Gap between chips: 8px

No changes needed in frontend/src/services/api.js —
the existing chat fetch already returns the full response.

─────────────────────────────────────────────────────────────
CHANGE 5 — Add tests to backend/tests/test_agent_logic.py
─────────────────────────────────────────────────────────────
Add a new class TestAmbiguousQueryDetection:

  test_short_query_flagged
    "courses" → is_ambiguous_query() returns True

  test_specific_query_not_flagged
    "What are the assessment criteria for CS405?"
    → is_ambiguous_query() returns False

  test_broad_term_flagged
    "tell me about the syllabus" → returns True

  test_reasonable_query_not_flagged
    "What is the deadline for assignment submission in CS405?"
    → returns False

  test_clarification_response_is_role_safe
    Generate clarification for student role.
    Assert none of the options mention admin-only or
    faculty-only document names.

  test_response_shape_always_consistent
    Mock both a clarification response and a normal response.
    Assert both have is_clarification and clarification_options
    fields present.

─────────────────────────────────────────────────────────────
CONSTRAINTS
─────────────────────────────────────────────────────────────
- Do not change auth.py, ingest.py, tools.py, config.py
- Do not change any of the existing 43 tests
- Do not add any new pip dependencies
- Detection must be pure Python — no LLM call
- If clarification generation fails fall through silently
  to normal agent execution (handled in Change 2 try/except)
- Student must never see restricted content in chip options

─────────────────────────────────────────────────────────────
AFTER ALL CHANGES — verification and deployment
─────────────────────────────────────────────────────────────

Step 1 — Run full test suite:
  python3 -m pytest backend/tests/test_agent_logic.py -v
  Expected: 49 tests passing (43 existing + 6 new)

Step 2 — Syntax check all changed files:
  python3 -c "
  import ast
  for f in ['backend/app/pre_process.py',
            'backend/app/agent.py',
            'backend/app/routers/chat_router.py']:
      ast.parse(open(f).read())
      print(f'syntax ok: {f}')
  "

Step 3 — Start backend locally:
  cd backend
  source .venv/bin/activate
  uvicorn app.main:app --reload --port 8000

Step 4 — Start frontend locally (new terminal tab):
  cd frontend
  VITE_API_URL=http://localhost:8000 npm run dev
  Open http://localhost:5173 in browser

Step 5 — Ingest documents locally:
  TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
    -F "username=admin" -F "password=HMAdmin@2024" | \
    python3 -c "import sys,json; \
    print(json.load(sys.stdin)['access_token'])")

  curl -X POST http://localhost:8000/admin/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test_docs/Feature2_CS405_Advanced_Data_Structures_Algorithm_Optimization_Syllabus.pdf" \
    -F "display_name=Feature 2 CS405 Syllabus" \
    -F 'allowed_roles=["admin","faculty","student"]'

  curl -X POST http://localhost:8000/admin/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test_docs/Feature_5_Academic_Operations_Manual_2026-2027.pdf" \
    -F "display_name=Feature 5 Academic Operations Manual" \
    -F 'allowed_roles=["admin","faculty"]'

  curl -X POST http://localhost:8000/admin/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test_docs/Feature_6_Curriculum_Design_Assessment_Moderation_Blueprint.pdf" \
    -F "display_name=Feature 6 Curriculum Design Blueprint" \
    -F 'allowed_roles=["admin","faculty"]'

  curl -X POST http://localhost:8000/admin/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test_docs/Feature_7_CS_Faculty_Senate_Minutes_Confidential.pdf" \
    -F "display_name=Feature 7 Faculty Senate Minutes" \
    -F 'allowed_roles=["admin"]'

  curl -X POST http://localhost:8000/admin/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test_docs/Feature_8_Tier_4_Restricted_Data_Protocol.pdf" \
    -F "display_name=Feature 8 Tier 4 Restricted Data Protocol" \
    -F 'allowed_roles=["admin"]'

  curl -X POST http://localhost:8000/admin/documents/ingest \
    -H "Authorization: Bearer $TOKEN"

Step 6 — Verify clarification works via API:
  curl -s -X POST http://localhost:8000/chat \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"message":"courses","session_id":"uc08-test"}' | \
    python3 -m json.tool | \
    grep -E "is_clarification|clarification_options|answer"

  Expected:
    "is_clarification": true,
    "clarification_options": ["...", "..."],
    "answer": "Your question is a bit broad..."

Step 7 — Commit and push to GitHub:
  git add backend/app/pre_process.py \
          backend/app/agent.py \
          backend/app/routers/chat_router.py \
          backend/tests/test_agent_logic.py
  git commit -m "feat: UC-08 clarify ambiguous queries (UIB-113, UIB-117)

  - Add pre_process.py with is_ambiguous_query() detection
  - Add generate_clarification_questions() role-safe function
  - Add clarification short-circuit in agent.py chat()
  - Add is_clarification + clarification_options to response shape
  - Add clickable suggestion chips in frontend
  - Add 6 new tests — all passing
  - All 43 existing tests still passing"

  git push origin main

Step 8 — Push to GitLab:
  git checkout gitlab-main
  git merge main
  git push gitlab gitlab-main:main
  git checkout main

Step 9 — Confirm both remotes are updated:
  git log --oneline -3
  git remote -v
```

---

## Testing Guide

### Before Implementation — Take Baseline Screenshots

Login at https://gazfq7ai7a.ap-south-1.awsapprunner.com and
run the queries below. Screenshot every response — you need a
clear before/after comparison to validate the feature worked.

**Queries that SHOULD trigger clarification (currently don't):**

| Query to type | What happens today | What should happen after |
|---------------|--------------------|--------------------------|
| `courses` | Dumps content or not found | Clarification chips appear |
| `tell me about documents` | Vague answer | Clarification chips appear |
| `explain` | Not found | Clarification chips appear |
| `overview` | Not found | Clarification chips appear |
| `what is the syllabus` | Generic answer | Clarification chips appear |

**Queries that should NOT trigger clarification:**

| Query to type | Expected behaviour |
|---------------|--------------------|
| `What are the assessment criteria for CS405?` | Direct answer, no chips |
| `What was discussed in the Faculty Senate meeting?` | Direct answer, no chips |
| `What is the Tier 4 Restricted Data Protocol?` | Direct answer, no chips |

### Local Test — Always Do This Before Deploying

```
1. Run the Claude Code prompt → code changes made locally
2. Start backend:  uvicorn app.main:app --reload --port 8000
3. Start frontend: VITE_API_URL=http://localhost:8000 npm run dev
4. Open http://localhost:5173
5. Ingest documents using the curl commands in Step 5 above
6. Run all test queries — verify chips appear for vague queries
7. Run the curl API test — verify is_clarification: true
8. Happy with results? → commit and push to App Runner
```

### Role-Safety Test — Do Not Skip This

Login as **student1 / HMStudent@2024** and type:
```
tell me about documents
overview
what is available
```

The chips must NEVER show:
- Faculty Senate Minutes (Feature 7 — faculty/admin only)
- Tier 4 Restricted Data Protocol (Feature 8 — admin only)
- Any content the student role cannot access

If restricted content appears in chips — the role safety check
is broken. Do not deploy until this is fixed.

### Pass Criteria

| Check | How to verify |
|-------|--------------|
| 49 tests pass | `pytest backend/tests/test_agent_logic.py -v` |
| Vague query → chips appear | Type "courses" in chat |
| Specific query → no chips | Type full specific question |
| Chips are clickable | Click one — it submits as next query |
| Chips disappear after click | Visual check in browser |
| Student sees no restricted chips | Login as student1 and test |
| `is_clarification` in API response | curl test in Step 6 |
| GitHub updated | `git log --oneline -3` |
| GitLab updated | Check gitlab.happiestminds.com/root/INTLSE01 |

---

## How This Fits the Bigger Picture

This feature directly improves three other UCs:

**UC-02 (Retrieve Authorized Information)** — better input queries
mean better FAISS retrieval and better answers overall.

**UC-09 (Handle No Matching Content)** — fewer "not found" responses
because vague queries never reach FAISS in the first place.

**UC-13 (Handle Irrelevant Queries)** — clarification catches
accidental broad queries before they hit the out-of-scope detector.

After this ships, the chatbot will feel genuinely intelligent to
anyone watching a demo — it asks a smart follow-up instead of
guessing or failing. That's the difference between a prototype
and a product.

---

## Troubleshooting

**Clarification triggering on specific queries**
The detection is too aggressive. Check `is_ambiguous_query()` — 
all three conditions must be true simultaneously. A specific noun 
in the query like "CS405" or "Protocol" should always pass 
Condition 3 and prevent triggering.

**Chips not showing in frontend**
Check that `is_clarification` is coming through in the API response:
```bash
curl ... | python3 -m json.tool | grep is_clarification
```
If it is missing, the `ChatResponse` model in `chat_router.py`
was not updated correctly.

**Existing 43 tests breaking after changes**
The most likely cause is the response shape change in `agent.py`.
Every `return {}` in the `chat()` function must now include
`is_clarification=False` and `clarification_options=[]`.
Check all return paths — there are several.

**GitLab push rejected (protected branch)**
```bash
# Unprotect in GitLab UI first:
# Settings → Repository → Protected Branches → Unprotect main
git push gitlab gitlab-main:main --force
# Re-protect after push completes
```

**Student sees restricted content in chips**
The `generate_clarification_questions()` function is not filtering
by `allowed_collections`. Add a check: only include a topic in
the options if its source document is in `allowed_collections`.

---

## Maintenance Notes

| Scenario | What to update |
|----------|---------------|
| New broad term to detect | Add to `BROAD_TERMS` in `pre_process.py` |
| New document category added | Update `generate_clarification_questions()` context |
| Chip styling change requested | Update chip CSS in `ChatMessage.jsx` |
| New role added to system | Update role-safe filter in `generate_clarification_questions()` |
| Clarification text needs rewording | Update `CLARIFICATION_RESPONSE_TEMPLATE` in `pre_process.py` |

---

*Version 1.0 | March 2026 | Soumya Shrivastava | Happiest Minds Technologies*
