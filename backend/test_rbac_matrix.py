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
