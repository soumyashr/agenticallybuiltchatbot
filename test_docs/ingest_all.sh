#!/bin/bash
# Happiest Minds Knowledge Hub — Bulk Document Ingest Script
# Run from anywhere: bash ingest_all.sh

BASE_URL="https://c2cnjknssm.ap-south-1.awsapprunner.com"
PDF_DIR="/Users/soumya.shrivastava/Downloads/ChatBotTestDocs"

# ── Get admin token ──────────────────────────────────────────
TOKEN=$(curl -s -X POST $BASE_URL/auth/token \
  -F "username=admin" -F "password=HMAdmin@2024" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token obtained: ${TOKEN:0:20}..."
echo ""

# ── Upload function ──────────────────────────────────────────
upload() {
  FILE=$1
  ROLES=$2
  echo "Uploading: $FILE"
  echo "  Roles: $ROLES"
  curl -s -X POST $BASE_URL/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$PDF_DIR/$FILE" \
    -F "allowed_roles=$ROLES" \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print('  →', r.get('message', r.get('detail','?')))"
  echo ""
}

# ── Admin only ───────────────────────────────────────────────
upload "Admin_Operations_Manual.pdf"           '["admin"]'
upload "Admin_IT_Systems_Guide.pdf"            '["admin"]'
upload "Admin_Data_Security_Policy.pdf"        '["admin"]'
upload "Restricted_Department_Minutes.pdf"     '["admin"]'

# ── Admin + Faculty ──────────────────────────────────────────
upload "Faculty_Leave_Policy.pdf"              '["admin","faculty"]'
upload "Faculty_Assessment_Policy.pdf"         '["admin","faculty"]'

# ── Faculty only ─────────────────────────────────────────────
upload "Faculty_Research_Policy.pdf"           '["faculty"]'

# ── Admin + Faculty + Student ────────────────────────────────
upload "Faculty_Teaching_Guidelines.pdf"       '["admin","faculty","student"]'
upload "Student_Academic_Handbook.pdf"         '["admin","faculty","student"]'
upload "Student_Attendance_Policy.pdf"         '["admin","faculty","student"]'
upload "Exam_Rules_Integrity.pdf"              '["admin","faculty","student"]'
upload "Course_Outline_ComputerScience.pdf"    '["admin","faculty","student"]'

# ── Student only ─────────────────────────────────────────────
upload "Student_Campus_Services.pdf"           '["student"]'

# ── Student + Admin ──────────────────────────────────────────
upload "Student_Admissions_and_Fees.pdf"       '["admin","student"]'

# ── Trigger ingest ───────────────────────────────────────────
echo "All uploads done. Triggering ingest (chunking + vectorizing)..."
echo ""
curl -s -X POST $BASE_URL/documents/ingest \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('Ingest result:', r)"

# ── Verify ───────────────────────────────────────────────────
echo ""
echo "Verifying ingested documents:"
curl -s $BASE_URL/documents \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "
import sys,json
docs = json.load(sys.stdin)
ingested = docs.get('ingested', [])
print(f'  Total ingested: {len(ingested)}')
for d in ingested:
    print(f'  {d[\"name\"][:55]:55} {d[\"status\"]:12} {d[\"allowed_roles\"]}')
"
