import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt

from app.auth import decode_token
from app.models import FeedbackRequest, FeedbackResponse
from app.feedback_store import save_feedback, get_all_feedback
from app.escalation_store import get_all_escalations

log = logging.getLogger(__name__)
router = APIRouter()
admin_router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


# ── POST /feedback — any authenticated user ──────────────────

@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    req: FeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """Save user feedback (thumbs up/down) for a chat response."""
    feedback_id = save_feedback(
        session_id=req.session_id,
        message=req.message,
        response_preview=req.response_preview,
        rating=req.rating,
        comment=req.comment,
        user_role=user.get("role", "unknown"),
    )
    return FeedbackResponse(id=feedback_id, status="saved")


# ── GET /admin/feedback — admin only ─────────────────────────

@admin_router.get("/feedback")
def list_feedback(admin: dict = Depends(require_admin)):
    """Return all feedback records (admin only)."""
    return get_all_feedback()


# ── GET /admin/escalations — admin only ──────────────────────

@admin_router.get("/escalations")
def list_escalations(admin: dict = Depends(require_admin)):
    """Return all escalation records (admin only)."""
    return get_all_escalations()
