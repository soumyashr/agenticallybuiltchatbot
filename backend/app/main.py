import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import init_users_db
from app.routers import auth_router, chat_router, documents_router

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
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    log.info("Starting Happiest Minds Knowledge Hub API...")
    init_users_db()
    from app.document_store import init_db
    init_db()
    log.info("Startup complete.")


app.include_router(auth_router.router,      prefix="/auth",  tags=["Auth"])
app.include_router(chat_router.router,                       tags=["Chat"])
app.include_router(documents_router.router, prefix="/admin", tags=["Admin"])


@app.get("/health", tags=["Health"])
def health() -> dict:
    return {"status": "ok", "service": "Happiest Minds Knowledge Hub"}
