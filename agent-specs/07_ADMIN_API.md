# 07 — ADMIN_API.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Replace the documents_router.py stub with all 5 admin endpoints.
# Prerequisites: 06_RBAC.md must be COMPLETE and VERIFIED.

---

## 6 Endpoints to Build

| Method | Path | Action |
|--------|------|--------|
| POST | /admin/documents/upload | Upload PDF + register with roles |
| GET | /admin/documents | List all documents by status |
| POST | /admin/documents/ingest | Ingest all UPLOADED documents |
| DELETE | /admin/documents/{id} | Delete document + rebuild index |
| GET | /admin/documents/{id}/status | Poll single document status |
| GET | /documents/my | Return documents accessible to current user's role (any authenticated user) |

---

## STEP 1 — Replace documents_router.py

Overwrite `backend/app/routers/documents_router.py` completely:

```python
import json
import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt

from app.auth import decode_token
from app.document_store import (
    delete_document,
    get_all_documents,
    get_pending_documents,
    get_ingested_documents,
    register_document,
)
from app.ingest import run_pending, run_after_delete
from app.config import settings

log = logging.getLogger(__name__)
router = APIRouter()
public_router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

ALLOWED_ROLES = {"admin", "faculty", "student"}


# ── Auth dependencies ─────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )
    return user


# ── 1. Upload ─────────────────────────────────────────────────

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    display_name: str = Form(...),
    allowed_roles: str = Form(...),
    admin: dict = Depends(require_admin),
):
    """
    Upload a PDF and register it in DynamoDB (status=UPLOADED).
    allowed_roles: JSON string e.g. '["admin","faculty"]'
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Parse and validate roles
    try:
        roles = json.loads(allowed_roles)
        if not isinstance(roles, list) or not roles:
            raise ValueError("roles must be a non-empty list")
        invalid = [r for r in roles if r not in ALLOWED_ROLES]
        if invalid:
            raise ValueError(f"Invalid roles: {invalid}")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"allowed_roles must be a valid JSON array. {exc}",
        )

    # Check for duplicate filename
    existing = [d for d in get_all_documents() if d["filename"] == file.filename]
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A file named '{file.filename}' already exists. "
                "Delete it first or rename your file."
            ),
        )

    # Save file to disk
    os.makedirs(settings.data_dir, exist_ok=True)
    filepath = os.path.join(settings.data_dir, file.filename)
    content  = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Register in DB
    doc_id = register_document(
        filename=file.filename,
        display_name=display_name,
        allowed_roles=roles,
        file_size=len(content),
    )
    log.info(f"Uploaded: {file.filename} ({len(content)} bytes) → id={doc_id}")

    return {
        "id":            doc_id,
        "filename":      file.filename,
        "display_name":  display_name,
        "allowed_roles": roles,
        "status":        "UPLOADED",
        "file_size":     len(content),
    }


# ── 2. List all ───────────────────────────────────────────────

@router.get("/documents")
def list_documents(admin: dict = Depends(require_admin)):
    """Return all documents grouped by status."""
    docs = get_all_documents()
    return {
        "pending":   [d for d in docs if d["status"] == "UPLOADED"],
        "ingesting": [d for d in docs if d["status"] == "INGESTING"],
        "ingested":  [d for d in docs if d["status"] == "INGESTED"],
        "failed":    [d for d in docs if d["status"] == "FAILED"],
        "total":     len(docs),
    }


# ── 3. Ingest pending ─────────────────────────────────────────

@router.post("/documents/ingest")
def ingest_documents(admin: dict = Depends(require_admin)):
    """
    Ingest all UPLOADED documents.
    Rebuilds the full vector index (FAISS or Azure AI Search, per AI_PROVIDER).
    """
    pending = get_pending_documents()
    if not pending:
        return {"message": "No pending documents to ingest.", "ingested": 0}

    run_pending()

    ingested = get_ingested_documents()
    log.info(f"Ingested {len(pending)} documents. Total ingested: {len(ingested)}")
    return {
        "message":        f"Successfully ingested {len(pending)} document(s).",
        "ingested":       len(pending),
        "total_ingested": len(ingested),
    }


# ── 4. Delete ─────────────────────────────────────────────────

@router.delete("/documents/{doc_id}")
def delete_doc(doc_id: str, admin: dict = Depends(require_admin)):
    """
    Delete a document record from DB + its PDF file from disk.
    If the document was INGESTED, rebuilds vector index (FAISS or Azure AI Search) without it.
    """
    docs = get_all_documents()
    doc  = next((d for d in docs if d["id"] == doc_id), None)

    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")

    was_ingested = doc["status"] == "INGESTED"

    # Remove physical file
    filepath = os.path.join(settings.data_dir, doc["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)
        log.info(f"Deleted file: {filepath}")

    # Remove DB record
    delete_document(doc_id)
    log.info(f"Deleted document record: id={doc_id}")

    # Rebuild vector index if the doc was part of the index
    if was_ingested:
        run_after_delete()
        log.info("Vector index rebuilt after deletion.")

    return {"deleted": doc_id, "filename": doc["filename"]}


# ── 5. My documents (any role) ────────────────────────────────

@public_router.get("/documents/my")
def my_documents(user: dict = Depends(get_current_user)):
    """Return documents accessible to the current user's role."""
    role = user.get("role", "student")
    docs = get_all_documents()
    return [
        {
            "id": d["id"],
            "display_name": d["display_name"],
            "allowed_roles": d["allowed_roles"],
            "chunk_count": d["chunk_count"],
        }
        for d in docs
        if d["status"] == "INGESTED" and role in d.get("allowed_roles", [])
    ]


# ── 6. Status poll ────────────────────────────────────────────

@router.get("/documents/{doc_id}/status")
def get_document_status(doc_id: str, admin: dict = Depends(require_admin)):
    """Poll a single document's ingest status. Used by frontend during ingest."""
    docs = get_all_documents()
    doc  = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return {
        "id":          doc["id"],
        "status":      doc["status"],
        "chunk_count": doc["chunk_count"],
        "error_msg":   doc["error_msg"],
    }
```

**Note:** `public_router` is mounted in `main.py` without a prefix (not under `/admin`),
so the endpoint is accessible at `GET /documents/my` to any authenticated user.
The `router` is mounted with prefix `/admin`, so admin endpoints remain at `/admin/documents/*`.

Registration in `main.py`:
```python
app.include_router(documents_router.router,        prefix="/admin", tags=["Admin"])
app.include_router(documents_router.public_router,                  tags=["Documents"])
```

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL. Fix all FAILs before moving to 08.

- [ ] `POST /admin/documents/upload` with admin token + PDF file → 200 with doc id
- [ ] `POST /admin/documents/upload` with faculty token → 403
- [ ] `POST /admin/documents/upload` with non-PDF file → 400
- [ ] `POST /admin/documents/upload` with empty allowed_roles → 400
- [ ] `POST /admin/documents/upload` duplicate filename → 409 with clear message
- [ ] `GET /admin/documents` with admin token → returns `{ pending, ingesting, ingested, failed, total }`
- [ ] `POST /admin/documents/ingest` → all UPLOADED docs move to INGESTED
- [ ] `GET /admin/documents/{id}/status` returns correct status after ingest
- [ ] `DELETE /admin/documents/{id}` removes file from `backend/data/`
- [ ] `DELETE /admin/documents/{id}` removes record from DynamoDB
- [ ] After delete of INGESTED doc, vector index is rebuilt (run a chat query to verify)
- [ ] `DELETE /admin/documents/{id}` with faculty token → 403
- [ ] `GET /documents/my` with any authenticated token → returns list of documents for that role
- [ ] `GET /documents/my` with student token → returns only student-accessible documents
- [ ] `GET /documents/my` with admin token → returns all documents
- [ ] `GET /documents/my` with no token → 401
- [ ] All 6 endpoints appear in Swagger UI at `http://localhost:8000/docs`
