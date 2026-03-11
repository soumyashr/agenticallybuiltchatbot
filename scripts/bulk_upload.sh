#!/bin/bash
# ────────────────────────────────────────────────────────────
# Bulk upload + ingest all PDFs from a local directory
# via the admin API.
#
# Usage:
#   ./scripts/bulk_upload.sh /path/to/pdf/folder
#   ./scripts/bulk_upload.sh                      # uses current dir
# ────────────────────────────────────────────────────────────
set -euo pipefail

BACKEND_URL="https://c2cnjknssm.ap-south-1.awsapprunner.com"
PDF_DIR="${1:-.}"

if [ ! -d "$PDF_DIR" ]; then
  echo "❌ Directory not found: $PDF_DIR"
  exit 1
fi

# ── Get admin token ──────────────────────────────────────────
echo "Getting admin token..."
TOKEN_RESP=$(curl -s -X POST "$BACKEND_URL/auth/token" \
  -d "username=admin&password=HMAdmin@2024" \
  -H "Content-Type: application/x-www-form-urlencoded")

ADMIN=$(echo "$TOKEN_RESP" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin)['access_token'])
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$ADMIN" ]; then
  echo "❌ Failed to get admin token"
  echo "   Response: $TOKEN_RESP"
  exit 1
fi
echo "✅ Token obtained"
echo ""

PASS=0
FAIL=0
SKIP=0

# ── Role assignment based on filename patterns ───────────────
get_roles_json() {
  local filename=$1
  case $filename in
    Student_*)                echo '["student","faculty","admin"]' ;;
    Faculty_*)                echo '["faculty","admin"]' ;;
    Admin_*)                  echo '["admin"]' ;;
    Feature_7_*|Feature_8_*)  echo '["admin"]' ;;
    Restricted_*)             echo '["admin"]' ;;
    Feature_*)                echo '["student","faculty","admin"]' ;;
    campus_navigation_*)      echo '["student","faculty","admin"]' ;;
    Course_Outline_*)         echo '["student","faculty"]' ;;
    Exam_Rules_*)             echo '["student","faculty","admin"]' ;;
    *)                        echo '["student","faculty","admin"]' ;;
  esac
}

# ── Display name from filename (strip .pdf, replace _ with space) ──
get_display_name() {
  echo "$1" | sed 's/\.pdf$//i' | sed 's/_/ /g'
}

# ── Upload each PDF ──────────────────────────────────────────
for filepath in "$PDF_DIR"/*.pdf; do
  [ -f "$filepath" ] || continue
  filename=$(basename "$filepath")
  roles_json=$(get_roles_json "$filename")
  display_name=$(get_display_name "$filename")

  echo "Uploading: $filename"
  echo "  roles: $roles_json"

  RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BACKEND_URL/admin/documents/upload" \
    -H "Authorization: Bearer $ADMIN" \
    -F "file=@$filepath" \
    -F "display_name=$display_name" \
    -F "allowed_roles=$roles_json")

  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | sed '$d')

  if [ "$HTTP_CODE" = "200" ]; then
    DOC_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    echo "  ✅ UPLOADED — id=$DOC_ID"
    PASS=$((PASS+1))
  elif [ "$HTTP_CODE" = "409" ]; then
    echo "  ⏭️  SKIP — already exists"
    SKIP=$((SKIP+1))
  else
    DETAIL=$(echo "$BODY" | python3 -c "
import sys,json
try:
    print(json.load(sys.stdin).get('detail','unknown'))
except:
    print('parse error')
" 2>/dev/null)
    echo "  ❌ FAIL ($HTTP_CODE) — $DETAIL"
    FAIL=$((FAIL+1))
  fi
  echo ""
done

# ── Trigger ingest ───────────────────────────────────────────
if [ "$PASS" -gt 0 ]; then
  echo "Triggering ingest for $PASS uploaded document(s)..."
  INGEST_RESP=$(curl -s -X POST "$BACKEND_URL/admin/documents/ingest" \
    -H "Authorization: Bearer $ADMIN")
  INGEST_MSG=$(echo "$INGEST_RESP" | python3 -c "
import sys,json
try:
    r=json.load(sys.stdin)
    print(f\"Ingested: {r.get('ingested',0)}, Total: {r.get('total_ingested',0)}\")
except:
    print('parse error')
" 2>/dev/null)
  echo "✅ $INGEST_MSG"
else
  echo "No new uploads — skipping ingest."
fi

# ── Summary ──────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Upload Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Total PDFs: $((PASS+FAIL+SKIP))"
echo "  ✅ Uploaded: $PASS"
echo "  ⏭️  Skipped: $SKIP"
echo "  ❌ Failed:   $FAIL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
