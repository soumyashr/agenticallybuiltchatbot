# 03 — BACKEND_CORE.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Build the FastAPI skeleton, config, models, auth, and startup.
# Do NOT build the AI layer yet (that is 04_RAG_PIPELINE.md).

---

## STEP 1 — Create Project Structure

Run these commands exactly:
```bash
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot
mkdir -p backend/app/routers
mkdir -p backend/data
mkdir -p backend/vector_store
touch backend/data/.gitkeep
touch backend/vector_store/.gitkeep
touch backend/app/__init__.py
touch backend/app/routers/__init__.py
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
```

---

## STEP 2 — requirements.txt

Write this file exactly to `backend/requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
python-dotenv==1.0.1
pydantic-settings==2.2.1
pyjwt==2.8.0
bcrypt==4.1.3
python-multipart==0.0.9
aiofiles==23.2.1
langchain==0.2.1
langchain-openai==0.1.8
langchain-ollama==0.1.1
langchain-community==0.2.1
faiss-cpu==1.8.0
pypdf==4.2.0
azure-search-documents>=11.4.0
azure-identity>=1.15.0
boto3>=1.34.0
moto[dynamodb]>=5.0.0
httpx>=0.27.0
```

Then run:
```bash
pip install -r requirements.txt
```

---

## STEP 3 — .env.example

Write to `backend/.env.example`:
```
# ── AI Provider (single flag switches LLM + embeddings + vector store) ──
AI_PROVIDER=azure_openai

# ── LLM ──────────────────────────────────────
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.1

# ── Embeddings ────────────────────────────────
EMBEDDING_MODEL=text-embedding-ada-002

# ── OpenAI (only if AI_PROVIDER=openai) ──────
OPENAI_API_KEY=sk-your-key-here

# ── Azure OpenAI (only if AI_PROVIDER=azure_openai) ─
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# ── Azure AI Search (only if AI_PROVIDER=azure_openai) ─
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_ADMIN_KEY=
AZURE_SEARCH_INDEX=

# ── Auth ─────────────────────────────────────
JWT_SECRET=AgenticallyBuiltChatBot-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8

# ── Agent ────────────────────────────────────
AGENT_MAX_ITERATIONS=5
AGENT_SYSTEM_PROMPT=You are Happiest Minds Knowledge Hub, an AI assistant for Happiest Minds Technologies internal documents. Use the semantic_search tool to find relevant information. Search once or twice maximum. Once you find relevant content, STOP searching and write your Final Answer immediately. Always cite the source document name and page number. If you cannot find information after two searches, say clearly: I could not find information on this topic in the documents accessible to you.

# ── DynamoDB ─────────────────────────────────
DYNAMO_TABLE=hm-documents
DYNAMO_REGION=ap-south-1
FEEDBACK_TABLE=hm-feedback
ESCALATION_TABLE=hm-escalations

# ── UC-08/UC-13 Prompt Overrides ─────────────
CLARIFY_PROMPT=
IRRELEVANT_QUERY_MSG=

# ── UC-10 Escalation ────────────────────────
SLACK_WEBHOOK_URL=
ESCALATION_ENABLED=true

# ── Data ─────────────────────────────────────
DATA_DIR=data
VECTOR_STORE_DIR=vector_store
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
RETRIEVER_TOP_K=5
MAX_HISTORY_TURNS=10
```

Then run:
```bash
cp .env.example .env
# User will add their OPENAI_API_KEY to .env
```

---

## STEP 4 — config.py

Write to `backend/app/config.py`:
```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # AI Provider (single flag switches LLM + embeddings + vector store)
    ai_provider: str = "azure_openai"  # "openai" or "azure_openai"

    # LLM
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1

    # Embeddings
    embedding_model: str = "text-embedding-ada-002"

    # OpenAI
    openai_api_key: str = ""

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_api_version: str = "2024-08-01-preview"

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_admin_key: str = ""
    azure_search_index: str = "hm-knowledge-hub"

    # Auth
    jwt_secret: str = "AgenticallyBuiltChatBot-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # DynamoDB
    dynamo_table: str = "hm-documents"
    dynamo_region: str = "ap-south-1"
    feedback_table: str = "hm-feedback"
    escalation_table: str = "hm-escalations"

    # UC-08/UC-13 prompt overrides
    clarify_ambiguous_prompt: str = ""
    irrelevant_query_response: str = ""

    # UC-10 Escalation
    slack_webhook_url: str = ""
    escalation_enabled: bool = True

    # Agent
    agent_max_iterations: int = 5
    agent_system_prompt: str = (
        "You are HM Knowledge Hub, an AI assistant for Happiest Minds Technologies. "
        "Use the semantic_search tool to find relevant information. "
        "Search once or twice maximum. Once you find relevant content, write your Final Answer immediately. "
        "Always cite: Source document name and page number. "
        "If not found after two searches, say so clearly."
    )

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
```

---

## STEP 5 — models.py

Write to `backend/app/models.py`:
```python
from pydantic import BaseModel
from enum import Enum
from typing import Optional, Literal


class Role(str, Enum):
    admin = "admin"
    faculty = "faculty"
    student = "student"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class ChatRequest(BaseModel):
    message: str
    session_id: str


class SourceDoc(BaseModel):
    source: str
    page: Optional[int] = None
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    role: str
    sources: list[SourceDoc]
    reasoning_steps: int


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    chunk_count: int
    error_msg: Optional[str] = None


class FeedbackRequest(BaseModel):
    session_id: str
    message: str
    response_preview: str
    rating: Literal["positive", "negative"]
    comment: str = ""


class FeedbackResponse(BaseModel):
    id: str
    status: str
```

---

## STEP 6 — auth.py

Write to `backend/app/auth.py`:
```python
import sqlite3
import logging
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.config import settings

log = logging.getLogger(__name__)
DB_PATH = "users.db"


def init_users_db() -> None:
    """Create users table and seed default users on first run."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role     TEXT NOT NULL
        )
    """)
    con.commit()
    _seed_users(con)
    con.close()
    log.info("Users DB initialised.")


def _seed_users(con: sqlite3.Connection) -> None:
    """Seed three default users if they do not already exist."""
    seeds = [
        ("admin",    "HMAdmin@2024",    "admin"),
        ("faculty1", "HMFaculty@2024",  "faculty"),
        ("student1", "HMStudent@2024",  "student"),
    ]
    for username, password, role in seeds:
        existing = con.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not existing:
            hashed = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            con.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed, role),
            )
            log.info(f"Seeded user: {username} ({role})")
    con.commit()


def verify_user(username: str, password: str) -> dict | None:
    """Return { username, role } if credentials are valid, else None."""
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT password, role FROM users WHERE username = ?", (username,)
    ).fetchone()
    con.close()
    if not row:
        return None
    stored_hash, role = row
    if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        return {"username": username, "role": role}
    return None


def create_token(username: str, role: str) -> str:
    """Issue a signed JWT token."""
    payload = {
        "sub":  username,
        "role": role,
        "exp":  datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises jwt exceptions on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
```

---

## STEP 7 — routers/auth_router.py

Write to `backend/app/routers/auth_router.py`:
```python
from fastapi import APIRouter, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.auth import verify_user, create_token
from app.models import TokenResponse

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return JWT token."""
    user = verify_user(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
        )
    token = create_token(user["username"], user["role"])
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
    )
```

---

## STEP 8 — routers/chat_router.py (Stub)

Write to `backend/app/routers/chat_router.py`:
```python
# Stub — full implementation in 05_AGENT.md
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt

from app.auth import decode_token
from app.models import ChatRequest, ChatResponse, Role, SourceDoc

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, user: dict = Depends(get_current_user)):
    """Stub — replaced in 05_AGENT.md."""
    return ChatResponse(
        answer="Agent not yet initialised. Complete 04 and 05 first.",
        session_id=req.session_id,
        role=user["role"],
        sources=[],
        reasoning_steps=0,
    )


@router.post("/chat/clear")
async def clear_chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    return {"cleared": req.session_id}
```

---

## STEP 9 — routers/documents_router.py (Stub)

Write to `backend/app/routers/documents_router.py`:
```python
# Stub — full implementation in 07_ADMIN_API.md
from fastapi import APIRouter
router = APIRouter()
```

---

## STEP 10 — main.py

Write to `backend/app/main.py`:
```python
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import init_users_db
from app.routers import auth_router, chat_router, documents_router, feedback_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI(
    title="Happiest Minds Knowledge Hub API",
    description="Happiest Minds Technologies — Internal AI Knowledge Assistant",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:3001",
        "https://c2cnjknssm.ap-south-1.awsapprunner.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    from app.config import settings
    log.info("Starting Happiest Minds Knowledge Hub API...")
    log.info("AI_PROVIDER: %s", settings.ai_provider)
    if settings.ai_provider.lower() == "azure_openai":
        log.info("LLM: Azure OpenAI")
        log.info("VectorStore: Azure AI Search")
    else:
        log.info("LLM: OpenAI")
        log.info("VectorStore: FAISS")
    init_users_db()
    from app.document_store import init_db
    init_db()
    log.info("DocumentStore: DynamoDB table '%s' in %s", settings.dynamo_table, settings.dynamo_region)
    from app.feedback_store import init_feedback_table
    from app.escalation_store import init_escalation_table
    init_feedback_table()
    init_escalation_table()
    log.info("Startup complete.")


app.include_router(auth_router.router,      prefix="/auth",  tags=["Auth"])
app.include_router(chat_router.router,                       tags=["Chat"])
app.include_router(documents_router.router,        prefix="/admin", tags=["Admin"])
app.include_router(documents_router.public_router,                  tags=["Documents"])
app.include_router(feedback_router.router,                          tags=["Feedback"])
app.include_router(feedback_router.admin_router,   prefix="/admin", tags=["Admin"])


@app.get("/health", tags=["Health"])
def health() -> dict:
    return {"status": "ok", "service": "Happiest Minds Knowledge Hub"}
```

---

## STEP 11 — Start the Server

```bash
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

---

## Deployment Prerequisites — DynamoDB Tables

The App Runner IAM role (`apprunner-hm-instance-role`) does **NOT** have
`dynamodb:CreateTable`. Before deploying, for each DynamoDB table
(`hm-documents`, `hm-feedback`, `hm-escalations`):

1. **Create the table manually via AWS CLI:**
   ```bash
   aws dynamodb create-table \
     --table-name <TABLE_NAME> \
     --attribute-definitions AttributeName=id,AttributeType=S \
     --key-schema AttributeName=id,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region ap-south-1
   ```

2. **Add the table ARN to the `DynamoDBAccess` inline policy** on
   `apprunner-hm-instance-role`:
   ```
   arn:aws:dynamodb:ap-south-1:*:table/<TABLE_NAME>
   ```

See `10_AWS_DEPLOY.md` for the full IAM policy JSON.

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL. Fix all FAILs before moving to 04.

- [ ] `GET http://localhost:8000/health` returns `{"status":"ok","service":"Happiest Minds Knowledge Hub"}`
- [ ] `POST http://localhost:8000/auth/token` with admin / HMAdmin@2024 returns JSON with `access_token`, `username`, `role`
- [ ] `role` field in token response is exactly `"admin"` (not "ADMIN", not "Admin")
- [ ] `POST http://localhost:8000/auth/token` with wrong password returns 401
- [ ] `POST http://localhost:8000/auth/token` with faculty1 / HMFaculty@2024 returns `"role": "faculty"`
- [ ] `POST http://localhost:8000/auth/token` with student1 / HMStudent@2024 returns `"role": "student"`
- [ ] File `backend/users.db` exists and contains 3 rows
- [ ] Swagger UI loads at `http://localhost:8000/docs`
- [ ] No import errors in terminal output
- [ ] Server restarts cleanly after `Ctrl+C` and `uvicorn app.main:app --reload --port 8000`
