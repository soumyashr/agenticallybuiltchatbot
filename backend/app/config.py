from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Master provider switch ───────────────────────────────
    # "openai" → ChatOpenAI + OpenAIEmbeddings + FAISS
    # "azure_openai" → AzureChatOpenAI + AzureOpenAIEmbeddings + Azure AI Search
    ai_provider: str = "azure_openai"

    # LLM
    llm_provider: str = "openai"          # legacy — ignored when ai_provider is set
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1

    # Embeddings
    embedding_provider: str = "openai"    # legacy — ignored when ai_provider is set
    embedding_model: str = "text-embedding-ada-002"
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"

    # Direct OpenAI (used when ai_provider=openai)
    openai_api_key: str = ""

    # Azure OpenAI (used when ai_provider=azure_openai)
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_api_version: str = "2024-08-01-preview"

    # Azure AI Search (used when ai_provider=azure_openai)
    azure_search_endpoint: str = ""
    azure_search_admin_key: str = ""
    azure_search_index: str = "hm-knowledge-hub"

    # Auth
    jwt_secret: str = "AgenticallyBuiltChatBot-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # Agent
    agent_max_iterations: int = 5
    agent_system_prompt: str = (
        "You are HM Knowledge Hub, an AI assistant for Happiest Minds Technologies. "
        "Use the semantic_search tool to find relevant information. "
        "Search once or twice maximum. Once you find relevant content, write your Final Answer immediately. "
        "Always cite: Source document name and page number. "
        "If not found after two searches, say so clearly."
    )

    # DynamoDB
    dynamo_table: str = "hm-documents"
    dynamo_region: str = "ap-south-1"

    # Data
    data_dir: str = "data"
    vector_store_dir: str = "vector_store"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retriever_top_k: int = 5
    max_history_turns: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
