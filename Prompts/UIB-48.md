mplement UIB-48 — Suggest safe next steps.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRE-FLIGHT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot
git pull origin main
git log --oneline -3
source .venv/bin/activate
 
# Baseline test count
python3 -m pytest backend/tests/ --tb=no -q 2>&1 | tail -3
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — FETCH STORY FROM JIRA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetch UIB-48 full details via Jira REST API v3:
GET https://$JIRA_BASE_URL/rest/api/3/issue/UIB-48
  ?fields=summary,description,customfield_10016,status
 
Extract and print:
- Summary
- Status
- All Acceptance Criteria points (every AC)
 
DO NOT proceed to implementation until AC is printed.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — READ CODEBASE BEFORE CODING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Read these files completely:
- backend/app/agent.py (full file)
- backend/app/tools.py (full file)
- backend/app/config.py
- backend/app/models.py
- backend/app/routers/chat_router.py (full file)
- agent-specs/05_AGENT.md
- agent-specs/03_BACKEND_CORE.md
 
Understand:
- How the agent generates responses
- Where the final answer is assembled
- How sources are returned
- What the chat response model looks like
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — DESIGN BEFORE CODING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Based on AC from Jira and codebase reading:
 
Design the implementation approach:
- Where will next_steps be generated?
  (agent.py post-processing? tools.py? chat_router.py?)
- What format will next_steps be returned in?
  (list of strings? part of answer text? separate field?)
- How will next_steps be safe?
  (no workflow actions, no form submissions,
   info/guidance only)
- What triggers next_steps?
  (every response? only when sources found?
   only for certain query types?)
 
Print design decision before writing any code.
If design conflicts with AC — flag the conflict.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4 — IMPLEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Implement UIB-48 following the design from Step 3.
 
Guidelines:
- Next steps must be SAFE — informational only
  Examples of safe next steps:
  ✅ "Refer to the Student Handbook section 3.2"
  ✅ "Contact the registrar office for more details"
  ✅ "Visit the student portal for current deadlines"
  ❌ "Submit the form via the portal" (workflow — blocked by UC-12)
  ❌ "Click here to apply" (action — not safe)
 
- Next steps must be RELEVANT to the query
  Not generic — derived from the actual answer content
 
- Next steps must RESPECT RBAC
  Only suggest resources the user's role can access
  Student next steps ≠ Faculty next steps for same query
 
- Next steps format in API response:
  Add next_steps field to chat response:
  {
    "answer": "...",
    "sources": [...],
    "next_steps": [
      "Review the attendance policy document for details",
      "Contact your academic advisor for exceptions"
    ]
  }
 
- If no relevant next steps — return empty list []
  Do not force generic next steps
 
- Add config flag to enable/disable:
  NEXT_STEPS_ENABLED=true (default true)
  In config.py: next_steps_enabled: bool = True
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 5 — UPDATE RESPONSE MODEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Update backend/app/models.py:
Add next_steps field to chat response model:
 
class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    next_steps: List[str] = []  # new field
 
Ensure backward compatibility — default to empty list
so existing clients are not broken.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 6 — ADD TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Add to backend/tests/test_agent_logic.py:
 
# AC: UIB-48-AC1
def test_next_steps_returned_in_response():
    """Chat response must include next_steps field"""
    # next_steps must be present in response
    # can be empty list but field must exist
 
# AC: UIB-48-AC2
def test_next_steps_are_safe_no_workflow_actions():
    """Next steps must not contain workflow action words"""
    unsafe_words = [
        "submit", "approve", "apply now",
        "click here", "sign the form", "process my"
    ]
    # For any response, next_steps must not contain
    # any of the workflow action words from UC-12
 
# AC: UIB-48-AC3
def test_next_steps_empty_when_no_relevant_sources():
    """Next steps should be empty when no sources found"""
    # Query about unknown topic → sources=[] → next_steps=[]
 
# AC: UIB-48-AC4
def test_next_steps_respect_rbac():
    """Next steps must not suggest resources
    inaccessible to user role"""
    # Student next steps must not reference
    # admin-only or faculty-only documents
 
# AC: UIB-48-AC5
def test_next_steps_disabled_when_config_false(mocker):
    """When NEXT_STEPS_ENABLED=false next_steps always empty"""
    mocker.patch('app.config.settings.next_steps_enabled', False)
    # next_steps must be [] regardless of query
 
# AC: UIB-48-AC6
def test_next_steps_are_list_of_strings():
    """next_steps must always be a list of strings"""
    # Never None, never dict, always List[str]
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 7 — REGRESSION GATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
python3 -m pytest backend/tests/ --tb=short -q
 
Target: 0 failures.
If failures — fix before proceeding.
Print final pass/fail count.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 8 — UPDATE SPEC AND DOCS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Update agent-specs/05_AGENT.md:
Add section for UIB-48 next steps:
- How next_steps are generated
- Safety rules
- RBAC awareness
- Config flag NEXT_STEPS_ENABLED
- Response format
 
Update docs/JIRA_TRACKER.md:
- UIB-48 status: ✅ Done
- Tests Tagged: 6
 
Update docs/TEST_RECORD.md:
- Add UIB-48 tests to list
- Update total count
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 9 — COMMIT AND PUSH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
git add backend/app/
git add backend/tests/
git add agent-specs/05_AGENT.md
git add docs/JIRA_TRACKER.md
git add docs/TEST_RECORD.md
 
git commit -m "feat: UIB-48 — suggest safe next steps in chat response
 
Added next_steps field to ChatResponse model.
Next steps are generated post-processing from answer content.
Safety rules: no workflow actions, RBAC-aware suggestions.
Config flag: NEXT_STEPS_ENABLED (default true).
 
Tests added (6):
- UIB-48-AC1: next_steps field present in response
- UIB-48-AC2: no unsafe workflow action words
- UIB-48-AC3: empty when no sources found
- UIB-48-AC4: respects RBAC role boundaries
- UIB-48-AC5: disabled when config flag false
- UIB-48-AC6: always returns List[str] never None"
 
git push origin main
Print commit hash.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSTRAINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Print ALL Jira ACs before writing any code
- Print design decision before implementing
- If AC conflicts with existing UC-12 — flag conflict,
  do not silently override
- next_steps must never trigger workflow prevention
- Do not break existing chat response format
- Backward compatible — next_steps defaults to []
- Run regression before commit
- Print commit hash when done
