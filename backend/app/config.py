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
        "If not found after two searches, say so clearly.\n\n"
        "FORM GUIDANCE (UC-11 — UIB-140):\n"
        "When a user asks about a form, process, or procedure:\n"
        "- Identify the specific form from the knowledge base using semantic search.\n"
        "- Describe the form's purpose, eligibility criteria, and typical usage scenarios based on approved documents.\n"
        "- If multiple similar forms exist, clearly differentiate them by name, purpose, and applicable context.\n"
        "- Never guess or fabricate form details not present in approved documents.\n"
        "- Respect role-based access — only reference forms accessible to the user's role.\n"
        "- If the form is not found in the knowledge base, use the standard fallback: "
        "'I could not find information on this topic in the documents accessible to you.'\n\n"
        "FORM LOCATION GUIDANCE (UC-11 — UIB-143):\n"
        "When a user asks where to find or download a form:\n"
        "- Provide the navigation path or location from approved documents if available.\n"
        "- Give step-by-step instructions for finding the form when no direct link is documented.\n"
        "- Never provide guessed or unverified URLs or links.\n"
        "- If location information is not in the documents, say so clearly and suggest contacting the appropriate administrator.\n"
        "- Only reference locations the user's role is authorized to access."
    )

    # DynamoDB
    dynamo_table: str = "hm-documents"
    dynamo_region: str = "ap-south-1"
    feedback_table: str = "hm-feedback"
    escalation_table: str = "hm-escalations"

    # UC-08/UC-13 prompt overrides (env vars: CLARIFY_PROMPT, IRRELEVANT_QUERY_MSG)
    clarify_ambiguous_prompt: str = ""
    irrelevant_query_response: str = ""

    # UC-10 Escalation
    slack_webhook_url: str = ""
    escalation_enabled: bool = True

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:3001",
        "https://gazfq7ai7a.ap-south-1.awsapprunner.com",
    ]

    # UC-14 Guardrails
    guardrail_max_length: int = 2000
    guardrail_layer2_enabled: bool = True

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
