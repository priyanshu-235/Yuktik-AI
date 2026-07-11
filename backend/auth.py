"""Auth service using native Google OAuth (Google Identity Services).

Flow:
  1. Frontend uses Google Identity Services (GSI) with your Google OAuth client ID.
  2. GSI returns a JWT `credential` (Google ID token) after the user picks an account.
  3. Frontend POSTs { credential } to /api/auth/google.
  4. Backend verifies the ID token against Google's public keys using google-auth,
     upserts the user, issues our own random session token, sets an httpOnly cookie.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel

# Google ID token verification
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from models import User, new_id, utcnow


SESSION_COOKIE = "session_token"
SESSION_DURATION_DAYS = 7

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _db(request: Request):
    return request.app.state.db


# --- Dependency: current user ---
async def _extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        return token
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    return None


async def get_current_user(request: Request) -> User:
    token = await _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = _db(request)
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user_doc = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user_doc)


async def optional_user(request: Request) -> Optional[User]:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


def require_role(*roles: str):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep


# --- Google login ---
class GoogleLoginBody(BaseModel):
    credential: str  # the ID token JWT returned by Google Identity Services


@router.post("/google")
async def google_login(body: GoogleLoginBody, request: Request, response: Response):
    """Verify a Google ID token, upsert the user, issue our session token."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLIENT_ID is not configured on the server. Add it to backend/.env",
        )

    # Verify the ID token against Google's public keys and our audience.
    try:
        payload = google_id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}")

    # Payload has iss, aud, email, name, picture, sub, exp, iat
    email = payload.get("email")
    if not email or not payload.get("email_verified", True):
        raise HTTPException(status_code=401, detail="Email not verified by Google")
    name = payload.get("name") or email.split("@")[0]
    picture = payload.get("picture")

    db = _db(request)

    # Upsert user; first user becomes admin
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        await db.users.update_one(
            {"email": email},
            {"$set": {"name": name, "picture": picture}},
        )
        user_id = existing["user_id"]
        role = existing.get("role", "patient")
    else:
        count = await db.users.count_documents({})
        role = "admin" if count == 0 else "patient"
        user_id = new_id("user")
        await db.users.insert_one(
            User(
                user_id=user_id,
                email=email,
                name=name,
                picture=picture,
                role=role,
            ).model_dump()
        )

    # Issue our own opaque session token (not the Google ID token)
    session_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)
    await db.user_sessions.insert_one(
        {
            "session_token": session_token,
            "user_id": user_id,
            "expires_at": expires_at,
            "created_at": utcnow(),
        }
    )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=SESSION_DURATION_DAYS * 24 * 3600,
    )

    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "role": role,
        "session_token": session_token,
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return user.model_dump()


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = await _extract_token(request)
    if token:
        await _db(request).user_sessions.delete_one({"session_token": token})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/config")
async def auth_config():
    """Public endpoint so the frontend knows which Google client id to use."""
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        "configured": bool(os.getenv("GOOGLE_CLIENT_ID", "").strip()),
    }


# --- Role management (admin only) ---
class RoleUpdate(BaseModel):
    role: str
    doctor_id: Optional[str] = None


@router.get("/users")
async def list_users(request: Request, admin: User = Depends(require_role("admin"))):
    docs = await _db(request).users.find({}, {"_id": 0}).to_list(500)
    return docs


@router.post("/users/{user_id}/role")
async def set_role(user_id: str, body: RoleUpdate, request: Request, admin: User = Depends(require_role("admin"))):
    if body.role not in ("patient", "doctor", "admin"):
        raise HTTPException(400, "Invalid role")
    update = {"role": body.role, "doctor_id": body.doctor_id if body.role == "doctor" else None}
    res = await _db(request).users.update_one({"user_id": user_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"ok": True}
