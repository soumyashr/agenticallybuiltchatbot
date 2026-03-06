# 06 — RBAC.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Add route-level guards. Verify both enforcement layers work correctly.
# Prerequisites: 05_AGENT.md must be COMPLETE and VERIFIED.

---

## Two RBAC Layers — Both Required

```
Layer 1 — API Route Guard (FastAPI Depends):
  /admin/* routes → only role=="admin" allowed → else 403

Layer 2 — Chunk Retrieval Guard (already in tools.py):
  FAISS returns top-5 → filter by user_role in chunk.metadata.allowed_roles
  LLM only sees chunks the user is authorised for
```

Layer 2 is already implemented in `tools.py`. This spec adds Layer 1.

---

## STEP 1 — Add require_admin dependency

Add this to `backend/app/routers/documents_router.py`
(this file currently just has `router = APIRouter()`):

```python
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt

from app.auth import decode_token

log = logging.getLogger(__name__)
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency — raises 403 if the user is not an admin."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Your role does not permit this action.",
        )
    return user


# Full admin endpoints added in 07_ADMIN_API.md
# Add a probe route to verify RBAC works now:

@router.get("/documents/ping")
def admin_ping(admin: dict = Depends(require_admin)):
    return {"message": f"Admin access confirmed for {admin['username']}"}
```

---

## STEP 2 — Verify JWT tamper protection

The `decode_token` function in `auth.py` uses `jwt.decode()` with the secret.
Any tampered token (e.g. modified role claim) will fail signature verification
and return 401. No additional code needed — this is already implemented.

**Verify manually:**
1. Get a valid student token from POST /auth/token
2. Decode the JWT payload (base64 middle segment)
3. Change "role":"student" to "role":"admin"
4. Re-encode without re-signing
5. Use tampered token on GET /admin/documents/ping → must return 401

---

## STEP 3 — Session role isolation

The `get_or_create_session` function in `agent.py` already raises `PermissionError`
if a `session_id` is reused with a different role. No additional code needed.

**The full RBAC matrix:**

| User | Document | Expected |
|------|----------|----------|
| student1 | student_syllabus.pdf | ✅ Answer |
| student1 | feature_6_document.pdf | ❌ "not available" |
| student1 | feature_7_document.pdf | ❌ "not available" |
| faculty1 | student_syllabus.pdf | ✅ Answer |
| faculty1 | feature_6_document.pdf | ✅ Answer |
| faculty1 | feature_7_document.pdf | ❌ "not available" |
| admin | student_syllabus.pdf | ✅ Answer |
| admin | feature_6_document.pdf | ✅ Answer |
| admin | feature_7_document.pdf | ✅ Answer |

---

## STEP 4 — Full RBAC Matrix Test Script

Write to `backend/test_rbac_matrix.py`:
```python
"""Full 3x3 RBAC matrix test — 3 roles x 3 documents = 9 tests."""
import requests, time

BASE = "http://localhost:8000"

def get_token(username, password):
    r = requests.post(f"{BASE}/auth/token", data={"username": username, "password": password})
    return r.json()["access_token"]

tokens = {
    "student": get_token("student1", "HMStudent@2024"),
    "faculty": get_token("faculty1", "HMFaculty@2024"),
    "admin":   get_token("admin",    "HMAdmin@2024"),
}

tests = [
    # (role, question, expect_doc_substring, should_block, label)
    ("student", "What are the academic standing and GPA requirements?",      "student_syllabus", False, "student → syllabus    (ALLOW)"),
    ("faculty", "What are the academic standing and GPA requirements?",      "student_syllabus", False, "faculty → syllabus    (ALLOW)"),
    ("admin",   "What are the academic standing and GPA requirements?",      "student_syllabus", False, "admin   → syllabus    (ALLOW)"),
    ("student", "What is the pre-assessment moderation protocol for exams?", "Feature_6",        True,  "student → Feature_6   (BLOCK)"),
    ("faculty", "What is the pre-assessment moderation protocol for exams?", "Feature_6",        False, "faculty → Feature_6   (ALLOW)"),
    ("admin",   "What is the pre-assessment moderation protocol for exams?", "Feature_6",        False, "admin   → Feature_6   (ALLOW)"),
    ("student", "What was discussed in the Faculty Senate meeting?",         "Feature_7",        True,  "student → Feature_7   (BLOCK)"),
    ("faculty", "What was discussed in the Faculty Senate meeting?",         "Feature_7",        True,  "faculty → Feature_7   (BLOCK)"),
    ("admin",   "What was discussed in the Faculty Senate meeting?",         "Feature_7",        False, "admin   → Feature_7   (ALLOW)"),
]

print("=" * 62)
print("  FULL RBAC MATRIX — 3 roles x 3 documents = 9 tests")
print("=" * 62)

passed = 0
failed = 0
for role, question, expect_doc, should_block, label in tests:
    sid = f"matrix-{role}-{int(time.time() * 1000)}"
    r = requests.post(
        f"{BASE}/chat",
        headers={"Authorization": f"Bearer {tokens[role]}"},
        json={"message": question, "session_id": sid},
    )
    data = r.json()
    ans = data.get("answer", "")
    srcs = [s["source"] for s in data.get("sources", [])]
    blocked = "could not find" in ans.lower() or "not find" in ans.lower()

    if should_block:
        ok = blocked and not any(expect_doc in s for s in srcs)
    else:
        ok = not blocked and any(expect_doc in s for s in srcs)

    status = "PASS" if ok else "FAIL"
    passed += ok
    failed += not ok
    print(f"  {status}  {label}")
    if not ok:
        print(f"         blocked={blocked} srcs={[s[:45] for s in srcs[:2]]}")
        print(f"         answer={ans[:150]}")

print("=" * 62)
print(f"  Results: {passed} passed, {failed} failed out of 9")
print("=" * 62)
```

Run:
```bash
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot/backend
source .venv/bin/activate
python3 test_rbac_matrix.py
```

All 9 must pass.

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL. Fix all FAILs before moving to 07.

- [ ] `GET /admin/documents/ping` with admin token → 200 `{"message":"Admin access confirmed for admin"}`
- [ ] `GET /admin/documents/ping` with faculty token → 403
- [ ] `GET /admin/documents/ping` with student token → 403
- [ ] `GET /admin/documents/ping` with no token → 401
- [ ] `GET /admin/documents/ping` with expired token → 401
- [ ] Full RBAC matrix test: `python3 test_rbac_matrix.py` → 9/9 PASS
- [ ] student1 → student_syllabus: ALLOW (real answer with source citation)
- [ ] student1 → Feature_6: BLOCK ("could not find", no Feature_6 sources)
- [ ] student1 → Feature_7: BLOCK ("could not find", no Feature_7 sources)
- [ ] faculty1 → student_syllabus: ALLOW
- [ ] faculty1 → Feature_6: ALLOW
- [ ] faculty1 → Feature_7: BLOCK
- [ ] admin → student_syllabus: ALLOW
- [ ] admin → Feature_6: ALLOW
- [ ] admin → Feature_7: ALLOW
- [ ] Tampered JWT test: modified role claim → 401 Unauthorized
