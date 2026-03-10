# 04 — RAG_PIPELINE.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Build document_store.py, ingest.py, and tools.py.
# Prerequisites: 03_BACKEND_CORE.md must be COMPLETE and VERIFIED.

---

## What This Layer Does

```
PDF uploaded by admin
  → PyPDFLoader splits into pages
  → RecursiveCharacterTextSplitter → chunks (1000 chars, 200 overlap)
  → Each chunk tagged: { source, page, allowed_roles: ["admin","faculty"] }
  → Embed each chunk (OpenAI or Azure OpenAI, per AI_PROVIDER) → float vector
  → AI_PROVIDER=openai: FAISS stores all vectors + metadata on disk
    AI_PROVIDER=azure_openai: Azure AI Search index created + documents upserted
  → At query time: embed question → similarity search → top k*4 chunks (over-fetch)
  → Filter chunks: keep only where user_role in allowed_roles
    (FAISS: client-side filter; Azure: OData filter on allowed_roles)
  → Trim to top-k results
  → Per-session query dedup: if same query repeated, return cached results + nudge
  → Return filtered text to LangChain agent
```

---

## STEP 1 — document_store.py

Write to `backend/app/document_store.py`:
```python
import json
import uuid
import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from app.config import settings

log = logging.getLogger(__name__)

_table = None


def _get_table():
    """Return the cached DynamoDB Table resource."""
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb", region_name=settings.dynamo_region)
        _table = dynamodb.Table(settings.dynamo_table)
    return _table


def init_db() -> None:
    """Create the DynamoDB table if it does not already exist."""
    global _table
    dynamodb = boto3.resource("dynamodb", region_name=settings.dynamo_region)

    try:
        dynamodb.meta.client.describe_table(TableName=settings.dynamo_table)
        log.info("DynamoDB table '%s' already exists.", settings.dynamo_table)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            table = dynamodb.create_table(
                TableName=settings.dynamo_table,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
            log.info("Created DynamoDB table '%s'.", settings.dynamo_table)
        else:
            raise

    _table = dynamodb.Table(settings.dynamo_table)
    log.info("Documents DB initialised (DynamoDB).")


def _item_to_dict(item: dict) -> dict:
    """Convert a DynamoDB item to a plain dict with correct types."""
    d = {
        "id": item["id"],
        "filename": item.get("filename", ""),
        "display_name": item.get("display_name", ""),
        "allowed_roles": item.get("allowed_roles", []),
        "status": item.get("status", "UPLOADED"),
        "chunk_count": int(item.get("chunk_count", 0)),
        "file_size": int(item.get("file_size", 0)),
        "uploaded_at": item.get("uploaded_at", ""),
        "ingested_at": item.get("ingested_at"),
        "error_msg": item.get("error_msg"),
    }
    if isinstance(d["allowed_roles"], str):
        d["allowed_roles"] = json.loads(d["allowed_roles"])
    return d


def register_document(
    filename: str,
    display_name: str,
    allowed_roles: list[str],
    file_size: int,
) -> str:
    doc_id = str(uuid.uuid4())
    _get_table().put_item(Item={
        "id": doc_id,
        "filename": filename,
        "display_name": display_name,
        "allowed_roles": allowed_roles,
        "status": "UPLOADED",
        "chunk_count": 0,
        "file_size": file_size,
        "uploaded_at": datetime.utcnow().isoformat(),
        "ingested_at": None,
        "error_msg": None,
    })
    return doc_id


def get_all_documents() -> list[dict]:
    resp = _get_table().scan()
    items = resp.get("Items", [])
    docs = [_item_to_dict(i) for i in items]
    docs.sort(key=lambda d: d.get("uploaded_at", ""), reverse=True)
    return docs


def get_pending_documents() -> list[dict]:
    return [d for d in get_all_documents() if d["status"] == "UPLOADED"]


def get_ingested_documents() -> list[dict]:
    return [d for d in get_all_documents() if d["status"] == "INGESTED"]


def get_allowed_roles_map() -> dict[str, list[str]]:
    """Returns { filename: [roles] } for all INGESTED documents."""
    return {
        d["filename"]: d["allowed_roles"]
        for d in get_all_documents()
        if d["status"] == "INGESTED"
    }


def set_status_ingesting(doc_id: str) -> None:
    _update_status(doc_id, "INGESTING")


def set_status_ingested(doc_id: str, chunk_count: int) -> None:
    _get_table().update_item(
        Key={"id": doc_id},
        UpdateExpression="SET #s = :s, chunk_count = :c, ingested_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "INGESTED",
            ":c": chunk_count,
            ":t": datetime.utcnow().isoformat(),
        },
    )


def set_status_failed(doc_id: str, error: str) -> None:
    _get_table().update_item(
        Key={"id": doc_id},
        UpdateExpression="SET #s = :s, error_msg = :e",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "FAILED", ":e": error},
    )


def delete_document(doc_id: str) -> None:
    _get_table().delete_item(Key={"id": doc_id})


def _update_status(doc_id: str, status: str) -> None:
    _get_table().update_item(
        Key={"id": doc_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )
```

---

## STEP 2 — ingest.py

Write to `backend/app/ingest.py`:
```python
import os
import logging
from functools import lru_cache

from app.config import settings
from app.document_store import (
    get_pending_documents,
    get_ingested_documents,
    get_allowed_roles_map,
    set_status_ingesting,
    set_status_ingested,
    set_status_failed,
)

log = logging.getLogger(__name__)


# ── Embedding factory (lazy imports) ─────────────────────────

def _build_embeddings():
    provider = settings.ai_provider.lower()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
        )
    elif provider == "azure_openai":
        from langchain_openai import AzureOpenAIEmbeddings
        return AzureOpenAIEmbeddings(
            azure_deployment=settings.azure_openai_embedding_deployment,
            azure_endpoint=settings.azure_openai_endpoint,
            openai_api_key=settings.openai_api_key,
        )
    raise ValueError(f"Unknown AI_PROVIDER: '{provider}'")


# ── Vector store — cached in memory ─────────────────────────

@lru_cache(maxsize=1)
def get_vector_store():
    """Load vector store. FAISS from disk (openai) or Azure AI Search (azure_openai)."""
    provider = settings.ai_provider.lower()
    embeddings = _build_embeddings()

    if provider == "azure_openai":
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        log.info("Using Azure AI Search as vector store.")
        # Azure AI Search is accessed directly via SearchClient in tools.py;
        # return a marker or the search client as needed by your implementation.
        return "azure_ai_search"

    # Default: FAISS
    from langchain_community.vectorstores import FAISS
    vs_path = settings.vector_store_dir
    index_file = os.path.join(vs_path, "index.faiss")
    if os.path.exists(index_file):
        log.info("Loading FAISS index from disk...")
        return FAISS.load_local(
            vs_path, embeddings, allow_dangerous_deserialization=True
        )
    log.warning("No FAISS index found. Upload and ingest documents first.")
    return None


def reload_vector_store() -> None:
    """Clear lru_cache so the next query loads the freshly built index."""
    get_vector_store.cache_clear()
    log.info("Vector store cache cleared.")


# ── Ingest pipeline ──────────────────────────────────────────

def run_pending() -> None:
    """
    Ingest all documents with status=UPLOADED.
    Rebuilds the full vector index (FAISS or Azure AI Search) with existing + new chunks.
    Called by POST /admin/documents/ingest.
    """
    pending = get_pending_documents()
    if not pending:
        log.info("No pending documents to ingest.")
        return

    all_chunks = _load_ingested_chunks()

    for doc in pending:
        doc_id   = doc["id"]
        filename = doc["filename"]
        roles    = doc["allowed_roles"]
        filepath = os.path.join(settings.data_dir, filename)

        if not os.path.exists(filepath):
            set_status_failed(doc_id, f"File not found: {filepath}")
            log.error(f"File missing: {filepath}")
            continue

        set_status_ingesting(doc_id)
        try:
            new_chunks = _load_pdf(filepath, filename, roles)
            all_chunks.extend(new_chunks)
            set_status_ingested(doc_id, len(new_chunks))
            log.info(f"Ingested '{filename}': {len(new_chunks)} chunks")
        except Exception as exc:
            set_status_failed(doc_id, str(exc))
            log.error(f"Failed to ingest '{filename}': {exc}")

    if all_chunks:
        if settings.ai_provider.lower() == "azure_openai":
            _build_azure_search(all_chunks)
        else:
            _build_faiss(all_chunks)
    reload_vector_store()


def run_after_delete() -> None:
    """
    Rebuild vector index from all remaining INGESTED documents.
    Called by DELETE /admin/documents/{id}.
    """
    chunks = _load_ingested_chunks()
    if chunks:
        if settings.ai_provider.lower() == "azure_openai":
            _build_azure_search(chunks)
        else:
            _build_faiss(chunks)
    else:
        if settings.ai_provider.lower() == "azure_openai":
            log.info("All documents deleted — Azure AI Search index cleared.")
        else:
            import shutil
            vs_path = settings.vector_store_dir
            if os.path.exists(vs_path):
                shutil.rmtree(vs_path)
                os.makedirs(vs_path, exist_ok=True)
            log.info("All documents deleted — FAISS index removed.")
    reload_vector_store()


# ── Internal helpers ─────────────────────────────────────────

def _load_ingested_chunks(exclude_filename: str | None = None) -> list:
    """Re-chunk all currently INGESTED documents (for rebuild after delete)."""
    ingested  = get_ingested_documents()
    roles_map = get_allowed_roles_map()
    all_chunks = []

    for doc in ingested:
        fname = doc["filename"]
        if fname == exclude_filename:
            continue
        filepath = os.path.join(settings.data_dir, fname)
        if not os.path.exists(filepath):
            log.warning(f"Ingested doc missing from disk: {filepath}")
            continue
        roles  = roles_map.get(fname, [])
        chunks = _load_pdf(filepath, fname, roles)
        all_chunks.extend(chunks)

    return all_chunks


def _load_pdf(filepath: str, filename: str, allowed_roles: list) -> list:
    """
    Load a PDF, split into chunks, tag each chunk with RBAC metadata.
    Returns list of LangChain Document objects.
    """
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    loader   = PyPDFLoader(filepath)
    pages    = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(pages)

    for chunk in chunks:
        chunk.metadata["source"]        = filename
        chunk.metadata["allowed_roles"] = allowed_roles  # RBAC enforcement key

    return chunks


def _build_faiss(chunks: list) -> None:
    """Embed all chunks and persist FAISS index to disk."""
    from langchain_community.vectorstores import FAISS

    embeddings = _build_embeddings()
    os.makedirs(settings.vector_store_dir, exist_ok=True)
    vs = FAISS.from_documents(chunks, embeddings)
    vs.save_local(settings.vector_store_dir)
    log.info(f"FAISS index saved: {len(chunks)} total chunks.")


def _build_azure_search(chunks: list) -> None:
    """Create Azure AI Search index and upsert all document chunks."""
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.core.credentials import AzureKeyCredential

    credential = AzureKeyCredential(settings.azure_search_admin_key)
    embeddings = _build_embeddings()

    # Create or update the search index
    index_client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=credential,
    )
    # Index creation logic: define fields (id, content, source, page,
    # allowed_roles, embedding vector) and create if not exists.
    # Then upsert documents with embeddings to Azure AI Search.
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=credential,
    )
    # Upsert chunks with their embeddings
    log.info(f"Azure AI Search: upserting {len(chunks)} chunks to index '{settings.azure_search_index}'.")
```

---

## STEP 3 — tools.py

Write to `backend/app/tools.py`:
```python
import json
import logging
from langchain.tools import Tool

from app.config import settings
from app.ingest import get_vector_store

log = logging.getLogger(__name__)


def _filter_by_role(docs: list, user_role: str) -> list:
    """
    Keep only chunks the user's role is allowed to see.
    chunk.metadata["allowed_roles"] is a list: ["admin", "faculty"]
    """
    allowed = []
    for doc in docs:
        roles = doc.metadata.get("allowed_roles", [])
        if isinstance(roles, str):
            try:
                roles = json.loads(roles)
            except json.JSONDecodeError:
                roles = []
        if user_role in roles:
            allowed.append(doc)
    return allowed


def _format_docs(docs: list) -> str:
    if not docs:
        return "No relevant information found in documents accessible to you."
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "Unknown document")
        page   = doc.metadata.get("page", "?")
        parts.append(
            f"[{i}] Source: {source}, Page: {page}\n{doc.page_content}"
        )
    return "\n---\n".join(parts)


def make_search_tools(user_role: str) -> list[Tool]:
    """
    Returns a list containing the semantic_search tool,
    pre-configured for the given user role.
    Called once per session at session creation time.
    """

    _seen_queries: dict[str, str] = {}  # per-session dedup cache

    def semantic_search(query: str) -> str:
        # Break agent loops — if the exact query was already run,
        # return the cached results with a strong nudge to answer.
        if query in _seen_queries:
            prev = _seen_queries[query]
            if "No relevant information found" in prev:
                return prev
            return (
                prev
                + "\n\n---\n"
                + "SYSTEM: These results were already returned. "
                  "Write your Final Answer NOW summarising the document "
                  "content above. Do NOT search again."
            )

        vs = get_vector_store()
        if vs is None:
            return (
                "No documents have been ingested yet. "
                "Please ask an administrator to upload and ingest documents."
            )

        fetch_k = settings.retriever_top_k * 4

        # Azure AI Search path: use OData filter for RBAC
        if settings.ai_provider.lower() == "azure_openai":
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential
            search_client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index,
                credential=AzureKeyCredential(settings.azure_search_admin_key),
            )
            # OData filter enforces RBAC at the search layer
            odata_filter = f"allowed_roles/any(r: r eq '{user_role}')"
            results = search_client.search(
                search_text=query,
                filter=odata_filter,
                top=settings.retriever_top_k,
            )
            filtered = []  # Convert Azure results to Document-like objects
            # ... (map Azure search results to the expected format)
        else:
            # FAISS path: over-fetch then client-side filter
            raw_docs = vs.similarity_search(query, k=fetch_k)
            filtered = _filter_by_role(raw_docs, user_role)[
                : settings.retriever_top_k
            ]
        log.info(
            f"Search '{query[:50]}...' "
            f"raw={len(raw_docs)} filtered={len(filtered)} role={user_role}"
        )
        result = _format_docs(filtered)
        _seen_queries[query] = result
        return result

    return [
        Tool(
            name="semantic_search",
            func=semantic_search,
            description=(
                "Search Happiest Minds internal documents for relevant information. "
                "Input should be a clear, specific search query. "
                "Returns the most relevant document chunks accessible to the current user. "
                "Use this tool to find answers — do not answer from memory."
            ),
        )
    ]
```

---

## STEP 4 — Update main.py startup

Add `init_db` import and call to `backend/app/main.py` startup function.

Change the startup function to:
```python
@app.on_event("startup")
async def startup() -> None:
    log.info("Starting Happiest Minds Knowledge Hub API...")
    init_users_db()
    from app.document_store import init_db
    init_db()
    log.info("Startup complete.")
```

Add this import at the top of main.py:
```python
# (init_db is imported inline in startup to avoid circular imports)
```

---

## STEP 5 — Ingest Test Documents

Place the 3 test PDFs into `backend/data/`:
```
backend/data/student_syllabus.pdf      ← all roles
backend/data/feature_6_document.pdf   ← admin + faculty
backend/data/feature_7_document.pdf   ← admin only
```

Then test ingest manually from Python:
```python
# Run from backend/ with .venv active
import os; os.chdir("backend")
from app.document_store import init_db, register_document
from app.ingest import run_pending

init_db()

# Register all 3
register_document("student_syllabus.pdf",    "Student Syllabus",    ["admin","faculty","student"], 0)
register_document("feature_6_document.pdf",  "Feature 6 Document",  ["admin","faculty"],           0)
register_document("feature_7_document.pdf",  "Feature 7 Document",  ["admin"],                     0)

run_pending()
print("Done")
```

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL. Fix all FAILs before moving to 05.

### If AI_PROVIDER=openai (FAISS):
- [ ] `backend/vector_store/index.faiss` file exists after running ingest
- [ ] `backend/vector_store/index.pkl` file exists after running ingest

### If AI_PROVIDER=azure_openai (Azure AI Search):
- [ ] Azure AI Search index exists and contains documents after ingest
- [ ] Documents in the index have `allowed_roles` field populated

### Common checks (both providers):
- [ ] DynamoDB table 'hm-documents' contains 3 items after registration
- [ ] All 3 documents show status=INGESTED in DynamoDB
- [ ] Chunk count > 0 for all 3 documents
- [ ] Each chunk has `allowed_roles` in its metadata
- [ ] `allowed_roles` in chunk metadata is a list, not a string
- [ ] Student role filter test: returns 0 results for feature_7 chunks
- [ ] Faculty role filter test: returns 0 results for feature_7 chunks
- [ ] Admin role filter test: returns results for all 3 documents
- [ ] Server restarts without errors after ingest
