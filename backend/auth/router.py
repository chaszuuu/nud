# backend/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address
import aiohttp

from db import get_db
from models.user import User
from schemas.user import UserOut, TokenOut
from auth.utils import create_access_token, decode_access_token
from config import settings

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google", auto_error=False)

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── dependencies ──────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User | None:
    """Returns user if token valid, None if guest."""
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id: str = payload.get("sub")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        return None

    return user


async def require_user(
    current_user: User | None = Depends(get_current_user)
) -> User:
    """Use this on routes that require login."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(require_user)
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user


# ── routes ────────────────────────────────────────────────────

@router.get("/google")
@limiter.limit("20/minute")
async def google_login(request: Request):
    """Redirect user to Google consent screen."""
    params = {
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback")
@limiter.limit("20/minute")
async def google_callback(
    request: Request,
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """Google redirects here with an auth code. Exchange it for a JWT."""
    if not code or len(code) > 512:
        raise HTTPException(status_code=400, detail="Invalid auth code")

    async with aiohttp.ClientSession() as session:
        # exchange code for access token
        async with session.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri":  settings.GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        }) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=502, detail="Google token exchange failed")
            token_data = await resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="No access token from Google")

        # fetch user info
        async with session.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        ) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch Google user info")
            google_user = await resp.json()

    google_id = google_user.get("sub")
    email     = google_user.get("email")
    name      = google_user.get("name", email)
    avatar    = google_user.get("picture")

    if not google_id or not email:
        raise HTTPException(status_code=502, detail="Incomplete Google user data")

    # upsert user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user:
        user.display_name = name
        user.avatar_url   = avatar
    else:
        user = User(
            google_id=google_id,
            email=email,
            display_name=name,
            avatar_url=avatar,
        )
        db.add(user)

    await db.flush()

    jwt_token = create_access_token(subject=user.id, extra={"email": user.email})
    
    # redirect to frontend with token
    return RedirectResponse(
        f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}"
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(require_user)):
    return current_user