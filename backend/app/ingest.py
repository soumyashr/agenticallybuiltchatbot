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
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
        )
    elif provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: '{provider}'")


# ── Vector store — cached in memory ─────────────────────────

@lru_cache(maxsize=1)
def get_vector_store():
    """Load FAISS index from disk. Cached — one load per server lifetime."""
    from langchain_community.vectorstores import FAISS
    embeddings = _build_embeddings()
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
    Rebuilds the full FAISS index with existing + new chunks.
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
        _build_faiss(all_chunks)
    reload_vector_store()


def run_after_delete() -> None:
    """
    Rebuild FAISS index from all remaining INGESTED documents.
    Called by DELETE /admin/documents/{id}.
    """
    chunks = _load_ingested_chunks()
    if chunks:
        _build_faiss(chunks)
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
