import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt

from app.auth import decode_token
from app.models import ChatRequest, ChatResponse, Role
from app.agent import chat as agent_chat, clear_session, _build_llm
from app.guardrails import run_guardrails, GuardrailViolation
from app.escalation_store import save_escalation

log = logging.getLogger(__name__)
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Send a message to the ReAct agent and receive a grounded answer."""
    role = Role(user["role"])

    # ── UC-14: guardrail block — separate from agent block ────────
    try:
        llm = _build_llm()
        await run_guardrails(req.message, llm)
    except GuardrailViolation as gv:
        log.warning("Guardrail blocked: layer=%s reason=%s session=%s",
                    gv.layer, gv.reason, req.session_id)
        try:
            save_escalation(
                req.session_id,
                req.message[:200],
                user["role"],
                f"guardrail_{gv.layer}_blocked",
            )
        except Exception:
            log.warning("Failed to log guardrail escalation (non-blocking)")
        raise HTTPException(
            status_code=400,
            detail={
                "answer": "I'm unable to process this request. Please rephrase "
                          "your question or contact support if you believe this "
                          "is an error.",
                "session_id": req.session_id,
                "sources": [],
            },
        )
    except Exception as exc:
        # Fail open — guardrail infrastructure errors never block users
        log.warning("Guardrail infrastructure error (fail open): %s", exc)

    # ── Agent block — only reached if guardrail passed ────────────
    try:
        result = await agent_chat(
            message=req.message,
            session_id=req.session_id,
            role=role,
        )
        return ChatResponse(**result)
    except HTTPException:
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        log.error(f"Chat error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat/clear")
async def clear_chat_endpoint(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Clear conversation memory for a session (New Chat button)."""
    clear_session(req.session_id)
    return {"cleared": req.session_id}
