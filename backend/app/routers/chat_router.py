import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt

from app.auth import decode_token
from app.models import ChatRequest, ChatResponse, Role
from app.agent import chat as agent_chat, clear_session

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
    try:
        role   = Role(user["role"])
        result = await agent_chat(
            message=req.message,
            session_id=req.session_id,
            role=role,
        )
        return ChatResponse(**result)
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
