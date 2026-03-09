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


# ── Embedding factory ────────────────────────────────────────

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
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    raise ValueError(f"Unknown AI_PROVIDER: '{provider}'")


# ── Vector store — cached in memory ─────────────────────────

@lru_cache(maxsize=1)
def get_vector_store():
    """Load vector store. Cached — one load per server lifetime."""
    provider = settings.ai_provider.lower()

    if provider == "azure_openai":
        from langchain_community.vectorstores import AzureSearch
        embeddings = _build_embeddings()
        log.info("VectorStore: Azure AI Search (index=%s)", settings.azure_search_index)
        return AzureSearch(
            azure_search_endpoint=settings.azure_search_endpoint,
            azure_search_key=settings.azure_search_admin_key,
            index_name=settings.azure_search_index,
            embedding_function=embeddings.embed_query,
        )

    # Default: FAISS
    from langchain_community.vectorstores import FAISS
    embeddings = _build_embeddings()
    vs_path = settings.vector_store_dir
    index_file = os.path.join(vs_path, "index.faiss")
    if os.path.exists(index_file):
        log.info("VectorStore: FAISS (loading from disk)")
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
    Rebuilds the full index with existing + new chunks.
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
        _build_index(all_chunks)
    reload_vector_store()


def run_after_delete() -> None:
    """
    Rebuild index from all remaining INGESTED documents.
    Called by DELETE /admin/documents/{id}.
    """
    chunks = _load_ingested_chunks()
    if chunks:
        _build_index(chunks)
    else:
        provider = settings.ai_provider.lower()
        if provider != "azure_openai":
            # Only delete local FAISS files; Azure Search index persists
            import shutil
            vs_path = settings.vector_store_dir
            if os.path.exists(vs_path):
                shutil.rmtree(vs_path)
                os.makedirs(vs_path, exist_ok=True)
        log.info("All documents deleted — index cleared.")
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


def _build_index(chunks: list) -> None:
    """Build and persist the vector index from chunks."""
    provider = settings.ai_provider.lower()
    embeddings = _build_embeddings()

    if provider == "azure_openai":
        _push_to_azure_search(chunks, embeddings)
    else:
        _build_faiss(chunks, embeddings)


def _build_faiss(chunks: list, embeddings) -> None:
    """Embed all chunks and persist FAISS index to disk."""
    from langchain_community.vectorstores import FAISS

    os.makedirs(settings.vector_store_dir, exist_ok=True)
    vs = FAISS.from_documents(chunks, embeddings)
    vs.save_local(settings.vector_store_dir)
    log.info(f"FAISS index saved: {len(chunks)} total chunks.")


def _push_to_azure_search(chunks: list, embeddings) -> None:
    """Push document chunks to Azure AI Search index (create if not exists)."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SimpleField,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        VectorSearch,
        HnswAlgorithmConfiguration,
        VectorSearchProfile,
    )
    import hashlib

    credential = AzureKeyCredential(settings.azure_search_admin_key)
    index_name = settings.azure_search_index

    # ── Create index if it doesn't exist ──────────────────
    index_client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=credential,
    )

    index_def = SearchIndex(
        name=index_name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(
                name="allowed_roles",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="default-profile",
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="default-algorithm")],
            profiles=[VectorSearchProfile(name="default-profile", algorithm_configuration_name="default-algorithm")],
        ),
    )
    index_client.create_or_update_index(index_def)
    log.info("Azure Search index '%s' ready.", index_name)

    # ── Upsert documents in batches ───────────────────────
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=index_name,
        credential=credential,
    )

    batch = []
    for i, chunk in enumerate(chunks):
        content = chunk.page_content
        source = chunk.metadata.get("source", "unknown")
        page = chunk.metadata.get("page", 0)
        roles = chunk.metadata.get("allowed_roles", [])
        if isinstance(roles, str):
            import json
            roles = json.loads(roles)

        doc_id = hashlib.sha256(f"{source}:{page}:{i}:{content[:100]}".encode()).hexdigest()[:32]
        vector = embeddings.embed_query(content)

        batch.append({
            "id": doc_id,
            "content": content,
            "source": source,
            "page": int(page) if page else 0,
            "allowed_roles": roles,
            "content_vector": vector,
        })

        if len(batch) >= 100:
            search_client.upload_documents(documents=batch)
            batch = []

    if batch:
        search_client.upload_documents(documents=batch)

    log.info("Azure Search: upserted %d chunks to index '%s'.", len(chunks), index_name)
